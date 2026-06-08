# Stream Day Cheatsheet

**Event:** Microsoft Reactor Reasoning Agents Live Streaming Battle
**Date / Time:** Wednesday, June 10, 2026 · 12:00 PM ET
**Tech check:** 11:45 AM ET (be ready 15 min early)

This is the laser-focused one-page reference for stream day. For the full runbook (architecture talking points, fallback plans, post-stream actions), see [`live_battle_runbook.md`](./live_battle_runbook.md).

---

## T-30 Pre-Flight (5 minutes total)

```powershell
cd C:\Users\lwhieldon\Microsoft\MSFTAgentsLeague\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
az login
az account show     # confirm SC&H Foundry subscription is active
pytest              # unit tests should all pass, runs in seconds
python -m src.scenario_loader   # three OK lines, no Azure call
```

If anything in the block above fails, fix it before going live. Re-running `az login` resolves 95% of issues.

---

## Two Terminals to Open

### Terminal A — Activity log (the audience proof surface)

```powershell
cd C:\Users\lwhieldon\Microsoft\MSFTAgentsLeague\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
.\scripts\tail_activity.ps1 -Clear
```

### Terminal B — Chainlit UI (the player surface)

```powershell
cd C:\Users\lwhieldon\Microsoft\MSFTAgentsLeague\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
chainlit run app.py -w
```

Open browser to `http://localhost:8000`, hard-refresh with Ctrl+Shift+R to bust any CSS cache.

### Terminal C — CLI fallback (open but minimized)

```powershell
cd C:\Users\lwhieldon\Microsoft\MSFTAgentsLeague\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
# Don't run yet. If Chainlit breaks mid-stream:
python -m src.orchestrator
# Type `help` for the command list
```

---

## Screen Layout on Stream

- **Primary share:** the Chainlit browser tab
- **Secondary visible:** Terminal A (activity log scrolling)
- The audience sees both. The UI tells the story; the log proves it's real.

---

## Opening Framing (45 seconds)

> "I'm Lee Whieldon, Principal at SC&H Group. I built Compliance Academy: a multi-agent cyber-mystery game on Microsoft Foundry Agent Service. You play a lead investigator at a fictional biotech that just lost 14 GB of clinical trial data. Five suspects, one perpetrator, and at the end a Compliance Officer agent delivers the actual framework lesson the player just lived through. What you'll see on screen is the Chainlit UI on the left and the live agent orchestration log on the right. The log is how I prove the agents are actually reasoning, retrieving from a policy index, and not just dressing up a single prompt. If anything goes sideways, I've got a CLI orchestrator running in a third terminal that talks to the same agents — that's my engineering backup."

---

## Per-Slot Talking Points

### Slot 1 — Architecture Intro (3-4 min)

- Premise: Helix Dynamics, biotech, lost 14 GB of clinical trial data overnight
- 4 party agents (GM, Forensic Analyst, Compliance Officer, Scenario Generator) + 5 suspects per scenario
- Microsoft Foundry Agent Service + Azure OpenAI gpt-4.1-mini + Azure AI Search agentic retrieval
- 52 chunks indexed: SOC 2, HIPAA, ISO 27001, NIST 800-53, + fictional Helix Dynamics policies
- Tee up the Scenario Generator wow moment

### Slot 2 — Default Scenario Interrogation (3-4 min)

**Demo beats in this slot:** (1) grounded FA retrieval with sources, then (2) persona-driven suspect interrogation. Two different agent patterns side by side.

- Click 🏥 **Default (Healthcare)** scenario picker on first load
- Click 🔍 **Evidence** — the audience sees a clean roster of every piece of evidence with a value rating, plus a row of 📄 **EV-NNN** buttons (one per item). Click 📄 **EV-003** (the ServiceNow change request) to surface its full detail as a new message. The picker buttons re-attach to every detail message (with a • marker on the currently-displayed item) so you can jump straight to another piece of evidence without scrolling back. Narrate: *"EV-003 is going to be central — notice Morgan Webb requested the MFA exception three weeks before the breach."*
- **Open with a Forensic Analyst question (NO suspect picked yet)** — type into the chat: *"Walk me through HD-SEC-AC-001 §4.1 and which evidence items show controls were bypassed."*
- **Sources panel attaches** — you'll see entries like `[1] access_control_policy.md (score 5.82)`, `[2] helix_dynamics_overview.md (score 4.21)`, `[3] soc2_trust_service_criteria.md (score 3.94)` as side-drawer pills next to the FA's response. Click one to expand the actual snippet for the audience.
- **Control IDs vs source filenames** — the FA cites control IDs like `HD-SEC-AC-001 §4.1` and `SOC 2 CC6.1` *in the response text*. Those are the policy section identifiers. The source panel shows the *underlying retrieved files* (12 docs in the index: 4 framework files, 4 Helix policies, 3 playbooks, 1 company overview). Different surfaces, same evidence trail.
- Narrate: *"The activity log just showed `[Foundry IQ] Retrieved N sources` — these aren't training data, they're real chunks pulled from the index in real time. That's how we close the trust loop on compliance content."*
- Click 👥 **Suspects** → pick **Casey Doyle** (executive assistant, phishing victim)
- Ask: *"Tell me about emails you received Sunday night before the incident."*
- Narrate the shift: *"Notice no sources attach here. Suspect agents are a different pattern — persona-driven prompts with backstory, alibis, and leak conditions. Same Foundry Agent Service, completely different role."*
- Switch to **Riley Park** (the perpetrator in Default), ask: *"Walk me through your vendor access workflow."*
- Tee up Slot 3: *"Now let's see if we can hot-load a brand new scenario from a one-sentence breach prompt."*

**Reminder — which agents attach sources:**
- ✅ Forensic Analyst (free-text question with no suspect active)
- ✅ Compliance Officer (after Accuse or Wrap)
- ❌ Suspects (persona only, no retrieval)

### Slot 3 — Scenario Generator Live Build (4 min)

- Click 🆕 **Generate**
- Paste the host-supplied breach (or use this if no host prompt): *"A contractor's stolen laptop with cached HelixVault credentials is used to exfiltrate IRB submission documents over 48 hours from a hotel network."*
- **Timing reality:** the Generator can take 30-90 seconds when validation retries fire. If you're past 60s and the audience looks restless, narrate: *"The Scenario Generator just hit a validation error and is self-correcting — you'll see it retry in the log in a moment."*
- When the new scenario hot-loads, briefly point out: brand new premise, new suspects with the same canonical cast (Alex, Morgan, Riley, Casey, Jordan), new evidence graph, new compliance lesson

### Slot 4 — Final Reveal + Compliance Officer (3-4 min)

- Run one interrogation in the new scenario
- Click ⚖️ **Accuse** → pick a suspect
- Compliance Officer delivers the closer with framework citations and the post-mortem
- Land the message: *"This is what compliance training feels like when reasoning agents are good enough to gamify it. The framework lesson sticks because the player just earned it."*

---

## Quick Recovery Moves

| Problem | Move |
|---|---|
| Chainlit looks frozen mid-response | Wait 30 more seconds (Azure cold starts can cause this). If still hung, hard-refresh browser. |
| Generate is hung past 2 minutes | Open Terminal A and confirm the Scenario events are flowing. If silent, refresh Chainlit and switch to a pre-built backup scenario. |
| Chainlit dies entirely | Switch to Terminal C, run `python -m src.orchestrator`. Same agents, terminal UI. The CLI fallback you teased in the opening. Audience sees the recovery as a feature, not a fail. |
| Azure call returns content filter error | Pick a different suspect or rephrase the question. The agents have retry layers but the surface error is the safest case. |
| Mid-stream silence from an agent | The audience sees the activity log. Let the streaming finish naturally. Don't narrate over the streaming tokens — let the visual carry it. |
| Token expired (`DefaultAzureCredential failed`) | Open a 4th terminal, run `az login`, refresh Chainlit. Whole process takes ~30 seconds. |

---

## Backup Scenarios (Pre-Loaded)

| Scenario | Perpetrator | Use when |
|---|---|---|
| `helix_dynamics_default.json` | Riley Park (vendor) | Default opening |
| `helix_dynamics_supplychain.json` | Morgan Webb (IT) | Generate fails OR host wants a different vector |
| `helix_dynamics_vishing.json` | Jordan Smith (intern) | Backup for a social-engineering angle |

Pick scenario from the picker on first load, or click 🆕 **Generate** anytime to swap.

---

## Closing Reflection (one line, 30 seconds)

Pick one based on what landed best during the demo:

- *"What I'd build next is a Manager Insights dashboard that aggregates readiness across an entire workforce."*
- *"What surprised me most was how much the role-play framing changed the reasoning quality. Asking 'as the Forensic Analyst, what do you think' produces more useful output than asking 'analyze this evidence' directly."*
- *"Enterprise compliance training is the most boring AI application nobody's done well yet. There's a real opportunity for whoever cracks the gamification."*

---

## After Going Off-Air

1. Save the activity log (`logs/activity.log`) for the recap blog
2. Push any last-minute commits to the public repo
3. Post on LinkedIn within 24 hours with a short clip
4. Send Lee Stott and Carlotta a thank-you
5. Brief Nick Scott and Greg Tselikis with stream highlights for client conversations
