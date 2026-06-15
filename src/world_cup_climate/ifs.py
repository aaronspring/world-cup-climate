"""Simple IFS-only access via the open forecast repo.

`spring-data/ecwmf-ifs-15-days-forecast-open` ships proper CF coordinates:
real lat/lon (-180..180), `time` = 6-hourly init datetimes, `step` = timedelta
out to 15 days. We use two slices of it:

- **best estimate** : `step="0 days"` across every init -> the analysis at each
  cycle, i.e. a 6-hourly series of recent conditions up to the latest init.
- **forecast**      : the latest init, all steps -> the 0..15-day outlook.

Joined, they give one continuous "recent + forecast" line per location. We focus
on instantaneous fields (2t, 2d) + derived relative humidity and heat index, which
are exactly the fields that are meaningful at step 0.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
import xarray as xr

from .config import IFS_OPEN_REPO
from .sports import heat_index_celsius, kelvin_to_celsius, relative_humidity

VARS = ["2t", "2d"]  # instantaneous; valid at step 0


@lru_cache(maxsize=1)
def open_ifs() -> xr.Dataset:
    from arraylake import Client

    repo = Client().get_repo(IFS_OPEN_REPO)
    return xr.open_zarr(repo.readonly_session("main").store, chunks={})


def latest_init() -> pd.Timestamp:
    return pd.Timestamp(open_ifs()["time"].values[-1])


def _derive(t2m_k, d2m_k) -> pd.DataFrame:
    t2m_c = kelvin_to_celsius(t2m_k)
    d2m_c = kelvin_to_celsius(d2m_k)
    rh = relative_humidity(t2m_c, d2m_c)
    out = pd.DataFrame(
        {
            "t2m_c": t2m_c,
            "d2m_c": d2m_c,
            "rh": rh,
            "heat_index_c": heat_index_celsius(t2m_c, rh),
        }
    )
    return out


@lru_cache(maxsize=256)
def location_series(lat: float, lon: float) -> pd.DataFrame:
    """Continuous best-estimate + 15-day forecast series at a point.

    Columns: t2m_c, d2m_c, rh, heat_index_c, plus boolean `is_forecast`.
    Index: valid_time (UTC). Rows up to the latest init are the step=0 analysis;
    rows after are the latest init's forecast.
    """
    ds = open_ifs()
    pt = ds[VARS].sel(latitude=lat, longitude=lon, method="nearest")

    # best estimate: step 0 at every init
    analysis = pt.sel(step="0 days").load()
    a = _derive(analysis["2t"].values, analysis["2d"].values)
    a.index = pd.DatetimeIndex(analysis["time"].values, name="valid_time")
    a["is_forecast"] = False

    # forecast: latest init, all steps
    fc = pt.isel(time=-1).load()
    valid = pd.DatetimeIndex(fc["time"].values + fc["step"].values, name="valid_time")
    f = _derive(fc["2t"].values, fc["2d"].values)
    f.index = valid
    f["is_forecast"] = True

    # join; forecast wins at the overlap (its step 0 == latest analysis point)
    out = pd.concat([a[a.index < f.index[0]], f]).sort_index()
    return out[~out.index.duplicated(keep="last")]


def matchday_value(series: pd.DataFrame, matchday, col: str = "t2m_c") -> float:
    """Daily-max of `col` on the matchday (local-agnostic, UTC day)."""
    day = pd.Timestamp(matchday).normalize()
    sel = series[(series.index >= day) & (series.index < day + pd.Timedelta(days=1))]
    if sel.empty:
        return float("nan")
    return float(sel[col].max())
