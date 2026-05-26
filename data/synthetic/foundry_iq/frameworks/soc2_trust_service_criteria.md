# SOC 2 Trust Service Criteria (Synthetic Reference)

This document provides a synthetic reference summary of the SOC 2 trust service criteria as they are commonly applied in enterprise compliance programs. It is created for the Compliance Academy training scenarios and does not reproduce content from the AICPA's Trust Services Criteria document. Specific control language has been rewritten in original prose.

For authoritative source material, refer to the AICPA's published Trust Services Criteria.

## Overview of SOC 2

SOC 2 is an attestation framework administered by the American Institute of Certified Public Accountants (AICPA) for service organizations that handle customer or partner data. A SOC 2 report is issued by an independent licensed CPA firm after evaluating an organization's controls against the trust service criteria.

There are two types of SOC 2 reports:

- **Type I:** Evaluates whether controls are suitably designed at a point in time
- **Type II:** Evaluates whether controls operated effectively over a period of observation, typically 6 to 12 months

SOC 2 is an attestation rather than a certification. The report describes the auditor's opinion on the design and operating effectiveness of controls. There is no SOC 2 "pass" or "fail," but there is a clean opinion versus a qualified opinion.

## Trust Service Criteria Categories

SOC 2 evaluates controls across five trust service criteria categories. Service organizations select the categories relevant to their service offering. Most organizations include Security at minimum. The five categories are:

1. **Security** (also referred to as the Common Criteria): always included
2. **Availability:** included when uptime is a customer commitment
3. **Confidentiality:** included when the service handles confidential information
4. **Processing Integrity:** included when the service processes transactions
5. **Privacy:** included when the service collects, uses, or discloses personal information

Helix Dynamics has elected to include Security, Availability, and Confidentiality in the scope of its SOC 2 reporting.

## Common Criteria (Security): Selected Controls

The Common Criteria are organized into nine categories (CC1 through CC9). The following selections are most relevant to the Compliance Academy investigation scenarios.

### CC6.1 - Logical and Physical Access Controls

The organization implements logical access security software, infrastructure, and architectures over the resources that are protected from security events. This includes controls over the granting and revoking of access, authentication mechanisms appropriate to the sensitivity of the resource, and protection of authentication credentials.

Common evidence requested by auditors:

- Access provisioning and termination workflows
- Multi-factor authentication coverage
- Privileged access reviews
- Authentication logs for sensitive systems

### CC6.6 - Boundary Protection

The organization implements logical access controls at the boundaries of the system to protect against unauthorized access from external parties. This includes network segmentation, firewall rules, and controls on remote access mechanisms.

Common evidence requested by auditors:

- Firewall configuration and change records
- VPN access logs and authentication patterns
- Network segmentation documentation
- Vulnerability scan results for boundary devices

### CC6.7 - Information in Transit

The organization restricts the transmission, movement, and removal of information to authorized internal and external parties using protected methods. This includes encryption of data in transit and controls on data exfiltration.

Common evidence requested by auditors:

- Encryption configuration for data transmission
- Data loss prevention (DLP) policies and alerts
- Egress filtering rules
- Records of approved exceptions

### CC7.2 - System Monitoring

The organization monitors system components and the operation of those components for anomalies that are indicative of malicious acts, natural disasters, or errors affecting the entity's ability to meet its objectives. Anomalies are analyzed to determine if they represent security events.

Common evidence requested by auditors:

- Security information and event management (SIEM) configuration
- Alert routing and triage procedures
- Sample incident records with documented response
- Mean time to detect and mean time to respond metrics

### CC9.2 - Vendor and Business Partner Risk Management

The organization assesses the risks associated with vendors and business partners on an ongoing basis. This includes risk-based vendor selection, contractual obligations addressing security and confidentiality, and periodic re-assessment of vendor risk.

Common evidence requested by auditors:

- Vendor inventory with risk classification
- Vendor due diligence documentation (security questionnaires, SOC 2 reports of vendors)
- Vendor contracts containing required security clauses
- Records of periodic vendor re-assessment

## Availability Criteria: Selected Controls

### A1.2 - Environmental Controls and Backup

The organization implements environmental protections and data backup procedures to meet its availability commitments. This includes protections against environmental threats (fire, flood, power loss) and tested procedures for data backup and restoration.

## Confidentiality Criteria: Selected Controls

### C1.1 - Identification and Confidentiality of Information

The organization identifies and classifies confidential information so that confidentiality controls can be applied consistently. Classification typically distinguishes between public, internal, confidential, and restricted information.

### C1.2 - Disposal of Confidential Information

The organization disposes of confidential information using procedures that prevent unauthorized access during and after disposal. This includes secure deletion of digital information and destruction of physical media.

## Mapping: Helix Dynamics Internal Controls to SOC 2 Criteria

The following table illustrates how selected Helix Dynamics internal controls map to SOC 2 criteria. This mapping is referenced in scenario debriefs to surface the framework relevance of in-game decisions.

| Helix Dynamics Control | Policy Reference | SOC 2 Criterion |
|---|---|---|
| MFA on all Tier 1 systems | HD-SEC-AC-001 §4.1 | CC6.1 |
| Account termination within four hours | HD-SEC-AC-001 §3.3 | CC6.1 |
| Privileged session recording | HD-SEC-AC-001 §4.2 | CC6.1 |
| Vendor contract security clauses | HD-SEC-VR-001 §5 | CC9.2 |
| Vendor security questionnaire | HD-SEC-VR-001 §6 | CC9.2 |
| Quarterly access reviews | HD-SEC-AC-001 §6 | CC6.1 |
| DLP rules on clinical trial data | HD-SEC-DC-001 §7 | CC6.7 |
| Incident response playbook | HD-SEC-IR-001 | CC7.2 |

## A Note on This Document

This is a synthetic reference summary created for the Compliance Academy training scenarios. The structure and concepts reflect publicly known patterns of the SOC 2 framework. No content is reproduced from the AICPA's Trust Services Criteria document or any other copyrighted source. For authoritative reference, consult the AICPA's published materials.
