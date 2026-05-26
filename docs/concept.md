# Breach at Helix Dynamics: Concept

## The Premise

It's 7:14 AM on a Monday. Overnight, Helix Dynamics (a fictional mid-market biotech specializing in early-stage oncology) lost 14GB of clinical trial data to an unauthorized exfiltration. The Board has called for an internal investigation. The human player is the lead investigator on Day 1, with one shift to figure out what happened, who is responsible, and what control failed.

The player does not investigate alone. A party of five AI investigator agents joins each session, each with a distinct specialty and personality. Five Helix Dynamics employees are the suspects. Their stories conflict. The truth is reconstructable, but the picture only forms when the party's specialties combine.

The case is the assessment. The investigation is the gameplay. The reasoning is what the live battle audience watches happen on screen.

## Why This Framing

This solution targets the Reasoning Agents Live Streaming Battle (Battle 2 of the Agents League Post Build edition). It is intentionally designed as a multi-agent role-play game, satisfying the live battle challenge requirements while reframing the genre.

Most competitors will build fantasy RPGs because the starter kit emphasizes that. The same kit explicitly permits "another character archetype," which opens the door to a corporate compliance investigation. That genre choice maps cleanly onto every required mechanic: party-based exploration, character agents with distinct skills, dice-based skill checks, world state, in-character dialogue, and meaningful consequences.

The corporate setting also creates a real-world enterprise narrative that fantasy doesn't: compliance training is a major enterprise spend category, and gamification is how the more progressive organizations are starting to make training effective.

## The Player Experience

Each session of Compliance Academy plays out as a four-act investigation.

**Act 1, Briefing.** The Game Master narrates the breach. Foundry IQ surfaces relevant policy context (Helix Dynamics access controls, vendor management procedures, applicable framework controls). The investigator party introduces themselves in character. The player picks an opening direction.

**Act 2, Interrogation rounds.** The player questions suspects, one at a time. Party members assist: the Forensic Analyst spots inconsistencies in technical statements, the HR Liaison reads emotional cues, the Compliance Auditor flags policy violations a suspect didn't realize they admitted. Skill checks are rolled when the player attempts something risky (intimidating a senior exec, demanding records without a warrant).

**Act 3, Evidence reconciliation.** The party gathers in the war room. Each member presents what they noticed. The Forensic Analyst reasons aloud about whose story conflicts with the timestamps. The player commits to an accusation.

**Act 4, Debrief.** The Compliance Officer agent surfaces the real-world lesson the scenario was teaching, cited by framework and control number. If the player accused correctly, the session closes with a readiness assessment. If not, the system loops back for another scenario.

## Agent Cast

### Game Master (orchestrator, narrator, world builder)

Single point of orchestration. Routes player input to the right party member or suspect. Tracks shared state (active scene, evidence inventory, suspect trust levels, party morale). Adjudicates dice rolls. Decides when to advance the act. Implemented as a Foundry Connected Agent with the other agents declared as connected specialists.

Reasoning model. Routing mode: Quality.

### The Investigator Party (five character agents)

Each member is the player's companion. They speak in character, contribute specialty knowledge, can request rolls within their domain, and react to story events based on their backstory.

- **Forensic Analyst.** Analytical, slightly arrogant, takes detail seriously. Specialty: digital forensics, log analysis, anomaly detection. Grounded in Foundry IQ for technical references. Often the loudest reasoning agent in the room (intentional, the audience watches her think).
- **IT Specialist.** Direct, protective, suspicious of vendors. Specialty: network architecture, access control mechanics, MFA configurations. Defends the IT department's reputation but will not lie about what the logs say.
- **HR Liaison.** Compassionate, observant, ethically careful. Specialty: employee relations, termination procedures, interpersonal dynamics. Steers the party away from harsh interrogation tactics. Watches for emotional manipulation by suspects.
- **Compliance Auditor.** Skeptical, opportunistic, knows where the policy gaps live. Specialty: SOC2, ISO 27001, HIPAA (biotech-relevant), vendor risk frameworks. Often calls out which violated control matters before anyone else notices.
- **Whistleblower Contact.** Charismatic, proud, unpredictable. A recurring character who knows more than they say. May help, mislead, or compete with the player depending on prior decisions. Forces the player to reason through trust and motive. Plays the live battle starter kit's "Rival" archetype.

### Scenario Generator (the live-battle showcase)

A reasoning agent that ingests a real-world breach description (provided by hosts or audience during the live stream) and produces a complete new case in JSON: synthetic suspect personas, alibi structures, hidden truths, clue graph, mapped compliance lesson. The output hot-loads into game state. The audience watches the AI write the whodunit, then watches the player play it.

Reasoning model. Routing mode: Quality.

### Suspect Agents (NPCs, spawned per scenario)

For the default Helix Dynamics scenario, five suspects: HR Director, IT Admin, Vendor Rep, Executive Assistant, Intern. Each implemented as a single Suspect class instantiated with a persona configuration (backstory, alibi, hidden truth, conversational style, leak conditions). Suspects respond to interrogation in character, with hidden state that shifts under pressure. A well-placed skill check reveals what they would not voluntarily disclose.

Persona model. Routing mode: Cost (persona consistency matters more than reasoning depth for these turns).

### Compliance Officer (post-scene educator)

Surfaces the real-world cybersecurity or compliance lesson the scenario was teaching. Cites the violated control by framework and section. Grounded in Foundry IQ.

Standard model. Routing mode: Balanced.

## Microsoft Foundry IQ Integration

All three IQs plug in as different kinds of intelligence the party draws on. This is the multi-IQ integration the starter kit calls out as a high-value extra.

**Foundry IQ as the case file knowledge base.** Synthetic policy documents, compliance framework references (SOC2 Trust Service Criteria, NIST 800-53 controls, ISO 27001 Annex A, HIPAA Security Rule for biotech context), Helix Dynamics' internal security policies, and incident response playbooks. The Forensic Analyst, Compliance Auditor, and Compliance Officer query Foundry IQ during interrogations and debrief. Citations surface in the UI so the audience sees grounded answers.

**Work IQ as employee work signals turned into evidence.** Synthetic data only. Each Helix Dynamics employee has a Work IQ-style profile: meeting hours per week, focus hours per week, typical collaboration partners, after-hours activity patterns, recent access to sensitive systems. These signals become investigative evidence. "Why was Casey logged into the document server at 3:14 AM when their typical activity ends at 6 PM?" The party reasons over Work IQ-style anomalies to identify clues.

**Fabric IQ as the semantic investigation model.** A synthetic ontology connecting employees, roles, access levels, systems, policies, and breach vectors. The Forensic Analyst walks this knowledge graph during reasoning: the access pattern looks like Pattern X, which in the ontology maps to vendor-side credential reuse, which violates control AC-2.4. The post-scene readiness view expresses gaps in semantic terms.

## Model Router Integration

Every agent calls a single Foundry Model Router endpoint, which selects the right underlying model per request based on each agent's configured routing mode. Quality mode for the reasoning-heavy agents (Game Master, Forensic Analyst, Compliance Auditor, Scenario Generator). Cost mode for the persona-heavy agents (Suspects, Whistleblower Contact). Balanced for the supporting agents.

The pitch on stream: one endpoint, multiple intelligences, transparent failover. Enterprise customers get cost optimization without rewriting agents.

The Foundry resource (`<your-unique-foundry-name>`) should be in East US 2 or Sweden Central, the two Model Router-supported regions.

## What Makes This Distinctive

Three things, in priority order.

The audience watches the AI write a brand new compliance scenario in real time when hosts throw a surprise breach, then watches the player play that newly written scenario. Two distinct AI capabilities (generative case design plus multi-agent role-play) in a single demo.

The reasoning agents reason about each other. The Forensic Analyst pushes back on the IT Specialist's defense of the network team. The Whistleblower Contact tries to mislead the party, and the Compliance Auditor catches the lie. The audience sees real inter-agent debate, not just turn-taking.

The corporate framing addresses a real enterprise problem. Compliance training is one of the most universally hated parts of working at a regulated company, and most existing solutions are genuinely terrible. The pitch lands with hiring managers, CISOs, and L&D leaders in a way that fantasy RPGs cannot.

## Live Battle Scoring Map

| Criterion | Weight | How Compliance Academy targets it |
|---|---|---|
| Accuracy & Relevance | 25% | Multi-agent system aligned to the role-play scenario, produces in-character outputs grounded in IQ-retrieved compliance content |
| Reasoning & Multi-step Thinking | 25% | Game Master decomposes player intent, party debates evidence, Scenario Generator reasons end-to-end through a new breach |
| Creativity & Originality | 15% | Corporate compliance whodunit reframing of the role-play genre, three-IQ integration |
| User Experience & Presentation | 15% | Chainlit UI streams reasoning chains live, character avatars and colors, audience can vote in chat |
| Reliability & Safety | 20% | Synthetic data only, Model Router automatic failover, scenario validation, content filters on suspect dialogue |

## Synthetic Data Discipline

All data is fabricated. No real customer information, no real employee information, no PII. Identifier conventions: employees `EMP-001` through `EMP-NNN`, scenarios `SCN-001` through `SCN-NNN`. Helix Dynamics is fictional. Suspects have fabricated names that do not correspond to real people. Policy documents are synthetic but reflect real framework structure.
