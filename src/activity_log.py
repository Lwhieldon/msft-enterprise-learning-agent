"""Structured activity log for Compliance Academy agents.

This module exists to make agent orchestration visible to a live audience.
During the Microsoft Reactor agents battle (June 10, 2026), the Chainlit
UI is the primary surface, but a second terminal tails this log file to
show what the agent system is doing under the hood. Both surfaces describe
the same activity from different vantage points: the UI is the user
experience, the log is the proof that something real is happening.

The log lives at the agent layer (not the orchestrator or UI layer) so
that it populates regardless of which surface drove the call. Running
the CLI orchestrator fills the log with CLI-driven events. Running the
Chainlit app fills it with Chainlit-driven events. The format is the
same either way.

Output destinations:
    1. A file at ``logs/activity.log`` (default; configurable via
       ``ACTIVITY_LOG_PATH`` env var). This is what the live demo tails.
    2. Optionally stdout, when ``ACTIVITY_LOG_TO_STDOUT=1`` is set in env.
       Useful for local development. Off by default so the CLI
       orchestrator's own stdout output is not duplicated.

Disabling the log:
    Set ``ACTIVITY_LOG_DISABLED=1`` in env. This is the recommended
    pattern for unit tests so they do not pollute the workspace with a
    ``logs/`` directory.

Public API:
    emit(category, message, **metadata)
        Write a single event line to the configured destinations.

    log_line(message)
        Write a raw, uncategorized line. Used for headers and separators
        in the demo flow.

Color theme:
    Categories are color-coded using ANSI escape codes calibrated to the
    SC&H brand palette (best-effort, since ANSI is an 8/16-color space).
    PowerShell on Windows Terminal renders these natively. The terminal
    must support ANSI escape sequences; standard Windows ``cmd.exe`` may
    not render them correctly. Use Windows Terminal or any modern shell.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# ANSI color theme (mapped from the SC&H brand palette where possible)
# ---------------------------------------------------------------------------

# ANSI standard 8/16-color palette can only approximate the SC&H hex
# colors. The mapping below picks the closest fit per category and uses
# bold/dim modifiers for emphasis. The "true color" alternative (24-bit
# ANSI sequences like ``\033[38;2;0;121;255m``) renders accurately on
# Windows Terminal and most modern terminals; we use it here.

# Brand-color truecolor codes
_NAVY = "\033[38;2;0;24;100m"        # SC&H Deep Navy
_BLUE = "\033[38;2;0;121;255m"       # SC&H Bright Blue
_MINT = "\033[38;2;65;239;175m"      # SC&H Mint Green
_GOLD = "\033[38;2;255;216;51m"      # SC&H Gold
_CYAN = "\033[38;2;12;197;255m"      # Bright Cyan
_TEAL = "\033[38;2;0;183;255m"       # Sky Blue (more visible than Dark Teal on black bg)
_GRAY = "\033[38;2;112;112;112m"     # Medium Gray (timestamps + metadata)
_RED = "\033[38;2;220;60;60m"        # Errors

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

#: Mapping from category to its display color. Categories not in this
#: mapping render in default terminal color (white/no color).
_CATEGORY_COLORS: dict[str, str] = {
    "Chainlit": _CYAN,
    "Orchestrator": _BLUE,
    "Agent": _BOLD + _BLUE,
    "Foundry IQ": _MINT,
    "Azure OpenAI": _GOLD,
    "Scenario": _TEAL,
    "Error": _BOLD + _RED,
}


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

#: Default log file path. Override with ACTIVITY_LOG_PATH env var.
_DEFAULT_LOG_PATH = Path("logs/activity.log")


def _is_disabled() -> bool:
    """Check whether logging is disabled via environment variable.

    Returns True when ACTIVITY_LOG_DISABLED is set to a truthy value
    (``1``, ``true``, ``yes``, case-insensitive). Used by unit tests to
    prevent log file creation during test runs.
    """
    val = os.environ.get("ACTIVITY_LOG_DISABLED", "").strip().lower()
    return val in ("1", "true", "yes")


def _stdout_enabled() -> bool:
    """Check whether to also mirror events to stdout."""
    val = os.environ.get("ACTIVITY_LOG_TO_STDOUT", "").strip().lower()
    return val in ("1", "true", "yes")


def _resolve_log_path() -> Path:
    """Resolve the log file path from env or default.

    The parent directory is NOT created here; that is done lazily on
    first emit so a disabled run never touches the filesystem.
    """
    custom = os.environ.get("ACTIVITY_LOG_PATH", "").strip()
    if custom:
        return Path(custom)
    return _DEFAULT_LOG_PATH


def _ensure_parent_dir(path: Path) -> None:
    """Create the parent directory of the log file if needed.

    Silently no-ops if the directory already exists. If the directory
    cannot be created (e.g., permissions error), the exception
    propagates so the caller knows logging is not working.
    """
    parent = path.parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit(category: str, message: str, **metadata: Any) -> None:
    """Emit one structured event to the activity log.

    Args:
        category: A short label for the event source. Recognized
            categories with brand-color theming: ``Chainlit``,
            ``Orchestrator``, ``Agent``, ``Foundry IQ``, ``Azure OpenAI``,
            ``Scenario``, ``Error``. Other strings render in default
            terminal color.
        message: The primary human-readable text for the event. Should
            be a single line with a leading verb (e.g., "Retrieved 5
            sources in 410ms"). Do not include trailing newlines.
        **metadata: Optional key=value pairs rendered in dim gray after
            the message. Useful for timing, sizes, identifiers.

    Example:
        emit("Foundry IQ", "Retrieved 5 sources",
             elapsed_ms=411, top_score=8.34)

    Side effects:
        Appends one line to the configured log file (creating parent
        directories on first call). If ACTIVITY_LOG_TO_STDOUT=1, also
        writes to stdout. No-op if ACTIVITY_LOG_DISABLED=1.

    Errors are swallowed silently. The activity log is best-effort
    instrumentation; a logging failure must not break agent execution.
    """
    if _is_disabled():
        return

    try:
        line = _format_line(category, message, metadata)
        path = _resolve_log_path()
        _ensure_parent_dir(path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if _stdout_enabled():
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    except Exception:
        # Best-effort: never raise from the logger. If the disk is
        # full, permissions are wrong, or the terminal is closed, the
        # demo still runs.
        pass


def log_line(message: str = "") -> None:
    """Emit a raw line with no category prefix or color formatting.

    Used for section separators and demo-flow markers. Pass an empty
    string to write a blank line for visual breathing room.
    """
    if _is_disabled():
        return

    try:
        path = _resolve_log_path()
        _ensure_parent_dir(path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(message + "\n")
        if _stdout_enabled():
            sys.stdout.write(message + "\n")
            sys.stdout.flush()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_line(
    category: str,
    message: str,
    metadata: dict[str, Any],
) -> str:
    """Build one display line: ``HH:MM:SS.mmm  [Category]  Message  (k=v, ...)``."""
    timestamp = _format_timestamp()
    category_label = _format_category(category)
    metadata_str = _format_metadata(metadata)
    return f"{_GRAY}{timestamp}{_RESET}  {category_label}  {message}{metadata_str}"


def _format_timestamp() -> str:
    """Return current local time as HH:MM:SS.mmm string."""
    now = datetime.now()
    return now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


def _format_category(category: str) -> str:
    """Return color-wrapped, fixed-width category label."""
    color = _CATEGORY_COLORS.get(category, "")
    # Pad to 14 chars so the message column aligns across categories.
    # The longest registered category is "Azure OpenAI" (12 chars) +
    # brackets = 14.
    label = f"[{category}]"
    padded = label.ljust(14)
    if color:
        return f"{color}{padded}{_RESET}"
    return padded


def _format_metadata(metadata: dict[str, Any]) -> str:
    """Render metadata as ``  (k1=v1, k2=v2)`` in dim gray. Empty if no metadata."""
    if not metadata:
        return ""
    parts = []
    for key, value in metadata.items():
        # Quote string values that contain spaces for readability
        if isinstance(value, str) and " " in value:
            parts.append(f'{key}="{value}"')
        else:
            parts.append(f"{key}={value}")
    rendered = ", ".join(parts)
    return f"  {_DIM}({rendered}){_RESET}"
