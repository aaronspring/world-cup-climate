"""Simple IFS-only access via the open forecast repo.

`spring-data/ecwmf-ifs-15-days-forecast-open` ships proper CF coordinates:
real lat/lon (-180..180), `time` = 6-hourly init datetimes, `step` = timedelta
out to 15 days. We use two slices of it:

- **best estimate** : `step="0 days"` across every init -> the analysis at each
  cycle, i.e. a 6-hourly series of recent conditions up to the latest init.
- **forecast**      : the latest init, all steps -> the 0..15-day outlook.

Joined, they give one continuous "recent + forecast" line per location.

Variables extracted: 2t, 2d (instantaneous) plus 10u, 10v (wind components,
instantaneous) and ssrd (solar radiation, accumulated — deaccumulated to W/m²
in the forecast branch; NaN for step-0 analysis where it's always 0).
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
from .sports import (
    heat_index_celsius,
    humidex_celsius,
    kelvin_to_celsius,
    relative_humidity,
    utci_celsius,
    wbgt_celsius,
    wind_chill_celsius,
)

# Instantaneous fields + accumulated solar radiation.
VARS = ["2t", "2d", "10u", "10v", "ssrd"]

# North-America t2m overlay: bbox + downsample for a compact web raster.
NA_BBOX = (-125.0, 14.0, -65.0, 60.0)  # west, south, east, north
NA_STRIDE = 1  # native 0.1° grid, no resampling -> ~601×461 cells

CACHE_DIR = Path(os.environ.get("WCC_CACHE_DIR", PROJECT_DIR / ".cache" / "ifs"))

# Include variable list in cache keys so adding/removing VARS busts old files.
_VARS_KEY = hashlib.md5(str(sorted(VARS)).encode()).hexdigest()[:8]


def _disk_cached(fn):
    """Persist a bulk extraction to disk, keyed by the init cycle + args.

    Lets a fresh `recompute.py` run reuse the last download instead of re-pulling
    from Arraylake — the data is identical until a new init cycle lands. Computing
    the key calls latest_init() (one cheap metadata read), far less than the pull.
    """
    @wraps(fn)
    def inner(*args):
        key = hashlib.md5(
            pickle.dumps((fn.__name__, _VARS_KEY, str(latest_init()), args))
        ).hexdigest()
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
    from arraylake import Client

    # CACHE_ARRAYLAKE_TOKEN is the one with access to the open IFS repo;
    # fall back to ARRAYLAKE_TOKEN / ~/.arraylake login if it's unset.
    token = os.environ.get("CACHE_ARRAYLAKE_TOKEN") or os.environ.get("ARRAYLAKE_TOKEN")
    repo = Client(token=token).get_repo(IFS_OPEN_REPO)
    return xr.open_zarr(repo.readonly_session("main").store, chunks={})


def latest_init() -> pd.Timestamp:
    return pd.Timestamp(open_ifs()["time"].values[-1])


# A land point that always carries a valid 2t value; used to probe whether an
# init's longest step is actually populated.
_PROBE_LATLON = (48.85, 2.35)  # Paris


def _latest_long_idx(ds: xr.Dataset) -> int:
    """Index of the latest init whose full 15-day forecast is actually populated.

    Two gates, both verified against the store:
    - ECMWF open data publishes all 145 steps (out to 15 days) only for the 00z
      and 12z runs; the 06z/18z runs stop at 144h, leaving the longer steps NaN.
    - A freshly announced init can appear on the `time` axis before its data is
      written, so we also require the longest step to be non-NaN at a land probe
      point and walk back to the most recent complete long run.
    """
    times = pd.DatetimeIndex(ds["time"].values)
    longs = np.where((times.hour == 0) | (times.hour == 12))[0]
    probe = ds["2t"].isel(step=-1).sel(
        latitude=_PROBE_LATLON[0], longitude=_PROBE_LATLON[1], method="nearest"
    )
    for i in longs[::-1]:
        if np.isfinite(probe.isel(time=int(i)).load().values):
            return int(i)
    raise RuntimeError("no complete 15-day IFS init found")


def latest_long_init() -> pd.Timestamp:
    ds = open_ifs()
    return pd.Timestamp(ds["time"].values[_latest_long_idx(ds)])


def _deaccumulate_ssrd(ssrd_accumulated, steps_timedelta) -> np.ndarray:
    """Convert step-accumulated ssrd (J/m²) to per-step average flux (W/m²).

    ssrd at step 0 is always 0 (nothing elapsed). We diff and divide by the
    step duration. Negative values (rounding noise) are clipped to 0.
    """
    raw = np.asarray(ssrd_accumulated, dtype=float)
    # Step duration in seconds; prepend 0 so dt[0] = duration of first step.
    dt_s = np.diff(
        steps_timedelta.astype("timedelta64[s]").astype(float), prepend=0.0
    )
    dt_s = np.where(dt_s > 0, dt_s, 3600.0)
    return np.clip(np.diff(raw, prepend=0.0) / dt_s, 0.0, None)


def _derive(
    t2m_k, d2m_k,
    u10=None, v10=None,
    ssrd_wm2=None,
) -> pd.DataFrame:
    t2m_c = kelvin_to_celsius(t2m_k)
    d2m_c = kelvin_to_celsius(d2m_k)
    rh = relative_humidity(t2m_c, d2m_c)
    out = pd.DataFrame(
        {
            "t2m_c": t2m_c,
            "d2m_c": d2m_c,
            "rh": rh,
            "heat_index_c": heat_index_celsius(t2m_c, rh),
            "humidex_c": humidex_celsius(t2m_c, d2m_c),
        }
    )
    if u10 is not None and v10 is not None:
        wind_ms = np.sqrt(np.asarray(u10, dtype=float) ** 2 + np.asarray(v10, dtype=float) ** 2)
        out["wind_ms"] = wind_ms
        out["wind_chill_c"] = wind_chill_celsius(t2m_c, wind_ms)
        out["utci_c"] = utci_celsius(t2m_c, rh, wind_ms, ssrd_wm2)
        out["wbgt_c"] = wbgt_celsius(t2m_c, rh, wind_ms, ssrd_wm2)
        if ssrd_wm2 is not None:
            out["ssrd_wm2"] = ssrd_wm2
    return out


def _assemble(
    a2t, a2d, a_time,
    f2t, f2d, f_valid, init,
    a_u10=None, a_v10=None,
    f_u10=None, f_v10=None,
    f_ssrd=None, f_steps=None,
) -> pd.DataFrame:
    """Join one point's step-0 analysis history + latest-init forecast → 1h series.

    Columns: t2m_c, d2m_c, rh, heat_index_c, humidex_c, and (when wind/solar
    are available) wind_ms, wind_chill_c, apparent_temp_c, ssrd_wm2, wbgt_c,
    plus boolean `is_forecast`.
    Index: valid_time (UTC). Past is 6-hourly, the forecast coarsens to 3h/6h,
    so we resample to a gap-free 1h grid.
    """
    # ssrd is accumulated from init; deaccumulate to W/m² for the forecast branch.
    # At step=0 (analysis), ssrd is always 0 — not useful, so we pass None.
    f_ssrd_wm2 = None
    if f_ssrd is not None and f_steps is not None:
        f_ssrd_wm2 = _deaccumulate_ssrd(f_ssrd, f_steps)

    a = _derive(a2t, a2d, a_u10, a_v10, None)
    a.index = pd.DatetimeIndex(a_time, name="valid_time")
    f = _derive(f2t, f2d, f_u10, f_v10, f_ssrd_wm2)
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
    init_idx = _latest_long_idx(ds)
    init = pd.Timestamp(ds["time"].values[init_idx])
    analysis = pt.sel(step="0 days").load()      # step 0 at every init (6-hourly)
    fc = pt.isel(time=init_idx).load()           # latest 15-day init, all steps
    f_valid = fc["time"].values + fc["step"].values
    return _assemble(
        analysis["2t"].values, analysis["2d"].values, analysis["time"].values,
        fc["2t"].values, fc["2d"].values, f_valid, init,
        a_u10=analysis["10u"].values, a_v10=analysis["10v"].values,
        f_u10=fc["10u"].values, f_v10=fc["10v"].values,
        f_ssrd=fc["ssrd"].values, f_steps=fc["step"].values,
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
    init_idx = _latest_long_idx(ds)
    init = pd.Timestamp(ds["time"].values[init_idx])

    analysis = sel.sel(step="0 days").load()     # dims (time, pt)
    fc = sel.isel(time=init_idx).load()          # dims (step, pt)
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
    init_idx = _latest_long_idx(ds)
    init = pd.Timestamp(ds["time"].values[init_idx])
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
        # lat/lon are cell *centers*; the image-source quad must sit on cell
        # *edges*, so pad the bounds by half a grid step (else a ~½-cell shift).
        lo, la = g.longitude.values, g.latitude.values
        dx = float(np.diff(lo).mean()) / 2 if lo.size > 1 else 0.0
        dy = float(np.diff(la).mean()) / 2 if la.size > 1 else 0.0
        meta = {
            "bounds": [float(lo.min()) - dx, float(la.min()) - dy,
                       float(lo.max()) + dx, float(la.max()) + dy],
            "nx": int(g.sizes["longitude"]), "ny": int(g.sizes["latitude"]),
        }
        for p, i in enumerate(sorted(need)):
            k = pd.Timestamp(need[i]).strftime("%Y-%m-%dT%H")
            fields[k] = block[p].ravel().tolist()

    if fc_need:
        harvest(sub.isel(time=init_idx).isel(step=sorted(fc_need)), fc_need)
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
