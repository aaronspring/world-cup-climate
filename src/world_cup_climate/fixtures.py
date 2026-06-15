"""Load curated World Cup fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from .config import DATA_DIR
from .locations import Place, capital, venue


@dataclass(frozen=True)
class Match:
    date: str            # YYYY-MM-DD (matchday)
    kickoff_utc: str
    stage: str
    team_a: str
    team_b: str
    venue_key: str

    @property
    def matchday(self) -> pd.Timestamp:
        return pd.Timestamp(self.date)

    @property
    def title(self) -> str:
        return f"{self.team_a} vs {self.team_b}"

    @property
    def venue(self) -> Place:
        return venue(self.venue_key)

    @property
    def capital_a(self) -> Place:
        return capital(self.team_a)

    @property
    def capital_b(self) -> Place:
        return capital(self.team_b)

    def places(self) -> list[Place]:
        """The three locations compared for this match."""
        return [self.venue, self.capital_a, self.capital_b]


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
