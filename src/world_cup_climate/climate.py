"""Assemble the climate story for one location: current window (ERA5 + forecast),
forward outlook, and the 10-year historical normal for the same calendar window.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from .client import era5_end_time
from .config import N_HISTORICAL_YEARS, WINDOW_DAYS
from .era5 import era5_point
from .forecast import choose_gap_init, forecast_point, latest_init
from .locations import Place
from .sports import DAILY_VARS, aggregate_daily

CLIM_STATS = ["mean", "std", "p10", "p50", "p90", "min", "max"]


@dataclass
class LocationClimate:
    place: Place
    current: pd.DataFrame                 # daily, index=date, has 'offset' column
    outlook: pd.DataFrame | None          # daily forecast beyond matchday
    hist_years: dict[int, pd.DataFrame]   # year -> daily window, 'offset' column
    climatology: dict[str, pd.DataFrame]  # var -> DataFrame(index=offset, CLIM_STATS)
    matchday: pd.Timestamp

    @property
    def matchday_now(self) -> pd.Series:
        """Daily values at the matchday (offset 0) from the current series."""
        row = self.current[self.current["offset"] == 0]
        return row.iloc[0] if len(row) else self.current.iloc[-1]

    def matchday_normal(self, var: str) -> pd.Series:
        """Climatological stats for `var` on the matchday (offset 0)."""
        clim = self.climatology[var]
        return clim.loc[0] if 0 in clim.index else clim.iloc[-1]


def _window_bounds(matchday: pd.Timestamp, window_days: int):
    end = matchday.normalize() + pd.Timedelta(hours=23, minutes=59)
    start = (matchday.normalize() - pd.Timedelta(days=window_days - 1))
    return start, end


def _with_offset(daily: pd.DataFrame, anchor: pd.Timestamp) -> pd.DataFrame:
    daily = daily.copy()
    daily["offset"] = (daily.index.normalize() - anchor.normalize()).days
    return daily


def _current_series(lat, lon, matchday, window_days) -> pd.DataFrame:
    start, end = _window_bounds(matchday, window_days)
    era5_end = era5_end_time()

    parts = []
    era5_stop = min(end, era5_end)
    if era5_stop >= start:
        parts.append(era5_point(lat, lon, start, era5_stop))

    # forecast fills the ERA5 -> matchday gap, if any
    if end > era5_end:
        gap_init = choose_gap_init(era5_end)
        parts.append(
            forecast_point(lat, lon, gap_init, era5_end + pd.Timedelta(hours=1), end)
        )

    hourly = pd.concat(parts).sort_index()
    hourly = hourly[~hourly.index.duplicated(keep="first")]
    return _with_offset(aggregate_daily(hourly), matchday)


def _outlook_series(lat, lon, matchday, outlook_days) -> pd.DataFrame | None:
    if outlook_days <= 0:
        return None
    init = latest_init()
    start = matchday.normalize() + pd.Timedelta(days=1)
    end = matchday.normalize() + pd.Timedelta(days=outlook_days, hours=23, minutes=59)
    try:
        hourly = forecast_point(lat, lon, init, start, end)
    except ValueError:
        return None
    if hourly.empty:
        return None
    return _with_offset(aggregate_daily(hourly), matchday)


def _historical(lat, lon, matchday, n_years, window_days):
    hist = {}
    for y in range(matchday.year - 1, matchday.year - 1 - n_years, -1):
        try:
            anchor = matchday.replace(year=y)
        except ValueError:  # Feb 29 in a non-leap year
            anchor = matchday.replace(year=y, day=28)
        start, end = _window_bounds(anchor, window_days)
        hourly = era5_point(lat, lon, start, end)
        if hourly.empty:
            continue
        hist[y] = _with_offset(aggregate_daily(hourly), anchor)

    # stack into climatology per variable, indexed by day-offset
    clim = {}
    daily_cols = [c for c in DAILY_VARS if any(c in df for df in hist.values())]
    for var in daily_cols:
        wide = pd.DataFrame(
            {y: df.set_index("offset")[var] for y, df in hist.items() if var in df}
        )
        stats = pd.DataFrame(index=wide.index)
        stats["mean"] = wide.mean(axis=1)
        stats["std"] = wide.std(axis=1)
        stats["p10"] = wide.quantile(0.10, axis=1)
        stats["p50"] = wide.quantile(0.50, axis=1)
        stats["p90"] = wide.quantile(0.90, axis=1)
        stats["min"] = wide.min(axis=1)
        stats["max"] = wide.max(axis=1)
        clim[var] = stats.sort_index()
    return hist, clim


@lru_cache(maxsize=128)
def _location_climate_cached(
    lat: float,
    lon: float,
    place_name: str,
    place_label: str,
    place_country: str,
    matchday_iso: str,
    n_years: int,
    window_days: int,
    outlook_days: int,
) -> LocationClimate:
    matchday = pd.Timestamp(matchday_iso)
    place = Place(place_name, place_label, place_country, lat, lon)
    current = _current_series(lat, lon, matchday, window_days)
    outlook = _outlook_series(lat, lon, matchday, outlook_days)
    hist, clim = _historical(lat, lon, matchday, n_years, window_days)
    return LocationClimate(
        place=place,
        current=current,
        outlook=outlook,
        hist_years=hist,
        climatology=clim,
        matchday=matchday,
    )


def location_climate(
    place: Place,
    matchday,
    n_years: int = N_HISTORICAL_YEARS,
    window_days: int = WINDOW_DAYS,
    outlook_days: int = 5,
) -> LocationClimate:
    """Full climate bundle for a place around a matchday (cached)."""
    matchday = pd.Timestamp(matchday)
    return _location_climate_cached(
        place.lat,
        place.lon,
        place.name,
        place.label,
        place.country,
        matchday.strftime("%Y-%m-%d"),
        n_years,
        window_days,
        outlook_days,
    )
