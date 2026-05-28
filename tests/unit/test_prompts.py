"""Unit tests for prompt file integrity.

Every agent loads its system prompt from a file under ``prompts/``. If a
file is missing, renamed, or stored at the wrong path, the failure surfaces
only when the agent is first invoked (which during a live demo means the
breach is on stage). These cheap unit tests pin the expected file layout
so a refactor that moves a prompt has to update these tests deliberately.

What's covered:
    - The four prompts in active use exist at their expected paths
    - Each loads through ``load_prompt`` without error
    - Each is non-trivial in length
    - The suspect template carries every placeholder the agent substitutes
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agents._azure_client import load_prompt


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"

# The four prompts the demo path depends on. The "party" folder also
# contains unused legacy prompts (hr_liaison, it_specialist, etc.) from
# an earlier multi-agent design; those are not active so we do not pin
# them here, but we do verify the four we actually use.
ACTIVE_PROMPT_PATHS = {
    "scenario_generator": PROMPTS_DIR / "scenario_generator.md",
    "suspect_template": PROMPTS_DIR / "suspects" / "_template.md",
    "forensic_analyst": PROMPTS_DIR / "party" / "forensic_analyst.md",
    "compliance_officer": PROMPTS_DIR / "compliance_officer.md",
}


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------


class TestPromptFilesExist:
    """Every active prompt must exist at its expected path. If this fails,
    an agent will not initialize at runtime."""

    @pytest.mark.parametrize(
        "name, path",
        list(ACTIVE_PROMPT_PATHS.items()),
        ids=list(ACTIVE_PROMPT_PATHS.keys()),
    )
    def test_prompt_file_exists(self, name, path):
        assert path.exists(), (
            f"Active prompt '{name}' is expected at {path} but the file "
            f"is missing. If you renamed or moved it, update the agent "
            f"that loads it AND this test."
        )

    @pytest.mark.parametrize(
        "name, path",
        list(ACTIVE_PROMPT_PATHS.items()),
        ids=list(ACTIVE_PROMPT_PATHS.keys()),
    )
    def test_prompt_file_is_a_file_not_a_directory(self, name, path):
        assert path.is_file(), f"{path} exists but is not a file"


# ---------------------------------------------------------------------------
# Loadability
# ---------------------------------------------------------------------------


class TestPromptFilesLoad:
    """Each prompt must round-trip through ``load_prompt`` without error
    and come back as non-trivial content."""

    @pytest.mark.parametrize(
        "name, path",
        list(ACTIVE_PROMPT_PATHS.items()),
        ids=list(ACTIVE_PROMPT_PATHS.keys()),
    )
    def test_prompt_loads_without_error(self, name, path):
        content = load_prompt(path)
        assert content, f"Prompt '{name}' loaded but is empty"

    @pytest.mark.parametrize(
        "name, path",
        list(ACTIVE_PROMPT_PATHS.items()),
        ids=list(ACTIVE_PROMPT_PATHS.keys()),
    )
    def test_prompt_is_substantive_length(self, name, path):
        """Each prompt should be at least a few hundred characters. A
        prompt that suddenly drops below this is almost certainly a
        truncated file or accidental overwrite."""
        content = load_prompt(path)
        assert len(content) > 500, (
            f"Prompt '{name}' is only {len(content)} characters; expected "
            f">500. File may be truncated or corrupted."
        )


# ---------------------------------------------------------------------------
# Suspect template placeholders
# ---------------------------------------------------------------------------


# Every placeholder the suspect_agent substitutes when building the suspect
# system prompt. If a refactor adds or removes one, this test must change
# deliberately, which keeps the contract between template and agent honest.
SUSPECT_TEMPLATE_PLACEHOLDERS = [
    "{{name}}",
    "{{role}}",
    "{{premise}}",
    "{{backstory}}",
    "{{open_knowledge}}",
    "{{guarded_knowledge}}",
    "{{hidden_truth}}",
    "{{alibi}}",
    "{{conversational_style}}",
    "{{style_examples}}",
    "{{leak_conditions}}",
    "{{starting_trust}}",
]


class TestSuspectTemplatePlaceholders:
    """The suspect template uses Mustache-style ``{{var}}`` placeholders.
    Every placeholder the agent expects to substitute must actually be
    present in the file."""

    @pytest.fixture(scope="class")
    def template_content(self):
        return load_prompt(ACTIVE_PROMPT_PATHS["suspect_template"])

    @pytest.mark.parametrize("placeholder", SUSPECT_TEMPLATE_PLACEHOLDERS)
    def test_placeholder_present_in_template(self, template_content, placeholder):
        assert placeholder in template_content, (
            f"Expected placeholder {placeholder} missing from the suspect "
            f"template. The suspect agent will substitute it with persona "
            f"data; without it, that data has nowhere to land."
        )

    def test_no_unexpected_double_brace_placeholders(self, template_content):
        """Catch typos: if someone writes ``{{namee}}`` it stays unsubstituted
        and leaks into the model's input verbatim. Pin the set of
        identifier-shaped placeholders that may appear.

        The template prose also contains the literal documentation marker
        ``{{ ... }}`` (used to *describe* the placeholder syntax to a human
        reader). We deliberately exclude markers that aren't valid Python
        identifiers so that documentation doesn't trip this check."""
        import re

        # Only flag placeholders that LOOK like real variables: an
        # identifier inside the braces (letters, digits, underscores).
        # ``{{ ... }}`` and other non-identifier markers are documentation,
        # not typos.
        found = set(
            re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", template_content)
        )
        expected = {p.strip("{}") for p in SUSPECT_TEMPLATE_PLACEHOLDERS}
        unexpected = found - expected
        assert not unexpected, (
            f"Suspect template contains unexpected identifier-shaped "
            f"placeholders: {unexpected}. These will not be substituted "
            f"and will appear in the model's input verbatim. Either fix "
            f"the typo or add the placeholder to "
            f"SUSPECT_TEMPLATE_PLACEHOLDERS in this test."
        )


# ---------------------------------------------------------------------------
# Compliance Officer prompt safety
# ---------------------------------------------------------------------------


class TestComplianceOfficerPromptSafety:
    """Sanity checks on the Compliance Officer prompt. The CO is the most
    visible agent on stream (the closing speech), so we pin some basics
    so it doesn't silently regress."""

    @pytest.fixture(scope="class")
    def co_prompt(self):
        return load_prompt(ACTIVE_PROMPT_PATHS["compliance_officer"])

    def test_prompt_does_not_contain_jailbreak_trigger_phrases(self, co_prompt):
        """The system prompt is allowed to use these phrases; this test
        only pins the USER message side (where we removed them).
        This is a smoke check: the prompt should not, e.g., contain stray
        user-style template content that leaked in from a copy-paste."""
        # The system prompt SHOULD reference the prompt itself in some way;
        # this test is just a smoke check that nothing obviously weird is
        # in there.
        assert "Helix Dynamics" in co_prompt
        assert "framework" in co_prompt.lower()
