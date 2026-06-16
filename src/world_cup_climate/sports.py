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
