"""Load curated World Cup fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .config import DATA_DIR
from .locations import Place, capital, has_capital, venue


@dataclass(frozen=True)
class Match:
    date: str            # YYYY-MM-DD (matchday)
    kickoff_utc: str
    stage: str
    team_a: str
    team_b: str
    venue_key: str

    @property
    def title(self) -> str:
        return f"{self.team_a} vs {self.team_b}"

    @property
    def venue(self) -> Place:
        return venue(self.venue_key)

    @property
    def capital_a(self) -> Place | None:
        """Home capital of ``team_a``, or ``None`` for a bracket placeholder."""
        return capital(self.team_a) if has_capital(self.team_a) else None

    @property
    def capital_b(self) -> Place | None:
        """Home capital of ``team_b``, or ``None`` for a bracket placeholder."""
        return capital(self.team_b) if has_capital(self.team_b) else None

    def places(self) -> list[Place]:
        """The locations compared for this match: venue plus any resolvable
        capitals (knockout placeholders without a capital are skipped)."""
        return [p for p in (self.venue, self.capital_a, self.capital_b) if p is not None]


def load_matches(date: str | None = None) -> list[Match]:
    """All curated matches, optionally filtered to a single matchday (YYYY-MM-DD)."""
    with open(DATA_DIR / "fixtures.json") as f:
        raw = json.load(f)
    matches = [
        Match(
            date=m["date"],
            kickoff_utc=m["kickoff_utc"],
            stage=m["stage"],
            team_a=m["team_a"],
            team_b=m["team_b"],
            venue_key=m["venue"],
        )
        for m in raw["matches"]
    ]
    if date is not None:
        matches = [m for m in matches if m.date == date]
    return matches
