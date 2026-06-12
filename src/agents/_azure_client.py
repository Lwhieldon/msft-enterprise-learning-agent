"""Shared Azure OpenAI client setup for Compliance Academy agents.

Centralizes the Azure Foundry connection details so each agent module
(Scenario Generator, Suspect, Forensic Analyst, Compliance Officer) does
not need to duplicate authentication, deployment resolution, or prompt
loading logic.

Authentication strategy:
    The credential chain is built by ``build_credential()`` and used by
    ``build_azure_client()``. Two paths are supported:

    1. Service Principal (recommended for live demos and any non-interactive
       workload). Set ``AZURE_CLIENT_ID``, ``AZURE_CLIENT_SECRET``, and
       ``AZURE_TENANT_ID`` in ``.env`` and the chain uses
       ``ClientSecretCredential`` (non-interactive, no IMDS hang).

    2. Azure CLI (daily dev default). Run ``az login`` in your shell. The
       chain falls back to ``AzureCliCredential`` when the SP env vars are
       not all set.

    The chain DELIBERATELY OMITS ``ManagedIdentityCredential``. On a local
    dev machine the IMDS endpoint at ``169.254.169.254`` does not exist,
    and including it adds a fifty-second hang on every auth failure. See
    the post-mortem at
    https://lwhieldon.github.io/2026/06/10/foundry-auth-timeout-postmortem.html
    for the full story.

    For complete recovery insurance, ``build_azure_client()`` also supports
    an API key fallback via ``AZURE_OPENAI_API_KEY``. If set, the Azure
    OpenAI client uses the key directly and skips Entra ID entirely. This
    mirrors the dual-path pattern already used by ``_search_client.py``.

Environment variables (required by ``build_azure_client``):
    AZURE_AI_PROJECT_ENDPOINT
        e.g., https://sch-foundry-poc-eastus2.services.ai.azure.com/api/projects/sch-foundry-poc-eastus2

Environment variables (optional, Service Principal):
    AZURE_CLIENT_ID         Service Principal app ID
    AZURE_CLIENT_SECRET     Service Principal client secret
    AZURE_TENANT_ID         Tenant ID containing the SP

Environment variables (optional, last-resort fallback):
    AZURE_OPENAI_API_KEY    Azure OpenAI deployment API key

Environment variables (optional, general):
    AZURE_OPENAI_API_VERSION    defaults to '2024-10-21'

Pre-flight verification:
    Use ``warm_up_auth()`` before going live to verify auth ACTUALLY works
    through the SDK code path (not just that ``az login`` exited cleanly).
    Returns the resolved credential type so you know exactly which path
    was used.

Per-agent deployment selection is delegated to ``resolve_deployment``, which
each agent calls with its own preferred env var name plus shared fallbacks.
"""

from __future__ import annotations

import os
from pathlib import Path

# Best-effort .env loading so CLI smoke tests pick up Azure credentials.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv()
except ImportError:
    pass


#: Default API version for the Azure OpenAI chat completions endpoint.
DEFAULT_API_VERSION: str = "2024-10-21"

#: Default deployment used when no env var resolves. gpt-4.1-mini is fast
#: and predictable for the live demo budget.
DEFAULT_DEPLOYMENT: str = "gpt-4.1-mini"


class AgentClientError(Exception):
    """Raised for Azure client setup failures (missing env vars, missing deps)."""


def require_env(name: str) -> str:
    """Read a required environment variable or raise a clear error."""
    value = os.environ.get(name)
    if not value:
        raise AgentClientError(
            f"Required environment variable {name} is not set. "
            "Check your .env file or shell environment."
        )
    return value


def resolve_deployment(
    explicit: str | None,
    *env_var_names: str,
    default: str = DEFAULT_DEPLOYMENT,
) -> str:
    """Resolve a deployment name from caller arg, env vars, or default.

    Order of precedence: ``explicit`` argument, then each env var in
    ``env_var_names`` in order, then ``default``. This lets each agent
    declare its own preferred env var (e.g., ``SCENARIO_GENERATOR_DEPLOYMENT``)
    while still falling through to shared fallbacks like
    ``AZURE_AI_CHAT_DEPLOYMENT``.

    Args:
        explicit: An explicit deployment name passed by the caller, or None.
        *env_var_names: Names of env vars to try in order, e.g.
            ``"SUSPECT_AGENT_DEPLOYMENT", "AZURE_AI_CHAT_DEPLOYMENT"``.
        default: Final fallback if no env var resolves.

    Returns:
        The resolved deployment name.
    """
    if explicit:
        return explicit
    for name in env_var_names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def load_prompt(path: Path) -> str:
    """Read an agent system prompt file with a clear error on missing.

    Args:
        path: Path to the prompt markdown file.

    Returns:
        The prompt file contents as a string.

    Raises:
        AgentClientError: If the file does not exist.
    """
    if not path.exists():
        raise AgentClientError(f"Prompt file not found at {path}")
    return path.read_text(encoding="utf-8")


def build_credential():
    """Build a token credential with stream-day-safe fallback chain.

    Tries credentials in this order:
      1. ``ClientSecretCredential`` (Service Principal) if ``AZURE_CLIENT_ID``,
         ``AZURE_CLIENT_SECRET``, and ``AZURE_TENANT_ID`` are all set in env.
         Non-interactive, persistent, no dependency on a working Azure CLI.
         Use this for live demos and any other workload that runs without a
         human at the keyboard.
      2. ``AzureCliCredential`` (requires ``az login``). Developer-friendly
         default for daily local work.

    DELIBERATELY OMITTED: ``ManagedIdentityCredential``. This app does not
    run inside Azure, so the IMDS probe at 169.254.169.254 just hangs for
    ~50 seconds before failing. Including it in the chain means every auth
    failure becomes a fifty-second user-visible hang. See the post-mortem
    referenced in the module docstring for the full story.

    Returns:
        Either a single credential (if only one path is available) or a
        ``ChainedTokenCredential`` wrapping both.

    Raises:
        AgentClientError: If ``azure-identity`` is not installed.
    """
    try:
        from azure.identity import (
            AzureCliCredential,
            ChainedTokenCredential,
            ClientSecretCredential,
        )
    except ImportError as exc:
        raise AgentClientError(
            "azure-identity package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    credentials = []

    client_id = os.environ.get("AZURE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("AZURE_CLIENT_SECRET", "").strip()
    tenant_id = os.environ.get("AZURE_TENANT_ID", "").strip()

    # All three Service Principal env vars must be present together. A
    # partial set is treated as "not configured" rather than "misconfigured"
    # because partial SP setup is a common .env mistake during development
    # and we want clean fallback to AzureCliCredential, not a crash.
    if client_id and client_secret and tenant_id:
        credentials.append(
            ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        )

    credentials.append(AzureCliCredential())

    if len(credentials) == 1:
        return credentials[0]
    return ChainedTokenCredential(*credentials)


def warm_up_auth() -> dict:
    """Pre-flight check: verify auth works AND prime the token cache.

    Forces a fresh token acquisition through the same code path the app
    uses at runtime (``build_credential()`` then ``get_token()``). This
    catches the failure mode where ``az login`` succeeded in the shell
    but the SDK cannot invoke the CLI from inside Python.

    The returned token is cached by the credential, so the first agent
    call after warm-up does not pay any auth latency cost.

    Returns:
        A dict with two keys:
            - ``credential_type`` (str): The class name of the credential
              that actually produced the token. ``ClientSecretCredential``
              indicates the Service Principal path resolved; ``AzureCliCredential``
              indicates the CLI fallback was used. For a chained credential,
              this is the type of the credential WITHIN the chain that
              succeeded (or the chain class itself if introspection fails).
            - ``expires_on`` (int): Unix timestamp when the token expires.
              Subtract from current time to get seconds remaining.

    Raises:
        AgentClientError: If token acquisition fails, with the credential
            type that was attempted included in the error message for
            quick triage.
    """
    credential = build_credential()
    credential_type = type(credential).__name__

    try:
        token = credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
    except Exception as exc:
        raise AgentClientError(
            f"Pre-flight auth check failed via {credential_type}: {exc}. "
            f"For live demos, set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, "
            f"and AZURE_TENANT_ID in .env to use a Service Principal. "
            f"For daily dev, run `az login`."
        ) from exc

    return {
        "credential_type": credential_type,
        "expires_on": token.expires_on,
    }


def build_azure_client():
    """Construct an AzureOpenAI client for the Foundry resource.

    Auth strategy (in order of preference):
      1. If ``AZURE_OPENAI_API_KEY`` is set in env, use it directly. This
         is the last-resort fallback that mirrors the dual-path pattern in
         ``_search_client.py``. Useful for live demos when Entra ID auth
         has failed entirely and recovery is impossible in the moment.
      2. Otherwise, use ``build_credential()`` which prefers a Service
         Principal (if env vars set) and falls back to ``AzureCliCredential``.

    Strips the ``/api/projects/...`` suffix from ``AZURE_AI_PROJECT_ENDPOINT``
    to derive the resource base URL. The OpenAI SDK appends
    ``/openai/deployments/<deployment>/chat/completions`` itself.

    Returns:
        An ``openai.AzureOpenAI`` client instance.

    Raises:
        AgentClientError: If required env vars are missing or required
            packages (openai, azure-identity) are not installed.
    """
    try:
        from openai import AzureOpenAI
    except ImportError as exc:
        raise AgentClientError(
            "openai package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    project_endpoint = require_env("AZURE_AI_PROJECT_ENDPOINT")
    resource_endpoint = project_endpoint.split("/api/projects/")[0].rstrip("/") + "/"
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)

    # Path 1: API key fallback. If set, skip Entra ID entirely.
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    if api_key:
        return AzureOpenAI(
            azure_endpoint=resource_endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    # Path 2: Entra ID via the explicit credential chain.
    try:
        from azure.identity import get_bearer_token_provider
    except ImportError as exc:
        raise AgentClientError(
            "azure-identity package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    token_provider = get_bearer_token_provider(
        build_credential(),
        "https://cognitiveservices.azure.com/.default",
    )

    return AzureOpenAI(
        azure_endpoint=resource_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def _smoke_test_warmup() -> int:
    """Run the pre-flight auth check and print the resolved credential.

    Returns 0 on success, 1 on any failure. Use as the stream-day
    pre-flight verification:

        python -m src.agents._azure_client

    Prints the credential type that resolved (ClientSecretCredential
    means SP path; AzureCliCredential means CLI path) and the token
    expiry as a Unix timestamp + minutes remaining. Use this output to
    decide whether the demo is on the safe path before going live.
    """
    import time

    print("Compliance Academy auth pre-flight check")
    print("=" * 60)

    try:
        info = warm_up_auth()
    except AgentClientError as exc:
        print(f"FAIL: {exc}")
        return 1

    now = int(time.time())
    minutes_left = max(0, (info["expires_on"] - now) // 60)

    print(f"OK    credential_type = {info['credential_type']}")
    print(f"      expires_on     = {info['expires_on']} "
          f"({minutes_left} minutes from now)")

    if info["credential_type"] == "ClientSecretCredential":
        print("      ✔ Service Principal path resolved. Safe for live demo.")
    elif info["credential_type"] == "AzureCliCredential":
        print("      ⚠ Azure CLI path resolved. Fine for daily dev, fragile")
        print("        for live demos. Consider setting AZURE_CLIENT_ID,")
        print("        AZURE_CLIENT_SECRET, and AZURE_TENANT_ID in .env to")
        print("        upgrade to the Service Principal path.")
    else:
        print(f"      ⚠ Unexpected credential type. Investigate before going live.")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_smoke_test_warmup())
