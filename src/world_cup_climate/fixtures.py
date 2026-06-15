"""Load the (hardcoded) World Cup fixtures and capital-city lookup."""

from __future__ import annotations

import datetime as dt
import functools
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FIXTURES_PATH = DATA_DIR / "fixtures.json"


@functools.lru_cache(maxsize=1)
def _load() -> dict:
    with FIXTURES_PATH.open() as fh:
        return json.load(fh)


def capitals() -> dict:
    """Mapping of country name -> {name, lat, lon, flag}."""
    return _load()["capitals"]


def capital(country: str) -> dict:
    caps = capitals()
    if country not in caps:
        raise KeyError(f"No capital configured for {country!r}. Add it to fixtures.json.")
    return {"country": country, **caps[country]}


def all_matches() -> list[dict]:
    return _load()["matches"]


def matches_on(day: dt.date) -> list[dict]:
    """Fixtures scheduled on a given date."""
    iso = day.isoformat()
    return [m for m in all_matches() if m["date"] == iso]


def next_matchday(today: dt.date) -> dt.date | None:
    """First fixture date on/after ``today`` (so the demo always has a match)."""
    future = sorted({m["date"] for m in all_matches() if m["date"] >= today.isoformat()})
    return dt.date.fromisoformat(future[0]) if future else None
