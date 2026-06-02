"""Scenario Generator agent wrapper for Compliance Academy.

Wraps the Scenario Generator agent (defined by ``prompts/scenario_generator.md``)
with a Python interface that calls Azure OpenAI through the Foundry deployment.
Given a host-supplied breach description, it produces a complete scenario
override JSON, validates it via the loader, and returns the merged scenario
ready to hot-load into the running game.

This is the live-demo wow moment. During the Microsoft Reactor stream, the
Game Master invokes this agent in response to a breach description thrown
by the hosts or audience.

Performance notes:
    The default deployment is ``gpt-4.1-mini`` (direct, not via the Model
    Router) because the router will pick an o-series reasoning model for
    structured generation tasks, which adds 30-60 seconds of pre-emission
    latency. Scenario generation does not benefit from reasoning depth: the
    system prompt does the structural work; the model just maps a breach
    pattern to suspect roles and fabricates evidence.

    The API call streams. The caller can opt to print the stream live to
    stdout (used in the CLI smoke test and the Chainlit UI), which makes
    perceived latency drop dramatically because the audience sees the
    reasoning summary in seconds and watches the JSON build in real time.

Public API:
    generate_scenario(breach_description, *, stream_to_stdout=False, ...) -> dict
        Generate, validate, and merge a scenario from a breach description.
        Returns {'merged_scenario': dict, 'reasoning_summary': str,
        'raw_response': str, 'elapsed_seconds': float, 'deployment': str}.

Exceptions:
    ScenarioGenerationError
        Raised when the API call fails or the environment is not configured.

    ScenarioGenerationParseError
        Raised when the model response cannot be parsed into a scenario
        JSON object. The raw response is dumped to scenario_generator_debug.txt
        for inspection.

    (Validation failures bubble up as ScenarioValidationError from the loader.
    The raw response is dumped to scenario_generator_debug.txt in that case
    too.)

Live-demo resilience:
    Azure's content filter can stochastically trigger mid-stream and abort
    generation. The same prompt may succeed on one call and fail on the next.
    To handle this, ``generate_scenario`` retries once by default when it
    detects ``finish_reason='content_filter'``. The retry budget is
    configurable via the ``max_retries`` parameter.

    If retries are exhausted, the raised error includes mitigation guidance
    (relax the content filter in Azure portal, or adjust the breach
    description).

Environment variables (required):
    AZURE_AI_PROJECT_ENDPOINT       e.g., https://your-foundry-resource.services.ai.azure.com/api/projects/your-project-name

Authentication:
    Uses Entra ID via DefaultAzureCredential. Run ``az login`` in your shell
    before running the smoke test. The credential resolves through Azure CLI,
    environment variables, managed identity, and other standard sources.

Environment variables (optional, deployment selection):
    SCENARIO_GENERATOR_DEPLOYMENT      explicit override
    AZURE_AI_CHAT_DEPLOYMENT           preferred default (gpt-4.1-mini, fast)
    AZURE_AI_MODEL_ROUTER_DEPLOYMENT   last-resort fallback (slower because
                                        it can pick o-series reasoning models)
    AZURE_OPENAI_API_VERSION           defaults to '2024-10-21'

CLI:
    Running this module as a script generates a scenario from a hardcoded
    sample breach description, streams the model output live to stdout, and
    prints the validation summary. Useful as a pre-stream end-to-end smoke
    test:

        python -m src.agents.scenario_generator
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Best-effort .env loading so the CLI smoke test picks up Azure credentials
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv()
except ImportError:
    pass

from src.scenario_loader import (
    ScenarioValidationError,
    load_scenario_from_dict,
)
from src.activity_log import emit as _emit, log_line as _log_line
from src.agents._azure_client import (
    AgentClientError,
    build_azure_client,
    load_prompt,
    resolve_deployment,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default Foundry deployment name. We default to gpt-4.1-mini for the live
#: demo because it is faster and more predictable than the Model Router
#: (which can pick an o-series reasoning model and add 30-60s of pre-emission
#: latency). The resolution chain in generate_scenario() prefers
#: SCENARIO_GENERATOR_DEPLOYMENT, then AZURE_AI_CHAT_DEPLOYMENT, then this.
DEFAULT_DEPLOYMENT: str = "gpt-4.1-mini"

#: Default cap on the model's response length. Scenarios at the spec'd
#: density (6-10 evidence items, 5 suspects with full detail, 2-3 paragraph
#: compliance lesson) run ~9-11k tokens; 12000 gives headroom while keeping
#: latency bounded.
DEFAULT_MAX_TOKENS: int = 12000

#: Default temperature. Scenario authoring benefits from some variability
#: but should stay grounded; 0.5 is a reasonable balance.
DEFAULT_TEMPERATURE: float = 0.5

#: Default number of retries when Azure's content filter triggers mid-stream.
#: Content filter is stochastic; a single retry usually clears.
DEFAULT_MAX_RETRIES: int = 1

#: Default number of retries when the generated scenario fails loader
#: validation. The model sometimes produces structurally invalid scenarios
#: (most commonly: 3+ red herrings on vague breach descriptions). A single
#: corrective retry with the validation error fed back as explicit guidance
#: usually fixes it; 2 retries gives margin.
DEFAULT_MAX_VALIDATION_RETRIES: int = 2

#: Path to the Scenario Generator system prompt, resolved from this file.
PROMPT_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent / "prompts" / "scenario_generator.md"
)

#: Where to dump the raw model response when parsing or validation fails.
#: Resolved relative to the current working directory so it lands next to
#: where the user ran the command.
DEBUG_DUMP_PATH: Path = Path("scenario_generator_debug.txt")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ScenarioGenerationError(Exception):
    """Raised when scenario generation fails for environmental or API reasons."""


class ScenarioGenerationParseError(ScenarioGenerationError):
    """Raised when the model response cannot be parsed into a scenario JSON object."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_user_message(breach_description: str) -> str:
    """Compose the user-side message for one generation call."""
    return (
        "Host-supplied breach description:\n"
        f"{breach_description.strip()}\n\n"
        "Current scenario context:\n"
        "The active fiction is Helix Dynamics, a fictional Cambridge MA biotech "
        "with approximately 340 employees, Phase II clinical trials in oncology, "
        "and a HelixVault / PatientChain / LabConnect data footprint. Shared "
        "baseline content (canonical Microsoft systems pool, the five canonical "
        "suspect IDs, and base personas) is loaded from "
        "data/synthetic/scenarios/_shared/scenario_commons.json and will be "
        "merged with your override at load time.\n\n"
        "Instruction:\n"
        "Produce a new scenario override JSON that translates the breach "
        "description into a Helix Dynamics scenario the game can hot-load. "
        "Follow your system prompt's output order: brief acknowledgment, a "
        "3-5 sentence reasoning summary that the audience will read, the "
        "scenario override JSON wrapped in a ```json fenced block, and a "
        "closing line that reads exactly: Scenario ready to hot-load."
    )


def _build_validation_retry_message(
    breach_description: str,
    validation_error: ScenarioValidationError,
) -> str:
    """Compose a corrective user message for a validation-retry attempt.

    The model produced a scenario that failed loader validation. We tell it
    what went wrong, in plain language, and ask for a fresh attempt that
    addresses the issue. The original breach description is included so the
    model has full context.

    We deliberately do NOT include the model's previous JSON output in this
    retry message. Anchoring on the failed attempt biases the regeneration
    toward the same structural shape; a clean restart with the error as a
    constraint produces better fresh attempts.
    """
    return (
        "Host-supplied breach description:\n"
        f"{breach_description.strip()}\n\n"
        "Current scenario context:\n"
        "The active fiction is Helix Dynamics, a fictional Cambridge MA biotech "
        "with approximately 340 employees, Phase II clinical trials in oncology, "
        "and a HelixVault / PatientChain / LabConnect data footprint. Shared "
        "baseline content (canonical Microsoft systems pool, the five canonical "
        "suspect IDs, and base personas) is loaded from "
        "data/synthetic/scenarios/_shared/scenario_commons.json and will be "
        "merged with your override at load time.\n\n"
        "Important - your previous scenario attempt failed loader validation "
        "with the following error:\n\n"
        f"  {validation_error}\n\n"
        "Please regenerate the scenario, ensuring this error does not recur. "
        "Re-read the suspect roster rules and quality bar in your system "
        "prompt. In particular: exactly one suspect must have "
        "is_perpetrator=true, exactly one or two suspects must have "
        "is_red_herring=true (no more, no fewer), and the remaining suspects "
        "are tangential with both flags false.\n\n"
        "Follow the same output order: brief acknowledgment, 3-5 sentence "
        "reasoning summary, scenario override JSON in a ```json fenced "
        "block, and a closing line that reads exactly: Scenario ready to "
        "hot-load."
    )


def _extract_json_from_response(text: str) -> dict[str, Any]:
    """Extract the scenario JSON object from a mixed model response.

    Tries a ```json fenced block first, then falls back to raw_decode from the
    first ``{`` character in the text. Raises ScenarioGenerationParseError
    with a useful snippet if no valid JSON can be extracted.
    """
    # Try fenced ```json ... ``` block first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass  # Fall through to raw_decode

    # Fall back to raw_decode from the first { in the response
    first_brace = text.find("{")
    if first_brace == -1:
        raise ScenarioGenerationParseError(
            "No JSON object found in model response. "
            f"Response begins with: {text[:200]!r}"
        )

    try:
        obj, _ = json.JSONDecoder().raw_decode(text[first_brace:])
    except json.JSONDecodeError as exc:
        snippet = text[first_brace : first_brace + 500]
        raise ScenarioGenerationParseError(
            f"Could not parse JSON starting at offset {first_brace}: "
            f"{exc.msg} (line {exc.lineno} col {exc.colno}). "
            f"Response snippet: {snippet!r}"
        ) from exc

    if not isinstance(obj, dict):
        raise ScenarioGenerationParseError(
            f"Extracted JSON is a {type(obj).__name__}, expected an object"
        )
    return obj


def _extract_reasoning_summary(text: str) -> str:
    """Extract the visible reasoning summary that precedes the JSON block."""
    fenced_start = text.find("```")
    brace_start = text.find("{")

    if fenced_start != -1 and (brace_start == -1 or fenced_start < brace_start):
        return text[:fenced_start].strip()
    if brace_start != -1:
        return text[:brace_start].strip()
    return text.strip()


def _dump_debug_response(raw_response: str, error_summary: str,
                        parsed_json: dict[str, Any] | None = None,
                        dump_path: Path | None = None) -> Path:
    """Write the raw model response (and optionally the parsed JSON) to disk.

    Called when parsing or validation fails so the caller can inspect what
    the model actually emitted. Returns the path written.
    """
    target = dump_path or DEBUG_DUMP_PATH
    target = Path(target).resolve()

    with target.open("w", encoding="utf-8") as f:
        f.write("# Scenario Generator debug dump\n")
        f.write(f"# Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Error: {error_summary}\n")
        f.write("# " + "=" * 70 + "\n\n")
        f.write("## Raw model response\n\n")
        f.write(raw_response)
        if parsed_json is not None:
            f.write("\n\n## Parsed JSON (failed validation)\n\n")
            f.write(json.dumps(parsed_json, indent=2, ensure_ascii=False))

    return target


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_scenario(
    breach_description: str,
    *,
    deployment: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    stream_to_stdout: bool = False,
    debug_dump_path: Path | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_validation_retries: int = DEFAULT_MAX_VALIDATION_RETRIES,
) -> dict[str, Any]:
    """Generate, validate, and merge a scenario from a breach description.

    Args:
        breach_description: Free-text description of a real-world or
            hypothetical breach pattern, supplied by the host or audience.
        deployment: Azure OpenAI deployment name. If not provided, resolves
            via env vars (see module docstring). Defaults to ``gpt-4.1-mini``.
        max_tokens: Cap on the model's response length. Defaults to 8000.
        temperature: Sampling temperature. Defaults to 0.5.
        stream_to_stdout: If True, write each streamed chunk to stdout as
            it arrives. Used by the CLI smoke test for visible progress.
            Production callers (orchestrator, UI) typically leave this False
            and handle display themselves.
        debug_dump_path: Optional custom path for the debug dump file. Defaults
            to ``scenario_generator_debug.txt`` in the current directory.
        max_retries: Number of retries when Azure's content filter triggers
            mid-stream. Default is 1. The retry uses the same prompt; content
            filter is stochastic and usually clears on a second attempt.
        max_validation_retries: Number of retries when the generated scenario
            fails loader validation (e.g., wrong red herring count, missing
            required field). Default is 2. Each retry feeds the validation
            error back to the model as explicit corrective guidance.

    Returns:
        A dict with seven keys:
            - ``merged_scenario`` (dict): the validated, fully-merged scenario
              ready to hot-load into the Game Master.
            - ``reasoning_summary`` (str): the visible reasoning the audience
              should see explaining how the breach was translated.
            - ``raw_response`` (str): the unparsed model response text from
              the final (successful) attempt.
            - ``elapsed_seconds`` (float): wall-clock time of the final
              (successful) model call. Excludes time spent on aborted retries.
            - ``deployment`` (str): the resolved deployment name actually used.
            - ``attempts`` (int): total number of model calls made across
              all content-filter and validation retries.
            - ``validation_attempts`` (int): number of full validation cycles
              attempted (1 if first attempt validated, 2 if one corrective
              retry was needed, etc.).

    Raises:
        ScenarioGenerationError: For missing env vars, API failures, or
            unparseable responses.
        ScenarioGenerationParseError: When the response contains no valid
            scenario JSON object. Raw response dumped to debug file.
        ScenarioValidationError: When the parsed scenario fails the loader's
            schema validation. Raw response + parsed JSON dumped to debug file.
    """
    if not breach_description or not breach_description.strip():
        raise ScenarioGenerationError("breach_description must be a non-empty string")

    # Visual separator + scope header for this generation in the activity log.
    _log_line("")
    _breach_preview = (
        breach_description if len(breach_description) < 100
        else breach_description[:97] + "..."
    )
    _emit(
        "Scenario",
        "Scenario Generator: beginning live generation",
        breach=_breach_preview,
    )

    deployment = resolve_deployment(
        deployment,
        "SCENARIO_GENERATOR_DEPLOYMENT",
        "AZURE_AI_CHAT_DEPLOYMENT",
        "AZURE_AI_MODEL_ROUTER_DEPLOYMENT",
        default=DEFAULT_DEPLOYMENT,
    )

    try:
        client = build_azure_client()
        system_prompt = load_prompt(PROMPT_PATH)
    except AgentClientError as exc:
        _emit("Error", f"Client/prompt setup failed: {exc}")
        raise ScenarioGenerationError(str(exc)) from exc
    _emit(
        "Scenario",
        f"Loaded system prompt ({len(system_prompt)} chars)",
        path=PROMPT_PATH.name,
    )
    user_message = _build_user_message(breach_description)

    # Outer loop: validation retry. Each iteration runs a full streaming
    # call (with its own inner content_filter retry loop) and then parses
    # and validates the result. If validation fails AND we have budget,
    # we rebuild the user message with the validation error fed back as
    # corrective guidance and try again.
    total_attempts = 0

    for validation_attempt in range(max_validation_retries + 1):
        if validation_attempt > 0:
            _emit(
                "Scenario",
                f"Validation retry cycle "
                f"({validation_attempt}/{max_validation_retries})",
            )
        # Streaming loop with retry on content_filter. Each attempt starts
        # fresh state so partial output from an aborted attempt doesn't
        # contaminate the next one.
        raw_response = ""
        elapsed = 0.0
        finish_reason: str | None = None
        cf_attempts = 0

        for attempt in range(max_retries + 1):
            cf_attempts = attempt + 1
            is_retry = attempt > 0
            if is_retry:
                _emit(
                    "Scenario",
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
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )

                for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    # finish_reason is None on intermediate chunks; set on the last.
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
                raise ScenarioGenerationError(
                    f"Azure OpenAI request to deployment '{deployment}' failed: {exc}"
                ) from exc

            if stream_to_stdout:
                sys.stdout.write("\n")
                sys.stdout.flush()

            elapsed = time.monotonic() - start
            raw_response = "".join(parts)
            approx_tokens = len(raw_response) // 4
            _emit(
                "Azure OpenAI",
                f"Stream complete: ~{approx_tokens} tokens in {elapsed:.1f}s",
                finish_reason=finish_reason or "unknown",
            )

            # Retry only on content_filter, only if budget remains.
            if finish_reason == "content_filter" and attempt < max_retries:
                continue
            break

        total_attempts += cf_attempts

        # If the final attempt did not end cleanly, surface a specific error.
        # These are not retried at the validation layer because they indicate
        # a deeper problem (filter, length cap, or API misbehavior) that a
        # corrective user message will not fix.
        if finish_reason and finish_reason != "stop":
            dump_target = _dump_debug_response(
                raw_response,
                error_summary=(
                    f"Stream terminated with finish_reason='{finish_reason}' "
                    f"after {total_attempts} attempt(s)"
                ),
                dump_path=debug_dump_path,
            )
            if finish_reason == "content_filter":
                raise ScenarioGenerationError(
                    f"Azure content filter triggered on all {total_attempts} attempt(s). "
                    f"Mitigation: in the Azure AI Foundry portal, find the "
                    f"deployment '{deployment}' under Models + endpoints and "
                    f"relax its content filter (set 'self-harm', 'violence', "
                    f"and 'sexual' to High threshold, or apply a custom filter). "
                    f"Alternatively, increase max_retries or adjust the breach "
                    f"description to avoid trigger phrases. "
                    f"Partial response written to: {dump_target}"
                )
            if finish_reason == "length":
                raise ScenarioGenerationError(
                    f"Response truncated by max_tokens cap ({max_tokens}). "
                    f"The model wanted to write more JSON than the cap allows. "
                    f"Try increasing max_tokens or instruct the prompt to be "
                    f"more concise. Partial response written to: {dump_target}"
                )
            raise ScenarioGenerationError(
                f"Stream terminated with unexpected finish_reason='{finish_reason}'. "
                f"Partial response written to: {dump_target}"
            )

        if not raw_response.strip():
            raise ScenarioGenerationError(
                f"Model returned empty response. Deployment: {deployment}, "
                f"elapsed: {elapsed:.1f}s, attempts: {total_attempts}"
            )

        # Parse JSON from the response. On failure, dump the raw response.
        # Parse failures are NOT retried at the validation layer: they mean
        # the model emitted unparseable output, which a corrective message
        # is unlikely to fix and would burn budget for no benefit.
        try:
            scenario_override = _extract_json_from_response(raw_response)
        except ScenarioGenerationParseError as exc:
            dump_target = _dump_debug_response(
                raw_response, error_summary=f"Parse failure: {exc}",
                dump_path=debug_dump_path,
            )
            raise ScenarioGenerationParseError(
                f"{exc}\nRaw response written to: {dump_target}"
            ) from exc

        # Validate via loader. THIS is the retry point.
        try:
            merged_scenario = load_scenario_from_dict(scenario_override)
        except ScenarioValidationError as exc:
            # If we have validation retry budget remaining, build a corrective
            # user message and loop. Each retry feeds the specific validation
            # error back to the model as explicit guidance.
            if validation_attempt < max_validation_retries:
                _emit(
                    "Scenario",
                    f"Validation FAILED: {str(exc)[:160]}",
                )
                _emit(
                    "Scenario",
                    f"Building corrective retry message "
                    f"({validation_attempt + 1}/{max_validation_retries})",
                )
                if stream_to_stdout:
                    sys.stdout.write(
                        f"\n[Validation failed: {exc}]\n"
                        f"[Retrying with corrective feedback "
                        f"({validation_attempt + 1}/{max_validation_retries})...]\n"
                    )
                    sys.stdout.flush()
                user_message = _build_validation_retry_message(
                    breach_description, exc
                )
                continue  # Outer loop

            # Budget exhausted. Dump and re-raise with cumulative attempt info.
            dump_target = _dump_debug_response(
                raw_response,
                error_summary=(
                    f"Validation failure after {validation_attempt + 1} "
                    f"validation attempt(s), {total_attempts} total model "
                    f"call(s): {exc}"
                ),
                parsed_json=scenario_override,
                dump_path=debug_dump_path,
            )
            _emit(
                "Error",
                f"Validation retries exhausted ({total_attempts} model calls)",
            )
            raise ScenarioValidationError(
                f"{exc}\nValidation retries exhausted "
                f"({validation_attempt + 1} validation attempt(s), "
                f"{total_attempts} total model call(s)). "
                f"Raw response and parsed JSON written to: {dump_target}"
            ) from exc

        # SUCCESS path. Build reasoning summary and return.
        reasoning_summary = _extract_reasoning_summary(raw_response)

        scn = merged_scenario
        perp_name = next(
            (s["name"] for s in scn["suspects"] if s.get("is_perpetrator")),
            "?",
        )
        _emit(
            "Scenario",
            f"Scenario validated and merged: {scn['scenario_name']!r}",
            id=scn["scenario_id"],
            pattern=scn["attack_pattern_category"],
            evidence=len(scn["evidence_seeds"]),
            controls=len(scn["violated_controls"]),
            perpetrator=perp_name,
            elapsed=f"{elapsed:.1f}s",
            validation_attempts=validation_attempt + 1,
            total_calls=total_attempts,
        )

        return {
            "merged_scenario": merged_scenario,
            "reasoning_summary": reasoning_summary,
            "raw_response": raw_response,
            "elapsed_seconds": elapsed,
            "deployment": deployment,
            "attempts": total_attempts,
            "validation_attempts": validation_attempt + 1,
        }

    # The loop above either returns on success or raises on terminal failure;
    # this line is unreachable but satisfies static type checkers that the
    # function always returns or raises.
    raise ScenarioGenerationError(
        "generate_scenario loop exited without success or error; this should "
        "never happen and indicates a logic bug in the retry loop."
    )


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


SAMPLE_BREACH_DESCRIPTION = (
    "An employee's session token gets stolen from a browser cache on a personal "
    "laptop they used at an industry conference. The attacker uses the still-valid "
    "session token to make HelixVault API calls before it expires, exfiltrating "
    "regulatory submission documents. The pattern is similar to recent "
    "post-authentication token theft attacks seen against cloud SaaS environments."
)


def _smoke_test() -> int:
    """Generate a scenario from a hardcoded breach description and validate it.

    Streams the model output live to stdout, then prints the validation
    summary. On any failure, points to the debug dump file for inspection.
    Returns 0 on success, 1 on any failure.
    """
    resolved_deployment = resolve_deployment(
        None,
        "SCENARIO_GENERATOR_DEPLOYMENT",
        "AZURE_AI_CHAT_DEPLOYMENT",
        "AZURE_AI_MODEL_ROUTER_DEPLOYMENT",
        default=DEFAULT_DEPLOYMENT,
    )
    print("Compliance Academy Scenario Generator smoke test")
    print(f"Prompt:       {PROMPT_PATH}")
    print(f"Deployment:   {resolved_deployment}")
    print(f"Debug dump:   {DEBUG_DUMP_PATH.resolve()} (only written on failure)")
    print("=" * 78)
    print("Breach description:")
    print(f"  {SAMPLE_BREACH_DESCRIPTION}")
    print("=" * 78)
    print("Streaming model output below. First tokens should appear within 5 seconds.")
    print("-" * 78)

    start = time.monotonic()
    try:
        result = generate_scenario(SAMPLE_BREACH_DESCRIPTION, stream_to_stdout=True)
    except ScenarioGenerationParseError as exc:
        elapsed = time.monotonic() - start
        print()
        print("-" * 78)
        print(f"FAIL after {elapsed:.1f}s: model response could not be parsed as scenario JSON")
        print(f"      {exc}")
        return 1
    except ScenarioValidationError as exc:
        elapsed = time.monotonic() - start
        print()
        print("-" * 78)
        print(f"FAIL after {elapsed:.1f}s: generated scenario did not pass loader validation")
        print(f"      {exc}")
        return 1
    except ScenarioGenerationError as exc:
        elapsed = time.monotonic() - start
        print()
        print("-" * 78)
        print(f"FAIL after {elapsed:.1f}s: {exc}")
        return 1

    print("-" * 78)
    scenario = result["merged_scenario"]
    perp = next((s["name"] for s in scenario["suspects"] if s["is_perpetrator"]), "?")
    herrings = [s["name"] for s in scenario["suspects"] if s["is_red_herring"]]

    print()
    val_attempts = result.get("validation_attempts", 1)
    if val_attempts > 1:
        print(f"OK    Scenario generated after {val_attempts} validation cycles "
              f"({result['attempts']} total model calls; corrective-feedback retry succeeded)")
        print(f"      Final attempt: {result['elapsed_seconds']:.1f}s")
    elif result["attempts"] > 1:
        print(f"OK    Scenario generated after {result['attempts']} attempts "
              f"(content filter retry succeeded)")
        print(f"      Final attempt: {result['elapsed_seconds']:.1f}s")
    else:
        print(f"OK    Scenario generated, parsed, validated, and merged in "
              f"{result['elapsed_seconds']:.1f}s")
    print(f"      deployment={result['deployment']}")
    print(f"      id={scenario['scenario_id']}  name={scenario['scenario_name']!r}")
    print(
        f"      pattern={scenario['attack_pattern_category']}  "
        f"systems={len(scenario['involved_systems'])}  "
        f"controls={len(scenario['violated_controls'])}  "
        f"evidence={len(scenario['evidence_seeds'])}"
    )
    print(f"      perpetrator={perp}  red_herrings={herrings}")
    print()
    print("Extracted reasoning summary (audience-facing portion):")
    print("-" * 78)
    print(result["reasoning_summary"])
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
