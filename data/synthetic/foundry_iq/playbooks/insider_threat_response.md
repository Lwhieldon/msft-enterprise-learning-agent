# Insider Threat Response Playbook

**Document ID:** HD-IR-PB-002
**Version:** 1.4
**Effective Date:** 2024-10-15
**Document Owner:** Director of Information Security
**Aligned to:** HD-SEC-IR-001

## 1. Purpose and Scope

This playbook provides the response procedure for incidents in which a current or former Helix Dynamics employee, contractor, or vendor representative is suspected of intentionally or recklessly misusing access to systems or data. Insider threats include theft of intellectual property, unauthorized data exfiltration, sabotage, fraud, and policy violations conducted with intent.

Insider threat response is distinct from credential compromise response in two important ways: the human subject of the investigation has legitimate access, and the investigation often requires HR and Legal involvement before any technical action. Mishandled insider investigations create employment law exposure.

## 2. Detection Triggers

This playbook is initiated when any of the following are observed:

- DLP alerts indicating bulk download or transmission of Confidential or Restricted data inconsistent with job function
- Anomalous after-hours access to Tier 1 systems by a user without documented business need
- Repeated DLP exceptions requested by the same user for data they do not normally handle
- Access to systems or records the user has no role-based need to view
- Resignation or termination context combined with elevated activity in the preceding 30 days
- Manager report of behavioral indicators (expressed grievances, financial distress, unauthorized side work)
- Tip received through the anonymous reporting channel
- Vendor report of unusual offer to acquire confidential information

## 3. Initial Response

### 3.1 Activate the Insider Threat Working Group

Insider threat investigations are conducted by a designated Insider Threat Working Group, not by the standard Security Operations team. The working group includes:

- Director of Information Security (technical lead)
- General Counsel (legal lead)
- HR Director (employment lead)
- Director of Compliance (process lead)

The working group is convened by the Director of Information Security within 24 hours of trigger confirmation. The investigation is tracked in a restricted-access ServiceNow ticket categorized as `IR-INSIDER`.

### 3.2 Preserve and Observe (Do Not Alert the Subject)

Unlike credential compromise response, the initial actions in an insider investigation **do not** include containment or remediation that would alert the subject. The first steps are:

1. Preserve forensic evidence quietly: snapshot the user's mailbox, OneDrive, Microsoft 365 audit logs, Microsoft Entra ID sign-in logs, and Tier 1 system access logs
2. Place a litigation hold on the user's data through Microsoft Purview eDiscovery
3. Coordinate with HR to determine whether the subject is currently active, on notice, in a termination process, or already separated
4. Coordinate with Legal to determine whether outside counsel should be engaged

Any change visible to the subject (account disabled, MFA reset, conversation with the user) is deferred until the working group authorizes it.

### 3.3 Assess Scope

The working group reviews:

- Scope of the user's legitimate access
- Activity patterns in the 90 days preceding the trigger
- Any DLP, audit, or anomaly data linking the user to the trigger event
- Whether intellectual property, clinical trial data, financial records, or vendor master data are implicated
- Whether the activity appears to be theft (data leaves Helix), sabotage (Helix systems are altered or destroyed), or other (policy violation without exfiltration)

## 4. Investigation

### 4.1 Coordinate with HR and Legal

Before any technical action that would alert the subject, the working group must obtain:

- HR sign-off on the employment status of the subject and any active disciplinary processes
- Legal sign-off on the investigative approach, including whether to engage outside counsel and whether to involve law enforcement
- General Counsel approval if the investigation will involve review of the subject's email or personal effects under company policy

### 4.2 Investigation Methods

Permissible investigation methods include:

- Review of business records (system access logs, badge access records, DLP alerts, ServiceNow tickets)
- Review of company-provided device contents per the Acceptable Use Policy
- Interviews with the subject's manager and colleagues, conducted by HR
- Forensic imaging of company-issued devices when authorized
- Review of email and document activity through Microsoft Purview eDiscovery

Investigation methods that are not permitted without specific legal authorization include:

- Reading content of personal communications on personal devices
- Physical surveillance outside Helix Dynamics facilities
- Pretexting to obtain information from the subject
- Reviewing union representation materials or protected concerted activity

### 4.3 Document Findings

All findings are documented in the restricted ServiceNow ticket. Documentation is written with the assumption that it may be reviewed in litigation. Speculation is clearly distinguished from observation. Conclusions are tied to specific evidence.

## 5. Decision and Action

The working group reaches one of the following dispositions:

| Disposition | Description | Next Steps |
|---|---|---|
| Substantiated, material harm | Evidence supports intentional misuse with material harm | Coordinate termination; pursue civil action; notify law enforcement if appropriate; recover or preserve data |
| Substantiated, limited harm | Evidence supports policy violation without material harm | Disciplinary action per HR; targeted retraining; access review |
| Unsubstantiated, follow-up warranted | Insufficient evidence but pattern suggests monitoring | Continued passive monitoring; manager coaching |
| Unfounded | Trigger was a false positive | Close ticket; review detection rule for tuning |

For substantiated cases, technical containment (account disabled, sessions revoked, devices returned) is coordinated with HR to occur at the moment of termination notification or shortly after.

## 6. Post-Incident Actions

Within 14 days of incident closure:

- Post-incident review per HD-SEC-IR-001 §6.4, conducted with the Insider Threat Working Group
- Update detection rules based on observed patterns
- Update training content if employees were unaware of restrictions they violated
- Review access patterns of other employees in the same role for similar indicators

## 7. Special Considerations

### 7.1 Departing Employees

The 30 days preceding a resignation or termination notification are the highest-risk window for data exfiltration. When an employee with access to Tier 1 systems gives notice, the following automatic measures are enabled:

- Enhanced DLP monitoring on the user's accounts
- Review of large downloads or email transmissions
- Review of personal device backup attempts
- Inventory of company-issued devices

These measures are documented in ServiceNow but are not disclosed to the departing employee. They are routine for Tier 1 access holders.

### 7.2 Whistleblowers

Behavior that initially appears to be insider misconduct may, on investigation, prove to be protected whistleblower activity. Whistleblower protections under Sarbanes-Oxley, the Dodd-Frank Act, and applicable state laws apply. The working group's investigation must not retaliate or appear to retaliate against protected activity. If whistleblower concerns surface during investigation, General Counsel is notified immediately and the matter is reassessed.

## 8. Related Documents

- HD-SEC-IR-001 Incident Response Policy
- HD-SEC-AC-001 Access Control Policy
- HD-SEC-DC-001 Data Classification Policy
- HD-IR-PB-001 Credential Compromise Response Playbook
- HD-HR-AUP-001 Acceptable Use Policy

---

*This is a synthetic playbook created for the Compliance Academy training scenarios. Helix Dynamics is fictional.*
