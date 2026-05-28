"""Discover the schema and contents of the Azure AI Search index.

Run once before wiring up the Foundry IQ retrieval layer. Prints:
    1. Index schema (field names, types, retrievability flags)
    2. Document count
    3. A sample document so we know what content looks like
    4. A sample retrieval query against likely-relevant terms

This lets us calibrate the production search client to the actual field
names in the index rather than guessing. The Azure indexer that built
the index chose those names when it crawled the docs (typically things
like ``content``, ``metadata_storage_name``, ``metadata_storage_path``
for the standard blob storage indexer, but other patterns exist).

Authentication: tries DefaultAzureCredential first (requires the user to
have ``Search Index Data Reader`` role on the search service). If that
fails, falls back to ``AZURE_SEARCH_ADMIN_KEY`` from the environment.

Usage:
    python -m scripts.discover_search_index

Required env vars:
    AZURE_SEARCH_ENDPOINT       e.g., https://<your-search-endpoint>.search.windows.net
    AZURE_SEARCH_INDEX_NAME     e.g., compliance-content-index
Optional:
    AZURE_SEARCH_ADMIN_KEY      admin key fallback if RBAC is not granted
    AZURE_SEARCH_API_VERSION    defaults to 2024-07-01
"""

from __future__ import annotations

import os
import sys
from typing import Any

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv()
except ImportError:
    pass


def _build_credential():
    """Try DefaultAzureCredential first; fall back to admin key if present.

    Returns:
        A tuple of (credential, label) where credential is either a
        ``DefaultAzureCredential`` instance or an ``AzureKeyCredential``
        and label is a human-readable description for logging.
    """
    admin_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "").strip()

    try:
        from azure.identity import DefaultAzureCredential
        cred = DefaultAzureCredential()
        # Don't validate eagerly; the actual search call will surface auth
        # failures with a clearer error than a token probe would.
        return cred, "DefaultAzureCredential (Entra ID via az login)"
    except ImportError:
        if not admin_key:
            print(
                "ERROR: azure-identity is not installed and AZURE_SEARCH_ADMIN_KEY "
                "is not set. Run: pip install -r requirements.txt"
            )
            sys.exit(1)

    if admin_key:
        from azure.core.credentials import AzureKeyCredential
        return AzureKeyCredential(admin_key), "AzureKeyCredential (admin key fallback)"

    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential(), "DefaultAzureCredential (Entra ID via az login)"


def main() -> int:
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").strip()
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "").strip()
    api_version = os.environ.get("AZURE_SEARCH_API_VERSION", "2024-07-01")
    admin_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "").strip()

    if not endpoint:
        print("ERROR: AZURE_SEARCH_ENDPOINT is not set in .env")
        return 1
    if not index_name:
        print("ERROR: AZURE_SEARCH_INDEX_NAME is not set in .env")
        return 1

    print("=" * 78)
    print("Azure AI Search index discovery")
    print("=" * 78)
    print(f"Endpoint:     {endpoint}")
    print(f"Index:        {index_name}")
    print(f"API version:  {api_version}")

    try:
        from azure.search.documents import SearchClient
        from azure.search.documents.indexes import SearchIndexClient
    except ImportError as exc:
        print(
            "\nERROR: azure-search-documents is not installed. "
            "Run: pip install -r requirements.txt"
        )
        print(f"      ({exc})")
        return 1

    credential, cred_label = _build_credential()
    print(f"Auth:         {cred_label}")
    print("-" * 78)

    # --- Step 1: Pull the index schema ---
    print("\n[1] Index schema")
    print("-" * 78)
    try:
        index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=credential,
            api_version=api_version,
        )
        index_def = index_client.get_index(index_name)
    except Exception as exc:
        print(f"FAIL: could not fetch index schema: {exc}")
        if "AuthorizationFailed" in str(exc) or "403" in str(exc):
            print()
            print(
                "Auth failure. Two options:\n"
                "  A) Assign yourself 'Search Index Data Reader' role on the\n"
                "     search service via portal > Access control (IAM), then re-run.\n"
                "  B) Add AZURE_SEARCH_ADMIN_KEY to .env (key from Keys panel),\n"
                "     then re-run. The script will use it as a fallback."
            )
        return 1

    print(f"Field count:  {len(index_def.fields)}")
    print()
    print(f"{'Name':<40} {'Type':<22} {'Retrievable':<12} {'Searchable'}")
    print("-" * 78)
    for f in index_def.fields:
        # Field.type may be a string like 'Edm.String' or a complex type.
        ftype = str(f.type) if hasattr(f, "type") else "?"
        retrievable = "yes" if getattr(f, "retrievable", True) else "no"
        searchable = "yes" if getattr(f, "searchable", False) else "no"
        print(f"{f.name:<40} {ftype:<22} {retrievable:<12} {searchable}")

    # --- Step 2: Document count ---
    print("\n[2] Document count")
    print("-" * 78)
    try:
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
            api_version=api_version,
        )
        count_results = search_client.search(
            search_text="*",
            include_total_count=True,
            top=0,
        )
        # Accessing .get_count() consumes the iterator; do it after iteration would
        # not work, so do it now while the result is open.
        total = count_results.get_count()
        print(f"Total documents in index: {total}")
    except Exception as exc:
        print(f"WARN: could not get document count: {exc}")
        total = None

    # --- Step 3: Sample one document ---
    print("\n[3] Sample document (first match)")
    print("-" * 78)
    try:
        sample_results = search_client.search(
            search_text="*",
            top=1,
        )
        sample = next(iter(sample_results), None)
        if sample is None:
            print("(no documents returned)")
        else:
            for k, v in sample.items():
                # Skip system fields starting with @ if any
                if k.startswith("@search"):
                    continue
                # Truncate long values for readability
                if isinstance(v, str) and len(v) > 200:
                    display = v[:200] + f"... [truncated, {len(v)} total chars]"
                elif isinstance(v, list) and len(v) > 5:
                    display = f"[list of {len(v)} items: {v[:3]}...]"
                else:
                    display = repr(v)
                print(f"  {k}: {display}")
    except Exception as exc:
        print(f"WARN: could not fetch sample document: {exc}")

    # --- Step 4: Test retrieval with a realistic query ---
    print("\n[4] Sample retrieval query")
    print("-" * 78)
    test_query = "MFA exception process"
    print(f"Query: {test_query!r} (top=3)")
    print()
    try:
        results = search_client.search(
            search_text=test_query,
            top=3,
        )
        for i, result in enumerate(results, 1):
            score = result.get("@search.score", "?")
            print(f"  Result {i}: score={score}")
            # Find the most content-like field and show a preview
            content_field = None
            for candidate in ("content", "chunk", "text", "body"):
                if candidate in result and isinstance(result[candidate], str):
                    content_field = candidate
                    break
            # Find the most source-like field
            source_field = None
            for candidate in ("metadata_storage_name", "source", "title", "filepath",
                              "metadata_storage_path"):
                if candidate in result and isinstance(result[candidate], str):
                    source_field = candidate
                    break

            if source_field:
                print(f"    source ({source_field}): {result[source_field]}")
            if content_field:
                preview = result[content_field][:300].replace("\n", " ")
                print(f"    content ({content_field}): {preview}...")
            else:
                print(f"    (no content-shaped field found; raw keys: "
                      f"{list(result.keys())})")
            print()
    except Exception as exc:
        print(f"WARN: sample query failed: {exc}")

    print("=" * 78)
    print("Discovery complete.")
    print()
    print("Paste this output back to Claude so the search client can be")
    print("calibrated to the actual field names in your index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
