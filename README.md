# world-cup-climate

[![Deploy to GitHub Pages](https://github.com/aaronspring/world-cup-climate/actions/workflows/pages.yml/badge.svg)](https://github.com/aaronspring/world-cup-climate/actions/workflows/pages.yml)

For a World Cup 2026 match **today**, compare the climate at the **match venue** with the
climate in **each competing country's capital** — temperature and how hot it *feels*
(heat index) — for the days around the match.

Data:
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

## Web app (React + MapLibre)

A static single-page app: a date-pickable map of the host cities with a
temperature-colored pin per match. Click a pin (or a match in the list) for a glass
card with venue-vs-home comparison stats and per-variable forecast charts. See
`docs/ARCHITECTURE.md`.

```bash
# 1. generate the per-match JSON the frontend reads (writes frontend/public/data/)
uv run python backend/recompute.py            # --source demo (default, no auth)
uv run python backend/recompute.py --source ifs   # real IFS t2m/d2m (needs Arraylake auth)

# 2. run the frontend
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The committed `frontend/public/data/` is demo data, so `npm run dev` works without
running the backend first. `--source demo` is a physically plausible synthetic
forecast (smooth lat/lon climate field + diurnal cycle); swap in full server-side IFS
extraction for live data. The map basemap uses public CARTO tiles (no token).

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
