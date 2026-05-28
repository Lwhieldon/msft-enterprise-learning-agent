"""Compliance Officer post-scene closer for Compliance Academy.

Wraps the Compliance Officer agent (defined by ``prompts/compliance_officer.md``)
with a Python interface. The Compliance Officer is the final beat of every
case: she steps out of the investigation fiction at Act 4 to deliver the
post-game lesson that turns the scenario into actual training.

This is the demo's closer. After the player accuses a suspect (correctly or
incorrectly), the orchestrator invokes this agent to deliver the framework
citation, the Helix Dynamics policy reference, and the practical takeaway
the audience can action in their own organization.

Grounding:
    The wrapper passes the scenario's compliance_lesson and violated_controls
    directly into the user message. It also retrieves additional policy and
    framework passages live from the Foundry IQ Azure AI Search index
    (``compliance-content-index``) and injects them into the user message
    as additional source material. The retrieval query is built from the
    scenario's violated control identifiers (rather than the player's
    accusation) since the CO is invoked at scene close and the relevant
    grounding is the framework picture, not any specific player question.

    Retrieval is on by default but degrades gracefully: if Azure Search is
    unavailable or auth fails, the wrapper continues using scenario-only
    context. The scenario JSON's compliance_lesson contains enough
    substantive material for the CO to function; retrieval is enhancement,
    not requirement.

Architecture:
    The CO is invoked once per scene close. The wrapper takes the scenario,
    the player's accusation (or None if no accusation was made), and an
    outcome label that tells the agent how to calibrate tone.

Outcome labels:
    - 'correct': player accused the actual perpetrator
    - 'wrong_perpetrator': player accused someone other than the perpetrator
    - 'no_accusation': player ended the scene without naming anyone
    The agent calibrates per the prompt's "Tone Calibration" section.

Public API:
    deliver_closer(scenario, accused_suspect_id, outcome, **opts) -> dict
        One closing speech. Returns the speech plus timing metadata and
        retrieval count.

Exceptions:
    ComplianceOfficerError
        Raised for any model-side failure. NOT raised for Azure Search
        failures — those degrade silently.

CLI:
    Running this module as a script loads the default scenario and runs the
    closer for a 'correct' accusation against Riley Park (the actual
    perpetrator of the default scenario):

        python -m src.agents.compliance_officer
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Literal

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
from src.agents._search_client import (
    SearchClientError,
    format_retrieved_context,
    retrieve_context,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Preferred deployment. The CO is "Balanced" routing per her prompt; we
#: use the shared default gpt-4.1-mini for predictability.
DEFAULT_DEPLOYMENT: str = "gpt-4.1-mini"

#: Cap on response length. The CO delivers 250-400 words per her prompt;
#: 1500 tokens accommodates that comfortably without truncation risk.
DEFAULT_MAX_TOKENS: int = 1500

#: Sampling temperature. Lower than dialogue so the framework citations stay
#: accurate and the tone stays professional.
DEFAULT_TEMPERATURE: float = 0.4

#: Default content-filter retry budget.
DEFAULT_MAX_RETRIES: int = 1

#: Path to the Compliance Officer system prompt.
PROMPT_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts" / "compliance_officer.md"
)

#: Allowed outcome labels. Used to calibrate the CO's tone per her prompt.
ComplianceOutcome = Literal["correct", "wrong_perpetrator", "no_accusation"]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ComplianceOfficerError(Exception):
    """Raised for any Compliance Officer agent failure."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_outcome_briefing(scenario: dict[str, Any],
                             accused_suspect_id: str | None,
                             outcome: ComplianceOutcome) -> str:
    """Compose the outcome-specific framing for the CO as PURE DATA.

    Important: this function used to include meta-instructions like "Calibrate
    per the prompt's guidance..." which triggered Azure's jailbreak detector
    on the prompt (the detector flags user messages that talk about the
    system prompt). Now we provide only facts (who was accused, who was the
    actual perpetrator, did the player get it right) and let the system
    prompt's tone calibration section handle the rest.
    """
    suspects = scenario.get("suspects", [])
    perpetrator = next(
        (s for s in suspects if s.get("is_perpetrator")), None
    )
    perp_name = perpetrator.get("name", "?") if perpetrator else "?"
    perp_role = perpetrator.get("role", "?") if perpetrator else "?"

    if accused_suspect_id:
        accused = next(
            (s for s in suspects if s.get("suspect_id") == accused_suspect_id),
            None,
        )
        accused_name = accused.get("name", accused_suspect_id) if accused else accused_suspect_id
        accused_role = accused.get("role", "?") if accused else "?"
        accused_was_red_herring = (
            bool(accused.get("is_red_herring", False)) if accused else False
        )
    else:
        accused_name = None
        accused_role = None
        accused_was_red_herring = False

    if outcome == "correct":
        return (
            f"Actual perpetrator: {perp_name} ({perp_role}).\n"
            f"Player's accusation: {accused_name} ({accused_role}).\n"
            f"Result: correct identification."
        )
    if outcome == "wrong_perpetrator":
        herring_note = (
            " The accused suspect was a red herring whose policy violation was "
            "real but separate from the breach."
            if accused_was_red_herring else ""
        )
        return (
            f"Actual perpetrator: {perp_name} ({perp_role}).\n"
            f"Player's accusation: {accused_name} ({accused_role}).\n"
            f"Result: incorrect identification.{herring_note}"
        )
    # no_accusation
    return (
        f"Actual perpetrator: {perp_name} ({perp_role}).\n"
        f"Player ended the scene without naming a perpetrator."
    )


def _format_violated_controls(controls: list[dict[str, Any]]) -> str:
    """Render violated_controls as a citation reference for the CO."""
    if not controls:
        return "(no controls cited in scenario)"
    lines = []
    for c in controls:
        framework = c.get("framework", "?")
        identifier = c.get("identifier", "?")
        summary = c.get("summary", "")
        lines.append(f"- {framework} {identifier}: {summary}")
    return "\n".join(lines)


def _build_user_message(scenario: dict[str, Any],
                       accused_suspect_id: str | None,
                       outcome: ComplianceOutcome,
                       retrieved_context: str = "") -> str:
    """Compose the user-side message giving the CO the case briefing.

    The message provides only data: case identifiers, the outcome facts,
    the violated controls (citation source material), the lesson seed
    text, and optionally a block of policy passages retrieved live from
    Foundry IQ. The system prompt at ``compliance_officer.md`` defines
    structure, tone, and length; we deliberately do not re-state those
    rules in the user message because doing so triggered Azure's
    jailbreak detector (which flags user messages that reference the
    system prompt). The retrieval section uses the same pure-data shape
    — it presents passages as labeled source material with no behavioral
    instructions.

    Args:
        scenario: A merged scenario dict.
        accused_suspect_id: The suspect_id the player accused, or None.
        outcome: 'correct' | 'wrong_perpetrator' | 'no_accusation'.
        retrieved_context: Optional pre-formatted text block of passages
            retrieved live from Foundry IQ. When non-empty, injected as
            an additional source-material section. When empty (default),
            no retrieval section is included — preserves backward
            compatibility for callers that do not use Foundry IQ.
    """
    base = (
        f"Case: {scenario.get('scenario_name', '?')} "
        f"({scenario.get('scenario_id', '?')})\n\n"
        f"## Case outcome\n\n{_format_outcome_briefing(scenario, accused_suspect_id, outcome)}\n\n"
        f"## Violated controls\n\n"
        f"{_format_violated_controls(scenario.get('violated_controls', []))}\n\n"
        f"## Compliance lesson source material\n\n"
        f"{scenario.get('compliance_lesson', '')}\n\n"
    )

    retrieval_section = ""
    if retrieved_context:
        retrieval_section = (
            "## Additional policy and framework passages "
            "(live from Foundry IQ)\n\n"
            f"{retrieved_context}\n\n"
        )

    return (
        base
        + retrieval_section
        + "Please deliver the post-scene closing segment for this case."
    )


def _build_retrieval_query(scenario: dict[str, Any]) -> str:
    """Build a Foundry IQ retrieval query from the scenario's violated controls.

    The CO is invoked at scene close, not in response to a free-text
    player question, so the most relevant grounding signal is the
    framework picture. Concatenating the control identifiers gives the
    search engine specific terminology (e.g., 'SOC 2 CC9.2', 'HIPAA
    §164.308(b)', 'HD-SEC-AC-001') to match against indexed policy and
    framework chunks.

    Args:
        scenario: A merged scenario dict.

    Returns:
        A space-separated string of framework + identifier tokens. Empty
        string if the scenario has no violated controls.
    """
    controls = scenario.get("violated_controls", []) or []
    parts: list[str] = []
    for c in controls:
        framework = c.get("framework", "").strip()
        identifier = c.get("identifier", "").strip()
        if framework and identifier:
            parts.append(f"{framework} {identifier}")
        elif identifier:
            parts.append(identifier)
        elif framework:
            parts.append(framework)
    return " ".join(parts)


def _fetch_retrieved_context(
    query: str,
    top_k: int = 5,
    *,
    stream_to_stdout: bool = False,
) -> tuple[str, int]:
    """Run a Foundry IQ retrieval and format the results.

    Wraps ``retrieve_context`` and ``format_retrieved_context`` with
    graceful failure handling. Search failures are logged (when streaming)
    and produce an empty context block rather than an exception, so the
    CO can still deliver the closer using scenario-only context if Azure
    Search is unavailable.

    Args:
        query: The text to search the index for (typically built from
            ``_build_retrieval_query`` for CO).
        top_k: Maximum number of snippets to retrieve.
        stream_to_stdout: If True, print a status notice when retrieval
            fails. Status output for successful retrievals is handled by
            the caller.

    Returns:
        A tuple of (formatted_context_string, retrieval_count). On any
        failure (including empty query), returns ("", 0).
    """
    if not query.strip():
        return "", 0

    try:
        retrievals = retrieve_context(query, top_k=top_k)
    except SearchClientError as exc:
        if stream_to_stdout:
            sys.stdout.write(
                f"\n[Foundry IQ retrieval unavailable: {exc}. "
                f"Proceeding with scenario-only context.]\n"
            )
            sys.stdout.flush()
        return "", 0

    return format_retrieved_context(retrievals), len(retrievals)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deliver_closer(
    scenario: dict[str, Any],
    accused_suspect_id: str | None,
    outcome: ComplianceOutcome,
    *,
    deployment: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    stream_to_stdout: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
    enable_retrieval: bool = True,
    retrieval_top_k: int = 5,
) -> dict[str, Any]:
    """Run the Compliance Officer's post-scene closing segment.

    Args:
        scenario: A merged scenario dict (output of scenario_loader).
        accused_suspect_id: The suspect_id the player accused, or None if no
            accusation was made. The CO uses this to address the player's
            inference directly.
        outcome: One of 'correct', 'wrong_perpetrator', 'no_accusation'.
            Calibrates the CO's tone per her prompt's "Tone Calibration"
            section.
        deployment: Optional explicit deployment override.
        max_tokens: Cap on response length. Default 1500.
        temperature: Sampling temperature. Default 0.4.
        stream_to_stdout: If True, write chunks to stdout as they arrive.
        max_retries: Retry budget on content filter triggers. Default 1.
        enable_retrieval: If True (default), retrieves policy and framework
            passages from Foundry IQ (query built from the scenario's
            violated controls) and injects them into the user message as
            additional source material. If False, skips the search call
            entirely — useful for tests, offline runs, or scenarios where
            the index is known to be unhelpful.
        retrieval_top_k: Maximum number of snippets to retrieve. Default 5.

    Returns:
        A dict with six keys:
            - ``speech`` (str): the CO's closing speech
            - ``elapsed_seconds`` (float)
            - ``deployment`` (str)
            - ``attempts`` (int)
            - ``outcome`` (str): echoed back for orchestrator convenience
            - ``retrieval_count`` (int): number of Foundry IQ snippets
              injected into the user message (0 if disabled or failed)

    Raises:
        ComplianceOfficerError: For any model-side failure. NOT raised for
            search failures — those degrade silently to retrieval_count=0.
    """
    if outcome not in ("correct", "wrong_perpetrator", "no_accusation"):
        raise ComplianceOfficerError(
            f"Invalid outcome '{outcome}'. Must be one of: "
            "correct, wrong_perpetrator, no_accusation"
        )

    deployment = resolve_deployment(
        deployment,
        "COMPLIANCE_OFFICER_DEPLOYMENT",
        "AZURE_AI_CHAT_DEPLOYMENT",
        default=DEFAULT_DEPLOYMENT,
    )

    try:
        client = build_azure_client()
        system_prompt = load_prompt(PROMPT_PATH)
    except AgentClientError as exc:
        raise ComplianceOfficerError(str(exc)) from exc

    # Foundry IQ retrieval (optional, graceful on failure). Query built
    # from the violated control identifiers since the CO is invoked at
    # scene close, not in response to a free-text question.
    retrieved_context_text = ""
    retrieval_count = 0
    if enable_retrieval:
        retrieval_query = _build_retrieval_query(scenario)
        retrieved_context_text, retrieval_count = _fetch_retrieved_context(
            retrieval_query,
            top_k=retrieval_top_k,
            stream_to_stdout=stream_to_stdout,
        )
        if stream_to_stdout and retrieval_count > 0:
            sys.stdout.write(
                f"[Retrieved {retrieval_count} relevant passages "
                f"from Foundry IQ]\n"
            )
            sys.stdout.flush()

    user_message = _build_user_message(
        scenario, accused_suspect_id, outcome, retrieved_context_text
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    speech_text = ""
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
            # Some Azure failures (especially jailbreak/content filter on the
            # prompt) return HTTP 400 BEFORE the stream starts. The mid-stream
            # finish_reason retry below doesn't help for those. Detect by
            # string match on the error and retry if budget remains.
            error_str = str(exc)
            prompt_filter_triggered = (
                "content_filter" in error_str or "jailbreak" in error_str
            )
            if prompt_filter_triggered and attempt < max_retries:
                if stream_to_stdout:
                    sys.stdout.write(
                        f"\n[Azure prompt filter triggered at request time, "
                        f"retrying ({attempt + 1}/{max_retries})...]\n"
                    )
                    sys.stdout.flush()
                continue
            if prompt_filter_triggered:
                raise ComplianceOfficerError(
                    f"Azure content/jailbreak filter rejected the prompt on all "
                    f"{attempt + 1} attempt(s). The user message construction may "
                    f"still contain phrasing the filter flags as prompt injection. "
                    f"Inspect the user message and remove any meta-references to "
                    f"the system prompt. Original error: {exc}"
                ) from exc
            raise ComplianceOfficerError(
                f"Azure OpenAI request to deployment '{deployment}' failed: {exc}"
            ) from exc

        if stream_to_stdout:
            sys.stdout.write("\n")
            sys.stdout.flush()

        elapsed = time.monotonic() - start
        speech_text = "".join(parts)

        if finish_reason == "content_filter" and attempt < max_retries:
            continue
        break

    if finish_reason and finish_reason != "stop":
        if finish_reason == "content_filter":
            raise ComplianceOfficerError(
                f"Azure content filter triggered on all {attempts} attempt(s) "
                f"for the closing speech."
            )
        if finish_reason == "length":
            raise ComplianceOfficerError(
                f"Closing speech truncated by max_tokens cap ({max_tokens})."
            )
        raise ComplianceOfficerError(
            f"Closing speech stream terminated unexpectedly: "
            f"finish_reason='{finish_reason}'"
        )

    if not speech_text.strip():
        raise ComplianceOfficerError(
            f"Compliance Officer returned empty response. "
            f"Deployment: {deployment}, elapsed: {elapsed:.1f}s, attempts: {attempts}"
        )

    return {
        "speech": speech_text.strip(),
        "elapsed_seconds": elapsed,
        "deployment": deployment,
        "attempts": attempts,
        "outcome": outcome,
        "retrieval_count": retrieval_count,
    }


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


SAMPLE_SCENARIO_NAME: str = "helix_dynamics_default"
SAMPLE_ACCUSED: str = "riley_park"     # the actual perpetrator of SCN-001
SAMPLE_OUTCOME: ComplianceOutcome = "correct"


def _smoke_test() -> int:
    """Load the default scenario and run the CO's closing for a correct accusation."""
    print("Compliance Academy Compliance Officer smoke test")
    print(f"Prompt:       {PROMPT_PATH}")
    print(f"Scenario:     {SAMPLE_SCENARIO_NAME}")
    print(f"Accused:      {SAMPLE_ACCUSED}")
    print(f"Outcome:      {SAMPLE_OUTCOME}")
    print("=" * 78)

    try:
        scenario = load_scenario_by_name(SAMPLE_SCENARIO_NAME)
    except (ScenarioLoadError, ScenarioValidationError) as exc:
        print(f"FAIL: could not load scenario '{SAMPLE_SCENARIO_NAME}': {exc}")
        return 1

    print(f"Loaded scenario: {scenario['scenario_name']!r}")
    print(f"Violated controls: {len(scenario['violated_controls'])}")
    print("-" * 78)
    print("Streaming Compliance Officer closing speech below.")
    print("-" * 78)

    start = time.monotonic()
    try:
        result = deliver_closer(
            scenario,
            SAMPLE_ACCUSED,
            SAMPLE_OUTCOME,
            stream_to_stdout=True,
        )
    except ComplianceOfficerError as exc:
        elapsed = time.monotonic() - start
        print()
        print("-" * 78)
        print(f"FAIL after {elapsed:.1f}s: {exc}")
        return 1

    print("-" * 78)
    print()
    if result["attempts"] > 1:
        print(f"OK    Closing speech delivered after {result['attempts']} attempts "
              f"(content filter retry succeeded)")
        print(f"      Final attempt: {result['elapsed_seconds']:.1f}s")
    else:
        print(f"OK    Closing speech delivered in {result['elapsed_seconds']:.1f}s")
    print(f"      deployment={result['deployment']}")
    print(f"      outcome={result['outcome']}")
    print(f"      speech_length={len(result['speech'])} chars "
          f"(~{len(result['speech'].split())} words)")
    print(f"      foundry_iq_sources={result['retrieval_count']}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
