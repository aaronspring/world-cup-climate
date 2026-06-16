"""Minimal self-checks: `uv run python backend/test_recompute.py`.

No framework — just asserts on the non-trivial bits (the smooth climate field, the
stats math, the JSON shape).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from world_cup_climate.locations import Place
from recompute import build_match, synth_series, utc_offset_hours, VARIABLES
from world_cup_climate.fixtures import Match
from world_cup_climate.ifs import _latest_long_idx, _PROBE_LATLON


def _place(lat: float, lon: float) -> Place:
    return Place(name="x", label="Match venue — x", country="x", lat=lat, lon=lon)


def test_colocated_points_have_near_zero_delta():
    """A stadium and its own capital (a few km apart) must read ~same climate."""
    times = pd.date_range("2026-06-15", periods=48, freq="1h")
    a = synth_series(_place(33.75, -84.40), times)["t2m"]
    b = synth_series(_place(33.76, -84.39), times)["t2m"]
    assert np.max(np.abs(a - b)) < 0.5, np.max(np.abs(a - b))


def test_seasonal_sign():
    """June: NH subtropics hot, SH winter cold."""
    times = pd.date_range("2026-06-15", periods=24, freq="1h")
    nh = synth_series(_place(30, 0), times)["t2m"].mean()
    sh = synth_series(_place(-30, 0), times)["t2m"].mean()
    assert nh > sh + 5, (nh, sh)


def test_offset():
    assert utc_offset_hours(0) == 0
    assert utc_offset_hours(-84) == -6   # US east, solar estimate
    assert utc_offset_hours(135) == 9    # Japan-ish


def test_build_match_shape():
    m = Match("2026-06-15", "2026-06-15T19:00:00Z", "Group X",
              "Mexico", "South Africa", "estadio_azteca")
    doc = build_match(m, synth_series)
    n = len(doc["series"]["time"])
    for who in ("venue", "team_a", "team_b"):
        for k in VARIABLES:
            assert len(doc["series"][who][k]) == n, (who, k)
    assert set(doc["stats"]["team_a"]) >= {"home", "tz_diff_h", "d_t2m", "d_heat_index"}
    # kickoff falls inside the series window
    assert doc["window"]["start"] <= doc["kickoff_utc"].replace("Z", "") <= doc["window"]["end"]


def test_latest_long_idx_skips_short_and_unwritten_inits():
    """Pick the latest 00z/12z init whose longest step is actually populated."""
    times = pd.to_datetime([
        "2026-06-16T00", "2026-06-16T06", "2026-06-16T12",  # 12z = newest long run
    ])
    lat, lon = _PROBE_LATLON
    t2m = np.full((3, 2, 1, 1), 290.0)  # (time, step, lat, lon)
    t2m[1, -1] = np.nan   # 06z is a short run -> no 15-day step (excluded by hour anyway)
    t2m[2, -1] = np.nan   # 12z announced but its 15-day step isn't written yet
    ds = xr.Dataset(
        {"2t": (("time", "step", "latitude", "longitude"), t2m)},
        coords={"time": times, "step": [0, 360], "latitude": [lat], "longitude": [lon]},
    )
    assert _latest_long_idx(ds) == 0  # falls back to the complete 00z run


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
