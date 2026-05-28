"""Forensic Analyst party agent wrapper for Compliance Academy.

Wraps the Forensic Analyst party agent (defined by
``prompts/party/forensic_analyst.md``) with a Python interface. The Forensic
Analyst is the loudest reasoning voice on the investigator party: she reads
the technical evidence, cites framework controls, and pushes back when other
party members or the player jump to conclusions.

For the MVP, this wrapper passes the scenario context (evidence seeds,
violated controls, involved systems, premise) into the user message rather
than retrieving from Foundry IQ. Live Azure AI Search retrieval can be added
later as a tool. The scenario already contains enough grounded synthetic
content for the analyst to cite specific identifiers verbatim.

Architecture:
    The Forensic Analyst is invoked by the Game Master (or directly by the
    orchestrator during the demo) when a question involves logs, anomalies,
    reconstruction of events, or framework citation. Unlike suspect agents,
    she is on the player's team and reasons in their interest.

Public API:
    consult_forensic_analyst(scenario, player_message, **opts) -> dict
        One turn of analyst consultation. Returns her analysis plus timing
        metadata.

Exceptions:
    ForensicAnalystError
        Raised for any failure (env not configured, API failure, content
        filter exhausted, empty response).

CLI:
    Running this module as a script loads the default Helix Dynamics scenario
    and asks the analyst a sample question. Useful as a smoke test:

        python -m src.agents.forensic_analyst
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Preferred deployment. The Forensic Analyst is in the prompt's "Quality"
#: routing tier, so a reasoning model would be ideal. For MVP we use the
#: same gpt-4.1-mini default for predictable latency; switching to
#: o4-mini or gpt-5 for live battle is a one-env-var change.
DEFAULT_DEPLOYMENT: str = "gpt-4.1-mini"

#: Cap on response length. Analyst turns are longer than suspect turns
#: because she walks an inference chain (observe -> reason -> cite).
#: ~150-400 words, with citations.
DEFAULT_MAX_TOKENS: int = 1500

#: Sampling temperature. Lower than dialogue because we want consistent
#: reasoning and accurate citations, not stylistic variation.
DEFAULT_TEMPERATURE: float = 0.4

#: Default content-filter retry budget.
DEFAULT_MAX_RETRIES: int = 1

#: Path to the Forensic Analyst system prompt.
PROMPT_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts" / "party" / "forensic_analyst.md"
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ForensicAnalystError(Exception):
    """Raised for any Forensic Analyst agent failure."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_violated_controls(controls: list[dict[str, Any]]) -> str:
    """Render the violated_controls list as a citation reference block."""
    if not controls:
        return "(no controls cited in scenario)"
    lines = []
    for c in controls:
        framework = c.get("framework", "?")
        identifier = c.get("identifier", "?")
        summary = c.get("summary", "")
        lines.append(f"- {framework} {identifier}: {summary}")
    return "\n".join(lines)


def _format_evidence_seeds(evidence: list[dict[str, Any]]) -> str:
    """Render the evidence_seeds list as a numbered reference block.

    The analyst uses these as her source material. Each item is one piece
    of evidence she can quote, cross-reference, or push back on.
    """
    if not evidence:
        return "(no evidence seeds in scenario)"
    lines = []
    for e in evidence:
        eid = e.get("evidence_id", "?")
        source = e.get("source", "?")
        content = e.get("content", "")
        value = e.get("value", "?")
        supports = e.get("supports_suspect", "?")
        lines.append(
            f"[{eid}] source={source} | value={value}/10 | "
            f"supports={supports}\n    {content}"
        )
    return "\n".join(lines)


def _format_suspect_summary(suspects: list[dict[str, Any]]) -> str:
    """Render a concise suspect roster the analyst can reference by name."""
    lines = []
    for s in suspects:
        sid = s.get("suspect_id", "?")
        name = s.get("name", "?")
        role = s.get("role", "?")
        lines.append(f"- {name} ({sid}): {role}")
    return "\n".join(lines)


def _build_user_message(scenario: dict[str, Any], player_message: str) -> str:
    """Compose the user-side message giving the analyst her case context.

    The first turn includes the full scenario briefing. Follow-up turns
    in a multi-turn conversation will rely on conversation_history for
    continuity; the briefing is repeated only on turn one.
    """
    return (
        "Case briefing (provided once at the start of the consultation):\n\n"
        f"## Case: {scenario.get('scenario_name', '?')} "
        f"({scenario.get('scenario_id', '?')})\n\n"
        f"### Premise\n{scenario.get('premise_narration', '')}\n\n"
        f"### Suspects\n{_format_suspect_summary(scenario.get('suspects', []))}\n\n"
        f"### Evidence available to you\n"
        f"{_format_evidence_seeds(scenario.get('evidence_seeds', []))}\n\n"
        f"### Violated controls (framework picture)\n"
        f"{_format_violated_controls(scenario.get('violated_controls', []))}\n\n"
        f"### Involved systems\n"
        f"{', '.join(scenario.get('involved_systems', []))}\n\n"
        "---\n\n"
        f"Investigator's question or instruction:\n{player_message}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def consult_forensic_analyst(
    scenario: dict[str, Any],
    player_message: str,
    *,
    conversation_history: list[dict[str, str]] | None = None,
    deployment: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    stream_to_stdout: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Run one turn of consultation with the Forensic Analyst.

    Args:
        scenario: A merged scenario dict (output of scenario_loader).
        player_message: The investigator's question or instruction.
        conversation_history: Prior turns in this consultation, in OpenAI
            messages format. Pass None or empty for the first turn; the
            scenario briefing is included on every call so the analyst
            does not lose context across turns.
        deployment: Optional explicit deployment override.
        max_tokens: Cap on response length. Default 1500.
        temperature: Sampling temperature. Default 0.4 (lower than dialogue
            because we want consistent reasoning and accurate citations).
        stream_to_stdout: If True, write chunks to stdout as they arrive.
        max_retries: Retry budget on content filter triggers. Default 1.

    Returns:
        A dict with five keys:
            - ``reply`` (str): the analyst's response
            - ``elapsed_seconds`` (float): wall-clock of final successful call
            - ``deployment`` (str): resolved deployment name
            - ``attempts`` (int): number of model calls made
            - ``scenario_id`` (str): convenience field

    Raises:
        ForensicAnalystError: For any failure.
    """
    if not player_message or not player_message.strip():
        raise ForensicAnalystError("player_message must be a non-empty string")

    deployment = resolve_deployment(
        deployment,
        "FORENSIC_ANALYST_DEPLOYMENT",
        "PARTY_AGENT_DEPLOYMENT",
        "AZURE_AI_CHAT_DEPLOYMENT",
        default=DEFAULT_DEPLOYMENT,
    )

    try:
        client = build_azure_client()
        system_prompt = load_prompt(PROMPT_PATH)
    except AgentClientError as exc:
        raise ForensicAnalystError(str(exc)) from exc

    user_message = _build_user_message(scenario, player_message)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    reply_text = ""
    elapsed = 0.0
    finish_reason: str | None = None
    attempts = 0

    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        is_retry = attempt > 0
        if is_retry and stream_to_stdout:
            sys.stdout.write(
                f"\n[Azure content filter triggered, retrying "
                f"({attempt}/{max_retries})...]\n"
            )
            sys.stdout.flush()

        start = time.monotonic()
        parts: list[str] = []
        finish_reason = None

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
                parts.append(content)
                if stream_to_stdout:
                    sys.stdout.write(content)
                    sys.stdout.flush()
        except Exception as exc:
            raise ForensicAnalystError(
                f"Azure OpenAI request to deployment '{deployment}' failed: {exc}"
            ) from exc

        if stream_to_stdout:
            sys.stdout.write("\n")
            sys.stdout.flush()

        elapsed = time.monotonic() - start
        reply_text = "".join(parts)

        if finish_reason == "content_filter" and attempt < max_retries:
            continue
        break

    if finish_reason and finish_reason != "stop":
        if finish_reason == "content_filter":
            raise ForensicAnalystError(
                f"Azure content filter triggered on all {attempts} attempt(s). "
                f"Consider rephrasing the question or relaxing the deployment's "
                f"content filter."
            )
        if finish_reason == "length":
            raise ForensicAnalystError(
                f"Analyst response truncated by max_tokens cap ({max_tokens}). "
                f"Consider increasing max_tokens for this consultation."
            )
        raise ForensicAnalystError(
            f"Analyst stream terminated unexpectedly: finish_reason='{finish_reason}'"
        )

    if not reply_text.strip():
        raise ForensicAnalystError(
            f"Analyst returned empty response. Deployment: {deployment}, "
            f"elapsed: {elapsed:.1f}s, attempts: {attempts}"
        )

    return {
        "reply": reply_text.strip(),
        "elapsed_seconds": elapsed,
        "deployment": deployment,
        "attempts": attempts,
        "scenario_id": scenario.get("scenario_id", "?"),
    }


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


SAMPLE_SCENARIO_NAME: str = "helix_dynamics_default"
SAMPLE_PLAYER_MESSAGE: str = (
    "Walk me through the evidence we have so far. What does the access log "
    "pattern actually tell us about who was where during the breach window, "
    "and which framework control is most clearly implicated?"
)


def _smoke_test() -> int:
    """Load the default scenario and consult the analyst with a sample question.

    Returns 0 on success, 1 on any failure.
    """
    print("Compliance Academy Forensic Analyst smoke test")
    print(f"Prompt:       {PROMPT_PATH}")
    print(f"Scenario:     {SAMPLE_SCENARIO_NAME}")
    print("=" * 78)
    print(f"Player question:")
    print(f"  {SAMPLE_PLAYER_MESSAGE}")
    print("=" * 78)

    try:
        scenario = load_scenario_by_name(SAMPLE_SCENARIO_NAME)
    except (ScenarioLoadError, ScenarioValidationError) as exc:
        print(f"FAIL: could not load scenario '{SAMPLE_SCENARIO_NAME}': {exc}")
        return 1

    print(f"Loaded scenario: {scenario['scenario_name']!r}")
    print(f"Evidence items: {len(scenario['evidence_seeds'])}")
    print(f"Violated controls: {len(scenario['violated_controls'])}")
    print("-" * 78)
    print("Streaming analyst response below.")
    print("-" * 78)

    start = time.monotonic()
    try:
        result = consult_forensic_analyst(
            scenario,
            SAMPLE_PLAYER_MESSAGE,
            stream_to_stdout=True,
        )
    except ForensicAnalystError as exc:
        elapsed = time.monotonic() - start
        print()
        print("-" * 78)
        print(f"FAIL after {elapsed:.1f}s: {exc}")
        return 1

    print("-" * 78)
    print()
    if result["attempts"] > 1:
        print(f"OK    Consultation completed after {result['attempts']} attempts "
              f"(content filter retry succeeded)")
        print(f"      Final attempt: {result['elapsed_seconds']:.1f}s")
    else:
        print(f"OK    Consultation completed in {result['elapsed_seconds']:.1f}s")
    print(f"      deployment={result['deployment']}")
    print(f"      reply_length={len(result['reply'])} chars")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
