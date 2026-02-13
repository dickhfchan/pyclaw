"""Integration test for the skills pipeline.

Creates temp SKILL.md -> discovers -> verifies skill in prompt -> retrieves content.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.skills.loader import discover_skills, format_skills_list, get_skill_content


@pytest.fixture
def skills_env(tmp_path: Path):
    """Set up a temporary skills directory with sample skills."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a weather skill
    weather_dir = skills_dir / "weather"
    weather_dir.mkdir()
    (weather_dir / "SKILL.md").write_text(
        '---\n'
        'name: weather\n'
        'description: "Get current weather using curl."\n'
        'metadata:\n'
        '  requires:\n'
        '    bins: ["curl"]\n'
        '---\n\n'
        '# Weather\n\n'
        'Use `curl -s "wttr.in/London?format=3"` for weather.\n'
    )

    # Create a notes skill (no requirements)
    notes_dir = skills_dir / "notes"
    notes_dir.mkdir()
    (notes_dir / "SKILL.md").write_text(
        '---\n'
        'name: notes\n'
        'description: "Create and manage notes."\n'
        '---\n\n'
        '# Notes\n\n'
        'Write notes to a file.\n'
    )

    return skills_dir


def test_discover_all_skills(skills_env):
    skills = discover_skills(skills_env)
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert "weather" in names
    assert "notes" in names


def test_skills_appear_in_formatted_list(skills_env):
    skills = discover_skills(skills_env)
    formatted = format_skills_list(skills)

    assert "weather" in formatted
    assert "notes" in formatted
    assert "## Available Skills" in formatted


def test_skill_content_retrievable(skills_env):
    skills = discover_skills(skills_env)

    weather_content = get_skill_content(skills, "weather")
    assert weather_content is not None
    assert "wttr.in" in weather_content

    notes_content = get_skill_content(skills, "notes")
    assert notes_content is not None
    assert "Write notes" in notes_content


def test_nonexistent_skill_returns_none(skills_env):
    skills = discover_skills(skills_env)
    assert get_skill_content(skills, "nonexistent") is None


def test_new_skill_discovered_on_rescan(skills_env):
    skills = discover_skills(skills_env)
    assert len(skills) == 2

    # Add a new skill
    new_dir = skills_env / "timer"
    new_dir.mkdir()
    (new_dir / "SKILL.md").write_text(
        '---\n'
        'name: timer\n'
        'description: "Set timers."\n'
        '---\n\n'
        '# Timer\n\n'
        'Use sleep command for timers.\n'
    )

    # Re-scan
    skills = discover_skills(skills_env)
    assert len(skills) == 3
    names = {s.name for s in skills}
    assert "timer" in names
