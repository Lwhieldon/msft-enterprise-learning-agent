# Credential Compromise Response Playbook

**Document ID:** HD-IR-PB-001
**Version:** 2.2
**Effective Date:** 2025-01-20
**Document Owner:** Director of Information Security
**Aligned to:** HD-SEC-IR-001

## 1. Purpose and Scope

This playbook provides the response procedure for incidents involving suspected or confirmed compromise of user credentials. It applies to all credential types including standard user accounts, privileged accounts, service accounts, and vendor accounts.

The playbook is initiated by a ServiceNow SecOps ticket categorized as `IR-CREDENTIAL`.

## 2. Detection Triggers

This playbook is initiated when any of the following are observed:

- Failed authentication anomaly: more than 50 failed attempts against a single account in 1 hour, or distributed brute force patterns from Microsoft Entra ID sign-in logs
- Impossible travel: successful authentication from geographically inconsistent locations within a short time window
- Sign-in from unusual location, device, or IP relative to the user's baseline
- Disabled MFA notification followed by sign-in success
- Direct user report of suspected compromise (lost device, phishing engagement, observed credential entry on suspicious page)
- Vendor or external party notification that credentials may have been exposed
- DLP alert for download or export immediately following an anomalous sign-in

## 3. Initial Response (0 to 30 minutes)

### 3.1 Validate

The Security Operations analyst reviews:

- Microsoft Entra ID sign-in logs for the account
- Conditional Access policy decisions on recent sign-ins
- Microsoft Defender alerts for the account or affected device
- Recent ServiceNow tickets involving the account

If the alert is a true positive, escalate to SEV-2. If access to Restricted data is involved or confirmed, escalate to SEV-1 and page the Incident Commander.

### 3.2 Contain

Within 30 minutes of confirmation, execute the following containment steps in order:

1. Revoke all active sessions for the account in Microsoft Entra ID
2. Force password reset on next sign-in
3. Invalidate MFA tokens and require re-enrollment
4. If a device is suspected as the source, isolate it through Microsoft Defender for Endpoint
5. If the account is privileged, revoke privileged access in the PAM system and review the JIT request history
6. Document each action in the ServiceNow ticket with timestamp and operator

### 3.3 Preserve

Before remediating affected systems, capture forensic evidence:

- Microsoft Entra ID sign-in logs for the account, 30 days prior
- Microsoft Defender alerts for the account and any associated devices
- Audit logs from any Tier 1 system the account accessed in the 30 days prior
- ServiceNow ticket history for the account
- Email message trace records if phishing is suspected

Evidence is preserved per the Forensic Preservation Procedure.

## 4. Investigation (30 minutes to 24 hours)

### 4.1 Determine Scope

The investigation team determines:

- How was the credential compromised? (phishing, password reuse, malware, social engineering of the helpdesk)
- When did the compromise occur? (earliest unusual sign-in)
- What did the attacker access? (which Tier 1 systems, which data classifications)
- What did the attacker exfiltrate or modify? (DLP records, change history, document download logs)
- Are other accounts affected? (same device, same phishing campaign, same IP)

### 4.2 Coordinate with the IRT

For SEV-1 incidents, the Incident Commander convenes the IRT within 4 hours of confirmation. If Restricted data is involved, General Counsel determines notification obligations.

### 4.3 Vendor and Service Account Considerations

If the compromised account is a vendor account, notify the vendor's incident response contact within 4 hours. If the account is a service account, identify all dependent systems before invalidation to avoid cascading availability issues.

## 5. Recovery

Recovery requires Incident Commander sign-off that:

- The credential is invalidated and re-issued
- The root cause is identified and remediated (phishing campaign blocked, exposed system patched, helpdesk procedure updated)
- The user has completed any required re-training
- Forensic evidence is preserved
- Audit logs of unauthorized access have been reviewed

## 6. Post-Incident Actions

Within 14 days of incident closure:

- Post-incident review per HD-SEC-IR-001 §6.4
- Update detection rules in the SIEM if a novel pattern was observed
- Update the MFA Exception Register if exceptions contributed to the compromise
- Update the phishing simulation program if a phishing campaign was the vector

## 7. Common Patterns and Targeted Responses

| Pattern | Indicators | Targeted Response |
|---|---|---|
| Phishing for credentials | User reports clicking link; sign-in from unusual IP shortly after | Block sender; revoke sessions; phishing simulation refresh for affected user |
| Helpdesk social engineering | MFA reset ticket from impersonator; sign-in immediately after reset | Review and tighten helpdesk identity verification; sanction if helpdesk procedure was violated |
| Password reuse | Credential appears in known breach corpus; sign-in from unusual location | Force company-wide password reset for the affected service; review password manager adoption |
| Service account compromise | Anomalous activity from service account; access patterns inconsistent with documented purpose | Rotate service account credentials; review all dependent systems; consider managed identity migration |

## 8. Related Documents

- HD-SEC-IR-001 Incident Response Policy
- HD-SEC-AC-001 Access Control Policy
- HD-IR-PB-002 Insider Threat Response Playbook
- HD-IR-PB-003 Vendor Breach Response Playbook

---

*This is a synthetic playbook created for the Compliance Academy training scenarios. Helix Dynamics is fictional.*
