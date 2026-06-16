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
                    Slower, needs Arraylake auth. No synthetic fill — only the
                    variables IFS actually provides.

Both backends carry the same variable set: t2m, d2m, and the derived heat index
(all from real 2t/2d). Wind/precip/cloud/solar were dropped (no IFS extraction).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

log = logging.getLogger("recompute")

from world_cup_climate.config import PROJECT_DIR
from world_cup_climate.fixtures import Match, load_matches
from world_cup_climate.locations import Place
from world_cup_climate.sports import heat_index_celsius, relative_humidity

OUT_DIR = PROJECT_DIR / "frontend" / "public" / "data"

# Variables carried in every per-place timeseries (canonical key -> label/unit/color).
# Only what real IFS 2t/2d gives us: temperature, dewpoint, and the derived heat index.
VARIABLES = {
    "t2m": {"label": "Temperature", "unit": "°C", "color": "#f97316"},
    "heat_index": {"label": "Feels like", "unit": "°C", "color": "#ef4444"},
    "d2m": {"label": "Dewpoint", "unit": "°C", "color": "#22d3ee"},
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

def synth_series(place: Place, times: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Plausible hourly t2m/d2m/heat-index for one location over `times` (UTC, naive).

    Temperature/dewpoint are *smooth* functions of lat/lon, so two nearby points
    (e.g. a stadium and its own capital) get near-identical climate and a ~0 delta,
    as real forecast data would.
    """
    lat, lon = place.lat, place.lon
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

    return {
        "t2m": t2m,
        "heat_index": np.asarray(hi, dtype=float),
        "d2m": d2m,
    }


def _pkey(p: Place) -> tuple[float, float]:
    return (round(p.lat, 4), round(p.lon, 4))


def make_ifs_series_fn(matches: list[Match]):
    """Prefetch every unique fixture point in one bulk IFS read, then serve series
    from memory. Avoids the per-location round-trips that made this slow."""
    from world_cup_climate.ifs import extract_points

    uniq: dict[tuple[float, float], tuple[float, float]] = {}
    for m in matches:
        for p in (m.venue, m.capital_a, m.capital_b):
            uniq[_pkey(p)] = (p.lat, p.lon)

    log.info("extracting %d unique points in one bulk read...", len(uniq))
    t0 = time.perf_counter()
    keys = list(uniq)
    dfs = dict(zip(keys, extract_points([uniq[k] for k in keys])))
    log.info("  extracted %d points in %.1fs", len(keys), time.perf_counter() - t0)

    cols = ["t2m_c", "d2m_c", "heat_index_c"]

    def series_fn(place: Place, times: pd.DatetimeIndex) -> dict[str, np.ndarray]:
        s = dfs[_pkey(place)][cols].reindex(times).interpolate("time")
        return {
            "t2m": s["t2m_c"].to_numpy(),
            "heat_index": s["heat_index_c"].to_numpy(),
            "d2m": s["d2m_c"].to_numpy(),
        }

    return series_fn


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
    d = {
        k: match[k]
        for k in (
            "id", "date", "stage", "kickoff_utc", "kickoff_local",
            "team_a", "team_b", "venue", "t2m_at_kickoff", "heat_index_at_kickoff",
        )
    }
    if "t2m_map" in match:
        d["t2m_map"] = match["t2m_map"]
    return d


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["demo", "ifs"], default="demo")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    matches = load_matches()
    map_keys: list[str | None] = [None] * len(matches)
    if args.source == "ifs":
        from world_cup_climate.ifs import latest_init, na_t2m_fields
        log.info("IFS latest init cycle: %s", latest_init())
        series_fn = make_ifs_series_fn(matches)
        log.info("extracting North-America t2m fields for match timings...")
        t0 = time.perf_counter()
        fields, meta, map_keys = na_t2m_fields(
            [pd.Timestamp(m.kickoff_utc).tz_convert(None) for m in matches]
        )
        for k, vals in fields.items():
            # NaN (masked/ocean cells) isn't valid JSON -> null (transparent in UI).
            clean = [None if v != v else v for v in vals]
            write_json(args.out / "t2m" / f"{k}.json", {**meta, "values": clean})
        log.info("  %d unique t2m fields (%d×%d) in %.1fs",
                 len(fields), meta["nx"], meta["ny"], time.perf_counter() - t0)
    else:
        series_fn = synth_series
    log.info("building %d matches from source=%s -> %s", len(matches), args.source, args.out)

    t0 = time.perf_counter()
    by_date: dict[str, list[dict]] = {}
    for m, mkey in zip(tqdm(matches, desc="matches", unit="match"), map_keys):
        doc = build_match(m, series_fn)
        if mkey:
            doc["t2m_map"] = f"t2m/{mkey}.json"
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
    log.info("wrote %d matches across %d dates in %.1fs",
             len(matches), len(by_date), time.perf_counter() - t0)


if __name__ == "__main__":
    main()
