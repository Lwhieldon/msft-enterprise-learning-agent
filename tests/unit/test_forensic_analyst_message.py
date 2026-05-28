"""Unit tests for Forensic Analyst user message construction.

The Forensic Analyst's quality on stream depends on her getting the right
case briefing as source material. These tests pin the format of the briefing
so a future refactor cannot quietly degrade what the analyst sees.

Pure logic tests; no Azure calls.
"""

from __future__ import annotations

import pytest

from src.agents.forensic_analyst import (
    _build_user_message,
    _format_evidence_seeds,
    _format_suspect_summary,
    _format_violated_controls,
)


# ---------------------------------------------------------------------------
# _format_violated_controls
# ---------------------------------------------------------------------------


class TestFormatViolatedControls:
    """The analyst's user message includes the scenario's violated controls
    as citation source material."""

    def test_empty_controls_returns_placeholder(self):
        result = _format_violated_controls([])
        assert "no controls" in result.lower()

    def test_single_control_rendered_with_full_citation(self):
        controls = [
            {"framework": "SOC 2", "identifier": "CC6.1",
             "summary": "Logical access controls"},
        ]
        result = _format_violated_controls(controls)
        assert "SOC 2 CC6.1" in result
        assert "Logical access controls" in result

    def test_multiple_controls_each_appear(self):
        controls = [
            {"framework": "SOC 2", "identifier": "CC9.2",
             "summary": "Vendor risk management"},
            {"framework": "NIST 800-53", "identifier": "AC-2(4)",
             "summary": "Account management"},
            {"framework": "Helix Dynamics", "identifier": "HD-SEC-VR-001 §7",
             "summary": "Out-of-cycle vendor reassessment"},
        ]
        result = _format_violated_controls(controls)
        assert "SOC 2 CC9.2" in result
        assert "NIST 800-53 AC-2(4)" in result
        assert "HD-SEC-VR-001 §7" in result


# ---------------------------------------------------------------------------
# _format_evidence_seeds
# ---------------------------------------------------------------------------


class TestFormatEvidenceSeeds:
    """Evidence rendering is core to the analyst's value: she needs the
    evidence_id, source, content, value, and supports_suspect for every item
    so she can cite specifics under questioning."""

    def test_empty_evidence_returns_placeholder(self):
        result = _format_evidence_seeds([])
        assert "no evidence" in result.lower()

    def test_evidence_rendering_includes_all_quotable_fields(self):
        evidence = [
            {
                "evidence_id": "EV-001",
                "source": "Microsoft Entra ID sign-in logs",
                "content": "casey.doyle signed in from Sofia at 11:23 PM.",
                "value": 5,
                "supports_suspect": "casey_doyle",
                "appears_to_support_suspect": "casey_doyle",
            }
        ]
        result = _format_evidence_seeds(evidence)
        assert "EV-001" in result
        assert "Microsoft Entra ID sign-in logs" in result
        assert "casey_doyle" in result
        assert "5" in result  # value
        assert "Sofia" in result  # content body

    def test_multiple_evidence_items_all_appear(self):
        evidence = [
            {"evidence_id": "EV-001", "source": "Source A",
             "content": "Content A", "value": 3,
             "supports_suspect": "alex_chen"},
            {"evidence_id": "EV-002", "source": "Source B",
             "content": "Content B", "value": 4,
             "supports_suspect": "morgan_webb"},
            {"evidence_id": "EV-003", "source": "Source C",
             "content": "Content C", "value": 5,
             "supports_suspect": "riley_park"},
        ]
        result = _format_evidence_seeds(evidence)
        for eid in ("EV-001", "EV-002", "EV-003"):
            assert eid in result

    def test_default_scenario_evidence_renders_without_error(self, default_scenario):
        """Smoke check against real data: the default scenario's 12 evidence
        seeds should render cleanly through the formatter."""
        result = _format_evidence_seeds(default_scenario["evidence_seeds"])
        assert result.strip()
        # Every evidence_id from the scenario should appear in the rendered
        # output, otherwise the analyst is missing source material.
        for ev in default_scenario["evidence_seeds"]:
            assert ev["evidence_id"] in result


# ---------------------------------------------------------------------------
# _format_suspect_summary
# ---------------------------------------------------------------------------


class TestFormatSuspectSummary:
    """The analyst gets a concise suspect roster so she can reference any
    of them by name without us needing to inject full personas."""

    def test_empty_suspect_list_renders_to_empty_string(self):
        # Edge case; not realistic but the function should not crash
        result = _format_suspect_summary([])
        assert result == ""

    def test_each_suspect_appears_with_name_and_role(self, default_scenario):
        result = _format_suspect_summary(default_scenario["suspects"])
        for suspect in default_scenario["suspects"]:
            assert suspect["name"] in result
            assert suspect["suspect_id"] in result

    def test_summary_is_one_line_per_suspect(self, default_scenario):
        result = _format_suspect_summary(default_scenario["suspects"])
        # Five canonical suspects; expect five non-empty lines
        non_empty_lines = [line for line in result.split("\n") if line.strip()]
        assert len(non_empty_lines) == 5


# ---------------------------------------------------------------------------
# _build_user_message  (full case briefing assembly)
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    """The user message stitches the case briefing together. We pin the
    structural pieces so the analyst's grounding cannot silently regress."""

    def test_message_includes_scenario_name_and_id(self, default_scenario):
        message = _build_user_message(default_scenario, "test question")
        assert default_scenario["scenario_name"] in message
        assert default_scenario["scenario_id"] in message

    def test_message_includes_premise_narration(self, default_scenario):
        message = _build_user_message(default_scenario, "test question")
        assert default_scenario["premise_narration"] in message

    def test_message_includes_all_evidence_ids(self, default_scenario):
        message = _build_user_message(default_scenario, "test question")
        for ev in default_scenario["evidence_seeds"]:
            assert ev["evidence_id"] in message

    def test_message_includes_all_control_identifiers(self, default_scenario):
        message = _build_user_message(default_scenario, "test question")
        for control in default_scenario["violated_controls"]:
            assert control["identifier"] in message

    def test_message_includes_all_involved_systems(self, default_scenario):
        message = _build_user_message(default_scenario, "test question")
        for system in default_scenario["involved_systems"]:
            assert system in message

    def test_message_includes_player_question_verbatim(self, default_scenario):
        question = "What does the access pattern tell us about the breach window?"
        message = _build_user_message(default_scenario, question)
        assert question in message

    def test_message_for_different_scenarios_differs(
        self, default_scenario, supplychain_scenario
    ):
        """Same player question, different scenarios should produce
        different briefings. Catches accidental hardcoding."""
        question = "Walk me through this."
        msg_default = _build_user_message(default_scenario, question)
        msg_supply = _build_user_message(supplychain_scenario, question)
        assert msg_default != msg_supply

    def test_briefing_marker_separates_briefing_from_question(self, default_scenario):
        """The user message uses a separator so the model can distinguish
        case context from the actual question."""
        question = "Walk me through this."
        message = _build_user_message(default_scenario, question)
        # The separator is "---" or similar; just check that the question
        # appears AFTER the premise (briefing comes first, then question).
        premise_pos = message.find(default_scenario["premise_narration"])
        question_pos = message.find(question)
        assert premise_pos < question_pos, (
            "Player question should appear after the case briefing in the "
            "user message structure."
        )


# ---------------------------------------------------------------------------
# _build_user_message — retrieved context injection
# ---------------------------------------------------------------------------


class TestBuildUserMessageWithRetrievedContext:
    """Cover the new ``retrieved_context`` parameter on ``_build_user_message``.

    The existing TestBuildUserMessage tests above continue to use the
    2-arg signature; the default empty string preserves the legacy
    behavior (no retrieval section in the output). These tests cover the
    new behavior when retrieved context is supplied.
    """

    def test_empty_retrieved_context_does_not_add_section(self, default_scenario):
        """Empty default preserves the message shape for callers that
        don't use Foundry IQ retrieval (and for every existing test).

        Note: we check for the unique section header text — not the bare
        string 'Foundry IQ' — because the scenario data itself may mention
        Foundry IQ as a named system in Helix's tech stack.
        """
        msg = _build_user_message(
            default_scenario, "What happened?", retrieved_context=""
        )
        assert "Retrieved policy and framework context" not in msg
        assert "live from Foundry IQ" not in msg

    def test_omitted_retrieved_context_does_not_add_section(self, default_scenario):
        """Calling with the 2-arg signature must still work and must not
        add a retrieval section."""
        msg = _build_user_message(default_scenario, "What happened?")
        assert "Retrieved policy and framework context" not in msg
        assert "live from Foundry IQ" not in msg

    def test_non_empty_retrieved_context_adds_section(self, default_scenario):
        retrieved = (
            "[Source 1: access_control_policy.md]\n"
            "Vendor accounts must be sponsored by a Helix Dynamics manager."
        )
        msg = _build_user_message(
            default_scenario, "What happened?", retrieved_context=retrieved
        )
        assert "Retrieved policy and framework context" in msg
        assert "live from Foundry IQ" in msg
        assert "access_control_policy.md" in msg
        assert "sponsored by a Helix Dynamics manager" in msg

    def test_retrieved_context_appears_between_briefing_and_question(
        self, default_scenario
    ):
        """The retrieval section must land AFTER the case briefing but
        BEFORE the player's question. This positioning matters because
        the model treats the final question as 'the ask' and prior
        sections as 'the context'."""
        retrieved = (
            "[Source 1: access_control_policy.md]\n"
            "Sample policy text content here."
        )
        question = "VERYUNIQUEPLAYERQUESTIONABC123"
        msg = _build_user_message(
            default_scenario, question, retrieved_context=retrieved
        )
        idx_briefing = msg.index("Case briefing")
        idx_retrieved = msg.index("Retrieved policy")
        idx_question = msg.index(question)
        assert idx_briefing < idx_retrieved < idx_question

    def test_retrieved_context_does_not_displace_scenario_data(
        self, default_scenario
    ):
        """Adding retrieved context must not strip any of the scenario
        briefing sections — evidence, controls, suspects, premise should
        all still be present."""
        retrieved = "[Source 1: policy.md]\nSample policy."
        msg = _build_user_message(
            default_scenario, "Question?", retrieved_context=retrieved
        )
        assert "### Premise" in msg
        assert "### Suspects" in msg
        assert "### Evidence available to you" in msg
        assert "### Violated controls" in msg
        assert "### Involved systems" in msg
