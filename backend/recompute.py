"""Recompute job: build the static JSON contract the frontend reads.

Writes three kinds of file under ``frontend/public/data`` (see docs/ARCHITECTURE.md
section 2 / 4):

    cycles/latest.json   cycle metadata + index of available match dates
    days/{date}.json     pins for that day (one entry per match)
    matches/{id}.json    full per-match timeseries + overview stats

Two data backends:

    --source demo   physically plausible synthetic forecast (no auth, default).
                    Deterministic per location so re-runs are stable.
    --source ifs    real ECMWF IFS point extraction via world_cup_climate.ifs.
                    Slower, needs Arraylake auth. (t2m/d2m/rh/heat-index only;
                    other vars fall back to the synthetic model.)

The synthetic model is good enough to make the app look real locally; swap in the
full server-side IFS extraction (ARCHITECTURE step 3) when wiring live data.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from world_cup_climate.config import PROJECT_DIR
from world_cup_climate.fixtures import Match, load_matches
from world_cup_climate.locations import Place
from world_cup_climate.sports import heat_index_celsius, relative_humidity

OUT_DIR = PROJECT_DIR / "frontend" / "public" / "data"

# Variables carried in every per-place timeseries (canonical key -> label/unit/color).
VARIABLES = {
    "t2m": {"label": "Temperature", "unit": "°C", "color": "#f97316"},
    "heat_index": {"label": "Feels like", "unit": "°C", "color": "#ef4444"},
    "d2m": {"label": "Dewpoint", "unit": "°C", "color": "#22d3ee"},
    "rh": {"label": "Humidity", "unit": "%", "color": "#38bdf8"},
    "wind": {"label": "Wind", "unit": "m/s", "color": "#a78bfa"},
    "tp": {"label": "Precip", "unit": "mm", "color": "#60a5fa"},
    "cloud": {"label": "Cloud", "unit": "%", "color": "#94a3b8"},
    "ssrd": {"label": "Solar", "unit": "W/m²", "color": "#fbbf24"},
}

WINDOW_BEFORE = pd.Timedelta(days=1)   # series starts matchday - 1
WINDOW_AFTER = pd.Timedelta(days=5)    # ... and runs 5 days past for the outlook


def utc_offset_hours(lon: float) -> int:
    """Rough wall-clock offset from longitude.

    ponytail: solar-longitude estimate, accurate to ~1-2h. Only the *difference*
    between two cities is shown. Upgrade to timezonefinder + zoneinfo if exact
    DST-aware offsets matter.
    """
    return int(round(lon / 15.0))


# --- synthetic forecast model -------------------------------------------------

def _seed(lat: float, lon: float) -> np.random.Generator:
    return np.random.default_rng(int((lat + 90) * 1000) * 100000 + int((lon + 180) * 1000))


def synth_series(place: Place, times: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Plausible hourly forecast for one location over `times` (UTC, tz-naive).

    Temperature/dewpoint are *smooth* functions of lat/lon, so two nearby points
    (e.g. a stadium and its own capital) get near-identical climate and a ~0 delta,
    as real forecast data would. Only chart-only fields (wind/precip/cloud) carry
    seeded random weather variety.
    """
    rng = _seed(place.lat, place.lon)
    lat, lon = place.lat, place.lon
    n = len(times)
    hours = times.view("int64") / 3.6e12  # hours since epoch
    local_h = (np.array([t.hour + t.minute / 60 for t in times]) + lon / 15.0) % 24

    # June climatological daily-mean temperature: a smooth parabola peaking in the
    # NH subtropics (hot summer) and falling off toward the SH (winter) and poles.
    micro = 1.5 * math.sin(math.radians(lat) * 4) * math.cos(math.radians(lon) * 3)  # smooth city-scale
    # ponytail: no altitude term (not in locations.json), so high cities like
    # Mexico City read a few °C warm. Add an elevation lookup when wiring real IFS.
    t_mean = float(np.clip(26 - 0.008 * (lat - 18) ** 2 + micro, -8, 38))

    # Dryness 0 (humid/coastal) .. 1 (continental/desert): bigger diurnal range, drier.
    dryness = float(np.clip(0.3 + abs(lat) / 120 + 0.15 * math.sin(math.radians(lon) * 2), 0.05, 0.95))
    diurnal_amp = 4 + 7 * dryness

    # Large-scale synoptic wave: phase set by location (weather travels), not random,
    # so co-located points stay in phase.
    synoptic = 3.5 * np.sin(2 * np.pi * (hours - hours[0]) / 84 + math.radians(lon) * 1.5 + math.radians(lat))

    diurnal = diurnal_amp * np.cos(2 * np.pi * (local_h - 15) / 24)
    t2m = t_mean + diurnal + synoptic

    spread = (3 + 12 * dryness) * (0.6 + 0.4 * np.clip((local_h - 6) / 12, 0, 1))
    d2m = np.minimum(t2m - spread, t2m - 0.5)

    rh = relative_humidity(t2m, d2m)
    hi = heat_index_celsius(t2m, rh)

    wind = np.clip(2 + 3 * abs(np.sin(2 * np.pi * hours / 23 + lat)) + rng.normal(0, 0.8, n), 0.2, 18)

    # Showers: more likely when humid; cluster a few wet hours.
    wet_prob = (1 - dryness) * 0.18
    wet = rng.random(n) < wet_prob
    tp = np.where(wet, rng.gamma(2.0, 1.5, n), 0.0)

    cloud = np.clip(0.25 + 0.5 * (1 - dryness) + 0.4 * (tp > 0) + rng.normal(0, 0.12, n), 0, 1)

    # Clear-sky solar from a daytime bell, attenuated by cloud.
    decl = 23.44 * math.cos(math.radians((172 - 172)))  # ~solstice, June
    elev = np.sin(math.radians(lat)) * math.sin(math.radians(decl)) + math.cos(
        math.radians(lat)
    ) * math.cos(math.radians(decl)) * np.cos(2 * np.pi * (local_h - 12) / 24)
    ssrd = np.clip(1050 * np.clip(elev, 0, 1) * (1 - 0.7 * cloud), 0, 1100)

    return {
        "t2m": t2m,
        "heat_index": np.asarray(hi, dtype=float),
        "d2m": d2m,
        "rh": np.asarray(rh, dtype=float),
        "wind": wind,
        "tp": tp,
        "cloud": cloud * 100,
        "ssrd": ssrd,
    }


def ifs_series(place: Place, times: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Real IFS t2m/d2m/rh/heat-index; synthetic fill for the rest."""
    from world_cup_climate.ifs import location_series

    s = location_series(place.lat, place.lon).reindex(times).interpolate("time")
    out = synth_series(place, times)  # for wind/tp/cloud/ssrd
    out["t2m"] = s["t2m_c"].to_numpy()
    out["d2m"] = s["d2m_c"].to_numpy()
    out["rh"] = s["rh"].to_numpy()
    out["heat_index"] = s["heat_index_c"].to_numpy()
    return out


# --- assembly ----------------------------------------------------------------

def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def match_id(m: Match) -> str:
    return f"{m.date}_{slug(m.team_a)}-vs-{slug(m.team_b)}"


def round_series(a: np.ndarray, nd: int = 1) -> list[float]:
    return [round(float(x), nd) for x in a]


def window_mean(times: pd.DatetimeIndex, vals: np.ndarray, ko: pd.Timestamp) -> float:
    mask = (times >= ko) & (times <= ko + pd.Timedelta(hours=2))
    sel = vals[mask]
    return float(np.mean(sel)) if len(sel) else float(np.mean(vals))


def venue_place(m: Match) -> Place:
    return m.venue


def build_match(m: Match, series_fn) -> dict:
    md = pd.Timestamp(m.date)
    times = pd.date_range(md - WINDOW_BEFORE, md + WINDOW_AFTER, freq="1h")
    ko = pd.Timestamp(m.kickoff_utc).tz_convert(None)

    v, ca, cb = venue_place(m), m.capital_a, m.capital_b
    sv = series_fn(v, times)
    sa = series_fn(ca, times)
    sb = series_fn(cb, times)

    v_off = utc_offset_hours(v.lon)
    kickoff_local = (ko + pd.Timedelta(hours=v_off)).strftime("%Y-%m-%d %H:%M")

    def stats(home: Place, sh: dict) -> dict:
        h_off = utc_offset_hours(home.lon)
        return {
            "home": home.name,
            "country": home.country,
            "tz_diff_h": h_off - v_off,
            "d_t2m": round(window_mean(times, sv["t2m"], ko) - window_mean(times, sh["t2m"], ko), 1),
            "d_d2m": round(window_mean(times, sv["d2m"], ko) - window_mean(times, sh["d2m"], ko), 1),
            "d_heat_index": round(
                window_mean(times, sv["heat_index"], ko) - window_mean(times, sh["heat_index"], ko), 1
            ),
        }

    return {
        "id": match_id(m),
        "date": m.date,
        "stage": m.stage,
        "kickoff_utc": m.kickoff_utc,
        "kickoff_local": kickoff_local,
        "team_a": m.team_a,
        "team_b": m.team_b,
        "venue": {
            "key": m.venue_key,
            "stadium": v.name,
            "city": v.label.split(" — ")[-1],
            "country": v.country,
            "lat": v.lat,
            "lon": v.lon,
        },
        "t2m_at_kickoff": round(window_mean(times, sv["t2m"], ko), 1),
        "heat_index_at_kickoff": round(window_mean(times, sv["heat_index"], ko), 1),
        "window": {"start": times[0].isoformat() + "Z", "end": times[-1].isoformat() + "Z"},
        "series": {
            "time": [t.isoformat() + "Z" for t in times],
            "venue": {k: round_series(sv[k]) for k in VARIABLES},
            "team_a": {k: round_series(sa[k]) for k in VARIABLES},
            "team_b": {k: round_series(sb[k]) for k in VARIABLES},
        },
        "stats": {"team_a": stats(ca, sa), "team_b": stats(cb, sb)},
    }


def pin(match: dict) -> dict:
    """Lightweight per-day pin entry (subset of the full match doc)."""
    return {
        k: match[k]
        for k in (
            "id", "date", "stage", "kickoff_utc", "kickoff_local",
            "team_a", "team_b", "venue", "t2m_at_kickoff", "heat_index_at_kickoff",
        )
    }


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["demo", "ifs"], default="demo")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    series_fn = synth_series if args.source == "demo" else ifs_series
    matches = load_matches()
    print(f"building {len(matches)} matches from source={args.source} -> {args.out}")

    by_date: dict[str, list[dict]] = {}
    for m in matches:
        doc = build_match(m, series_fn)
        write_json(args.out / "matches" / f"{doc['id']}.json", doc)
        by_date.setdefault(m.date, []).append(pin(doc))

    for date, pins in by_date.items():
        write_json(args.out / "days" / f"{date}.json", {"date": date, "matches": pins})

    cycle = {
        "cycle": datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat(),
        "source": args.source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dates": sorted(by_date),
        "variables": VARIABLES,
    }
    write_json(args.out / "cycles" / "latest.json", cycle)
    print(f"wrote {len(matches)} matches across {len(by_date)} dates")


if __name__ == "__main__":
    main()
