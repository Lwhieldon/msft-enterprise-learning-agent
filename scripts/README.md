# Compliance Academy Scripts

Reusable scripts that provision Azure resources and upload content for the Compliance Academy demo. Designed to be audience-portable. If you are following along from the live battle, fork the repo and run these scripts with your own resource names.

## Inventory

| Script | Purpose | Platform |
|---|---|---|
| `upload_foundry_iq.ps1` | Upload synthetic Foundry IQ content to Azure Blob Storage | Windows / macOS / Linux (via PowerShell 7+) |
| `upload_foundry_iq.sh` | Same as above, native bash | macOS / Linux |

The two scripts are functionally equivalent. Pick whichever matches your shell.

## Prerequisites

- **Azure CLI** (`az`). Install: https://learn.microsoft.com/cli/azure/install-azure-cli
- **AzCopy** v10+. Install: https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10
- An Azure subscription where you can create resources
- Owner, Contributor, or User Access Administrator role on the target resource group (needed if the script assigns a role to your user)

To verify:

```bash
az --version       # any recent version works
azcopy --version   # 10.x or higher
az login           # if not already logged in
```

## What the Script Does

The upload script is idempotent. Re-running it does not break anything. Specifically it:

1. Verifies prerequisites (Azure CLI and AzCopy installed)
2. Confirms Azure authentication (prompts for `az login` if needed)
3. Creates the resource group if it does not exist
4. Creates the storage account if it does not exist
5. Creates the blob container if it does not exist
6. Assigns the running user the **Storage Blob Data Contributor** role on the storage account (skip with `--skip-role`)
7. Uses AzCopy with Azure AD authentication to upload the source content recursively
8. Optionally writes the resulting endpoint info to `.env` at the repo root

## Usage

### PowerShell (Windows, macOS, Linux)

```powershell
# From the scripts directory
cd scripts

# Minimum required args
.\upload_foundry_iq.ps1 `
    -ResourceGroup my-resource-group `
    -StorageAccount complianceacademy123

# With custom location, container, and .env write
.\upload_foundry_iq.ps1 `
    -ResourceGroup my-resource-group `
    -StorageAccount complianceacademy123 `
    -Location centralus `
    -Container my-content `
    -WriteEnvFile

# Skip the confirmation prompt and use storage key auth (faster for CI)
.\upload_foundry_iq.ps1 `
    -ResourceGroup my-resource-group `
    -StorageAccount complianceacademy123 `
    -UseStorageKey `
    -Force
```

### Bash (macOS, Linux)

```bash
# From the scripts directory
cd scripts
chmod +x upload_foundry_iq.sh

# Minimum required args
./upload_foundry_iq.sh -g my-resource-group -s complianceacademy123

# With custom location, container, and .env write
./upload_foundry_iq.sh \
    -g my-resource-group \
    -s complianceacademy123 \
    -l centralus \
    -c my-content \
    --write-env

# Skip the confirmation prompt and use storage key auth
./upload_foundry_iq.sh -g my-resource-group -s complianceacademy123 --use-storage-key -f
```

## Parameters

| PowerShell | Bash | Required | Default | Description |
|---|---|---|---|---|
| `-ResourceGroup` | `-g, --resource-group` | yes | | Azure resource group name |
| `-StorageAccount` | `-s, --storage-account` | yes | | Storage account name (3-24 lowercase letters/digits, globally unique) |
| `-Location` | `-l, --location` | no | `eastus` | Azure region for new resources |
| `-Container` | `-c, --container` | no | `foundry-iq-source` | Blob container name |
| `-SourcePath` | `-p, --source-path` | no | `../data/synthetic/foundry_iq` | Local content folder to upload |
| `-SubscriptionId` | `--subscription` | no | current az context | Override active subscription |
| `-SkipRoleAssignment` | `--skip-role` | no | false | Skip assigning Storage Blob Data Contributor to running user |
| `-UseStorageKey` | `--use-storage-key` | no | false | Use storage key for AzCopy instead of Azure AD |
| `-WriteEnvFile` | `--write-env` | no | false | Write FOUNDRY_IQ_* values to `.env` at repo root |
| `-Force` | `-f, --force` | no | false | Skip the interactive confirmation prompt |

## Authentication Notes

By default the script uses **Azure AD authentication** for AzCopy. This is the secure path:

- The script assigns you the `Storage Blob Data Contributor` role on the storage account
- AzCopy authenticates as you via `azcopy login`
- No storage keys touch your shell history or disk

During the AzCopy auth step, **expect either a browser tab to open automatically** (with a Microsoft sign-in page) or a **device code printed to the terminal** that you paste at `https://microsoft.com/devicelogin`. Complete the sign-in with the same account you used for `az login`. The script will resume automatically once auth completes.

There is a known timing gotcha: Azure AD role assignments can take **1 to 5 minutes** to propagate. If AzCopy fails immediately after a fresh role assignment, wait 60 seconds and re-run.

If you cannot wait, or you are running this in CI, pass `--use-storage-key` (`-UseStorageKey`) to bypass Azure AD and use a SAS token generated from the storage account key.

## After the Upload

The script prints the next steps. Briefly:

1. In the Foundry portal, open your project > **Build** > **Knowledge bases**
2. **Create knowledge base**, name it (e.g. `compliance-academy-kb`)
3. Select your existing Azure AI Search service
4. **Add knowledge source** > **Azure Blob Storage**
5. Point it at the storage account and container the script just populated
6. Wait for indexing (2-15 minutes for our content set)
7. Test with a query like *"What is the Helix Dynamics access control policy?"*

The full setup walkthrough is in `docs/foundry_setup.md` Section 6.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Storage account name 'X' is not available` | Name already taken (storage account names are globally unique) | Choose a different name. Lowercase letters and digits only, 3-24 chars |
| `AzCopy login failed` | Tenant ID mismatch or expired refresh token | Run `azcopy logout` then re-run script |
| `Forbidden` from AzCopy | Role assignment has not propagated yet | Wait 60 seconds, re-run. If persistent after 10 minutes, switch to `--use-storage-key` |
| `az ad signed-in-user show` returns nothing | Logged in via service principal (no signed-in user) | Pass `--skip-role` and pre-assign the role manually |
| AzCopy hangs at "logging in" | Browser flow blocked or not redirecting | Try `azcopy login --tenant-id <tenant>` manually, then re-run with `--skip-role` |
| Indexing succeeds but queries return nothing | Foundry IQ index name mismatch, or Search permissions missing | Confirm the IQ knowledge base points at the right container; confirm Foundry project managed identity has Search Index Data Reader on the Search service |

## What to Change If You Are Adapting This

The script is intentionally generic. To use it for a different project:

- Change `--source-path` to your own content folder
- Pick your own storage account name (must be globally unique)
- Adjust the SKU / kind / replication in the storage account creation block if you need GZRS, Premium, or hierarchical namespace
- If you want a different role (e.g. read-only for an indexer-only identity), edit the role assignment block

The script is structured so each step is a labeled block; copy and adapt freely.

## License

MIT, same as the parent repo.
