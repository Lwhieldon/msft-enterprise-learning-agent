# Helix Dynamics: Company Overview

## About Helix Dynamics

Helix Dynamics is a mid-market biotechnology company headquartered in Boston, Massachusetts, focused on early-stage oncology therapeutics. The company was founded in 2014 and operates as a privately held research and development organization with approximately 340 employees across two physical locations and a remote workforce.

This document is a synthetic profile created for the Compliance Academy training scenarios. All names, roles, and identifiers are fabricated.

## Lines of Business

Helix Dynamics develops small-molecule and antibody-based therapies targeting solid tumor indications. The company has three molecules in Phase I clinical trials and one molecule in Phase II as of the current scenario context. Research operations are headquartered in Cambridge, Massachusetts, with a secondary GMP manufacturing facility in Devens, Massachusetts.

Helix Dynamics holds approximately 14TB of structured and unstructured research data, including:

- Pre-clinical research datasets (compound libraries, assay results)
- Clinical trial data (patient outcomes, adverse event reports, dosing schedules)
- Manufacturing process documentation (batch records, quality control)
- Regulatory submissions (IND filings, IRB correspondence, FDA communications)
- Intellectual property documentation (patent filings, freedom-to-operate analyses)

Clinical trial data is the company's highest-value information asset. Loss or unauthorized disclosure of clinical trial data has material implications for regulatory standing, patent prosecution, and commercial partnerships.

## Organizational Structure

The company is led by a Chief Executive Officer reporting to a Board of Directors. Direct reports to the CEO include:

- Chief Operating Officer (manufacturing, supply chain, quality)
- Chief Scientific Officer (research, clinical operations)
- Chief Financial Officer (finance, IT, facilities)
- Chief Medical Officer (clinical strategy, regulatory affairs)
- General Counsel (legal, compliance, contracts)

The IT function reports up through the CFO. The IT team has six engineers including the IT Director and an IT Administrator. The IT Administrator role has elevated access to identity systems, network infrastructure, and the document management system.

The Human Resources function reports through the COO. The HR Director oversees a team of four. The Compliance function reports to General Counsel and is staffed by a Compliance Officer plus two analysts.

## Critical Systems

Helix Dynamics operates the following business-critical systems:

- **HelixVault** (internal document management system): primary repository for clinical trial documentation, research data, and regulatory submissions
- **LabConnect** (laboratory information management system): manages experimental data, sample tracking, and assay results
- **PatientChain** (clinical trial management system): tracks patient enrollment, dosing schedules, and adverse event reporting
- **Dynamics 365** (enterprise resource planning): system of record for accounting, finance, operations, vendor master data, and procurement workflows. Integrated with HelixVault for invoice-to-contract reconciliation
- **ServiceNow** (IT service management and GRC platform): system of record for all IT helpdesk tickets, access requests, change management, asset management, vendor risk workflows, and incident response tracking. Used by IT, Compliance, and HR for any workflow that requires an auditable ticket trail. The ServiceNow ITSM, SecOps, and GRC modules are licensed
- **Microsoft 365**: email, document collaboration, and identity through Microsoft Entra ID
- **Dynamics 365 Sales**: contact management, partner relationship tracking, and business development workflows. Integrated with Microsoft 365 for activity capture and with Dynamics 365 Finance and Operations for vendor and customer master data
- **Dynamics 365 Human Resources (within Finance and Operations)**: HR information system, employee lifecycle workflows, and personnel records. Payroll is processed through an integrated third-party service

Privileged access to HelixVault, PatientChain, and Dynamics 365 is restricted to staff with documented business need and explicit approval from the relevant data steward.

## Vendor Ecosystem

Helix Dynamics works with approximately 80 third-party vendors across categories including:

- Contract research organizations (CROs) running clinical trials
- Contract manufacturing organizations (CMOs) for early-stage drug substance and drug product
- SaaS providers for the systems listed above
- Specialty consultants for regulatory strategy, patent prosecution, and business development

Vendors with access to clinical trial data, manufacturing documentation, or regulatory submissions are classified as **Tier 1 vendors** and subject to enhanced security requirements outlined in the Vendor Management Policy.

## Regulatory Posture

Helix Dynamics is subject to the following regulatory frameworks:

- FDA 21 CFR Part 11 (electronic records and signatures)
- HIPAA (clinical trial data may contain protected health information)
- GxP guidelines (Good Clinical Practice, Good Manufacturing Practice)
- State data breach notification laws (Massachusetts 201 CMR 17.00 in particular)

Helix Dynamics has voluntarily adopted SOC 2 Type II as its primary attestation framework. The most recent SOC 2 report covers the trust service criteria for Security, Availability, and Confidentiality. ISO 27001 certification is targeted for the next fiscal year.

## Recent Security Investments

In the eighteen months preceding the current scenario context, Helix Dynamics has invested in:

- A privileged access management (PAM) solution
- Multi-factor authentication (MFA) for all employees and critical vendors
- A managed detection and response (MDR) service
- Quarterly security awareness training
- Annual penetration testing

The MFA rollout was completed eight months before the current scenario context. The investigation may surface whether all systems are actually within the MFA scope, or whether exceptions exist.

## A Note on This Document

This overview is synthetic content created for the Compliance Academy training scenarios. Helix Dynamics is fictional. Any resemblance to real biotechnology companies or their employees is coincidental. Specific control references and policy clauses in companion documents are written to reflect realistic patterns from common frameworks (SOC 2, NIST 800-53, ISO 27001, HIPAA) without reproducing copyrighted material.
