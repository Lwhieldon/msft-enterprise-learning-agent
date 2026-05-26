# Foundry Setup Walkthrough

This document captures every Foundry portal action required to provision the infrastructure Compliance Academy needs. Follow it in order. Each section ends with a verification step. The estimated total time is 90 minutes if nothing breaks.

## Resources

You already have:

- Foundry resource: `<your-unique-foundry-name>` in region of choice
- Resource group: `<your-azure-resource-group-name>`

You will provision:

- Model Router deployment (required)
- Claude Sonnet 4.5 and Haiku 4.5 deployments (optional, see caveat below)
- Azure AI Search service (required for Foundry IQ)
- Foundry IQ knowledge source (pointing at synthetic policy docs in Azure Blob Storage)
- Foundry IQ knowledge base (used by party agents at runtime)

## Critical Constraint: Model Router and Agent Service Tools

Per the official Model Router how-to documentation, "If you use Agent service tools in your flows, only OpenAI models will be used for routing." This matters because:

- The Game Master, Forensic Analyst, Compliance Auditor, and Compliance Officer all use Agent Service tools (code interpreter, Foundry IQ retrieval, state mutator)
- For those agents, Model Router will only select from OpenAI models in the subset, even if Claude models are configured
- The Suspect agents and Whistleblower Contact have no tool calls in their persona-only turns, so Model Router can select Claude models for them

Implication: deploying Claude is genuinely useful for suspect dialogue, but the demo functions fully without it. Treat Claude deployment as a stretch goal. If anything goes wrong, fall back to an OpenAI-only subset.

## Section 1: Verify the Foundry Resource (5 minutes)

1. Sign into the Microsoft Foundry portal at `https://ai.azure.com`
2. Confirm the **New Foundry** toggle is on (top of the portal)
3. Open the `<your-unique-foundry-name>` resource
4. Open or select your Foundry project
5. Confirm:
   - Region is East US 2
   - The resource shows as healthy (no warning banners)
   - You have Contributor or Owner role on the resource group (`<your-azure-resource-group-name>`)

**Verification:** the project endpoint is visible in **Project settings**, in the form `https://<project-name>.<region>.inference.ml.azure.com` or similar. Copy it to a notes file. You will need it for `.env`.

## Section 2: Deploy Model Router (10 minutes)

1. In the Foundry portal, go to **Models + endpoints** in the left navigation
2. Click **Deploy model**, then **Deploy base model**
3. Search for `model-router` and select it
4. Choose **Custom deployment** so you can configure routing mode and subset
5. Settings:
   - **Deployment name:** `compliance-academy-router` (or any name you prefer; record it for `.env`)
   - **Model version:** the latest available (`2025-11-18` or newer)
   - **Routing mode:** **Balanced** (you can configure per-agent routing modes through SDK parameters at runtime)
   - **Model subset:** select **Route to a subset of models** and check these initially:
     - `gpt-5`
     - `gpt-5-mini`
     - `o4-mini`
     - `gpt-4.1-mini` (good Balanced/Cost fallback)
   - **Content filter:** select the default or a custom filter you have already configured. The filter applies to all underlying models, do not set per-model filters
   - **Tokens-per-minute limit:** start at the default; you can raise it later if needed
6. Click **Deploy**

**Verification:**
- After deployment completes, click the new model router deployment to open it
- Open the playground tab from the deployment page
- Send a test prompt ("Explain SOC2 in three sentences")
- Confirm the response renders and the `model` field in the response details shows which underlying model was selected

## Section 3: Deploy Claude Models (Optional, 20 minutes)

Skip this section if you want to keep scope tight. The demo works without Claude deployed.

Prerequisites (verify before proceeding):

- Your Azure subscription is **Enterprise or MCA-E** (Claude in Foundry is gated to these subscription types). Regular pay-as-you-go does not qualify
- Your subscription has access to **Azure Marketplace** with the permissions to subscribe to model offerings
- You are deploying in East US 2 or Sweden Central (East US 2 is your case, so this is fine)

Steps:

1. In **Models + endpoints**, click **Deploy model**
2. Search for `claude-sonnet-4-5` and select it
3. Configure:
   - **Deployment name:** `claude-sonnet-4-5` (keep simple, this is the name Model Router will reference)
   - **Deployment type:** Global Standard
   - **Tokens-per-minute limit:** start at the default Enterprise quota
4. Click **Deploy**
5. Wait for the deployment to enter the **Succeeded** state (usually 2-5 minutes)
6. Repeat for `claude-haiku-4-5`

Known gotcha: in April 2026 you hit an `AnthropicOrganizationCreationFailed` backend error during Claude deployment. That error originated on Anthropic's side, not Foundry's. If it recurs:

- Wait 15 minutes and retry (the most common cause was transient)
- If still failing, raise a Foundry support ticket referencing the previous incident
- For the demo, simply skip Claude and continue with OpenAI-only routing

**Verification:**
- Open each deployment from **Models + endpoints**
- Confirm the base URL pattern: `https://<your-unique-foundry-name>.services.ai.azure.com/anthropic`
- Confirm a deployment-level API key or that you can authenticate via Microsoft Entra ID with `Cognitive Services User` role

After both Claude models are deployed and verified, update the Model Router subset:

1. Open your `compliance-academy-router` deployment
2. Click **Edit** (or equivalent)
3. Add `claude-sonnet-4-5` and `claude-haiku-4-5` to the subset
4. Save (changes take up to 5 minutes to apply)

## Section 4: Create Azure AI Search Service for Foundry IQ (15 minutes)

Foundry IQ is built on Azure AI Search's agentic retrieval. You need a search service that supports this capability.

1. In the Azure portal (not Foundry), go to **Create a resource** > **AI + machine learning** > **Azure AI Search**
2. Configuration:
   - **Resource group:** `<your-azure-resource-group-name>` (same as the Foundry resource)
   - **Service name:** `org-search-compliance` (or any unique name)
   - **Region:** East US (Virginia) is the recommended choice. Cross-region with the Foundry resource is supported. If East US is unavailable, Central US or South Central US are good alternatives. East US 2 sometimes shows the Standard tier as disabled due to capacity constraints; that is not a blocker.
   - **Pricing tier:** Standard (Basic is too limited; the agentic retrieval features need Standard or above)
3. Click **Review + create**, then **Create**
4. Wait for deployment to complete (~5-10 minutes)

Once created:

1. Open the new search service
2. In **Keys**, copy the primary admin key (you will need this for index creation)
3. In **Access control (IAM)**, ensure:
   - Your Foundry project's managed identity has the **Search Index Data Reader** role assigned at the search service scope
   - If your code will write to the index, also assign **Search Index Data Contributor**

**Verification:** the search service shows as **Running** with green status, and the **Search explorer** tab is accessible (it will be empty initially).

## Section 5: Prepare Synthetic Foundry IQ Content (30 minutes)

This is a content-creation step, not a portal step. You will create synthetic policy and framework documents that Foundry IQ will index. These files go in `data/synthetic/foundry_iq/`.

Create:

- `frameworks/hipaa_security_rule_biotech.md`: synthetic HIPAA Security Rule, biotech-relevant
- `frameworks/iso_27001_annex_a.md`: synthetic excerpts of ISO 27001
- `frameworks/nist_800_53_subset.md`: synthetic excerpts of NIST 800-53 controls relevant to the scenarios
- `frameworks/soc2_trust_service_criteria.md`: synthetic excerpts of SOC2 (paraphrased, original wording)
- `helix_policies/access_control_policy.md`: synthetic Helix Dynamics access control policy (SOC2-aligned)
- `helix_policies/data_classification_policy.md`: synthetic data classification rules
- `helix_policies/incident_response_playbook.md`: synthetic IR playbook
- `helix_policies/vendor_management_policy.md`: synthetic vendor risk procedures
- `playbooks/credential_compromise_response.md`: synthetic playbook
- `playbooks/insider_threat_response.md`: synthetic playbook
- `playbooks/vendor_breach_response.md`: synthetic playbook

All content is synthetic. None of these files copy from real proprietary or copyrighted material.

Once created, upload to Azure Blob Storage:

1. In the Azure portal, create a storage account if you don't have one in `<your-azure-resource-group-name>`. Name suggestion: `orgcomplianceacademy`
2. Create a container named `foundry-iq-source`
3. Upload all the synthetic markdown files

**Verification:** the container shows the uploaded files with the expected sizes and content.

## Section 6: Configure Agentic Retrieval in Azure AI Search (15 minutes)

The "knowledge base" abstraction Foundry IQ exposes is implemented on top of Azure AI Search's agentic retrieval feature. The Foundry portal provides a UI for this, but during the build for this project the portal flow had several rough edges (state mismatches, name conflicts, inlined model deployment wizards). The direct Azure AI Search path is more reliable and produces the same end result: an indexed, vector-searchable knowledge base your agents can query through the Azure AI Search SDK or the Foundry Agent Service.

### Section 6.1: Deploy an Embedding Model and Chat Completion Model (5 minutes)

The indexing pipeline needs an embedding model to vectorize each chunk, and a small chat completion model for query rewriting and result re-ranking. The agents themselves use the Model Router, but the search service's agentic retrieval needs direct deployments.

1. In the Foundry portal, go to **Models + endpoints**
2. **Deploy model** > search for `text-embedding-3-large` (or `text-embedding-3-small` for lower cost)
   - **Deployment name:** `text-embedding-3-large`
   - Defaults for TPM and version
   - **Deploy**
3. **Deploy model** again > search for `gpt-4.1-mini`
   - **Deployment name:** `gpt-4.1-mini`
   - Defaults
   - **Deploy**

Both deployments take ~30 seconds each.

### Section 6.2: Grant Search Service the Required Roles (5 minutes)

Your search service's system-assigned managed identity needs read access to two resources:

**Storage Blob Data Reader on the storage account:**

1. Azure portal > open your storage account (e.g. `orgcomplianceacademy`)
2. **Access control (IAM)** > **Add role assignment**
3. Role: **Storage Blob Data Reader**
4. Assign to: **Managed identity** > select your search service (e.g. `org-search-compliance`)
5. Save. Wait 1-2 minutes for propagation.

**Cognitive Services OpenAI User on the Foundry resource:**

1. Azure portal > open your Foundry resource (the AI services account)
2. **Access control (IAM)** > **Add role assignment**
3. Role: **Cognitive Services OpenAI User**
4. Assign to: **Managed identity** > select your search service
5. Save. Wait 1-2 minutes for propagation.

Without these roles, the indexing run in Section 6.3 will fail with `Forbidden` errors during either the blob read step or the embedding generation step.

### Section 6.3: Run the "Import and Vectorize Data" Wizard (5 minutes)

This wizard creates the data source, skillset (chunking + embedding), index, and indexer in a single flow.

1. Azure portal > open your Azure AI Search service
2. From the **Overview** page, click **Import and vectorize data**
3. **Data source:** Azure Blob Storage
   - **Subscription:** your subscription
   - **Storage account:** your storage account (e.g. `orgcomplianceacademy`)
   - **Blob container:** `foundry-iq-source`
   - **Blob folder:** leave blank
   - **Authentication:** System-assigned managed identity
4. **Next**
5. **Vectorize your text:**
   - **Kind:** Azure OpenAI
   - **Subscription / Service:** your Foundry resource
   - **Model deployment:** the embedding model you deployed in 6.1 (`text-embedding-3-large`)
   - **Authentication:** System-assigned managed identity
6. **Next**
7. **Vectorize and enrich images:** leave OFF (our content is text-only)
8. **Next**
9. **Advanced settings:** leave defaults
10. **Object name prefix:** `compliance` (this prefixes the auto-generated index, indexer, and skillset names)
11. **Create**

The wizard provisions the resources and starts the first indexing run immediately. For ~12 small markdown files, expect indexing to complete in 2-5 minutes.

### Section 6.4: Verify End-to-End

Once indexing completes:

1. In the search service, navigate to **Search management > Indexes** in the left nav
2. Click the index that was created (e.g. `compliance-content-index`)
3. Confirm:
   - **Documents** count is reasonable. Expect ~40-60 chunks for 12 source files (Azure AI Search chunks each document into smaller pieces for retrieval precision)
   - **Vector index quota usage** is non-zero (confirms embeddings were generated)
4. Use the **Search explorer** tab to run a test query:
   - Type: `four-hour termination window`
   - Click **Search**
   - You should get one or more results citing content from `access_control_policy.md`
5. Try a semantic / vector query:
   - Click **Query options** > set Search type to **Semantic** or **Vector**
   - Same query
   - Vector results should still be relevant even if phrasing differs

If you see grounded results with reasonable relevance scores, the indexing pipeline is verified end-to-end. The agents can now query this index at runtime.

### Section 6.5: Optional Knowledge Base Wrapper

The "knowledge base" abstraction that Foundry IQ exposes is also accessible in the Azure AI Search portal under **Agentic retrieval > Knowledge bases**. If you ran the wizard above, you'll see a knowledge base auto-created. You can attach additional knowledge sources to it later (more blob containers, web sources, SharePoint sites) without re-running the wizard.

### Why the Direct Path

The Foundry portal Knowledge Bases experience is the same underlying mechanism, but it inlines several steps (search connection, embedding deployment, chat deployment, indexer config) into UI flows that can fail in confusing ways. The direct Azure AI Search wizard:

- Surfaces errors earlier and more clearly
- Lets you wire role assignments correctly upfront
- Provisions all four artifacts (data source, skillset, index, indexer) in one transaction
- Produces resources that Foundry IQ recognizes automatically if you later want to manage them through the Foundry UI

Once the index exists, agents query it the same way regardless of how it was created.

## Section 7: Wire Up Environment Variables

Create `.env` in the repo root (it will be gitignored). Populate:

```env
# Foundry project
AZURE_AI_PROJECT_ENDPOINT=<from Section 1>

# Model Router (for agents)
AZURE_AI_MODEL_ROUTER_DEPLOYMENT=compliance-academy-router

# Direct model deployments (used by search service for agentic retrieval)
AZURE_AI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_AI_CHAT_DEPLOYMENT=gpt-4.1-mini

# Claude models (if Section 3 was completed)
AZURE_AI_CLAUDE_SONNET_DEPLOYMENT=claude-sonnet-4-5
AZURE_AI_CLAUDE_HAIKU_DEPLOYMENT=claude-haiku-4-5
AZURE_AI_CLAUDE_BASE_URL=https://<your-unique-foundry-name>.services.ai.azure.com/anthropic

# Azure AI Search (the retrieval layer)
AZURE_SEARCH_ENDPOINT=https://<your-search-service-name>.search.windows.net
AZURE_SEARCH_INDEX_NAME=compliance-content-index
AZURE_SEARCH_API_VERSION=2024-07-01
```

Confirm `.env` is in `.gitignore` (it should be already). The `scripts/upload_foundry_iq.ps1` script populates the `FOUNDRY_IQ_*` storage values automatically when run with `-WriteEnvFile`.

## Cost Awareness

Approximate per-day cost during development (rough estimate):

- Model Router: pay per token, scales with usage. Expect $5-$20/day during heavy build and testing
- Claude Sonnet 4.5: per-token, more expensive than GPT-5-mini. Used only for suspect persona turns
- Azure AI Search Standard tier: ~$1.00-$2.00/hour while running, can be stopped between sessions
- Azure Blob Storage: trivial for our content sizes

For the live battle on June 10:

- Plan for ~$30-$50 of usage during the 90 minutes of broadcast plus pre-stream tech check
- Set a budget alert on the resource group at $200/month to catch surprises early

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Model Router deployment fails | Region or quota issue | Confirm East US 2, check subscription quota for model-router |
| Claude deployment fails with `AnthropicOrganizationCreationFailed` | Anthropic backend transient | Wait 15 minutes, retry. If persistent, raise support ticket. Demo works without Claude. |
| Foundry IQ indexing fails | Managed identity missing Search role | Assign `Search Index Data Reader` (and `Search Index Data Contributor` if writing) to the Foundry project managed identity |
| Knowledge base query returns nothing | Indexing still running, or no files in source container | Check indexing status; verify blob container has files |
| Agent flow only picks OpenAI models even with Claude in subset | Working as designed | Agent Service tool calls force OpenAI routing; Claude routes only for non-tool turns |
| Knowledge base query returns 403 | Managed identity permissions | Verify the role assignment on the search service and that the project endpoint is correct |
