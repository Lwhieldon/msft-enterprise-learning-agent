<#
.SYNOPSIS
    Uploads Compliance Academy synthetic content to Azure Blob Storage for Foundry IQ ingestion.

.DESCRIPTION
    Idempotent setup script that provisions Azure Blob Storage and uploads source content
    that Microsoft Foundry IQ will index. Designed to be re-runnable and audience-reusable.

    The script:
    1. Verifies prerequisites (Azure CLI, AzCopy)
    2. Confirms Azure authentication
    3. Creates the resource group if it does not exist
    4. Creates the storage account if it does not exist
    5. Creates the blob container if it does not exist
    6. Assigns Storage Blob Data Contributor role to the running user (skip with -SkipRoleAssignment)
    7. Uploads the source content folder using AzCopy with Azure AD authentication
    8. Optionally writes/updates a .env file with the resulting endpoint values

.PARAMETER ResourceGroup
    Resource group name. Required.

.PARAMETER StorageAccount
    Storage account name. Required. Must be globally unique, 3-24 chars, lowercase letters and numbers only.

.PARAMETER Location
    Azure region for new resources. Default: eastus.

.PARAMETER Container
    Blob container name. Default: foundry-iq-source.

.PARAMETER SourcePath
    Local path to the content folder. Default: ..\data\synthetic\foundry_iq relative to script location.

.PARAMETER SubscriptionId
    Subscription ID. Optional; uses the current Azure CLI context if omitted.

.PARAMETER SkipRoleAssignment
    Skip assigning Storage Blob Data Contributor to the current user. Use when role is already assigned.

.PARAMETER UseStorageKey
    Use a storage account key instead of Azure AD auth for AzCopy. Less secure; useful when AD role propagation is delayed.

.PARAMETER WriteEnvFile
    Write or update an .env file at the repo root with FOUNDRY_IQ_* values.

.PARAMETER Force
    Skip the confirmation prompt.

.EXAMPLE
    .\upload_foundry_iq.ps1 -ResourceGroup my-resource-group -StorageAccount complianceacademy123

.EXAMPLE
    .\upload_foundry_iq.ps1 -ResourceGroup my-resource-group -StorageAccount complianceacademy123 -Location centralus -WriteEnvFile

.EXAMPLE
    .\upload_foundry_iq.ps1 -ResourceGroup my-resource-group -StorageAccount complianceacademy123 -UseStorageKey -Force

.NOTES
    Compliance Academy / Reasoning Agents Live Streaming Battle (June 10, 2026)
    Built for Microsoft Reactor Agents League Post Build edition
    Repo: https://github.com/lwhieldon/msft-enterprise-learning-agent
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$true)]
    [ValidateLength(3,24)]
    [ValidatePattern('^[a-z0-9]+$')]
    [string]$StorageAccount,

    [string]$Location = 'eastus',
    [string]$Container = 'foundry-iq-source',
    [string]$SourcePath,
    [string]$SubscriptionId,
    [switch]$SkipRoleAssignment,
    [switch]$UseStorageKey,
    [switch]$WriteEnvFile,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# ----- Helpers -----
function Write-Step    { param([string]$Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Info    { param([string]$Msg) Write-Host "    $Msg" -ForegroundColor Gray }
function Write-Ok      { param([string]$Msg) Write-Host "    OK: $Msg" -ForegroundColor Green }
function Write-Warn    { param([string]$Msg) Write-Host "    WARNING: $Msg" -ForegroundColor Yellow }
function Write-Fail    { param([string]$Msg) Write-Host "    ERROR: $Msg" -ForegroundColor Red }
function Test-Command  { param([string]$Cmd) [bool](Get-Command $Cmd -ErrorAction SilentlyContinue) }

# ----- Banner -----
Write-Host ""
Write-Host "Compliance Academy: Foundry IQ Content Upload" -ForegroundColor Magenta
Write-Host "----------------------------------------------" -ForegroundColor Magenta

# ----- Resolve source path default -----
if (-not $SourcePath) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $SourcePath = Join-Path (Split-Path -Parent $scriptRoot) 'data\synthetic\foundry_iq'
}

# ----- Prerequisite checks -----
Write-Step "Checking prerequisites"

if (-not (Test-Command 'az')) {
    Write-Fail "Azure CLI ('az') not found."
    Write-Info "Install: https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
}
$azVersion = (az version --output json | ConvertFrom-Json).'azure-cli'
Write-Ok "Azure CLI v$azVersion"

if (-not (Test-Command 'azcopy')) {
    Write-Fail "AzCopy not found."
    Write-Info "Install: https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10"
    exit 1
}
$azcVersion = (azcopy --version) -replace 'azcopy version ',''
Write-Ok "AzCopy $azcVersion"

if (-not (Test-Path $SourcePath)) {
    Write-Fail "Source path not found: $SourcePath"
    exit 1
}
$fileCount = (Get-ChildItem -Path $SourcePath -Recurse -File).Count
Write-Ok "Source path: $SourcePath ($fileCount files)"

# ----- Azure authentication -----
Write-Step "Verifying Azure authentication"

$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Warn "Not logged in. Launching 'az login'..."
    az login --output none
    $account = az account show --output json | ConvertFrom-Json
}

if ($SubscriptionId) {
    Write-Info "Setting subscription context to $SubscriptionId"
    az account set --subscription $SubscriptionId
    $account = az account show --output json | ConvertFrom-Json
}

Write-Ok "Tenant:       $($account.tenantId)"
Write-Ok "Subscription: $($account.name)"
Write-Ok "User:         $($account.user.name)"
$currentUserId = (az ad signed-in-user show --query id -o tsv 2>$null)
if (-not $currentUserId) {
    Write-Warn "Could not resolve signed-in user object ID. Role assignment will be skipped."
    $SkipRoleAssignment = $true
}

# ----- Plan summary and confirmation -----
Write-Step "Plan"
Write-Host "    Resource Group:    $ResourceGroup" -ForegroundColor White
Write-Host "    Storage Account:   $StorageAccount" -ForegroundColor White
Write-Host "    Location:          $Location" -ForegroundColor White
Write-Host "    Container:         $Container" -ForegroundColor White
Write-Host "    Source Path:       $SourcePath" -ForegroundColor White
Write-Host "    Files to Upload:   $fileCount" -ForegroundColor White
Write-Host "    Auth for AzCopy:   $(if ($UseStorageKey) {'Storage Account Key'} else {'Azure AD'})" -ForegroundColor White
Write-Host "    Assign Role:       $(if ($SkipRoleAssignment) {'Skipped'} else {'Yes (Storage Blob Data Contributor)'})" -ForegroundColor White
Write-Host "    Write .env File:   $(if ($WriteEnvFile) {'Yes'} else {'No'})" -ForegroundColor White

if (-not $Force) {
    $confirm = Read-Host "`nProceed? (y/N)"
    if ($confirm -notmatch '^[yY]') {
        Write-Warn "Aborted by user."
        exit 0
    }
}

# ----- Resource group -----
Write-Step "Resource group"
$rgExists = (az group exists --name $ResourceGroup) -eq 'true'
if ($rgExists) {
    Write-Ok "Resource group '$ResourceGroup' already exists; reusing"
} else {
    Write-Info "Creating resource group '$ResourceGroup' in $Location..."
    az group create --name $ResourceGroup --location $Location --output none
    Write-Ok "Created"
}

# ----- Storage account -----
Write-Step "Storage account"
$saExists = az storage account show --name $StorageAccount --resource-group $ResourceGroup --output json 2>$null
if ($saExists) {
    Write-Ok "Storage account '$StorageAccount' already exists; reusing"
} else {
    Write-Info "Checking name availability..."
    $available = (az storage account check-name --name $StorageAccount --query nameAvailable -o tsv)
    if ($available -ne 'true') {
        $reason = (az storage account check-name --name $StorageAccount --query reason -o tsv)
        Write-Fail "Storage account name '$StorageAccount' is not available: $reason"
        exit 1
    }
    Write-Info "Creating storage account '$StorageAccount' in $Location..."
    az storage account create `
        --name $StorageAccount `
        --resource-group $ResourceGroup `
        --location $Location `
        --sku Standard_LRS `
        --kind StorageV2 `
        --access-tier Hot `
        --allow-blob-public-access false `
        --min-tls-version TLS1_2 `
        --output none
    Write-Ok "Created"
}

$storageUrl = "https://$StorageAccount.blob.core.windows.net"
$storageScope = (az storage account show --name $StorageAccount --resource-group $ResourceGroup --query id -o tsv)

# ----- Role assignment -----
if (-not $SkipRoleAssignment) {
    Write-Step "Role assignment (Storage Blob Data Contributor)"
    $existing = az role assignment list `
        --assignee-object-id $currentUserId `
        --role 'Storage Blob Data Contributor' `
        --scope $storageScope `
        --output json | ConvertFrom-Json

    if ($existing -and $existing.Count -gt 0) {
        Write-Ok "Role already assigned to current user"
    } else {
        Write-Info "Assigning role to current user..."
        az role assignment create `
            --assignee-object-id $currentUserId `
            --assignee-principal-type User `
            --role 'Storage Blob Data Contributor' `
            --scope $storageScope `
            --output none
        Write-Ok "Assigned. Note: AD role propagation can take 1-5 minutes."
    }
}

# ----- Container -----
Write-Step "Blob container"
if ($UseStorageKey) {
    $accountKey = (az storage account keys list --account-name $StorageAccount --resource-group $ResourceGroup --query '[0].value' -o tsv)
    $exists = (az storage container exists --account-name $StorageAccount --account-key $accountKey --name $Container --query exists -o tsv)
    if ($exists -eq 'true') {
        Write-Ok "Container '$Container' already exists; reusing"
    } else {
        Write-Info "Creating container '$Container'..."
        az storage container create --account-name $StorageAccount --account-key $accountKey --name $Container --output none
        Write-Ok "Created"
    }
} else {
    $exists = (az storage container exists --account-name $StorageAccount --auth-mode login --name $Container --query exists -o tsv 2>$null)
    if ($exists -eq 'true') {
        Write-Ok "Container '$Container' already exists; reusing"
    } elseif ($exists -eq 'false') {
        Write-Info "Creating container '$Container'..."
        az storage container create --account-name $StorageAccount --auth-mode login --name $Container --output none
        Write-Ok "Created"
    } else {
        Write-Warn "Could not verify container with AD auth (role propagation delay likely)."
        Write-Info "Waiting 30 seconds before retry..."
        Start-Sleep -Seconds 30
        az storage container create --account-name $StorageAccount --auth-mode login --name $Container --output none
        Write-Ok "Created after retry"
    }
}

# ----- AzCopy upload -----
Write-Step "Uploading content via AzCopy"
$dest = "$storageUrl/$Container"

if ($UseStorageKey) {
    $sasToken = (az storage container generate-sas `
        --account-name $StorageAccount `
        --account-key $accountKey `
        --name $Container `
        --permissions rwdl `
        --expiry ((Get-Date).AddHours(1).ToString('yyyy-MM-ddTHH:mmZ')) `
        --https-only `
        --output tsv)
    $dest = "$dest`?$sasToken"
} else {
    Write-Info "Authenticating AzCopy with Azure AD..."
    Write-Info "A browser window may open, or AzCopy will print a device code to enter at https://microsoft.com/devicelogin"
    azcopy login --tenant-id $account.tenantId
}

Write-Info "Source:      $SourcePath"
Write-Info "Destination: $storageUrl/$Container"
$azcopyArgs = @('copy', "$SourcePath\*", $dest, '--recursive', '--overwrite=true')
& azcopy @azcopyArgs

if ($LASTEXITCODE -ne 0) {
    Write-Fail "AzCopy upload failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Ok "Upload complete"

# ----- Optional .env file -----
if ($WriteEnvFile) {
    Write-Step "Writing .env"
    $repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
    $envPath = Join-Path $repoRoot '.env'
    $envEntries = @(
        "# Generated by upload_foundry_iq.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
        "FOUNDRY_IQ_STORAGE_ACCOUNT=$StorageAccount"
        "FOUNDRY_IQ_STORAGE_URL=$storageUrl"
        "FOUNDRY_IQ_CONTAINER=$Container"
        "FOUNDRY_IQ_RESOURCE_GROUP=$ResourceGroup"
        "FOUNDRY_IQ_LOCATION=$Location"
    )
    if (Test-Path $envPath) {
        Write-Warn "$envPath already exists. Appending new entries."
        Add-Content -Path $envPath -Value "`n$($envEntries -join "`n")"
    } else {
        Set-Content -Path $envPath -Value ($envEntries -join "`n")
    }
    Write-Ok "Wrote $envPath"
}

# ----- Success summary -----
Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "----- Summary -----" -ForegroundColor Magenta
Write-Host "Storage URL: $storageUrl" -ForegroundColor White
Write-Host "Container:   $Container" -ForegroundColor White
Write-Host "Files:       $fileCount uploaded" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. In the Foundry portal, open your project > Build > Knowledge bases"
Write-Host "  2. Create a knowledge base, e.g. 'compliance-academy-kb'"
Write-Host "  3. Add knowledge source: Azure Blob Storage"
Write-Host "     - Storage account: $StorageAccount"
Write-Host "     - Container:       $Container"
Write-Host "  4. Wait for indexing to complete (2-15 minutes)"
Write-Host "  5. Validate with a test query against the knowledge base"
Write-Host ""
