"""Unit tests for ``src.scenario_loader``.

Covers the loader's contract: validation rules, merge semantics, normalization
defaults, and error handling on malformed input. Pure Python logic; no Azure
calls.

Test categories:
    - Happy path: each pre-built scenario loads cleanly
    - Merge semantics: base persona + override produce the expected fields
    - Normalization: missing soft-optional fields default correctly
    - Validation: each rule rejects the right kind of malformed input
    - Programmatic: load_scenario_from_dict works for runtime scenarios
"""

from __future__ import annotations

import copy

import pytest

from src.scenario_loader import (
    CANONICAL_SUSPECT_IDS,
    ScenarioValidationError,
    load_scenario_by_name,
    load_scenario_from_dict,
)


# ---------------------------------------------------------------------------
# Happy path: each pre-built scenario loads cleanly
# ---------------------------------------------------------------------------


class TestPreBuiltScenariosLoad:
    """Every shipping scenario must load through the validator without error."""

    def test_default_scenario_loads(self, default_scenario):
        assert default_scenario["scenario_id"] == "SCN-001"
        assert default_scenario["scenario_name"] == "Breach at Helix Dynamics"

    def test_supplychain_scenario_loads(self, supplychain_scenario):
        assert supplychain_scenario["scenario_id"] == "SCN-002"
        assert "LabConnect" in supplychain_scenario["scenario_name"]

    def test_vishing_scenario_loads(self, vishing_scenario):
        assert vishing_scenario["scenario_id"] == "SCN-003"
        assert "Help Desk" in vishing_scenario["scenario_name"]


# ---------------------------------------------------------------------------
# Merge semantics
# ---------------------------------------------------------------------------


class TestMergeSemantics:
    """The loader merges base personas with scenario overrides per the
    rules documented in scenario_commons.json."""

    def test_merged_scenario_has_all_canonical_suspects(self, default_scenario):
        suspect_ids = {s["suspect_id"] for s in default_scenario["suspects"]}
        assert suspect_ids == set(CANONICAL_SUSPECT_IDS)

    def test_merged_scenario_has_exactly_one_perpetrator(self, default_scenario):
        perps = [s for s in default_scenario["suspects"] if s["is_perpetrator"]]
        assert len(perps) == 1

    def test_merged_scenario_has_at_least_one_red_herring(self, default_scenario):
        herrings = [s for s in default_scenario["suspects"] if s["is_red_herring"]]
        assert 1 <= len(herrings) <= 2

    def test_perpetrator_and_red_herring_are_mutually_exclusive(self, default_scenario):
        for s in default_scenario["suspects"]:
            assert not (s["is_perpetrator"] and s["is_red_herring"])

    def test_merged_suspect_has_name_from_base_persona(self, default_scenario):
        # Casey Doyle's name comes from the base persona, not the override
        casey = next(s for s in default_scenario["suspects"]
                     if s["suspect_id"] == "casey_doyle")
        assert casey["name"] == "Casey Doyle"

    def test_merged_suspect_role_uses_specific_role_from_override(self, default_scenario):
        # The merged 'role' field should come from override.specific_role, not
        # from the base persona's role_family. We assert by checking that the
        # scenario-specific role for Casey (Executive Assistant to the CSO)
        # is what landed in the merged dict.
        casey = next(s for s in default_scenario["suspects"]
                     if s["suspect_id"] == "casey_doyle")
        # role_family is data owned by scenario_commons.json (we do not pin it
        # here so the test stays decoupled from base persona text changes).
        assert casey["role_family"], "merged suspect must carry role_family from base"
        # The override-driven role should include the CSO-specific phrasing.
        assert "Chief Scientific Officer" in casey["role"]

    def test_merged_backstory_combines_base_and_override(self, default_scenario):
        # The merged backstory is base.backstory_core + " " + override.scenario_context.
        # Both halves should be present in the merged string.
        for suspect in default_scenario["suspects"]:
            assert suspect["backstory"], (
                f"suspect {suspect['suspect_id']} has empty merged backstory"
            )

    def test_compliance_lesson_is_non_empty(self, default_scenario):
        lesson = default_scenario["compliance_lesson"]
        assert lesson and len(lesson) > 100, (
            "compliance_lesson should be substantive prose, not a placeholder"
        )

    def test_violated_controls_include_framework_and_helix_policy(self, default_scenario):
        frameworks = {c["framework"] for c in default_scenario["violated_controls"]}
        assert "Helix Dynamics" in frameworks
        # At least one external framework
        assert frameworks - {"Helix Dynamics"}, (
            "violated_controls must cite at least one external framework"
        )


# ---------------------------------------------------------------------------
# Normalization: missing soft-optional fields get safe defaults
# ---------------------------------------------------------------------------


class TestNormalizationDefaults:
    """Some fields are required by validation but semantically optional.

    The normalization layer fills in safe defaults before validation so the
    Scenario Generator (which sometimes omits these fields) does not break
    hot-load. This is the demo-resilience contract.
    """

    def _minimal_valid_scenario(self) -> dict:
        """Build the smallest scenario override that should pass validation,
        with leak_conditions intentionally OMITTED from a tangential suspect
        to exercise the normalization layer."""
        return {
            "_extends": "_shared/scenario_commons.json",
            "scenario_id": "TEST-001",
            "scenario_name": "Normalization test scenario",
            "premise_narration": (
                "A synthetic test scenario used only for normalization "
                "regression checks. Not playable."
            ),
            "attack_pattern_category": "credential_compromise",
            "violated_controls": [
                {
                    "framework": "SOC 2",
                    "identifier": "CC6.1",
                    "summary": "Test framework control",
                },
                {
                    "framework": "Helix Dynamics",
                    "identifier": "HD-SEC-AC-001 §1",
                    "summary": "Test Helix policy",
                },
            ],
            "involved_systems": ["Microsoft Entra ID"],
            "suspects": [
                self._suspect("alex_chen", is_perpetrator=False, is_red_herring=False,
                              include_leak_conditions=True),
                self._suspect("morgan_webb", is_perpetrator=True, is_red_herring=False,
                              include_leak_conditions=True),
                self._suspect("riley_park", is_perpetrator=False, is_red_herring=True,
                              include_leak_conditions=True),
                # Casey deliberately MISSING leak_conditions field
                self._suspect("casey_doyle", is_perpetrator=False, is_red_herring=False,
                              include_leak_conditions=False),
                self._suspect("jordan_smith", is_perpetrator=False, is_red_herring=False,
                              include_leak_conditions=True),
            ],
            "evidence_seeds": [
                {
                    "evidence_id": "EV-001",
                    "source": "test source",
                    "content": "test evidence content",
                    "value": 5,
                    "supports_suspect": "morgan_webb",
                    "appears_to_support_suspect": "morgan_webb",
                },
            ],
            "clue_graph": {"nodes": [], "edges": []},
            "compliance_lesson": (
                "Test scenario lesson. This is intentionally generic test "
                "content used to exercise the normalization and validation "
                "layers of the loader."
            ),
        }

    def _suspect(self, suspect_id: str, is_perpetrator: bool, is_red_herring: bool,
                 include_leak_conditions: bool) -> dict:
        base = {
            "suspect_id": suspect_id,
            "specific_role": "Test role",
            "scenario_context": "Test scenario context for this suspect.",
            "starting_trust": 0.5,
            "alibi": "Test alibi with verifiability cue.",
            "open_knowledge": "Test open knowledge.",
            "guarded_knowledge": "Test guarded knowledge.",
            "hidden_truth": "Test hidden truth with specific detail and a second sentence.",
            "is_perpetrator": is_perpetrator,
            "is_red_herring": is_red_herring,
        }
        if include_leak_conditions:
            base["leak_conditions"] = ["Test trigger 1", "Test trigger 2"]
        return base

    def test_missing_leak_conditions_defaults_to_empty_list(self):
        scenario = self._minimal_valid_scenario()

        merged = load_scenario_from_dict(scenario)

        casey = next(s for s in merged["suspects"]
                     if s["suspect_id"] == "casey_doyle")
        assert casey["leak_conditions"] == [], (
            "Missing leak_conditions on a suspect should normalize to []"
        )

    def test_present_leak_conditions_are_preserved(self):
        scenario = self._minimal_valid_scenario()

        merged = load_scenario_from_dict(scenario)

        morgan = next(s for s in merged["suspects"]
                      if s["suspect_id"] == "morgan_webb")
        assert morgan["leak_conditions"] == ["Test trigger 1", "Test trigger 2"]


# ---------------------------------------------------------------------------
# Validation: each rule rejects the right kind of malformed input
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """The loader rejects malformed scenarios with specific error messages."""

    def _valid_scenario(self) -> dict:
        """A known-good scenario we then mutate per test to exercise one
        validation rule at a time."""
        # Reuse the normalization test's scenario factory by instantiating
        # a normalization helper and getting a valid scenario from it.
        # This keeps test data in one place.
        helper = TestNormalizationDefaults()
        scenario = helper._minimal_valid_scenario()
        # Add leak_conditions to all so the only validation failure we test
        # is the one we deliberately introduce.
        for s in scenario["suspects"]:
            s.setdefault("leak_conditions", [])
        return scenario

    def test_missing_top_level_field_fails(self):
        scenario = self._valid_scenario()
        del scenario["compliance_lesson"]
        with pytest.raises(ScenarioValidationError, match="compliance_lesson"):
            load_scenario_from_dict(scenario)

    def test_wrong_suspect_count_fails(self):
        scenario = self._valid_scenario()
        scenario["suspects"] = scenario["suspects"][:4]  # only 4
        with pytest.raises(ScenarioValidationError, match="canonical IDs"):
            load_scenario_from_dict(scenario)

    def test_zero_perpetrators_fails(self):
        scenario = self._valid_scenario()
        for s in scenario["suspects"]:
            s["is_perpetrator"] = False
        with pytest.raises(ScenarioValidationError, match="perpetrator"):
            load_scenario_from_dict(scenario)

    def test_multiple_perpetrators_fails(self):
        scenario = self._valid_scenario()
        scenario["suspects"][0]["is_perpetrator"] = True
        scenario["suspects"][1]["is_perpetrator"] = True
        with pytest.raises(ScenarioValidationError, match="perpetrator"):
            load_scenario_from_dict(scenario)

    def test_zero_red_herrings_fails(self):
        scenario = self._valid_scenario()
        for s in scenario["suspects"]:
            s["is_red_herring"] = False
        with pytest.raises(ScenarioValidationError, match="red herring"):
            load_scenario_from_dict(scenario)

    def test_starting_trust_out_of_range_fails(self):
        scenario = self._valid_scenario()
        scenario["suspects"][0]["starting_trust"] = 1.5
        with pytest.raises(ScenarioValidationError, match="starting_trust"):
            load_scenario_from_dict(scenario)

    def test_perpetrator_marked_as_red_herring_fails(self):
        scenario = self._valid_scenario()
        # Find the perpetrator and also mark them as a red herring
        for s in scenario["suspects"]:
            if s["is_perpetrator"]:
                s["is_red_herring"] = True
                break
        with pytest.raises(ScenarioValidationError, match="both perpetrator and red herring"):
            load_scenario_from_dict(scenario)

    def test_only_helix_policy_no_framework_fails(self):
        scenario = self._valid_scenario()
        # Strip all external framework citations, leave only Helix policy
        scenario["violated_controls"] = [
            c for c in scenario["violated_controls"]
            if c["framework"] == "Helix Dynamics"
        ]
        with pytest.raises(ScenarioValidationError, match="external framework"):
            load_scenario_from_dict(scenario)

    def test_no_helix_policy_fails(self):
        scenario = self._valid_scenario()
        scenario["violated_controls"] = [
            c for c in scenario["violated_controls"]
            if c["framework"] != "Helix Dynamics"
        ]
        with pytest.raises(ScenarioValidationError, match="Helix Dynamics policy"):
            load_scenario_from_dict(scenario)
