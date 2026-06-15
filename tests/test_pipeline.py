"""Offline tests for the climate pipeline using the synthetic provider."""

import datetime as dt
import os

os.environ["WCC_DATA_SOURCE"] = "fake"

import pandas as pd
import pytest

from world_cup_climate import climate, config, fixtures, providers

MATCHDAY = dt.date(2026, 6, 15)
MEXICO_CITY = (19.4326, -99.1332)


def test_fake_hourly_has_diurnal_cycle():
    hourly = providers.fake_hourly_point(*MEXICO_CITY, "2026-06-01", "2026-06-03")
    assert len(hourly) == 24 * 3
    # ssrd is zero at night and positive by day -> a real diurnal swing
    assert hourly["ssrd"].min() == 0
    assert hourly["ssrd"].max() > 0
    # daytime temperature exceeds night-time temperature on average
    by_hour = (hourly["t2m"]).groupby(hourly.index.hour).mean()
    assert by_hour.max() - by_hour.min() > 2.0  # > 2 K diurnal range


def test_daily_aggregation_rules():
    daily = providers.daily_point("era5", *MEXICO_CITY, "2026-06-01", "2026-06-05")
    assert list(daily.index) == list(pd.date_range("2026-06-01", "2026-06-05", freq="1D"))
    assert set(config.VARIABLES) <= set(daily.columns)
    # precipitation aggregates as a non-negative daily total
    assert (daily["tp"] >= 0).all()


def test_current_series_splices_era5_and_forecast():
    cur = climate.current_series(*MEXICO_CITY, MATCHDAY)
    assert len(cur) == config.WINDOW_DAYS
    assert {"era5", "forecast"} == set(cur["source"].unique())
    # forecast only covers the tail (after the ERA5 cutoff)
    cutoff = pd.Timestamp(providers.era5_cutoff(MATCHDAY))
    assert (cur.loc[cur["source"] == "era5"].index <= cutoff).all()
    assert (cur.loc[cur["source"] == "forecast"].index > cutoff).all()


def test_climatology_shape_and_spread():
    clim = climate.climatology(*MEXICO_CITY, MATCHDAY)
    assert list(clim.index) == list(range(-(config.WINDOW_DAYS - 1), 1))
    for var in ("t2m", "tp", "ssrd"):
        assert (clim[f"{var}_p90"] >= clim[f"{var}_p10"]).all()


def test_build_match_report_contract():
    match = fixtures.matches_on(MATCHDAY)[0]
    rep = climate.build_match_report(match)
    assert rep["window"]["days"] == config.WINDOW_DAYS
    for side in ("home", "away"):
        block = rep["capitals"][side]
        assert len(block["current"]["dates"]) == config.WINDOW_DAYS
        assert "climatology" in block and "summary" in block
        assert "anomaly" in block["summary"]["t2m"]
    # venue has a current series but no climatology
    assert "climatology" not in rep["venue"]


def test_relative_humidity_bounds():
    rh = climate.relative_humidity(pd.Series([300.0]), pd.Series([295.0]))
    assert 0 <= rh.iloc[0] <= 100
