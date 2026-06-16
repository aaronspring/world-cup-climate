"""Shared configuration for world-cup-climate."""

from __future__ import annotations

from pathlib import Path

# Repo paths
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parents[1]
DATA_DIR = PROJECT_DIR / "data"

# Open IFS forecast with proper CF coordinates (real lat/lon, time=init, step=timedelta).
IFS_OPEN_REPO = "spring-data/ecwmf-ifs-15-days-forecast-open"
