"""Point time-series providers + daily aggregation.

A *provider* returns a **raw hourly** point series (see the convention in
:mod:`world_cup_climate.arraylake_io`). Two sources are supported and chosen by
the ``WCC_DATA_SOURCE`` environment variable:

* ``live`` (default) — ERA5 via Flux **EDR** (falling back to the Arraylake
  Python client), and the IFS forecast via the Python client.
* ``fake`` — a synthetic generator with a realistic **diurnal cycle**, used for
  offline development, tests, and demos when no token / network is available.
  It mimics the *raw* hourly returns from Arraylake so the exact same
  aggregation / climatology code runs on top of it.

Everything downstream consumes :func:`daily_point` / :func:`era5_cutoff`, so the
choice of source is fully transparent to :mod:`world_cup_climate.climate`.
"""

from __future__ import annotations

import datetime as dt
import functools
import hashlib
import json
import os
import pickle

import numpy as np
import pandas as pd

from . import config


def data_source() -> str:
    return os.environ.get("WCC_DATA_SOURCE", "live").lower()


# --------------------------------------------------------------------------- #
# Synthetic provider — physically-flavoured diurnal cycle
# --------------------------------------------------------------------------- #
S0 = 1361.0  # solar constant, W m-2


def _rng(lat: float, lon: float, day: pd.Timestamp) -> np.random.Generator:
    """Deterministic RNG seeded by location + calendar day.

    Same (lat, lon, date) -> same draw (stable), but different years differ,
    which gives the climatology genuine year-to-year spread.
    """
    key = f"{round(lat, 1)}_{round(lon, 1)}_{day.date().isoformat()}"
    seed = int.from_bytes(hashlib.sha1(key.encode()).digest()[:8], "big")
    return np.random.default_rng(seed)


def fake_hourly_point(
    lat: float, lon: float, start: str, end: str,
    variables: tuple[str, ...] = config.VARIABLES,
) -> pd.DataFrame:
    """Synthetic raw hourly series with a diurnal (and seasonal/latitudinal) cycle.

    Units match ERA5: t2m/d2m in K, tp in m (per-hour), ssrd in J m-2 (per-hour).
    """
    idx = pd.date_range(
        pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="1h"
    )
    doy = idx.dayofyear.to_numpy()
    hour = idx.hour.to_numpy()

    # --- solar geometry (drives ssrd and the diurnal temperature shape) ---
    decl = np.deg2rad(23.44 * np.cos(np.deg2rad(360.0 / 365.0 * (doy - 172))))
    latr = np.deg2rad(lat)
    local_hour = (hour + lon / 15.0) % 24.0
    hour_angle = np.deg2rad(15.0 * (local_hour - 12.0))
    cos_zen = np.clip(
        np.sin(latr) * np.sin(decl) + np.cos(latr) * np.cos(decl) * np.cos(hour_angle),
        0.0, None,
    )

    # --- per-day random fields (cloud, temp anomaly, rain) ---
    cloud = np.empty(len(idx))
    temp_anom = np.empty(len(idx))
    rain_hourly = np.zeros(len(idx))
    for day, mask in _group_by_day(idx):
        rng = _rng(lat, lon, day)
        cloud[mask] = np.clip(rng.beta(2, 3) + rng.normal(0, 0.05), 0, 1)
        temp_anom[mask] = rng.normal(0, 2.0)  # K, synoptic-scale daily anomaly
        # rain: tropics wetter; if a rainy day, dump over the afternoon
        p_rain = 0.25 + 0.35 * np.exp(-((lat / 15.0) ** 2))
        if rng.random() < p_rain:
            total_mm = rng.gamma(2.0, 4.0)  # mm for the day
            lh = local_hour[mask]
            weight = np.clip(np.cos(np.deg2rad(15.0 * (lh - 16.0))), 0, None) ** 2
            weight = weight / weight.sum() if weight.sum() else weight
            rain_hourly[mask] = total_mm * weight / 1000.0  # mm -> m

    # --- temperature: annual mean by latitude + seasonal + diurnal + anomaly ---
    annual_mean = 300.0 - 0.35 * abs(lat)                       # K
    seasonal_amp = 0.18 * abs(lat)                              # K
    hemis = np.sign(lat) if lat != 0 else 1.0
    seasonal = hemis * seasonal_amp * np.cos(np.deg2rad(360.0 / 365.0 * (doy - 202)))
    diurnal = 4.5 * np.cos(np.deg2rad(15.0 * (local_hour - 15.0))) * (1 - 0.4 * cloud)
    t2m = annual_mean + seasonal + diurnal + temp_anom

    # dewpoint: temperature minus a (cloud-modulated) depression
    depression = (2.0 + 7.0 * (1 - cloud)).clip(0, None)
    d2m = t2m - depression

    # surface solar radiation downwards, J m-2 per hour
    ssrd = 0.78 * S0 * cos_zen * (1 - 0.7 * cloud) * 3600.0

    frame = pd.DataFrame(
        {"t2m": t2m, "d2m": d2m, "tp": rain_hourly, "ssrd": ssrd}, index=idx
    )
    return frame[list(variables)]


def _group_by_day(idx: pd.DatetimeIndex):
    days = idx.normalize()
    for day in pd.unique(days):
        yield pd.Timestamp(day), (days == day)


# --------------------------------------------------------------------------- #
# Dispatch: raw hourly for a dataset ("era5" | "forecast")
# --------------------------------------------------------------------------- #
def hourly_point(
    dataset: str, lat: float, lon: float, start: str, end: str,
    variables: tuple[str, ...] = config.VARIABLES,
) -> pd.DataFrame:
    if data_source() == "fake":
        return fake_hourly_point(lat, lon, start, end, variables)

    from . import arraylake_io as io

    if dataset == "era5":
        return io.era5_hourly_point(lat, lon, start, end, variables)
    if dataset == "forecast":
        return io.forecast_hourly_point(lat, lon, start, end, variables)
    raise ValueError(f"Unknown dataset {dataset!r}")


# --------------------------------------------------------------------------- #
# Daily aggregation (UTC calendar day) with a small on-disk cache
# --------------------------------------------------------------------------- #
def _daily_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    pieces = {}
    for var in df.columns:
        rule = config.VARIABLE_META.get(var, {}).get("daily_agg", "mean")
        resampled = df[var].resample("1D")
        pieces[var] = resampled.sum() if rule == "sum" else resampled.mean()
    return pd.DataFrame(pieces)


def daily_point(
    dataset: str, lat: float, lon: float, start: str, end: str,
    variables: tuple[str, ...] = config.VARIABLES,
) -> pd.DataFrame:
    """Daily series at the nearest grid cell for ``[start, end]`` (UTC days)."""
    source = data_source()
    if source != "fake":
        cached = _cache_get(dataset, source, lat, lon, start, end, variables)
        if cached is not None:
            return cached

    hourly = hourly_point(dataset, lat, lon, start, end, variables)
    daily = _daily_aggregate(hourly)
    daily = daily.loc[(daily.index >= pd.Timestamp(start).normalize())
                      & (daily.index <= pd.Timestamp(end).normalize())]

    if source != "fake":
        _cache_put(daily, dataset, source, lat, lon, start, end, variables)
    return daily


def era5_cutoff(today: dt.date | None = None) -> dt.date:
    """Latest reanalysis day. For fake data, ``today`` minus the typical latency."""
    if data_source() == "fake":
        base = today or dt.date.today()
        return base - dt.timedelta(days=config.ERA5_LATENCY_DAYS)
    from . import arraylake_io as io

    return io.era5_latest_time().normalize().date()


# --- tiny disk cache -------------------------------------------------------- #
def _cache_path(*parts) -> "os.PathLike":
    key = json.dumps(parts, default=str, sort_keys=True)
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    return config.CACHE_DIR / f"daily_{digest}.pkl"


def _cache_get(*parts):
    path = _cache_path(*parts)
    if path.exists():
        with open(path, "rb") as fh:
            return pickle.load(fh)
    return None


def _cache_put(value, *parts):
    with open(_cache_path(*parts), "wb") as fh:
        pickle.dump(value, fh)
