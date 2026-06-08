# Compliance Academy

A multi-agent role-play game for corporate compliance training, built for the Microsoft Reactor Agents League Post Build edition (Reasoning Agents Live Streaming Battle, June 10, 2026).

Compliance Academy delivers cybersecurity and compliance education through a playable breach investigation. The human player works alongside a party of five AI investigator agents to solve a corporate data breach. The reasoning is visible, the consequences are real, and the gameplay teaches enterprise compliance concepts that traditional training fails to deliver.

## What's in here

| Path | Purpose |
|---|---|
| `docs/concept.md` | The premise, agent cast, Microsoft IQ integration, scoring map |
| `docs/architecture.md` | Agent specifications, Model Router setup, game mechanics, synthetic data |
| `docs/live_battle_runbook.md` | Full stream-day runbook, four-slot demo flow, fallback plans |
| `docs/stream_day_cheatsheet.md` | One-page laser-focused day-of reference (commands, talking points, recovery moves) |
| `docs/blog/` | Launch blog drafts (GitHub + Tech Community versions) and hero image |
| `2-reasoning-agents/` | The Microsoft Reactor starter kit (reference materials, do not modify) |
| `app.py` | Chainlit UI entry point (the player-facing surface) |
| `src/` | Application code (agents, orchestrator, scenario loader) |
| `data/synthetic/` | Synthetic policies, scenarios, Foundry IQ source content |

## Tech stack

- **Microsoft Foundry Agent Service** with the Connected Agents pattern
- **Foundry Model Router** for cost-aware routing across reasoning and persona model families
- **Foundry IQ** for grounded compliance content (synthetic policy documents)
- **Work IQ** style signals for employee work pattern evidence (synthetic)
- **Fabric IQ** semantic model for the investigation ontology (synthetic)
- **Chainlit** for the player-facing UI with native reasoning chain rendering
- **Python 3.10+**

Foundry resource: `<your-unique-foundry-name>` (East US 2 or your region of choice). Model Router supports both East US 2 and Sweden Central.

## Quick start

The project runs on Python 3.10+ and authenticates to Azure AI Foundry via Entra ID (no API keys stored locally). Before running any agent, you need an active Azure CLI session.

### 1. Clone and set up the Python environment

```powershell
git clone https://github.com/lwhieldon/msft-enterprise-learning-agent.git
cd msft-enterprise-learning-agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell on Windows
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
```

### 2. Configure your Foundry endpoint

```powershell
Copy-Item .env.example .env
# Edit .env and set AZURE_AI_PROJECT_ENDPOINT to your Foundry project endpoint
# Example: https://your-foundry-resource.services.ai.azure.com/api/projects/your-project-name
```

The agents resolve their deployment names through env vars (`AZURE_AI_CHAT_DEPLOYMENT`, `AZURE_AI_MODEL_ROUTER_DEPLOYMENT`, agent-specific overrides) with a fallback to `gpt-4.1-mini`. See `.env.example` for the full list.

### 3. Authenticate to Azure

All agents use `DefaultAzureCredential`, which picks up your Azure CLI session automatically. Run this once per working session (tokens last roughly one hour):

```powershell
az login
az account show     # verify you're logged into the correct subscription
```

If you have multiple Azure subscriptions, set the active one:

```powershell
az account set --subscription "<subscription-id-or-name>"
```

### 4. Verify the setup

Run the loader smoke test (no API calls; validates the pre-built scenarios):

```powershell
python -m src.scenario_loader
```

Expected: three `OK` lines for the pre-built scenarios.

Then run the Scenario Generator end-to-end (one Azure API call, ~40-60 seconds):

```powershell
python -m src.agents.scenario_generator
```

Expected: streamed scenario JSON, ending with an `OK` summary line. If you see `DefaultAzureCredential failed to retrieve a token`, your Azure CLI session has expired. Re-run `az login` and try again.

### 5. Available agent smoke tests

Each agent module ships with a CLI smoke test runnable as `python -m <module>`. These are operational verification scripts with streaming output, intended for runbook checks where you want to see the agent's actual response build live:

| Command | What it tests |
|---|---|
| `python -m src.scenario_loader` | Pre-built scenario validation (no API calls) |
| `python -m src.agents.scenario_generator` | End-to-end scenario generation from a sample breach |
| `python -m src.agents.suspect_agent` | One interrogation turn against Casey Doyle |
| `python -m src.agents.forensic_analyst` | One Forensic Analyst consultation on the default scenario |
| `python -m src.agents.compliance_officer` | Compliance Officer closing speech for a correct accusation against Riley Park |
| `python -m src.orchestrator` | Full interactive REPL game loop. Type `help` once inside for commands |

### 6. Automated test suite

The automated tests live under `tests/` and follow the standard pytest convention: unit tests for fast offline logic checks, integration tests for live Azure calls.

```
tests/
├── conftest.py                  # shared fixtures (loaded scenarios)
├── unit/                        # fast tests, no external dependencies
│   ├── test_scenario_loader.py
│   ├── test_suspect_template.py
│   └── test_compliance_officer_message.py
└── integration/                 # live Azure tests, opt-in
    └── test_agents.py           # smoke + parameterized stress
```

Default `pytest` runs only the unit suite (offline, instant). Integration tests are opt-in:

```powershell
pytest                                          # unit tests only (default)
pytest -m integration                           # full integration battery (~10-15 min, ~20 live calls)
pytest -m integration -k stress                 # just the stress subset
pytest tests/integration/test_agents.py::TestBasicSmoke -m integration
                                                # one quick call per agent (~1-2 min)
```

The pytest markers are defined in `pytest.ini`. `integration` is the marker for any test requiring live Azure access; the default `pytest` invocation deselects it.

### 7. Running the game

The primary player-facing surface is the **Chainlit UI**. The CLI orchestrator is preserved as a fallback for live-demo recovery and for headless smoke testing.

```powershell
# Chainlit UI (primary, recommended for demos)
chainlit run app.py -w

# In a second terminal, tail the live activity log
.\scripts\tail_activity.ps1 -Clear

# CLI orchestrator (fallback / scripted runs)
python -m src.orchestrator                              # default: Helix Dynamics breach
python -m src.orchestrator --scenario helix_dynamics_supplychain
python -m src.orchestrator --scenario helix_dynamics_vishing
```

Inside the CLI REPL, type `help` for the command list. A typical CLI demo session looks like:

```
> look                          # hear the case premise
> suspects                      # see who's available
> ask casey_doyle Where were you Sunday night?
> forensic Walk me through the access logs around the breach window
> generate A vendor's compromised credentials were used to access patient records on Sunday night.
> look                          # hear the new generated case
> ask jordan_smith ...          # interrogate in the new scenario
> accuse riley_park             # triggers the Compliance Officer
> quit
```

## A note on data

Everything in this project is synthetic. Helix Dynamics is fictional. Employees, policies, scenarios, and Work IQ signals are fabricated for the purpose of demonstrating the architecture. No real customer information, no PII, no copyrighted material. The synthetic data conventions follow the Microsoft Reactor starter kit guidance.

## Event details

- **Battle:** Reasoning Agents Live Streaming Battle (Agents League Post Build, Battle #2)
- **Date and time:** June 10, 2026, 12:00 PM EST (9:00 AM PT)
- **Platform:** Microsoft Reactor YouTube channel via Streamyard


## License

MIT (see `LICENSE`).
