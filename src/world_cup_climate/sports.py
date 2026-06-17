"""Sports-relevant derived variables and daily aggregation.

Raw ERA5/IFS units:
  t2m, d2m : kelvin (instantaneous)
  tp       : metres (accumulation)
  ssrd     : J m-2 (accumulation)

We convert to athlete-friendly units and add a suite of heat-stress and
thermal-comfort indices. Three indices are computed via xclim:
  - humidex          xclim.indices.humidex
  - wind_chill       xclim.indices.wind_chill_index
  - utci             xclim.indices.universal_thermal_climate_index

WBGT is implemented here directly (simplified Liljegren/Stull method) because
xclim ≤0.61 does not expose wet_bulb_globe_temperature as a standalone index.
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


# ---------------------------------------------------------------------------
# xclim-based indices
# ---------------------------------------------------------------------------

def _da(arr, units: str):
    """Wrap a numpy array as an xarray DataArray with CF units for xclim."""
    import xarray as xr
    return xr.DataArray(np.asarray(arr, dtype=float), attrs={"units": units})


def humidex_celsius(t2m_c, d2m_c):
    """Humidex (°C) via xclim.indices.humidex — Environment Canada's heat-stress index.

    Above 40 is dangerous for physical exertion; above 45, all exercise should stop.
    """
    from xclim.indices import humidex
    return np.asarray(humidex(_da(t2m_c, "degC"), _da(d2m_c, "degC")))


def wind_chill_celsius(t2m_c, wind_speed_ms):
    """Wind chill (°C) via xclim.indices.wind_chill_index (Environment Canada formula).

    Returns NaN where conditions are outside validity range (T > 0°C or calm wind).
    """
    from xclim.indices import wind_chill_index
    return np.asarray(
        wind_chill_index(_da(t2m_c, "degC"), _da(wind_speed_ms, "m s-1"))
    )


def _estimate_mrt(t2m_c, wind_speed_ms, ssrd_wm2=None):
    """Approximate mean radiant temperature (°C) from solar radiation and wind.

    When no solar data are available (nighttime or analysis period) MRT equals
    T_air (shade assumption). During daytime, solar load heats the globe above
    air temperature; wind cools it. Simplified formula following Malchaire et al.
    (2001) and scaled for a standard 150 mm black globe:
      ΔTg ≈ 17.5 * (ssrd/1000) - 2.5 * sqrt(V)   [°C above air temp]
    """
    if ssrd_wm2 is None:
        return t2m_c.copy() if hasattr(t2m_c, "copy") else np.array(t2m_c)
    solar = np.clip(np.asarray(ssrd_wm2, dtype=float), 0, None)
    wind = np.maximum(np.asarray(wind_speed_ms, dtype=float), 0.1)
    delta = 17.5 * (solar / 1000.0) - 2.5 * np.sqrt(wind)
    return np.asarray(t2m_c, dtype=float) + np.maximum(delta, 0.0)


def utci_celsius(t2m_c, rh, wind_speed_ms, ssrd_wm2=None):
    """Universal Thermal Climate Index (°C) via xclim.indices.universal_thermal_climate_index.

    The IOC-endorsed gold standard for outdoor thermal stress. Combines dry-bulb
    temperature, humidity, wind, and mean radiant temperature (MRT). When ssrd is
    available, MRT is estimated from solar load and wind; otherwise shade is assumed.
    """
    from xclim.indices import universal_thermal_climate_index
    mrt_c = _estimate_mrt(t2m_c, wind_speed_ms, ssrd_wm2)
    return np.asarray(
        universal_thermal_climate_index(
            _da(t2m_c, "degC"),
            _da(rh, "%"),
            _da(wind_speed_ms, "m s-1"),
            mrt=_da(mrt_c, "degC"),
        )
    )


# ---------------------------------------------------------------------------
# WBGT — manual implementation (not yet in xclim ≤0.61)
# ---------------------------------------------------------------------------

def wbgt_celsius(t2m_c, rh, wind_speed_ms, ssrd_wm2=None):
    """Outdoor Wet Bulb Globe Temperature (°C).

    WBGT = 0.7·NWB + 0.2·GT + 0.1·DBT  (ISO 7243 / Yaglou & Minard 1957)

    NWB estimated via Stull (2011); GT estimated via Malchaire et al. (2001).
    Accurate to roughly ±1°C under typical summer conditions.

    FIFA cooling-break protocol:
      < 28°C  normal play
      28–32°C cooling/water breaks may be authorised
      > 32°C  breaks mandatory under IFAB laws
    """
    t2m = np.asarray(t2m_c, dtype=float)
    rh_ = np.asarray(rh, dtype=float)

    # Natural wet-bulb temperature: Stull (2011), accurate to ±0.65°C for RH 5–99%.
    tw = (
        t2m * np.arctan(0.151977 * (rh_ + 8.313659) ** 0.5)
        + np.arctan(t2m + rh_)
        - np.arctan(rh_ - 1.676331)
        + 0.00391838 * rh_ ** 1.5 * np.arctan(0.023101 * rh_)
        - 4.686035
    )

    # Globe temperature: solar heats globe, wind cools it.
    # When ssrd is unavailable (night / analysis period), globe ≈ air temp + 2°C.
    if ssrd_wm2 is not None:
        solar = np.clip(np.asarray(ssrd_wm2, dtype=float), 0, None)
        wind = np.maximum(np.asarray(wind_speed_ms, dtype=float), 0.1)
        tg = t2m + 17.5 * (solar / 1000.0) - 2.5 * np.sqrt(wind)
        tg = np.clip(tg, t2m, t2m + 30.0)
    else:
        tg = t2m + 2.0

    return 0.7 * tw + 0.2 * tg + 0.1 * t2m
