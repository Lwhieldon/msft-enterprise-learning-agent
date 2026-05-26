#!/usr/bin/env bash
# upload_foundry_iq.sh
# Uploads Compliance Academy synthetic content to Azure Blob Storage for Foundry IQ ingestion.
# Idempotent. Re-runnable. Audience-reusable for other Foundry IQ projects.
#
# Compliance Academy / Reasoning Agents Live Streaming Battle (June 10, 2026)
# Built for Microsoft Reactor Agents League Post Build edition.

set -euo pipefail

# ---------- Defaults ----------
LOCATION="eastus"
CONTAINER="foundry-iq-source"
SOURCE_PATH=""
SUBSCRIPTION_ID=""
SKIP_ROLE_ASSIGNMENT=false
USE_STORAGE_KEY=false
WRITE_ENV_FILE=false
FORCE=false

# ---------- Colors ----------
if [[ -t 1 ]]; then
    CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; MAGENTA='\033[35m'; GRAY='\033[90m'; RESET='\033[0m'
else
    CYAN=''; GREEN=''; YELLOW=''; RED=''; MAGENTA=''; GRAY=''; RESET=''
fi

step()  { echo -e "\n${CYAN}==> $1${RESET}"; }
info()  { echo -e "    ${GRAY}$1${RESET}"; }
ok()    { echo -e "    ${GREEN}OK: $1${RESET}"; }
warn()  { echo -e "    ${YELLOW}WARNING: $1${RESET}"; }
fail()  { echo -e "    ${RED}ERROR: $1${RESET}"; }

# ---------- Usage ----------
usage() {
cat <<EOF
Usage: $0 -g <resource-group> -s <storage-account> [options]

Required:
  -g, --resource-group    Resource group name
  -s, --storage-account   Storage account name (3-24 chars, lowercase letters and numbers)

Options:
  -l, --location          Azure region (default: eastus)
  -c, --container         Blob container (default: foundry-iq-source)
  -p, --source-path       Local content path (default: ../data/synthetic/foundry_iq)
      --subscription      Subscription ID (default: current az context)
      --skip-role         Skip role assignment to current user
      --use-storage-key   Use storage account key instead of Azure AD auth
      --write-env         Write/update .env at repo root with FOUNDRY_IQ_* values
  -f, --force             Skip confirmation
  -h, --help              Show this help

Examples:
  $0 -g my-resource-group -s complianceacademy123
  $0 -g my-resource-group -s complianceacademy123 -l centralus --write-env
  $0 -g my-resource-group -s complianceacademy123 --use-storage-key -f
EOF
}

# ---------- Parse args ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -g|--resource-group)   RESOURCE_GROUP="$2"; shift 2 ;;
        -s|--storage-account)  STORAGE_ACCOUNT="$2"; shift 2 ;;
        -l|--location)         LOCATION="$2"; shift 2 ;;
        -c|--container)        CONTAINER="$2"; shift 2 ;;
        -p|--source-path)      SOURCE_PATH="$2"; shift 2 ;;
        --subscription)        SUBSCRIPTION_ID="$2"; shift 2 ;;
        --skip-role)           SKIP_ROLE_ASSIGNMENT=true; shift ;;
        --use-storage-key)     USE_STORAGE_KEY=true; shift ;;
        --write-env)           WRITE_ENV_FILE=true; shift ;;
        -f|--force)            FORCE=true; shift ;;
        -h|--help)             usage; exit 0 ;;
        *)                     echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# ---------- Validation ----------
: "${RESOURCE_GROUP:?Missing required: --resource-group}"
: "${STORAGE_ACCOUNT:?Missing required: --storage-account}"

if ! [[ "$STORAGE_ACCOUNT" =~ ^[a-z0-9]{3,24}$ ]]; then
    fail "Storage account name must be 3-24 lowercase letters/digits, got: $STORAGE_ACCOUNT"
    exit 1
fi

echo
echo -e "${MAGENTA}Compliance Academy: Foundry IQ Content Upload${RESET}"
echo -e "${MAGENTA}----------------------------------------------${RESET}"

# ---------- Resolve source path ----------
if [[ -z "$SOURCE_PATH" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SOURCE_PATH="$(cd "$SCRIPT_DIR/.." && pwd)/data/synthetic/foundry_iq"
fi

# ---------- Prereqs ----------
step "Checking prerequisites"

if ! command -v az >/dev/null 2>&1; then
    fail "Azure CLI ('az') not found."
    info "Install: https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi
AZ_VER=$(az version --output json 2>/dev/null | grep -o '"azure-cli": *"[^"]*"' | head -1 | cut -d'"' -f4)
ok "Azure CLI v$AZ_VER"

if ! command -v azcopy >/dev/null 2>&1; then
    fail "AzCopy not found."
    info "Install: https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10"
    exit 1
fi
AZC_VER=$(azcopy --version 2>/dev/null | sed -E 's/azcopy version //')
ok "AzCopy $AZC_VER"

if [[ ! -d "$SOURCE_PATH" ]]; then
    fail "Source path not found: $SOURCE_PATH"
    exit 1
fi
FILE_COUNT=$(find "$SOURCE_PATH" -type f | wc -l | tr -d ' ')
ok "Source path: $SOURCE_PATH ($FILE_COUNT files)"

# ---------- Azure auth ----------
step "Verifying Azure authentication"
if ! az account show >/dev/null 2>&1; then
    warn "Not logged in. Launching 'az login'..."
    az login --output none
fi

if [[ -n "$SUBSCRIPTION_ID" ]]; then
    info "Setting subscription context to $SUBSCRIPTION_ID"
    az account set --subscription "$SUBSCRIPTION_ID"
fi

TENANT_ID=$(az account show --query tenantId -o tsv)
SUB_NAME=$(az account show --query name -o tsv)
USER_NAME=$(az account show --query user.name -o tsv)
USER_OBJ_ID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")

ok "Tenant:       $TENANT_ID"
ok "Subscription: $SUB_NAME"
ok "User:         $USER_NAME"

if [[ -z "$USER_OBJ_ID" ]]; then
    warn "Could not resolve signed-in user object ID. Role assignment will be skipped."
    SKIP_ROLE_ASSIGNMENT=true
fi

# ---------- Plan ----------
step "Plan"
echo "    Resource Group:    $RESOURCE_GROUP"
echo "    Storage Account:   $STORAGE_ACCOUNT"
echo "    Location:          $LOCATION"
echo "    Container:         $CONTAINER"
echo "    Source Path:       $SOURCE_PATH"
echo "    Files to Upload:   $FILE_COUNT"
if [[ "$USE_STORAGE_KEY" == true ]]; then
    echo "    Auth for AzCopy:   Storage Account Key"
else
    echo "    Auth for AzCopy:   Azure AD"
fi
if [[ "$SKIP_ROLE_ASSIGNMENT" == true ]]; then
    echo "    Assign Role:       Skipped"
else
    echo "    Assign Role:       Yes (Storage Blob Data Contributor)"
fi
if [[ "$WRITE_ENV_FILE" == true ]]; then
    echo "    Write .env File:   Yes"
else
    echo "    Write .env File:   No"
fi

if [[ "$FORCE" != true ]]; then
    echo
    read -r -p "Proceed? (y/N) " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[yY]$ ]]; then
        warn "Aborted by user."
        exit 0
    fi
fi

# ---------- Resource group ----------
step "Resource group"
if [[ "$(az group exists --name "$RESOURCE_GROUP")" == "true" ]]; then
    ok "Resource group '$RESOURCE_GROUP' already exists; reusing"
else
    info "Creating resource group '$RESOURCE_GROUP' in $LOCATION..."
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
    ok "Created"
fi

# ---------- Storage account ----------
step "Storage account"
if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    ok "Storage account '$STORAGE_ACCOUNT' already exists; reusing"
else
    AVAILABLE=$(az storage account check-name --name "$STORAGE_ACCOUNT" --query nameAvailable -o tsv)
    if [[ "$AVAILABLE" != "true" ]]; then
        REASON=$(az storage account check-name --name "$STORAGE_ACCOUNT" --query reason -o tsv)
        fail "Storage account name '$STORAGE_ACCOUNT' is not available: $REASON"
        exit 1
    fi
    info "Creating storage account '$STORAGE_ACCOUNT' in $LOCATION..."
    az storage account create \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2 \
        --access-tier Hot \
        --allow-blob-public-access false \
        --min-tls-version TLS1_2 \
        --output none
    ok "Created"
fi

STORAGE_URL="https://${STORAGE_ACCOUNT}.blob.core.windows.net"
STORAGE_SCOPE=$(az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query id -o tsv)

# ---------- Role assignment ----------
if [[ "$SKIP_ROLE_ASSIGNMENT" != true ]]; then
    step "Role assignment (Storage Blob Data Contributor)"
    EXISTING=$(az role assignment list \
        --assignee-object-id "$USER_OBJ_ID" \
        --role "Storage Blob Data Contributor" \
        --scope "$STORAGE_SCOPE" \
        --query "[].id" -o tsv | wc -l | tr -d ' ')

    if [[ "$EXISTING" -gt 0 ]]; then
        ok "Role already assigned to current user"
    else
        info "Assigning role to current user..."
        az role assignment create \
            --assignee-object-id "$USER_OBJ_ID" \
            --assignee-principal-type User \
            --role "Storage Blob Data Contributor" \
            --scope "$STORAGE_SCOPE" \
            --output none
        ok "Assigned. Note: AD role propagation can take 1-5 minutes."
    fi
fi

# ---------- Container ----------
step "Blob container"
if [[ "$USE_STORAGE_KEY" == true ]]; then
    ACCOUNT_KEY=$(az storage account keys list --account-name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query '[0].value' -o tsv)
    EXISTS=$(az storage container exists --account-name "$STORAGE_ACCOUNT" --account-key "$ACCOUNT_KEY" --name "$CONTAINER" --query exists -o tsv)
    if [[ "$EXISTS" == "true" ]]; then
        ok "Container '$CONTAINER' already exists; reusing"
    else
        info "Creating container '$CONTAINER'..."
        az storage container create --account-name "$STORAGE_ACCOUNT" --account-key "$ACCOUNT_KEY" --name "$CONTAINER" --output none
        ok "Created"
    fi
else
    EXISTS=$(az storage container exists --account-name "$STORAGE_ACCOUNT" --auth-mode login --name "$CONTAINER" --query exists -o tsv 2>/dev/null || echo "")
    if [[ "$EXISTS" == "true" ]]; then
        ok "Container '$CONTAINER' already exists; reusing"
    elif [[ "$EXISTS" == "false" ]]; then
        info "Creating container '$CONTAINER'..."
        az storage container create --account-name "$STORAGE_ACCOUNT" --auth-mode login --name "$CONTAINER" --output none
        ok "Created"
    else
        warn "Could not verify container with AD auth (role propagation delay likely)."
        info "Waiting 30 seconds before retry..."
        sleep 30
        az storage container create --account-name "$STORAGE_ACCOUNT" --auth-mode login --name "$CONTAINER" --output none
        ok "Created after retry"
    fi
fi

# ---------- Upload ----------
step "Uploading content via AzCopy"
DEST="${STORAGE_URL}/${CONTAINER}"

if [[ "$USE_STORAGE_KEY" == true ]]; then
    SAS_EXPIRY=$(date -u -d '1 hour' '+%Y-%m-%dT%H:%MZ' 2>/dev/null || date -u -v+1H '+%Y-%m-%dT%H:%MZ')
    SAS_TOKEN=$(az storage container generate-sas \
        --account-name "$STORAGE_ACCOUNT" \
        --account-key "$ACCOUNT_KEY" \
        --name "$CONTAINER" \
        --permissions rwdl \
        --expiry "$SAS_EXPIRY" \
        --https-only \
        --output tsv)
    DEST="${DEST}?${SAS_TOKEN}"
else
    info "Authenticating AzCopy with Azure AD..."
    info "A browser window may open, or AzCopy will print a device code to enter at https://microsoft.com/devicelogin"
    azcopy login --tenant-id "$TENANT_ID"
fi

info "Source:      $SOURCE_PATH"
info "Destination: $STORAGE_URL/$CONTAINER"
azcopy copy "$SOURCE_PATH/*" "$DEST" --recursive --overwrite=true

ok "Upload complete"

# ---------- Optional .env ----------
if [[ "$WRITE_ENV_FILE" == true ]]; then
    step "Writing .env"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    ENV_PATH="$REPO_ROOT/.env"
    {
        echo "# Generated by upload_foundry_iq.sh on $(date '+%Y-%m-%d %H:%M')"
        echo "FOUNDRY_IQ_STORAGE_ACCOUNT=$STORAGE_ACCOUNT"
        echo "FOUNDRY_IQ_STORAGE_URL=$STORAGE_URL"
        echo "FOUNDRY_IQ_CONTAINER=$CONTAINER"
        echo "FOUNDRY_IQ_RESOURCE_GROUP=$RESOURCE_GROUP"
        echo "FOUNDRY_IQ_LOCATION=$LOCATION"
    } >> "$ENV_PATH"
    ok "Wrote $ENV_PATH"
fi

# ---------- Summary ----------
echo
echo -e "${GREEN}Done.${RESET}"
echo -e "${MAGENTA}----- Summary -----${RESET}"
echo "Storage URL: $STORAGE_URL"
echo "Container:   $CONTAINER"
echo "Files:       $FILE_COUNT uploaded"
echo
echo -e "${CYAN}Next steps:${RESET}"
echo "  1. In the Foundry portal, open your project > Build > Knowledge bases"
echo "  2. Create a knowledge base, e.g. 'compliance-academy-kb'"
echo "  3. Add knowledge source: Azure Blob Storage"
echo "     - Storage account: $STORAGE_ACCOUNT"
echo "     - Container:       $CONTAINER"
echo "  4. Wait for indexing to complete (2-15 minutes)"
echo "  5. Validate with a test query against the knowledge base"
echo
