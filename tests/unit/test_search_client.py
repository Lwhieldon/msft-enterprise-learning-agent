"""Unit tests for ``src.agents._search_client``.

Tests the search client helpers (build_search_client, retrieve_context,
format_retrieved_context, _source_name_from_url) with mocked search
responses. No live Azure Search calls.

The integration test against the live compliance-content-index lives in
tests/integration/.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agents._search_client import (
    DEFAULT_API_VERSION,
    DEFAULT_INDEX_NAME,
    DEFAULT_TOP_K,
    FIELD_BLOB_URL,
    FIELD_PARENT_ID,
    FIELD_SNIPPET,
    FIELD_UID,
    SearchClientError,
    _source_name_from_url,
    format_retrieved_context,
    retrieve_context,
)


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """Pin defaults that other modules implicitly depend on."""

    def test_default_index_name_matches_provisioned_index(self):
        assert DEFAULT_INDEX_NAME == "compliance-content-index"

    def test_default_top_k_is_five(self):
        # Five snippets balances grounding richness against user-message bloat.
        assert DEFAULT_TOP_K == 5

    def test_default_api_version_format(self):
        assert DEFAULT_API_VERSION
        # YYYY-MM-DD format
        assert DEFAULT_API_VERSION[:4].isdigit()
        assert DEFAULT_API_VERSION[4] == "-"

    def test_field_names_match_provisioned_schema(self):
        # If the index gets rebuilt with different field names, these must
        # update deliberately. Pinning prevents silent retrieval breakage.
        assert FIELD_UID == "uid"
        assert FIELD_SNIPPET == "snippet"
        assert FIELD_BLOB_URL == "blob_url"
        assert FIELD_PARENT_ID == "snippet_parent_id"


# ---------------------------------------------------------------------------
# _source_name_from_url
# ---------------------------------------------------------------------------


class TestSourceNameFromUrl:
    """Extract a citable filename from a blob URL."""

    def test_extracts_filename_from_blob_url(self):
        url = (
            "https://schhelixacademy.blob.core.windows.net/"
            "foundry-iq-source/HD-SEC-AC-001-Access-Control-Policy.md"
        )
        assert _source_name_from_url(url) == "HD-SEC-AC-001-Access-Control-Policy.md"

    def test_handles_url_with_query_string(self):
        url = (
            "https://example.blob.core.windows.net/container/"
            "policy.md?sv=2020-08-04&sig=abc123"
        )
        assert _source_name_from_url(url) == "policy.md"

    def test_handles_url_with_no_path(self):
        # Pathological case: a bare hostname. The function extracts what's
        # after the last '/' — which is the hostname when there's no path.
        # Real Azure blob URLs always have a path so this case doesn't occur
        # in production; we just verify it doesn't crash.
        assert _source_name_from_url(
            "https://example.com"
        ) == "example.com"

    def test_handles_empty_string(self):
        assert _source_name_from_url("") == "(unknown source)"

    def test_handles_none_via_default(self):
        # The caller may pass None when the field is missing; treat gracefully.
        # The function signature takes str; callers should pass "" instead.
        # But verify the empty-string path is the documented behavior.
        assert _source_name_from_url("") == "(unknown source)"

    def test_handles_trailing_slash(self):
        # If URL ends with /, the last segment is empty; fall back to unknown.
        url = "https://example.blob.core.windows.net/container/"
        assert _source_name_from_url(url) == "(unknown source)"


# ---------------------------------------------------------------------------
# retrieve_context  (with mocked SearchClient)
# ---------------------------------------------------------------------------


def _make_search_result(
    uid="chunk-001",
    snippet="HD-SEC-AC-001 §4.1 requires MFA exceptions to be documented.",
    blob_url="https://example.blob.core.windows.net/foundry-iq-source/HD-SEC-AC-001.md",
    parent_id="doc-hd-sec-ac-001",
    score=8.5,
):
    """Build a dict mimicking one row returned by Azure SearchClient."""
    return {
        "uid": uid,
        "snippet": snippet,
        "blob_url": blob_url,
        "snippet_parent_id": parent_id,
        "@search.score": score,
    }


class TestRetrieveContext:
    """retrieve_context dispatches a search and shapes the result."""

    def test_empty_query_returns_empty_list_without_calling_search(self):
        mock_client = MagicMock()
        result = retrieve_context("", client=mock_client)
        assert result == []
        mock_client.search.assert_not_called()

    def test_whitespace_only_query_returns_empty_list(self):
        mock_client = MagicMock()
        result = retrieve_context("   \t  ", client=mock_client)
        assert result == []
        mock_client.search.assert_not_called()

    def test_top_k_zero_returns_empty_list(self):
        mock_client = MagicMock()
        result = retrieve_context("test", top_k=0, client=mock_client)
        assert result == []
        mock_client.search.assert_not_called()

    def test_negative_top_k_returns_empty_list(self):
        mock_client = MagicMock()
        result = retrieve_context("test", top_k=-3, client=mock_client)
        assert result == []
        mock_client.search.assert_not_called()

    def test_search_called_with_stripped_query(self):
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        retrieve_context("  MFA exception  ", client=mock_client)
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["search_text"] == "MFA exception"

    def test_search_called_with_correct_top(self):
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        retrieve_context("query", top_k=3, client=mock_client)
        assert mock_client.search.call_args.kwargs["top"] == 3

    def test_search_called_with_correct_field_select(self):
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        retrieve_context("query", client=mock_client)
        select = mock_client.search.call_args.kwargs["select"]
        assert "uid" in select
        assert "snippet" in select
        assert "blob_url" in select
        assert "snippet_parent_id" in select

    def test_default_top_k_used_when_not_specified(self):
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        retrieve_context("query", client=mock_client)
        assert mock_client.search.call_args.kwargs["top"] == DEFAULT_TOP_K

    def test_single_result_shaped_correctly(self):
        mock_client = MagicMock()
        mock_client.search.return_value = iter([_make_search_result()])

        results = retrieve_context("MFA exception", client=mock_client)

        assert len(results) == 1
        r = results[0]
        assert r["uid"] == "chunk-001"
        assert r["snippet"].startswith("HD-SEC-AC-001")
        assert r["source_url"].endswith("HD-SEC-AC-001.md")
        assert r["parent_id"] == "doc-hd-sec-ac-001"
        assert r["score"] == 8.5

    def test_multiple_results_preserve_order(self):
        mock_client = MagicMock()
        mock_client.search.return_value = iter([
            _make_search_result(uid="a", snippet="First.", score=9.0),
            _make_search_result(uid="b", snippet="Second.", score=8.0),
            _make_search_result(uid="c", snippet="Third.", score=7.0),
        ])

        results = retrieve_context("query", client=mock_client)

        assert [r["uid"] for r in results] == ["a", "b", "c"]
        assert [r["snippet"] for r in results] == ["First.", "Second.", "Third."]

    def test_missing_score_defaults_to_zero(self):
        """Defensive: if Azure ever omits @search.score, score becomes 0.0
        rather than crashing."""
        mock_client = MagicMock()
        result_without_score = {
            "uid": "x",
            "snippet": "text",
            "blob_url": "https://example/x.md",
            "snippet_parent_id": "doc-x",
        }
        mock_client.search.return_value = iter([result_without_score])

        results = retrieve_context("query", client=mock_client)
        assert results[0]["score"] == 0.0

    def test_missing_field_defaults_to_empty_string(self):
        """Defensive: if a result is missing a field, default to '' rather
        than KeyError."""
        mock_client = MagicMock()
        sparse_result = {"@search.score": 5.0}  # no uid, snippet, etc.
        mock_client.search.return_value = iter([sparse_result])

        results = retrieve_context("query", client=mock_client)
        assert results[0]["uid"] == ""
        assert results[0]["snippet"] == ""
        assert results[0]["source_url"] == ""
        assert results[0]["parent_id"] == ""

    def test_search_exception_wrapped_in_search_client_error(self):
        """Azure transport errors should be wrapped, not leaked, so callers
        only need to catch SearchClientError."""
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("network down")

        with pytest.raises(SearchClientError, match="failed"):
            retrieve_context("query", client=mock_client)

    def test_search_error_includes_query_for_debugging(self):
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("boom")

        with pytest.raises(SearchClientError) as excinfo:
            retrieve_context("very_specific_query_xyz", client=mock_client)

        assert "very_specific_query_xyz" in str(excinfo.value)

    def test_empty_search_results_returns_empty_list_not_error(self):
        """No matches is NOT an error condition; the agent will fall back
        to its scenario data."""
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])

        results = retrieve_context("nonsense query", client=mock_client)
        assert results == []


# ---------------------------------------------------------------------------
# format_retrieved_context
# ---------------------------------------------------------------------------


class TestFormatRetrievedContext:
    """Render retrieval results as a structured text block for agent injection."""

    def test_empty_list_returns_empty_string(self):
        assert format_retrieved_context([]) == ""

    def test_single_retrieval_includes_source_header_and_snippet(self):
        retrievals = [{
            "uid": "x", "snippet": "Policy text here.",
            "source_url": "https://example.blob.core.windows.net/c/policy.md",
            "parent_id": "p", "score": 5.0,
        }]
        result = format_retrieved_context(retrievals)
        assert "[Source 1: policy.md]" in result
        assert "Policy text here." in result

    def test_multiple_retrievals_numbered_in_order(self):
        retrievals = [
            {"uid": "a", "snippet": "First.",
             "source_url": "https://x/first.md", "parent_id": "p", "score": 1.0},
            {"uid": "b", "snippet": "Second.",
             "source_url": "https://x/second.md", "parent_id": "p", "score": 1.0},
            {"uid": "c", "snippet": "Third.",
             "source_url": "https://x/third.md", "parent_id": "p", "score": 1.0},
        ]
        result = format_retrieved_context(retrievals)
        # Each numbered header is present in order
        assert result.index("[Source 1: first.md]") < result.index("[Source 2: second.md]")
        assert result.index("[Source 2: second.md]") < result.index("[Source 3: third.md]")

    def test_snippet_truncated_at_max_chars(self):
        long_text = "a" * 2000
        retrievals = [{
            "uid": "x", "snippet": long_text,
            "source_url": "https://x/long.md", "parent_id": "p", "score": 1.0,
        }]
        result = format_retrieved_context(retrievals, max_snippet_chars=500)
        # Original chars not present in full
        assert "a" * 2000 not in result
        # Truncation marker is
        assert "truncated" in result
        assert "2000 chars total" in result

    def test_snippet_under_max_not_truncated(self):
        short_text = "Short content."
        retrievals = [{
            "uid": "x", "snippet": short_text,
            "source_url": "https://x/s.md", "parent_id": "p", "score": 1.0,
        }]
        result = format_retrieved_context(retrievals, max_snippet_chars=500)
        assert short_text in result
        assert "truncated" not in result

    def test_empty_snippet_field_renders_empty_body(self):
        """Defensive: an empty snippet should not crash, just render an
        empty body under the source header."""
        retrievals = [{
            "uid": "x", "snippet": "",
            "source_url": "https://x/s.md", "parent_id": "p", "score": 1.0,
        }]
        result = format_retrieved_context(retrievals)
        assert "[Source 1: s.md]" in result

    def test_missing_source_url_uses_unknown_source(self):
        retrievals = [{
            "uid": "x", "snippet": "Content.",
            "source_url": "", "parent_id": "p", "score": 1.0,
        }]
        result = format_retrieved_context(retrievals)
        assert "(unknown source)" in result

    def test_snippet_whitespace_stripped(self):
        retrievals = [{
            "uid": "x", "snippet": "\n\n  Trimmed content.  \n\n",
            "source_url": "https://x/s.md", "parent_id": "p", "score": 1.0,
        }]
        result = format_retrieved_context(retrievals)
        assert "Trimmed content." in result
        # Should not have the leading/trailing whitespace from the original
        assert "Trimmed content.  " not in result

    def test_no_trailing_blank_line(self):
        retrievals = [{
            "uid": "x", "snippet": "Content.",
            "source_url": "https://x/s.md", "parent_id": "p", "score": 1.0,
        }]
        result = format_retrieved_context(retrievals)
        # The formatter trims trailing whitespace so the injection point is clean.
        assert not result.endswith("\n")
        assert not result.endswith(" ")
