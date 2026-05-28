"""Shared Azure OpenAI client setup for Compliance Academy agents.

Centralizes the Azure Foundry connection details so each agent module
(Scenario Generator, Suspect, Forensic Analyst, Compliance Officer) does
not need to duplicate authentication, deployment resolution, or prompt
loading logic.

Authentication:
    Uses Entra ID via DefaultAzureCredential. Run ``az login`` in your shell
    before invoking any agent. The credential chain resolves through Azure
    CLI, environment variables, managed identity, and other standard sources.

Environment variables (required by ``build_azure_client``):
    AZURE_AI_PROJECT_ENDPOINT
        e.g., https://sch-foundry-poc-eastus2.services.ai.azure.com/api/projects/sch-foundry-poc-eastus2

Environment variables (optional):
    AZURE_OPENAI_API_VERSION    defaults to '2024-10-21'

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


def build_azure_client():
    """Construct an AzureOpenAI client for the Foundry resource via Entra ID.

    Strips the ``/api/projects/...`` suffix from ``AZURE_AI_PROJECT_ENDPOINT``
    to derive the resource base URL, then authenticates via
    DefaultAzureCredential. The OpenAI SDK appends
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

    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as exc:
        raise AgentClientError(
            "azure-identity package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    project_endpoint = require_env("AZURE_AI_PROJECT_ENDPOINT")
    resource_endpoint = project_endpoint.split("/api/projects/")[0].rstrip("/") + "/"

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )

    return AzureOpenAI(
        azure_endpoint=resource_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION),
    )
