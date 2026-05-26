# Helix Dynamics Vendor Risk Management Policy

**Document ID:** HD-SEC-VR-001
**Version:** 3.1
**Effective Date:** 2025-01-10
**Document Owner:** General Counsel
**Approver:** Chief Operating Officer
**Review Cycle:** Annual

## 1. Purpose

This policy establishes the requirements for assessing, contracting with, and ongoing monitoring of third-party vendors who access Helix Dynamics systems, data, or facilities. It is designed to ensure that vendor relationships do not introduce unacceptable risk to confidential information, clinical trial data, or regulated operations.

## 2. Scope

This policy applies to all Helix Dynamics third-party vendors, contractors, and consultants. It governs vendor selection, contracting, ongoing monitoring, and offboarding. The Vendor Risk Register is maintained in the ServiceNow GRC module and is the system of record for all vendor risk classifications.

## 3. Vendor Tiering

Vendors are classified into three tiers based on risk exposure:

- **Tier 1 (High):** vendors with access to clinical trial data, manufacturing documentation, regulatory submissions, financial systems, vendor master data, or identity infrastructure. All contract research organizations (CROs) and contract manufacturing organizations (CMOs) are Tier 1
- **Tier 2 (Medium):** vendors with access to internal business systems but not to Tier 1 data, including HR consultants, marketing agencies with access to Microsoft 365, and non-clinical SaaS providers
- **Tier 3 (Low):** vendors with no logical access to Helix Dynamics systems or data

Tiering is determined by the Compliance team during onboarding and reviewed at contract renewal. The tier determines which controls in this policy apply.

## 4. Vendor Onboarding

Onboarding follows the workflow below, tracked in ServiceNow with a `VENDOR-ONBOARD` ticket category:

1. Business sponsor submits an onboarding request with documented business need
2. Procurement validates the request against the Dynamics 365 vendor master and assigns a vendor ID
3. Compliance assigns the proposed tier and routes for security review if Tier 1 or Tier 2
4. Security review completes the security questionnaire process (see Section 6)
5. Legal negotiates contract terms, including the security clauses required by Section 5
6. The vendor is activated in Dynamics 365 Sales and Dynamics 365 Finance and Operations
7. If logical access is required, accounts are provisioned per HD-SEC-AC-001

No vendor may be granted logical access to a Tier 1 system until all steps are complete and the ServiceNow ticket is in the `APPROVED` state.

## 5. Required Contract Security Clauses

All Tier 1 and Tier 2 vendor contracts must include the following provisions:

- **Confidentiality:** the vendor agrees to maintain the confidentiality of Helix Dynamics data using controls no less protective than those Helix Dynamics applies to its own data
- **Security requirements:** the vendor maintains controls appropriate to the data accessed, including encryption in transit and at rest, multi-factor authentication for personnel accessing Helix Dynamics systems, and documented access management
- **Subcontractor restrictions:** the vendor does not subcontract access to Helix Dynamics data without prior written approval
- **Right to audit:** Helix Dynamics or its designated auditor may review the vendor's security controls upon reasonable notice
- **Breach notification:** the vendor notifies Helix Dynamics within 24 hours of confirming a security incident affecting Helix Dynamics data
- **Data return or destruction:** at contract termination, the vendor returns or destroys all Helix Dynamics data and provides written attestation
- **Compliance with applicable laws:** the vendor complies with HIPAA, GDPR, and other applicable laws when handling Helix Dynamics data

Deviations from these clauses require General Counsel approval and are documented in the ServiceNow GRC vendor record.

## 6. Vendor Security Questionnaire

Tier 1 vendors complete a comprehensive security questionnaire before contract signing. The questionnaire covers:

- Governance and risk management
- Access control and authentication practices
- Encryption and key management
- Vulnerability management and patching cadence
- Incident response procedures
- Subcontractor management
- Compliance attestations (SOC 2, ISO 27001, HIPAA if applicable)

Vendors with current SOC 2 Type II reports may submit the report in lieu of completing the questionnaire sections covered by the report. Tier 2 vendors complete an abbreviated questionnaire. Tier 3 vendors are exempt.

Completed questionnaires are stored in the ServiceNow GRC vendor record. Findings are scored on a 1-5 scale; vendors scoring 3 or below require remediation commitments before contracting.

## 7. Ongoing Monitoring

Tier 1 vendors are reassessed annually. The reassessment includes:

- Refreshed security questionnaire or current SOC 2 report
- Review of any security incidents involving the vendor during the year
- Verification that vendor accounts in Helix Dynamics systems remain appropriate
- Confirmation that vendor MFA is configured as required by HD-SEC-AC-001 §5

Tier 2 vendors are reassessed every two years.

Material vendor changes (acquisition, change in subcontractors, security incident affecting the vendor) trigger an out-of-cycle reassessment.

## 8. Vendor Offboarding

When a vendor relationship ends, the following must occur within 24 hours of the contract end date documented in Dynamics 365 Sales:

- All vendor accounts in Tier 1 systems are deactivated
- Vendor MFA tokens are invalidated
- Vendor user accounts are disabled in Microsoft Entra ID
- The vendor is moved to `INACTIVE` status in the Dynamics 365 vendor master

Confirmation of return or destruction of Helix Dynamics data is collected within 30 days and stored in the ServiceNow ticket.

## 9. Related Documents

- HD-SEC-AC-001 Access Control Policy
- HD-SEC-IR-001 Incident Response Policy
- HD-SEC-DC-001 Data Classification Policy

## 10. Document History

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 2021-06-01 | General Counsel | Initial policy |
| 2.0 | 2023-02-15 | General Counsel | Tiering model added |
| 3.0 | 2024-08-01 | General Counsel | Aligned with SOC 2 CC9.2 |
| 3.1 | 2025-01-10 | General Counsel | Updated to reference Dynamics 365 and ServiceNow GRC |

---

*This is a synthetic policy document created for the Compliance Academy training scenarios. Helix Dynamics is fictional. The structure and clauses reflect common patterns in corporate vendor risk policies. No content is reproduced from real company policies or copyrighted material.*
