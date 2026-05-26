# Helix Dynamics Data Classification Policy

**Document ID:** HD-SEC-DC-001
**Version:** 2.3
**Effective Date:** 2024-11-01
**Document Owner:** Director of Information Security
**Approver:** Chief Financial Officer
**Review Cycle:** Annual

## 1. Purpose

This policy establishes the framework for classifying Helix Dynamics information by sensitivity and defines the handling requirements for each classification level. Consistent classification enables the application of appropriate technical and procedural controls.

## 2. Scope

This policy applies to all Helix Dynamics information, regardless of format (electronic or physical) or location (on-premises, cloud, vendor environments). It applies to all employees, contractors, and authorized third parties.

## 3. Classification Levels

Helix Dynamics information is classified into four levels:

### 3.1 Public

Information that is approved for external release and whose disclosure presents no risk to the company. Examples include published research, marketing materials, press releases, and the public company website.

### 3.2 Internal

Information intended for use by Helix Dynamics employees and contractors but not approved for external release. Disclosure would cause minor harm. Examples include internal policies, organizational charts, training materials, and internal product documentation.

### 3.3 Confidential

Information whose disclosure would cause material harm to Helix Dynamics, its employees, partners, or research subjects. Examples include financial records, HR records, vendor contracts, non-public research data, and pre-publication scientific findings.

### 3.4 Restricted

Information whose disclosure would cause severe harm and may trigger regulatory or legal consequences. Examples include clinical trial patient data, regulatory submissions in progress, intellectual property filings, board-level financial information, and credentials or cryptographic keys.

## 4. Default Classification

Information that has not been explicitly classified defaults to Internal. Data stewards may elevate classification based on content. Data in clinical trial management systems (PatientChain), regulatory submissions (HelixVault), and the financial ledger (Dynamics 365 Finance and Operations) defaults to Restricted unless explicitly downgraded by the relevant data steward.

## 5. Labeling

Confidential and Restricted information must be labeled. Acceptable methods include:

- Microsoft Purview sensitivity labels for documents and email
- Watermarks on printed materials
- Folder-level inheritance in HelixVault for clinical trial documentation
- Header banners in PatientChain reports

Unlabeled information is treated as Internal until classified.

## 6. Handling Requirements

| Activity | Public | Internal | Confidential | Restricted |
|---|---|---|---|---|
| External transmission | Permitted | Approval required | Approval required, encrypted | Prohibited except through approved channels |
| Email | Permitted | Permitted (internal only) | Encrypted required | Restricted to approved DLP-cleared workflows |
| Cloud storage | Microsoft 365 | Microsoft 365 | Microsoft 365 with sensitivity labels | HelixVault or PatientChain only |
| Removable media | Permitted | Encrypted required | Encrypted, justification required | Prohibited |
| Printing | Permitted | Permitted | Approval required | Prohibited except for regulatory submissions |
| Retention | Per business need | 3 years default | 7 years default | Per regulatory requirement, minimum 25 years for clinical trial data |

## 7. Data Loss Prevention (DLP)

DLP policies are applied through Microsoft Purview and configured to enforce this policy:

- **DLP Rule R-001:** any document or email containing clinical trial subject identifiers, dosing data, or adverse event records is blocked from transmission to external recipients without an approved exception in ServiceNow
- **DLP Rule R-002:** any document or email containing financial records labeled Restricted is blocked from removable media transfer
- **DLP Rule R-003:** any document or email containing credentials, API keys, or cryptographic material is blocked and an alert is raised to the Security Operations team
- **DLP Rule R-004:** bulk transfer thresholds (more than 100 documents in 24 hours from a single user) trigger alerts even if individual documents are not classified as Restricted

DLP exceptions require approval from the Director of Information Security and are documented in the ServiceNow GRC module.

## 8. Storage Requirements

Restricted information must be stored only in approved systems:

- Clinical trial data: PatientChain or HelixVault
- Manufacturing records: HelixVault
- Regulatory submissions: HelixVault
- Financial records: Dynamics 365 Finance and Operations
- Personnel records: Dynamics 365 Human Resources
- Vendor contracts: Dynamics 365 Sales (metadata) and HelixVault (executed copies)

Storage of Restricted data outside these systems is prohibited and constitutes a policy violation.

## 9. Disposal

Confidential and Restricted information must be disposed of using approved methods:

- Electronic: secure deletion using the approved enterprise tooling, with confirmation logged in ServiceNow
- Physical: cross-cut shredding for paper, certified destruction for media
- Cloud: documented purge requests for cloud-hosted data, with vendor attestation

Disposal of Restricted information is logged and reviewed by Compliance annually.

## 10. Related Documents

- HD-SEC-AC-001 Access Control Policy
- HD-SEC-VR-001 Vendor Risk Management Policy
- HD-SEC-IR-001 Incident Response Policy

## 11. Document History

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 2022-04-01 | Director of IS | Initial policy |
| 2.0 | 2023-10-15 | Director of IS | Added Restricted tier |
| 2.1 | 2024-03-01 | Director of IS | DLP rule numbering |
| 2.2 | 2024-07-15 | Director of IS | Microsoft Purview integration |
| 2.3 | 2024-11-01 | Director of IS | Refined retention requirements for clinical trial data |

---

*This is a synthetic policy document created for the Compliance Academy training scenarios. Helix Dynamics is fictional. No content is reproduced from real company policies or copyrighted material.*
