"""Scenario loader and validator for Compliance Academy.

Loads a per-scenario override JSON file, merges it with the shared baseline
in ``data/synthetic/scenarios/_shared/scenario_commons.json``, and returns a
single fully-populated scenario dict that the Game Master and suspect agents
can consume.

Merge semantics are defined authoritatively in ``scenario_commons.json``
under the ``merge_semantics`` key. The implementation here is the operational
reference.

Public API:
    load_scenario(scenario_path) -> dict
        Load, validate, and merge a scenario file. Returns a flat dict.

    load_scenario_from_dict(scenario, commons_path=None) -> dict
        Validate and merge an in-memory scenario dict against the shared
        commons. Use this for the live Scenario Generator output, where
        the scenario exists as a dict and never touches disk.

    load_scenario_by_name(name, scenarios_dir=None) -> dict
        Convenience wrapper for loading a scenario by its base filename.

Exceptions:
    ScenarioLoadError
        Raised for IO failures, JSON parse failures, or missing files.

    ScenarioValidationError
        Raised when a scenario does not conform to the override schema
        (wrong suspect IDs, multiple perpetrators, fields missing, etc.).

CLI:
    Running this module as a script loads all three pre-built scenarios in
    ``data/synthetic/scenarios/`` and prints a validation summary. Useful as
    a pre-stream smoke test:

        python -m src.scenario_loader
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The five canonical suspect IDs that every scenario must use.
CANONICAL_SUSPECT_IDS: tuple[str, ...] = (
    "alex_chen",
    "morgan_webb",
    "riley_park",
    "casey_doyle",
    "jordan_smith",
)

#: Top-level fields a scenario override file must declare.
REQUIRED_SCENARIO_FIELDS: tuple[str, ...] = (
    "scenario_id",
    "scenario_name",
    "premise_narration",
    "attack_pattern_category",
    "violated_controls",
    "involved_systems",
    "suspects",
    "evidence_seeds",
    "clue_graph",
    "compliance_lesson",
)

#: Fields a suspect override must declare.
REQUIRED_SUSPECT_OVERRIDE_FIELDS: tuple[str, ...] = (
    "suspect_id",
    "specific_role",
    "scenario_context",
    "starting_trust",
    "alibi",
    "open_knowledge",
    "guarded_knowledge",
    "hidden_truth",
    "leak_conditions",
    "is_perpetrator",
    "is_red_herring",
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ScenarioLoadError(Exception):
    """Raised when a scenario file cannot be read or parsed."""


class ScenarioValidationError(Exception):
    """Raised when a scenario does not conform to the expected schema."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file with clear error messages on failure."""
    if not path.exists():
        raise ScenarioLoadError(f"File not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ScenarioLoadError(
            f"Invalid JSON in {path}: line {exc.lineno} col {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise ScenarioLoadError(f"Could not read {path}: {exc}") from exc


def _resolve_commons_path(scenario_path: Path, extends: str | None) -> Path:
    """Resolve the path to the shared commons file from the scenario file.

    The ``_extends`` field in the scenario file is treated as a path
    relative to the scenario file's parent directory. If absent, defaults
    to ``_shared/scenario_commons.json`` in the same directory.
    """
    relative = extends or "_shared/scenario_commons.json"
    return (scenario_path.parent / relative).resolve()


def _normalize_scenario_overrides(scenario: dict[str, Any]) -> None:
    """In-place defaults for soft-optional fields. Demo-resilience layer.

    Some required fields are semantically empty for tangential suspects
    (e.g., a suspect with no leak conditions has ``leak_conditions: []``).
    The Scenario Generator agent inconsistently emits these fields: sometimes
    as empty arrays, sometimes omitted entirely. This normalization treats
    missing-and-empty as equivalent so the live demo is robust against model
    non-determinism.

    Only ``leak_conditions`` is auto-defaulted today. Other 'missing' fields
    still fail validation, which is correct: missing alibi or hidden_truth
    indicates a broken scenario the audience would notice.
    """
    for s in scenario.get("suspects", []):
        if isinstance(s, dict):
            s.setdefault("leak_conditions", [])


def _validate_scenario_overrides(scenario: dict[str, Any], label: str) -> None:
    """Validate the structure of a scenario override file.

    Raises ScenarioValidationError on the first problem found. The ``label``
    (typically a filename or 'in-memory scenario') is included in every error
    so live-demo debugging is fast.
    """
    # Required top-level fields
    missing = [f for f in REQUIRED_SCENARIO_FIELDS if f not in scenario]
    if missing:
        raise ScenarioValidationError(
            f"{label}: missing required top-level fields: {', '.join(missing)}"
        )

    # Suspects: must be a list of exactly the five canonical IDs
    suspects = scenario["suspects"]
    if not isinstance(suspects, list):
        raise ScenarioValidationError(f"{label}: 'suspects' must be a list")

    seen_ids = [s.get("suspect_id") for s in suspects]
    if sorted(seen_ids) != sorted(CANONICAL_SUSPECT_IDS):
        raise ScenarioValidationError(
            f"{label}: 'suspects' must contain exactly the five canonical IDs "
            f"{CANONICAL_SUSPECT_IDS}, got {seen_ids}"
        )

    # Each suspect override has required fields
    for s in suspects:
        sid = s.get("suspect_id", "<unknown>")
        missing_s = [f for f in REQUIRED_SUSPECT_OVERRIDE_FIELDS if f not in s]
        if missing_s:
            raise ScenarioValidationError(
                f"{label}: suspect '{sid}' missing required fields: {', '.join(missing_s)}"
            )
        if not isinstance(s["leak_conditions"], list):
            raise ScenarioValidationError(
                f"{label}: suspect '{sid}' leak_conditions must be a list"
            )
        if not (0.0 <= s["starting_trust"] <= 1.0):
            raise ScenarioValidationError(
                f"{label}: suspect '{sid}' starting_trust must be in [0.0, 1.0], "
                f"got {s['starting_trust']}"
            )

    # Exactly one perpetrator
    perps = [s["suspect_id"] for s in suspects if s["is_perpetrator"]]
    if len(perps) != 1:
        raise ScenarioValidationError(
            f"{label}: expected exactly one perpetrator, found {len(perps)}: {perps}"
        )

    # One or two red herrings
    herrings = [s["suspect_id"] for s in suspects if s["is_red_herring"]]
    if not (1 <= len(herrings) <= 2):
        raise ScenarioValidationError(
            f"{label}: expected 1 or 2 red herrings, found {len(herrings)}: {herrings}"
        )

    # Perpetrator and red herring are mutually exclusive
    overlap = set(perps) & set(herrings)
    if overlap:
        raise ScenarioValidationError(
            f"{label}: suspect(s) marked as both perpetrator and red herring: {overlap}"
        )

    # At least one framework + one Helix policy control cited
    controls = scenario["violated_controls"]
    frameworks = {c.get("framework") for c in controls}
    if "Helix Dynamics" not in frameworks:
        raise ScenarioValidationError(
            f"{label}: violated_controls must cite at least one Helix Dynamics policy"
        )
    if not (frameworks - {"Helix Dynamics"}):
        raise ScenarioValidationError(
            f"{label}: violated_controls must cite at least one external framework "
            f"(SOC 2, NIST 800-53, ISO 27001, HIPAA, etc.)"
        )


def _validate_against_commons(scenario: dict[str, Any], commons: dict[str, Any],
                              label: str) -> None:
    """Cross-validate a scenario against the shared commons.

    Checks that suspect IDs exist in the base personas, and that
    involved_systems is a subset of the canonical Microsoft systems pool.
    """
    base_personas = commons.get("suspect_base_personas", {})

    for s in scenario["suspects"]:
        sid = s["suspect_id"]
        if sid not in base_personas:
            raise ScenarioValidationError(
                f"{label}: suspect_id '{sid}' has no matching base persona in "
                f"scenario_commons.json. Available: {sorted(base_personas.keys())}"
            )

    canonical_systems = set(commons.get("canonical_microsoft_systems", []))
    unknown_systems = [s for s in scenario["involved_systems"] if s not in canonical_systems]
    if unknown_systems:
        raise ScenarioValidationError(
            f"{label}: involved_systems contains entries not in "
            f"canonical_microsoft_systems: {unknown_systems}"
        )


def _merge_suspect(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge a single suspect base persona with a scenario override.

    Implements the merge semantics documented in scenario_commons.json:
    - name comes from base
    - role comes from override.specific_role
    - backstory = base.backstory_core + ' ' + override.scenario_context
    - conversational_style = base.core + optional override.scenario_style_note
    - voice_examples = base.core + optional override.scenario_voice_examples
    - everything else comes from override
    """
    style = base["conversational_style_core"]
    style_note = override.get("scenario_style_note")
    if style_note:
        style = style + " " + style_note

    voice_examples = list(base["voice_examples_core"]) + list(
        override.get("scenario_voice_examples", [])
    )

    return {
        "suspect_id": override["suspect_id"],
        "name": base["name"],
        "role": override["specific_role"],
        "role_family": base["role_family"],
        "tenure_at_helix": base["tenure_at_helix"],
        "starting_trust": override["starting_trust"],
        "backstory": base["backstory_core"] + " " + override["scenario_context"],
        "conversational_style": style,
        "voice_examples": voice_examples,
        "alibi": override["alibi"],
        "open_knowledge": override["open_knowledge"],
        "guarded_knowledge": override["guarded_knowledge"],
        "hidden_truth": override["hidden_truth"],
        "leak_conditions": list(override["leak_conditions"]),
        "is_perpetrator": override["is_perpetrator"],
        "is_red_herring": override["is_red_herring"],
    }


def _merge(scenario: dict[str, Any], commons: dict[str, Any], label: str) -> dict[str, Any]:
    """Validate and merge a scenario dict with a commons dict.

    This is the shared core used by both ``load_scenario`` (file-based) and
    ``load_scenario_from_dict`` (in-memory). It runs schema validation, the
    cross-validation against the commons, and then performs the merge.

    Returns a fully-populated, flat scenario dict.
    """
    _normalize_scenario_overrides(scenario)
    _validate_scenario_overrides(scenario, label)
    _validate_against_commons(scenario, commons, label)

    # Compose disclosure
    disclosure = commons["synthetic_disclosure_boilerplate"]
    extra = scenario.get("scenario_specific_disclosure", "")
    if extra:
        disclosure = disclosure + " " + extra

    # Merge suspects
    base_personas = commons["suspect_base_personas"]
    merged_suspects = [_merge_suspect(base_personas[s["suspect_id"]], s)
                       for s in scenario["suspects"]]

    return {
        "scenario_id": scenario["scenario_id"],
        "scenario_name": scenario["scenario_name"],
        "synthetic_disclosure": disclosure,
        "premise_narration": scenario["premise_narration"],
        "attack_pattern_category": scenario["attack_pattern_category"],
        "violated_controls": scenario["violated_controls"],
        "involved_systems": scenario["involved_systems"],
        "helix_dynamics_company_profile": commons["helix_dynamics_company_profile"],
        "suspects": merged_suspects,
        "evidence_seeds": scenario["evidence_seeds"],
        "clue_graph": scenario["clue_graph"],
        "compliance_lesson": scenario["compliance_lesson"],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_scenario(scenario_path: str | Path) -> dict[str, Any]:
    """Load, validate, and merge a scenario file with the shared baseline.

    Args:
        scenario_path: Path to a scenario override JSON file (e.g.,
            ``data/synthetic/scenarios/helix_dynamics_default.json``).

    Returns:
        A fully-populated scenario dict with merged suspect personas,
        composed synthetic disclosure, and all scenario-specific content.
        Top-level keys: scenario_id, scenario_name, synthetic_disclosure,
        premise_narration, attack_pattern_category, violated_controls,
        involved_systems, helix_dynamics_company_profile, suspects,
        evidence_seeds, clue_graph, compliance_lesson.

    Raises:
        ScenarioLoadError: If a file cannot be read or parsed.
        ScenarioValidationError: If the scenario or its merge with the
            shared commons violates the expected schema.
    """
    scenario_path = Path(scenario_path).resolve()
    scenario = _read_json(scenario_path)

    commons_path = _resolve_commons_path(scenario_path, scenario.get("_extends"))
    commons = _read_json(commons_path)

    return _merge(scenario, commons, scenario_path.name)


def load_scenario_from_dict(scenario: dict[str, Any],
                            commons_path: str | Path | None = None) -> dict[str, Any]:
    """Validate and merge an in-memory scenario dict with the shared baseline.

    Use this when a scenario is produced at runtime (e.g., by the Scenario
    Generator agent during the live demo) and you want to feed it straight
    into the game without round-tripping through disk.

    Args:
        scenario: A scenario override dict matching the schema documented in
            ``prompts/scenario_generator.md``.
        commons_path: Optional path to ``scenario_commons.json``. Defaults to
            the canonical location at
            ``<repo>/data/synthetic/scenarios/_shared/scenario_commons.json``.

    Returns:
        A fully-populated scenario dict (same shape as ``load_scenario``).

    Raises:
        ScenarioLoadError: If the commons file cannot be read.
        ScenarioValidationError: If the scenario does not match the schema.
    """
    if commons_path is None:
        commons_path = (
            Path(__file__).resolve().parent.parent
            / "data" / "synthetic" / "scenarios" / "_shared" / "scenario_commons.json"
        )
    commons = _read_json(Path(commons_path).resolve())

    label = scenario.get("scenario_id", "<in-memory scenario>")
    return _merge(scenario, commons, label)


def load_scenario_by_name(name: str, scenarios_dir: str | Path | None = None) -> dict[str, Any]:
    """Load a scenario by its base filename (without ``.json``).

    Args:
        name: Base filename, e.g. ``"helix_dynamics_default"`` or
            ``"helix_dynamics_supplychain"``.
        scenarios_dir: Optional directory to look in. Defaults to the
            repository's ``data/synthetic/scenarios/`` relative to this file.

    Returns:
        The merged scenario dict (see ``load_scenario``).
    """
    if scenarios_dir is None:
        scenarios_dir = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "scenarios"
    scenarios_dir = Path(scenarios_dir)
    return load_scenario(scenarios_dir / f"{name}.json")


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def _smoke_test() -> int:
    """Load all three pre-built scenarios and print a validation summary.

    Returns:
        0 if all scenarios loaded clean, 1 if any failed.
    """
    scenarios_dir = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "scenarios"
    scenario_files = sorted(p for p in scenarios_dir.glob("*.json"))

    if not scenario_files:
        print(f"No scenario files found in {scenarios_dir}", file=sys.stderr)
        return 1

    print(f"Compliance Academy scenario loader smoke test")
    print(f"Scenarios directory: {scenarios_dir}")
    print(f"Found {len(scenario_files)} scenario file(s)")
    print("=" * 78)

    failures = 0
    for path in scenario_files:
        try:
            merged = load_scenario(path)
        except (ScenarioLoadError, ScenarioValidationError) as exc:
            failures += 1
            print(f"FAIL  {path.name}")
            print(f"      {type(exc).__name__}: {exc}")
            continue

        perp = next((s["name"] for s in merged["suspects"] if s["is_perpetrator"]), "?")
        herrings = [s["name"] for s in merged["suspects"] if s["is_red_herring"]]
        n_evidence = len(merged["evidence_seeds"])
        n_controls = len(merged["violated_controls"])
        n_systems = len(merged["involved_systems"])

        print(f"OK    {path.name}")
        print(f"      id={merged['scenario_id']}  name={merged['scenario_name']!r}")
        print(f"      pattern={merged['attack_pattern_category']}  "
              f"systems={n_systems}  controls={n_controls}  evidence={n_evidence}")
        print(f"      perpetrator={perp}  red_herrings={herrings}")

    print("=" * 78)
    if failures:
        print(f"{failures} of {len(scenario_files)} scenarios FAILED to load")
        return 1
    print(f"All {len(scenario_files)} scenarios loaded clean")
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
