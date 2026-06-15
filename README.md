# world-cup-climate

For a World Cup match **today**, compare the climate at the **match venue** with the
climate in **each competing country's capital** — temperature and how hot it *feels*
(heat index) — for the days around the match.

**Simple app = IFS only.** One data source, proper coordinates, no stitching:

- `spring-data/ecwmf-ifs-15-days-forecast-open` (ECMWF IFS-ENS, open) via [Arraylake](https://docs.earthmover.io).
- **Best estimate**: `step="0 days"` across every 6-hourly init → recent conditions up to today.
- **Forecast**: the latest init, steps `0 … 15 days` → the outlook ahead.
- Joined into one continuous line per location.

**Variables (sports-relevant):** `2t` (air temperature) and `2d` (dewpoint) →
relative humidity → **heat index** (player heat stress). Both are instantaneous, so
they are meaningful exactly at `step=0`.

## Setup

```bash
uv sync
uv run arraylake auth login   # once; writes ~/.arraylake/token.json
```

## Use

```python
from world_cup_climate.fixtures import load_matches
from world_cup_climate import viz_ifs

match = load_matches("2026-06-15")[0]
viz_ifs.plot_match(match.places(), col="heat_index_c", matchday=match.date)
```

- `ifs.location_series(lat, lon)` → DataFrame (`t2m_c, d2m_c, rh, heat_index_c, is_forecast`), indexed by `valid_time`.
- `ifs.matchday_value(series, matchday, col)` → daily-max on the matchday.
- Fixtures (`data/fixtures.json`) and locations (`data/locations.json`) are curated for the demo.

## Ideas / next steps

- **Heat index via [`xclim`](https://xclim.readthedocs.io/en/stable/api_indicators.html#xclim.indicators.convert.heat_index)** —
  replace the hand-rolled NOAA Rothfusz formula in `sports.py` with the validated,
  unit-aware `xclim.indicators.convert.heat_index` (xarray-native, CF metadata).
- **ERA5 for historical comparison** — bring back `earthmover-public/era5-private`
  (`single/temporal`) to overlay the **10-year normal** for the same calendar window,
  so today's match reads as an anomaly vs climatology (hotter/cooler than usual). The
  ERA5 + stitching code already exists in `era5.py` / `forecast.py` / `climate.py` /
  `viz.py` from the earlier richer prototype.
- Precip (`tp`) and solar (`ssrd`): accumulated fields, need deaccumulation along step
  (logic already in `forecast.py`); add once the simple temperature view is locked in.
- Swap curated fixtures for a live football fixtures API.
- Frontend: Streamlit app on top of `ifs.location_series` + `viz_ifs.plot_match`.

## Notes on the data stores

- The **open** IFS repo above has clean CF coordinates — preferred for the app.
- The **low-latency** subscription repo
  (`spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription`) ships *bare integer*
  dimensions; decoding it required reverse-engineering (longitude offset by 180°, `step`
  as an index over ECMWF's non-uniform schedule hourly→90h/3-hourly→144h/6-hourly→360h).
  See `client.py` if you ever need that store; the app does not.
- Point reads pull one 900×900 spatial chunk per step (~30 s/location), so results are cached.
