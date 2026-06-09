"""Compliance Academy source package.

Modules:
    scenario_loader: Loads and validates scenario JSON files, merging
        per-scenario overrides with the shared baseline.
"""

# Corporate TLS interception fix: use the Windows certificate store (which
# has the Netskope corporate root CA installed by IT) instead of certifi.
# Lives here at the package level so it fires automatically for every entry
# point that touches the src.* namespace — python -m src.X smoke tests,
# chainlit run app.py, pytest, and the orchestrator CLI — without needing
# each caller to remember to inject it themselves.
import truststore as _truststore
_truststore.inject_into_ssl()
