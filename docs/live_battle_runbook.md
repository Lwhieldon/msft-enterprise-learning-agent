# Live Battle Runbook

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

## Lee's Airtime Map

These minute marks are estimates based on Battle 2. Adjust to host pacing on the day.

| Slot | Approx. minute | Duration | What Lee shows |
|---|---|---|---|
| Pre-roll bio | 10-12 | 60 seconds | One-line pitch, hint at the surprise |
| Architecture intro | 18-22 | 3-4 minutes | Diagram, agent topology, Model Router, tee up Scenario Generator |
| Check-in #1 | 30-35 | 3-4 minutes | Live interrogation in default Helix Dynamics scenario, reasoning chains streaming |
| Check-in #2 | 43-48 | 3-4 minutes | The wow moment: Scenario Generator builds the host-thrown breach into a new case |
| Final reveal | 51-56 | 3-4 minutes | Live interrogation of the generated scenario, Compliance Officer surfaces the lesson |
| Reflection | 58-59 | 30-60 seconds | One line: what comes next |

## Pre-Roll Bio (60 seconds)

Draft, customize as you like:

> "I'm Lee Whieldon, a Principal on SC&H's Enterprise Advisory & Transformation team. Fifteen years modernizing data ecosystems on the Microsoft platform across Azure, Fabric, Power BI, and most recently Foundry and Copilot. For this battle I built Compliance Academy: a multi-agent role-play game on Foundry Agent Service, where five investigator agents help a human player solve a corporate data breach. It leverages all three Microsoft IQs for grounded content and Model Router for cost-aware routing across reasoning and persona models. I'm hoping a host throws me a surprise breach so the system can improvise on stream."

If the host asks a different question, answer it directly and keep the substance.

## Slot 1: Architecture Intro (minute 18-22)

**On screen:** Architecture diagram open. Chainlit UI behind it ready to go.

**Talking points in order:**

1. The premise. "Helix Dynamics, fictional biotech, lost 14GB of trial data overnight. The player is the investigator on Day 1. This is a role-play game where the gameplay IS the assessment."
2. The topology. "Game Master orchestrates. Five investigator party members assist the player. Five suspects per scenario. A Scenario Generator agent can produce a new case from any breach description. A Compliance Officer agent surfaces the real-world lesson at the end."
3. The reasoning showcase. "Four of these agents run on reasoning models routed through Foundry's new Model Router. Three Microsoft IQs plug in as different kinds of evidence: Foundry IQ for compliance frameworks, Work IQ for employee work signals, Fabric IQ for the semantic investigation ontology."
4. The tee-up. "I'm going to run the default scenario in a moment, but the part I'm most excited for is when the hosts throw me a new breach. Watch the Scenario Generator write a brand-new case in real time, then watch the player play it."

Target: 3 to 3.5 minutes. Do not exceed 4.

## Slot 2: Check-in #1 (minute 30-35)

**On screen:** Chainlit UI showing an active interrogation of the HR Director suspect.

**Talking points:**

1. "We are in Act 2. The player just asked the HR Director why she stayed late Thursday. Watch the Forensic Analyst's reasoning chain stream in real time as she cross-references the Work IQ signals against the suspect's claimed alibi."
2. Let the reasoning render. Do not narrate over the streaming tokens. The visual carries the moment.
3. After the analysis lands: "Notice that the Forensic Analyst flagged a conflict. The HR Director's work signal shows no after-hours activity, but the access logs do. The Compliance Auditor will pick that up next round."
4. Quick architecture pointer: "Behind the scenes, the GM is routing this turn to the Forensic Analyst with the suspect's response in context. The Foundry Connected Agents pattern handles the plumbing. Model Router selected a reasoning-tier model because the GM flagged this turn as high-complexity."

**Background activity while this runs:** prepare to paste the host-thrown breach into the Scenario Generator. Have a tab open and ready.

Target: 3 minutes. Do not exceed 4.

## Slot 3: Check-in #2, The Wow Moment (minute 43-48)

**On screen:** Chainlit UI split with the Scenario Generator's reasoning chain on the left and the generated JSON populating on the right.

**Talking points:**

1. "Earlier the hosts handed me [host's chosen breach]. I just pasted the description into the Scenario Generator. Watch it reason through what a synthetic version of this case would look like."
2. Let the reasoning stream. Highlight one or two interesting moves the model makes. ("Notice it just deduced that the most plausible suspect role for this attack pattern is a third-party vendor.")
3. When generation completes: "The output is a complete case file. New synthetic suspects with new alibis. New evidence graph. New mapped compliance lesson. All grounded in Foundry IQ for citation integrity."
4. "Now I'm going to hot-load this into the game state, and we'll run an interrogation on this brand new scenario in our final slot. Audience, if you can drop in chat which suspect you want me to question first, I'll pick the most-voted one."

This is the spike moment. Energy goes up. Be specific about what the system did that was hard.

Target: 4 minutes. Can stretch to 4.5 if generation is slow.

## Slot 4: Final Reveal (minute 51-56)

**On screen:** Live interrogation of the audience-chosen suspect in the newly generated scenario.

**Talking points:**

1. "Audience picked [suspect name]. Here we go." Start the interrogation.
2. Let one full exchange play out. Party reacts in character. Forensic Analyst pulls grounded evidence. Compliance Auditor cites the controlled framework.
3. After the exchange: "And here's what makes this useful. The Compliance Officer agent surfaces what just happened in real-world terms." Trigger the Compliance Officer.
4. Compliance Officer cites the framework section. Close with: "If this were a real enterprise rollout, every employee would walk through scenarios like this. They would get a readiness signal from the Manager Insights view, and the gaps would be specific: 'EMP-001 needs more practice on vendor risk under SOC2 CC9.2.'"

Target: 3 to 4 minutes.

## Reflection (minute 58-59)

One line. Pick one of:

- "What I'd build next is a Manager Insights dashboard that aggregates readiness across an entire workforce. The Fabric IQ semantic model is already there. The visualization is the missing piece."
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
- [ ] Claude Sonnet 4.5 and Haiku 4.5 deployments healthy in the Foundry resource
- [ ] Foundry IQ index populated with synthetic policy documents

### Application

- [ ] Default Helix Dynamics scenario loaded
- [ ] Backup scenarios (`helix_dynamics_supplychain.json`, `helix_dynamics_vishing.json`) verified end-to-end
- [ ] Chainlit UI running on a dedicated tab (`chainlit run app.py -w`)
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
