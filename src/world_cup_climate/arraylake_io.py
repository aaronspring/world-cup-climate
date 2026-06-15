"""Real Arraylake data access — returns *raw hourly* point series.

Convention for the "raw" frames returned here (so providers can be swapped
freely, incl. the synthetic one in :mod:`world_cup_climate.providers`):

* index   : hourly ``valid_time`` (UTC, tz-naive)
* columns : canonical variable names in native units
            (``t2m``/``d2m`` in K, ``tp`` in m, ``ssrd`` in J m⁻²)
* accumulations (``tp``, ``ssrd``) are expressed as **per-hour increments**,
  matching ERA5's native hourly accumulation. The forecast fetcher therefore
  de-accumulates the IFS run (which accumulates from step 0) by differencing.

Access paths
------------
* **ERA5** — preferred path is the **Flux EDR** service (OGC Environmental Data
  Retrieval): a ``position`` query returns a point time series as compact JSON,
  no Zarr chunk reads. Set ``WCC_ERA5_VIA=xarray`` to use the Python client
  instead (e.g. EDR unavailable). EDR is the recommended service for time-series
  access in a web app.
* **Forecast** — ``spring-data`` has no Flux service deployed, so this always
  uses the Arraylake Python client + xarray, reading only the steps in-window.

Credentials come from ``ARRAYLAKE_TOKEN`` (an ``ema_...`` token); nothing is
hardcoded.
"""

from __future__ import annotations

import functools
import os

import numpy as np
import pandas as pd
import xarray as xr

from . import config


class MissingTokenError(RuntimeError):
    """Raised when no Arraylake credentials are available."""


def _token() -> str | None:
    return os.environ.get("ARRAYLAKE_TOKEN")


# --------------------------------------------------------------------------- #
# Python client / dataset handles
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=1)
def get_client():
    """Authenticated Arraylake ``Client`` (prefers ``ARRAYLAKE_TOKEN``)."""
    from arraylake import Client

    token = _token()
    if token:
        return Client(token=token)
    try:
        client = Client()
        client.list_orgs()
        return client
    except Exception as exc:  # noqa: BLE001
        raise MissingTokenError(
            "No Arraylake credentials found. Set ARRAYLAKE_TOKEN (an 'ema_...' "
            "token from https://app.earthmover.io), e.g. `export ARRAYLAKE_TOKEN=ema_…`, "
            "or run `al auth login`. For offline development set WCC_DATA_SOURCE=fake."
        ) from exc


@functools.lru_cache(maxsize=4)
def open_dataset(repo_name: str, group: str) -> xr.Dataset:
    """Open an Arraylake repo group as a lazy (non-Dask) xarray Dataset."""
    repo = get_client().get_repo(repo_name)
    store = repo.readonly_session(branch=config.BRANCH).store
    return xr.open_zarr(store, group=group or None, consolidated=False, chunks=None)


def _nearest(ds: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    return ds.sel(latitude=lat, longitude=lon % 360.0, method="nearest")


# --------------------------------------------------------------------------- #
# ERA5 — latency boundary
# --------------------------------------------------------------------------- #
def era5_latest_time() -> pd.Timestamp:
    """Most recent ERA5 ``valid_time`` (reanalysis end / latency boundary)."""
    ds = open_dataset(config.ERA5_REPO, config.ERA5_GROUP)
    return pd.Timestamp(ds.valid_time.values[-1])


# --------------------------------------------------------------------------- #
# ERA5 — raw hourly point series
# --------------------------------------------------------------------------- #
def era5_hourly_point(
    lat: float, lon: float, start: str, end: str,
    variables: tuple[str, ...] = config.VARIABLES,
) -> pd.DataFrame:
    via = os.environ.get("WCC_ERA5_VIA", "edr").lower()
    if via == "edr":
        try:
            return _era5_hourly_edr(lat, lon, start, end, variables)
        except Exception:  # noqa: BLE001 - fall back to the client path
            return _era5_hourly_xarray(lat, lon, start, end, variables)
    return _era5_hourly_xarray(lat, lon, start, end, variables)


def _era5_hourly_xarray(lat, lon, start, end, variables) -> pd.DataFrame:
    ds = open_dataset(config.ERA5_REPO, config.ERA5_GROUP)
    point = _nearest(ds[list(variables)], lat, lon)
    sub = point.sel(valid_time=slice(np.datetime64(start), np.datetime64(end))).load()
    df = pd.DataFrame(
        {v: np.asarray(sub[v].values).ravel() for v in variables},
        index=pd.to_datetime(sub.valid_time.values),
    )
    return df.sort_index()


def _era5_hourly_edr(lat, lon, start, end, variables) -> pd.DataFrame:
    """Flux EDR ``position`` query -> CoverageJSON -> hourly DataFrame.

    See :mod:`world_cup_climate.edr` for the HTTP client.
    """
    from . import edr

    return edr.position_timeseries(
        service_url=config.ERA5_EDR_SERVICE_URL,
        repo=config.ERA5_REPO,
        ref=config.BRANCH,
        group=config.ERA5_GROUP,
        lat=lat, lon=lon, start=start, end=end,
        variables=variables, token=_token(),
    )


# --------------------------------------------------------------------------- #
# Forecast — raw hourly point series (de-accumulated)
# --------------------------------------------------------------------------- #
def _open_forecast() -> xr.Dataset:
    ds = open_dataset(config.FORECAST_REPO, config.FORECAST_GROUP)
    rename = {k: v for k, v in config.FORECAST_RENAME.items() if k in ds.variables}
    return ds.rename(rename)


def forecast_hourly_point(
    lat: float, lon: float, start: str, end: str,
    variables: tuple[str, ...] = config.VARIABLES,
) -> pd.DataFrame:
    """Raw hourly forecast at a point, accumulations de-accumulated to per-hour.

    Uses the most recent run starting on/before ``start`` so accumulated fields
    share one accumulation origin; reads only the in-window steps.
    """
    ds = _open_forecast()
    init_times = pd.to_datetime(ds.time.values)
    steps = pd.to_timedelta(ds.step.values)
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

    eligible = np.where(init_times <= start_ts)[0]
    i0 = int(eligible[-1]) if len(eligible) else 0
    init = init_times[i0]

    valid = init + steps
    in_window = (valid >= start_ts) & (valid <= end_ts + pd.Timedelta(days=1))
    step_idx = np.where(in_window)[0]
    if len(step_idx) and step_idx[0] > 0:  # keep one lead-in step for diff()
        step_idx = np.insert(step_idx, 0, step_idx[0] - 1)
    if len(step_idx) == 0:
        return pd.DataFrame(columns=list(variables))

    sub = _nearest(ds[list(variables)], lat, lon).isel(time=i0, step=step_idx).load()
    idx = pd.to_datetime((init + steps[step_idx]).values)
    raw = pd.DataFrame(
        {v: np.asarray(sub[v].values).ravel() for v in variables}, index=idx
    ).sort_index()

    for var in variables:
        if var in config.ACCUMULATED:
            raw[var] = raw[var].diff().clip(lower=0)  # per-hour increment
    return raw.loc[(raw.index >= start_ts) & (raw.index <= end_ts + pd.Timedelta(days=1))]


def forecast_init_times() -> pd.DatetimeIndex:
    return pd.to_datetime(_open_forecast().time.values)
