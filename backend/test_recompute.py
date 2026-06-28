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
from world_cup_climate.ifs import _latest_init_idx, _PROBE_LATLON


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


def test_build_match_placeholder_team_is_venue_only():
    """A knockout placeholder team (no capital) yields a venue-only doc:
    the venue series + kickoff stats stay, but that team's series and stats
    are omitted rather than faked."""
    m = Match("2026-07-04", "2026-07-04T17:00:00Z", "Round of 16",
              "South Africa/Canada", "Netherlands/Morocco", "nrg_stadium")
    doc = build_match(m, synth_series)
    assert set(doc["series"]) == {"time", "venue"}      # no team_a/team_b series
    assert doc["stats"] == {}                            # no home comparison
    assert isinstance(doc["t2m_at_kickoff"], float)      # venue numbers still there
    n = len(doc["series"]["time"])
    for k in VARIABLES:
        assert len(doc["series"]["venue"][k]) == n


def test_build_match_beyond_horizon_emits_null_not_nan():
    """A match past the forecast horizon (all-NaN series) must serialise the
    kickoff numbers as JSON null, never a bare NaN token (which breaks the
    browser's JSON.parse)."""
    import json

    def nan_series(place, times):
        return {k: np.full(len(times), np.nan) for k in VARIABLES}

    m = Match("2026-07-19", "2026-07-19T19:00:00Z", "Final",
              "Winner SF1", "Winner SF2", "metlife")
    doc = build_match(m, nan_series)
    assert doc["t2m_at_kickoff"] is None
    assert doc["heat_index_at_kickoff"] is None
    # strict parse (no NaN/Infinity) must succeed, like JSON.parse in the browser
    json.loads(
        json.dumps(doc),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NaN not allowed")),
    )


def test_build_match_winner_slot_is_venue_only():
    """Quarter-final-onward slots ("Winner R16-1", "Loser SF1") have no capital
    either, so they also render venue-only."""
    m = Match("2026-07-19", "2026-07-19T19:00:00Z", "Final",
              "Winner SF1", "Winner SF2", "metlife")
    doc = build_match(m, synth_series)
    assert set(doc["series"]) == {"time", "venue"}
    assert doc["stats"] == {}


def test_build_match_one_placeholder_one_real():
    """If only one side is a placeholder, keep the resolvable side's series/stats."""
    m = Match("2026-07-04", "2026-07-04T17:00:00Z", "Round of 16",
              "Mexico", "England/DR Congo", "estadio_azteca")
    doc = build_match(m, synth_series)
    assert "team_a" in doc["series"] and "team_b" not in doc["series"]
    assert set(doc["stats"]) == {"team_a"}


def test_latest_init_idx_takes_newest_written_any_cycle():
    """Pick the newest init that's written, regardless of cycle hour.

    The 18z run is a short run (no 15-day step) but its step-0 is written, so it
    wins. An init announced on the axis but not yet written (step-0 NaN) is skipped.
    """
    times = pd.to_datetime([
        "2026-06-16T00", "2026-06-16T12", "2026-06-16T18", "2026-06-17T00",
    ])
    lat, lon = _PROBE_LATLON
    t2m = np.full((4, 2, 1, 1), 290.0)  # (time, step, lat, lon)
    t2m[2, -1] = np.nan   # 18z short run: 15-day step missing, but step-0 is fine
    t2m[3, :] = np.nan    # 00z next day announced but not written yet
    ds = xr.Dataset(
        {"2t": (("time", "step", "latitude", "longitude"), t2m)},
        coords={"time": times, "step": [0, 360], "latitude": [lat], "longitude": [lon]},
    )
    assert _latest_init_idx(ds) == 2  # newest written init = the short 18z run


def test_series_reindex_does_not_extrapolate_short_run():
    """A short run's series must not flat-line a fake tail past its last step.

    Mirrors make_ifs_series_fn's reindex+interpolate: gaps between observations
    fill, but trailing hours past the data horizon stay NaN.
    """
    df = pd.DataFrame(
        {"t2m_c": [20.0, np.nan, 22.0]},
        index=pd.to_datetime(["2026-06-20T14", "2026-06-20T15", "2026-06-20T16"]),
    )
    times = pd.date_range("2026-06-20T14", "2026-06-20T20", freq="1h")
    out = df.reindex(times).interpolate("time", limit_area="inside")["t2m_c"]
    assert out.loc["2026-06-20T15"] == 21.0          # interior gap filled
    assert out.loc["2026-06-20T17":].isna().all()    # tail past horizon stays NaN


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
