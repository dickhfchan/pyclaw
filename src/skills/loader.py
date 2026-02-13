from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from src.skills.types import Skill


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a Markdown file.

    Returns (metadata_dict, body_text). If no frontmatter is found,
    returns an empty dict and the full text.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return {}, text

    try:
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict):
            return {}, text
    except yaml.YAMLError:
        return {}, text

    return metadata, match.group(2)


def _check_bins(bins: list[str]) -> bool:
    """Check if all required binaries are on PATH."""
    return all(shutil.which(b) is not None for b in bins)


def _check_env(env_vars: list[str]) -> bool:
    """Check if all required environment variables are set."""
    return all(os.environ.get(v) for v in env_vars)


def discover_skills(skills_dir: str | Path) -> list[Skill]:
    """Scan the skills directory for SKILL.md files and load them.

    Each subdirectory containing a SKILL.md file is treated as a skill.
    Returns a list of Skill objects with the `available` flag set based
    on whether required binaries and env vars are present.
    """
    skills_dir = Path(skills_dir)
    if not skills_dir.exists():
        return []

    skills: list[Skill] = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.exists():
            continue

        text = skill_file.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(text)

        name = metadata.get("name", entry.name)
        description = metadata.get("description", "")
        requires = metadata.get("metadata", {}).get("requires", {})
        requires_bins = requires.get("bins", [])
        requires_env = requires.get("env", [])

        if not isinstance(requires_bins, list):
            requires_bins = []
        if not isinstance(requires_env, list):
            requires_env = []

        available = _check_bins(requires_bins) and _check_env(requires_env)

        skills.append(
            Skill(
                name=name,
                description=description,
                content=body.strip(),
                path=str(skill_file),
                requires_bins=requires_bins,
                requires_env=requires_env,
                available=available,
            )
        )

    return skills


def format_skills_list(skills: list[Skill]) -> str:
    """Format available skills as a Markdown list for the system prompt."""
    available = [s for s in skills if s.available]
    if not available:
        return ""

    lines = ["## Available Skills\n"]
    for s in available:
        lines.append(f"- **{s.name}**: {s.description}")
    return "\n".join(lines)


def get_skill_content(skills: list[Skill], skill_name: str) -> str | None:
    """Return the full Markdown body of a skill by name."""
    for s in skills:
        if s.name == skill_name:
            return s.content
    return None


class SkillWatcher:
    """Watches the skills directory for changes and re-runs discovery."""

    def __init__(
        self,
        skills_dir: str | Path,
        on_update: Callable[[list[Skill]], None] | None = None,
        debounce_seconds: float = 5.0,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        self.on_update = on_update
        self.debounce_seconds = debounce_seconds
        self._observer: Any = None

    def start(self) -> None:
        """Start watching for skill file changes."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return

        watcher = self

        class _Handler(FileSystemEventHandler):
            def __init__(self) -> None:
                self._last_sync = 0.0

            def on_any_event(self, event: Any) -> None:
                if not event.src_path.endswith(".md"):
                    return
                now = time.time()
                if now - self._last_sync < watcher.debounce_seconds:
                    return
                self._last_sync = now
                skills = discover_skills(watcher.skills_dir)
                if watcher.on_update:
                    watcher.on_update(skills)

        observer = Observer()
        observer.schedule(_Handler(), str(self.skills_dir), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer is not None:
            self._observer.stop()
            self._observer = None
