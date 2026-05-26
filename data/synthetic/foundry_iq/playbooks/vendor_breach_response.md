# Vendor Breach Response Playbook

**Document ID:** HD-IR-PB-003
**Version:** 2.0
**Effective Date:** 2025-01-15
**Document Owner:** Director of Information Security, with General Counsel
**Aligned to:** HD-SEC-IR-001, HD-SEC-VR-001

## 1. Purpose and Scope

This playbook provides the response procedure for security incidents originating at, or significantly affecting, a third-party vendor that processes, stores, or transmits Helix Dynamics data. This includes incidents reported by the vendor and incidents detected by Helix Dynamics involving vendor activity.

Vendor breach response differs from internal incident response because Helix Dynamics has limited direct access to the affected systems. The response depends heavily on vendor cooperation and on the strength of the contractual rights established under HD-SEC-VR-001 §5.

## 2. Detection Triggers

This playbook is initiated when any of the following occurs:

- A vendor notifies Helix Dynamics of a security incident affecting Helix data (required within 24 hours under HD-SEC-VR-001 §5)
- A vendor notifies Helix Dynamics of a security incident not yet known to affect Helix data, but where Helix data is potentially in scope
- Helix Dynamics detects anomalous activity from a vendor account in Tier 1 systems
- A vendor's parent organization is publicly disclosed as having experienced a breach
- A vendor's named subcontractor is publicly disclosed as having experienced a breach
- Threat intelligence indicates a vendor in the Helix Dynamics vendor inventory has been targeted

## 3. Initial Response (0 to 4 hours)

### 3.1 Create Ticket and Notify

The Helix Dynamics employee receiving the vendor notification creates a ServiceNow SecOps ticket categorized as `IR-VENDOR` within 4 hours of receipt. The ticket includes:

- Vendor name and Dynamics 365 vendor ID
- Tier classification (1, 2, or 3)
- Vendor's stated incident description
- Vendor's stated scope of Helix Dynamics data potentially affected
- Vendor's stated timeline of discovery and response actions to date
- Vendor's incident response point of contact
- Any vendor-provided incident reference number

The ticket auto-pages the on-call Incident Commander if the vendor is Tier 1.

### 3.2 Triage Severity

Severity is assigned based on the data scope:

- **SEV-1** if Restricted data (clinical trial data, regulatory submissions in progress, financial records) is potentially in scope
- **SEV-2** if Confidential data is potentially in scope
- **SEV-3** if Internal data is potentially in scope and no Confidential or Restricted data is suspected
- **SEV-4** otherwise, subject to review as more information becomes available

Severity may be re-classified as the investigation proceeds.

### 3.3 Initial Containment

If a vendor account exists in Helix Dynamics systems, the initial containment options are:

1. Suspend the vendor account in Microsoft Entra ID pending investigation
2. Apply Conditional Access restrictions limiting the account's permitted operations
3. Snapshot logs from any Tier 1 system the vendor accessed in the 90 days prior
4. If integration uses service principals or app registrations, rotate the associated secrets

The decision to suspend the vendor account is made by the Incident Commander in consultation with the business sponsor. Suspending vendor access may have operational impact (clinical trial milestones, manufacturing batch records, financial close); the impact is documented before action.

## 4. Vendor Coordination

### 4.1 Engagement

The Helix Dynamics business sponsor or Procurement contact engages the vendor's incident response point of contact. Initial questions include:

- What systems and data are affected?
- What is the vendor's stated cause and timeline?
- Has the vendor engaged forensic counsel or a third-party investigator?
- What containment actions has the vendor taken?
- What is the vendor's notification plan to its other customers?
- What evidence can the vendor share, and on what timeline?
- Does the vendor's incident affect any of its subcontractors who hold Helix Dynamics data?

All vendor communications are logged in the ServiceNow ticket. Calls are summarized in writing and confirmed back to the vendor.

### 4.2 Right to Audit

Per HD-SEC-VR-001 §5, Helix Dynamics has the right to audit vendor security controls on reasonable notice. For SEV-1 incidents, Legal may exercise this right and engage external forensic counsel. The vendor's cooperation is documented; non-cooperation is a material consideration in the post-incident vendor relationship decision.

### 4.3 Subcontractor and Fourth-Party Risk

If the vendor identifies a subcontractor as the source of the breach, the response expands to the subcontractor relationship. The vendor remains the primary point of contact and bears primary responsibility under the contract. Helix Dynamics tracks the subcontractor relationship in the ServiceNow GRC vendor record.

## 5. Helix Dynamics Internal Investigation

### 5.1 Determine Data Scope

The investigation determines what Helix Dynamics data was actually exposed:

- Review of data sent to or stored at the vendor (referenced in the original contract scope of work)
- Microsoft Purview audit logs of file shares or transmissions to the vendor
- ServiceNow tickets documenting vendor access requests in the prior 12 months
- Dynamics 365 records for invoices, deliverables, or other artifacts indicating data exchange

For SEV-1 incidents, the investigation engages the data steward for each Tier 1 system the vendor accessed.

### 5.2 Regulatory and Contractual Notification

General Counsel evaluates Helix Dynamics' obligations:

- HIPAA breach notification if ePHI is in scope (see HIPAA framework reference)
- State data breach notification laws if personal information is in scope
- FDA notification if clinical trial data integrity is affected
- Contractual notification to Helix Dynamics customers and partners
- IRB notification if clinical trial subject information is affected

Notification timelines are tracked against statutory clocks (typically 60 days from discovery for HIPAA, varying by state for state laws). Discovery is generally defined as the date Helix Dynamics knew, or by exercising reasonable diligence should have known, of the breach.

### 5.3 Stakeholder Briefing

For SEV-1 vendor incidents:

- Briefing to the CEO, CFO, COO, CMO, General Counsel within 24 hours
- Briefing to the Audit and Risk Committee of the Board within 7 days
- Communications plan developed jointly by General Counsel and Communications lead

## 6. Recovery and Closure

Vendor incident closure requires:

- Vendor has provided a written post-incident summary acceptable to the Incident Commander
- Helix Dynamics has documented its assessment of the vendor's response adequacy
- All required notifications have been completed
- Vendor relationship decision has been documented (continue, continue with enhanced controls, sunset, terminate)
- Lessons learned have been integrated into vendor risk processes

## 7. Vendor Relationship Decisions

After incident closure, the Vendor Risk Review Committee evaluates the vendor relationship using a documented framework:

- Was the breach the result of vendor negligence or of an unavoidable threat?
- How well did the vendor respond?
- What is the cost of replacing the vendor relative to the cost of continued risk?
- What additional controls can mitigate residual risk?

The committee's recommendation goes to the General Counsel and the business sponsor for decision. Decisions are documented in the ServiceNow GRC vendor record and feed into the next contract renewal cycle.

## 8. Post-Incident Actions

Within 14 days of incident closure:

- Post-incident review per HD-SEC-IR-001 §6.4
- Update of the Vendor Risk Register for the affected vendor and for similar vendors
- Review of vendor inventory for other vendors with similar risk profiles
- Update to vendor onboarding security questionnaire if a new control gap was identified
- Update to vendor monitoring detection rules

## 9. Related Documents

- HD-SEC-IR-001 Incident Response Policy
- HD-SEC-VR-001 Vendor Risk Management Policy
- HD-SEC-DC-001 Data Classification Policy
- HD-IR-PB-001 Credential Compromise Response Playbook
- HD-IR-PB-002 Insider Threat Response Playbook

---

*This is a synthetic playbook created for the Compliance Academy training scenarios. Helix Dynamics is fictional.*
