"""Compliance Academy orchestrator (CLI game loop).

Minimal Game Master that loads a scenario, routes player commands to the
right agent (suspect, forensic analyst, scenario generator, compliance
officer), and maintains per-agent conversation history in memory.

This is the MVP demo-driver. It is not a full Game Master implementation:
no dice rolls, no multi-act state machine, no trust mutation, no party
roster beyond the Forensic Analyst. What it does cover is the complete
demo path:

    1. Open with the loaded scenario's premise (Act 1 narration)
    2. Player interrogates suspects in any order
    3. Player consults the Forensic Analyst for evidence analysis
    4. Player can have the Scenario Generator build a new case from a
       host-supplied breach (the live wow moment)
    5. Player accuses a suspect, the Compliance Officer closes out
       with the framework lesson (Act 4)

Usage:
    python -m src.orchestrator
    python -m src.orchestrator --scenario helix_dynamics_supplychain

Type ``help`` inside the REPL for the full command list.

Design notes:
    Conversation history is per-agent and persists for the life of one
    REPL session against one scenario. When a new scenario is hot-loaded
    via ``generate``, all histories reset because the suspects are now
    playing different roles. A long-lived Azure client lives in this
    process so credential discovery (the multi-second DefaultAzureCredential
    walk) happens once per session, not once per tool call.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Any

from src.scenario_loader import (
    ScenarioLoadError,
    ScenarioValidationError,
    load_scenario_by_name,
    load_scenario_from_dict,
)
from src.agents.scenario_generator import (
    ScenarioGenerationError,
    ScenarioGenerationParseError,
    generate_scenario,
)
from src.agents.suspect_agent import SuspectAgentError, interrogate_suspect
from src.agents.forensic_analyst import (
    ForensicAnalystError,
    consult_forensic_analyst,
)
from src.agents.compliance_officer import (
    ComplianceOfficerError,
    deliver_closer,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SCENARIO_NAME: str = "helix_dynamics_default"

#: Speaker labels printed before each agent's output. Kept short for
#: quick visual scanning during interrogation.
LABEL_GAME_MASTER: str = "[Game Master]"
LABEL_FORENSIC: str = "[Forensic Analyst]"
LABEL_COMPLIANCE: str = "[Compliance Officer]"
LABEL_GENERATOR: str = "[Scenario Generator]"
LABEL_ERROR: str = "[!]"
LABEL_INFO: str = "[i]"

#: Prompt shown in the REPL.
REPL_PROMPT: str = "\n> "

#: Help text shown for the `help` command.
HELP_TEXT: str = textwrap.dedent("""
    Commands:

      help                      Show this help
      scenario                  Show the current scenario summary
      look                      Re-narrate the case premise
      suspects                  List the five canonical suspects
      evidence                  List the evidence seeds available in this scenario

      ask <suspect_id> <msg>    Interrogate a suspect. Example:
                                  ask casey_doyle Where were you Sunday night?
      forensic <message>        Consult the Forensic Analyst. Example:
                                  forensic Walk me through the access logs

      accuse <suspect_id>       Accuse a suspect; triggers Compliance Officer closing
      wrap                      End scene without accusation; CO closes with the lesson

      generate <breach desc>    Have the Scenario Generator build a new case live,
                                then hot-load it (clears all conversation history).
                                Example: generate A vendor's compromised credentials
                                were used to access patient records on a Sunday night.

      reset                     Reload the current scenario fresh (clears history)
      quit                      Exit
""").strip()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """In-memory game loop for one player session.

    Maintains the current scenario plus per-agent conversation history.
    Routes player commands to the appropriate agent wrapper module.
    """

    def __init__(self, scenario: dict[str, Any], scenario_label: str) -> None:
        self.scenario: dict[str, Any] = scenario
        self.scenario_label: str = scenario_label
        # Per-agent conversation history. Keys: suspect_id strings,
        # plus the special key "forensic" for the Forensic Analyst.
        self.histories: dict[str, list[dict[str, str]]] = {}
        # Track total elapsed time across tool calls in this session.
        self.total_agent_seconds: float = 0.0
        # Track whether we've already delivered the closer (for end-of-session).
        self.closed: bool = False

    # ---- Command handlers ------------------------------------------------

    def cmd_help(self, _rest: str) -> None:
        print(HELP_TEXT)

    def cmd_scenario(self, _rest: str) -> None:
        s = self.scenario
        print(f"\n{LABEL_INFO} Scenario: {s.get('scenario_name', '?')} "
              f"({s.get('scenario_id', '?')})")
        print(f"      pattern={s.get('attack_pattern_category', '?')}")
        print(f"      systems={len(s.get('involved_systems', []))} "
              f"controls={len(s.get('violated_controls', []))} "
              f"evidence={len(s.get('evidence_seeds', []))}")
        perp = next(
            (sus["name"] for sus in s.get("suspects", []) if sus.get("is_perpetrator")),
            "?",
        )
        herrings = [
            sus["name"] for sus in s.get("suspects", []) if sus.get("is_red_herring")
        ]
        print(f"      perpetrator={perp}  red_herrings={herrings}")
        print(f"      (loaded from: {self.scenario_label})")
        print(f"      session agent time: {self.total_agent_seconds:.1f}s")

    def cmd_look(self, _rest: str) -> None:
        print(f"\n{LABEL_GAME_MASTER}")
        print(self.scenario.get("premise_narration", "(no premise)"))

    def cmd_suspects(self, _rest: str) -> None:
        print(f"\n{LABEL_INFO} Suspects in this scenario:")
        for s in self.scenario.get("suspects", []):
            sid = s.get("suspect_id", "?")
            name = s.get("name", "?")
            role = s.get("role", "?")
            print(f"  {sid:<14}  {name} ({role})")

    def cmd_evidence(self, _rest: str) -> None:
        evidence = self.scenario.get("evidence_seeds", [])
        if not evidence:
            print(f"\n{LABEL_INFO} No evidence seeds in this scenario.")
            return
        print(f"\n{LABEL_INFO} Evidence seeds available ({len(evidence)} items):")
        for e in evidence:
            eid = e.get("evidence_id", "?")
            source = e.get("source", "?")
            content = e.get("content", "")
            print(f"  [{eid}] {source}")
            print(f"        {content}")

    def cmd_ask(self, rest: str) -> None:
        if not rest.strip():
            print(f"{LABEL_ERROR} Usage: ask <suspect_id> <your question>")
            return
        parts = rest.split(maxsplit=1)
        if len(parts) < 2:
            print(f"{LABEL_ERROR} You need to ask a question. "
                  f"Example: ask {parts[0]} Where were you Sunday night?")
            return
        suspect_id, player_message = parts[0], parts[1]

        suspect = next(
            (s for s in self.scenario.get("suspects", [])
             if s.get("suspect_id") == suspect_id),
            None,
        )
        if suspect is None:
            print(f"{LABEL_ERROR} Unknown suspect '{suspect_id}'. "
                  f"Try `suspects` to list available IDs.")
            return

        history = self.histories.setdefault(suspect_id, [])
        print(f"\n[{suspect['name']}]")
        try:
            result = interrogate_suspect(
                self.scenario,
                suspect_id,
                player_message,
                conversation_history=history,
                stream_to_stdout=True,
            )
        except SuspectAgentError as exc:
            print(f"{LABEL_ERROR} Suspect agent failed: {exc}")
            return

        # Persist the turn into history for next ask of this suspect.
        history.append({"role": "user", "content": player_message})
        history.append({"role": "assistant", "content": result["reply"]})
        self.total_agent_seconds += result["elapsed_seconds"]
        attempt_note = f", {result['attempts']} attempts" if result["attempts"] > 1 else ""
        print(f"{LABEL_INFO} {result['elapsed_seconds']:.1f}s{attempt_note}")

    def cmd_forensic(self, rest: str) -> None:
        if not rest.strip():
            print(f"{LABEL_ERROR} Usage: forensic <your question>")
            return

        history = self.histories.setdefault("forensic", [])
        print(f"\n{LABEL_FORENSIC}")
        try:
            result = consult_forensic_analyst(
                self.scenario,
                rest.strip(),
                conversation_history=history,
                stream_to_stdout=True,
            )
        except ForensicAnalystError as exc:
            print(f"{LABEL_ERROR} Forensic Analyst failed: {exc}")
            return

        # We only persist the BARE question and reply in history, not the
        # full case briefing wrapper, so future turns don't duplicate the
        # scenario context. The wrapper builds the briefing fresh each call.
        history.append({"role": "user", "content": rest.strip()})
        history.append({"role": "assistant", "content": result["reply"]})
        self.total_agent_seconds += result["elapsed_seconds"]
        attempt_note = f", {result['attempts']} attempts" if result["attempts"] > 1 else ""
        retrieval_note = (
            f", {result['retrieval_count']} sources"
            if result.get("retrieval_count", 0) > 0
            else ""
        )
        print(f"{LABEL_INFO} {result['elapsed_seconds']:.1f}s{attempt_note}"
              f"{retrieval_note}")

    def cmd_accuse(self, rest: str) -> None:
        suspect_id = rest.strip()
        if not suspect_id:
            print(f"{LABEL_ERROR} Usage: accuse <suspect_id>")
            return
        suspect = next(
            (s for s in self.scenario.get("suspects", [])
             if s.get("suspect_id") == suspect_id),
            None,
        )
        if suspect is None:
            print(f"{LABEL_ERROR} Unknown suspect '{suspect_id}'.")
            return

        perpetrator = next(
            (s for s in self.scenario.get("suspects", []) if s.get("is_perpetrator")),
            None,
        )
        perp_id = perpetrator.get("suspect_id") if perpetrator else None
        outcome = "correct" if suspect_id == perp_id else "wrong_perpetrator"

        if outcome == "correct":
            print(f"\n{LABEL_INFO} You accused {suspect['name']}. "
                  f"That is the correct perpetrator.")
        else:
            perp_name = perpetrator.get("name", "?") if perpetrator else "?"
            print(f"\n{LABEL_INFO} You accused {suspect['name']}. "
                  f"The actual perpetrator was {perp_name}.")

        print(f"\n{LABEL_COMPLIANCE}")
        try:
            result = deliver_closer(
                self.scenario,
                accused_suspect_id=suspect_id,
                outcome=outcome,  # type: ignore[arg-type]
                stream_to_stdout=True,
            )
        except ComplianceOfficerError as exc:
            print(f"{LABEL_ERROR} Compliance Officer failed: {exc}")
            return

        self.total_agent_seconds += result["elapsed_seconds"]
        self.closed = True
        attempt_note = f", {result['attempts']} attempts" if result["attempts"] > 1 else ""
        retrieval_note = (
            f", {result['retrieval_count']} sources"
            if result.get("retrieval_count", 0) > 0
            else ""
        )
        print(f"{LABEL_INFO} {result['elapsed_seconds']:.1f}s{attempt_note}"
              f"{retrieval_note}  "
              f"(~{len(result['speech'].split())} words)")
        print(f"{LABEL_INFO} Scene closed. Use `reset` to replay or `quit` to exit.")

    def cmd_wrap(self, _rest: str) -> None:
        print(f"\n{LABEL_COMPLIANCE}")
        try:
            result = deliver_closer(
                self.scenario,
                accused_suspect_id=None,
                outcome="no_accusation",
                stream_to_stdout=True,
            )
        except ComplianceOfficerError as exc:
            print(f"{LABEL_ERROR} Compliance Officer failed: {exc}")
            return

        self.total_agent_seconds += result["elapsed_seconds"]
        self.closed = True
        attempt_note = f", {result['attempts']} attempts" if result["attempts"] > 1 else ""
        retrieval_note = (
            f", {result['retrieval_count']} sources"
            if result.get("retrieval_count", 0) > 0
            else ""
        )
        print(f"{LABEL_INFO} {result['elapsed_seconds']:.1f}s{attempt_note}"
              f"{retrieval_note}  "
              f"(~{len(result['speech'].split())} words)")
        print(f"{LABEL_INFO} Scene closed. Use `reset` to replay or `quit` to exit.")

    def cmd_generate(self, rest: str) -> None:
        breach = rest.strip()
        if not breach:
            print(f"{LABEL_ERROR} Usage: generate <breach description>")
            print("    Example: generate A vendor's compromised credentials were "
                  "used to access patient records on a Sunday night.")
            return

        print(f"\n{LABEL_GENERATOR} Generating a new scenario from your breach description...")
        print(f"(Streaming below. First tokens in ~5 seconds, full generation ~40-70s.)")
        print("-" * 72)
        try:
            result = generate_scenario(breach, stream_to_stdout=True)
        except ScenarioGenerationParseError as exc:
            print(f"\n{LABEL_ERROR} Scenario JSON could not be parsed: {exc}")
            return
        except ScenarioValidationError as exc:
            print(f"\n{LABEL_ERROR} Generated scenario failed validation: {exc}")
            return
        except ScenarioGenerationError as exc:
            print(f"\n{LABEL_ERROR} Scenario generation failed: {exc}")
            return

        print("-" * 72)
        # Hot-load: replace state with the new scenario, clear all histories
        # (the suspects are now playing different roles, prior turns are stale).
        self.scenario = result["merged_scenario"]
        self.scenario_label = f"generated:{self.scenario.get('scenario_id', '?')}"
        self.histories.clear()
        self.closed = False
        attempt_note = (
            f", {result['attempts']} attempts" if result["attempts"] > 1 else ""
        )
        print(f"\n{LABEL_INFO} Scenario hot-loaded in {result['elapsed_seconds']:.1f}s"
              f"{attempt_note}")
        self.cmd_scenario("")
        print(f"\n{LABEL_INFO} All prior conversation history cleared. "
              f"Use `look` to hear the new premise.")

    def cmd_reset(self, _rest: str) -> None:
        """Reload the current scenario fresh from disk if it was disk-loaded."""
        if self.scenario_label.startswith("generated:"):
            print(f"{LABEL_INFO} Current scenario is a generated one; reset clears "
                  f"history but keeps the generated scenario.")
            self.histories.clear()
            self.closed = False
            print(f"{LABEL_INFO} History cleared.")
            return
        try:
            self.scenario = load_scenario_by_name(self.scenario_label)
        except (ScenarioLoadError, ScenarioValidationError) as exc:
            print(f"{LABEL_ERROR} Could not reload '{self.scenario_label}': {exc}")
            return
        self.histories.clear()
        self.closed = False
        print(f"{LABEL_INFO} Scenario '{self.scenario_label}' reloaded. History cleared.")

    # ---- REPL loop -------------------------------------------------------

    COMMANDS = {
        "help": "cmd_help",
        "?": "cmd_help",
        "scenario": "cmd_scenario",
        "look": "cmd_look",
        "start": "cmd_look",
        "suspects": "cmd_suspects",
        "evidence": "cmd_evidence",
        "ask": "cmd_ask",
        "forensic": "cmd_forensic",
        "accuse": "cmd_accuse",
        "wrap": "cmd_wrap",
        "generate": "cmd_generate",
        "reset": "cmd_reset",
    }

    def run(self) -> int:
        print("=" * 72)
        print("Compliance Academy")
        print("=" * 72)
        self.cmd_scenario("")
        print(f"\n{LABEL_INFO} Type `help` for commands. `look` to hear the case premise.")

        while True:
            try:
                line = input(REPL_PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                return 0

            if not line:
                continue
            if line in ("quit", "exit", "q"):
                print("Goodbye.")
                return 0

            parts = line.split(maxsplit=1)
            verb = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""

            handler_name = self.COMMANDS.get(verb)
            if handler_name is None:
                print(f"{LABEL_ERROR} Unknown command '{verb}'. Type `help`.")
                continue
            handler = getattr(self, handler_name)
            try:
                handler(rest)
            except KeyboardInterrupt:
                print(f"\n{LABEL_INFO} Interrupted. Returning to prompt.")
                continue


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.orchestrator",
        description="Compliance Academy CLI orchestrator. "
                    "Loads a scenario and runs a REPL for player commands.",
    )
    parser.add_argument(
        "--scenario",
        default=DEFAULT_SCENARIO_NAME,
        help=f"Scenario filename without .json (default: {DEFAULT_SCENARIO_NAME})",
    )
    args = parser.parse_args(argv)

    try:
        scenario = load_scenario_by_name(args.scenario)
    except (ScenarioLoadError, ScenarioValidationError) as exc:
        print(f"{LABEL_ERROR} Could not load scenario '{args.scenario}': {exc}",
              file=sys.stderr)
        return 1

    orch = Orchestrator(scenario, args.scenario)
    return orch.run()


if __name__ == "__main__":
    sys.exit(main())
