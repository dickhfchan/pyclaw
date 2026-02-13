from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.skills.loader import (
    discover_skills,
    format_skills_list,
    get_skill_content,
    _parse_frontmatter,
)
from src.skills.types import Skill

VALID_SKILL = """\
---
name: weather
description: "Get current weather and forecasts."
metadata:
  requires:
    bins: ["curl"]
---

# Weather

Get weather data using curl.

## Usage

```bash
curl -s "wttr.in/London?format=3"
```
"""

SKILL_NO_BINS = """\
---
name: notes
description: "Manage notes."
---

# Notes

A simple skill with no requirements.
"""

SKILL_MISSING_ENV = """\
---
name: github
description: "GitHub integration."
metadata:
  requires:
    env: ["GITHUB_TOKEN_THAT_DOES_NOT_EXIST"]
---

# GitHub

Needs a token.
"""

SKILL_BAD_FRONTMATTER = """\
---
not: valid: yaml: [
---

Some body content.
"""


def _create_skill(tmp_path: Path, name: str, content: str) -> Path:
    """Create a skill directory with a SKILL.md file."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


def test_discover_valid_skill(tmp_path: Path) -> None:
    _create_skill(tmp_path, "weather", VALID_SKILL)
    skills = discover_skills(tmp_path)
    assert len(skills) == 1
    s = skills[0]
    assert s.name == "weather"
    assert s.description == "Get current weather and forecasts."
    assert "curl" in s.requires_bins
    assert s.available is True  # curl should be available
    assert "# Weather" in s.content


def test_discover_no_bins_required(tmp_path: Path) -> None:
    _create_skill(tmp_path, "notes", SKILL_NO_BINS)
    skills = discover_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "notes"
    assert skills[0].available is True
    assert skills[0].requires_bins == []


def test_discover_missing_env(tmp_path: Path) -> None:
    _create_skill(tmp_path, "github", SKILL_MISSING_ENV)
    skills = discover_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "github"
    assert skills[0].available is False


def test_discover_bad_frontmatter(tmp_path: Path) -> None:
    _create_skill(tmp_path, "bad", SKILL_BAD_FRONTMATTER)
    skills = discover_skills(tmp_path)
    assert len(skills) == 1
    # Falls back to directory name when frontmatter is invalid
    assert skills[0].name == "bad"


def test_discover_empty_directory(tmp_path: Path) -> None:
    skills = discover_skills(tmp_path)
    assert skills == []


def test_discover_nonexistent_directory(tmp_path: Path) -> None:
    skills = discover_skills(tmp_path / "nonexistent")
    assert skills == []


def test_discover_dir_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "empty_dir").mkdir()
    skills = discover_skills(tmp_path)
    assert skills == []


def test_discover_multiple_skills(tmp_path: Path) -> None:
    _create_skill(tmp_path, "weather", VALID_SKILL)
    _create_skill(tmp_path, "notes", SKILL_NO_BINS)
    skills = discover_skills(tmp_path)
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"weather", "notes"}


def test_discover_missing_required_bin(tmp_path: Path) -> None:
    content = """\
---
name: impossible
description: "Needs a nonexistent binary."
metadata:
  requires:
    bins: ["__nonexistent_bin_xyz__"]
---

# Impossible

This skill requires a binary that doesn't exist.
"""
    _create_skill(tmp_path, "impossible", content)
    skills = discover_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].available is False


def test_format_skills_list() -> None:
    skills = [
        Skill(name="weather", description="Weather info", content="", path="", available=True),
        Skill(name="notes", description="Note taking", content="", path="", available=True),
        Skill(name="hidden", description="Unavailable", content="", path="", available=False),
    ]
    result = format_skills_list(skills)
    assert "weather" in result
    assert "notes" in result
    assert "hidden" not in result
    assert "## Available Skills" in result


def test_format_skills_list_empty() -> None:
    assert format_skills_list([]) == ""


def test_format_skills_list_all_unavailable() -> None:
    skills = [
        Skill(name="x", description="X", content="", path="", available=False),
    ]
    assert format_skills_list(skills) == ""


def test_get_skill_content() -> None:
    skills = [
        Skill(name="weather", description="", content="Use curl for weather", path="", available=True),
        Skill(name="notes", description="", content="Manage notes", path="", available=True),
    ]
    assert get_skill_content(skills, "weather") == "Use curl for weather"
    assert get_skill_content(skills, "notes") == "Manage notes"
    assert get_skill_content(skills, "nonexistent") is None


def test_parse_frontmatter_valid() -> None:
    meta, body = _parse_frontmatter(VALID_SKILL)
    assert meta["name"] == "weather"
    assert "# Weather" in body


def test_parse_frontmatter_none() -> None:
    meta, body = _parse_frontmatter("Just plain text")
    assert meta == {}
    assert body == "Just plain text"
