"""Shared configuration for world-cup-climate."""

from __future__ import annotations

from pathlib import Path

# Repo paths
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parents[1]
DATA_DIR = PROJECT_DIR / "data"

# Arraylake repositories
ERA5_REPO = "earthmover-public/era5-private"
ERA5_GROUP = "single/temporal"  # chunked long-in-time -> cheap point time series
FORECAST_REPO = "spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription"
# Open IFS forecast with proper CF coordinates (real lat/lon, time=init, step=timedelta).
# This is what the simplified app uses (IFS only, no ERA5).
IFS_OPEN_REPO = "spring-data/ecwmf-ifs-15-days-forecast-open"

# Forecast init cadence (verified from commit history: 00/06/12/18 UTC cycles)
FORECAST_INIT_FREQ_HOURS = 6

# Canonical sports-relevant variables, with the per-dataset source names.
# era5: name in earthmover-public/era5-private  single/*
# fc  : name in the ECMWF IFS forecast repo
# accum: True for fluxes accumulated over time (precip, radiation)
VARIABLES = {
    "t2m": {"era5": "t2m", "fc": "2t", "accum": False, "label": "2 m air temperature", "unit": "degC"},
    "d2m": {"era5": "d2m", "fc": "2d", "accum": False, "label": "2 m dewpoint", "unit": "degC"},
    "tp": {"era5": "tp", "fc": "tp", "accum": True, "label": "Total precipitation", "unit": "mm/day"},
    "ssrd": {"era5": "ssrd", "fc": "ssrd", "accum": True, "label": "Surface solar radiation", "unit": "W/m2"},
}

# Analysis window
WINDOW_DAYS = 30          # 30-day window ending on matchday
N_HISTORICAL_YEARS = 10   # climatology over the last N years
FORECAST_STEP_STRIDE = 3  # subsample forecast steps (hours) to keep point reads cheap
