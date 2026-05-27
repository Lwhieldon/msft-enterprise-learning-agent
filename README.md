# Compliance Academy

A multi-agent role-play game for corporate compliance training, built for the Microsoft Reactor Agents League Post Build edition (Reasoning Agents Live Streaming Battle, June 10, 2026).

Compliance Academy delivers cybersecurity and compliance education through a playable breach investigation. The human player works alongside a party of five AI investigator agents to solve a corporate data breach. The reasoning is visible, the consequences are real, and the gameplay teaches enterprise compliance concepts that traditional training fails to deliver.

## What's in here

| Path | Purpose |
|---|---|
| `docs/concept.md` | The premise, agent cast, Microsoft IQ integration, scoring map |
| `docs/architecture.md` | Agent specifications, Model Router setup, game mechanics, synthetic data |
| `docs/live_battle_runbook.md` | Stream-day cheat sheet, four-slot demo flow, fallback plans |
| `2-reasoning-agents/` | The Microsoft Reactor starter kit (reference materials, do not modify) |
| `src/` | Application code (to be added) |
| `data/synthetic/` | Synthetic policies, employees, scenarios (to be added) |

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

Setup instructions will be added as the codebase comes online. The current focus is the docs and synthetic data.

## A note on data

Everything in this project is synthetic. Helix Dynamics is fictional. Employees, policies, scenarios, and Work IQ signals are fabricated for the purpose of demonstrating the architecture. No real customer information, no PII, no copyrighted material. The synthetic data conventions follow the Microsoft Reactor starter kit guidance.

## Event details

- **Battle:** Reasoning Agents Live Streaming Battle (Agents League Post Build, Battle #2)
- **Date and time:** June 10, 2026, 12:00 PM EST (9:00 AM PT)
- **Platform:** Microsoft Reactor YouTube channel via Streamyard


## License

MIT (see `LICENSE`).
