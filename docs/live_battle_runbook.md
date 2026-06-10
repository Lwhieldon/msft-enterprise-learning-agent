# Live Battle Runbook

> **Format update (June 9 host email):** the actual session is **three rotating 5-minute Q&A rounds** (~15 min airtime), NOT the continuous 4-slot demo originally planned. Use [`stream_day_cheatsheet.md`](./stream_day_cheatsheet.md) as the day-of reference — it has the Q1/Q2/Q3 structure with prep-able answers for each question. This runbook is now background context (bio, format reality, fallback plans) plus the original slot scripts as historical reference.

**Event:** Agents League Post Build edition, Reasoning Agents Live Streaming Battle
**Date:** June 10, 2026, 12:00 PM EST (9:00 AM PT)
**Platform:** Streamyard, broadcast to the Microsoft Reactor YouTube channel
**Hosts:** Lee Stott and Carlotta Castelluccio
**Competitors:** Princeps, Lee Whieldon, plus one TBC
**Tech check:** 15 minutes early (11:45 AM EST). Show up earlier than that.

## The Format Reality

Total broadcast: approximately 1 hour. From the prior Battle 2 broadcast (Feb 2026):

- ~17 min pre-roll (welcomes, code of conduct, scenario overview, competitor intros, voting explanation)
- ~41 min live coding window with three competitors rotating across short segments
- ~4.5 min reflections, what's next, close

Each competitor gets four short slots totaling 12 to 15 minutes of airtime. The work happens in background while hosts cut between competitors. Lee's job is to be ready with a concrete deliverable at each checkpoint.

## Lee's Airtime Map (Updated from June 9 host email)

Three rotating 5-minute Q&A rounds. Hosts ask the same question to each competitor in turn before moving to the next question. You're on camera 5 minutes at a time, three times, totaling ~15 minutes.

| Block | Approx. minute | Duration | What |
|---|---|---|---|
| Pre-roll: Agents League intro | 0-5 | 5 minutes | Host-led, you don't speak |
| Pre-roll: 2 challenge scenarios intro | 5-7 | 2 minutes | Carlotta introduces — listen for which challenge applies to you |
| **Q1 round (all competitors): challenge + tech stack** | 7-22 | 5 min each | Your slot is one of these three |
| **Q2 round (all competitors): code walkthrough** | 22-37 | 5 min each | Foundry capability tour |
| **Q3 round (all competitors): demo + evolution** | 37-52 | 5 min each | Live demo + what's next |
| Wrap-up + CTAs | 52-55 | 3 min | Host-led, have your CTAs ready |
| Audience Q&A | 55-60 | 5 min | Anticipated questions pre-loaded in cheatsheet |

**The original 4-slot continuous-demo airtime map (Slot 1 → Slot 4 below) is preserved as background but is not the day-of structure.** The slot scripts contain useful narrative beats that have been consolidated into the cheatsheet's Q1/Q2/Q3 sections.

## Pre-Roll Bio (60 seconds)

Draft, customize as you like:

> "I'm Lee Whieldon, a Principal on SC&H's Enterprise Advisory & Transformation team. Fifteen years modernizing data ecosystems on the Microsoft platform across Azure, Fabric, Power BI, and most recently Foundry and Copilot. For this battle I built Compliance Academy: a multi-agent cyber-mystery game on Microsoft Foundry Agent Service. Four party agents work alongside a roster of five suspects to help a human player solve a corporate data breach. The agents ground their responses in real policy documents through Foundry IQ — an Azure AI Search index covering SOC 2, HIPAA, ISO 27001, NIST 800-53, plus a fictional biotech's internal policies. I'm hoping a host throws me a surprise breach so the system can improvise on stream."

If the host asks a different question, answer it directly and keep the substance.

## Slot 1: Architecture Intro (minute 18-22)

**On screen:** Architecture diagram open. Chainlit UI behind it ready to go.

**Talking points in order:**

1. The premise. "Helix Dynamics, fictional biotech, lost 14GB of trial data overnight. The player is the investigator on Day 1. This is a role-play game where the gameplay IS the assessment."
2. The topology. "Game Master orchestrates the scene. Three other party agents assist: the Forensic Analyst pulls grounded retrieval from a compliance policy index, the Compliance Officer delivers the framework-grounded post-mortem at the end, and the Scenario Generator can hot-load a brand-new case from any breach description. Plus five suspect agents per scenario — persona-driven, each with their own backstory, alibi, and leak conditions."
3. The reasoning showcase. "All agents run on gpt-4.1-mini routed through Foundry's Model Router. The Forensic Analyst and Compliance Officer ground their responses through Foundry IQ — an Azure AI Search index with 52 chunks across SOC 2, HIPAA, ISO 27001, NIST 800-53, plus the fictional biotech's internal policies. The activity log on screen shows every retrieval with its source filename and relevance score, so you can see the trust loop close in real time."
4. The tee-up. "I'm going to run the default scenario in a moment, but the part I'm most excited for is when the hosts throw me a new breach. Watch the Scenario Generator write a brand-new case in real time, then watch the player play it."

**Optional code walkthrough beat (2-3 min):** if you want to spend airtime showing Foundry capabilities in code, switch share to VS Code and walk through three files: `_azure_client.py` (Entra ID auth, no API keys), `_search_client.py` (Foundry IQ retrieval as a typed Azure AI Search query), and `scenario_generator.py` (structured generation with validation retry loop). Detailed beats + narration in [`stream_day_cheatsheet.md`](./stream_day_cheatsheet.md) Appendix A.

Target: 4 to 5 minutes if code walkthrough included, 3 to 3.5 minutes if not.

## Slot 2: Check-in #1 (minute 30-35)

**On screen:** Chainlit UI showing the default Helix Dynamics briefing. About to surface evidence and run a Forensic Analyst question.

**Talking points in order:**

1. "We are in Act 1. The player has just been briefed on the breach." Click 🔍 **Evidence**. "Twelve pieces of evidence on the table, each ranked by investigative value. Let me pull up EV-003 — the ServiceNow change request from three weeks before the breach. Notice the requester: Morgan Webb, our IT admin. Notice the approval field is empty." Click 📄 **EV-003**.
2. Pivot to grounded retrieval. "Now let me ask the Forensic Analyst a question that requires actual policy lookup." Type into chat: *"Walk me through HD-SEC-AC-001 §4.1 and which evidence items show controls were bypassed."*
3. Let the response stream. As sources attach in the side panel, narrate: "The Forensic Analyst is citing HD-SEC-AC-001 §4.1 in the response text. The side panel is showing the actual policy file the citation was retrieved from — `access_control_policy.md`, with a relevance score. The activity log on the right just emitted `[Foundry IQ] Retrieved 5 sources`. These aren't training data — they're real chunks pulled from the index in real time. That's the trust loop for compliance content."
4. Contrast with the suspect pattern. Click 👥 **Suspects** → pick **Casey Doyle**. "Now I'm switching to a suspect agent. Casey was the phishing victim — an executive assistant whose session token got stolen." Ask: *"Tell me about emails you received Sunday night before the incident."*
5. Let the suspect respond. After: "Notice the side panel didn't attach this time. Suspects are persona-driven prompts — backstory, alibi, leak conditions. Same Foundry Agent Service, completely different role. The Forensic Analyst grounds in policy. Suspects ground in their own fabricated history."

**Background activity while this runs:** prepare to paste the host-thrown breach into the Scenario Generator. Have it staged mentally.

Target: 3 to 4 minutes. Do not exceed 4.

## Slot 3: Check-in #2, The Wow Moment (minute 43-48)

**On screen:** Chainlit UI showing the Scenario Generator working: a placeholder message while the model builds the new scenario, with the activity log on the right streaming retrieval and generation events.

**Talking points:**

1. "Earlier the hosts handed me [host's chosen breach]. I just pasted the description into the Scenario Generator. Watch it build a complete new case from one sentence."
2. Let the activity log carry the moment. Highlight one or two interesting things in real time. ("Notice the validation layer just kicked in — the model proposed a scenario, the validator checked it, fed back the error, and the model is now self-correcting. That retry loop is what makes generated scenarios actually usable.")
3. When generation completes: "The output is a complete case file: brand-new premise, five suspects with backstories and alibis, an evidence graph, six controls implicated, and a compliance lesson mapped to specific framework sections. All wired into the same UI — same buttons, same agents, completely different world."
4. "Now I'm going to run an interrogation on this brand new scenario in our final slot. Audience, drop in chat which suspect you want me to question first — I'll pick the most-voted one." (Skip the audience-vote ask if chat moderation feels noisy on the day; default to your own pick.)

This is the spike moment. Energy goes up. Be specific about what the system did that was hard — generating valid JSON that passes structural validation in 30 to 90 seconds is the real engineering moat.

Target: 4 minutes. Can stretch to 4.5 if generation is slow.

## Slot 4: Final Reveal (minute 51-56)

**On screen:** Live interrogation in the newly generated scenario, then the Compliance Officer closer.

**Talking points:**

1. "Audience picked [suspect name]. Here we go." Start the interrogation.
2. Let one full exchange play out. The suspect responds in character. Optionally ask a follow-up Forensic Analyst question to surface a grounded citation from the generated scenario's evidence graph.
3. Trigger the closing. Click ⚖️ **Accuse** → pick a suspect. "And here's where it lands. The Compliance Officer agent reviews the case, surfaces the framework lesson, and cites the controls that were implicated."
4. Let the Compliance Officer's response stream. Notice the framework citations in the body and the source attachments in the side panel.
5. Land the close: "This is what compliance training feels like when reasoning agents are good enough to gamify it. The framework lesson sticks because the player just earned it. The natural next step is a Manager Insights view on top of this: 'EMP-001 needs more practice on vendor risk under SOC 2 CC9.2.' Specific, evidence-backed, generated from the play."

Target: 3 to 4 minutes.

## Reflection (minute 58-59)

One line. Pick one of:

- "What I'd build next is a Manager Insights dashboard that aggregates readiness across an entire workforce — the agent activity log already captures the right signals, the visualization is the missing piece."
- "What surprised me most was how much the role-play framing changed the reasoning quality. Asking an agent 'as the Forensic Analyst, what do you think' produces more useful output than asking 'analyze this evidence' directly."
- "If you take one thing away: enterprise training is the most boring AI application nobody's done well yet. There's a real opportunity for whoever cracks the gamification."

## Fallback Plans

**If the Scenario Generator hiccups or generates poor output:**

1. Acknowledge briefly. "The Scenario Generator just produced something I'm not happy with. Let me run a backup."
2. Load one of the pre-built backup scenarios (`helix_dynamics_supplychain.json` or `helix_dynamics_vishing.json`).
3. Continue the demo from there. The audience will not know the difference.

**If a model has a transient outage:**

- Model Router automatic failover should handle this silently. If it does not, restart the Chainlit session. The Game Master will resume from the last persisted state.

**If Chainlit crashes:**

- Have a second tab open with a backup Chainlit session pre-warmed. Switch tabs. Continue.

**If everything goes wrong:**

- Switch to the recorded backup video (record one the night before the battle as insurance). Narrate over it.

## Pre-Stream Checklist (T-30 minutes)

Work through these in order. Authentication first, because every Foundry verification step below it depends on a valid Azure CLI session.

### Hardware and accounts

- [ ] Streamyard joined, mic and camera tested
- [ ] Phone silenced, Teams notifications off
- [ ] Water within reach

### Authentication and environment (DO NOT SKIP)

Azure CLI tokens expire roughly one hour after `az login`. The demo is ~1 hour long. Log in at T-30, verify at T-5, and you have margin for the full broadcast.

- [ ] Python venv activated: `.\.venv\Scripts\Activate.ps1` (prompt shows `(.venv)`)
- [ ] `.env` file present in repo root with a valid `AZURE_AI_PROJECT_ENDPOINT`
- [ ] Authenticated to Azure CLI: `az login`
- [ ] Correct subscription active: `az account show` shows the SC&H Foundry subscription
- [ ] Unit tests pass (no API calls, instant):
  ```powershell
  pytest
  ```
  All tests under `tests/unit/` should pass. If anything fails here, the build is broken and no live call will help; fix before going live.
- [ ] Loader smoke test passes (no API calls, instant, streams scenario summary):
  ```powershell
  python -m src.scenario_loader
  ```
  Three `OK` lines expected.
- [ ] Scenario Generator smoke test passes (one live API call, ~40-60s):
  ```powershell
  python -m src.agents.scenario_generator
  ```
  Streamed JSON, ends with `OK`. If this fails on `DefaultAzureCredential`, re-run `az login` and retry.
- [ ] Suspect agent smoke test passes (one live API call, ~5-10s):
  ```powershell
  python -m src.agents.suspect_agent
  ```
  Casey Doyle response streamed in character, ends with `OK`.

### Day-before dry run (T-1 day)

The day before the live battle, do a full integration test pass. This is the most expensive single check (~10-15 minutes, ~20 live calls) but it catches every category of failure we have seen in development: content filter false positives, jailbreak detector false positives, length cap issues, and any new regressions.

- [ ] All integration tests pass:
  ```powershell
  pytest -m integration
  ```
  All tests under `tests/integration/` should pass. Any failure indicates a real demo risk worth investigating before stream day.
- [ ] Full orchestrator dry run executed: load default scenario, interrogate at least three suspects, consult the Forensic Analyst, generate a hot-loaded scenario from a host-style breach, accuse the perpetrator, hear the Compliance Officer closer. End-to-end demo path verified.

### Foundry and models

- [ ] Foundry project deployed and reachable
- [ ] Model Router deployment healthy
- [ ] gpt-4.1-mini deployment healthy in the Foundry resource
- [ ] Foundry IQ index (`compliance-content-index`) populated with synthetic policy documents

### Application

- [ ] Default Helix Dynamics scenario loaded
- [ ] Backup scenarios (`helix_dynamics_supplychain.json`, `helix_dynamics_vishing.json`) verified end-to-end
- [ ] Chainlit UI running on a dedicated tab (`chainlit run app.py` — no `-w` for live demo)
- [ ] Live activity log tailing in a second terminal (`.\scripts\tail_activity.ps1 -Clear`)
- [ ] Second Chainlit tab pre-warmed as backup

### Stream materials

- [ ] Architecture diagram open in a separate tab
- [ ] Concept doc open as a reference for any host questions
- [ ] Backup demo video accessible
- [ ] Public repo URL handy for the close

### Final 5-minute auth re-verification (T-5 minutes)

Quick sanity check right before going live. Token from `az login` at T-30 should still be valid, but verifying takes 2 seconds and avoids a mid-demo failure.

- [ ] `az account get-access-token --output none` returns no error
- [ ] If it does error, re-run `az login`, then re-run the Suspect agent smoke test as a final live check

## After the Battle

- Push the final code to the public repo
- Post on LinkedIn within 24 hours with a clip
- Send Carlotta a thank-you and a short post-mortem
- Brief internal stakeholders with talking points (if it landed well, this becomes case study material for client conversations)
