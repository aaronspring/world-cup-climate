#!/usr/bin/env python3
"""Scaffold a sports-weather app (weather forecast at the locations of a sports
event, deployed to GitHub Pages).

Emits a complete, runnable, deployable project: a Python recompute backend
(synthetic "demo" source with zero auth, plus a real ECMWF IFS source), a React +
MapLibre single-page frontend that reads the static JSON contract, and a GitHub
Pages workflow. This is a generalisation of the world-cup-climate app: the
domain is abstracted to *occasions* (a scheduled thing with a time, a primary
map location, and 0..N "compare" locations) so it fits football matches
(venue vs team home cities), cycling stages (finish vs start), and more.

Usage:
    python scaffold.py --out ../tour-de-france-weather \
        --slug tour-de-france-weather \
        --title "Tour de France Weather" \
        --repo aaronspring/tour-de-france-weather \
        --sport cycling

--repo drives the Vite base path (project GitHub Pages live at
/<repo-name>/). --sport picks the seed data (football | cycling | generic);
the agent then edits data/events.json + data/locations.json for the real event.

The script is pure stdlib, so it always runs. After it finishes, generate the
demo JSON and preview:

    cd <out>
    uv run python backend/recompute.py --source demo   # writes frontend/public/data
    cd frontend && npm install && npm run dev
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# --------------------------------------------------------------------------- #
# File templates. Tokens __APP_TITLE__ / __APP_SLUG__ / __BASE_PATH__ are
# replaced at write time. Bodies are raw strings so JS/TS/CSS escapes pass
# through untouched.
# --------------------------------------------------------------------------- #

FILES: dict[str, str] = {}


def _f(path: str, body: str) -> None:
    FILES[path] = body


# ---- backend --------------------------------------------------------------- #

_f("backend/config.py", r'''"""Shared paths and the IFS forecast repo id."""
from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
OUT_DIR = PROJECT_DIR / "frontend" / "public" / "data"

# Open ECMWF IFS 15-day forecast with clean CF coordinates (real lat/lon,
# time = 6-hourly init, step = timedelta out to 15 days), via Arraylake.
IFS_OPEN_REPO = "spring-data/ecwmf-ifs-15-days-forecast-open"
''')

_f("backend/sports.py", r'''"""Sports-relevant derived weather variables (heat stress).

Pure-numpy indices (relative humidity, NOAA heat index, WBGT) have no heavy
dependencies and drive the demo source. humidex / UTCI are optional and only
imported when you install the `ifs` extra (they use xclim).
"""
from __future__ import annotations

import numpy as np


def kelvin_to_celsius(k):
    return k - 273.15


def relative_humidity(t2m_c, d2m_c):
    """RH (%) from temperature and dewpoint in degC (Magnus formula)."""
    a, b = 17.625, 243.04
    e_d = np.exp((a * d2m_c) / (b + d2m_c))
    e_t = np.exp((a * t2m_c) / (b + t2m_c))
    return np.clip(100.0 * e_d / e_t, 0, 100)


def heat_index_celsius(t2m_c, rh):
    """NOAA heat index ("feels like") in degC from temp (degC) and RH (%)."""
    t_f = t2m_c * 9 / 5 + 32
    hi_simple = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    hi_full = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 6.83783e-3 * t_f**2
        - 5.481717e-2 * rh**2
        + 1.22874e-3 * t_f**2 * rh
        + 8.5282e-4 * t_f * rh**2
        - 1.99e-6 * t_f**2 * rh**2
    )
    hi_f = np.where((hi_simple + t_f) / 2 >= 80.0, hi_full, hi_simple)
    return (np.asarray(hi_f) - 32) * 5 / 9


def wbgt_celsius(t2m_c, rh, wind_speed_ms, ssrd_wm2=None):
    """Outdoor Wet Bulb Globe Temperature (degC) — the heat-stress standard for
    sport. WBGT = 0.7*NWB + 0.2*GT + 0.1*DBT (ISO 7243). NWB via Stull (2011),
    globe temperature via a simplified solar/wind balance.
    """
    t2m = np.asarray(t2m_c, dtype=float)
    rh_ = np.asarray(rh, dtype=float)
    tw = (
        t2m * np.arctan(0.151977 * (rh_ + 8.313659) ** 0.5)
        + np.arctan(t2m + rh_)
        - np.arctan(rh_ - 1.676331)
        + 0.00391838 * rh_ ** 1.5 * np.arctan(0.023101 * rh_)
        - 4.686035
    )
    if ssrd_wm2 is not None:
        solar = np.clip(np.asarray(ssrd_wm2, dtype=float), 0, None)
        wind = np.maximum(np.asarray(wind_speed_ms, dtype=float), 0.1)
        tg = np.clip(t2m + 17.5 * (solar / 1000.0) - 2.5 * np.sqrt(wind), t2m, t2m + 30.0)
    else:
        tg = t2m + 2.0
    return 0.7 * tw + 0.2 * tg + 0.1 * t2m
''')

_f("backend/model.py", r'''"""Load the two static files that drive the app into typed objects.

    data/events.json    the schedule (occasions)
    data/locations.json  key -> point (lat/lon + label)

An *occasion* is the atomic scheduled thing: a time, one primary `location`
(the map pin) and 0..N `compare` locations (drawn on the chart against the
primary). Football: location = venue, compare = the two team home cities.
Cycling: location = stage finish, compare = [stage start].
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Place:
    key: str
    name: str
    role: str
    country: str
    lat: float
    lon: float
    sublabel: str = ""


@dataclass(frozen=True)
class Occasion:
    id: str
    date: str
    start_utc: str
    title: str
    subtitle: str
    location: Place
    compare: tuple[Place, ...]


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def load(data_dir: Path) -> tuple[dict, list[Occasion]]:
    events = json.loads((data_dir / "events.json").read_text())
    locs = json.loads((data_dir / "locations.json").read_text())

    def place(key: str) -> Place:
        v = locs[key]
        return Place(
            key=key,
            name=v["name"],
            role=v.get("role", "point"),
            country=v.get("country", ""),
            lat=float(v["lat"]),
            lon=float(v["lon"]),
            sublabel=v.get("sublabel", ""),
        )

    occ: list[Occasion] = []
    for o in events["occasions"]:
        oid = o.get("id") or f"{o['date']}_{_slug(o['title'])}"
        occ.append(
            Occasion(
                id=oid,
                date=o["date"],
                start_utc=o["start_utc"],
                title=o["title"],
                subtitle=o.get("subtitle", ""),
                location=place(o["location"]),
                compare=tuple(place(k) for k in o.get("compare", [])),
            )
        )
    return events, occ
''')

_f("backend/weather_ifs.py", r'''"""Real ECMWF IFS point extraction (the `--source ifs` backend).

Joins the step-0 analysis history (recent conditions, 6-hourly) with the latest
init's full 15-day forecast into one continuous hourly series per point. Needs
the `ifs` extra (xarray + arraylake + xclim + icechunk) and Arraylake auth
(ARRAYLAKE_TOKEN or `arraylake auth login`).
"""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import pandas as pd
import xarray as xr

from config import IFS_OPEN_REPO
from sports import heat_index_celsius, kelvin_to_celsius, relative_humidity, wbgt_celsius

VARS = ["2t", "2d", "10u", "10v", "ssrd"]


@lru_cache(maxsize=1)
def open_ifs() -> xr.Dataset:
    from arraylake import Client

    token = os.environ.get("ARRAYLAKE_TOKEN")
    repo = Client(token=token).get_repo(IFS_OPEN_REPO)
    return xr.open_zarr(repo.readonly_session("main").store, chunks={})


_PROBE_LATLON = (48.85, 2.35)  # Paris — a land point that always carries 2t


def _latest_init_idx(ds: xr.Dataset) -> int:
    probe = ds["2t"].isel(step=0).sel(
        latitude=_PROBE_LATLON[0], longitude=_PROBE_LATLON[1], method="nearest"
    )
    for i in range(ds.sizes["time"] - 1, -1, -1):
        if np.isfinite(probe.isel(time=i).load().values):
            return i
    raise RuntimeError("no populated IFS init found")


def latest_forecast_init() -> pd.Timestamp:
    ds = open_ifs()
    return pd.Timestamp(ds["time"].values[_latest_init_idx(ds)])


def _deaccumulate_ssrd(ssrd_accumulated, steps_timedelta) -> np.ndarray:
    raw = np.asarray(ssrd_accumulated, dtype=float)
    dt_s = np.diff(steps_timedelta.astype("timedelta64[s]").astype(float), prepend=0.0)
    dt_s = np.where(dt_s > 0, dt_s, 3600.0)
    return np.clip(np.diff(raw, prepend=0.0) / dt_s, 0.0, None)


def _derive(t2m_k, d2m_k, u10=None, v10=None, ssrd_wm2=None) -> pd.DataFrame:
    t2m_c = kelvin_to_celsius(t2m_k)
    d2m_c = kelvin_to_celsius(d2m_k)
    rh = relative_humidity(t2m_c, d2m_c)
    out = pd.DataFrame(
        {
            "t2m_c": t2m_c,
            "d2m_c": d2m_c,
            "heat_index_c": heat_index_celsius(t2m_c, rh),
        }
    )
    if u10 is not None and v10 is not None:
        wind_ms = np.sqrt(np.asarray(u10, float) ** 2 + np.asarray(v10, float) ** 2)
        out["wind_ms"] = wind_ms
        out["wbgt_c"] = wbgt_celsius(t2m_c, rh, wind_ms, ssrd_wm2)
    return out


def _assemble(a2t, a2d, a_time, f2t, f2d, f_valid, init,
              a_u10=None, a_v10=None, f_u10=None, f_v10=None,
              f_ssrd=None, f_steps=None) -> pd.DataFrame:
    f_ssrd_wm2 = None
    if f_ssrd is not None and f_steps is not None:
        f_ssrd_wm2 = _deaccumulate_ssrd(f_ssrd, f_steps)
    a = _derive(a2t, a2d, a_u10, a_v10, None)
    a.index = pd.DatetimeIndex(a_time, name="valid_time")
    f = _derive(f2t, f2d, f_u10, f_v10, f_ssrd_wm2)
    f.index = pd.DatetimeIndex(f_valid, name="valid_time")
    f = f[f["t2m_c"].notna()]
    joined = pd.concat([a[a.index < init], f]).sort_index()
    out = joined[~joined.index.duplicated(keep="last")].resample("1h").interpolate("time")
    out["is_forecast"] = out.index >= init
    return out


def extract_points(latlons: list[tuple[float, float]]) -> list[pd.DataFrame]:
    """Bulk nearest-point extraction, aligned to `latlons` order.

    Two `.load()` calls total (analysis + forecast); xarray fetches each Zarr
    chunk once and reuses it for every point in it, so cost scales with distinct
    chunks touched, not point count.
    """
    ds = open_ifs()
    lat = xr.DataArray([la for la, _ in latlons], dims="pt")
    lon = xr.DataArray([lo for _, lo in latlons], dims="pt")
    sel = ds[VARS].sel(latitude=lat, longitude=lon, method="nearest")
    init_idx = _latest_init_idx(ds)
    init = pd.Timestamp(ds["time"].values[init_idx])
    analysis = sel.sel(step="0 days").load()
    fc = sel.isel(time=init_idx).load()
    a_time = analysis["time"].values
    f_valid = fc["time"].values + fc["step"].values
    f_steps = fc["step"].values
    return [
        _assemble(
            analysis["2t"].isel(pt=i).values, analysis["2d"].isel(pt=i).values, a_time,
            fc["2t"].isel(pt=i).values, fc["2d"].isel(pt=i).values, f_valid, init,
            a_u10=analysis["10u"].isel(pt=i).values, a_v10=analysis["10v"].isel(pt=i).values,
            f_u10=fc["10u"].isel(pt=i).values, f_v10=fc["10v"].isel(pt=i).values,
            f_ssrd=fc["ssrd"].isel(pt=i).values, f_steps=f_steps,
        )
        for i in range(len(latlons))
    ]
''')

_f("backend/recompute.py", r'''"""Build the static JSON contract the frontend reads.

    cycles/latest.json   cycle metadata + index of available dates
    days/{date}.json     pins for that day (one entry per occasion)
    events/{id}.json     full per-occasion timeseries + compare stats

    --source demo   plausible synthetic forecast (no auth, default, deterministic)
    --source ifs    real ECMWF IFS extraction (needs the `ifs` extra + Arraylake auth)
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

from config import DATA_DIR, OUT_DIR
from model import Occasion, Place, load
from sports import heat_index_celsius, relative_humidity, wbgt_celsius

log = logging.getLogger("recompute")

# Canonical variable set carried in every series (key -> chart metadata).
VARIABLES = {
    "t2m":        {"label": "Temperature", "unit": "°C",  "color": "#f97316"},
    "d2m":        {"label": "Dewpoint",    "unit": "°C",  "color": "#22d3ee"},
    "heat_index": {"label": "Feels like",  "unit": "°C",  "color": "#ef4444"},
    "wbgt":       {"label": "WBGT",        "unit": "°C",  "color": "#f43f5e"},
    "wind_speed": {"label": "Wind",        "unit": "m/s", "color": "#94a3b8"},
}

WINDOW_BEFORE = pd.Timedelta(days=1)
WINDOW_AFTER = pd.Timedelta(days=5)


def utc_offset_hours(lon: float) -> int:
    return int(round(lon / 15.0))


# --- synthetic forecast model (demo) ----------------------------------------

def synth_series(place: Place, times: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    lat, lon = place.lat, place.lon
    hours = times.view("int64") / 3.6e12
    local_h = (np.array([t.hour + t.minute / 60 for t in times]) + lon / 15.0) % 24
    micro = 1.5 * math.sin(math.radians(lat) * 4) * math.cos(math.radians(lon) * 3)
    t_mean = float(np.clip(26 - 0.008 * (lat - 18) ** 2 + micro, -8, 38))
    dryness = float(np.clip(0.3 + abs(lat) / 120 + 0.15 * math.sin(math.radians(lon) * 2), 0.05, 0.95))
    diurnal_amp = 4 + 7 * dryness
    synoptic = 3.5 * np.sin(2 * np.pi * (hours - hours[0]) / 84 + math.radians(lon) * 1.5 + math.radians(lat))
    diurnal = diurnal_amp * np.cos(2 * np.pi * (local_h - 15) / 24)
    t2m = t_mean + diurnal + synoptic
    spread = (3 + 12 * dryness) * (0.6 + 0.4 * np.clip((local_h - 6) / 12, 0, 1))
    d2m = np.minimum(t2m - spread, t2m - 0.5)
    wind_ms = np.clip(
        3.5 + 1.5 * (1.0 - dryness)
        + 2.0 * np.cos(2 * np.pi * (local_h - 14) / 24)
        + 1.0 * np.sin(2 * np.pi * (hours - hours[0]) / 72 + math.radians(lat)),
        0.3, 14.0,
    )
    day_frac = (local_h - 6) / 12
    solar = np.where((day_frac >= 0) & (day_frac <= 1), np.sin(np.pi * day_frac), 0.0)
    ssrd_wm2 = 800.0 * (0.7 + 0.3 * dryness) * solar
    rh = relative_humidity(t2m, d2m)
    return {
        "t2m": t2m,
        "d2m": d2m,
        "heat_index": np.asarray(heat_index_celsius(t2m, rh), dtype=float),
        "wbgt": np.asarray(wbgt_celsius(t2m, rh, wind_ms, ssrd_wm2), dtype=float),
        "wind_speed": wind_ms,
    }


# --- ifs source -------------------------------------------------------------

_IFS_COL = {"t2m": "t2m_c", "d2m": "d2m_c", "heat_index": "heat_index_c",
            "wbgt": "wbgt_c", "wind_speed": "wind_ms"}


def make_ifs_series_fn(occ: list[Occasion]):
    from weather_ifs import extract_points

    def pkey(p: Place):
        return (round(p.lat, 4), round(p.lon, 4))

    uniq: dict[tuple[float, float], tuple[float, float]] = {}
    for o in occ:
        for p in (o.location, *o.compare):
            uniq[pkey(p)] = (p.lat, p.lon)
    keys = list(uniq)
    log.info("extracting %d unique points in one bulk read...", len(keys))
    dfs = dict(zip(keys, extract_points([uniq[k] for k in keys])))

    def series_fn(place: Place, times: pd.DatetimeIndex) -> dict[str, np.ndarray]:
        df = dfs[pkey(place)]
        rx = (df.select_dtypes(include="number").reindex(times)
              .interpolate("time", limit_area="inside"))
        n = len(times)
        return {
            vk: (rx[col].to_numpy() if col in rx.columns else np.full(n, np.nan))
            for vk, col in _IFS_COL.items()
        }

    return series_fn


# --- assembly ---------------------------------------------------------------

def round_series(a: np.ndarray, nd: int = 1) -> list[float | None]:
    return [None if math.isnan(float(x)) else round(float(x), nd) for x in a]


def _safe_round(x: float, nd: int = 1) -> float | None:
    return None if math.isnan(x) else round(x, nd)


def window_mean(times, vals, start) -> float:
    mask = (times >= start) & (times <= start + pd.Timedelta(hours=2))
    sel = vals[mask]
    valid = sel[~np.isnan(sel)] if len(sel) else np.array([])
    if len(valid):
        return float(np.mean(valid))
    fallback = vals[~np.isnan(vals)]
    return float(np.mean(fallback)) if len(fallback) else float("nan")


def build_event(o: Occasion, series_fn) -> dict:
    md = pd.Timestamp(o.date)
    times = pd.date_range(md - WINDOW_BEFORE, md + WINDOW_AFTER, freq="1h")
    start = pd.Timestamp(o.start_utc).tz_convert(None)
    sl = series_fn(o.location, times)
    v_off = utc_offset_hours(o.location.lon)
    start_local = (start + pd.Timedelta(hours=v_off)).strftime("%Y-%m-%d %H:%M")

    series: dict = {
        "time": [t.isoformat() + "Z" for t in times],
        "location": {k: round_series(sl[k]) for k in VARIABLES},
        "compare": [],
    }
    stats: list[dict] = []
    for c in o.compare:
        sc = series_fn(c, times)
        series["compare"].append(
            {"key": c.key, "name": c.name, "role": c.role,
             "vars": {k: round_series(sc[k]) for k in VARIABLES}}
        )
        deltas = {k: _safe_round(window_mean(times, sl[k], start) - window_mean(times, sc[k], start))
                  for k in VARIABLES}
        stats.append({"key": c.key, "name": c.name, "role": c.role, "country": c.country,
                      "tz_diff_h": utc_offset_hours(c.lon) - v_off, "deltas": deltas})

    return {
        "id": o.id, "date": o.date, "title": o.title, "subtitle": o.subtitle,
        "start_utc": o.start_utc, "start_local": start_local,
        "location": {"key": o.location.key, "name": o.location.name,
                     "sublabel": o.location.sublabel, "country": o.location.country,
                     "lat": o.location.lat, "lon": o.location.lon, "role": o.location.role},
        "t2m_at_start": _safe_round(window_mean(times, sl["t2m"], start)),
        "heat_index_at_start": _safe_round(window_mean(times, sl["heat_index"], start)),
        "window": {"start": times[0].isoformat() + "Z", "end": times[-1].isoformat() + "Z"},
        "series": series, "stats": stats,
    }


def pin(doc: dict) -> dict:
    return {k: doc[k] for k in (
        "id", "date", "title", "subtitle", "start_utc", "start_local",
        "location", "t2m_at_start", "heat_index_at_start")}


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["demo", "ifs"], default="demo")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    events, occ = load(DATA_DIR)
    cycle_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if args.source == "ifs":
        from weather_ifs import latest_forecast_init
        cycle_time = latest_forecast_init().tz_localize("UTC").to_pydatetime()
        series_fn = make_ifs_series_fn(occ)
    else:
        series_fn = synth_series

    log.info("building %d occasions from source=%s -> %s", len(occ), args.source, args.out)
    t0 = time.perf_counter()
    by_date: dict[str, list[dict]] = {}
    for o in occ:
        doc = build_event(o, series_fn)
        write_json(args.out / "events" / f"{doc['id']}.json", doc)
        by_date.setdefault(o.date, []).append(pin(doc))

    for date, pins in by_date.items():
        write_json(args.out / "days" / f"{date}.json", {"date": date, "events": pins})

    write_json(args.out / "cycles" / "latest.json", {
        "cycle": cycle_time.isoformat(),
        "source": args.source,
        "event": events.get("event", ""),
        "sport": events.get("sport", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dates": sorted(by_date),
        "variables": VARIABLES,
    })
    log.info("wrote %d occasions across %d dates in %.1fs",
             len(occ), len(by_date), time.perf_counter() - t0)


if __name__ == "__main__":
    main()
''')

_f("backend/test_recompute.py", r'''"""Runnable self-checks for the demo build (no auth). `python backend/test_recompute.py`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from config import DATA_DIR
from model import load
from recompute import VARIABLES, build_event, pin, synth_series


def main() -> int:
    _, occ = load(DATA_DIR)
    assert occ, "no occasions in data/events.json"
    doc = build_event(occ[0], synth_series)

    # JSON round-trips (no bare NaN, which is invalid JSON).
    txt = json.dumps(doc)
    assert "NaN" not in txt, "doc contains a bare NaN"

    # Series line up with the time axis.
    n = len(doc["series"]["time"])
    for k in VARIABLES:
        assert len(doc["series"]["location"][k]) == n, f"{k} length mismatch"

    # Pin carries the map essentials.
    p = pin(doc)
    for key in ("id", "title", "location", "t2m_at_start"):
        assert key in p, f"pin missing {key}"
    assert "lat" in p["location"] and "lon" in p["location"]

    # One compare entry produces one stat entry.
    assert len(doc["series"]["compare"]) == len(doc["stats"])

    # Synthetic series has no gaps on the hourly grid.
    times = pd.date_range(pd.Timestamp(occ[0].date) - pd.Timedelta(days=1),
                          pd.Timestamp(occ[0].date) + pd.Timedelta(days=5), freq="1h")
    s = synth_series(occ[0].location, times)
    assert not any(pd.isna(v).any() for v in s.values()), "synthetic series has NaN"

    print(f"ok: {len(occ)} occasions, {n} timesteps, {len(doc['stats'])} compares")
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')

# ---- frontend -------------------------------------------------------------- #

_f("frontend/package.json", r'''{
  "name": "__APP_SLUG__-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "maplibre-gl": "^4.7.1",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.13.0"
  },
  "devDependencies": {
    "@types/geojson": "^7946.0.14",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }
}
''')

_f("frontend/tsconfig.json", r'''{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "types": ["geojson", "vite/client"]
  },
  "include": ["src"]
}
''')

_f("frontend/src/vite-env.d.ts", r'''/// <reference types="vite/client" />
''')

_f("frontend/vite.config.ts", r'''import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "__BASE_PATH__",
  plugins: [react()],
});
''')

_f("frontend/index.html", r'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>__APP_TITLE__</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''')

_f("frontend/src/main.tsx", r'''import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "maplibre-gl/dist/maplibre-gl.css";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
''')

_f("frontend/src/types.ts", r'''// Shared data contract — mirrors backend/recompute.py output.

export interface VarMeta { label: string; unit: string; color: string; }

export interface Cycle {
  cycle: string;
  source: string;
  event: string;
  sport: string;
  generated_at: string;
  dates: string[];
  variables: Record<string, VarMeta>;
}

export interface PinLocation {
  key: string;
  name: string;
  sublabel?: string;
  country: string;
  lat: number;
  lon: number;
  role: string;
}

export interface Pin {
  id: string;
  date: string;
  title: string;
  subtitle: string;
  start_utc: string;
  start_local: string;
  location: PinLocation;
  // null when the occasion is beyond the forecast horizon (no data yet).
  t2m_at_start: number | null;
  heat_index_at_start: number | null;
}

export interface Day { date: string; events: Pin[]; }

export type SeriesVars = Record<string, (number | null)[]>;

export interface CompareSeries { key: string; name: string; role: string; vars: SeriesVars; }

export interface CompareStat {
  key: string;
  name: string;
  role: string;
  country: string;
  tz_diff_h: number;
  deltas: Record<string, number | null>;
}

export interface EventDoc extends Pin {
  window: { start: string; end: string };
  series: { time: string[]; location: SeriesVars; compare: CompareSeries[] };
  stats: CompareStat[];
}
''')

_f("frontend/src/data.ts", r'''import type { Cycle, Day, EventDoc } from "./types";

const base = `${import.meta.env.BASE_URL}data`;

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${base}/${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

export const loadCycle = () => get<Cycle>("cycles/latest.json");
export const loadDay = (date: string) => get<Day>(`days/${date}.json`);
export const loadEvent = (id: string) => get<EventDoc>(`events/${id}.json`);
''')

_f("frontend/src/colors.ts", r'''type RGB = [number, number, number];

// Perceptual cold-to-hot ramp (RdYlBu-ish), keyed on degC.
const STOPS: [number, RGB][] = [
  [-10, [49, 54, 149]],
  [0, [69, 117, 180]],
  [8, [116, 173, 209]],
  [16, [171, 217, 233]],
  [20, [224, 243, 248]],
  [24, [254, 224, 144]],
  [28, [253, 174, 97]],
  [32, [244, 109, 67]],
  [38, [215, 48, 39]],
  [45, [165, 0, 38]],
];

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const css = (c: RGB) => `rgb(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])})`;

export function tempColor(c: number | null | undefined): string {
  if (c == null || Number.isNaN(c)) return "#8b95a3";
  if (c <= STOPS[0][0]) return css(STOPS[0][1]);
  const last = STOPS[STOPS.length - 1];
  if (c >= last[0]) return css(last[1]);
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [x0, c0] = STOPS[i];
    const [x1, c1] = STOPS[i + 1];
    if (c >= x0 && c <= x1) {
      const t = (c - x0) / (x1 - x0);
      return css([lerp(c0[0], c1[0], t), lerp(c0[1], c1[1], t), lerp(c0[2], c1[2], t)]);
    }
  }
  return css(last[1]);
}
''')

_f("frontend/src/MapView.tsx", r'''import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Pin } from "./types";
import { tempColor } from "./colors";

const STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

function fc(pins: Pin[], selectedId: string | null): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: pins.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.location.lon, p.location.lat] },
      properties: {
        id: p.id,
        color: tempColor(p.t2m_at_start),
        selected: p.id === selectedId,
      },
    })),
  };
}

export default function MapView({
  pins,
  selectedId,
  onSelect,
}: {
  pins: Pin[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);

  useEffect(() => {
    if (!container.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: STYLE,
      center: [-30, 25],
      zoom: 1.3,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      m.addSource("pins", { type: "geojson", data: fc([], null) });
      m.addLayer({
        id: "pins-halo",
        type: "circle",
        source: "pins",
        filter: ["==", ["get", "selected"], true],
        paint: { "circle-radius": 14, "circle-color": "#ffffff", "circle-opacity": 0.85 },
      });
      m.addLayer({
        id: "pins",
        type: "circle",
        source: "pins",
        paint: {
          "circle-radius": 8,
          "circle-color": ["get", "color"],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#0b1020",
        },
      });
      m.on("click", "pins", (e) => {
        const f = e.features?.[0];
        if (f?.properties) onSelect(f.properties.id as string);
      });
      m.on("mouseenter", "pins", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "pins", () => (m.getCanvas().style.cursor = ""));
      ready.current = true;
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      ready.current = false;
    };
  }, [onSelect]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready.current) return;
    const src = m.getSource("pins") as maplibregl.GeoJSONSource | undefined;
    src?.setData(fc(pins, selectedId));
    if (pins.length) {
      const b = new maplibregl.LngLatBounds();
      pins.forEach((p) => b.extend([p.location.lon, p.location.lat]));
      m.fitBounds(b, { padding: 90, maxZoom: 6, duration: 600 });
    }
  }, [pins, selectedId]);

  return <div ref={container} className="map" />;
}
''')

_f("frontend/src/Chart.tsx", r'''import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EventDoc, VarMeta } from "./types";

const PALETTE = ["#38bdf8", "#f472b6", "#a3e635", "#fbbf24"];

const fmt = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });

export default function Chart({
  ev,
  varKey,
  meta,
}: {
  ev: EventDoc;
  varKey: string;
  meta: VarMeta;
}) {
  const rows = ev.series.time.map((iso, i) => {
    const row: Record<string, number | string | null> = { label: fmt(iso) };
    row.location = ev.series.location[varKey]?.[i] ?? null;
    ev.series.compare.forEach((c) => {
      row[c.key] = c.vars[varKey]?.[i] ?? null;
    });
    return row;
  });

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#8b95a3" }} minTickGap={44} />
          <YAxis tick={{ fontSize: 10, fill: "#8b95a3" }} width={40} unit={meta.unit} />
          <Tooltip
            contentStyle={{
              background: "#0b1020",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#c7d0dc" }}
          />
          <ReferenceLine x={fmt(ev.start_utc)} stroke="#e2e8f0" strokeDasharray="3 3" />
          <Line
            type="monotone"
            dataKey="location"
            name={ev.location.name}
            stroke={meta.color}
            dot={false}
            strokeWidth={2.4}
            connectNulls
          />
          {ev.series.compare.map((c, i) => (
            <Line
              key={c.key}
              type="monotone"
              dataKey={c.key}
              name={c.name}
              stroke={PALETTE[i % PALETTE.length]}
              dot={false}
              strokeWidth={1.6}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
''')

_f("frontend/src/EventCard.tsx", r'''import { useState } from "react";
import type { Cycle, EventDoc } from "./types";
import Chart from "./Chart";
import { tempColor } from "./colors";

function Tile({
  label,
  value,
  unit,
  color,
  signed,
}: {
  label: string;
  value: number | null;
  unit: string;
  color: string;
  signed?: boolean;
}) {
  const txt =
    value == null ? "—" : `${signed && value > 0 ? "+" : ""}${value.toFixed(1)}${unit}`;
  return (
    <div className="tile">
      <div className="tile-v" style={{ color }}>
        {txt}
      </div>
      <div className="tile-l">{label}</div>
    </div>
  );
}

export default function EventCard({
  ev,
  cycle,
  onClose,
}: {
  ev: EventDoc;
  cycle: Cycle;
  onClose: () => void;
}) {
  const varKeys = Object.keys(cycle.variables);
  const [varKey, setVarKey] = useState(
    varKeys.includes("heat_index") ? "heat_index" : varKeys[0],
  );
  const meta = cycle.variables[varKey];

  return (
    <div className="card">
      <button className="close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="card-head">
        <h2>{ev.title}</h2>
        <div className="sub">
          {ev.subtitle} · {ev.location.name}
          {ev.location.sublabel ? ` (${ev.location.sublabel})` : ""}
        </div>
        <div className="sub">Local start {ev.start_local}</div>
      </div>

      <div className="tiles">
        <Tile label="Temp at start" value={ev.t2m_at_start} unit="°C" color={tempColor(ev.t2m_at_start)} />
        <Tile label="Feels like" value={ev.heat_index_at_start} unit="°C" color={tempColor(ev.heat_index_at_start)} />
        {ev.stats.map((s) => (
          <Tile key={s.key} label={`Δ vs ${s.name}`} value={s.deltas.t2m ?? null} unit="°C" color="#c7d0dc" signed />
        ))}
      </div>

      <div className="var-row">
        {varKeys.map((k) => (
          <button
            key={k}
            className={k === varKey ? "chip on" : "chip"}
            onClick={() => setVarKey(k)}
          >
            {cycle.variables[k].label}
          </button>
        ))}
      </div>

      <Chart ev={ev} varKey={varKey} meta={meta} />
    </div>
  );
}
''')

_f("frontend/src/App.tsx", r'''import { useEffect, useState } from "react";
import type { Cycle, Day, EventDoc, Pin } from "./types";
import { loadCycle, loadDay, loadEvent } from "./data";
import { tempColor } from "./colors";
import MapView from "./MapView";
import EventCard from "./EventCard";

const fmtDate = (d: string) =>
  new Date(d + "T00:00:00Z").toLocaleDateString(undefined, { month: "short", day: "numeric" });

function ListPanel({ pins, onSelect }: { pins: Pin[]; onSelect: (id: string) => void }) {
  if (!pins.length) return <div className="empty">No events on this day.</div>;
  return (
    <div className="list">
      {pins.map((p) => (
        <button key={p.id} className="list-row" onClick={() => onSelect(p.id)}>
          <span className="dot" style={{ background: tempColor(p.t2m_at_start) }} />
          <span className="lr-main">
            <b>{p.title}</b>
            <span className="lr-sub">
              {p.subtitle} · {p.location.name}
            </span>
          </span>
          <span className="lr-temp">
            {p.t2m_at_start == null ? "—" : `${p.t2m_at_start.toFixed(0)}°`}
          </span>
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [day, setDay] = useState<Day | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [ev, setEv] = useState<EventDoc | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    loadCycle()
      .then((c) => {
        setCycle(c);
        const today = new Date().toISOString().slice(0, 10);
        setDate(c.dates.find((x) => x >= today) ?? c.dates[0] ?? null);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    if (!date) return;
    setSelected(null);
    loadDay(date).then(setDay).catch((e) => setErr(String(e)));
  }, [date]);

  useEffect(() => {
    if (!selected) {
      setEv(null);
      return;
    }
    loadEvent(selected).then(setEv).catch((e) => setErr(String(e)));
  }, [selected]);

  const pins = day?.events ?? [];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">__APP_TITLE__</div>
        <div className="dates">
          {cycle?.dates.map((d) => (
            <button
              key={d}
              className={d === date ? "date on" : "date"}
              onClick={() => setDate(d)}
            >
              {fmtDate(d)}
            </button>
          ))}
        </div>
      </header>

      <div className="stage">
        <MapView pins={pins} selectedId={selected} onSelect={setSelected} />
        <aside className={ev ? "panel open" : "panel"}>
          {ev && cycle ? (
            <EventCard ev={ev} cycle={cycle} onClose={() => setSelected(null)} />
          ) : (
            <ListPanel pins={pins} onSelect={setSelected} />
          )}
        </aside>
      </div>

      {err && <div className="err">{err}</div>}
      {cycle && (
        <div className="foot">
          {cycle.event ? `${cycle.event} · ` : ""}source: {cycle.source} · cycle{" "}
          {new Date(cycle.cycle).toISOString().slice(0, 13)}Z
        </div>
      )}
    </div>
  );
}
''')

_f("frontend/src/index.css", r''':root {
  --bg: #0b1020;
  --panel: rgba(20, 27, 45, 0.72);
  --line: rgba(255, 255, 255, 0.12);
  --text: #e6ebf2;
  --muted: #8b95a3;
  color-scheme: dark;
}

* { box-sizing: border-box; }

html, body, #root { height: 100%; margin: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font: 14px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.app { display: flex; flex-direction: column; height: 100%; }

.topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(11, 16, 32, 0.9);
  z-index: 2;
}

.brand { font-weight: 700; font-size: 15px; white-space: nowrap; }

.dates { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: thin; }

.date {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.date.on { background: #2563eb; border-color: #2563eb; color: #fff; }

.stage { position: relative; flex: 1; min-height: 0; }

.map { position: absolute; inset: 0; }

.panel {
  position: absolute;
  top: 12px;
  right: 12px;
  bottom: 12px;
  width: min(390px, calc(100% - 24px));
  background: var(--panel);
  backdrop-filter: blur(14px);
  border: 1px solid var(--line);
  border-radius: 16px;
  overflow-y: auto;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
}

.list { padding: 8px; }
.list-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  border-radius: 10px;
  padding: 10px;
  color: var(--text);
  cursor: pointer;
}
.list-row:hover { background: rgba(255, 255, 255, 0.06); }
.dot { width: 12px; height: 12px; border-radius: 50%; flex: none; }
.lr-main { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.lr-sub { color: var(--muted); font-size: 12px; }
.lr-temp { font-variant-numeric: tabular-nums; color: var(--muted); }
.empty { padding: 24px; color: var(--muted); text-align: center; }

.card { padding: 16px; position: relative; }
.close {
  position: absolute;
  top: 10px;
  right: 12px;
  background: transparent;
  border: none;
  color: var(--muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}
.card-head h2 { margin: 0 26px 4px 0; font-size: 18px; }
.sub { color: var(--muted); font-size: 12px; }

.tiles {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin: 14px 0;
}
.tile {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
}
.tile-v { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tile-l { color: var(--muted); font-size: 11px; margin-top: 2px; }

.var-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chip {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  cursor: pointer;
}
.chip.on { background: rgba(255, 255, 255, 0.14); color: var(--text); }

.chart { margin: 0 -6px; }

.err {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: #7f1d1d;
  color: #fee;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  z-index: 3;
}
.foot {
  padding: 6px 16px;
  font-size: 11px;
  color: var(--muted);
  border-top: 1px solid var(--line);
  background: rgba(11, 16, 32, 0.9);
}

@media (max-width: 640px) {
  .panel { top: auto; height: 55%; width: calc(100% - 24px); }
}
''')

# ---- project root ---------------------------------------------------------- #

_f("pyproject.toml", r'''[project]
name = "__APP_SLUG__"
version = "0.1.0"
description = "Weather forecast at the locations of a sports event."
requires-python = ">=3.11"
dependencies = ["numpy", "pandas"]

[project.optional-dependencies]
# Real ECMWF IFS source (`recompute.py --source ifs`). Needs Arraylake auth.
ifs = ["xarray", "arraylake", "xclim", "icechunk", "zarr"]

[tool.setuptools]
py-modules = []
''')

_f(".gitignore", r'''# python
__pycache__/
*.pyc
.venv/
.cache/
# node / build
node_modules/
frontend/dist/
# generated data contract (rebuilt by backend/recompute.py)
frontend/public/data/
''')

_f("README.md", r'''# __APP_TITLE__

Weather forecast at the locations of a sports event, on a date-pickable map, one
temperature-colored pin per event. Click a pin for per-variable forecast charts
comparing the venue with the "compare" locations. Static SPA (React + MapLibre),
deployed to GitHub Pages. Scaffolded with the `sports-weather-app` skill.

## Data (edit these two files for your event)

- `data/events.json` — the schedule (`occasions`: date, start time, title,
  `location`, `compare`).
- `data/locations.json` — every referenced key → `{name, lat, lon, role, country}`.

An *occasion* has one primary `location` (the map pin) and 0..N `compare`
locations drawn against it on the chart. Football: location = venue, compare =
team home cities. Cycling: location = stage finish, compare = [stage start].

## Build and preview

```bash
uv run python backend/recompute.py --source demo   # writes frontend/public/data
uv run python backend/test_recompute.py            # self-checks
cd frontend && npm install && npm run dev          # http://localhost:5173
```

The default **demo** source is a physically plausible synthetic forecast (no
auth), so the app runs immediately. Swap in real ECMWF IFS data:

```bash
uv sync --extra ifs
export ARRAYLAKE_TOKEN=ema_...     # or: uv run arraylake auth login
uv run python backend/recompute.py --source ifs
```

## Deploy (GitHub Pages)

Push to `main`; `.github/workflows/pages.yml` builds the demo data + frontend
and deploys. In the repo settings, set **Pages → Source → GitHub Actions**. The
Vite `base` is set to `__BASE_PATH__` for the project page. To deploy real data,
add an `ARRAYLAKE_TOKEN` secret and switch the workflow's recompute step to
`--source ifs`.
''')

_f(".github/workflows/pages.yml", r'''name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:
  schedule:
    # Rebuild twice daily to pick up a fresh forecast (demo re-renders "today").
    - cron: "30 7,19 * * *"

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      # Default demo source needs no secrets, so the page works out of the box.
      # For live data: `uv sync --extra ifs`, add an ARRAYLAKE_TOKEN secret, and
      # change this to `--source ifs`.
      - name: Generate data contract
        run: uv run python backend/recompute.py --source demo

      - uses: actions/setup-node@v6
        with:
          node-version: 20

      - name: Build frontend
        working-directory: frontend
        run: |
          npm install
          npm run build

      - uses: actions/upload-pages-artifact@v5
        with:
          path: frontend/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - id: deploy
        uses: actions/deploy-pages@v5
''')


# --------------------------------------------------------------------------- #
# Seed data presets (agent edits these for the real event).
# --------------------------------------------------------------------------- #

def preset_football() -> tuple[dict, dict]:
    locations = {
        "mercedes_benz": {"name": "Mercedes-Benz Stadium", "sublabel": "Atlanta",
                          "country": "United States", "lat": 33.755, "lon": -84.401, "role": "venue"},
        "metlife": {"name": "MetLife Stadium", "sublabel": "New York/New Jersey",
                    "country": "United States", "lat": 40.813, "lon": -74.074, "role": "venue"},
        "estadio_azteca": {"name": "Estadio Azteca", "sublabel": "Mexico City",
                           "country": "Mexico", "lat": 19.303, "lon": -99.150, "role": "venue"},
        "Spain": {"name": "Madrid", "country": "Spain", "lat": 40.417, "lon": -3.703, "role": "home"},
        "Cape Verde": {"name": "Praia", "country": "Cape Verde", "lat": 14.917, "lon": -23.508, "role": "home"},
        "Mexico": {"name": "Mexico City", "country": "Mexico", "lat": 19.433, "lon": -99.133, "role": "home"},
        "USA": {"name": "Washington", "country": "United States", "lat": 38.895, "lon": -77.036, "role": "home"},
        "Brazil": {"name": "Brasilia", "country": "Brazil", "lat": -15.793, "lon": -47.882, "role": "home"},
        "Argentina": {"name": "Buenos Aires", "country": "Argentina", "lat": -34.607, "lon": -58.437, "role": "home"},
    }
    events = {
        "event": "FIFA World Cup 2026 (seed)",
        "sport": "football",
        "note": "Seed data — replace with the real fixture list and venues.",
        "occasions": [
            {"date": "2026-06-15", "start_utc": "2026-06-15T16:00:00Z", "title": "Spain vs Cape Verde",
             "subtitle": "Group H", "location": "mercedes_benz", "compare": ["Spain", "Cape Verde"]},
            {"date": "2026-06-16", "start_utc": "2026-06-16T19:00:00Z", "title": "Mexico vs USA",
             "subtitle": "Group A", "location": "estadio_azteca", "compare": ["Mexico", "USA"]},
            {"date": "2026-06-17", "start_utc": "2026-06-17T23:00:00Z", "title": "Brazil vs Argentina",
             "subtitle": "Group C", "location": "metlife", "compare": ["Brazil", "Argentina"]},
        ],
    }
    return events, locations


def preset_cycling() -> tuple[dict, dict]:
    locations = {
        "s1_start": {"name": "Barcelona (start)", "country": "Spain", "lat": 41.390, "lon": 2.170, "role": "start"},
        "s1_finish": {"name": "Barcelona (finish)", "country": "Spain", "lat": 41.365, "lon": 2.152, "role": "finish"},
        "s7_start": {"name": "Bordeaux", "country": "France", "lat": 44.838, "lon": -0.579, "role": "start"},
        "s7_finish": {"name": "Pau", "country": "France", "lat": 43.300, "lon": -0.370, "role": "finish"},
        "s12_start": {"name": "Bourg-d'Oisans", "country": "France", "lat": 45.055, "lon": 6.031, "role": "start"},
        "s12_finish": {"name": "Alpe d'Huez", "country": "France", "lat": 45.092, "lon": 6.070, "role": "finish"},
    }
    events = {
        "event": "Tour de France 2026 (seed)",
        "sport": "cycling",
        "note": "Seed data — replace with the real stage list, dates and towns.",
        "occasions": [
            {"date": "2026-07-04", "start_utc": "2026-07-04T11:00:00Z", "title": "Stage 1: Barcelona → Barcelona",
             "subtitle": "Flat", "location": "s1_finish", "compare": ["s1_start"]},
            {"date": "2026-07-10", "start_utc": "2026-07-10T11:30:00Z", "title": "Stage 7: Bordeaux → Pau",
             "subtitle": "Hilly", "location": "s7_finish", "compare": ["s7_start"]},
            {"date": "2026-07-16", "start_utc": "2026-07-16T10:30:00Z", "title": "Stage 12: Bourg-d'Oisans → Alpe d'Huez",
             "subtitle": "Mountain", "location": "s12_finish", "compare": ["s12_start"]},
        ],
    }
    return events, locations


def preset_generic() -> tuple[dict, dict]:
    locations = {
        "loc_a": {"name": "Location A", "country": "", "lat": 51.507, "lon": -0.128, "role": "venue"},
        "loc_b": {"name": "Location B", "country": "", "lat": 48.857, "lon": 2.352, "role": "venue"},
    }
    events = {
        "event": "My Sports Event (seed)",
        "sport": "generic",
        "note": "Seed data — replace with your event.",
        "occasions": [
            {"date": "2026-06-15", "start_utc": "2026-06-15T14:00:00Z", "title": "Event One",
             "subtitle": "Round 1", "location": "loc_a", "compare": []},
            {"date": "2026-06-16", "start_utc": "2026-06-16T14:00:00Z", "title": "Event Two",
             "subtitle": "Round 1", "location": "loc_b", "compare": []},
        ],
    }
    return events, locations


PRESETS = {"football": preset_football, "cycling": preset_cycling, "generic": preset_generic}


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="target project directory")
    ap.add_argument("--slug", required=True, help="npm/package slug, e.g. tour-de-france-weather")
    ap.add_argument("--title", required=True, help="human title shown in the UI")
    ap.add_argument("--repo", required=True, help="owner/name — drives the GitHub Pages base path")
    ap.add_argument("--sport", choices=list(PRESETS), default="generic")
    ap.add_argument("--force", action="store_true", help="write even if --out is non-empty")
    args = ap.parse_args()

    out = args.out.resolve()
    if out.exists() and any(out.iterdir()) and not args.force:
        raise SystemExit(f"{out} is not empty (pass --force to write anyway)")

    repo_name = args.repo.split("/")[-1]
    base_path = f"/{repo_name}/"
    tokens = {
        "__APP_TITLE__": args.title,
        "__APP_SLUG__": args.slug,
        "__BASE_PATH__": base_path,
    }

    for rel, body in FILES.items():
        for k, v in tokens.items():
            body = body.replace(k, v)
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body)

    events, locations = PRESETS[args.sport]()
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "data" / "events.json").write_text(json.dumps(events, indent=2) + "\n")
    (out / "data" / "locations.json").write_text(json.dumps(locations, indent=2) + "\n")

    print(f"scaffolded {args.sport} app -> {out}")
    print(f"  base path: {base_path}  (GitHub Pages: https://{args.repo.split('/')[0]}.github.io{base_path})")
    print("next:")
    print(f"  cd {out}")
    print("  uv run python backend/recompute.py --source demo")
    print("  uv run python backend/test_recompute.py")
    print("  cd frontend && npm install && npm run dev")


if __name__ == "__main__":
    main()
