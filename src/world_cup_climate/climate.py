"""Climate assembly: build the current-window series and the 10-year
climatology for a point, convert to display units, and produce the
match-level comparison report consumed by the API.

The comparison, per the brief, is three-way:

* **Venue, now** — the match venue's current 30-day window (ERA5 + forecast).
* **Capitals, now** — each competing nation's capital, current window.
* **Capitals, climatology** — each capital's same calendar window averaged over
  the previous ``CLIMATOLOGY_YEARS`` years (ERA5 only).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import config, fixtures
from . import providers as prov

KELVIN = 273.15


# --------------------------------------------------------------------------- #
# Units & derived variables
# --------------------------------------------------------------------------- #
def _saturation_vapour_pressure(temp_k: pd.Series) -> pd.Series:
    """Magnus formula, hPa, input in Kelvin."""
    tc = temp_k - KELVIN
    return 6.112 * np.exp(17.62 * tc / (243.12 + tc))


def relative_humidity(t2m_k: pd.Series, d2m_k: pd.Series) -> pd.Series:
    """Relative humidity (%) from 2 m temperature and dewpoint (both Kelvin)."""
    rh = 100.0 * _saturation_vapour_pressure(d2m_k) / _saturation_vapour_pressure(t2m_k)
    return rh.clip(0, 100)


def to_display_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert canonical (K, m, J/m²) to display units and add derived RH."""
    out = pd.DataFrame(index=df.index)
    if "t2m" in df:
        out["t2m"] = df["t2m"] - KELVIN          # K -> °C
    if "d2m" in df:
        out["d2m"] = df["d2m"] - KELVIN          # K -> °C
    if "tp" in df:
        out["tp"] = df["tp"] * 1000.0            # m -> mm
    if "ssrd" in df:
        out["ssrd"] = df["ssrd"] / 3.6e6         # J/m² -> kWh/m²
    if "t2m" in df and "d2m" in df:
        out["rh"] = relative_humidity(df["t2m"], df["d2m"])
    return out


# --------------------------------------------------------------------------- #
# Window helpers
# --------------------------------------------------------------------------- #
def window_bounds(matchday: dt.date, days: int = config.WINDOW_DAYS) -> tuple[dt.date, dt.date]:
    """The ``days``-long window ending on (and including) the matchday."""
    return matchday - dt.timedelta(days=days - 1), matchday


def _shift_year(day: dt.date, year: int) -> dt.date:
    try:
        return day.replace(year=year)
    except ValueError:  # 29 Feb in a non-leap year
        return day.replace(year=year, day=28)


# --------------------------------------------------------------------------- #
# Current-year series (ERA5 spliced with forecast across the latency gap)
# --------------------------------------------------------------------------- #
def current_series(lat: float, lon: float, matchday: dt.date) -> pd.DataFrame:
    """Daily series for the current window, ERA5 up to its cutoff then forecast.

    Returns display units with a ``source`` column ('era5' | 'forecast').
    """
    start, end = window_bounds(matchday)
    cutoff = prov.era5_cutoff(matchday)

    frames: list[pd.DataFrame] = []
    if start <= cutoff:
        era5 = prov.daily_point("era5", lat, lon, str(start), str(min(end, cutoff)))
        era5 = to_display_units(era5)
        era5["source"] = "era5"
        frames.append(era5)
    if end > cutoff:
        fc_start = max(start, cutoff + dt.timedelta(days=1))
        fc = prov.daily_point("forecast", lat, lon, str(fc_start), str(end))
        fc = to_display_units(fc)
        fc["source"] = "forecast"
        frames.append(fc)

    df = pd.concat(frames).sort_index()
    return df[~df.index.duplicated(keep="first")]


# --------------------------------------------------------------------------- #
# Historical climatology (ERA5, last N years, same calendar window)
# --------------------------------------------------------------------------- #
def climatology(
    lat: float, lon: float, matchday: dt.date, years: int = config.CLIMATOLOGY_YEARS
) -> pd.DataFrame:
    """Per day-offset climatology over the previous ``years`` years.

    Indexed by offset (-(WINDOW_DAYS-1) .. 0, where 0 == matchday). Columns are
    ``{var}_mean``, ``{var}_p10``, ``{var}_p90`` in display units.
    """
    per_year: list[pd.DataFrame] = []
    for year in range(matchday.year - years, matchday.year):
        md = _shift_year(matchday, year)
        start, end = window_bounds(md)
        raw = prov.daily_point("era5", lat, lon, str(start), str(end))
        disp = to_display_units(raw).reset_index(drop=True)
        # Align by offset from the window end (matchday == 0).
        disp.index = range(-(len(disp) - 1), 1)
        disp["year"] = year
        per_year.append(disp)

    panel = pd.concat(per_year)
    value_cols = [c for c in panel.columns if c != "year"]
    grouped = panel.groupby(panel.index)
    out = pd.DataFrame(index=sorted(panel.index.unique()))
    for col in value_cols:
        out[f"{col}_mean"] = grouped[col].mean()
        out[f"{col}_p10"] = grouped[col].quantile(0.10)
        out[f"{col}_p90"] = grouped[col].quantile(0.90)
    return out


# --------------------------------------------------------------------------- #
# Match-level report
# --------------------------------------------------------------------------- #
DISPLAY_VARS = ("t2m", "d2m", "rh", "tp", "ssrd")


def _series_payload(df: pd.DataFrame) -> dict:
    """JSON-able series payload: dates + per-variable arrays + source flags."""
    return {
        "dates": [d.date().isoformat() for d in df.index],
        "source": df["source"].tolist() if "source" in df else None,
        "values": {
            v: [None if pd.isna(x) else round(float(x), 3) for x in df[v]]
            for v in DISPLAY_VARS
            if v in df
        },
    }


def _matchday_summary(current: pd.DataFrame, clim: pd.DataFrame, matchday: dt.date) -> dict:
    """Headline numbers for the matchday itself (offset 0) per variable."""
    summary = {}
    md_ts = pd.Timestamp(matchday)
    cur_row = current.loc[md_ts] if md_ts in current.index else current.iloc[-1]
    for v in DISPLAY_VARS:
        if v not in current:
            continue
        entry = {"now": _round(cur_row.get(v))}
        if f"{v}_mean" in clim and 0 in clim.index:
            mean = clim.loc[0, f"{v}_mean"]
            entry["clim_mean"] = _round(mean)
            entry["clim_p10"] = _round(clim.loc[0, f"{v}_p10"])
            entry["clim_p90"] = _round(clim.loc[0, f"{v}_p90"])
            if pd.notna(cur_row.get(v)) and pd.notna(mean):
                entry["anomaly"] = _round(cur_row[v] - mean)
        summary[v] = entry
    return summary


def _round(x):
    return None if x is None or pd.isna(x) else round(float(x), 2)


def build_location_block(
    name: str, country: str | None, lat: float, lon: float, matchday: dt.date,
    *, with_climatology: bool,
) -> dict:
    """Assemble current series (+ optional climatology) for one location."""
    current = current_series(lat, lon, matchday)
    block = {
        "name": name,
        "country": country,
        "lat": lat,
        "lon": lon,
        "current": _series_payload(current),
    }
    if with_climatology:
        clim = climatology(lat, lon, matchday)
        block["climatology"] = {
            "offsets": [int(i) for i in clim.index],
            "values": {
                v: {
                    "mean": [_round(x) for x in clim[f"{v}_mean"]],
                    "p10": [_round(x) for x in clim[f"{v}_p10"]],
                    "p90": [_round(x) for x in clim[f"{v}_p90"]],
                }
                for v in DISPLAY_VARS
                if f"{v}_mean" in clim
            },
        }
        block["summary"] = _matchday_summary(current, clim, matchday)
    return block


def build_match_report(match: dict) -> dict:
    """Full three-way report for a single fixture (venue + both capitals)."""
    matchday = dt.date.fromisoformat(match["date"])
    venue = match["venue"]

    home_cap = fixtures.capital(match["home"])
    away_cap = fixtures.capital(match["away"])

    return {
        "match": match,
        "matchday": matchday.isoformat(),
        "window": {
            "days": config.WINDOW_DAYS,
            "start": window_bounds(matchday)[0].isoformat(),
            "end": matchday.isoformat(),
        },
        "variables": {
            v: config.VARIABLE_META[v] for v in DISPLAY_VARS
        },
        "era5_cutoff": prov.era5_cutoff(matchday).isoformat(),
        "venue": build_location_block(
            venue["name"], venue["country"], venue["lat"], venue["lon"],
            matchday, with_climatology=False,
        ),
        "capitals": {
            "home": build_location_block(
                home_cap["name"], match["home"], home_cap["lat"], home_cap["lon"],
                matchday, with_climatology=True,
            ),
            "away": build_location_block(
                away_cap["name"], match["away"], away_cap["lat"], away_cap["lon"],
                matchday, with_climatology=True,
            ),
        },
    }
