"""Unit tests for scenario data integrity.

The three pre-built scenarios are hand-authored JSON. Hand-authored data is
prone to typos: evidence_id referenced in the clue graph but not in
evidence_seeds, suspect_id misspelled in a supports_suspect field, edge
referencing a node that doesn't exist, value out of expected range.

These tests cross-reference every internal pointer in each pre-built
scenario so that any such inconsistency fails fast in CI rather than
silently degrading agent behavior on stream.

What's covered (across all three pre-built scenarios):
    - Every evidence_id is unique within the scenario
    - Every supports_suspect / appears_to_support_suspect points to a real
      canonical suspect_id
    - Every clue_graph evidence node has a matching evidence_seed (and vice
      versa)
    - Every clue_graph suspect node corresponds to a canonical suspect_id
    - Every edge.from and edge.to references an actual node in the graph
    - Every evidence value is in the documented 1-10 range
    - compliance_lesson is substantive
"""

from __future__ import annotations

import pytest


CANONICAL_SUSPECT_IDS = frozenset({
    "alex_chen", "morgan_webb", "riley_park", "casey_doyle", "jordan_smith",
})

# Provided by conftest.py fixtures. Listed here for indirect parametrization.
SCENARIO_FIXTURE_NAMES = [
    "default_scenario",
    "supplychain_scenario",
    "vishing_scenario",
]


@pytest.fixture(params=SCENARIO_FIXTURE_NAMES)
def any_scenario(request):
    """Indirect-parameterized fixture so every test in this module runs
    against all three pre-built scenarios."""
    return request.getfixturevalue(request.param)


# ---------------------------------------------------------------------------
# Evidence integrity
# ---------------------------------------------------------------------------


class TestEvidenceIntegrity:

    def test_evidence_ids_are_unique(self, any_scenario):
        ids = [ev["evidence_id"] for ev in any_scenario["evidence_seeds"]]
        duplicates = {x for x in ids if ids.count(x) > 1}
        assert not duplicates, (
            f"Scenario {any_scenario['scenario_id']} has duplicate "
            f"evidence_ids: {duplicates}"
        )

    def test_evidence_count_is_reasonable(self, any_scenario):
        """Demo experience requires enough evidence for the Forensic
        Analyst to cite specifics. Below 5 the scene feels thin."""
        count = len(any_scenario["evidence_seeds"])
        assert count >= 5, (
            f"Scenario {any_scenario['scenario_id']} has only {count} "
            f"evidence items; expected at least 5 for a satisfying demo"
        )

    def test_evidence_values_in_valid_range(self, any_scenario):
        """The scenario generator prompt scopes evidence value to 1-10.
        Out-of-range values suggest a hand-authoring mistake."""
        for ev in any_scenario["evidence_seeds"]:
            assert 1 <= ev["value"] <= 10, (
                f"Evidence {ev['evidence_id']} in "
                f"{any_scenario['scenario_id']} has value={ev['value']}, "
                f"expected 1-10"
            )

    def test_supports_suspect_references_canonical_suspect(self, any_scenario):
        for ev in any_scenario["evidence_seeds"]:
            sid = ev.get("supports_suspect")
            if sid is None:
                continue  # Optional field
            assert sid in CANONICAL_SUSPECT_IDS, (
                f"Evidence {ev['evidence_id']} supports_suspect='{sid}' "
                f"which is not one of the canonical suspects "
                f"{sorted(CANONICAL_SUSPECT_IDS)}"
            )

    def test_appears_to_support_suspect_references_canonical_suspect(
        self, any_scenario
    ):
        for ev in any_scenario["evidence_seeds"]:
            sid = ev.get("appears_to_support_suspect")
            if sid is None:
                continue  # Optional field
            assert sid in CANONICAL_SUSPECT_IDS, (
                f"Evidence {ev['evidence_id']} appears_to_support_suspect="
                f"'{sid}' which is not one of the canonical suspects"
            )

    def test_every_evidence_has_substantive_content(self, any_scenario):
        """Evidence content shorter than 80 characters is almost always a
        placeholder. The Forensic Analyst needs specifics to cite."""
        for ev in any_scenario["evidence_seeds"]:
            content = ev.get("content", "")
            assert len(content) >= 80, (
                f"Evidence {ev['evidence_id']} in "
                f"{any_scenario['scenario_id']} has thin content "
                f"({len(content)} chars). Expected at least 80."
            )


# ---------------------------------------------------------------------------
# Clue graph integrity
# ---------------------------------------------------------------------------


class TestClueGraphIntegrity:

    def test_clue_graph_present(self, any_scenario):
        assert "clue_graph" in any_scenario
        assert "nodes" in any_scenario["clue_graph"]
        assert "edges" in any_scenario["clue_graph"]

    def test_node_ids_are_unique(self, any_scenario):
        ids = [n["id"] for n in any_scenario["clue_graph"]["nodes"]]
        duplicates = {x for x in ids if ids.count(x) > 1}
        assert not duplicates, (
            f"Scenario {any_scenario['scenario_id']} clue_graph has "
            f"duplicate node ids: {duplicates}"
        )

    def test_every_suspect_node_is_a_canonical_suspect(self, any_scenario):
        suspect_nodes = [
            n["id"] for n in any_scenario["clue_graph"]["nodes"]
            if n.get("type") == "suspect"
        ]
        for sid in suspect_nodes:
            assert sid in CANONICAL_SUSPECT_IDS, (
                f"Scenario {any_scenario['scenario_id']} clue_graph has "
                f"suspect node '{sid}' which is not canonical"
            )

    def test_every_canonical_suspect_appears_in_clue_graph(self, any_scenario):
        suspect_nodes = {
            n["id"] for n in any_scenario["clue_graph"]["nodes"]
            if n.get("type") == "suspect"
        }
        missing = CANONICAL_SUSPECT_IDS - suspect_nodes
        assert not missing, (
            f"Scenario {any_scenario['scenario_id']} clue_graph is missing "
            f"these canonical suspects: {missing}"
        )

    def test_every_evidence_node_matches_evidence_seed(self, any_scenario):
        evidence_node_ids = {
            n["id"] for n in any_scenario["clue_graph"]["nodes"]
            if n.get("type") == "evidence"
        }
        seed_ids = {ev["evidence_id"] for ev in any_scenario["evidence_seeds"]}
        # Every evidence node should have a matching seed (dangling node
        # in the graph means the analyst's mental model points at nothing).
        orphan_nodes = evidence_node_ids - seed_ids
        assert not orphan_nodes, (
            f"Scenario {any_scenario['scenario_id']} clue_graph has "
            f"evidence nodes with no matching evidence_seed: {orphan_nodes}"
        )

    def test_every_evidence_seed_appears_in_clue_graph(self, any_scenario):
        evidence_node_ids = {
            n["id"] for n in any_scenario["clue_graph"]["nodes"]
            if n.get("type") == "evidence"
        }
        seed_ids = {ev["evidence_id"] for ev in any_scenario["evidence_seeds"]}
        # Every seed should be a node (unreferenced seeds are dead weight).
        unreferenced_seeds = seed_ids - evidence_node_ids
        assert not unreferenced_seeds, (
            f"Scenario {any_scenario['scenario_id']} has evidence seeds "
            f"that do not appear as nodes in the clue_graph: "
            f"{unreferenced_seeds}"
        )

    def test_every_edge_endpoint_exists_as_a_node(self, any_scenario):
        node_ids = {n["id"] for n in any_scenario["clue_graph"]["nodes"]}
        for edge in any_scenario["clue_graph"]["edges"]:
            assert edge["from"] in node_ids, (
                f"Scenario {any_scenario['scenario_id']} clue_graph edge "
                f"from='{edge['from']}' references a node that does not "
                f"exist in the graph"
            )
            assert edge["to"] in node_ids, (
                f"Scenario {any_scenario['scenario_id']} clue_graph edge "
                f"to='{edge['to']}' references a node that does not exist"
            )

    def test_every_edge_has_a_relationship_label(self, any_scenario):
        for edge in any_scenario["clue_graph"]["edges"]:
            relationship = edge.get("relationship", "")
            assert relationship, (
                f"Scenario {any_scenario['scenario_id']} clue_graph has "
                f"an edge from='{edge['from']}' to='{edge['to']}' with "
                f"no relationship label"
            )


# ---------------------------------------------------------------------------
# Suspect roster integrity
# ---------------------------------------------------------------------------


class TestSuspectRosterIntegrity:

    def test_all_five_canonical_suspects_present(self, any_scenario):
        suspect_ids = {s["suspect_id"] for s in any_scenario["suspects"]}
        assert suspect_ids == CANONICAL_SUSPECT_IDS, (
            f"Scenario {any_scenario['scenario_id']} suspects "
            f"({suspect_ids}) does not match canonical roster "
            f"({CANONICAL_SUSPECT_IDS})"
        )

    def test_every_suspect_has_required_fields(self, any_scenario):
        """The suspect template uses these fields. Missing any of them
        causes the suspect agent to substitute the literal placeholder.

        Note: ``specific_role`` is an INPUT field on the override file
        that the loader consumes during merge and outputs as ``role``.
        The merged scenario carries ``role``, not ``specific_role``."""
        required_fields = {
            "suspect_id", "name", "role",
            "starting_trust", "alibi", "open_knowledge",
            "guarded_knowledge", "hidden_truth",
        }
        for suspect in any_scenario["suspects"]:
            missing = required_fields - set(suspect.keys())
            assert not missing, (
                f"Scenario {any_scenario['scenario_id']} suspect "
                f"'{suspect.get('suspect_id', '?')}' is missing required "
                f"fields: {missing}"
            )

    def test_starting_trust_in_valid_range(self, any_scenario):
        for suspect in any_scenario["suspects"]:
            trust = suspect["starting_trust"]
            assert 0.0 <= trust <= 1.0, (
                f"Scenario {any_scenario['scenario_id']} suspect "
                f"'{suspect['suspect_id']}' has starting_trust={trust}, "
                f"expected 0.0-1.0"
            )

    def test_perpetrator_has_substantive_hidden_truth(self, any_scenario):
        """The perpetrator's hidden_truth is the payoff of the scene. A
        short hidden_truth means the climax has no content."""
        perp = next(s for s in any_scenario["suspects"] if s["is_perpetrator"])
        assert len(perp["hidden_truth"]) >= 200, (
            f"Scenario {any_scenario['scenario_id']} perpetrator "
            f"'{perp['suspect_id']}' has hidden_truth of "
            f"{len(perp['hidden_truth'])} chars; expected at least 200 "
            f"for a satisfying reveal"
        )


# ---------------------------------------------------------------------------
# Compliance lesson integrity
# ---------------------------------------------------------------------------


class TestComplianceLessonIntegrity:

    def test_compliance_lesson_present_and_substantive(self, any_scenario):
        lesson = any_scenario.get("compliance_lesson", "")
        # The closing speech needs material; below 600 chars is almost
        # certainly a placeholder.
        assert len(lesson) >= 600, (
            f"Scenario {any_scenario['scenario_id']} compliance_lesson is "
            f"only {len(lesson)} chars; expected at least 600 for a "
            f"substantive closing"
        )

    def test_compliance_lesson_references_at_least_one_framework(
        self, any_scenario
    ):
        """The closing speech is supposed to anchor on framework citations.
        A lesson that mentions no frameworks suggests bland filler."""
        lesson = any_scenario["compliance_lesson"]
        framework_keywords = ["SOC 2", "NIST", "ISO 27001", "HIPAA",
                              "HD-SEC", "Helix Dynamics"]
        hits = [kw for kw in framework_keywords if kw in lesson]
        assert hits, (
            f"Scenario {any_scenario['scenario_id']} compliance_lesson "
            f"references none of the known framework keywords. The "
            f"closing speech should anchor on at least one framework."
        )


# ---------------------------------------------------------------------------
# Cross-scenario differentiation
# ---------------------------------------------------------------------------


class TestCrossScenarioDifferentiation:
    """The three scenarios should be meaningfully different so that any
    cross-scenario test (like the suspect template's premise-differs check)
    is exercising real differentiation, not noise."""

    def test_premises_are_all_different(
        self, default_scenario, supplychain_scenario, vishing_scenario
    ):
        premises = {
            default_scenario["premise_narration"],
            supplychain_scenario["premise_narration"],
            vishing_scenario["premise_narration"],
        }
        assert len(premises) == 3, (
            "Two or more pre-built scenarios share the same premise; that "
            "defeats the purpose of having multiple demo scenarios."
        )

    def test_perpetrators_are_distributed(
        self, default_scenario, supplychain_scenario, vishing_scenario
    ):
        """Different scenarios should have different perpetrators so the
        demo can showcase multiple breach patterns."""
        perps = []
        for scenario in (default_scenario, supplychain_scenario,
                         vishing_scenario):
            perp_id = next(
                s["suspect_id"] for s in scenario["suspects"]
                if s["is_perpetrator"]
            )
            perps.append(perp_id)
        # We expect three distinct perpetrators across the three scenarios.
        assert len(set(perps)) == 3, (
            f"Pre-built scenarios all use these perpetrators: {perps}. "
            f"Expected three distinct perpetrators for demo variety."
        )

    def test_attack_pattern_categories_differ(
        self, default_scenario, supplychain_scenario, vishing_scenario
    ):
        patterns = {
            default_scenario["attack_pattern_category"],
            supplychain_scenario["attack_pattern_category"],
            vishing_scenario["attack_pattern_category"],
        }
        assert len(patterns) == 3, (
            f"Pre-built scenarios should cover distinct attack patterns; "
            f"found {patterns}"
        )
