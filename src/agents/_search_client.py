"""Shared Azure AI Search client for Foundry IQ retrieval grounding.

Wraps the ``compliance-content-index`` Azure Search index with a Python
interface that the Forensic Analyst and Compliance Officer agents call
before invoking their model. The retrieved snippets are injected into
the agent's user message as grounding context, so citations come from
real indexed policy and framework text rather than from the model's
training data alone.

Index schema (compliance-content-index):
    uid                     unique chunk ID
    snippet_parent_id       which source doc the chunk belongs to
    blob_url                URL of the source document (used for citations)
    snippet                 the actual content text  (searchable)
    image_snippet_parent_id (not used here)
    snippet_vector          Collection(Edm.Single)  (hybrid search; not used yet)

Authentication:
    Tries Entra ID via DefaultAzureCredential first (requires the user to
    have ``Search Index Data Reader`` role on the search service). Falls
    back to the admin key from ``AZURE_SEARCH_ADMIN_KEY`` env var if that
    is set. Raises ``SearchClientError`` if neither path works.

Environment variables (required):
    AZURE_SEARCH_ENDPOINT       e.g., https://<your-search-endpoint>.search.windows.net
    AZURE_SEARCH_INDEX_NAME     e.g., compliance-content-index

Environment variables (optional):
    AZURE_SEARCH_API_VERSION    defaults to '2024-07-01'
    AZURE_SEARCH_ADMIN_KEY      admin key fallback if RBAC is not granted

Public API:
    build_search_client() -> SearchClient
        Construct an authenticated client against the index.

    retrieve_context(query, top_k=5) -> list[dict]
        Run a keyword search against ``snippet``; return the top-k results
        as a list of dicts with uid, snippet, source_url, score.

    format_retrieved_context(retrievals) -> str
        Render the retrieval results as a structured text block ready to
        inject into an agent user message. Includes source citations.
"""

from __future__ import annotations

import os
from typing import Any

# Best-effort .env loading so CLI smoke tests pick up Azure credentials.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv()
except ImportError:
    pass


#: Default API version for Azure AI Search queries.
DEFAULT_API_VERSION: str = "2024-07-01"

#: Default index name. Overridden by AZURE_SEARCH_INDEX_NAME env var.
DEFAULT_INDEX_NAME: str = "compliance-content-index"

#: Default number of snippets to retrieve per call. Five is enough to give
#: an agent meaningful grounding without bloating the user message.
DEFAULT_TOP_K: int = 5

#: Field names in the compliance-content-index. Pinned here so a schema
#: change forces a deliberate update rather than silently degrading
#: retrieval quality.
FIELD_UID: str = "uid"
FIELD_SNIPPET: str = "snippet"
FIELD_BLOB_URL: str = "blob_url"
FIELD_PARENT_ID: str = "snippet_parent_id"


class SearchClientError(Exception):
    """Raised for search client setup or query failures."""


def _build_credential():
    """Build an Azure Search credential.

    Tries DefaultAzureCredential first (requires Search Index Data Reader
    role on the search service); falls back to AzureKeyCredential using
    AZURE_SEARCH_ADMIN_KEY if set. Returns the credential object.
    """
    admin_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "").strip()

    if admin_key:
        try:
            from azure.core.credentials import AzureKeyCredential
        except ImportError as exc:
            raise SearchClientError(
                "azure-core is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc
        return AzureKeyCredential(admin_key)

    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise SearchClientError(
            "azure-identity is not installed and AZURE_SEARCH_ADMIN_KEY "
            "is not set. Run: pip install -r requirements.txt"
        ) from exc
    return DefaultAzureCredential()


def build_search_client():
    """Construct an authenticated SearchClient against the configured index.

    Returns:
        An ``azure.search.documents.SearchClient`` instance pointed at the
        index named by ``AZURE_SEARCH_INDEX_NAME`` (or the default).

    Raises:
        SearchClientError: If required env vars or packages are missing.
    """
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").strip()
    if not endpoint:
        raise SearchClientError(
            "AZURE_SEARCH_ENDPOINT is not set. Add it to your .env file."
        )

    index_name = os.environ.get(
        "AZURE_SEARCH_INDEX_NAME", DEFAULT_INDEX_NAME
    ).strip()
    api_version = os.environ.get(
        "AZURE_SEARCH_API_VERSION", DEFAULT_API_VERSION
    ).strip()

    try:
        from azure.search.documents import SearchClient
    except ImportError as exc:
        raise SearchClientError(
            "azure-search-documents is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    credential = _build_credential()

    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential,
        api_version=api_version,
    )


def retrieve_context(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    *,
    client: Any = None,
) -> list[dict[str, Any]]:
    """Retrieve the top-k most relevant snippets for a query.

    Runs a keyword search against the ``snippet`` field. Returns a list
    of dicts ready for downstream formatting.

    Args:
        query: Free-text query string. Player question, control identifier,
            scenario keyword, etc.
        top_k: Maximum number of snippets to return. Defaults to 5.
        client: Optional pre-built SearchClient for test injection. If not
            provided, a fresh one is built from env vars.

    Returns:
        List of dicts, each with keys:
            - ``uid`` (str): unique chunk ID
            - ``snippet`` (str): the content text
            - ``source_url`` (str): URL of the source document
            - ``parent_id`` (str): which source doc the chunk belongs to
            - ``score`` (float): relevance score from the search engine

        Returns an empty list if no results match (NOT an error condition;
        the agent should still answer using the scenario JSON it already
        has).

    Raises:
        SearchClientError: For client setup failures or query exceptions.
    """
    if not query or not query.strip():
        return []
    if top_k < 1:
        return []

    if client is None:
        client = build_search_client()

    try:
        results = client.search(
            search_text=query.strip(),
            top=top_k,
            select=[FIELD_UID, FIELD_SNIPPET, FIELD_BLOB_URL, FIELD_PARENT_ID],
        )
    except Exception as exc:
        raise SearchClientError(
            f"Azure Search query failed for query={query!r}: {exc}"
        ) from exc

    out: list[dict[str, Any]] = []
    for r in results:
        out.append({
            "uid": r.get(FIELD_UID, ""),
            "snippet": r.get(FIELD_SNIPPET, ""),
            "source_url": r.get(FIELD_BLOB_URL, ""),
            "parent_id": r.get(FIELD_PARENT_ID, ""),
            "score": float(r.get("@search.score", 0.0)),
        })
    return out


def _source_name_from_url(blob_url: str) -> str:
    """Extract a human-readable source name from a blob URL.

    e.g., 'https://schhelixacademy.blob.core.windows.net/foundry-iq-source/
    HD-SEC-AC-001-Access-Control-Policy.md' -> 'HD-SEC-AC-001-Access-Control-Policy.md'

    Falls back to '(unknown source)' if the URL is empty or malformed.
    """
    if not blob_url:
        return "(unknown source)"
    # Take the last path segment after '/', strip any query string.
    name = blob_url.rsplit("/", 1)[-1]
    if "?" in name:
        name = name.split("?", 1)[0]
    return name or "(unknown source)"


def format_retrieved_context(
    retrievals: list[dict[str, Any]],
    *,
    max_snippet_chars: int = 1200,
) -> str:
    """Render retrieved snippets as a text block for an agent user message.

    Each snippet is preceded by a citation header naming the source file,
    so the agent can cite specific policy documents in its response.
    Snippets longer than ``max_snippet_chars`` are truncated with an
    ellipsis indicator.

    Args:
        retrievals: List of retrieval result dicts (output of
            ``retrieve_context``).
        max_snippet_chars: Maximum characters per snippet body. Defaults to
            1200, which keeps a 5-result block under ~6000 chars total.

    Returns:
        A multi-line string ready to inject into a user message. Empty
        string if no retrievals were provided.
    """
    if not retrievals:
        return ""

    lines: list[str] = []
    for i, r in enumerate(retrievals, start=1):
        source = _source_name_from_url(r.get("source_url", ""))
        snippet_text = (r.get("snippet") or "").strip()
        if len(snippet_text) > max_snippet_chars:
            snippet_text = (
                snippet_text[:max_snippet_chars]
                + f"... [truncated, {len(r['snippet'])} chars total]"
            )
        lines.append(f"[Source {i}: {source}]")
        lines.append(snippet_text)
        lines.append("")  # blank line between sources
    # Trim trailing blank line for cleaner injection.
    return "\n".join(lines).rstrip()
