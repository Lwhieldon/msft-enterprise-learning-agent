# Helix Dynamics Access Control Policy

**Document ID:** HD-SEC-AC-001
**Version:** 4.2
**Effective Date:** 2024-09-15
**Document Owner:** Director of Information Security
**Approver:** Chief Financial Officer
**Review Cycle:** Annual

## 1. Purpose

This policy establishes the requirements for granting, modifying, and revoking access to Helix Dynamics information systems and data. It is intended to ensure that access privileges are appropriate to each employee's role, consistent with the principle of least privilege, and subject to ongoing review.

## 2. Scope

This policy applies to all Helix Dynamics employees, contractors, consultants, and authorized third-party vendors who access company information systems. It covers all systems classified as Tier 1 (business-critical), including but not limited to HelixVault, PatientChain, LabConnect, Dynamics 365, Microsoft Entra ID, and any system that processes clinical trial data, manufacturing records, regulatory submissions, financial records, or vendor master data.

## 3. Account Lifecycle

### 3.1 Provisioning

New user accounts are provisioned through Dynamics 365 Human Resources (the HR information system within Finance and Operations) when an employee is onboarded. The hiring manager submits a role-based access request that defines the employee's primary system access profile. The Compliance team must approve any deviations from the role-based template.

Privileged accounts (Administrator, Data Steward, Auditor) require additional approval from the General Counsel and are documented in the Privileged Access Register.

### 3.2 Modification

Access changes are triggered by:

- Role changes documented in Dynamics 365 Human Resources
- Project assignments requiring temporary elevated access
- Manager-initiated requests through the ServiceNow IT service portal

All access modifications require documented justification. Temporary access expires automatically after the documented duration unless explicitly extended.

### 3.3 Termination

Account termination is triggered by the HR Director through Dynamics 365 Human Resources at the time of separation. The following must occur within four hours of the termination notification:

- All active sessions for the terminated user are revoked
- Multi-factor authentication tokens are invalidated
- Email forwarding rules are disabled
- Mobile device management tokens are revoked

The IT Administrator is responsible for executing the termination workflow and confirming completion in the ServiceNow ticket. Termination tickets are tagged with the `OFFBOARD` category for audit reporting.

## 4. Authentication

### 4.1 Multi-Factor Authentication (MFA)

MFA is required for all access to Tier 1 systems. The approved second factor is the company-managed authenticator application. SMS and email-based MFA are not approved.

Exceptions to MFA enforcement may be granted only for documented technical incompatibility and must be approved by the Director of Information Security. Active exceptions are documented in the MFA Exception Register and reviewed quarterly.

### 4.2 Privileged Access

Privileged accounts are subject to the following additional controls:

- Just-in-time access for privileged operations through the PAM system, requested via ServiceNow with documented business justification
- Session recording for all privileged sessions on Tier 1 systems
- Quarterly access certification by the data steward, tracked in the ServiceNow GRC module

## 5. Vendor Access

Vendors with access to Helix Dynamics systems are subject to all controls in this policy. Additionally:

- Vendor accounts must be sponsored by a Helix Dynamics manager
- Vendor access expires automatically on the contract end date documented in Dynamics 365 Sales
- Vendor access is restricted to the systems and data necessary for the contracted scope of work
- Vendor MFA configuration is reviewed at contract renewal

## 6. Access Reviews

The data steward for each Tier 1 system conducts a quarterly access review. The review documents:

- Each user with active access to the system
- The business justification for that access
- Any anomalies such as orphaned accounts, dormant accounts, or excessive privileges

The Compliance team consolidates the quarterly reviews and reports findings to the CFO.

## 7. Violations

Violations of this policy may result in disciplinary action up to and including termination of employment or contract. Violations are also reported to the Compliance team for assessment under the company's incident response procedures.

## 8. Related Documents

- HD-SEC-IR-001 Incident Response Policy
- HD-SEC-VR-001 Vendor Risk Management Policy
- HD-SEC-DC-001 Data Classification Policy
- HD-SEC-PAM-001 Privileged Access Management Procedure

## 9. Document History

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 2020-03-01 | Director of IS | Initial policy |
| 2.0 | 2021-09-15 | Director of IS | Added MFA requirements |
| 3.0 | 2023-04-01 | Director of IS | Vendor access controls added |
| 4.0 | 2024-01-15 | Director of IS | Annual review, integrated PAM |
| 4.1 | 2024-06-10 | Director of IS | Clarified termination workflow |
| 4.2 | 2024-09-15 | Director of IS | Updated MFA Exception process |

---

*This is a synthetic policy document created for the Compliance Academy training scenarios. Helix Dynamics is fictional. The structure and clauses reflect common patterns in corporate security policies for the purpose of demonstration. No content is reproduced from real company policies, vendor frameworks, or copyrighted material.*
