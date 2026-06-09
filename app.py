"""Compliance Academy — Chainlit UI (Stage 3: full chat shell).

This is the audience-facing surface for the Microsoft Reactor live demo.
It runs alongside a separate terminal tailing logs/activity.log; that
terminal is where the audience sees the actual orchestration evidence
(Foundry IQ retrievals, Azure OpenAI POSTs, first-token timing, etc).

Stage 3 scope (this version):
    - Scenario picker on launch (Default / Supply Chain / Vishing)
    - Briefing + action button row (Briefing, Suspects, Evidence,
      Generate, Accuse, Wrap)
    - Message routing: free-text questions go to the Forensic Analyst
      by default, or to the active suspect after the player picks one
      from the Suspects roster
    - Real Foundry IQ source attachments via cl.Text elements (the
      retrievals list now flows through from the agent wrappers)
    - Multi-turn conversation history per agent (forensic + each suspect)
    - Live scenario generation via the Scenario Generator agent
    - Scene-close via the Compliance Officer (accuse or wrap)

Architecture:
    The CLI orchestrator (src/orchestrator.py) and this Chainlit app are
    two surfaces over the same agent functions in src/agents/. Both surfaces
    write to the same activity log, so the terminal tail is the single
    source of orchestration truth no matter which surface drove the call.

Avatar convention:
    Avatars live at public/avatars/<key>.png. The ``author`` string on
    cl.Message must match a filename stem. We use snake_case lowercase
    (game_master, forensic_analyst, casey_doyle, etc.) because Chainlit's
    avatar lookup is finicky with spaces in URLs.

Companion tooling:
    Open a second PowerShell window before launching:
        .\\scripts\\tail_activity.ps1 -Clear
    Then run:
        chainlit run app.py

    The ``-w`` (watch mode) flag is useful during development but adds
    file-watcher noise during a live demo every time the agents write
    to activity.log. Drop it for streams; keep it while iterating on
    Python code.
"""

from __future__ import annotations

# Corporate TLS interception fix: use the Windows certificate store (which has
# the Netskope corporate root CA installed by IT) instead of the certifi bundle
# that ships with Python packages. MUST run before any openai/azure-* imports
# below or those clients are created with the wrong SSL context, and every
# outbound HTTPS request fails with "self-signed certificate in certificate
# chain" on this loaner laptop.
import truststore
truststore.inject_into_ssl()

from typing import Any

import chainlit as cl

from src.scenario_loader import load_scenario_by_name
from src.agents.forensic_analyst import (
    ForensicAnalystError,
    consult_forensic_analyst,
)
from src.agents.suspect_agent import (
    SuspectAgentError,
    interrogate_suspect,
)
from src.agents.compliance_officer import (
    ComplianceOfficerError,
    deliver_closer,
)
from src.agents.scenario_generator import (
    ScenarioGenerationError,
    ScenarioGenerationParseError,
    generate_scenario,
)
from src.scenario_loader import ScenarioValidationError
from src.activity_log import emit as _emit, log_line as _log_line


# ---------------------------------------------------------------------------
# Avatar keys (must match public/avatars/<key>.png exactly)
# ---------------------------------------------------------------------------

AVATAR_GM = "game_master"
AVATAR_FA = "forensic_analyst"
AVATAR_CO = "compliance_officer"
AVATAR_SG = "scenario_generator"

# Map canonical suspect_id (used internally + in scenario JSON) to avatar
# key. They happen to be identical, but keeping the map explicit makes
# the intent clear and gives us a single place to change later.
SUSPECT_AVATARS: dict[str, str] = {
    "alex_chen": "alex_chen",
    "casey_doyle": "casey_doyle",
    "jordan_smith": "jordan_smith",
    "morgan_webb": "morgan_webb",
    "riley_park": "riley_park",
}


# ---------------------------------------------------------------------------
# Scenario picker — short label → load_scenario_by_name argument
# ---------------------------------------------------------------------------

SCENARIO_NAMES: dict[str, str] = {
    "default": "helix_dynamics_default",
    "supplychain": "helix_dynamics_supplychain",
    "vishing": "helix_dynamics_vishing",
}

SCENARIO_BLURBS: dict[str, str] = {
    "default": "Healthcare breach: 14 GB clinical trial data exfiltrated overnight.",
    "supplychain": "Vendor compromise: trusted upstream supplier shipped a tampered build.",
    "vishing": "Social engineering: a vishing call against a privileged help-desk account.",
}


# ---------------------------------------------------------------------------
# Session state helpers (thin wrappers over cl.user_session for clarity)
# ---------------------------------------------------------------------------


def _get_scenario() -> dict[str, Any] | None:
    return cl.user_session.get("scenario")


def _set_scenario(scenario: dict[str, Any]) -> None:
    cl.user_session.set("scenario", scenario)


def _get_active_suspect() -> str | None:
    return cl.user_session.get("active_suspect")


def _set_active_suspect(suspect_id: str | None) -> None:
    cl.user_session.set("active_suspect", suspect_id)


def _get_history(key: str) -> list[dict[str, str]]:
    """Get the conversation history for a given key (forensic or suspect_id)."""
    histories = cl.user_session.get("histories") or {}
    return histories.get(key, [])


def _append_history(key: str, user_msg: str, assistant_msg: str) -> None:
    histories = cl.user_session.get("histories") or {}
    h = histories.get(key, [])
    h.append({"role": "user", "content": user_msg})
    h.append({"role": "assistant", "content": assistant_msg})
    histories[key] = h
    cl.user_session.set("histories", histories)


def _reset_session(scenario: dict[str, Any]) -> None:
    """Initialize all session state for a freshly-loaded scenario."""
    _set_scenario(scenario)
    _set_active_suspect(None)
    cl.user_session.set("histories", {})
    cl.user_session.set("scene_closed", False)
    cl.user_session.set("awaiting_breach", False)


def _is_scene_closed() -> bool:
    return bool(cl.user_session.get("scene_closed"))


def _close_scene() -> None:
    cl.user_session.set("scene_closed", True)


# ---------------------------------------------------------------------------
# Element builders (build cl.Text source attachments from agent retrievals)
# ---------------------------------------------------------------------------


def _filename_from_url(url: str) -> str:
    """Extract a readable filename from a blob URL for source labels."""
    if not url:
        return "(unknown source)"
    name = url.rsplit("/", 1)[-1]
    if "?" in name:
        name = name.split("?", 1)[0]
    return name


def _build_source_elements(retrievals: list[dict[str, Any]]) -> list[cl.Text]:
    """Convert raw retrieval dicts into clickable cl.Text side-panel elements.

    Each retrieval becomes one collapsible source attachment with the
    filename as the label and the snippet text as the content. Display
    mode 'side' opens a side drawer when the user clicks; we use 'inline'
    for source 1 so at least one is visible without a click, and 'side'
    for the rest to keep the chat compact.
    """
    elements: list[cl.Text] = []
    for i, r in enumerate(retrievals, start=1):
        filename = _filename_from_url(r.get("source_url", ""))
        score = r.get("score", 0.0)
        snippet = (r.get("snippet", "") or "").strip()
        if not snippet:
            continue
        # Label includes the rank, filename, and relevance score so audience
        # can see the retrieval quality at a glance.
        name = f"[{i}] {filename}  (score {score:.2f})"
        elements.append(
            cl.Text(
                name=name,
                content=snippet,
                display="side",
            )
        )
    return elements


# ---------------------------------------------------------------------------
# Briefing + action button row
# ---------------------------------------------------------------------------


def _make_action_row() -> list[cl.Action]:
    """The persistent action row attached to most Game Master messages."""
    return [
        cl.Action(name="briefing", payload={}, label="📖 Briefing"),
        cl.Action(name="suspects", payload={}, label="👥 Suspects"),
        cl.Action(name="evidence", payload={}, label="🔍 Evidence"),
        cl.Action(name="generate", payload={}, label="🆕 Generate"),
        cl.Action(name="accuse", payload={}, label="⚖️ Accuse"),
        cl.Action(name="wrap", payload={}, label="🚪 Wrap"),
    ]


def _format_briefing(scenario: dict[str, Any], opening: bool = False) -> str:
    """Format a case briefing message for the player.

    The opening briefing includes the full premise; subsequent briefings
    (when the player clicks 📖 Briefing) repeat the same content so the
    player can re-read at any time.
    """
    name = scenario.get("scenario_name", "Untitled Scenario")
    sid = scenario.get("scenario_id", "?")
    premise = scenario.get("premise_narration", "")
    suspect_count = len(scenario.get("suspects", []))
    ev_count = len(scenario.get("evidence_seeds", []))
    ctrl_count = len(scenario.get("violated_controls", []))

    header = f"**{name}** _(case {sid})_\n\n"
    body = f"{premise}\n\n"
    stats = (
        f"_Roster: {suspect_count} suspects · "
        f"{ev_count} pieces of evidence on the table · "
        f"{ctrl_count} controls implicated._\n"
    )
    prompt = (
        "\nAsk the Forensic Analyst anything to start investigating, "
        "or use 👥 **Suspects** to interrogate someone directly."
        if opening else ""
    )
    return header + body + stats + prompt


async def _send_briefing(scenario: dict[str, Any], opening: bool = False) -> None:
    await cl.Message(
        content=_format_briefing(scenario, opening=opening),
        author=AVATAR_GM,
        actions=_make_action_row(),
    ).send()


# ---------------------------------------------------------------------------
# Entry: scenario picker and welcome
# ---------------------------------------------------------------------------


@cl.on_chat_start
async def on_chat_start() -> None:
    """Show the scenario picker, then load and brief the chosen scenario."""
    _log_line("")
    _emit("Chainlit", "New chat session started")

    picker = await cl.AskActionMessage(
        content=(
            "**Welcome to Compliance Academy.**\n\n"
            "You're the lead investigator. Pick a scenario to begin:\n\n"
            f"- 🏥 **Default** — {SCENARIO_BLURBS['default']}\n"
            f"- 🔌 **Supply Chain** — {SCENARIO_BLURBS['supplychain']}\n"
            f"- 📞 **Vishing** — {SCENARIO_BLURBS['vishing']}\n\n"
            "_You can also generate an entirely new scenario from a breach "
            "description after the case opens via 🆕 Generate._"
        ),
        actions=[
            cl.Action(
                name="pick_scenario",
                payload={"value": "default"},
                label="🏥 Default (Healthcare)",
            ),
            cl.Action(
                name="pick_scenario",
                payload={"value": "supplychain"},
                label="🔌 Supply Chain",
            ),
            cl.Action(
                name="pick_scenario",
                payload={"value": "vishing"},
                label="📞 Vishing",
            ),
        ],
        author=AVATAR_GM,
        timeout=600,
    ).send()

    if picker is None:
        _emit("Chainlit", "Scenario picker timed out or was dismissed")
        await cl.Message(
            content="No scenario selected. Reload the page to try again.",
            author=AVATAR_GM,
        ).send()
        return

    choice = (picker.get("payload") or {}).get("value", "default")
    scenario_name = SCENARIO_NAMES.get(choice, SCENARIO_NAMES["default"])

    try:
        scenario = load_scenario_by_name(scenario_name)
    except Exception as exc:
        _emit("Error", f"Failed to load scenario '{scenario_name}': {exc}")
        await cl.Message(
            content=f"Failed to load scenario: {exc}",
            author=AVATAR_GM,
        ).send()
        return

    _reset_session(scenario)
    _emit(
        "Chainlit",
        f"Loaded scenario: {scenario['scenario_name']!r}",
        id=scenario.get("scenario_id", "?"),
    )

    await _send_briefing(scenario, opening=True)


# ---------------------------------------------------------------------------
# Action callbacks — Game Master command surface
# ---------------------------------------------------------------------------


@cl.action_callback("briefing")
async def on_briefing(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    _emit("Chainlit", "User clicked: Briefing")
    await _send_briefing(scenario, opening=False)


@cl.action_callback("suspects")
async def on_suspects(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    _emit("Chainlit", "User clicked: Suspects")

    suspects = scenario.get("suspects", [])
    if not suspects:
        await cl.Message(
            content="No suspects in this scenario.",
            author=AVATAR_GM,
        ).send()
        return

    pick_actions = [
        cl.Action(
            name="pick_suspect",
            payload={"suspect_id": s["suspect_id"]},
            label=f"👤 {s['name']}",
        )
        for s in suspects
    ]

    # Render a short roster recap above the buttons so the player can read
    # role context before picking who to interrogate.
    lines = ["**Suspect roster:** pick one to start an interrogation thread.\n"]
    for s in suspects:
        lines.append(f"- **{s['name']}** — {s['role']}")
    lines.append(
        "\n_You can switch suspects at any time via 👥 Suspects. "
        "Each suspect remembers their own conversation history with you._"
    )

    # Picker actions PLUS the persistent action row so the player can
    # always escape to Briefing/Evidence/Accuse/Wrap without restarting.
    await cl.Message(
        content="\n".join(lines),
        author=AVATAR_GM,
        actions=pick_actions + _make_action_row(),
    ).send()


@cl.action_callback("pick_suspect")
async def on_pick_suspect(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    suspect_id = (action.payload or {}).get("suspect_id")
    if not suspect_id:
        return

    suspect = next(
        (s for s in scenario["suspects"] if s["suspect_id"] == suspect_id),
        None,
    )
    if not suspect:
        return

    _set_active_suspect(suspect_id)
    _emit(
        "Chainlit",
        f"Activated suspect: {suspect['name']}",
        suspect_id=suspect_id,
    )

    avatar = SUSPECT_AVATARS.get(suspect_id, AVATAR_GM)
    await cl.Message(
        content=(
            f"You're now interrogating **{suspect['name']}** "
            f"({suspect['role']}). Type your questions in the message box."
            f"\n\n_Use 👥 Suspects to switch, or any other button to step "
            f"out of the interview at any time._"
        ),
        author=avatar,
        actions=_make_action_row(),
    ).send()


def _make_evidence_picker_actions(
    evidence_seeds: list[dict[str, Any]],
    current_evidence_id: str | None = None,
) -> list[cl.Action]:
    """Build the EV-NNN picker action buttons for an evidence list.

    Attached to both the initial Evidence roster message and to every
    individual evidence detail message, so the presenter always has the
    full set of picker buttons at the bottom of whatever they're reading.
    No need to scroll back up to the roster after clicking through
    several items.

    If ``current_evidence_id`` is supplied, that item's button gets a
    visual marker so the presenter can see at a glance which item is
    currently displayed.
    """
    actions: list[cl.Action] = []
    for ev in evidence_seeds:
        eid = ev.get("evidence_id")
        if not eid:
            continue
        # Mark the currently-displayed item so the presenter doesn't
        # accidentally click the same evidence twice.
        marker = "• " if eid == current_evidence_id else "📄 "
        actions.append(
            cl.Action(
                name="show_evidence",
                payload={"evidence_id": eid},
                label=f"{marker}{eid}",
            )
        )
    return actions


@cl.action_callback("evidence")
async def on_evidence(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    _emit("Chainlit", "User clicked: Evidence")

    evidence = scenario.get("evidence_seeds", [])
    if not evidence:
        await cl.Message(content="No evidence yet.", author=AVATAR_GM).send()
        return

    # Roster: one line per evidence item in the main message for context,
    # plus a dedicated action button per item so the presenter has an
    # explicit, discoverable click target for each piece during the demo.
    lines = [
        "**Evidence on the table.** "
        "Click any **EV-NNN** button below to read the full detail.\n"
    ]
    for ev in evidence:
        eid = ev.get("evidence_id", "?")
        source = ev.get("source", "?")
        value = ev.get("value", "?")
        lines.append(f"- **{eid}** _(value {value}/10)_ — {source}")

    # Picker actions PLUS the persistent action row so the player can
    # escape to Suspects / Accuse / Wrap at any time.
    pick_actions = _make_evidence_picker_actions(evidence)

    await cl.Message(
        content="\n".join(lines),
        author=AVATAR_GM,
        actions=pick_actions + _make_action_row(),
    ).send()


@cl.action_callback("show_evidence")
async def on_show_evidence(action: cl.Action) -> None:
    """Render the full content of a single evidence item.

    Triggered by the per-evidence picker buttons on the Evidence roster
    message OR by the same picker re-attached to any evidence detail
    message. Posts a new GM message with the item's full content AND a
    fresh picker so the presenter can keep navigating without scrolling
    back up to the original roster.
    """
    scenario = _get_scenario()
    if not scenario:
        return
    evidence_id = (action.payload or {}).get("evidence_id")
    if not evidence_id:
        return

    evidence = scenario.get("evidence_seeds", [])
    ev = next(
        (e for e in evidence if e.get("evidence_id") == evidence_id),
        None,
    )
    if not ev:
        await cl.Message(
            content=f"Evidence item {evidence_id} not found in this scenario.",
            author=AVATAR_GM,
        ).send()
        return

    _emit("Chainlit", f"User opened evidence detail: {evidence_id}")

    eid = ev.get("evidence_id", "?")
    source = ev.get("source", "?")
    content = (ev.get("content", "") or "").strip() or "_(no content)_"
    value = ev.get("value", "?")

    # Re-attach the evidence picker (with current item marked) plus the
    # persistent action row, so the presenter can jump to any other item
    # directly from this detail message instead of having to scroll up
    # or re-click 🔍 Evidence.
    pick_actions = _make_evidence_picker_actions(
        evidence, current_evidence_id=eid
    )

    await cl.Message(
        content=(
            f"**{eid}** _(value {value}/10)_ — {source}\n\n"
            f"{content}"
        ),
        author=AVATAR_GM,
        actions=pick_actions + _make_action_row(),
    ).send()


@cl.action_callback("generate")
async def on_generate(action: cl.Action) -> None:
    """Prompt the user for a breach description.

    Instead of using cl.AskUserMessage (which has race conditions with
    the on_message handler), we set a session flag and let the next
    free-text message be routed to the scenario generator by on_message.
    """
    _emit("Chainlit", "User clicked: Generate (awaiting breach description)")
    cl.user_session.set("awaiting_breach", True)

    await cl.Message(
        content=(
            "**Describe a breach scenario.** A few sentences is plenty. "
            "The Scenario Generator will produce a complete case in "
            "30 to 60 seconds.\n\n"
            "_Example: \"An employee's session token gets stolen at an "
            "industry conference and used to exfiltrate regulatory "
            "documents.\"_\n\n"
            "_Type your breach description in the message box below and "
            "hit Enter. Click 🚫 Cancel to abort._"
        ),
        author=AVATAR_GM,
        actions=[
            cl.Action(
                name="cancel_generate",
                payload={},
                label="🚫 Cancel",
            ),
        ] + _make_action_row(),
    ).send()


@cl.action_callback("cancel_generate")
async def on_cancel_generate(action: cl.Action) -> None:
    """Clear the awaiting_breach flag so the next message routes normally."""
    if cl.user_session.get("awaiting_breach"):
        cl.user_session.set("awaiting_breach", False)
        _emit("Chainlit", "User cancelled scenario generation")
        await cl.Message(
            content="Scenario generation cancelled. Continue investigating.",
            author=AVATAR_GM,
            actions=_make_action_row(),
        ).send()


async def _run_scenario_generation(breach: str) -> None:
    """Call generate_scenario and hot-load the result.

    Sent as its own function so it can be invoked either from a flow
    that captures a breach description via on_message or any future
    direct-invocation path.
    """
    placeholder = cl.Message(
        content="_Generating a fresh scenario from your description (30-60 seconds)..._",
        author=AVATAR_SG,
    )
    await placeholder.send()

    try:
        result = await cl.make_async(generate_scenario)(breach)
    except (ScenarioGenerationError, ScenarioGenerationParseError,
            ScenarioValidationError) as exc:
        placeholder.content = (
            f"**Generation failed:** {exc}\n\n"
            "The current scenario is unchanged. Try again with a different "
            "breach description, or use 📖 Briefing to continue with the "
            "existing case."
        )
        placeholder.actions = _make_action_row()
        await placeholder.update()
        return
    except Exception as exc:
        placeholder.content = f"**Unexpected error:** {exc}"
        placeholder.actions = _make_action_row()
        await placeholder.update()
        return

    new_scenario = result["merged_scenario"]
    _reset_session(new_scenario)

    placeholder.content = (
        f"**New scenario hot-loaded: {new_scenario['scenario_name']}**\n\n"
        f"_Generated in {result['elapsed_seconds']:.1f}s · "
        f"{result['validation_attempts']} validation cycle(s) · "
        f"{result['attempts']} total model call(s)._\n\n"
        f"---\n\n"
        f"{result['reasoning_summary']}"
    )
    await placeholder.update()

    # Now send the actual briefing for the new scenario with the action row.
    await _send_briefing(new_scenario, opening=True)


@cl.action_callback("accuse")
async def on_accuse(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    if _is_scene_closed():
        await cl.Message(
            content="The scene is already closed. Use 🆕 Generate for a new case.",
            author=AVATAR_GM,
        ).send()
        return
    _emit("Chainlit", "User clicked: Accuse")

    suspects = scenario.get("suspects", [])
    pick_actions = [
        cl.Action(
            name="confirm_accuse",
            payload={"suspect_id": s["suspect_id"]},
            label=f"⚖️ {s['name']}",
        )
        for s in suspects
    ]

    # Accusation buttons PLUS persistent action row so player can back out.
    await cl.Message(
        content=(
            "**Make your accusation.** Pick the suspect you believe is the "
            "perpetrator. The Compliance Officer will deliver the verdict "
            "and the framework lesson.\n\n"
            "_This closes the scene. You can still ask the Forensic Analyst "
            "follow-up questions, but the case is locked._"
        ),
        author=AVATAR_GM,
        actions=pick_actions + _make_action_row(),
    ).send()


@cl.action_callback("confirm_accuse")
async def on_confirm_accuse(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    suspect_id = (action.payload or {}).get("suspect_id")
    if not suspect_id:
        return

    # Determine outcome by comparing to the canonical perpetrator.
    perp = next(
        (s for s in scenario["suspects"] if s.get("is_perpetrator")),
        None,
    )
    if perp and perp.get("suspect_id") == suspect_id:
        outcome = "correct"
    else:
        outcome = "wrong_perpetrator"

    _emit(
        "Chainlit",
        f"User accused: {suspect_id} (outcome={outcome})",
    )
    await _run_compliance_officer(scenario, suspect_id, outcome)


@cl.action_callback("wrap")
async def on_wrap(action: cl.Action) -> None:
    scenario = _get_scenario()
    if not scenario:
        return
    if _is_scene_closed():
        await cl.Message(
            content="The scene is already closed.",
            author=AVATAR_GM,
        ).send()
        return
    _emit("Chainlit", "User clicked: Wrap (no accusation)")
    await _run_compliance_officer(scenario, None, "no_accusation")


# ---------------------------------------------------------------------------
# Agent invocations (Forensic Analyst, Suspect Agent, Compliance Officer)
# ---------------------------------------------------------------------------


async def _run_compliance_officer(
    scenario: dict[str, Any],
    accused_suspect_id: str | None,
    outcome: str,
) -> None:
    placeholder = cl.Message(
        content="_The Compliance Officer steps to the podium..._",
        author=AVATAR_CO,
    )
    await placeholder.send()

    try:
        result = await cl.make_async(deliver_closer)(
            scenario, accused_suspect_id, outcome
        )
    except ComplianceOfficerError as exc:
        placeholder.content = f"**Compliance Officer error:** {exc}"
        await placeholder.update()
        return

    placeholder.content = result["speech"]
    elements = _build_source_elements(result.get("retrievals", []))
    if elements:
        placeholder.elements = elements
    await placeholder.update()

    _close_scene()

    # Follow-up note so the player knows what to do next.
    await cl.Message(
        content=(
            "_Scene closed._ The case is now part of your training record. "
            "Use 🆕 Generate to start a new case, or 📖 Briefing to review "
            "this one."
        ),
        author=AVATAR_GM,
        actions=[
            cl.Action(name="briefing", payload={}, label="📖 Briefing"),
            cl.Action(name="generate", payload={}, label="🆕 Generate new"),
        ],
    ).send()


async def _route_to_forensic(
    scenario: dict[str, Any],
    question: str,
) -> None:
    history = _get_history("forensic")

    placeholder = cl.Message(
        content="_Pulling logs and framework references..._",
        author=AVATAR_FA,
    )
    await placeholder.send()

    try:
        result = await cl.make_async(consult_forensic_analyst)(
            scenario, question, conversation_history=history
        )
    except ForensicAnalystError as exc:
        placeholder.content = f"**Forensic Analyst error:** {exc}"
        await placeholder.update()
        return

    placeholder.content = result["reply"]
    elements = _build_source_elements(result.get("retrievals", []))
    if elements:
        placeholder.elements = elements
    placeholder.actions = _make_action_row()
    await placeholder.update()

    _append_history("forensic", question, result["reply"])


async def _route_to_suspect(
    scenario: dict[str, Any],
    suspect_id: str,
    question: str,
) -> None:
    history = _get_history(suspect_id)
    avatar = SUSPECT_AVATARS.get(suspect_id, AVATAR_GM)

    placeholder = cl.Message(content="_(thinking...)_", author=avatar)
    await placeholder.send()

    try:
        result = await cl.make_async(interrogate_suspect)(
            scenario, suspect_id, question, conversation_history=history
        )
    except SuspectAgentError as exc:
        placeholder.content = f"**Suspect agent error:** {exc}"
        await placeholder.update()
        return

    placeholder.content = result["reply"]
    placeholder.actions = _make_action_row()
    await placeholder.update()

    _append_history(suspect_id, question, result["reply"])


# ---------------------------------------------------------------------------
# Message router (free-text input from the player)
# ---------------------------------------------------------------------------


@cl.on_message
async def on_message(message: cl.Message) -> None:
    scenario = _get_scenario()
    if not scenario:
        await cl.Message(
            content="Please select a scenario first (reload the page).",
            author=AVATAR_GM,
        ).send()
        return

    text = (message.content or "").strip()
    if not text:
        return

    # Priority 1: if we're awaiting a breach description for Generate,
    # this message IS the breach description — route to scenario generator
    # instead of FA/suspect.
    if cl.user_session.get("awaiting_breach"):
        cl.user_session.set("awaiting_breach", False)
        _emit(
            "Chainlit",
            f"Captured breach description for Generate: {text[:80]!r}",
        )
        await _run_scenario_generation(text)
        return

    active_suspect = _get_active_suspect()
    target = f"suspect:{active_suspect}" if active_suspect else "forensic_analyst"
    _emit(
        "Chainlit",
        f"User typed (routing to {target}): {text[:80]!r}",
    )

    if active_suspect:
        await _route_to_suspect(scenario, active_suspect, text)
    else:
        await _route_to_forensic(scenario, text)
