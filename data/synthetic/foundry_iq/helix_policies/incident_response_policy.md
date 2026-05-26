# Helix Dynamics Incident Response Policy

**Document ID:** HD-SEC-IR-001
**Version:** 3.4
**Effective Date:** 2025-02-01
**Document Owner:** Director of Information Security
**Approver:** General Counsel
**Review Cycle:** Annual

## 1. Purpose

This policy establishes the framework for identifying, responding to, and learning from information security incidents. It defines roles, responsibilities, severity levels, notification timelines, and post-incident activities. The objective is to limit the impact of security events and to meet regulatory and contractual notification obligations.

## 2. Scope

This policy applies to all information security incidents involving Helix Dynamics systems, data, employees, or vendors. Incidents are tracked in the ServiceNow Security Incident Response (SecOps) module, which is the system of record for incident lifecycle and post-incident records.

## 3. Definitions

- **Event:** an observed occurrence in a system or network
- **Incident:** an event that has been confirmed to violate or imminently threaten security policy, acceptable use policy, or standard security practices
- **Breach:** an incident resulting in confirmed unauthorized disclosure of Confidential or Restricted information as defined in HD-SEC-DC-001

## 4. Incident Severity Levels

| Severity | Definition | Examples |
|---|---|---|
| **SEV-1 (Critical)** | Confirmed or strongly suspected breach of Restricted data, or compromise affecting Tier 1 system availability | Exfiltration of clinical trial data; ransomware encrypting HelixVault; compromise of privileged Entra ID accounts |
| **SEV-2 (High)** | Confirmed compromise of Confidential data, significant unauthorized access, or compromise of a Tier 2 system | Compromised user credentials with access to HelixVault; vendor breach with potential Helix data exposure; persistent unauthorized access |
| **SEV-3 (Medium)** | Suspicious activity requiring investigation, or confirmed minor policy violations | Phishing attempt with link clicks but no credential entry; isolated DLP alert; misconfigured access not yet exploited |
| **SEV-4 (Low)** | Confirmed minor events with limited impact | Single-user phishing attempt with no engagement; routine policy violations resolved at the user level |

Severity is assigned at incident declaration and may be re-classified as investigation proceeds.

## 5. Incident Response Team

The Incident Response Team (IRT) is convened for SEV-1 and SEV-2 incidents. Standing members include:

- Director of Information Security (Incident Commander)
- IT Director (technical lead)
- General Counsel (legal lead)
- Chief Medical Officer (for incidents involving clinical trial data)
- HR Director (for incidents involving employees)
- Director of Compliance (for incidents with regulatory implications)
- Communications lead (for incidents with external disclosure)

For SEV-3 and SEV-4 incidents, the Security Operations team handles response without convening the full IRT.

## 6. Response Phases

### 6.1 Detection and Triage

Detection sources include the SIEM, DLP alerts, Microsoft Defender alerts, vendor notifications, and user reports. The Security Operations team reviews and validates each alert within the following targets:

- Critical-priority alerts: 15 minutes from generation
- High-priority alerts: 1 hour from generation
- Medium-priority alerts: 4 hours from generation

When an event is escalated to an incident, a ServiceNow SecOps ticket is created and assigned a severity level. A SEV-1 or SEV-2 ticket automatically pages the on-call Incident Commander.

### 6.2 Containment

Initial containment goals depend on severity but generally include:

- Isolating affected systems from the network
- Revoking compromised credentials and invalidating sessions
- Capturing forensic evidence before remediation
- Coordinating with vendors if vendor systems are involved

Forensic preservation is mandatory for SEV-1 incidents and follows the chain-of-custody procedures documented in the Forensic Preservation Procedure.

### 6.3 Eradication and Recovery

Eradication actions include removing malware, closing exploited vulnerabilities, and rebuilding compromised systems. Recovery requires explicit sign-off from the Incident Commander that the threat is contained, evidence has been preserved, and remediation has been verified.

### 6.4 Post-Incident Review

For SEV-1 and SEV-2 incidents, a post-incident review is conducted within 14 days of incident closure. The review documents:

- Incident timeline
- Detection effectiveness
- Response effectiveness
- Root cause analysis
- Corrective and preventive actions
- Lessons learned

Post-incident reports are reviewed by the IRT and submitted to the Audit and Risk Committee of the Board.

## 7. Notification Requirements

### 7.1 Internal Notification

| Severity | Notify | Within |
|---|---|---|
| SEV-1 | CEO, CFO, COO, CMO, General Counsel, Board Chair | 4 hours |
| SEV-2 | CFO, COO, General Counsel | 24 hours |
| SEV-3, SEV-4 | Department head as applicable | Per ticket |

### 7.2 External Notification

External notifications are coordinated by General Counsel based on the nature of the incident and applicable law:

- Affected individuals: per HIPAA, Massachusetts 201 CMR 17.00, and other applicable laws
- HHS Office for Civil Rights: per HIPAA Breach Notification Rule
- State Attorneys General: per state breach notification laws
- FDA: if the incident affects regulated data integrity
- IRB: if the incident affects clinical trial subject information
- Business partners and customers: per contractual obligations
- Law enforcement: where appropriate and authorized by General Counsel

Notification templates are maintained in HelixVault under `IR/Templates/`.

## 8. Vendor Incidents

When a vendor notifies Helix Dynamics of a security incident affecting Helix data, the receiving party (typically the Procurement contact or the vendor's Helix Dynamics sponsor) creates a ServiceNow SecOps ticket within 4 hours of receipt. Vendor incidents are subject to the same response process as internal incidents, with additional coordination requirements outlined in the Vendor Breach Response Playbook.

## 9. Training and Exercises

The IRT conducts at least one tabletop exercise per year. Tabletop scenarios rotate across attack vectors including credential compromise, vendor breach, ransomware, and insider threat. Lessons learned from exercises are documented in ServiceNow.

## 10. Related Documents

- HD-SEC-AC-001 Access Control Policy
- HD-SEC-VR-001 Vendor Risk Management Policy
- HD-SEC-DC-001 Data Classification Policy
- HD-IR-PB-001 Credential Compromise Response Playbook
- HD-IR-PB-002 Insider Threat Response Playbook
- HD-IR-PB-003 Vendor Breach Response Playbook

## 11. Document History

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 2020-08-01 | Director of IS | Initial policy |
| 2.0 | 2022-05-15 | Director of IS | Severity model revised |
| 3.0 | 2024-02-01 | Director of IS | ServiceNow SecOps integration |
| 3.1 | 2024-05-15 | Director of IS | Vendor notification timelines |
| 3.2 | 2024-09-01 | Director of IS | Added Board Chair to SEV-1 notification |
| 3.3 | 2024-12-01 | Director of IS | Annual review |
| 3.4 | 2025-02-01 | Director of IS | Forensic preservation requirements clarified |

---

*This is a synthetic policy document created for the Compliance Academy training scenarios. Helix Dynamics is fictional. No content is reproduced from real company policies or copyrighted material.*
