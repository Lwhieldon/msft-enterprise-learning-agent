"""Suspect agent wrapper for Compliance Academy.

Instantiates a suspect NPC by injecting the suspect's persona configuration
into the reusable suspect template prompt. Handles multi-turn interrogation
with conversation history maintained by the orchestrator.

Architecture:
    The suspect template at ``prompts/suspects/_template.md`` is a single
    reusable prompt with ``{{variable}}`` placeholders that get substituted
    per suspect at invocation time. The merged scenario dict (output of
    ``scenario_loader.load_scenario``) contains the per-suspect override data
    needed to fill those placeholders.

    Variable mapping (template placeholder -> merged scenario field):
        {{name}}                 -> suspect["name"]
        {{role}}                 -> suspect["role"] (= override["specific_role"])
        {{premise}}              -> scenario["premise_narration"]
        {{backstory}}            -> suspect["backstory"] (merged)
        {{open_knowledge}}       -> suspect["open_knowledge"]
        {{guarded_knowledge}}    -> suspect["guarded_knowledge"]
        {{hidden_truth}}         -> suspect["hidden_truth"]
        {{alibi}}                -> suspect["alibi"]
        {{conversational_style}} -> suspect["conversational_style"] (merged)
        {{style_examples}}       -> rendered from suspect["voice_examples"]
        {{leak_conditions}}      -> rendered from suspect["leak_conditions"]
        {{starting_trust}}       -> suspect["starting_trust"]

Performance notes:
    Suspect turns are 2-5 sentences (50-200 tokens) so cap is much lower
    than the scenario generator. Temperature is higher (0.7) to give dialogue
    natural variation. Latency target is sub-10 seconds per turn for
    interactive pacing on stream.

Public API:
    interrogate_suspect(scenario, suspect_id, player_message, **opts) -> dict
        Run one turn of interrogation. Returns the suspect's reply plus
        timing metadata.

Exceptions:
    SuspectAgentError
        Base exception for suspect agent failures (missing suspect, env
        problems, API errors, content filter exhausted).

CLI:
    Running this module as a script loads the default Helix Dynamics scenario
    and runs a sample interrogation against Casey Doyle. Useful as a smoke
    test for the prompt template and the Azure connection:

        python -m src.agents.suspect_agent
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from src.scenario_loader import (
    ScenarioLoadError,
    ScenarioValidationError,
    load_scenario_by_name,
)
from src.agents._azure_client import (
    AgentClientError,
    build_azure_client,
    load_prompt,
    resolve_deployment,
)
from src.activity_log import emit as _emit, log_line as _log_line

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Preferred deployment for suspect dialogue. gpt-4.1-mini handles persona
#: dialogue cleanly and stays fast (~3-8s per turn). The orchestrator can
#: override per-call if needed.
DEFAULT_DEPLOYMENT: str = "gpt-4.1-mini"

#: Cap on response length. Suspect turns are 2-5 sentences normally, longer
#: when a leak condition triggers and the suspect stumbles. 600 tokens
#: accommodates the longer leaked-truth case while keeping turns snappy.
DEFAULT_MAX_TOKENS: int = 600

#: Sampling temperature. Higher than the scenario generator because dialogue
#: benefits from variation in word choice and pause patterns.
DEFAULT_TEMPERATURE: float = 0.7

#: Default content-filter retry budget. Same rationale as scenario_generator:
#: Azure's filter is stochastic, a single retry usually clears.
DEFAULT_MAX_RETRIES: int = 1

#: Path to the reusable suspect template, resolved from this file's location.
TEMPLATE_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts" / "suspects" / "_template.md"
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SuspectAgentError(Exception):
    """Raised for any suspect agent failure."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_suspect(scenario: dict[str, Any], suspect_id: str) -> dict[str, Any]:
    """Locate a suspect by canonical ID in a merged scenario dict.

    Args:
        scenario: A merged scenario dict (output of load_scenario).
        suspect_id: One of the five canonical IDs.

    Returns:
        The suspect dict.

    Raises:
        SuspectAgentError: If the suspect_id is not present in the scenario.
    """
    for suspect in scenario.get("suspects", []):
        if suspect.get("suspect_id") == suspect_id:
            return suspect
    available = [s.get("suspect_id") for s in scenario.get("suspects", [])]
    raise SuspectAgentError(
        f"Suspect '{suspect_id}' not found in scenario "
        f"'{scenario.get('scenario_id', '?')}'. Available: {available}"
    )


def _render_bullet_list(items: list[str], empty_fallback: str) -> str:
    """Render a list of strings as a markdown bullet list.

    Args:
        items: List of strings to render.
        empty_fallback: Text to return if items is empty.

    Returns:
        A multi-line string with each item on its own line prefixed by '- '.
    """
    if not items:
        return empty_fallback
    return "\n".join(f"- {item}" for item in items)


def _build_system_prompt(template: str, suspect: dict[str, Any],
                         scenario: dict[str, Any]) -> str:
    """Substitute all {{ }} placeholders in the suspect template.

    Note that the template file contains both the system prompt body AND
    surrounding markdown sections (Default Suspect Configurations table,
    heading hierarchy, etc.). We pass the whole file as the system prompt
    rather than trying to slice out just the "System Prompt Template"
    section, because the surrounding context (Voice Rules, What You Do Not
    Do, Safety Rules, Length and Pace) is also instructional and belongs in
    the system prompt.

    Args:
        template: The raw text of _template.md.
        suspect: The merged suspect dict from the scenario.
        scenario: The full merged scenario dict (for premise injection).

    Returns:
        The substituted system prompt ready to send to the model.
    """
    style_examples = _render_bullet_list(
        suspect.get("voice_examples", []),
        empty_fallback="(use your conversational style as guidance; no scenario-specific quotes)",
    )
    leak_conditions = _render_bullet_list(
        suspect.get("leak_conditions", []),
        empty_fallback=(
            "No specific leak conditions for this scenario. Remain in character "
            "throughout the interview. You do not have a hidden truth to leak "
            "unless the investigator presents something that genuinely surprises you."
        ),
    )

    substitutions: dict[str, str] = {
        "{{name}}": str(suspect.get("name", "")),
        "{{role}}": str(suspect.get("role", "")),
        "{{premise}}": str(scenario.get("premise_narration", "")),
        "{{backstory}}": str(suspect.get("backstory", "")),
        "{{open_knowledge}}": str(suspect.get("open_knowledge", "")),
        "{{guarded_knowledge}}": str(suspect.get("guarded_knowledge", "")),
        "{{hidden_truth}}": str(suspect.get("hidden_truth", "")),
        "{{alibi}}": str(suspect.get("alibi", "")),
        "{{conversational_style}}": str(suspect.get("conversational_style", "")),
        "{{style_examples}}": style_examples,
        "{{leak_conditions}}": leak_conditions,
        "{{starting_trust}}": str(suspect.get("starting_trust", "")),
    }

    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def interrogate_suspect(
    scenario: dict[str, Any],
    suspect_id: str,
    player_message: str,
    *,
    conversation_history: list[dict[str, str]] | None = None,
    deployment: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    stream_to_stdout: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Run one turn of interrogation against a suspect.

    Args:
        scenario: A merged scenario dict (output of scenario_loader.load_scenario
            or scenario_generator.generate_scenario followed by load_scenario_from_dict).
        suspect_id: Canonical suspect ID, one of alex_chen, morgan_webb,
            riley_park, casey_doyle, jordan_smith.
        player_message: The investigator's latest question or statement.
        conversation_history: Prior turns of dialogue with this suspect,
            in OpenAI messages format (list of {"role": ..., "content": ...}).
            Pass None or empty list for the first turn.
        deployment: Optional explicit deployment override. Resolves via env
            vars otherwise. Defaults to gpt-4.1-mini.
        max_tokens: Cap on response length. Default 600.
        temperature: Sampling temperature. Default 0.7.
        stream_to_stdout: If True, write each streamed chunk to stdout as it
            arrives. Used by the CLI smoke test.
        max_retries: Retry budget when Azure content filter triggers
            mid-stream. Default 1.

    Returns:
        A dict with six keys:
            - ``reply`` (str): the suspect's response text
            - ``suspect_name`` (str): convenience field
            - ``suspect_id`` (str): the canonical ID
            - ``elapsed_seconds`` (float): wall-clock time of the final
              successful call (excludes aborted retries)
            - ``deployment`` (str): the resolved deployment name
            - ``attempts`` (int): how many model calls were made

    Raises:
        SuspectAgentError: For any failure (missing suspect, env not configured,
            API failure, content filter exhausted, empty response).
    """
    if not player_message or not player_message.strip():
        raise SuspectAgentError("player_message must be a non-empty string")

    suspect = _find_suspect(scenario, suspect_id)

    # Visual separator + scope header for this interrogation in the activity log.
    _log_line("")
    _question_preview = (
        player_message if len(player_message) < 100
        else player_message[:97] + "..."
    )
    _emit(
        "Agent",
        f"Interrogating {suspect.get('name', suspect_id)}",
        scenario=scenario.get("scenario_id", "?"),
        suspect=suspect_id,
        question=_question_preview,
    )

    deployment = resolve_deployment(
        deployment,
        "SUSPECT_AGENT_DEPLOYMENT",
        "AZURE_AI_CHAT_DEPLOYMENT",
        default=DEFAULT_DEPLOYMENT,
    )

    try:
        client = build_azure_client()
        template = load_prompt(TEMPLATE_PATH)
    except AgentClientError as exc:
        _emit("Error", f"Client/template setup failed: {exc}")
        raise SuspectAgentError(str(exc)) from exc

    system_prompt = _build_system_prompt(template, suspect, scenario)
    _emit(
        "Agent",
        f"Built persona-specific system prompt ({len(system_prompt)} chars)",
        template=TEMPLATE_PATH.name,
        persona=suspect.get("name", suspect_id),
    )

    # Build the messages list: system + prior history + new player message.
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": player_message})

    # Streaming loop with retry on content_filter, mirroring scenario_generator.
    reply_text = ""
    elapsed = 0.0
    finish_reason: str | None = None
    attempts = 0

    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        is_retry = attempt > 0
        if is_retry:
            _emit(
                "Agent",
                f"Retrying after content filter ({attempt}/{max_retries})",
            )
            if stream_to_stdout:
                sys.stdout.write(
                    f"\n[Azure content filter triggered, retrying "
                    f"({attempt}/{max_retries})...]\n"
                )
                sys.stdout.flush()

        _emit(
            "Azure OpenAI",
            f"POST {deployment}",
            max_tokens=max_tokens,
            temp=temperature,
        )
        start = time.monotonic()
        parts: list[str] = []
        finish_reason = None
        first_token_time: float | None = None

        try:
            stream = client.chat.completions.create(
                model=deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                content = getattr(choice.delta, "content", None)
                if not content:
                    continue
                if first_token_time is None:
                    first_token_time = time.monotonic()
                    first_token_ms = int(
                        (first_token_time - start) * 1000
                    )
                    _emit(
                        "Azure OpenAI",
                        f"First token in {first_token_ms}ms",
                    )
                parts.append(content)
                if stream_to_stdout:
                    sys.stdout.write(content)
                    sys.stdout.flush()
        except Exception as exc:
            _emit(
                "Error",
                f"Azure OpenAI request failed: {exc}",
                deployment=deployment,
            )
            raise SuspectAgentError(
                f"Azure OpenAI request to deployment '{deployment}' failed: {exc}"
            ) from exc

        if stream_to_stdout:
            sys.stdout.write("\n")
            sys.stdout.flush()

        elapsed = time.monotonic() - start
        reply_text = "".join(parts)
        approx_tokens = len(reply_text) // 4
        _emit(
            "Azure OpenAI",
            f"Stream complete: ~{approx_tokens} tokens in {elapsed:.1f}s",
            finish_reason=finish_reason or "unknown",
        )

        if finish_reason == "content_filter" and attempt < max_retries:
            continue
        break

    if finish_reason and finish_reason != "stop":
        if finish_reason == "content_filter":
            raise SuspectAgentError(
                f"Azure content filter triggered on all {attempts} attempt(s) "
                f"for suspect '{suspect_id}'. The player's question may have "
                f"hit a filter category. Consider rephrasing or relaxing the "
                f"deployment's content filter."
            )
        if finish_reason == "length":
            raise SuspectAgentError(
                f"Suspect response truncated by max_tokens cap ({max_tokens}). "
                f"The suspect was mid-sentence at cutoff. Consider increasing "
                f"max_tokens for this turn."
            )
        raise SuspectAgentError(
            f"Suspect response stream terminated unexpectedly: "
            f"finish_reason='{finish_reason}'"
        )

    if not reply_text.strip():
        raise SuspectAgentError(
            f"Suspect '{suspect_id}' returned empty response. "
            f"Deployment: {deployment}, elapsed: {elapsed:.1f}s, attempts: {attempts}"
        )

    _emit(
        "Agent",
        f"{suspect.get('name', suspect_id)} returned {len(reply_text)} chars",
        elapsed=f"{elapsed:.1f}s",
        attempts=attempts,
    )
    return {
        "reply": reply_text.strip(),
        "suspect_name": suspect.get("name", suspect_id),
        "suspect_id": suspect_id,
        "elapsed_seconds": elapsed,
        "deployment": deployment,
        "attempts": attempts,
    }


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


SAMPLE_SCENARIO_NAME: str = "helix_dynamics_default"
SAMPLE_SUSPECT_ID: str = "casey_doyle"
SAMPLE_PLAYER_MESSAGE: str = (
    "Thanks for coming in, Casey. I just have a few questions. Where were you "
    "Sunday night between 8 PM and midnight? I'm trying to nail down the timeline."
)


def _smoke_test() -> int:
    """Load the default scenario and run one interrogation turn against Casey.

    Returns 0 on success, 1 on any failure.
    """
    print("Compliance Academy Suspect Agent smoke test")
    print(f"Template:     {TEMPLATE_PATH}")
    print(f"Scenario:     {SAMPLE_SCENARIO_NAME}")
    print(f"Suspect:      {SAMPLE_SUSPECT_ID}")
    print("=" * 78)
    print(f"Player message:")
    print(f"  {SAMPLE_PLAYER_MESSAGE}")
    print("=" * 78)

    try:
        scenario = load_scenario_by_name(SAMPLE_SCENARIO_NAME)
    except (ScenarioLoadError, ScenarioValidationError) as exc:
        print(f"FAIL: could not load scenario '{SAMPLE_SCENARIO_NAME}': {exc}")
        return 1

    print(f"Loaded scenario: {scenario['scenario_name']!r}")
    suspect = _find_suspect(scenario, SAMPLE_SUSPECT_ID)
    print(f"Suspect: {suspect['name']} ({suspect['role']})")
    print(f"Conversational style: {suspect['conversational_style'][:100]}...")
    print("-" * 78)
    print("Streaming suspect response below. First tokens should appear in 3-5 seconds.")
    print("-" * 78)

    start = time.monotonic()
    try:
        result = interrogate_suspect(
            scenario,
            SAMPLE_SUSPECT_ID,
            SAMPLE_PLAYER_MESSAGE,
            stream_to_stdout=True,
        )
    except SuspectAgentError as exc:
        elapsed = time.monotonic() - start
        print()
        print("-" * 78)
        print(f"FAIL after {elapsed:.1f}s: {exc}")
        return 1

    print("-" * 78)
    print()
    if result["attempts"] > 1:
        print(f"OK    Interrogation turn completed after {result['attempts']} attempts "
              f"(content filter retry succeeded)")
        print(f"      Final attempt: {result['elapsed_seconds']:.1f}s")
    else:
        print(f"OK    Interrogation turn completed in {result['elapsed_seconds']:.1f}s")
    print(f"      deployment={result['deployment']}")
    print(f"      suspect={result['suspect_name']} ({result['suspect_id']})")
    print(f"      reply_length={len(result['reply'])} chars")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
