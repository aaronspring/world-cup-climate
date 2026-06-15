"""Point time-series extraction from the ERA5 store."""

from __future__ import annotations

import pandas as pd

from .client import era5_dataset
from .config import VARIABLES
from .sports import kelvin_to_celsius


def era5_point(lat: float, lon: float, start, end) -> pd.DataFrame:
    """Hourly ERA5 at the nearest grid point, converted to canonical columns.

    Returns a dataframe indexed by valid_time with columns (subset of):
      t2m_c, d2m_c [degC], tp_mm [mm in that hour], ssrd_wm2 [mean W/m2 that hour].
    ERA5 single-level accumulations are per-hour increments, so tp/ssrd map
    directly onto each hour with no deaccumulation.
    """
    ds = era5_dataset()
    src = [VARIABLES[v]["era5"] for v in VARIABLES]
    point = (
        ds[src]
        .sel(latitude=lat, longitude=lon % 360, method="nearest")
        .sel(valid_time=slice(pd.Timestamp(start), pd.Timestamp(end)))
        .load()
    )
    df = point.to_dataframe()[src]
    df.index = pd.DatetimeIndex(point["valid_time"].values, name="valid_time")

    out = pd.DataFrame(index=df.index)
    out["t2m_c"] = kelvin_to_celsius(df["t2m"])
    out["d2m_c"] = kelvin_to_celsius(df["d2m"])
    out["tp_mm"] = df["tp"] * 1000.0           # m -> mm (per hour)
    out["ssrd_wm2"] = df["ssrd"] / 3600.0      # J/m2 over the hour -> mean W/m2
    return out
