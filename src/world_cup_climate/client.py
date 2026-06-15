"""Cached Arraylake sessions and dataset handles.

Reads are fastest from a compute node in AWS us-east-1 (where the stores live);
they work from anywhere but a point time series pulled to a laptop is slower.
Authentication uses the token from `arraylake auth login` (~/.arraylake/token.json)
or the ARRAYLAKE_TOKEN environment variable.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
import xarray as xr

from .config import (
    ERA5_GROUP,
    ERA5_REPO,
    FORECAST_INIT_FREQ_HOURS,
    FORECAST_REPO,
)


@lru_cache(maxsize=1)
def _client():
    from arraylake import Client

    return Client()


@lru_cache(maxsize=1)
def era5_dataset() -> xr.Dataset:
    """ERA5 hourly point-optimized store (group `single/temporal`)."""
    repo = _client().get_repo(ERA5_REPO)
    session = repo.readonly_session("main")
    return xr.open_zarr(session.store, group=ERA5_GROUP, chunks=None)


@lru_cache(maxsize=1)
def _forecast_repo():
    return _client().get_repo(FORECAST_REPO)


@lru_cache(maxsize=1)
def forecast_dataset() -> xr.Dataset:
    """ECMWF IFS forecast store with real coordinates attached.

    The raw store ships `time`/`step`/`latitude`/`longitude` as bare integer
    indices, so we reconstruct them:
      - latitude  : 90 -> -90 at 0.1 deg
      - longitude : 0 -> 359.9 at 0.1 deg (degrees east)
      - step      : forecast lead in hours (index == hour)
      - time      : 6-hourly init cycles ending at the latest ingested init
    """
    repo = _forecast_repo()
    session = repo.readonly_session("main")
    ds = xr.open_zarr(session.store, chunks=None)

    nlat, nlon = ds.sizes["latitude"], ds.sizes["longitude"]
    lat = 90.0 - np.arange(nlat) * 0.1
    # NOTE: the raw longitude index starts at the dateline, not Greenwich.
    # Verified empirically against ERA5 (solar-noon timing + temperature match for
    # Madrid/Cairo/Tokyo/Buenos Aires): lon_deg = (idx * 0.1 + 180) % 360.
    # This coordinate is therefore non-monotonic; select points via fc_grid_index().
    lon = (np.arange(nlon) * 0.1 + 180.0) % 360.0
    step_hours = forecast_step_hours(ds.sizes["step"])

    init_times = latest_forecast_init()
    init_axis = pd.date_range(
        end=init_times, periods=ds.sizes["time"], freq=f"{FORECAST_INIT_FREQ_HOURS}h"
    )

    ds = ds.assign_coords(
        latitude=("latitude", lat),
        longitude=("longitude", lon),
        step=("step", pd.to_timedelta(step_hours, unit="h")),
        time=("time", init_axis),
    )
    return ds


def forecast_step_hours(n_steps: int) -> np.ndarray:
    """Real forecast lead hours for each `step` index.

    The store ships `step` as bare indices 0..n-1, but ECMWF IFS-ENS uses a
    non-uniform schedule: hourly to 90h, 3-hourly to 144h, 6-hourly to 360h
    (145 steps for the 15-day product). Verified against the ssrd accumulation
    curve (constant ~30 MJ/day at Madrid only under this mapping).
    """
    hours = np.concatenate(
        [
            np.arange(0, 91, 1),     # 0..90 hourly        (91)
            np.arange(93, 145, 3),   # 93..144 3-hourly     (18)
            np.arange(150, 361, 6),  # 150..360 6-hourly    (36)
        ]
    )
    if len(hours) != n_steps:
        # Unknown schedule: fall back to treating the index as hours.
        return np.arange(n_steps)
    return hours


@lru_cache(maxsize=1)
def latest_forecast_init() -> pd.Timestamp:
    """Init datetime of the most recently ingested forecast (newest commit)."""
    repo = _forecast_repo()
    snap = next(iter(repo.ancestry(branch="main")))
    dt = (snap.metadata or {}).get("datetime")
    if dt is None:
        raise RuntimeError("Could not read latest forecast init from commit metadata")
    return pd.Timestamp(dt).tz_localize(None)


def era5_end_time() -> pd.Timestamp:
    """Last valid_time available in ERA5 (≈ today - 6 days)."""
    return pd.Timestamp(era5_dataset()["valid_time"].values[-1])


def fc_grid_index(lat: float, lon: float) -> tuple[int, int]:
    """Nearest (latitude_index, longitude_index) into the forecast grid.

    Grid is 0.1 deg with latitude 90 -> -90 and longitude offset by 180 deg
    (index 0 == 180 deg E). Returns indices for direct .isel() selection.
    """
    li = int(round((90.0 - lat) / 0.1))
    lo = int(round((((lon % 360) - 180.0) % 360.0) / 0.1))
    li = min(max(li, 0), 1800)
    lo = lo % 3600
    return li, lo
