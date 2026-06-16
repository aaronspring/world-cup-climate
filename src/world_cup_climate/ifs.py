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

import hashlib
import os
import pickle
import time
from functools import lru_cache, wraps
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from .config import IFS_OPEN_REPO, PROJECT_DIR
from .sports import heat_index_celsius, kelvin_to_celsius, relative_humidity

VARS = ["2t", "2d"]  # instantaneous; valid at step 0

# North-America t2m overlay: bbox + downsample for a compact web raster.
NA_BBOX = (-125.0, 14.0, -65.0, 60.0)  # west, south, east, north
NA_STRIDE = 5  # 0.1° grid -> 0.5°: ~120×93 cells, plenty for a continental field

CACHE_DIR = Path(os.environ.get("WCC_CACHE_DIR", PROJECT_DIR / ".cache" / "ifs"))


def _disk_cached(fn):
    """Persist a bulk extraction to disk, keyed by the init cycle + args.

    Lets a fresh `recompute.py` run reuse the last download instead of re-pulling
    from Arraylake — the data is identical until a new init cycle lands. Computing
    the key calls latest_init() (one cheap metadata read), far less than the pull.
    """
    @wraps(fn)
    def inner(*args):
        key = hashlib.md5(pickle.dumps((fn.__name__, str(latest_init()), args))).hexdigest()
        path = CACHE_DIR / f"{fn.__name__}-{key}.pkl"
        if path.exists():
            return pickle.loads(path.read_bytes())
        out = fn(*args)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(out))
        return out
    return inner


def _ttl_cache(seconds: int, maxsize: int):
    """lru_cache whose entries expire every `seconds` (IFS cycles land ~6h)."""
    def deco(fn):
        @lru_cache(maxsize=maxsize)
        def cached(_bucket, *args):
            return fn(*args)

        @wraps(fn)
        def inner(*args):
            return cached(int(time.time() // seconds), *args)
        return inner
    return deco


@_ttl_cache(3600, maxsize=2)  # 1h: re-open the store hourly
def open_ifs() -> xr.Dataset:
    import os

    from arraylake import Client

    # CACHE_ARRAYLAKE_TOKEN is the one with access to the open IFS repo;
    # fall back to ARRAYLAKE_TOKEN / ~/.arraylake login if it's unset.
    token = os.environ.get("CACHE_ARRAYLAKE_TOKEN") or os.environ.get("ARRAYLAKE_TOKEN")
    repo = Client(token=token).get_repo(IFS_OPEN_REPO)
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


def _assemble(a2t, a2d, a_time, f2t, f2d, f_valid, init) -> pd.DataFrame:
    """Join one point's step-0 analysis history + latest-init forecast → 1h series.

    Columns: t2m_c, d2m_c, rh, heat_index_c, plus boolean `is_forecast`.
    Index: valid_time (UTC). Past is 6-hourly, the forecast coarsens to 3h/6h, so
    we resample to a gap-free 1h grid.
    """
    a = _derive(a2t, a2d)
    a.index = pd.DatetimeIndex(a_time, name="valid_time")
    f = _derive(f2t, f2d)
    f.index = pd.DatetimeIndex(f_valid, name="valid_time")
    joined = pd.concat([a[a.index < init], f]).sort_index()
    out = joined[~joined.index.duplicated(keep="last")].resample("1h").interpolate("time")
    out["is_forecast"] = out.index >= init
    return out


@_ttl_cache(3600, maxsize=256)  # 1h: cache point series for the fixtures
def location_series(lat: float, lon: float) -> pd.DataFrame:
    """Continuous best-estimate + 15-day forecast series at a single point."""
    ds = open_ifs()
    pt = ds[VARS].sel(latitude=lat, longitude=lon, method="nearest")
    init = pd.Timestamp(ds["time"].values[-1])
    analysis = pt.sel(step="0 days").load()      # step 0 at every init (6-hourly)
    fc = pt.isel(time=-1).load()                 # latest init, all steps
    return _assemble(
        analysis["2t"].values, analysis["2d"].values, analysis["time"].values,
        fc["2t"].values, fc["2d"].values, fc["time"].values + fc["step"].values, init,
    )


@_disk_cached
def extract_points(latlons: list[tuple[float, float]]) -> list[pd.DataFrame]:
    """Bulk nearest-point extraction, aligned to `latlons` order.

    One `.load()` for the analysis slice and one for the forecast slice — total,
    not per point. xarray's vectorized point selection fetches each Zarr chunk
    once and reuses it for every point that falls in it, so cost scales with the
    number of *distinct chunks* the points touch, not the number of points. Far
    cheaper than a round-trip per location, and a fraction of the full-globe pull
    (~7 GB for 2t+2d over 145 steps) it replaces.
    """
    ds = open_ifs()
    lat = xr.DataArray([la for la, _ in latlons], dims="pt")
    lon = xr.DataArray([lo for _, lo in latlons], dims="pt")
    sel = ds[VARS].sel(latitude=lat, longitude=lon, method="nearest")
    init = pd.Timestamp(ds["time"].values[-1])

    analysis = sel.sel(step="0 days").load()     # dims (time, pt)
    fc = sel.isel(time=-1).load()                # dims (step, pt)
    a_time = analysis["time"].values
    f_valid = fc["time"].values + fc["step"].values
    return [
        _assemble(
            analysis["2t"].isel(pt=i).values, analysis["2d"].isel(pt=i).values, a_time,
            fc["2t"].isel(pt=i).values, fc["2d"].isel(pt=i).values, f_valid, init,
        )
        for i in range(len(latlons))
    ]


@_disk_cached
def na_t2m_fields(valid_times: list) -> tuple[dict[str, list[float]], dict, list[str]]:
    """Downsampled North-America t2m (°C) at each distinct valid hour needed.

    For each requested valid time we pick the nearest available field: the
    latest-init forecast step for times at/after the init, or the step-0 analysis
    of the nearest init for past times. Two `.load()` calls total (one per branch).

    Returns ``(fields, meta, keys)`` where ``fields[hourKey]`` is a row-major
    (north-west origin) flat list, ``meta`` has ``bounds``/``nx``/``ny``, and
    ``keys[i]`` is the hour key serving ``valid_times[i]``.
    """
    ds = open_ifs()
    init = pd.Timestamp(ds["time"].values[-1])
    da = ds["2t"]
    lat, lon = da["latitude"].values, da["longitude"].values
    w, s, e, n = NA_BBOX
    yi = np.where((lat >= s) & (lat <= n))[0][::NA_STRIDE]
    xi = np.where((lon >= w) & (lon <= e))[0][::NA_STRIDE]
    sub = da.isel(latitude=yi, longitude=xi)

    fc_valid = init + pd.to_timedelta(da["step"].values)   # latest-init forecast
    an_valid = pd.DatetimeIndex(da["time"].values)         # step-0 analysis per init
    fc_need, an_need, keys = {}, {}, []
    for vt in valid_times:
        vt = pd.Timestamp(vt)
        if vt >= init:
            i = int(np.abs(fc_valid - vt).argmin()); t = fc_valid[i]; fc_need[i] = t
        else:
            i = int(np.abs(an_valid - vt).argmin()); t = an_valid[i]; an_need[i] = t
        keys.append(pd.Timestamp(t).strftime("%Y-%m-%dT%H"))

    fields, meta = {}, {}

    def harvest(grid, need):
        nonlocal meta
        g = grid.sortby("latitude", ascending=False).sortby("longitude")
        block = np.round(kelvin_to_celsius(g.load().values), 1)  # (k, ny, nx)
        meta = {
            "bounds": [float(g.longitude.min()), float(g.latitude.min()),
                       float(g.longitude.max()), float(g.latitude.max())],
            "nx": int(g.sizes["longitude"]), "ny": int(g.sizes["latitude"]),
        }
        for p, i in enumerate(sorted(need)):
            k = pd.Timestamp(need[i]).strftime("%Y-%m-%dT%H")
            fields[k] = block[p].ravel().tolist()

    if fc_need:
        harvest(sub.isel(time=-1).isel(step=sorted(fc_need)), fc_need)
    if an_need:
        harvest(sub.sel(step="0 days").isel(time=sorted(an_need)), an_need)
    return fields, meta, keys


def matchday_value(series: pd.DataFrame, matchday, col: str = "t2m_c") -> float:
    """Daily-max of `col` on the matchday (local-agnostic, UTC day)."""
    day = pd.Timestamp(matchday).normalize()
    sel = series[(series.index >= day) & (series.index < day + pd.Timedelta(days=1))]
    if sel.empty:
        return float("nan")
    return float(sel[col].max())
