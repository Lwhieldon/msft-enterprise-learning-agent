# ISO/IEC 27001:2022 Annex A Reference (Synthetic)

This document provides a synthetic reference summary of selected controls from ISO/IEC 27001:2022 Annex A as applied in the Compliance Academy training scenarios. The 2022 revision restructured Annex A from 114 controls in 14 sections to 93 controls in 4 themes. This document references the 2022 control numbering. Content is paraphrased in original prose and does not reproduce ISO publications.

## Overview

ISO/IEC 27001 is the international standard for information security management systems (ISMS). It specifies requirements for establishing, implementing, maintaining, and continually improving an ISMS. Certification is performed by accredited certification bodies and is widely recognized globally.

Annex A of ISO 27001 lists a reference set of information security controls organized into four themes:

- **A.5 Organizational controls** (37 controls)
- **A.6 People controls** (8 controls)
- **A.7 Physical controls** (14 controls)
- **A.8 Technological controls** (34 controls)

Helix Dynamics is pursuing ISO 27001 certification in the next fiscal year and has mapped its existing SOC 2 control set against Annex A to identify gaps.

## Selected Annex A Controls

### A.5 Organizational Controls

**A.5.15 Access control.** Rules to control physical and logical access to information and other associated assets are established and implemented based on business and information security requirements.

**A.5.16 Identity management.** The full lifecycle of identities is managed, including establishment, modification, and removal.

**A.5.17 Authentication information.** Allocation and management of authentication information is controlled by a management process, including advising personnel on the appropriate handling of authentication information.

**A.5.18 Access rights.** Access rights to information and other associated assets are provisioned, reviewed, modified, and removed in accordance with the topic-specific access control policy.

**A.5.19 Information security in supplier relationships.** Processes and procedures are defined to manage the information security risks associated with the use of supplier products or services.

**A.5.20 Addressing information security within supplier agreements.** Relevant information security requirements are established and agreed with each supplier based on the type of supplier relationship.

**A.5.23 Information security for use of cloud services.** Processes for acquisition, use, management, and exit from cloud services are established in accordance with the organization's information security requirements.

**A.5.24 Information security incident management planning and preparation.** The organization plans and prepares for managing information security incidents by defining, establishing, communicating, and assigning information security incident management roles and responsibilities.

**A.5.25 Assessment and decision on information security events.** The organization assesses information security events and decides whether they are to be categorized as information security incidents.

**A.5.26 Response to information security incidents.** Information security incidents are responded to in accordance with documented procedures.

### A.6 People Controls

**A.6.3 Information security awareness, education and training.** Personnel and relevant interested parties receive appropriate information security awareness, education, and training and regular updates on the organization's information security policy.

### A.8 Technological Controls

**A.8.2 Privileged access rights.** The allocation and use of privileged access rights are restricted and managed.

**A.8.5 Secure authentication.** Secure authentication technologies and procedures are implemented based on information access restrictions and the topic-specific access control policy.

**A.8.12 Data leakage prevention.** Data leakage prevention measures are applied to systems, networks, and any other devices that process, store, or transmit sensitive information.

**A.8.15 Logging.** Logs that record activities, exceptions, faults, and other relevant events are produced, stored, protected, and analyzed.

**A.8.16 Monitoring activities.** Networks, systems, and applications are monitored for anomalous behavior and appropriate actions are taken to evaluate potential information security incidents.

## Mapping: Helix Dynamics Controls to ISO 27001 Annex A

| Helix Dynamics Control | Policy Reference | ISO 27001:2022 Annex A |
|---|---|---|
| Access control policy | HD-SEC-AC-001 | A.5.15 |
| Identity lifecycle via Dynamics 365 HR | HD-SEC-AC-001 §3 | A.5.16 |
| MFA on Tier 1 systems | HD-SEC-AC-001 §4.1 | A.5.17, A.8.5 |
| Privileged access management | HD-SEC-AC-001 §4.2 | A.8.2 |
| Quarterly access reviews | HD-SEC-AC-001 §6 | A.5.18 |
| Vendor security clauses | HD-SEC-VR-001 §5 | A.5.20 |
| Vendor risk management | HD-SEC-VR-001 | A.5.19 |
| Incident response framework | HD-SEC-IR-001 | A.5.24, A.5.26 |
| Event assessment in ServiceNow SecOps | HD-SEC-IR-001 §6.1 | A.5.25 |
| DLP policies | HD-SEC-DC-001 §7 | A.8.12 |
| SIEM logging and review | HD-SEC-IR-001 §6.1 | A.8.15, A.8.16 |
| Annual security awareness training | (training program) | A.6.3 |

## Certification Path

Helix Dynamics' ISO 27001 certification scope will cover the Cambridge research operations and the Devens manufacturing facility. The certification engagement is planned in three phases:

1. **Stage 1 audit:** documentation review of the Information Security Management System
2. **Stage 2 audit:** on-site or remote assessment of implementation effectiveness
3. **Surveillance audits:** annual reviews to maintain certification

Gap remediation activities identified in the readiness assessment are tracked in the ServiceNow GRC module under the `ISO27001-PREP` project.

## A Note on This Document

This is a synthetic reference summary created for the Compliance Academy training scenarios. The structure and concepts reflect publicly known patterns of ISO/IEC 27001:2022. No content is reproduced from ISO publications. For authoritative reference, consult the ISO/IEC 27001:2022 standard directly.
