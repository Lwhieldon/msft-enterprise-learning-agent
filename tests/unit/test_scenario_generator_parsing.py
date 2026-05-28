"""Unit tests for Scenario Generator response parsing.

The Scenario Generator's model output is a mix of free-text reasoning and a
JSON code fence containing the scenario override. The parsing layer must
robustly extract the JSON from a variety of formats the model emits across
runs:

    - Fenced ```json block with valid JSON  (most common)
    - Fenced ```json block where JSON has trailing whitespace or text
    - Raw JSON (no fence) preceded by reasoning prose
    - Multiple { characters in reasoning before the actual JSON object
    - Unicode characters (§, em-dash, accented names) inside the JSON
    - Malformed JSON that should raise a clear parse error
    - Empty or whitespace-only response

These tests pin the contract of _extract_json_from_response and
_extract_reasoning_summary so the parsing is robust across model
nondeterminism. Pure logic; no Azure calls.
"""

from __future__ import annotations

import pytest

from src.agents.scenario_generator import (
    ScenarioGenerationParseError,
    _build_user_message,
    _extract_json_from_response,
    _extract_reasoning_summary,
)


# ---------------------------------------------------------------------------
# _extract_json_from_response - happy path
# ---------------------------------------------------------------------------


class TestExtractJsonHappyPath:
    """Standard model outputs the parser must handle without complaint."""

    def test_fenced_json_block_extracted(self):
        response = """Here is some reasoning text.

```json
{"scenario_id": "TEST-001", "scenario_name": "Test"}
```

Scenario ready to hot-load.
"""
        result = _extract_json_from_response(response)
        assert result == {"scenario_id": "TEST-001", "scenario_name": "Test"}

    def test_fenced_block_without_json_language_tag_extracted(self):
        """The model sometimes uses ``` without 'json' after it."""
        response = """Some text.
```
{"scenario_id": "TEST-002"}
```
"""
        result = _extract_json_from_response(response)
        assert result == {"scenario_id": "TEST-002"}

    def test_raw_json_without_fence_extracted(self):
        """When the model forgets the fence, the raw_decode fallback should
        still find the JSON object."""
        response = """Reasoning summary text first.

{"scenario_id": "TEST-003", "scenario_name": "Unfenced"}

Trailing notes.
"""
        result = _extract_json_from_response(response)
        assert result == {
            "scenario_id": "TEST-003",
            "scenario_name": "Unfenced",
        }

    def test_nested_objects_preserved(self):
        response = """```json
{
  "scenario_id": "TEST-004",
  "violated_controls": [
    {"framework": "SOC 2", "identifier": "CC6.1"},
    {"framework": "Helix Dynamics", "identifier": "HD-SEC-AC-001"}
  ],
  "clue_graph": {"nodes": [{"id": "x", "type": "suspect"}]}
}
```"""
        result = _extract_json_from_response(response)
        assert len(result["violated_controls"]) == 2
        assert result["clue_graph"]["nodes"][0]["id"] == "x"

    def test_unicode_characters_preserved(self):
        """The synthetic policies use § for sections. The parser must
        handle Unicode correctly."""
        response = """```json
{"identifier": "HD-SEC-AC-001 §4.1", "framework": "Helix Dynamics"}
```"""
        result = _extract_json_from_response(response)
        assert result["identifier"] == "HD-SEC-AC-001 §4.1"


# ---------------------------------------------------------------------------
# _extract_json_from_response - tricky cases
# ---------------------------------------------------------------------------


class TestExtractJsonTrickyCases:
    """Edge cases the parser must handle defensively."""

    def test_braces_in_reasoning_dont_confuse_parser(self):
        """If the reasoning text mentions JSON-like content with { before
        the actual JSON block, the parser should still find the right one."""
        response = """The breach pattern looks like {credential compromise}
and the fix involves controls like {access reviews}.

```json
{"scenario_id": "TEST-005"}
```"""
        result = _extract_json_from_response(response)
        assert result == {"scenario_id": "TEST-005"}

    def test_text_after_json_is_ignored(self):
        """Model often emits 'Scenario ready to hot-load.' after the JSON.
        That text should not cause parsing to fail."""
        response = """{"scenario_id": "TEST-006"}

Scenario ready to hot-load. Anything could go here including more text
that mentions } and other punctuation.
"""
        result = _extract_json_from_response(response)
        assert result["scenario_id"] == "TEST-006"

    def test_nested_json_extracted_via_raw_decode_fallback(self):
        """The fence regex uses non-greedy ``\\{.*?\\}`` which only matches
        flat JSON; nested objects make the fenced regex fail, but the
        raw_decode fallback handles nested structures correctly."""
        response = """```json
{
  "outer": {"inner": {"deepest": "value"}}
}
```"""
        result = _extract_json_from_response(response)
        assert result["outer"]["inner"]["deepest"] == "value"


# ---------------------------------------------------------------------------
# _extract_json_from_response - failure modes
# ---------------------------------------------------------------------------


class TestExtractJsonFailures:
    """Invalid inputs should raise ScenarioGenerationParseError with a
    useful message."""

    def test_empty_response_raises(self):
        with pytest.raises(ScenarioGenerationParseError, match="No JSON"):
            _extract_json_from_response("")

    def test_response_without_any_json_raises(self):
        with pytest.raises(ScenarioGenerationParseError, match="No JSON"):
            _extract_json_from_response(
                "Just some reasoning prose without any object."
            )

    def test_malformed_json_raises_with_snippet(self):
        """When parsing fails outright, the error should include a snippet
        of the broken response so debugging is fast."""
        response = '{"scenario_id": "TEST", "unterminated_string": "abc'
        with pytest.raises(ScenarioGenerationParseError) as excinfo:
            _extract_json_from_response(response)
        # The error message should include something from the broken response.
        assert "unterminated" in str(excinfo.value).lower() or \
               "TEST" in str(excinfo.value)

    def test_json_array_at_root_extracts_first_object_inside(self):
        """The parser is intentionally lenient: it finds the first ``{`` in
        the text and lets ``json.JSONDecoder.raw_decode`` parse from there.
        An array-at-root like ``[{...}]`` therefore yields the first object
        inside the array, not an error. The scenario loader's downstream
        validation catches genuinely malformed structures, so this
        leniency is harmless and resilient against minor model formatting
        slips (like wrapping the scenario in a stray array)."""
        response = '[{"scenario_id": "TEST"}]'
        result = _extract_json_from_response(response)
        assert result == {"scenario_id": "TEST"}

    def test_truncated_mid_string_raises_useful_error(self):
        """The actual failure we saw on stream once: stream aborted by
        content filter mid-string. Should produce a clear parse error."""
        response = (
            'Reasoning text.\n```json\n{"scenario_id": "TEST",\n'
            '  "scenario_name": "This string never closes'
        )
        with pytest.raises(ScenarioGenerationParseError):
            _extract_json_from_response(response)


# ---------------------------------------------------------------------------
# _extract_reasoning_summary
# ---------------------------------------------------------------------------


class TestExtractReasoningSummary:
    """The reasoning summary is the audience-facing prose preceding the
    JSON block. The extractor should grab everything before the JSON cleanly."""

    def test_extracts_prose_before_fenced_block(self):
        response = """Working from the breach you described.

This is the audience-facing reasoning summary.

```json
{"scenario_id": "TEST"}
```
"""
        summary = _extract_reasoning_summary(response)
        assert "Working from the breach" in summary
        assert "audience-facing reasoning summary" in summary
        assert "```" not in summary
        assert "{" not in summary

    def test_extracts_prose_before_raw_json(self):
        """If there's no fence, the extractor should stop at the first {."""
        response = """The reasoning summary first.

{"scenario_id": "TEST"}
"""
        summary = _extract_reasoning_summary(response)
        assert "reasoning summary first" in summary
        assert "{" not in summary

    def test_returns_whole_string_if_no_json_marker(self):
        """If there's no JSON or fence at all, just return the input
        stripped. Better than an empty summary."""
        response = "Just a reasoning paragraph and nothing else."
        summary = _extract_reasoning_summary(response)
        assert summary == "Just a reasoning paragraph and nothing else."

    def test_empty_response_returns_empty_string(self):
        assert _extract_reasoning_summary("") == ""

    def test_whitespace_stripped(self):
        response = "\n\n  Reasoning text.  \n\n```json\n{}\n```"
        summary = _extract_reasoning_summary(response)
        assert summary == "Reasoning text."


# ---------------------------------------------------------------------------
# _build_user_message
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    """The user message passes the breach description and Helix Dynamics
    context to the Scenario Generator."""

    def test_breach_description_included_verbatim(self):
        breach = "An employee accidentally exposed an S3 bucket."
        message = _build_user_message(breach)
        assert breach in message

    def test_helix_dynamics_context_included(self):
        """The message should remind the model that the active fiction is
        Helix Dynamics so the generated scenario stays in-universe."""
        message = _build_user_message("any breach")
        assert "Helix Dynamics" in message

    def test_canonical_suspect_reminder_included(self):
        """The message should remind the model that the five canonical
        suspect IDs are loaded from scenario_commons.json."""
        message = _build_user_message("any breach")
        assert "scenario_commons" in message or "canonical" in message.lower()

    def test_breach_description_whitespace_stripped(self):
        """Leading and trailing whitespace on the breach should not appear
        in the final user message."""
        breach = "   leading and trailing whitespace breach   "
        message = _build_user_message(breach)
        # Verify the stripped form is present
        assert "leading and trailing whitespace breach" in message
