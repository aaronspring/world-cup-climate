"""Point time-series extraction from the ECMWF IFS forecast store.

The store is chunked as (1, 1, 900, 900) over (time, step, lat, lon), so a single
point still reads one full spatial chunk per step. We therefore subsample steps
(`FORECAST_STEP_STRIDE`) and read only as many steps as the requested valid range
needs. Accumulated fields (tp, ssrd) are cumulative from the init time and are
deaccumulated by differencing along step.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .client import fc_grid_index, forecast_dataset
from .config import FORECAST_STEP_STRIDE, VARIABLES
from .sports import kelvin_to_celsius


def init_axis() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(forecast_dataset()["time"].values)


def choose_gap_init(after) -> pd.Timestamp:
    """First init cycle strictly after `after` (used to fill ERA5 -> matchday)."""
    inits = init_axis()
    after = pd.Timestamp(after)
    later = inits[inits > after]
    if len(later) == 0:
        return inits[-1]
    return later[0]


def latest_init() -> pd.Timestamp:
    return init_axis()[-1]


def forecast_point(
    lat: float,
    lon: float,
    init: pd.Timestamp,
    valid_start,
    valid_end,
    stride: int = FORECAST_STEP_STRIDE,
) -> pd.DataFrame:
    """Forecast point series for one init, valid in [valid_start, valid_end].

    Returns a dataframe indexed by valid_time with canonical converted columns:
      t2m_c, d2m_c [degC], tp_mm [mm over the step interval], ssrd_wm2 [mean W/m2].
    """
    ds = forecast_dataset()
    init = pd.Timestamp(init)
    valid_start = pd.Timestamp(valid_start)
    valid_end = pd.Timestamp(valid_end)

    # steps (as timedelta) needed: 0 .. step covering valid_end, subsampled by stride.
    steps = ds["step"].values  # timedelta64
    max_step = valid_end - init
    keep = steps <= (max_step + pd.Timedelta(hours=1))
    idx = np.where(keep)[0]
    if len(idx) == 0:
        raise ValueError(f"init {init} does not cover {valid_end}")
    idx = idx[:: max(stride, 1)]

    li, lo = fc_grid_index(lat, lon)
    src = [VARIABLES[v]["fc"] for v in VARIABLES]
    point = (
        ds[src]
        .sel(time=init)
        .isel(step=idx, latitude=li, longitude=lo)
        .load()
    )

    valid_time = init + pd.to_timedelta(point["step"].values)
    df = point.to_dataframe()[src]
    df.index = pd.DatetimeIndex(valid_time, name="valid_time")
    df = df.sort_index()

    out = pd.DataFrame(index=df.index)
    out["t2m_c"] = kelvin_to_celsius(df[VARIABLES["t2m"]["fc"]])
    out["d2m_c"] = kelvin_to_celsius(df[VARIABLES["d2m"]["fc"]])

    # Deaccumulate cumulative fluxes along step, then convert.
    interval_s = df.index.to_series().diff().dt.total_seconds()
    interval_s.iloc[0] = (df.index[0] - init).total_seconds() or 3600.0

    tp_inc_m = df[VARIABLES["tp"]["fc"]].diff()
    tp_inc_m.iloc[0] = df[VARIABLES["tp"]["fc"]].iloc[0]  # accumulation init -> step0
    out["tp_mm"] = (tp_inc_m.clip(lower=0) * 1000.0).values

    ssrd_inc_j = df[VARIABLES["ssrd"]["fc"]].diff()
    ssrd_inc_j.iloc[0] = df[VARIABLES["ssrd"]["fc"]].iloc[0]
    out["ssrd_wm2"] = (ssrd_inc_j.clip(lower=0).values / interval_s.values)

    return out.loc[(out.index >= valid_start) & (out.index <= valid_end)]
