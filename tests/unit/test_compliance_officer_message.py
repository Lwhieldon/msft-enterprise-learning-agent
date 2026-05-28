"""Unit tests for Compliance Officer user message construction.

Includes the regression test for the Azure jailbreak-detector false positive
we hit in dry runs: the user message must not contain meta-references to
the system prompt (phrases like "follow the structure from your system
prompt" or "calibrate per the prompt's guidance"), because Azure's
ResponsibleAIPolicyViolation detector flags those as prompt injection
attempts and returns HTTP 400 before any tokens stream.

These are unit tests against the pure message-building functions; no Azure
calls are made.
"""

from __future__ import annotations

import pytest

from src.agents.compliance_officer import (
    _build_retrieval_query,
    _build_user_message,
    _format_outcome_briefing,
    _format_violated_controls,
)


# ---------------------------------------------------------------------------
# _format_outcome_briefing
# ---------------------------------------------------------------------------


class TestFormatOutcomeBriefing:
    """The outcome briefing must convey case facts without instructing the
    agent on how to respond. Instructions belong in the system prompt."""

    def test_correct_outcome_states_facts(self, default_scenario):
        """Correct accusation: Riley Park is the actual perpetrator in SCN-001."""
        briefing = _format_outcome_briefing(
            default_scenario,
            accused_suspect_id="riley_park",
            outcome="correct",
        )

        assert "Riley Park" in briefing
        assert "correct" in briefing.lower()

    def test_wrong_perpetrator_outcome_names_both_actual_and_accused(
        self, default_scenario
    ):
        """When the player accuses the wrong person, the briefing should
        identify both who they accused AND who was actually responsible."""
        # Alex Chen is the red herring; Riley Park is the actual perpetrator.
        briefing = _format_outcome_briefing(
            default_scenario,
            accused_suspect_id="alex_chen",
            outcome="wrong_perpetrator",
        )

        assert "Alex Chen" in briefing
        assert "Riley Park" in briefing
        assert "incorrect" in briefing.lower()

    def test_wrong_perpetrator_briefing_flags_red_herring_explicitly(
        self, default_scenario
    ):
        """When the accused was a red herring, the briefing should say so."""
        briefing = _format_outcome_briefing(
            default_scenario,
            accused_suspect_id="alex_chen",   # the red herring in SCN-001
            outcome="wrong_perpetrator",
        )

        assert "red herring" in briefing.lower()

    def test_wrong_perpetrator_briefing_does_not_flag_non_herring(
        self, default_scenario
    ):
        """If the accused was a regular tangential suspect (not the perpetrator
        and not a red herring), don't claim it was a red herring."""
        # Find a tangential suspect (not perp, not red herring) in the default scenario.
        tangential = next(
            s for s in default_scenario["suspects"]
            if not s["is_perpetrator"] and not s["is_red_herring"]
        )
        briefing = _format_outcome_briefing(
            default_scenario,
            accused_suspect_id=tangential["suspect_id"],
            outcome="wrong_perpetrator",
        )

        assert "red herring" not in briefing.lower()

    def test_no_accusation_briefing_omits_accused_name(self, default_scenario):
        briefing = _format_outcome_briefing(
            default_scenario,
            accused_suspect_id=None,
            outcome="no_accusation",
        )

        assert "without naming a perpetrator" in briefing
        assert "Riley Park" in briefing  # actual perp still named


# ---------------------------------------------------------------------------
# _format_violated_controls
# ---------------------------------------------------------------------------


class TestFormatViolatedControls:
    """The CO's user message includes the scenario's violated controls as
    source material for citation."""

    def test_empty_controls_returns_placeholder(self):
        result = _format_violated_controls([])
        assert "no controls" in result.lower()

    def test_each_control_rendered_with_framework_identifier_summary(self):
        controls = [
            {"framework": "SOC 2", "identifier": "CC9.2",
             "summary": "Vendor risk management"},
            {"framework": "Helix Dynamics", "identifier": "HD-SEC-VR-001 §7",
             "summary": "Out-of-cycle vendor reassessment"},
        ]
        result = _format_violated_controls(controls)

        assert "SOC 2 CC9.2" in result
        assert "Vendor risk management" in result
        assert "HD-SEC-VR-001 §7" in result
        assert "Helix Dynamics" in result


# ---------------------------------------------------------------------------
# _build_user_message  (REGRESSION TESTS for the jailbreak fix)
# ---------------------------------------------------------------------------


# Phrases that previously triggered Azure's jailbreak detector. The user
# message MUST NOT contain any of these.
JAILBREAK_TRIGGER_PHRASES: list[str] = [
    "your system prompt",
    "Calibrate per the prompt",
    "Follow the structure from",
    "OUTCOME: correct",
    "OUTCOME: wrong",
    "OUTCOME: no accusation",
    "Calibrate per the",
]


class TestUserMessageDoesNotTriggerJailbreakFilter:
    """REGRESSION: the user message must not reference the system prompt or
    instruct the model how to respond. Azure's ResponsibleAIPolicyViolation
    detector flags those phrases as prompt injection attempts.

    The case that caused this regression and how we fixed it is in the
    project's transcript history. These tests pin the fix so it does not
    regress when the wrapper is touched later.
    """

    @pytest.mark.parametrize("outcome", ["correct", "wrong_perpetrator",
                                          "no_accusation"])
    @pytest.mark.parametrize("phrase", JAILBREAK_TRIGGER_PHRASES)
    def test_message_does_not_contain_jailbreak_trigger_phrase(
        self, default_scenario, outcome, phrase
    ):
        accused = "riley_park" if outcome == "correct" else (
            "alex_chen" if outcome == "wrong_perpetrator" else None
        )
        message = _build_user_message(default_scenario, accused, outcome)
        assert phrase not in message, (
            f"User message for outcome={outcome!r} contains jailbreak trigger "
            f"phrase {phrase!r}. This phrasing previously caused Azure to "
            f"return HTTP 400 ResponsibleAIPolicyViolation."
        )


class TestUserMessageContainsRequiredCaseData:
    """The user message provides the CO with the facts she needs to
    produce her closing speech."""

    def test_message_includes_scenario_name(self, default_scenario):
        message = _build_user_message(default_scenario, "riley_park", "correct")
        assert default_scenario["scenario_name"] in message

    def test_message_includes_scenario_id(self, default_scenario):
        message = _build_user_message(default_scenario, "riley_park", "correct")
        assert default_scenario["scenario_id"] in message

    def test_message_includes_violated_controls(self, default_scenario):
        message = _build_user_message(default_scenario, "riley_park", "correct")
        # Every control's identifier should appear in the message
        for control in default_scenario["violated_controls"]:
            assert control["identifier"] in message

    def test_message_includes_compliance_lesson_seed(self, default_scenario):
        message = _build_user_message(default_scenario, "riley_park", "correct")
        # The lesson is multi-paragraph; check that at least its first
        # sentence is present
        lesson = default_scenario["compliance_lesson"]
        first_sentence = lesson.split(".")[0]
        assert first_sentence in message

    def test_message_for_correct_outcome_mentions_actual_perpetrator(
        self, default_scenario
    ):
        message = _build_user_message(default_scenario, "riley_park", "correct")
        assert "Riley Park" in message


# ---------------------------------------------------------------------------
# _build_user_message — retrieved context injection
# ---------------------------------------------------------------------------


class TestBuildUserMessageWithRetrievedContext:
    """Cover the new ``retrieved_context`` parameter on ``_build_user_message``.

    The existing tests above use the 3-arg signature; the default empty
    string for ``retrieved_context`` preserves the legacy behavior (no
    retrieval section). These tests cover the new behavior.
    """

    def test_empty_retrieved_context_does_not_add_section(self, default_scenario):
        msg = _build_user_message(
            default_scenario, "riley_park", "correct", retrieved_context=""
        )
        assert "Foundry IQ" not in msg
        assert "Additional policy" not in msg

    def test_omitted_retrieved_context_does_not_add_section(self, default_scenario):
        """3-arg signature must still work and produce no retrieval section."""
        msg = _build_user_message(default_scenario, "riley_park", "correct")
        assert "Foundry IQ" not in msg
        assert "Additional policy" not in msg

    def test_non_empty_retrieved_context_adds_section(self, default_scenario):
        retrieved = (
            "[Source 1: access_control_policy.md]\n"
            "Vendor accounts must be sponsored by a Helix Dynamics manager."
        )
        msg = _build_user_message(
            default_scenario, "riley_park", "correct", retrieved_context=retrieved
        )
        assert "Additional policy and framework passages" in msg
        assert "live from Foundry IQ" in msg
        assert "access_control_policy.md" in msg
        assert "sponsored by a Helix Dynamics manager" in msg

    def test_retrieved_context_appears_before_closing_request(
        self, default_scenario
    ):
        """The retrieval section must land BEFORE the 'Please deliver the
        closing segment' line so the model treats it as source material,
        not as part of the ask."""
        retrieved = "[Source 1: policy.md]\nSome policy text."
        msg = _build_user_message(
            default_scenario, "riley_park", "correct", retrieved_context=retrieved
        )
        idx_retrieved = msg.index("Additional policy")
        idx_request = msg.index("Please deliver")
        assert idx_retrieved < idx_request

    def test_retrieved_context_does_not_displace_scenario_data(
        self, default_scenario
    ):
        """All existing CO scenario sections must remain when retrieved
        context is added."""
        retrieved = "[Source 1: policy.md]\nSample."
        msg = _build_user_message(
            default_scenario, "riley_park", "correct", retrieved_context=retrieved
        )
        assert "## Case outcome" in msg
        assert "## Violated controls" in msg
        assert "## Compliance lesson source material" in msg

    def test_retrieved_context_does_not_trigger_jailbreak_phrases(
        self, default_scenario
    ):
        """The retrieval section must stay pure-data: no behavioral
        instructions, no meta-references to the system prompt. This
        guards against re-triggering the Azure jailbreak detector that
        previously fired on CO messages."""
        retrieved = "[Source 1: policy.md]\nSample."
        msg = _build_user_message(
            default_scenario, "riley_park", "correct", retrieved_context=retrieved
        )
        jailbreak_phrases = [
            "your system prompt",
            "Follow the structure from",
            "Calibrate per the prompt",
            "per the prompt's guidance",
        ]
        for phrase in jailbreak_phrases:
            assert phrase.lower() not in msg.lower(), (
                f"Retrieval section must not include '{phrase}' — it triggers "
                f"Azure's jailbreak detector."
            )


# ---------------------------------------------------------------------------
# _build_retrieval_query
# ---------------------------------------------------------------------------


class TestBuildRetrievalQuery:
    """Build a Foundry IQ retrieval query from the scenario's violated controls."""

    def test_empty_scenario_returns_empty_string(self):
        assert _build_retrieval_query({}) == ""

    def test_empty_controls_list_returns_empty_string(self):
        assert _build_retrieval_query({"violated_controls": []}) == ""

    def test_none_controls_returns_empty_string(self):
        assert _build_retrieval_query({"violated_controls": None}) == ""

    def test_single_control_emits_framework_and_identifier(self):
        scenario = {
            "violated_controls": [
                {"framework": "SOC 2", "identifier": "CC9.2", "summary": ""},
            ]
        }
        assert _build_retrieval_query(scenario) == "SOC 2 CC9.2"

    def test_multiple_controls_joined_by_space(self):
        scenario = {
            "violated_controls": [
                {"framework": "SOC 2", "identifier": "CC9.2"},
                {"framework": "HIPAA", "identifier": "§164.308(b)"},
                {"framework": "Helix", "identifier": "HD-SEC-AC-001"},
            ]
        }
        result = _build_retrieval_query(scenario)
        assert "SOC 2 CC9.2" in result
        assert "HIPAA §164.308(b)" in result
        assert "Helix HD-SEC-AC-001" in result

    def test_missing_framework_falls_through_to_identifier_only(self):
        scenario = {
            "violated_controls": [
                {"identifier": "HD-SEC-AC-001"},
            ]
        }
        assert _build_retrieval_query(scenario) == "HD-SEC-AC-001"

    def test_missing_identifier_falls_through_to_framework_only(self):
        scenario = {
            "violated_controls": [
                {"framework": "SOC 2"},
            ]
        }
        assert _build_retrieval_query(scenario) == "SOC 2"

    def test_completely_empty_control_skipped(self):
        scenario = {
            "violated_controls": [
                {"framework": "", "identifier": ""},
                {"framework": "SOC 2", "identifier": "CC9.2"},
            ]
        }
        assert _build_retrieval_query(scenario) == "SOC 2 CC9.2"

    def test_query_uses_default_scenario_data(self, default_scenario):
        """Smoke test against a real scenario: the query is non-empty and
        includes recognizable framework tokens."""
        query = _build_retrieval_query(default_scenario)
        assert query, "Default scenario should produce a non-empty query"
        # The default scenario has SOC 2 controls
        assert "SOC" in query or "HIPAA" in query or "HD-SEC" in query
