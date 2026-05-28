"""Unit tests for ``src.agents._azure_client`` helpers.

The shared Azure client module is touched by every agent wrapper, so its
contract needs to be pinned. The three pure-Python helpers
(``require_env``, ``resolve_deployment``, ``load_prompt``) are easy to
unit-test; the ``build_azure_client`` factory requires real Azure SDK
imports and is exercised by the integration tests instead.

These tests use pytest's ``monkeypatch`` fixture to isolate the environment
so .env values do not pollute the test run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agents._azure_client import (
    DEFAULT_API_VERSION,
    DEFAULT_DEPLOYMENT,
    AgentClientError,
    load_prompt,
    require_env,
    resolve_deployment,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """Constants other modules import from this one. Changes break callers
    silently if uncaught."""

    def test_default_deployment_is_gpt_4_1_mini(self):
        # The live demo budget depends on this default. If we ever change
        # it, we want it to be a conscious choice flagged by a test failure.
        assert DEFAULT_DEPLOYMENT == "gpt-4.1-mini"

    def test_default_api_version_is_set(self):
        # Should be a valid YYYY-MM-DD or YYYY-MM-DD-preview string.
        assert DEFAULT_API_VERSION
        assert DEFAULT_API_VERSION[:4].isdigit()


# ---------------------------------------------------------------------------
# require_env
# ---------------------------------------------------------------------------


class TestRequireEnv:
    """Read a required env var with a clear error on missing/empty."""

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_PRESENT", "the value")
        assert require_env("TEST_VAR_PRESENT") == "the value"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR_MISSING", raising=False)
        with pytest.raises(AgentClientError, match="TEST_VAR_MISSING"):
            require_env("TEST_VAR_MISSING")

    def test_raises_when_empty_string(self, monkeypatch):
        """Empty string is treated as missing; users routinely forget to fill
        in .env values."""
        monkeypatch.setenv("TEST_VAR_EMPTY", "")
        with pytest.raises(AgentClientError, match="TEST_VAR_EMPTY"):
            require_env("TEST_VAR_EMPTY")

    def test_error_message_mentions_env_var_name(self, monkeypatch):
        """The error message should tell the operator WHICH env var is
        missing so debugging is fast."""
        monkeypatch.delenv("VERY_SPECIFIC_NAME_XYZ", raising=False)
        with pytest.raises(AgentClientError) as excinfo:
            require_env("VERY_SPECIFIC_NAME_XYZ")
        assert "VERY_SPECIFIC_NAME_XYZ" in str(excinfo.value)
        # Should also hint at where to fix it
        assert ".env" in str(excinfo.value).lower() or \
               "environment" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# resolve_deployment
# ---------------------------------------------------------------------------


class TestResolveDeployment:
    """Precedence chain: explicit arg > env vars in order > default."""

    def test_explicit_value_wins_over_env_vars(self, monkeypatch):
        monkeypatch.setenv("VAR_A", "from-env-a")
        monkeypatch.setenv("VAR_B", "from-env-b")
        result = resolve_deployment(
            "explicit-deployment", "VAR_A", "VAR_B", default="default-dep"
        )
        assert result == "explicit-deployment"

    def test_explicit_none_falls_through_to_env(self, monkeypatch):
        monkeypatch.setenv("VAR_A", "from-env-a")
        result = resolve_deployment(None, "VAR_A", default="default-dep")
        assert result == "from-env-a"

    def test_first_env_var_in_order_wins(self, monkeypatch):
        """If multiple env vars are set, the first one in the precedence
        chain should win, not the last."""
        monkeypatch.setenv("VAR_FIRST", "winner")
        monkeypatch.setenv("VAR_SECOND", "loser")
        result = resolve_deployment(
            None, "VAR_FIRST", "VAR_SECOND", default="default-dep"
        )
        assert result == "winner"

    def test_falls_to_second_env_var_if_first_missing(self, monkeypatch):
        monkeypatch.delenv("VAR_FIRST", raising=False)
        monkeypatch.setenv("VAR_SECOND", "second-wins")
        result = resolve_deployment(
            None, "VAR_FIRST", "VAR_SECOND", default="default-dep"
        )
        assert result == "second-wins"

    def test_default_used_when_all_env_vars_missing(self, monkeypatch):
        monkeypatch.delenv("VAR_A", raising=False)
        monkeypatch.delenv("VAR_B", raising=False)
        result = resolve_deployment(
            None, "VAR_A", "VAR_B", default="my-default"
        )
        assert result == "my-default"

    def test_default_used_when_all_env_vars_empty(self, monkeypatch):
        """Empty string env var should be treated as missing, not as a
        valid deployment name."""
        monkeypatch.setenv("VAR_A", "")
        monkeypatch.setenv("VAR_B", "")
        result = resolve_deployment(
            None, "VAR_A", "VAR_B", default="my-default"
        )
        assert result == "my-default"

    def test_no_env_vars_and_no_default_uses_module_default(self, monkeypatch):
        """If called with no env vars and no explicit default, it should
        fall back to DEFAULT_DEPLOYMENT (gpt-4.1-mini)."""
        result = resolve_deployment(None)
        assert result == DEFAULT_DEPLOYMENT

    def test_empty_string_explicit_falls_through(self, monkeypatch):
        """Passing explicit='' should be treated as no explicit (falsy),
        not as 'use empty string as deployment'."""
        monkeypatch.setenv("VAR_A", "from-env")
        result = resolve_deployment("", "VAR_A", default="default-dep")
        assert result == "from-env"


# ---------------------------------------------------------------------------
# load_prompt
# ---------------------------------------------------------------------------


class TestLoadPrompt:
    """Reading prompt files: returns content for existing files, raises for
    missing ones."""

    def test_returns_content_for_existing_file(self, tmp_path):
        prompt_file = tmp_path / "test_prompt.md"
        prompt_file.write_text("This is the prompt content.", encoding="utf-8")
        result = load_prompt(prompt_file)
        assert result == "This is the prompt content."

    def test_raises_for_missing_file(self, tmp_path):
        missing = tmp_path / "does_not_exist.md"
        with pytest.raises(AgentClientError, match="not found"):
            load_prompt(missing)

    def test_error_includes_path_for_debugging(self, tmp_path):
        missing = tmp_path / "very_specific_filename.md"
        with pytest.raises(AgentClientError) as excinfo:
            load_prompt(missing)
        assert "very_specific_filename.md" in str(excinfo.value)

    def test_preserves_utf8_content(self, tmp_path):
        """Prompts contain Unicode (§, em-dashes, accented names); the
        loader should preserve them."""
        prompt_file = tmp_path / "unicode_prompt.md"
        content = "Section §4.1 references HD-SEC-AC-001 § policy."
        prompt_file.write_text(content, encoding="utf-8")
        result = load_prompt(prompt_file)
        assert "§4.1" in result
        assert "§ policy" in result

    def test_preserves_multiline_content(self, tmp_path):
        prompt_file = tmp_path / "multiline.md"
        content = "Line 1\nLine 2\n\nLine 4 after blank."
        prompt_file.write_text(content, encoding="utf-8")
        result = load_prompt(prompt_file)
        assert result == content
