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
from unittest.mock import MagicMock, patch

import pytest

from src.agents._azure_client import (
    DEFAULT_API_VERSION,
    DEFAULT_DEPLOYMENT,
    AgentClientError,
    build_azure_client,
    build_credential,
    load_prompt,
    require_env,
    resolve_deployment,
    warm_up_auth,
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


# ---------------------------------------------------------------------------
# build_credential  (the explicit credential chain, post-mortem hardening)
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_auth_env(monkeypatch):
    """Ensure none of the auth-related env vars leak between tests.

    Tests that want SP env vars set should populate them via monkeypatch.
    Tests that want them absent get the empty state from this fixture.
    """
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)


class TestBuildCredential:
    """``build_credential`` returns an explicit, short credential chain.

    The whole reason this function exists (instead of ``DefaultAzureCredential``)
    is that ``DefaultAzureCredential`` includes ``ManagedIdentityCredential``,
    which hangs for ~50 seconds on a local dev machine waiting for an IMDS
    endpoint that does not exist. These tests pin the explicit shape of the
    chain so future regressions are caught immediately.
    """

    def test_returns_cli_credential_when_no_sp_env_vars(self, clean_auth_env):
        """With no SP env vars, only the CLI credential is in the chain.

        It is returned directly (not wrapped in a ChainedTokenCredential)
        because a chain of one element adds no value.
        """
        from azure.identity import AzureCliCredential

        cred = build_credential()
        assert isinstance(cred, AzureCliCredential)

    def test_returns_chained_credential_when_all_sp_env_vars_set(
        self, clean_auth_env, monkeypatch,
    ):
        monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")

        from azure.identity import ChainedTokenCredential

        cred = build_credential()
        assert isinstance(cred, ChainedTokenCredential)

    def test_partial_sp_env_vars_falls_back_to_cli_only(
        self, clean_auth_env, monkeypatch,
    ):
        """Partial SP setup (e.g., AZURE_CLIENT_ID set but not the others)
        should fall back to CLI alone, NOT include a half-built SP credential
        in the chain.

        This protects against a common .env mistake where the operator
        copies in some SP vars but forgets the rest. Failing gracefully to
        the CLI is friendlier than crashing.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
        # Other two SP vars deliberately not set

        from azure.identity import AzureCliCredential

        cred = build_credential()
        assert isinstance(cred, AzureCliCredential)

    def test_empty_string_sp_env_vars_treated_as_missing(
        self, clean_auth_env, monkeypatch,
    ):
        """Empty string env vars should not trigger the SP path. Common
        .env mistake where a value is set to the empty string by accident.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "")
        monkeypatch.setenv("AZURE_TENANT_ID", "")

        from azure.identity import AzureCliCredential

        cred = build_credential()
        assert isinstance(cred, AzureCliCredential)

    def test_whitespace_sp_env_vars_treated_as_missing(
        self, clean_auth_env, monkeypatch,
    ):
        """Whitespace-only env vars should be treated as not set. .env
        files sometimes get trailing spaces from copy-paste; the function
        ``strip()``s before checking.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "   ")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "\t\n")
        monkeypatch.setenv("AZURE_TENANT_ID", " ")

        from azure.identity import AzureCliCredential

        cred = build_credential()
        assert isinstance(cred, AzureCliCredential)

    def test_chained_credential_does_not_include_managed_identity(
        self, clean_auth_env, monkeypatch,
    ):
        """Regression test: ``ManagedIdentityCredential`` must NEVER be in
        the chain. Including it causes the 50-second IMDS hang documented
        in the post-mortem. If this test fails, the auth code has
        regressed to the broken behavior.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "test-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")

        from azure.identity import ManagedIdentityCredential

        cred = build_credential()
        # ChainedTokenCredential exposes its inner credentials. The
        # attribute name has been ``credentials`` since azure-identity 1.x;
        # fall through to ``_credentials`` for older SDK versions just in case.
        inner = getattr(cred, "credentials", None)
        if inner is None:
            inner = getattr(cred, "_credentials", [])
        for c in inner:
            assert not isinstance(c, ManagedIdentityCredential), (
                "ManagedIdentityCredential must NEVER be in build_credential's "
                "chain. See the post-mortem for the 50-second hang it causes "
                "on local dev machines."
            )

    def test_chained_credential_does_not_include_default_credential(
        self, clean_auth_env, monkeypatch,
    ):
        """``DefaultAzureCredential`` would re-introduce the IMDS hang
        transitively. Make sure it is not used directly either.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "test-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")

        from azure.identity import DefaultAzureCredential

        cred = build_credential()
        assert not isinstance(cred, DefaultAzureCredential)
        inner = getattr(cred, "credentials", None) or getattr(
            cred, "_credentials", []
        )
        for c in inner:
            assert not isinstance(c, DefaultAzureCredential)

    def test_client_secret_credential_built_with_env_values(
        self, clean_auth_env, monkeypatch,
    ):
        """The SP credential should receive exactly the env values, no
        substitution or reformatting. A test that pins this catches the
        copy-paste bug where someone wires AZURE_TENANT_ID into client_id
        or vice versa.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "my-client-id")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "my-secret-value")
        monkeypatch.setenv("AZURE_TENANT_ID", "my-tenant-id")

        with patch("azure.identity.ClientSecretCredential") as mock_csc:
            build_credential()
            mock_csc.assert_called_once_with(
                tenant_id="my-tenant-id",
                client_id="my-client-id",
                client_secret="my-secret-value",
            )

    def test_sp_values_stripped_of_whitespace(
        self, clean_auth_env, monkeypatch,
    ):
        """Env vars are stripped before use, so trailing whitespace from
        .env files does not break SP auth.
        """
        monkeypatch.setenv("AZURE_CLIENT_ID", "  my-client-id  ")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "\tmy-secret\n")
        monkeypatch.setenv("AZURE_TENANT_ID", " my-tenant ")

        with patch("azure.identity.ClientSecretCredential") as mock_csc:
            build_credential()
            mock_csc.assert_called_once_with(
                tenant_id="my-tenant",
                client_id="my-client-id",
                client_secret="my-secret",
            )


# ---------------------------------------------------------------------------
# build_azure_client  (the dual-path Foundry client: API key or Entra ID)
# ---------------------------------------------------------------------------


class TestBuildAzureClient:
    """``build_azure_client`` supports two paths: API key OR Entra ID.

    The API key path is the last-resort fallback that mirrors the dual-path
    pattern in ``_search_client.py``. Adding it was the third fix from the
    post-mortem.
    """

    def test_uses_api_key_when_set(self, clean_auth_env, monkeypatch):
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://test.services.ai.azure.com/api/projects/test",
        )
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sk-test-key-12345")

        with patch("openai.AzureOpenAI") as mock_client:
            build_azure_client()

            assert mock_client.call_count == 1
            kwargs = mock_client.call_args.kwargs
            # API key path was taken
            assert kwargs.get("api_key") == "sk-test-key-12345"
            # Token provider was NOT wired up (no Entra ID call)
            assert "azure_ad_token_provider" not in kwargs

    def test_uses_entra_id_when_api_key_not_set(
        self, clean_auth_env, monkeypatch,
    ):
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://test.services.ai.azure.com/api/projects/test",
        )
        # API key explicitly not set

        with patch("openai.AzureOpenAI") as mock_client:
            build_azure_client()

            assert mock_client.call_count == 1
            kwargs = mock_client.call_args.kwargs
            # Token provider path was taken
            assert "azure_ad_token_provider" in kwargs
            # API key was NOT used
            assert "api_key" not in kwargs

    def test_empty_string_api_key_falls_through_to_entra_id(
        self, clean_auth_env, monkeypatch,
    ):
        """An empty AZURE_OPENAI_API_KEY env var should not trigger the
        API key path. Treat as not set. Common mistake when copying .env
        templates.
        """
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://test.services.ai.azure.com/api/projects/test",
        )
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")

        with patch("openai.AzureOpenAI") as mock_client:
            build_azure_client()
            kwargs = mock_client.call_args.kwargs
            assert "azure_ad_token_provider" in kwargs
            assert "api_key" not in kwargs

    def test_strips_project_path_from_endpoint(
        self, clean_auth_env, monkeypatch,
    ):
        """Foundry project endpoints have ``/api/projects/...`` suffixes; the
        OpenAI SDK wants the bare resource URL.
        """
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://my-foundry.services.ai.azure.com/api/projects/my-project",
        )
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        with patch("openai.AzureOpenAI") as mock_client:
            build_azure_client()
            kwargs = mock_client.call_args.kwargs
            assert kwargs["azure_endpoint"] == (
                "https://my-foundry.services.ai.azure.com/"
            )

    def test_uses_default_api_version_when_env_not_set(
        self, clean_auth_env, monkeypatch,
    ):
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://test.services.ai.azure.com/api/projects/test",
        )
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)

        with patch("openai.AzureOpenAI") as mock_client:
            build_azure_client()
            assert (
                mock_client.call_args.kwargs["api_version"] == DEFAULT_API_VERSION
            )

    def test_uses_explicit_api_version_when_env_set(
        self, clean_auth_env, monkeypatch,
    ):
        """AZURE_OPENAI_API_VERSION override is respected on both paths."""
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://test.services.ai.azure.com/api/projects/test",
        )
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2099-12-31")

        with patch("openai.AzureOpenAI") as mock_client:
            build_azure_client()
            assert mock_client.call_args.kwargs["api_version"] == "2099-12-31"

    def test_raises_when_project_endpoint_missing(
        self, clean_auth_env, monkeypatch,
    ):
        monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
        # Doesn't matter which path; both call require_env first
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        with pytest.raises(AgentClientError, match="AZURE_AI_PROJECT_ENDPOINT"):
            build_azure_client()


# ---------------------------------------------------------------------------
# warm_up_auth  (the pre-flight check that catches SDK-level auth failures)
# ---------------------------------------------------------------------------


class TestWarmUpAuth:
    """``warm_up_auth`` actually fetches a token via the SDK and reports
    which credential resolved.

    The whole point of this function: catch the failure mode where ``az login``
    succeeded in PowerShell but the SDK cannot invoke the CLI from Python. The
    old behavior was 'CLI exit code 0 means auth works,' which was wrong. The
    new behavior is 'SDK can actually acquire a token means auth works.'
    """

    def test_returns_credential_type_and_expires_on(self):
        """Successful path returns the credential class name and expiry."""
        mock_token = MagicMock()
        mock_token.expires_on = 1718045833

        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        # type(credential).__name__ returns the class name; set it explicitly
        # so the test reads naturally.
        mock_credential.__class__.__name__ = "AzureCliCredential"

        with patch(
            "src.agents._azure_client.build_credential",
            return_value=mock_credential,
        ):
            info = warm_up_auth()

        assert info == {
            "credential_type": "AzureCliCredential",
            "expires_on": 1718045833,
        }

    def test_calls_get_token_with_cognitive_services_scope(self):
        """The scope must match what AzureOpenAI uses, or the cached token
        is useless. Pinning this prevents drift.
        """
        mock_token = MagicMock(expires_on=1234567890)
        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        mock_credential.__class__.__name__ = "ClientSecretCredential"

        with patch(
            "src.agents._azure_client.build_credential",
            return_value=mock_credential,
        ):
            warm_up_auth()

        mock_credential.get_token.assert_called_once_with(
            "https://cognitiveservices.azure.com/.default"
        )

    def test_raises_when_token_acquisition_fails(self):
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = RuntimeError("auth failed")
        mock_credential.__class__.__name__ = "AzureCliCredential"

        with patch(
            "src.agents._azure_client.build_credential",
            return_value=mock_credential,
        ):
            with pytest.raises(AgentClientError) as excinfo:
                warm_up_auth()

        # Error message includes the credential type that was attempted,
        # so operators know which path failed.
        assert "AzureCliCredential" in str(excinfo.value)

    def test_error_includes_recovery_guidance(self):
        """The error message should tell the operator how to fix the auth
        problem. Mention both the SP path and the CLI path.
        """
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = RuntimeError("timeout")
        mock_credential.__class__.__name__ = "AzureCliCredential"

        with patch(
            "src.agents._azure_client.build_credential",
            return_value=mock_credential,
        ):
            with pytest.raises(AgentClientError) as excinfo:
                warm_up_auth()

        msg = str(excinfo.value)
        # Recovery guidance for both auth paths
        assert "AZURE_CLIENT_ID" in msg or "Service Principal" in msg
        assert "az login" in msg

    def test_error_chains_from_original_exception(self):
        """The AgentClientError should chain from the original exception so
        the traceback shows the underlying error for debugging.
        """
        original_exc = ValueError("specific underlying error")
        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = original_exc
        mock_credential.__class__.__name__ = "AzureCliCredential"

        with patch(
            "src.agents._azure_client.build_credential",
            return_value=mock_credential,
        ):
            with pytest.raises(AgentClientError) as excinfo:
                warm_up_auth()

        assert excinfo.value.__cause__ is original_exc
