from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    """Represents a single skill loaded from a SKILL.md file."""

    name: str
    description: str
    content: str
    path: str
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)
    available: bool = True
