# Live Demo Setup Guide

This guide documents the pre-flight setup that makes Compliance Academy safe to run on a live stream. It is the operational counterpart to the [post-mortem on the Reactor demo auth failure](https://lwhieldon.github.io/2026/06/10/foundry-auth-timeout-postmortem.html), which explains why each of these steps exists.

If you are forking this repo to build your own live demo on Microsoft Foundry, follow this guide before going live. Each section is independent; do the ones that apply to your environment.

## Quick reference

| Goal | What to do | Section |
|---|---|---|
| Make auth not depend on `az login` | Set up a Service Principal | [Service Principal setup](#service-principal-setup) |
| Make `az login` recovery actually work on a corporate machine | Persist `REQUESTS_CA_BUNDLE` | [Corporate CA bundle persistence](#corporate-ca-bundle-persistence) |
| Verify auth works through the SDK before going live | Run `warm_up_auth` pre-flight | [Pre-flight verification](#pre-flight-verification) |
| Have a Plan B if Entra ID is completely broken | Set `AZURE_OPENAI_API_KEY` | [API key fallback](#api-key-fallback) |

---

## Service Principal setup

A Service Principal is a non-human identity in Microsoft Entra ID. It authenticates via tenant ID + client ID + client secret with the OAuth2 client credentials grant. There is no interactive login, no session that can expire while you are on camera, and no dependency on a working Azure CLI on the demo machine.

This is the recommended auth path for live demos.

### One-time setup

You need to be logged in as an account that can create Service Principals in your tenant and assign roles on the target resources.

```powershell
# 1. Create the Service Principal scoped to the Foundry resource
az ad sp create-for-rbac `
  --name "compliance-academy-stream" `
  --role "Cognitive Services OpenAI User" `
  --scopes "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource>"
```

The command outputs JSON with three fields:

```json
{
  "appId": "abc-123-...",
  "password": "client-secret-value...",
  "tenant": "tenant-uuid..."
}
```

Copy these into your local `.env` file (gitignored):

```
AZURE_CLIENT_ID=abc-123-...
AZURE_CLIENT_SECRET=client-secret-value...
AZURE_TENANT_ID=tenant-uuid...
```

### Grant the SP search access

Compliance Academy uses Azure AI Search for grounded retrieval. The SP needs read access to the search index:

```powershell
az role assignment create `
  --assignee <appId> `
  --role "Search Index Data Reader" `
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-resource>"
```

### How the codebase picks it up

`src/agents/_azure_client.py` provides `build_credential()` which:
1. Checks for `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
2. If all three are set, returns a `ClientSecretCredential`
3. If any are missing, falls back to `AzureCliCredential` (requires `az login`)

You do not need to change any code. The credential resolution is automatic based on what is in `.env`. Daily dev: leave the SP env vars blank, use `az login`. Stream day: populate them, no `az login` required.

### Rotating the SP secret

`az ad sp create-for-rbac` issues a secret that expires after 1 year by default. Rotate before expiry:

```powershell
az ad sp credential reset --id <appId>
```

Update the new password in `.env`. Old secret is invalidated immediately.

---

## Corporate CA bundle persistence

Skip this section if you are not on a corporate machine with a TLS-intercepting proxy (Netskope, Zscaler, Cisco Umbrella, etc.). If your `az login` ever fails with `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`, this section is for you.

The Azure CLI ships its own Python interpreter with its own CA bundle. That bundle does not trust your corporate root certificate, even though Windows itself does. The fix is to point the CLI's Python at a PEM file containing the corporate root.

### Get the corporate CA bundle

If your IT department has not already placed one on your machine, you can usually find or extract it. For SC&H specifically, the Netskope bundle lives at:

```
C:\Users\<username>\corp-ca-bundle.pem
```

For other organizations, ask IT for the corporate root certificate in PEM format.

### Persist the env var (the lesson learned)

Setting `REQUESTS_CA_BUNDLE` for the current PowerShell session is not enough. If your demo session is a new shell, the variable is gone, and any `az login` recovery attempt will fail with the same TLS error all over again.

Persist to the User scope so every future shell picks it up:

```powershell
[Environment]::SetEnvironmentVariable(
    "REQUESTS_CA_BUNDLE",
    "C:\Users\$env:USERNAME\corp-ca-bundle.pem",
    "User"
)
```

Verify after opening a new PowerShell window:

```powershell
echo $env:REQUESTS_CA_BUNDLE
# Should print: C:\Users\<username>\corp-ca-bundle.pem
```

### Why this matters even with a Service Principal

If you have an SP configured, you do not need `az login` for the app to run. So why bother with this?

Because the SP is your primary, and `az login` is your recovery path. If something goes wrong with the SP (secret rotated, role assignment removed, tenant misconfig), you want `az login` to be a one-command fix. If `az login` itself is broken because the CA bundle is not persistent, you have no recovery path on stream day.

Five seconds of one-time setup. Eliminates an entire class of "I cannot recover" scenarios.

---

## Pre-flight verification

The package's auth code is in `src/agents/_azure_client.py`. It exposes a `warm_up_auth()` function that fetches a token via the same code path the agents use at runtime. If `warm_up_auth()` succeeds, you know the SDK can acquire a token. If it fails, you know exactly what is broken before any audience is watching.

### Run it as a CLI

```powershell
python -m src.agents._azure_client
```

Expected successful output with Service Principal:

```
Compliance Academy auth pre-flight check
============================================================
OK    credential_type = ClientSecretCredential
      expires_on     = 1718045833 (59 minutes from now)
      ✔ Service Principal path resolved. Safe for live demo.
```

Expected successful output with Azure CLI fallback:

```
Compliance Academy auth pre-flight check
============================================================
OK    credential_type = AzureCliCredential
      expires_on     = 1718045833 (59 minutes from now)
      ⚠ Azure CLI path resolved. Fine for daily dev, fragile
        for live demos. Consider setting AZURE_CLIENT_ID,
        AZURE_CLIENT_SECRET, and AZURE_TENANT_ID in .env to
        upgrade to the Service Principal path.
```

Failure output:

```
Compliance Academy auth pre-flight check
============================================================
FAIL: Pre-flight auth check failed via AzureCliCredential: <details>...
      For live demos, set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET,
      and AZURE_TENANT_ID in .env to use a Service Principal.
      For daily dev, run `az login`.
```

### When to run

Run `python -m src.agents._azure_client` as the first step of your T-30 pre-flight, before starting Chainlit. The verification takes 2 to 5 seconds; failure surfaces immediately.

The same check runs automatically inside Chainlit when each new chat session starts, emitting an `[Auth]` line to the activity log. So even if you forget the CLI pre-flight, the activity log will show the credential type the first time you open the app in a browser. Watch for this line in your demo terminal:

```
[Auth]   Active credential: ClientSecretCredential  (token_valid_minutes=59, expires_on=1718045833)
```

If it shows `AzureCliCredential` and you are about to go live, abort and either populate your SP env vars or accept the risk explicitly.

---

## API key fallback

The Azure OpenAI deployments behind Foundry support both Entra ID auth and API key auth. By default Compliance Academy uses Entra ID. You can configure an API key as a last-resort fallback:

```
AZURE_OPENAI_API_KEY=<your-deployment-key>
```

If this env var is set, `build_azure_client()` uses the key directly and skips Entra ID entirely. The fallback is the same dual-path pattern already used by `_search_client.py` for Azure AI Search.

### When to use it

- **Daily dev**: leave it blank. Use Entra ID. Less key management overhead, no expiry to track.
- **Live demos with all paths possible**: leave it blank but have the key ready in a separate, untracked file so you can paste it into `.env` and restart Chainlit if Entra ID dies mid-event.
- **Live demos where Entra ID is known fragile**: populate it. The "no API keys in code" narrative still holds (the key only lives in your local `.env`, gitignored). The "no API keys anywhere" narrative does not, but neither does the post-mortem we are documenting here.

### How to verify it took effect

Run the pre-flight check. With the API key set, the activity log will show:

```
[Auth]   Active credential: AZURE_OPENAI_API_KEY (fallback)
```

This explicitly tells you (and the audience watching the activity log) that the app is on the keyed path, not Entra ID.

---

## T-30 pre-flight checklist

Print this and tape it next to your demo machine.

```
[ ] git pull               // latest fixes
[ ] echo $env:REQUESTS_CA_BUNDLE
    // Should show C:\Users\<username>\corp-ca-bundle.pem
    // If empty: [Environment]::SetEnvironmentVariable(...) and reopen shell

[ ] python -m src.agents._azure_client
    // Should print "ClientSecretCredential" or
    // "AZURE_OPENAI_API_KEY (fallback)" for stream-day safety
    // "AzureCliCredential" means you are on the fragile path

[ ] chainlit run app.py
    // Watch for [Auth] line in your tail terminal, confirms it matches above

[ ] Open Chainlit in browser
    // Pick the Default scenario, run one Forensic Analyst question
    // First-token latency should be <5s (token is cached from warm-up)

[ ] If everything green: you are clear to go live
```

---

## Common failure modes

### `AzureCliCredential: Failed to invoke the Azure CLI`

Either `az` is not on PATH, or `az login` has not been run, or the CLI session has expired. The mitigation that does not require fixing the CLI: set up a Service Principal. The CLI then becomes a fallback rather than the primary, and a broken CLI no longer breaks the app.

### `DefaultAzureCredential failed to retrieve a token`

You should never see this. This codebase does not use `DefaultAzureCredential` (deliberately; see the post-mortem). If you see this error, you are running an older revision of the code. Pull latest and retry.

### `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`

Corporate TLS interception is hitting `az login`. See [Corporate CA bundle persistence](#corporate-ca-bundle-persistence). The fix is `REQUESTS_CA_BUNDLE` pointing at the corp CA bundle, persisted to User env scope.

### `Pre-flight auth check failed via ClientSecretCredential`

Your SP credentials are misconfigured. Most common causes:
- `AZURE_CLIENT_SECRET` has expired (rotate via `az ad sp credential reset --id <appId>`)
- `AZURE_TENANT_ID` is wrong (must be the tenant that owns the SP, not the tenant of the resources it accesses)
- The SP does not have role assignments on the Foundry resource (re-run `az role assignment create`)

### Chainlit boots but first question hangs

Watch the activity log. If you see no `[Auth]` line at all, the pre-flight check did not run (you may be on an older revision). If you see `[Auth]` followed by a `[Foundry IQ]` retrieval and then nothing, the model call is hanging. That is no longer an auth issue; check Azure portal for the deployment status.

---

## What this guide is not

This guide covers auth and TLS, the two things that failed the Reactor demo and would have prevented it from failing. It does not cover:

- Foundry resource provisioning (see `docs/foundry_setup.md`)
- Index population for Foundry IQ retrieval (see `scripts/upload_foundry_iq.ps1`)
- Stream-day talking points and demo flow (see `docs/stream_day_cheatsheet.md`)
- General Chainlit configuration (see `chainlit.md`)

If you are setting up Compliance Academy for the first time, work through `docs/foundry_setup.md` first, then this guide for the live-demo hardening pass.
