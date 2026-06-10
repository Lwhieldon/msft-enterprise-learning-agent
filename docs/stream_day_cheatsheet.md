# Stream Day Cheatsheet

**Event:** Microsoft Reactor Reasoning Agents Live Streaming Battle
**Date / Time:** Wednesday, June 10, 2026 · 12:00 PM ET
**Tech check:** 11:45 AM ET (be ready 15 min early)

This is the laser-focused one-page reference for stream day. For the full runbook (architecture talking points, fallback plans, post-stream actions), see [`live_battle_runbook.md`](./live_battle_runbook.md).

---

## T-30 Pre-Flight (5 minutes total)

```powershell
cd C:\Users\lwhieldon\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
echo $env:REQUESTS_CA_BUNDLE     # MUST show C:\Users\lwhieldon\corp-ca-bundle.pem
az login
az account show                  # confirm SC&H Foundry subscription is active
pytest                           # unit tests should all pass, runs in seconds
python -m src.scenario_loader    # three OK lines, no Azure call
```

**If `REQUESTS_CA_BUNDLE` is empty:** Netskope will block `az login` with a self-signed certificate error. Set it for the session before continuing:

```powershell
$env:REQUESTS_CA_BUNDLE = "C:\Users\lwhieldon\corp-ca-bundle.pem"
```

If anything else in the block above fails, fix it before going live. Re-running `az login` resolves 95% of the rest.

---

## Two Terminals to Open

### Terminal A — Activity log (the audience proof surface)

```powershell
cd C:\Users\lwhieldon\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
.\scripts\tail_activity.ps1 -Clear
```

### Terminal B — Chainlit UI (the player surface)

```powershell
cd C:\Users\lwhieldon\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
chainlit run app.py
```

_Note: no `-w` flag for the live demo. Watch mode adds a file watcher that logs "change detected" noise every time the agents write to `activity.log`. Cleaner stream terminal without it._

Open browser to `http://localhost:8000`, hard-refresh with Ctrl+Shift+R to bust any CSS cache.

### Terminal C — CLI fallback (open but minimized)

```powershell
cd C:\Users\lwhieldon\msft-enterprise-learning-agent
.\.venv\Scripts\Activate.ps1
# Don't run yet. If Chainlit breaks mid-stream:
python -m src.orchestrator
# Type `help` for the command list
```

---

## Screen Layout on Stream

- **Primary share:** the Chainlit browser tab
- **Secondary visible:** Terminal A (activity log scrolling)
- **Switch share to VS Code** during Q2 for the code walkthrough (Ctrl+B to hide the sidebar, Ctrl+= to bump font size if needed). Keep the agent files pre-opened in tabs so navigation is one click.
- The audience sees both. The UI tells the story; the log proves it's real; the code shows depth.

---

## Session Flow (from Carlotta's email)

This is the actual format the hosts will run. Three rotating 5-minute Q&A rounds: hosts ask the same question to each competitor in turn before moving to the next question. You're on camera for 5 minutes at a time, three times, totaling ~15 minutes of airtime. Hosts will bounce to other competitors between your slots.

| Block | Time | Who | What |
|---|---|---|---|
| Intro to Agents League | 5 min | Carlotta & Lee Stott | Host-led event intro |
| Intro to the 2 challenge scenarios | 2 min | Carlotta | Host introduces the official challenges — **listen carefully so you can name yours in Q1** |
| **Q1: Which challenge did you choose + tech stack** | 5 min each | You | Your turn comes when hosts cycle to you |
| **Q2: Code/details walkthrough** | 5 min each | You | The Foundry code tour (see Appendix A) |
| **Q3: Demo + plans to evolve it** | 5 min each | You | Live demo + closing reflection on what's next |
| Wrap-up and CTAs | 3 min | Hosts (you contribute) | Have your CTAs ready (see below) |
| Q&A margin | ~5 min | Audience | Be ready for the likely questions (see below) |

**Total airtime for you: ~15 minutes across three slots.** Each slot is hard-capped at 5 minutes — hosts will cut you to move to the next competitor. Practice each slot at the 4:30 mark so you have buffer for transitions.

---

## Q1 — Challenge Choice + Tech Stack (5 min)

**Hosts ask:** *"Which challenge did you choose and which approach/tech stack did you choose to address it?"*

**On screen:** Hero banner / GitHub README (visual identity). Switch from this to architecture talking points at minute 2.

**The 5-minute structure:**

*0:00 — 0:30 — Name the challenge and your one-sentence pitch.* Carlotta will have just introduced the 2 official challenges. Cleanly name which one you picked, then your hook: *"I chose a mix between the reasoning & enterprise challenge - A combo of both!. I built Compliance Academy: a multi-agent cyber-mystery game where the player is a lead investigator at a fictional biotech that just lost 14 GB of clinical trial data. Five suspects, one perpetrator, and at the end a Compliance Officer agent delivers the actual framework lesson the player just lived through."*

*0:30 — 1:30 — Why this approach.* *"Compliance training is the most boring AI application that nobody's done well yet. Click-through PDFs, multiple-choice quizzes, no retention. I wanted to test whether reasoning agents are good enough to gamify it. The bet: if the player has to interrogate suspects and reason about evidence to find the answer, the framework lesson sticks because they just earned it."*

*1:30 — 3:30 — Tech stack walkthrough.* **Switch share to `docs/foundry_tech_stack.html` (open in browser, F11 for fullscreen)** so the audience sees the architecture as you narrate it. Walk top-to-bottom through the diagram:
- **Microsoft Foundry Agent Service** with the **Connected Agents** pattern. Four party agents (Game Master, Forensic Analyst, Compliance Officer, Scenario Generator) plus five suspect agents per scenario.
- **Azure OpenAI gpt-4.1-mini** routed through Foundry's **Model Router** — one endpoint, automatic model selection, no per-model deployment juggling.
- **Azure AI Search** as the **Foundry IQ** retrieval index — 52 chunks across SOC 2, HIPAA, ISO 27001, NIST 800-53, plus the fictional biotech's internal policies.
- **Entra ID** auth via DefaultAzureCredential — no API keys anywhere in the codebase.
- **Chainlit** for the player-facing UI plus a **live activity log terminal** that streams every retrieval and every model call in real time.

*3:30 — 4:30 — Why these specific choices.* *"Foundry isn't just OpenAI behind an Azure URL. The Connected Agents pattern, Model Router, and Foundry IQ retrieval are what make this a multi-agent system instead of a fancy chatbot. The activity log is how I prove that on stream — every Foundry IQ retrieval and every Azure OpenAI call shows up with its source filename and relevance score. The trust loop closes on screen."*

*4:30 — 5:00 — Tee up Q2.* *"In the next round I'll switch to the actual code so you can see exactly how this is wired — about 60 lines of Python is what stands between you and a production-ready agentic retrieval system on Foundry."*

---

## Q2 — Code & Details Walkthrough (5 min)

**Hosts ask:** *"Can you walk through the code/share the details of what you are building?"*

**On screen:** Switch share from Chainlit to VS Code. Three files pre-opened in tabs (see Appendix A for exact navigation):
1. `src/agents/_azure_client.py`
2. `src/agents/_search_client.py`
3. `src/agents/scenario_generator.py`

**The 5-minute structure — three Foundry capability beats:**

*0:00 — 0:30 — Set context.* *"I'm going to walk through three Python files that show three distinct Foundry capabilities. Each one is short — the whole agentic retrieval pattern is about 60 lines of business logic."*

*0:30 — 1:45 — Beat 1: Auth (no API keys).* Open `src/agents/_azure_client.py`, land on `build_azure_client()`. Narrate: *"Authentication is just Entra ID via DefaultAzureCredential. No API keys, no secret rotation, no .env-with-secrets sitting in a repo somewhere. The same `az login` that authorizes the Azure CLI is what authorizes every agent call. That's the Foundry promise: enterprise-grade auth becomes the default, not an upgrade."*

*1:45 — 3:15 — Beat 2: Foundry IQ retrieval.* Open `src/agents/_search_client.py`, land on `retrieve_context()`. Narrate: *"Foundry IQ retrieval is just a typed query against an Azure AI Search index. Roughly five lines of business logic: search the index, return ranked snippets with scores and source URLs. The Forensic Analyst and Compliance Officer call this BEFORE they call the model. That's why citations stay grounded in real policy text — the model doesn't have to remember what SOC 2 CC6.1 says, the index hands it the relevant chunk first."*

*3:15 — 4:30 — Beat 3: Structured generation with validation retry.* Open `src/agents/scenario_generator.py`, land on `_build_validation_retry_message()` and the surrounding outer loop. Narrate: *"Generated structured output isn't always valid. The model sometimes produces scenarios with two perpetrators, or four red herrings, or missing a required field. So I wrap the generate call in a validation retry loop — the loader checks the structure, and if it fails, I feed the specific error back to the model as corrective feedback for the next attempt. That's defensive engineering on top of Foundry's streaming + structured generation. It's what makes the hot-loaded scenarios you'll see in the demo actually safe to play through."*

*4:30 — 5:00 — Tee up Q3.* Switch share back to Chainlit. *"In the demo round, you'll see this code actually running. I'll throw the host-supplied breach at the Scenario Generator and we'll watch it build a brand-new compliance case in real time."*

---

## Q3 — Live Demo + Evolution Plans (5 min)

**Hosts ask:** *"Can you showcase a brief demo of what you've built so far? Any plans on how to evolve it?"*

**On screen:** Chainlit UI with the Default Helix Dynamics scenario already loaded from your T-30 setup. Briefing panel visible.

**The 5-minute structure — play one scenario end-to-end, then evolution plans:**

*0:00 — 0:45 — Forensic Analyst grounded retrieval.* Type into chat (no suspect picked):

> *Walk me through HD-SEC-AC-001 §4.1 and which evidence items show controls were bypassed.*

While the response streams, narrate: *"The Forensic Analyst is grounding this in five real policy chunks. Watch the side panel — those are the actual files from the index, with relevance scores. The activity log on the right just showed `[Foundry IQ] Retrieved 5 sources`. That's how the citation trail closes in real time."*

*0:45 — 2:00 — Interrogate Suspect #1: Casey Doyle (the phishing victim).* Click 👥 **Suspects** → **Casey Doyle**. Type:

> *Tell me about emails you received Sunday night before the incident.*

While Casey responds, narrate: *"Notice the side panel didn't attach this time. Suspect agents are a different pattern — persona-driven prompts with backstory, alibi, and leak conditions. Same Foundry Agent Service, completely different role."*

If time permits, follow up with:

> *Did you notice anything unusual about your laptop after that industry conference?*

*2:00 — 3:15 — Interrogate Suspect #2: Riley Park (the perpetrator).* Click 👥 **Suspects** → **Riley Park**. Type:

> *Walk me through your vendor access workflow on the night of the breach.*

Narrate during the response: *"Riley is the third-party vendor in this scenario — their access pattern is the angle the player needs to probe. Watch how the persona stays in character without leaking the answer."*

If time permits, push harder:

> *Were you logged into HelixVault between 11 PM Sunday and 3 AM Monday?*

*3:15 — 4:00 — Accuse Riley Park, Compliance Officer closes the case.* Click ⚖️ **Accuse** → select **Riley Park**. While the Compliance Officer streams its closer, narrate: *"This is the framework moment. Compliance Officer is grounded in the same Foundry IQ index as the Forensic Analyst — watch the sources panel attach again. It's citing the specific controls that were violated, tying them to SOC 2 CC6.1 and the internal access policy. The framework lesson sticks because the player just earned it."*

*4:00 — 4:45 — Evolution plans.* Pick the one that lands best in the moment:
- *"What I'd build next is a Manager Insights dashboard that aggregates readiness across an entire workforce — every scene the player runs becomes a training signal. 'EMP-001 needs more practice on vendor risk under SOC 2 CC9.2.' Evidence-backed, specific, generated from play."*
- *"I also have a Scenario Generator agent that can hot-load a brand new case from any breach description — you saw that file in Q2 with the validation retry loop. The natural next step is letting an instructor or compliance lead drop in a real incident and have the system build a teaching scenario around it."*
- *"What surprised me most was how the role-play framing changed the reasoning quality. Asking an agent 'as the Forensic Analyst, what do you think' produces more useful output than asking 'analyze this evidence' directly. There's something worth studying in personification-as-prompt-engineering."*
- *"Enterprise compliance training is the most boring AI application nobody's done well yet. Whoever cracks the gamification owns a real category."*

*4:45 — 5:00 — Close and hand back.* *"That's Compliance Academy. Hand back to you, Carlotta."*

**If a suspect gives an unexpectedly short or evasive response:** that's actually a good moment, not a problem. Narrate it: *"Notice how Riley is staying in character and not just confessing — that's the persona-driven pattern doing its job. The player has to triangulate across multiple suspects and the evidence to find the answer."* Then move on to the next beat. Don't try to coax a longer response.

**If the Forensic Analyst question doesn't surface the sources panel:** the call may still be streaming. Wait 5 more seconds. If it lands without sources, narrate the response normally and pivot to the suspects — don't dwell on the missing panel.

---

## Q&A Prep — Anticipated Audience Questions

The last ~5 minutes are open Q&A. Prepare one-liner answers for each so you don't have to think on the fly.

| Question | Your answer |
|---|---|
| *"Can this work for other domains besides compliance?"* | *"Yes — the engine is domain-agnostic. Swap the policy index for HR docs, sales playbooks, or product specs and the same Connected Agents pattern works. Compliance was my first target because the framework citations make the grounding test obvious."* |
| *"How much does a scenario cost to run?"* | *"Each full scene is roughly a few cents of gpt-4.1-mini usage plus negligible Azure AI Search cost. The Scenario Generator is the priciest call (10-20k tokens). For a training rollout the per-employee cost would be well under a dollar per hour of playtime."* |
| *"How do you handle hallucinations in the compliance content?"* | *"Forensic Analyst and Compliance Officer ground every citation in retrieved policy text. The model writes the narrative; the retrieval determines what facts are available. The activity log shows the retrieved sources by name and score so you can audit each citation."* |
| *"What about latency — doesn't streaming get slow?"* | *"First token usually 1-3 seconds, full responses 5-15 seconds. Generate is the longest call at 10-60 seconds depending on validation. The activity log gives the audience something to watch while streaming runs."* |
| *"Are the suspects fighting each other? Multi-agent debate?"* | *"Not in this build. The suspects are persona-driven — they only respond when the player asks. The party agents (Forensic Analyst, Compliance Officer) are the ones with retrieval-grounded reasoning. A multi-agent debate variant is on my roadmap."* |
| *"How long did this take to build?"* | *"About three weeks of focused evening work. Most of the time was on the prompts and the scenario data — the Foundry plumbing came together in days."* |
| *"Will you open-source it?"* | *"It's already on GitHub: github.com/lwhieldon/msft-enterprise-learning-agent."* |

---

## Wrap-Up CTAs (Hosts allocate 3 min)

Have these ready so when hosts ask for closing thoughts you can rattle them off cleanly:

- **GitHub:** `github.com/lwhieldon/msft-enterprise-learning-agent`
- **Blog post:** `lwhieldon.github.io/2026/06/08/compliance-academy.html`
- **LinkedIn:** post-stream connect requests welcome — mention you'll be sharing a recap clip
- **The ask:** *"If you build something on this engine for your own compliance domain, message me on LinkedIn — I want to compare notes."*

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

## After Going Off-Air

1. Save the activity log (`logs/activity.log`) for the recap blog
2. Push any last-minute commits to the public repo
3. Post on LinkedIn within 24 hours with a short clip
4. Send Lee Stott and Carlotta a thank-you
5. Brief Nick Scott and Greg Tselikis with stream highlights for client conversations

---

## Appendix A — Code Walkthrough Quick Reference (for Q2)

Keep these three files open in VS Code tabs before going live. During Q2 you'll switch share to VS Code and walk through them in order. Pre-position your cursor at the function indicated so Ctrl+G is one keystroke and the audience never sees you scrolling.

| Beat | File | What to land on | What to narrate (one line) |
|---|---|---|---|
| Auth | `src/agents/_azure_client.py` | `build_azure_client()` function | *"Entra ID via DefaultAzureCredential. The same `az login` authorizes every agent."* |
| Retrieval | `src/agents/_search_client.py` | `retrieve_context()` function | *"Foundry IQ is a typed query against Azure AI Search. Ranked snippets with scores. Five lines."* |
| Validation retry | `src/agents/scenario_generator.py` | `_build_validation_retry_message()` plus the surrounding outer for-loop | *"Structured generation isn't always valid. So I feed validation errors back to the model as corrective feedback."* |

**Foundry capabilities each beat showcases:**

- **Beat 1 (auth):** Entra ID integration, no API keys, single sign-on across CLI and agents
- **Beat 2 (retrieval):** Foundry IQ agentic retrieval pattern, Azure AI Search with relevance scoring, RBAC-based index access
- **Beat 3 (validation retry):** Foundry's streaming + structured generation + the defensive engineering pattern that makes it production-safe

**Mechanical reminders:**

- VS Code zoom: `Ctrl + =` to enlarge text for the audience. Bump to font size 18-20 before going live.
- Hide the sidebar: `Ctrl + B`. Maximizes the code area.
- Minimap and breadcrumbs OFF (View menu). Less visual noise on stream.
- Open the three files BEFORE going live so they're in your recent-files list (Ctrl+P then arrow keys is fast).
- If you get lost mid-tour, fall back to: *"All of this is in the public repo — github.com/lwhieldon/msft-enterprise-learning-agent — link in the closing slide."*
