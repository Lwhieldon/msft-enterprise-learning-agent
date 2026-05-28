"""Unit tests for suspect agent template substitution.

The suspect agent loads ``prompts/suspects/_template.md`` and substitutes
``{{placeholder}}`` variables from the merged scenario suspect dict. This
test module exercises the pure substitution logic without hitting Azure.
"""

from __future__ import annotations

import pytest

from src.agents.suspect_agent import (
    SuspectAgentError,
    _build_system_prompt,
    _find_suspect,
    _render_bullet_list,
)


# ---------------------------------------------------------------------------
# _find_suspect
# ---------------------------------------------------------------------------


class TestFindSuspect:
    """Locating a suspect by ID in a merged scenario dict."""

    def test_finds_existing_suspect(self, default_scenario):
        casey = _find_suspect(default_scenario, "casey_doyle")
        assert casey["name"] == "Casey Doyle"
        assert casey["suspect_id"] == "casey_doyle"

    def test_unknown_suspect_id_raises(self, default_scenario):
        with pytest.raises(SuspectAgentError, match="not found"):
            _find_suspect(default_scenario, "definitely_not_a_real_id")

    def test_error_includes_available_ids(self, default_scenario):
        with pytest.raises(SuspectAgentError) as excinfo:
            _find_suspect(default_scenario, "ghost")
        assert "casey_doyle" in str(excinfo.value), (
            "Error message should list available suspect IDs to help the caller"
        )


# ---------------------------------------------------------------------------
# _render_bullet_list
# ---------------------------------------------------------------------------


class TestRenderBulletList:
    """Rendering Python lists as markdown bullet lists for prompt injection."""

    def test_non_empty_list_renders_as_bullets(self):
        result = _render_bullet_list(
            ["First trigger", "Second trigger"],
            empty_fallback="ignored",
        )
        assert result == "- First trigger\n- Second trigger"

    def test_empty_list_returns_fallback_string(self):
        result = _render_bullet_list([], empty_fallback="no items here")
        assert result == "no items here"

    def test_single_item_list_renders_as_one_bullet(self):
        result = _render_bullet_list(["only one"], empty_fallback="ignored")
        assert result == "- only one"


# ---------------------------------------------------------------------------
# _build_system_prompt
# ---------------------------------------------------------------------------


# A minimal template stub for substitution testing. This isolates the
# substitution logic from the real template content so we don't depend on
# the prompt file's wording.
STUB_TEMPLATE: str = """You are {{name}}, {{role}} at Helix Dynamics.

Case: {{premise}}

Backstory: {{backstory}}

Open: {{open_knowledge}}
Guarded: {{guarded_knowledge}}
Hidden: {{hidden_truth}}
Alibi: {{alibi}}

Style: {{conversational_style}}
Examples:
{{style_examples}}

Triggers:
{{leak_conditions}}

Trust: {{starting_trust}}
"""


class TestBuildSystemPrompt:
    """Template substitution: every {{placeholder}} gets replaced from the
    merged suspect + scenario dicts."""

    def test_all_placeholders_replaced(self, default_scenario):
        casey = _find_suspect(default_scenario, "casey_doyle")
        prompt = _build_system_prompt(STUB_TEMPLATE, casey, default_scenario)

        # No unreplaced placeholders left.
        assert "{{" not in prompt, f"unreplaced placeholders found: {prompt}"
        assert "}}" not in prompt

    def test_name_and_role_substituted(self, default_scenario):
        casey = _find_suspect(default_scenario, "casey_doyle")
        prompt = _build_system_prompt(STUB_TEMPLATE, casey, default_scenario)

        assert "Casey Doyle" in prompt
        assert "Chief Scientific Officer" in prompt  # part of Casey's role

    def test_premise_substituted_from_scenario_not_hardcoded(
        self, default_scenario
    ):
        casey = _find_suspect(default_scenario, "casey_doyle")
        prompt = _build_system_prompt(STUB_TEMPLATE, casey, default_scenario)

        # The premise should come from scenario.premise_narration. Use a
        # specific phrase known to be in the default scenario's premise.
        assert default_scenario["premise_narration"] in prompt, (
            "Premise must be injected from the scenario, not the suspect"
        )

    def test_premise_changes_per_scenario(
        self, default_scenario, supplychain_scenario
    ):
        casey = _find_suspect(default_scenario, "casey_doyle")
        casey_supply = _find_suspect(supplychain_scenario, "casey_doyle")

        prompt_default = _build_system_prompt(STUB_TEMPLATE, casey, default_scenario)
        prompt_supply = _build_system_prompt(STUB_TEMPLATE, casey_supply,
                                             supplychain_scenario)

        # The two prompts should differ in the premise section. Otherwise the
        # template is hardcoding scenario-specific framing.
        assert default_scenario["premise_narration"] in prompt_default
        assert supplychain_scenario["premise_narration"] in prompt_supply
        assert prompt_default != prompt_supply

    def test_leak_conditions_rendered_as_bullets(self, default_scenario):
        # Find a suspect known to have leak conditions in the default scenario
        suspects_with_leaks = [
            s for s in default_scenario["suspects"]
            if s.get("leak_conditions")
        ]
        assert suspects_with_leaks, (
            "Default scenario should have at least one suspect with leak_conditions"
        )
        suspect = suspects_with_leaks[0]
        prompt = _build_system_prompt(STUB_TEMPLATE, suspect, default_scenario)

        for condition in suspect["leak_conditions"]:
            assert f"- {condition}" in prompt

    def test_empty_leak_conditions_renders_fallback(self, default_scenario):
        # Build a suspect dict with no leak conditions
        casey = _find_suspect(default_scenario, "casey_doyle")
        casey_no_leaks = {**casey, "leak_conditions": []}

        prompt = _build_system_prompt(STUB_TEMPLATE, casey_no_leaks, default_scenario)

        assert "No specific leak conditions" in prompt, (
            "Empty leak_conditions should render a clear fallback string"
        )

    def test_voice_examples_mapped_to_style_examples_placeholder(
        self, default_scenario
    ):
        # The merged scenario field is 'voice_examples'; the template
        # placeholder is '{{style_examples}}'. The wrapper must do the mapping.
        casey = _find_suspect(default_scenario, "casey_doyle")
        assert casey["voice_examples"], (
            "Test premise: Casey should have voice_examples in default scenario"
        )

        prompt = _build_system_prompt(STUB_TEMPLATE, casey, default_scenario)

        # At least one of Casey's voice examples should appear in the prompt
        assert any(ex in prompt for ex in casey["voice_examples"]), (
            "voice_examples values should be rendered into the {{style_examples}} slot"
        )

    def test_starting_trust_substituted(self, default_scenario):
        casey = _find_suspect(default_scenario, "casey_doyle")
        prompt = _build_system_prompt(STUB_TEMPLATE, casey, default_scenario)

        assert str(casey["starting_trust"]) in prompt
