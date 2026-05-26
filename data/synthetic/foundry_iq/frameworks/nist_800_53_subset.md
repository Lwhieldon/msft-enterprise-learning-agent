# NIST 800-53 Control Subset (Synthetic Reference)

This document provides a synthetic reference summary of selected controls from NIST Special Publication 800-53 (Security and Privacy Controls for Information Systems and Organizations) as applied in the Compliance Academy training scenarios. It is paraphrased in original prose and does not reproduce content from the NIST publication. For authoritative reference, consult the NIST publication directly.

## Overview

NIST 800-53 is a comprehensive catalog of security and privacy controls maintained by the National Institute of Standards and Technology. It is the primary control catalog for U.S. federal information systems and is widely adopted by private-sector organizations as a reference framework. Controls are organized into families and selected through a tailoring process based on system categorization.

The current revision is Rev. 5. This document references Rev. 5 control identifiers.

## Selected Control Families

### AC (Access Control)

Access Control family covers how access to systems and data is granted, modified, and revoked.

**AC-2 Account Management.** The organization manages information system accounts, including establishing the conditions for membership, identifying authorized users, requiring approvals for account requests, monitoring account use, and notifying account managers of changes that may affect account validity.

**AC-2(4) Account Management: Automated Audit Actions.** The information system automatically audits account creation, modification, enabling, disabling, and removal actions and notifies designated personnel.

**AC-3 Access Enforcement.** The information system enforces approved authorizations for logical access to information and system resources in accordance with applicable access control policies.

**AC-6 Least Privilege.** The organization employs the principle of least privilege, allowing only authorized access for users that is necessary to accomplish assigned tasks in accordance with organizational missions and business functions.

**AC-6(9) Least Privilege: Auditing Use of Privileged Functions.** The information system audits the execution of privileged functions.

### AU (Audit and Accountability)

The Audit and Accountability family covers what events are logged, how logs are protected, and how they are reviewed.

**AU-2 Audit Events.** The organization determines which events the system is capable of logging in support of the audit function, coordinates audit event selection with related functions, and reviews and updates the list of audited events periodically.

**AU-6 Audit Review, Analysis, and Reporting.** The organization reviews and analyzes audit records for indications of inappropriate or unusual activity and reports findings to designated personnel.

**AU-12 Audit Generation.** The information system generates audit records for the events defined in AU-2 with the content defined in AU-3.

### IR (Incident Response)

The Incident Response family covers incident handling capabilities and procedures.

**IR-4 Incident Handling.** The organization implements an incident handling capability that includes preparation, detection and analysis, containment, eradication, and recovery, and coordinates with related contingency planning activities.

**IR-6 Incident Reporting.** The organization requires personnel to report suspected security incidents to the organizational incident response capability within a defined timeframe and reports incident information to designated authorities.

### SI (System and Information Integrity)

The System and Information Integrity family covers monitoring, malicious code protection, and information handling.

**SI-4 Information System Monitoring.** The organization monitors the information system to detect attacks and indicators of potential attacks, monitors unauthorized local and network connections, and identifies authorized use of the system.

### SC (System and Communications Protection)

**SC-7 Boundary Protection.** The information system monitors and controls communications at the external boundary of the system and at key internal boundaries within the system.

**SC-8 Transmission Confidentiality and Integrity.** The information system protects the confidentiality and integrity of transmitted information using approved cryptographic mechanisms.

## Mapping: Helix Dynamics Controls to NIST 800-53

| Helix Dynamics Control | Policy Reference | NIST 800-53 Control |
|---|---|---|
| Role-based provisioning through Dynamics 365 HR | HD-SEC-AC-001 §3.1 | AC-2 |
| Automated account audit through ServiceNow | HD-SEC-AC-001 §3.3 | AC-2(4) |
| MFA on Tier 1 systems | HD-SEC-AC-001 §4.1 | AC-3 |
| Just-in-time privileged access | HD-SEC-AC-001 §4.2 | AC-6, AC-6(9) |
| Quarterly access reviews | HD-SEC-AC-001 §6 | AC-2 |
| SIEM and DLP monitoring | HD-SEC-DC-001 §7 | SI-4, AU-6 |
| Incident response procedures | HD-SEC-IR-001 | IR-4 |
| Internal and external incident notification | HD-SEC-IR-001 §7 | IR-6 |
| Encryption in transit | HD-SEC-DC-001 §6 | SC-8 |
| Network boundary controls | (network policy) | SC-7 |

## Tailoring and Baselines

NIST 800-53 controls are typically applied through one of three baselines: Low, Moderate, or High, based on the system's potential impact under FIPS 199 categorization. Helix Dynamics applies Moderate baseline controls to most Tier 1 systems, with High baseline controls applied to systems holding clinical trial data (PatientChain, HelixVault).

Helix Dynamics tailoring decisions are documented in the System Security Plans maintained in HelixVault under `Security/SSP/`.

## A Note on This Document

This is a synthetic reference summary created for the Compliance Academy training scenarios. The structure and concepts reflect publicly known patterns of NIST 800-53. No content is reproduced from NIST publications. For authoritative reference, consult NIST Special Publication 800-53 Rev. 5 directly.
