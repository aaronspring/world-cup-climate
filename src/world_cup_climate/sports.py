"""Sports-relevant derived variables and daily aggregation.

Raw ERA5/IFS units:
  t2m, d2m : kelvin (instantaneous)
  tp       : metres (accumulation)
  ssrd     : J m-2 (accumulation)

We convert to athlete-friendly units and add relative humidity + heat index, which
together drive heat-stress risk for players.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def kelvin_to_celsius(k):
    return k - 273.15


def relative_humidity(t2m_c, d2m_c):
    """RH (%) from temperature and dewpoint in degC (Magnus formula)."""
    a, b = 17.625, 243.04
    e_d = np.exp((a * d2m_c) / (b + d2m_c))
    e_t = np.exp((a * t2m_c) / (b + t2m_c))
    return np.clip(100.0 * e_d / e_t, 0, 100)


def heat_index_celsius(t2m_c, rh):
    """NOAA heat index ("feels like") in degC from temp (degC) and RH (%).

    Uses the Rothfusz regression (valid for warm conditions); below ~26.7degC it
    falls back to the simple formula, so cool values stay close to air temperature.
    """
    t_f = t2m_c * 9 / 5 + 32
    # Simple formula (Steadman) — used for cooler conditions / as the low branch.
    hi_simple = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    # Rothfusz regression for hot conditions.
    hi_full = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 6.83783e-3 * t_f**2
        - 5.481717e-2 * rh**2
        + 1.22874e-3 * t_f**2 * rh
        + 8.5282e-4 * t_f * rh**2
        - 1.99e-6 * t_f**2 * rh**2
    )
    hi_f = np.where((hi_simple + t_f) / 2 >= 80.0, hi_full, hi_simple)
    return (np.asarray(hi_f) - 32) * 5 / 9


# Daily aggregation rule per canonical variable.
# instantaneous temps -> mean & max; accumulated fluxes -> daily total.
def aggregate_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate an hourly point dataframe (columns = canonical vars in SI-ish units
    already converted) to daily, adding derived comfort variables.

    Expected input columns (any subset): t2m_c, d2m_c, tp_mm, ssrd_wm2.
    `tp_mm` and `ssrd_wm2` must already be per-timestep increments (deaccumulated),
    expressed as mm and W/m2 respectively for each row's interval.
    """
    g = hourly.resample("1D")
    out = pd.DataFrame(index=g.mean().index)

    if "t2m_c" in hourly:
        out["t2m_mean"] = g["t2m_c"].mean()
        out["t2m_max"] = g["t2m_c"].max()
        out["t2m_min"] = g["t2m_c"].min()
    if "d2m_c" in hourly:
        out["d2m_mean"] = g["d2m_c"].mean()
    if {"t2m_c", "d2m_c"} <= set(hourly.columns):
        rh = pd.Series(
            relative_humidity(hourly["t2m_c"], hourly["d2m_c"]), index=hourly.index
        )
        hi = pd.Series(
            heat_index_celsius(hourly["t2m_c"], rh), index=hourly.index
        )
        out["rh_mean"] = rh.resample("1D").mean()
        # peak feels-like is the sports-relevant heat-stress number
        out["heat_index_max"] = hi.resample("1D").max()
    if "tp_mm" in hourly:
        out["tp_total"] = g["tp_mm"].sum()        # mm/day
    if "ssrd_wm2" in hourly:
        out["ssrd_mean"] = g["ssrd_wm2"].mean()    # W/m2 daily mean

    return out


# Human-readable metadata for the daily aggregated columns.
DAILY_VARS = {
    "t2m_mean": ("Mean temperature", "degC"),
    "t2m_max": ("Max temperature", "degC"),
    "t2m_min": ("Min temperature", "degC"),
    "rh_mean": ("Mean relative humidity", "%"),
    "heat_index_max": ("Peak heat index (feels like)", "degC"),
    "tp_total": ("Daily precipitation", "mm"),
    "ssrd_mean": ("Mean solar radiation", "W/m2"),
}
