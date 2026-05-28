"""Integration tests for Compliance Academy agents.

These tests hit live Azure OpenAI through the Foundry deployment and require
a valid ``az login`` session plus the AZURE_AI_PROJECT_ENDPOINT env var.
They are opt-in via the ``integration`` pytest marker:

    pytest tests/integration/                          # run all integration tests
    pytest -m integration                              # same, via marker
    pytest tests/integration/test_agents.py            # one file
    pytest tests/integration/test_agents.py::TestBasicSmoke   # one class
    pytest -m integration -k stress                    # only the stress subset
    pytest -m integration -k "stress and generator"    # only generator stress

Test categories in this file:
    1. TestBasicSmoke: one happy-path call per agent. Fast verification that
       all four agent wrappers + the Azure connection are healthy.
    2. TestScenarioGeneratorStress: varied breach descriptions across risk
       categories to surface Azure content/jailbreak filter false positives.
    3. TestSuspectAgentStress: varied player questions including
       confrontational and emotionally-loaded ones.
    4. TestForensicAnalystStress: varied question styles (open-ended,
       control-specific, counterfactual).
    5. TestComplianceOfficerStress: all three outcome types
       (correct, wrong_perpetrator, no_accusation).

Total live API calls when all classes run: ~20. Total wall time: ~10-15 min.
Approximate cost on gpt-4.1-mini at current rates: < $1.

Each test asserts the minimum that proves the call worked AND produced
demo-quality output (non-empty response, expected entities present, etc.).
"""

from __future__ import annotations

import pytest

from src.agents.compliance_officer import deliver_closer
from src.agents.forensic_analyst import consult_forensic_analyst
from src.agents.scenario_generator import generate_scenario
from src.agents.suspect_agent import interrogate_suspect


# All tests in this file hit live Azure. Apply the marker at module level.
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Test case definitions
# ---------------------------------------------------------------------------


GENERATOR_STRESS_CASES: list[dict[str, str]] = [
    {
        "id": "low_risk_vendor",
        "breach": (
            "A vendor's compromised API key was used to download proprietary "
            "research data over a weekend, undetected for 36 hours."
        ),
    },
    {
        "id": "medium_risk_insider",
        "breach": (
            "An employee with privileged access copied internal customer "
            "records to a personal cloud storage account in the two weeks "
            "before submitting their resignation."
        ),
    },
    {
        "id": "high_risk_cyber_jargon",
        "breach": (
            "Attackers used a phishing kit to harvest credentials, then "
            "pivoted laterally through the network using stolen Kerberos "
            "tickets to access the clinical trial document repository."
        ),
    },
    {
        "id": "real_incident_analog",
        "breach": (
            "An MFA-bypass attack similar to recent incidents at major SaaS "
            "providers, where session tokens were stolen via a reverse-proxy "
            "phishing page and used to access the production data warehouse."
        ),
    },
    {
        "id": "vague_input",
        "breach": "Something happened to our patient data over the weekend.",
    },
]


SUSPECT_STRESS_CASES: list[dict[str, str]] = [
    {
        "id": "friendly_open",
        "suspect_id": "casey_doyle",
        "message": (
            "Hi Casey, thanks for coming in. Can you walk me through what your "
            "Sunday evening looked like? I am just trying to build a timeline."
        ),
    },
    {
        "id": "evidence_grounded",
        "suspect_id": "casey_doyle",
        "message": (
            "We have access logs showing your account signed in at 11:23 PM "
            "Sunday from an IP geolocated to Sofia, Bulgaria. Can you explain "
            "that sign-in?"
        ),
    },
    {
        "id": "confrontational",
        "suspect_id": "casey_doyle",
        "message": (
            "I am going to be direct. We have you on the access logs, we "
            "have you on the forwarded email at 9 PM, and we have the "
            "exfiltration timestamp aligning with your session. Did you "
            "click the link in that email?"
        ),
    },
    {
        "id": "empathy_invitation",
        "suspect_id": "casey_doyle",
        "message": (
            "I know this is a really stressful conversation. Take a breath. "
            "Is there anything you wanted to tell IT or HR last week that "
            "you ended up holding back on?"
        ),
    },
]


FORENSIC_STRESS_CASES: list[dict[str, str]] = [
    {
        "id": "open_ended",
        "message": (
            "Walk me through the evidence we have so far. What does the "
            "access log pattern actually tell us about who was where during "
            "the breach window?"
        ),
    },
    {
        "id": "control_specific",
        "message": (
            "Which framework control failure most directly enabled this "
            "breach? Give me the citation in full and tell me what the "
            "control actually requires."
        ),
    },
    {
        "id": "counterfactual",
        "message": (
            "If Helix had implemented every control in the SOC 2 CC9.2 "
            "section properly, would this breach have been prevented or just "
            "detected earlier? Walk me through the difference."
        ),
    },
]


COMPLIANCE_OFFICER_STRESS_CASES: list[dict[str, str | None]] = [
    {
        "id": "correct_riley",
        "accused_suspect_id": "riley_park",
        "outcome": "correct",
    },
    {
        "id": "wrong_perpetrator_red_herring",
        "accused_suspect_id": "alex_chen",   # the red herring in SCN-001
        "outcome": "wrong_perpetrator",
    },
    {
        "id": "no_accusation",
        "accused_suspect_id": None,
        "outcome": "no_accusation",
    },
]


# ---------------------------------------------------------------------------
# TestBasicSmoke: one call per agent, happy path
# ---------------------------------------------------------------------------


class TestBasicSmoke:
    """Minimum verification that all four agent wrappers + Azure are healthy.

    Run with::

        pytest tests/integration/test_agents.py::TestBasicSmoke -m integration

    Wall time: ~1-2 minutes.
    """

    def test_scenario_generator_produces_valid_scenario(self):
        result = generate_scenario(
            "A vendor's compromised API key was used to download "
            "proprietary research data over a weekend.",
            stream_to_stdout=False,
        )

        merged = result["merged_scenario"]
        assert merged["scenario_id"]
        assert merged["scenario_name"]
        assert len(merged["suspects"]) == 5
        perps = [s for s in merged["suspects"] if s["is_perpetrator"]]
        assert len(perps) == 1
        assert len(merged["evidence_seeds"]) >= 3
        assert result["elapsed_seconds"] > 0

    def test_suspect_responds_in_first_person(self, default_scenario):
        result = interrogate_suspect(
            default_scenario,
            "casey_doyle",
            "Where were you Sunday night between 8 PM and midnight?",
            stream_to_stdout=False,
        )

        assert result["reply"].strip(), "Reply must not be empty"
        assert result["suspect_name"] == "Casey Doyle"
        # In-character check: first-person dialogue should contain "I"
        # (defensive check; not a guarantee but catches third-person narration)
        reply_lower = result["reply"].lower()
        assert " i " in reply_lower or reply_lower.startswith("i "), (
            f"Suspect reply should use first person. Got: {result['reply'][:200]}"
        )

    def test_forensic_analyst_cites_evidence_or_controls(self, default_scenario):
        result = consult_forensic_analyst(
            default_scenario,
            "Walk me through the access logs and tell me which control "
            "is most clearly implicated.",
            stream_to_stdout=False,
        )

        assert result["reply"].strip(), "Reply must not be empty"
        reply = result["reply"]
        # The analyst should cite at least one evidence ID OR a control ID
        # from the scenario.
        has_evidence_citation = any(
            ev["evidence_id"] in reply
            for ev in default_scenario["evidence_seeds"]
        )
        has_control_citation = any(
            ctrl["identifier"] in reply
            for ctrl in default_scenario["violated_controls"]
        )
        assert has_evidence_citation or has_control_citation, (
            "Forensic Analyst response must cite at least one evidence ID "
            "or framework/policy identifier from the scenario."
        )

    def test_compliance_officer_delivers_structured_closer(self, default_scenario):
        result = deliver_closer(
            default_scenario,
            accused_suspect_id="riley_park",
            outcome="correct",
            stream_to_stdout=False,
        )

        speech = result["speech"]
        word_count = len(speech.split())

        assert speech.strip(), "Speech must not be empty"
        # The prompt targets 250-400 words; allow ±20% margin for the
        # integration test (some scenarios warrant longer).
        assert 200 <= word_count <= 500, (
            f"Closing speech length {word_count} words is far outside the "
            f"250-400 target range. Check the system prompt or token cap."
        )
        # Should cite the actual perpetrator
        assert "Riley Park" in speech
        # Should cite at least one violated control identifier
        assert any(c["identifier"] in speech
                   for c in default_scenario["violated_controls"]), (
            "Closing speech should cite at least one violated control identifier"
        )


# ---------------------------------------------------------------------------
# Stress: parameterized varied-input tests
# ---------------------------------------------------------------------------


class TestScenarioGeneratorStress:
    """Run the Scenario Generator across breach descriptions that span the
    risk spectrum the Azure content/jailbreak filters are most likely to
    flag. Each case must produce a valid scenario through the loader."""

    @pytest.mark.parametrize(
        "case", GENERATOR_STRESS_CASES, ids=[c["id"] for c in GENERATOR_STRESS_CASES]
    )
    def test_handles_varied_breach_descriptions(self, case):
        result = generate_scenario(case["breach"], stream_to_stdout=False)
        merged = result["merged_scenario"]

        # Minimum demo-quality checks (mirroring the validator's contract)
        assert len(merged["suspects"]) == 5
        assert len([s for s in merged["suspects"] if s["is_perpetrator"]]) == 1
        assert len(merged["evidence_seeds"]) >= 3
        assert len(merged["violated_controls"]) >= 2


class TestSuspectAgentStress:
    """Run varied player questions against Casey in the default scenario,
    including evidence-grounded and confrontational ones. The suspect should
    respond in character without filter rejection on any input."""

    @pytest.mark.parametrize(
        "case", SUSPECT_STRESS_CASES, ids=[c["id"] for c in SUSPECT_STRESS_CASES]
    )
    def test_handles_varied_player_messages(self, default_scenario, case):
        result = interrogate_suspect(
            default_scenario,
            case["suspect_id"],
            case["message"],
            stream_to_stdout=False,
        )
        assert result["reply"].strip()
        assert result["suspect_id"] == case["suspect_id"]


class TestForensicAnalystStress:
    """Run varied question styles against the Forensic Analyst on the
    default scenario."""

    @pytest.mark.parametrize(
        "case", FORENSIC_STRESS_CASES, ids=[c["id"] for c in FORENSIC_STRESS_CASES]
    )
    def test_handles_varied_questions(self, default_scenario, case):
        result = consult_forensic_analyst(
            default_scenario, case["message"], stream_to_stdout=False,
        )
        assert result["reply"].strip()


class TestComplianceOfficerStress:
    """Run the Compliance Officer with each outcome type.

    The wrong_perpetrator and no_accusation paths use different user message
    framing than correct; we test all three to catch any future regression
    in the message construction logic.
    """

    @pytest.mark.parametrize(
        "case",
        COMPLIANCE_OFFICER_STRESS_CASES,
        ids=[c["id"] for c in COMPLIANCE_OFFICER_STRESS_CASES],
    )
    def test_handles_all_outcome_types(self, default_scenario, case):
        result = deliver_closer(
            default_scenario,
            accused_suspect_id=case["accused_suspect_id"],
            outcome=case["outcome"],
            stream_to_stdout=False,
        )
        assert result["speech"].strip()
        word_count = len(result["speech"].split())
        # Word count target is 250-400; allow wider margin for the
        # wrong_perpetrator / no_accusation variants which may run longer.
        assert 150 <= word_count <= 600, (
            f"Closing speech length {word_count} words is outside acceptable "
            f"range for outcome={case['outcome']!r}"
        )
