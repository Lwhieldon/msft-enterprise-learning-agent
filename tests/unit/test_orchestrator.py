"""Unit tests for ``src.orchestrator``.

The orchestrator is the demo's command router: it parses player input,
dispatches to the right agent wrapper, and maintains in-memory state
(conversation history, current scenario, scene-closed flag). Tests here
mock the agent calls to keep these unit tests fast and offline.

We focus on:
    - State initialization
    - Command dispatch correctness (verb -> handler)
    - Argument parsing (ask, forensic, accuse, generate)
    - State mutations (history persistence, scenario hot-load, scene close)
    - Error handling (unknown suspect, unknown command, malformed input)

We deliberately do NOT unit-test the interactive REPL loop itself
(``Orchestrator.run``), which depends on ``input()`` and is best exercised
by the orchestrator integration tests / live dry runs.
"""

from __future__ import annotations

import pytest

from src.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Initialization and command dispatch wiring
# ---------------------------------------------------------------------------


class TestInitialState:
    """Fresh Orchestrator should have the expected starting state."""

    def test_init_stores_scenario_and_label(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.scenario is default_scenario
        assert orch.scenario_label == "helix_dynamics_default"

    def test_init_starts_with_empty_histories(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.histories == {}

    def test_init_starts_with_zero_agent_time(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.total_agent_seconds == 0.0

    def test_init_starts_with_scene_not_closed(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.closed is False


class TestCommandDispatchTable:
    """The COMMANDS dict maps verbs to handler method names. Pin the
    contract so renaming a handler does not silently break a command."""

    def test_all_documented_commands_present(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        expected_verbs = {
            "help", "?", "scenario", "look", "start", "suspects",
            "evidence", "ask", "forensic", "accuse", "wrap",
            "generate", "reset",
        }
        assert set(orch.COMMANDS.keys()) == expected_verbs

    def test_every_handler_in_table_exists_on_class(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        for verb, handler_name in orch.COMMANDS.items():
            assert hasattr(orch, handler_name), (
                f"Command '{verb}' maps to '{handler_name}' but no such method "
                f"exists on Orchestrator"
            )

    def test_help_and_question_mark_share_handler(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.COMMANDS["help"] == orch.COMMANDS["?"]

    def test_look_and_start_share_handler(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.COMMANDS["look"] == orch.COMMANDS["start"]


# ---------------------------------------------------------------------------
# cmd_scenario, cmd_look, cmd_suspects, cmd_evidence — pure read commands
# ---------------------------------------------------------------------------


class TestReadCommands:
    """Commands that print state but make no agent calls."""

    def test_cmd_scenario_prints_scenario_id_and_name(
        self, default_scenario, capsys
    ):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_scenario("")
        captured = capsys.readouterr()
        assert "SCN-001" in captured.out
        assert "Breach at Helix Dynamics" in captured.out

    def test_cmd_scenario_prints_perpetrator(self, default_scenario, capsys):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_scenario("")
        captured = capsys.readouterr()
        assert "Riley Park" in captured.out  # the perpetrator in SCN-001

    def test_cmd_look_prints_premise_narration(self, default_scenario, capsys):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_look("")
        captured = capsys.readouterr()
        assert default_scenario["premise_narration"] in captured.out

    def test_cmd_suspects_prints_all_five(self, default_scenario, capsys):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_suspects("")
        captured = capsys.readouterr()
        for suspect_id in ("alex_chen", "morgan_webb", "riley_park",
                           "casey_doyle", "jordan_smith"):
            assert suspect_id in captured.out

    def test_cmd_evidence_prints_all_evidence_ids(
        self, default_scenario, capsys
    ):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.cmd_evidence("")
        captured = capsys.readouterr()
        for ev in default_scenario["evidence_seeds"]:
            assert ev["evidence_id"] in captured.out


# ---------------------------------------------------------------------------
# cmd_ask — argument parsing and agent dispatch
# ---------------------------------------------------------------------------


class TestCmdAsk:
    """The ask command parses '<suspect_id> <message>' and routes to the
    suspect agent. Errors on malformed input. Persists conversation history
    per suspect."""

    def test_unknown_suspect_id_prints_error_and_does_not_call_agent(
        self, default_scenario, capsys, mocker
    ):
        mock_interrogate = mocker.patch(
            "src.orchestrator.interrogate_suspect"
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("not_a_real_suspect any question here")

        mock_interrogate.assert_not_called()
        captured = capsys.readouterr()
        assert "Unknown suspect" in captured.out

    def test_missing_message_prints_usage_and_does_not_call_agent(
        self, default_scenario, capsys, mocker
    ):
        mock_interrogate = mocker.patch(
            "src.orchestrator.interrogate_suspect"
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("casey_doyle")  # no message after the suspect_id

        mock_interrogate.assert_not_called()
        captured = capsys.readouterr()
        assert "ask a question" in captured.out.lower() or \
               "usage" in captured.out.lower()

    def test_empty_args_prints_usage(
        self, default_scenario, capsys, mocker
    ):
        mock_interrogate = mocker.patch(
            "src.orchestrator.interrogate_suspect"
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("")

        mock_interrogate.assert_not_called()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower()

    def test_valid_ask_calls_agent_with_parsed_args(
        self, default_scenario, mocker
    ):
        mock_interrogate = mocker.patch(
            "src.orchestrator.interrogate_suspect",
            return_value={
                "reply": "I was at home Sunday night.",
                "suspect_name": "Casey Doyle",
                "suspect_id": "casey_doyle",
                "elapsed_seconds": 5.0,
                "deployment": "gpt-4.1-mini",
                "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("casey_doyle Where were you Sunday night?")

        mock_interrogate.assert_called_once()
        # The agent should receive the parsed suspect_id and player_message
        call_kwargs = mock_interrogate.call_args
        # First positional is the scenario, second is suspect_id, third is message
        assert call_kwargs.args[1] == "casey_doyle"
        assert call_kwargs.args[2] == "Where were you Sunday night?"

    def test_ask_persists_conversation_history(self, default_scenario, mocker):
        """After a successful ask, the conversation_history for that
        suspect should contain the user turn and the assistant turn."""
        mocker.patch(
            "src.orchestrator.interrogate_suspect",
            return_value={
                "reply": "I was at home.",
                "suspect_name": "Casey Doyle",
                "suspect_id": "casey_doyle",
                "elapsed_seconds": 5.0,
                "deployment": "gpt-4.1-mini",
                "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("casey_doyle Question one?")

        history = orch.histories["casey_doyle"]
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Question one?"}
        assert history[1] == {"role": "assistant", "content": "I was at home."}

    def test_ask_persists_history_across_multiple_turns(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.interrogate_suspect",
            side_effect=[
                {"reply": "Reply one.", "suspect_name": "Casey Doyle",
                 "suspect_id": "casey_doyle", "elapsed_seconds": 1.0,
                 "deployment": "gpt-4.1-mini", "attempts": 1},
                {"reply": "Reply two.", "suspect_name": "Casey Doyle",
                 "suspect_id": "casey_doyle", "elapsed_seconds": 1.0,
                 "deployment": "gpt-4.1-mini", "attempts": 1},
            ],
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_ask("casey_doyle First question.")
        orch.cmd_ask("casey_doyle Second question.")

        history = orch.histories["casey_doyle"]
        assert len(history) == 4
        assert history[0]["content"] == "First question."
        assert history[2]["content"] == "Second question."


# ---------------------------------------------------------------------------
# cmd_accuse — outcome classification and CO dispatch
# ---------------------------------------------------------------------------


class TestCmdAccuse:
    """Accusing the perpetrator must classify outcome='correct'; accusing
    anyone else must classify outcome='wrong_perpetrator'. Both close the
    scene and trigger the Compliance Officer."""

    def _stub_co_result(self):
        return {
            "speech": "Closing speech text.",
            "elapsed_seconds": 10.0,
            "deployment": "gpt-4.1-mini",
            "attempts": 1,
            "outcome": "correct",
        }

    def test_accusing_perpetrator_calls_co_with_correct_outcome(
        self, default_scenario, mocker
    ):
        mock_co = mocker.patch(
            "src.orchestrator.deliver_closer",
            return_value=self._stub_co_result(),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_accuse("riley_park")  # the actual perpetrator in SCN-001

        mock_co.assert_called_once()
        assert mock_co.call_args.kwargs["outcome"] == "correct"
        assert mock_co.call_args.kwargs["accused_suspect_id"] == "riley_park"

    def test_accusing_red_herring_classifies_wrong_perpetrator(
        self, default_scenario, mocker
    ):
        mock_co = mocker.patch(
            "src.orchestrator.deliver_closer",
            return_value=self._stub_co_result(),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_accuse("alex_chen")  # the red herring in SCN-001

        assert mock_co.call_args.kwargs["outcome"] == "wrong_perpetrator"

    def test_accusing_tangential_suspect_classifies_wrong_perpetrator(
        self, default_scenario, mocker
    ):
        """Even tangential (non-perp, non-herring) suspects produce
        wrong_perpetrator outcome — they are still not the perpetrator."""
        mock_co = mocker.patch(
            "src.orchestrator.deliver_closer",
            return_value=self._stub_co_result(),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        # Find a tangential suspect (not perp, not herring) in SCN-001
        tangential = next(
            s for s in default_scenario["suspects"]
            if not s["is_perpetrator"] and not s["is_red_herring"]
        )

        orch.cmd_accuse(tangential["suspect_id"])

        assert mock_co.call_args.kwargs["outcome"] == "wrong_perpetrator"

    def test_unknown_suspect_id_prints_error_and_does_not_call_co(
        self, default_scenario, capsys, mocker
    ):
        mock_co = mocker.patch("src.orchestrator.deliver_closer")
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_accuse("nobody")

        mock_co.assert_not_called()
        captured = capsys.readouterr()
        assert "Unknown suspect" in captured.out

    def test_empty_arg_prints_usage_and_does_not_call_co(
        self, default_scenario, capsys, mocker
    ):
        mock_co = mocker.patch("src.orchestrator.deliver_closer")
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_accuse("")

        mock_co.assert_not_called()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower()

    def test_successful_accusation_closes_the_scene(
        self, default_scenario, mocker
    ):
        mocker.patch(
            "src.orchestrator.deliver_closer",
            return_value=self._stub_co_result(),
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        assert orch.closed is False

        orch.cmd_accuse("riley_park")

        assert orch.closed is True


# ---------------------------------------------------------------------------
# cmd_wrap — no-accusation path
# ---------------------------------------------------------------------------


class TestCmdWrap:
    """Wrap ends the scene without naming a perpetrator. CO closes with
    outcome='no_accusation'."""

    def test_wrap_calls_co_with_no_accusation_outcome(
        self, default_scenario, mocker
    ):
        mock_co = mocker.patch(
            "src.orchestrator.deliver_closer",
            return_value={
                "speech": "Closing speech.",
                "elapsed_seconds": 10.0,
                "deployment": "gpt-4.1-mini",
                "attempts": 1,
                "outcome": "no_accusation",
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_wrap("")

        mock_co.assert_called_once()
        assert mock_co.call_args.kwargs["outcome"] == "no_accusation"
        assert mock_co.call_args.kwargs["accused_suspect_id"] is None

    def test_wrap_closes_the_scene(self, default_scenario, mocker):
        mocker.patch(
            "src.orchestrator.deliver_closer",
            return_value={
                "speech": "x", "elapsed_seconds": 1.0,
                "deployment": "gpt-4.1-mini", "attempts": 1,
                "outcome": "no_accusation",
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_wrap("")

        assert orch.closed is True


# ---------------------------------------------------------------------------
# cmd_generate — scenario hot-load
# ---------------------------------------------------------------------------


class TestCmdGenerate:
    """Generate runs the scenario generator, replaces self.scenario with
    the merged result, and clears all conversation histories."""

    def test_empty_breach_prints_usage_and_does_not_call_generator(
        self, default_scenario, capsys, mocker
    ):
        mock_gen = mocker.patch("src.orchestrator.generate_scenario")
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_generate("")

        mock_gen.assert_not_called()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower()

    def test_successful_generate_replaces_scenario(
        self, default_scenario, supplychain_scenario, mocker
    ):
        """After generate, self.scenario should point at the new merged
        scenario, not the original one."""
        mocker.patch(
            "src.orchestrator.generate_scenario",
            return_value={
                "merged_scenario": supplychain_scenario,
                "reasoning_summary": "irrelevant",
                "raw_response": "irrelevant",
                "elapsed_seconds": 30.0,
                "deployment": "gpt-4.1-mini",
                "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_generate("A new breach description.")

        assert orch.scenario is supplychain_scenario
        assert orch.scenario is not default_scenario

    def test_successful_generate_clears_conversation_histories(
        self, default_scenario, supplychain_scenario, mocker
    ):
        """After hot-loading a new scenario, prior suspect conversations
        are stale (suspects may now be in different roles). Histories must
        clear."""
        mocker.patch(
            "src.orchestrator.generate_scenario",
            return_value={
                "merged_scenario": supplychain_scenario,
                "reasoning_summary": "x", "raw_response": "x",
                "elapsed_seconds": 30.0, "deployment": "x", "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        # Pre-populate some histories
        orch.histories["casey_doyle"] = [{"role": "user", "content": "x"}]
        orch.histories["forensic"] = [{"role": "user", "content": "y"}]

        orch.cmd_generate("A new breach description.")

        assert orch.histories == {}

    def test_successful_generate_updates_scenario_label(
        self, default_scenario, supplychain_scenario, mocker
    ):
        """After hot-load, scenario_label should reflect the generated
        scenario, not the originally-loaded one."""
        mocker.patch(
            "src.orchestrator.generate_scenario",
            return_value={
                "merged_scenario": supplychain_scenario,
                "reasoning_summary": "x", "raw_response": "x",
                "elapsed_seconds": 30.0, "deployment": "x", "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")

        orch.cmd_generate("A new breach.")

        assert orch.scenario_label.startswith("generated:")

    def test_successful_generate_reopens_closed_scene(
        self, default_scenario, supplychain_scenario, mocker
    ):
        """If the player closed a scene then generates a new one, the new
        scene should be open (closed=False) so they can keep playing."""
        mocker.patch(
            "src.orchestrator.generate_scenario",
            return_value={
                "merged_scenario": supplychain_scenario,
                "reasoning_summary": "x", "raw_response": "x",
                "elapsed_seconds": 30.0, "deployment": "x", "attempts": 1,
            },
        )
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.closed = True

        orch.cmd_generate("A new breach.")

        assert orch.closed is False


# ---------------------------------------------------------------------------
# cmd_reset
# ---------------------------------------------------------------------------


class TestCmdReset:
    """Reset clears conversation history. For disk-loaded scenarios it also
    reloads from disk; for generated scenarios it keeps the current scenario."""

    def test_reset_clears_histories(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.histories["casey_doyle"] = [{"role": "user", "content": "x"}]

        orch.cmd_reset("")

        assert orch.histories == {}

    def test_reset_reopens_closed_scene(self, default_scenario):
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.closed = True

        orch.cmd_reset("")

        assert orch.closed is False

    def test_reset_on_generated_scenario_keeps_current_scenario(
        self, default_scenario
    ):
        """Generated scenarios cannot be reloaded from disk. Reset should
        clear history but keep the scenario."""
        orch = Orchestrator(default_scenario, "helix_dynamics_default")
        orch.scenario_label = "generated:SCN-999"
        orch.histories["casey_doyle"] = [{"role": "user", "content": "x"}]

        orch.cmd_reset("")

        # History cleared, scenario unchanged
        assert orch.histories == {}
        assert orch.scenario is default_scenario
