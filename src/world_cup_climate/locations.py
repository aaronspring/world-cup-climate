"""Curated lookup of World Cup venues and national capitals -> lat/lon.

Offline and deterministic; swap for a geocoder later if arbitrary cities are needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from .config import DATA_DIR


@dataclass(frozen=True)
class Place:
    name: str          # display name, e.g. "Madrid" or "AT&T Stadium"
    label: str         # role label, e.g. "Capital of Brazil" / "Match venue"
    country: str
    lat: float         # degrees north
    lon: float         # degrees east, -180..180 (convert with % 360 at read time)


@lru_cache(maxsize=1)
def _raw() -> dict:
    with open(DATA_DIR / "locations.json") as f:
        return json.load(f)


def venue(key: str) -> Place:
    v = _raw()["venues"][key]
    return Place(
        name=v["stadium"],
        label=f"Match venue — {v['city']}",
        country=v["country"],
        lat=v["lat"],
        lon=v["lon"],
    )


def capital(country: str) -> Place:
    caps = _raw()["capitals"]
    if country not in caps:
        raise KeyError(
            f"No capital for {country!r} in locations.json. "
            f"Known: {sorted(caps)}"
        )
    c = caps[country]
    return Place(
        name=c["capital"],
        label=f"Capital of {country}",
        country=country,
        lat=c["lat"],
        lon=c["lon"],
    )
