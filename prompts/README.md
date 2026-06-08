# Compliance Academy Prompts

System prompts for every agent in Compliance Academy. Each file is the prompt that gets loaded as the agent's system message at instantiation time. Prompts are markdown for readability; agent runtime code loads each file as a plain string.

## Directory

```
prompts/
├── README.md                          (this file)
├── game_master.md                     orchestrator, narrator, dice arbiter, state owner
├── party/
│   ├── forensic_analyst.md            digital forensics, anomaly detection (loudest reasoner)
│   ├── it_specialist.md               [LEGACY] network and access control mechanics
│   ├── hr_liaison.md                  [LEGACY] rapport, behavioral cues, ethics
│   ├── compliance_auditor.md          [LEGACY] framework citations, control mapping
│   └── whistleblower_contact.md       [LEGACY] rival archetype, unreliable ally
├── suspects/
│   └── _template.md                   reusable NPC template (instantiated per scenario)
├── scenario_generator.md              live-twist case builder
└── compliance_officer.md              post-scene educator
```

The **current Chainlit UI** (`app.py`) wires five prompts:

- `game_master.md`
- `party/forensic_analyst.md`
- `compliance_officer.md`
- `scenario_generator.md`
- `suspects/_template.md` (instantiated five times per scenario)

The four `[LEGACY]` files in `party/` were written during the initial design to support a richer five-agent investigator party (IT Specialist, HR Liaison, Compliance Auditor, Whistleblower Contact). They are kept in the repo as design reference, but the current build does not load them. The Compliance Auditor's role was folded into the Compliance Officer for a tighter live-demo surface.

## How They Get Used

Each prompt is loaded as the system message for its corresponding agent in the Foundry Agent Service Connected Agents configuration. The Game Master is the primary agent. The others are declared as connected agents and invoked by the Game Master via tool calls.

The suspect template is special: it is loaded once and then **instantiated per suspect** by substituting the `{{ ... }}` variables with values from the scenario configuration JSON (`data/synthetic/scenarios/*.json`). This lets us spin up five different suspects from one template without writing five separate prompts.

## Design Principles

**Medium-tight.** Persona, voice rules, structural rules, and safety rules are locked. Specific phrasings are left to the model. Each agent has a distinct voice. Agents push back on each other when the evidence demands it.

**Microsoft-aligned.** All system references use the canonical fictional stack: HelixVault, PatientChain, LabConnect, Dynamics 365 (ERP and HR), Dynamics 365 Sales, ServiceNow, Microsoft 365 with Entra ID. No mentions of competing products. This keeps the demo grounded for the Microsoft Reactor audience.

**Stream-friendly.** Agents are instructed to produce text that reads well on a live stream: brief turns, specific citations (HD-SEC-AC-001 §3.3 rather than "the access control policy"), visible reasoning chains. Length caps are enforced by the prompts.

**Grounded by default.** Agents that have Azure AI Search retrieval available are instructed to use it for citations rather than improvising framework content. If retrieval fails, they acknowledge the gap.

**Safe by default.** Each prompt includes explicit guardrails for the YouTube broadcast context: no real PII, no real-person names, no graphic content, no real-world attack recipes. Synthetic-only fiction.

## Editing

You can edit prompts directly. Reload the agent runtime to pick up changes. For iterative tuning, edit, reload, run a sample scene, observe model behavior, repeat.

## Validation Strategy

Before locking the remaining prompts, the three anchors (Game Master, Forensic Analyst, Suspect template) should be validated against real model outputs:

1. Run a sample interrogation scene against `compliance-academy-router` with the Helix Dynamics default scenario
2. Watch for: voice consistency, citation accuracy, length discipline, character drift
3. Adjust the anchor prompts as needed
4. Once anchors are stable, write the remaining 8 prompts following the same patterns

## Safety Note

All scenarios, employees, policies, frameworks, and breach descriptions referenced in these prompts are synthetic. Helix Dynamics is fictional. The framework citations follow real framework structure (SOC 2, NIST 800-53, ISO 27001, HIPAA) but the specific clauses cited inside the Helix Dynamics policies are original paraphrasings. No copyrighted material is reproduced.
