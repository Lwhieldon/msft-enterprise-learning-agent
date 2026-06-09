"""Shared pytest fixtures for Compliance Academy tests.

Fixtures here are available to all tests under ``tests/`` without explicit
import. Session-scoped fixtures load expensive resources (pre-built scenarios)
once per test run rather than once per test.

Conventions:
    - ``default_scenario``: the canonical pre-built breach (SCN-001),
      Riley Park as perpetrator, Alex Chen as red herring.
    - ``supplychain_scenario``: SCN-002, Morgan Webb as perpetrator,
      Jordan Smith as red herring.
    - ``vishing_scenario``: SCN-003, Jordan Smith as perpetrator,
      Casey Doyle as red herring.

These are session-scoped because the loader is deterministic (same input
file produces the same merged dict) and tests should not mutate the dict.
If a test needs a mutable copy, it should ``copy.deepcopy`` the fixture.
"""

from __future__ import annotations

# Corporate TLS interception fix: use the Windows certificate store (which
# has the Netskope corporate root CA installed by IT) instead of certifi.
# MUST run before any openai/azure-* imports happen, including the transitive
# ones from src.scenario_loader below, or integration tests fail with
# "self-signed certificate in certificate chain" on this loaner laptop.
import truststore
truststore.inject_into_ssl()

import os
from typing import Any

import pytest

# Disable activity log writes BEFORE any test module imports happen, so
# importing src.agents.* does not create a logs/ directory in the working
# directory during pytest collection. (The agents themselves do not emit
# at import time, but smoke imports could touch the log path. Setting the
# env var here also makes any unit test that does trigger an emit a no-op.)
os.environ.setdefault("ACTIVITY_LOG_DISABLED", "1")

from src.scenario_loader import load_scenario_by_name


@pytest.fixture(scope="session")
def default_scenario() -> dict[str, Any]:
    """The SCN-001 Helix Dynamics default breach (Riley perpetrator)."""
    return load_scenario_by_name("helix_dynamics_default")


@pytest.fixture(scope="session")
def supplychain_scenario() -> dict[str, Any]:
    """The SCN-002 LabConnect supply chain breach (Morgan perpetrator)."""
    return load_scenario_by_name("helix_dynamics_supplychain")


@pytest.fixture(scope="session")
def vishing_scenario() -> dict[str, Any]:
    """The SCN-003 Help Desk vishing breach (Jordan perpetrator)."""
    return load_scenario_by_name("helix_dynamics_vishing")
