"""Unit tests for orchestrator commands not covered in test_orchestrator.py.

The main orchestrator test file covers the demo-critical commands (ask,
accuse, wrap, generate, reset, plus the read-only commands). This file
fills the remaining gaps:

    - cmd_forensic (parallel to cmd_ask, with its own history key)
    - cmd_help (renders the help text with all documented commands)
    - cmd_scenario printout when on a generated scenario (label format)

The interactive REPL loop itself (``Orchestrator.run``) is not unit tested
here; it involves ``input()`` and is exercised by integration / dry-run
testing.
"""

from __future__ import annotations

import pytest

from src.orchestrator import HELP_TEXT, Orchestrator


# ---------------------------------------------------------------------------
# cmd_forensic
# ---------------------------------------------------------------------------


class TestCmdForensic:
    """The Forensic Analyst is consulted by free-text question. Argument
    parsing is simpler than cmd_ask (no suspect_id), but the history
    persistence pattern is the same."""

    def _stub_forensic_result(self, reply="Analysis of access logs..."):
        return {
            "reply": reply,
            "elapsed_seconds": 17.5,
            "deployment": "gpt-4.1-mini",
            "attempts": 1,
        }

    def test_empty_input_prints_usage_and_does_not_call_agent(
        self, default_scenario, capsys, mocker
    ):
        mock_consult = mocker.patch(
            "src.orchestrator.consult_forensic_analyst"
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("")

        mock_consult.assert_not_called()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower()

    def test_whitespace_only_input_prints_usage(
        self, default_scenario, capsys, mocker
    ):
        mock_consult = mocker.patch(
            "src.orchestrator.consult_forensic_analyst"
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("   \t  ")

        mock_consult.assert_not_called()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower()

    def test_valid_question_calls_agent_with_stripped_input(
        self, default_scenario, mocker
    ):
        mock_consult = mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            return_value=self._stub_forensic_result(),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("  Walk me through the access logs.  ")

        mock_consult.assert_called_once()
        # The second positional arg (the question) should be stripped
        call_args = mock_consult.call_args
        assert call_args.args[1] == "Walk me through the access logs."

    def test_passes_scenario_as_first_arg(self, default_scenario, mocker):
        mock_consult = mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            return_value=self._stub_forensic_result(),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("any question")

        # First positional arg is the scenario
        assert mock_consult.call_args.args[0] is default_scenario

    def test_history_stored_under_forensic_key_not_suspect_id(
        self, default_scenario, mocker
    ):
        """Forensic Analyst history lives under the special 'forensic' key,
        distinct from any suspect_id."""
        mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            return_value=self._stub_forensic_result(reply="A reply."),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("First question.")

        assert "forensic" in orch.histories
        # And not collided with any canonical suspect
        for suspect_id in ("alex_chen", "morgan_webb", "riley_park",
                           "casey_doyle", "jordan_smith"):
            assert suspect_id not in orch.histories

    def test_history_persists_user_and_assistant_turns(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            return_value=self._stub_forensic_result(
                reply="Cited EV-002 and EV-011."
            ),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("Walk me through the logs.")

        history = orch.histories["forensic"]
        assert len(history) == 2
        assert history[0] == {"role": "user",
                              "content": "Walk me through the logs."}
        assert history[1] == {"role": "assistant",
                              "content": "Cited EV-002 and EV-011."}

    def test_multiple_consultations_persist_in_order(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            side_effect=[
                self._stub_forensic_result(reply="First analysis."),
                self._stub_forensic_result(reply="Second analysis."),
                self._stub_forensic_result(reply="Third analysis."),
            ],
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_forensic("Question one.")
        orch.cmd_forensic("Question two.")
        orch.cmd_forensic("Question three.")

        history = orch.histories["forensic"]
        assert len(history) == 6
        assert history[0]["content"] == "Question one."
        assert history[1]["content"] == "First analysis."
        assert history[2]["content"] == "Question two."
        assert history[3]["content"] == "Second analysis."
        assert history[4]["content"] == "Question three."
        assert history[5]["content"] == "Third analysis."

    def test_agent_seconds_accumulated_into_total(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            side_effect=[
                self._stub_forensic_result(reply="A") | {"elapsed_seconds": 12.5},
                self._stub_forensic_result(reply="B") | {"elapsed_seconds": 9.0},
            ],
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.total_agent_seconds == 0.0

        orch.cmd_forensic("First.")
        orch.cmd_forensic("Second.")

        assert orch.total_agent_seconds == pytest.approx(21.5)


# ---------------------------------------------------------------------------
# cmd_help
# ---------------------------------------------------------------------------


class TestCmdHelp:
    """The help command should print the HELP_TEXT constant. We pin that
    every documented command appears in the help text, so a new command
    cannot land without operator-facing documentation."""

    DOCUMENTED_COMMANDS = [
        "help", "scenario", "look", "suspects", "evidence",
        "ask", "forensic", "accuse", "wrap", "generate", "reset", "quit",
    ]

    def test_help_text_is_non_empty(self):
        assert HELP_TEXT
        assert len(HELP_TEXT) > 200

    @pytest.mark.parametrize("command", DOCUMENTED_COMMANDS)
    def test_every_documented_command_appears_in_help(self, command):
        assert command in HELP_TEXT, (
            f"Command '{command}' should be documented in HELP_TEXT but "
            f"is not"
        )

    def test_cmd_help_prints_help_text(self, default_scenario, capsys):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_help("")
        captured = capsys.readouterr()
        # Should print something substantial
        assert len(captured.out) > 200
        # Should contain the verbs
        for command in ("ask", "forensic", "accuse"):
            assert command in captured.out

    def test_cmd_help_ignores_argument(self, default_scenario, capsys):
        """cmd_help takes a rest argument but should ignore it; help is
        global, not topic-based in this MVP."""
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_help("ask")  # any argument
        captured_with_arg = capsys.readouterr().out

        orch.cmd_help("")
        captured_no_arg = capsys.readouterr().out

        assert captured_with_arg == captured_no_arg


# ---------------------------------------------------------------------------
# cmd_scenario behavior on generated scenarios
# ---------------------------------------------------------------------------


class TestCmdScenarioWithGeneratedLabel:
    """When the scenario was hot-loaded via generate, the label format is
    'generated:<id>'. cmd_scenario should still print sensibly."""

    def test_generated_label_shown_in_scenario_summary(
        self, default_scenario, capsys
    ):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.scenario_label = "generated:SCN-999"

        orch.cmd_scenario("")
        captured = capsys.readouterr()
        assert "generated:SCN-999" in captured.out

    def test_session_agent_time_reported(self, default_scenario, capsys):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.total_agent_seconds = 42.7

        orch.cmd_scenario("")
        captured = capsys.readouterr()
        assert "42.7" in captured.out


# ---------------------------------------------------------------------------
# Forensic + ask: histories must NOT collide
# ---------------------------------------------------------------------------


class TestHistoryNamespaceIsolation:
    """The orchestrator uses one ``self.histories`` dict keyed by suspect_id
    or by the literal 'forensic'. Histories from one agent must not leak
    into another's context."""

    def test_ask_and_forensic_histories_are_independent(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.interrogate_suspect",
            return_value={
                "reply": "Suspect reply.",
                "suspect_name": "Casey Doyle",
                "suspect_id": "casey_doyle",
                "elapsed_seconds": 5.0,
                "deployment": "gpt-4.1-mini",
                "attempts": 1,
            },
        )
        mocker.patch(
            "src.orchestrator.consult_forensic_analyst",
            return_value={
                "reply": "Forensic reply.",
                "elapsed_seconds": 10.0,
                "deployment": "gpt-4.1-mini",
                "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("casey_doyle Where were you Sunday?")
        orch.cmd_forensic("Walk me through the access logs.")

        # Each agent's history should contain only its own turns
        assert len(orch.histories["casey_doyle"]) == 2
        assert len(orch.histories["forensic"]) == 2
        # And the contents should not have mixed
        casey_contents = [t["content"] for t in orch.histories["casey_doyle"]]
        forensic_contents = [t["content"] for t in orch.histories["forensic"]]
        assert "Walk me through the access logs." not in casey_contents
        assert "Where were you Sunday?" not in forensic_contents

    def test_two_suspect_histories_are_independent(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.interrogate_suspect",
            side_effect=[
                {"reply": "Casey's reply.", "suspect_name": "Casey Doyle",
                 "suspect_id": "casey_doyle", "elapsed_seconds": 5.0,
                 "deployment": "x", "attempts": 1},
                {"reply": "Riley's reply.", "suspect_name": "Riley Park",
                 "suspect_id": "riley_park", "elapsed_seconds": 5.0,
                 "deployment": "x", "attempts": 1},
            ],
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("casey_doyle Question for Casey.")
        orch.cmd_ask("riley_park Question for Riley.")

        casey_contents = [t["content"] for t in orch.histories["casey_doyle"]]
        riley_contents = [t["content"] for t in orch.histories["riley_park"]]
        assert "Question for Casey." in casey_contents
        assert "Question for Riley." in riley_contents
        # Cross-contamination check
        assert "Question for Riley." not in casey_contents
        assert "Question for Casey." not in riley_contents
