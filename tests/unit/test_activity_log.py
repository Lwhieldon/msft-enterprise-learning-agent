"""Unit tests for ``src.activity_log.emit_auth_health``.

The auth health emission was added as part of the post-mortem fix for the
Reactor demo auth failure. It is the one log line that would have warned
about the failure mode before going live, so it deserves its own pinned
test even though the rest of activity_log is best-effort instrumentation.

These tests use ``ACTIVITY_LOG_DISABLED=1`` (set in conftest.py) plus
``patch`` on the ``emit`` function to verify the right category and
payload without touching the filesystem.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.activity_log import emit_auth_health


class TestEmitAuthHealth:
    """``emit_auth_health`` writes a structured Auth event to the activity log."""

    def test_emits_with_auth_category(self):
        """The log line must use the ``Auth`` category so it gets the violet
        color in the terminal AND so anyone filtering the log by category
        can find it.
        """
        future_expiry = int(time.time()) + 3600  # 60 minutes from now

        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health("AzureCliCredential", future_expiry)

        # emit was called once with the Auth category as first arg
        assert mock_emit.call_count == 1
        args = mock_emit.call_args.args
        assert args[0] == "Auth"

    def test_message_includes_credential_type(self):
        """The log message should literally name the credential class so
        operators can pattern-match it visually (e.g. spotting that
        AzureCliCredential resolved when ClientSecretCredential was expected).
        """
        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health("ClientSecretCredential", 1718045833)

        message = mock_emit.call_args.args[1]
        assert "ClientSecretCredential" in message

    def test_metadata_includes_token_valid_minutes(self):
        """The kwargs passed to emit should include the minutes-remaining
        count so the metadata column shows it.
        """
        # Token expires 90 minutes from now
        future_expiry = int(time.time()) + (90 * 60)

        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health("ClientSecretCredential", future_expiry)

        kwargs = mock_emit.call_args.kwargs
        # Allow 1 minute of clock-drift slack in the test
        assert "token_valid_minutes" in kwargs
        assert 88 <= kwargs["token_valid_minutes"] <= 90

    def test_metadata_includes_raw_expiry_timestamp(self):
        """The raw expires_on timestamp should also be in metadata so it
        is recoverable even if the human-readable minutes count drifts.
        """
        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health("ClientSecretCredential", 1718045833)

        kwargs = mock_emit.call_args.kwargs
        assert kwargs.get("expires_on") == 1718045833

    def test_expired_token_renders_zero_minutes_not_negative(self):
        """If the token has already expired (timestamp in the past), the
        minutes count should clamp to zero rather than going negative.
        Negative minutes would be confusing to read in the log.
        """
        past_expiry = int(time.time()) - 3600  # 1 hour ago

        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health("AzureCliCredential", past_expiry)

        kwargs = mock_emit.call_args.kwargs
        assert kwargs["token_valid_minutes"] == 0

    def test_zero_expiry_handled_gracefully(self):
        """The app.py pre-flight passes expires_on=0 for the API key path
        (since there is no token expiry to report). The function should
        not crash on zero.
        """
        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health("AZURE_OPENAI_API_KEY (fallback)", 0)

        assert mock_emit.call_count == 1
        kwargs = mock_emit.call_args.kwargs
        # Negative minutes from a zero timestamp should clamp to zero
        assert kwargs["token_valid_minutes"] == 0

    def test_credential_type_passed_through_verbatim(self):
        """Whatever string is passed as credential_type should appear in
        the message exactly. No string transformation.
        """
        custom_name = "SomeFutureCredentialType_v2"

        with patch("src.activity_log.emit") as mock_emit:
            emit_auth_health(custom_name, int(time.time()) + 60)

        message = mock_emit.call_args.args[1]
        assert custom_name in message
