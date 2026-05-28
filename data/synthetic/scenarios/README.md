# Compliance Academy Scenarios

This directory contains synthetic breach scenarios that the Game Master loads to populate game state, suspect personas, evidence inventory, and compliance lesson. Scenarios are split into shared baseline content and per-scenario override files.

## Architecture

```
data/synthetic/scenarios/
├── _shared/
│   └── scenario_commons.json          # baseline content loaded with every scenario
├── helix_dynamics_default.json        # overrides for SCN-001 (default demo)
├── helix_dynamics_supplychain.json    # overrides for SCN-002 (supply chain)
└── helix_dynamics_vishing.json        # overrides for SCN-003 (vishing)
```

The scenario loader reads `_shared/scenario_commons.json` first, then reads the active scenario file, then merges the two into a single fully-populated scenario object that the Game Master and the suspect agents consume.

### What lives in `_shared/scenario_commons.json`

- `synthetic_disclosure_boilerplate` — the standard disclosure paragraph
- `canonical_microsoft_systems` — the full Microsoft stack pool that scenarios pick from
- `helix_dynamics_company_profile` — fixed facts about Helix (headcount, locations, audit posture)
- `suspect_base_personas` — for each of the five canonical suspects (Alex Chen, Morgan Webb, Riley Park, Casey Doyle, Jordan Smith): `name`, `role_family`, `tenure_at_helix`, `backstory_core`, `conversational_style_core`, `voice_examples_core`
- `merge_semantics` — authoritative documentation of how the loader merges base + override

### What lives in each scenario file

Scenario-specific fields only. No duplication of baseline content. Each scenario file contains:

- `_extends` — pointer to the shared file (informational; loader uses this for sanity-checking)
- `scenario_id`, `scenario_name`
- `scenario_specific_disclosure` — optional clauses appended to the boilerplate
- `premise_narration` — what the Game Master narrates at Act 1 opening
- `attack_pattern_category`
- `violated_controls` — framework + Helix policy citations
- `involved_systems` — subset of `canonical_microsoft_systems`
- `suspects` — array of five override objects (see below)
- `evidence_seeds` — array of evidence items with `supports_suspect` and `appears_to_support_suspect` fields
- `clue_graph` — nodes and edges
- `compliance_lesson` — the Compliance Officer's full post-scene segment

### Suspect override schema

Each suspect entry in a scenario file contains only the fields that change per scenario:

- `suspect_id` — key matching an entry in `suspect_base_personas` (required)
- `specific_role` — specific role for this scenario (required, e.g., "IT Administrator (Lab Informatics Lead)")
- `scenario_context` — one or two sentences appended to `backstory_core` (required)
- `starting_trust` — 0.0 to 1.0 (required)
- `alibi`, `open_knowledge`, `guarded_knowledge`, `hidden_truth` — required strings
- `scenario_style_note` — optional, appended to `conversational_style_core`
- `scenario_voice_examples` — optional array, concatenated with `voice_examples_core`
- `leak_conditions` — array of strings (required)
- `is_perpetrator`, `is_red_herring` — booleans (required)

## Merge Semantics

Authoritative version is in `_shared/scenario_commons.json` under the `merge_semantics` key. Summary:

| Field | Resolution |
|---|---|
| `synthetic_disclosure` | `boilerplate` + `" "` + `scenario_specific_disclosure` (if present) |
| `suspect.name` | from base.name (always) |
| `suspect.role` | from scenario.specific_role |
| `suspect.backstory` | `base.backstory_core` + `" "` + `scenario.scenario_context` |
| `suspect.conversational_style` | `base.conversational_style_core` + (`" "` + `scenario.scenario_style_note` if present) |
| `suspect.voice_examples` | `base.voice_examples_core` concatenated with `scenario.scenario_voice_examples` (defaults to empty) |
| `suspect.alibi`, `open_knowledge`, `guarded_knowledge`, `hidden_truth` | from scenario (required) |
| `suspect.starting_trust`, `is_perpetrator`, `is_red_herring` | from scenario (required) |
| `suspect.leak_conditions` | from scenario (required) |

Reference loader (Python sketch):

```python
def load_scenario(scenario_path: str) -> dict:
    commons = json.load(open("data/synthetic/scenarios/_shared/scenario_commons.json"))
    scenario = json.load(open(scenario_path))

    disclosure = commons["synthetic_disclosure_boilerplate"]
    if scenario.get("scenario_specific_disclosure"):
        disclosure = disclosure + " " + scenario["scenario_specific_disclosure"]

    suspects = []
    for s in scenario["suspects"]:
        base = commons["suspect_base_personas"][s["suspect_id"]]
        merged = {
            "suspect_id": s["suspect_id"],
            "name": base["name"],
            "role": s["specific_role"],
            "starting_trust": s["starting_trust"],
            "backstory": base["backstory_core"] + " " + s["scenario_context"],
            "conversational_style": (
                base["conversational_style_core"]
                + ((" " + s["scenario_style_note"]) if s.get("scenario_style_note") else "")
            ),
            "voice_examples": (
                base["voice_examples_core"]
                + s.get("scenario_voice_examples", [])
            ),
            "alibi": s["alibi"],
            "open_knowledge": s["open_knowledge"],
            "guarded_knowledge": s["guarded_knowledge"],
            "hidden_truth": s["hidden_truth"],
            "leak_conditions": s["leak_conditions"],
            "is_perpetrator": s["is_perpetrator"],
            "is_red_herring": s["is_red_herring"],
        }
        suspects.append(merged)

    return {
        "scenario_id": scenario["scenario_id"],
        "scenario_name": scenario["scenario_name"],
        "synthetic_disclosure": disclosure,
        "premise_narration": scenario["premise_narration"],
        "attack_pattern_category": scenario["attack_pattern_category"],
        "violated_controls": scenario["violated_controls"],
        "involved_systems": scenario["involved_systems"],
        "suspects": suspects,
        "evidence_seeds": scenario["evidence_seeds"],
        "clue_graph": scenario["clue_graph"],
        "compliance_lesson": scenario["compliance_lesson"],
    }
```

## Files

| File | Scenario | Attack Pattern | Proximate Perpetrator | Use Case |
|---|---|---|---|---|
| `helix_dynamics_default.json` | Breach at Helix Dynamics | Vendor breach + credential phishing | Riley Park (vendor) | Default for live demo; balanced mix of technical and interpersonal evidence |
| `helix_dynamics_supplychain.json` | The LabConnect Update | Supply chain (compromised third-party software update) | Morgan Webb (IT) | Backup #1; emphasizes technical evidence (signature verification, hash comparison) |
| `helix_dynamics_vishing.json` | Help Desk at 2 AM | Social engineering (vishing the help desk) | Jordan Smith (intern on help desk rotation) | Backup #2; emphasizes interpersonal evidence (call recordings, training gaps) |

## Cast Continuity

All three scenarios use the same five canonical suspects (Alex Chen, Morgan Webb, Riley Park, Casey Doyle, Jordan Smith) with the same role families. This is intentional. The audience does not have to re-learn names mid-stream if the host swaps scenarios. What changes between scenarios is each suspect's specific role and scenario context, their alibis, their hidden truths, and which one is the proximate perpetrator.

The variance in perpetrator across scenarios (vendor, IT, intern) is also deliberate. The player cannot pattern-match "the vendor always did it." Each scenario tests a different framework lesson and a different control archetype.

The shared/overrides architecture enforces this continuity at the schema level. If Alex's baseline voice changes, it changes in one place and all three scenarios pick it up.

## Hot-Loading

The Game Master loads a scenario at game start. The default is `helix_dynamics_default.json`. During live play, the Scenario Generator agent can produce a new scenario at runtime from a host-supplied breach description; the generated scenario emits only the override-format suspect fields and is hot-loaded through the same merge pipeline.

The two backup scenarios in this directory are pre-built fallbacks for live battle day in case the Scenario Generator fails or produces an unusable output under pressure. The host can request a backup by name and the Game Master will load it directly.

## Validation

Each scenario JSON should:

1. Validate as JSON (no syntax errors)
2. Reference five `suspect_id` values, each matching a key in `_shared/scenario_commons.json.suspect_base_personas`
3. Have exactly one suspect with `is_perpetrator: true`
4. Have one or two suspects with `is_red_herring: true`
5. Have at least two violated controls cited (one framework, one Helix Dynamics policy)
6. Reference only systems present in `canonical_microsoft_systems` for the `involved_systems` array
7. Pass the loader's merge without missing-field errors

A future `scripts/validate_scenario.py` utility will run these checks automatically. For now, they are enforced by author discipline.

## Synthetic Disclosure

All scenarios, suspects, vendors, and breach details are synthetic. Helix Dynamics is fictional. Framework citations reference real frameworks (SOC 2, NIST 800-53, ISO 27001, HIPAA) using paraphrased clause text in synthetic Helix Dynamics policies. No real persons, real companies, or real breach victims are referenced. Attack patterns are inspired by real-world breach archetypes but do not reproduce specifics from any actual incident.
