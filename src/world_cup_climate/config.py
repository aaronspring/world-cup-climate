"""Static configuration: dataset locations, variables, and tunable constants.

Two Arraylake repos back the app:

* **Historical reanalysis** — ``earthmover-public/era5-private`` group
  ``single/temporal``. Hourly ERA5 back to 1940 on a 0.25 degree grid, chunked
  ``[8736, 12, 12]`` (i.e. optimised for pulling long time series at a point).
  Latency is ~6 days, so it covers everything up to "now minus 6 days".

* **Forecast** — ``spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription``.
  ECMWF IFS HRES on a 0.1 degree grid with ``(time=init, step=lead)`` dims. Used
  to bridge the ERA5 latency gap (the last ~6 days up to today) and to look ahead.
"""

from __future__ import annotations

# --- Arraylake repositories ------------------------------------------------
ERA5_REPO = "earthmover-public/era5-private"
ERA5_GROUP = "single/temporal"  # point-time-series optimised chunking

FORECAST_REPO = "spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription"
FORECAST_GROUP = ""  # variables live at the root group

BRANCH = "main"

# Flux EDR (OGC Environmental Data Retrieval) service for the earthmover-public
# org — the recommended endpoint for point time-series in a web app. Override
# with WCC_ERA5_EDR_URL if the deployment changes.
import os as _os

ERA5_EDR_SERVICE_URL = _os.environ.get(
    "WCC_ERA5_EDR_URL",
    "https://compute.earthmover.io/v1/services/edr/earthmover-public",
)

# --- Variables -------------------------------------------------------------
# Canonical names used throughout the app. ERA5 already uses these names; the
# IFS forecast uses ECMWF short names, mapped below.
VARIABLES = ("t2m", "d2m", "tp", "ssrd")

# forecast short name -> canonical name
FORECAST_RENAME = {"2t": "t2m", "2d": "d2m", "tp": "tp", "ssrd": "ssrd"}

# Which variables are instantaneous (state) vs accumulated-from-forecast-start.
# Matters for de-accumulating the IFS forecast and for daily aggregation.
INSTANTANEOUS = ("t2m", "d2m")
ACCUMULATED = ("tp", "ssrd")

# Human-facing metadata for each canonical variable, including the display unit
# and how to aggregate hourly data to a daily value.
VARIABLE_META = {
    "t2m": {
        "label": "Temperature",
        "display_unit": "°C",
        "daily_agg": "mean",  # also expose max/min separately
        "icon": "thermometer",
    },
    "d2m": {
        "label": "Dewpoint",
        "display_unit": "°C",
        "daily_agg": "mean",
        "icon": "droplet",
    },
    "tp": {
        "label": "Precipitation",
        "display_unit": "mm/day",
        "daily_agg": "sum",
        "icon": "cloud-rain",
    },
    "ssrd": {
        "label": "Solar radiation",
        "display_unit": "kWh/m²/day",
        "daily_agg": "sum",
        "icon": "sun",
    },
    # Derived (not fetched directly):
    "rh": {
        "label": "Relative humidity",
        "display_unit": "%",
        "daily_agg": "mean",
        "icon": "droplets",
    },
}

# --- Timing ----------------------------------------------------------------
# ERA5 (and the IFS forecast) are in UTC. To stay robust to "which hour of the
# local day" you'd otherwise sample, every variable is aggregated over the full
# UTC calendar day: a daily MEAN for instantaneous fields (t2m, d2m) and a daily
# TOTAL for accumulations (tp, ssrd, which are inherently per-day quantities).
TIMEZONE = "UTC"

# --- Analysis window -------------------------------------------------------
WINDOW_DAYS = 30          # "30 days ... before the matchday"
CLIMATOLOGY_YEARS = 10    # "historical climate ... over the last 10 years"

# ERA5 publication latency (days). Anything more recent than this is filled
# from the IFS forecast. Discovered dynamically at runtime, but used as a hint.
ERA5_LATENCY_DAYS = 6

# --- Cache -----------------------------------------------------------------
import os
from pathlib import Path

CACHE_DIR = Path(os.environ.get("WCC_CACHE_DIR", Path(__file__).resolve().parents[2] / "cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
