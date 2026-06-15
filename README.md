# ⚽ World Cup Climate

A small web app that, for a World Cup match **happening today**, compares the
match-day climate three ways:

1. **Venue, now** — the stadium's current 30-day window.
2. **Capitals, now** — the two competing nations' **capital cities**, current window.
3. **Capitals, climatology** — the same calendar window averaged over the **last 10 years**.

It looks at sports-relevant variables: **2 m temperature** (`t2m`), **2 m
dewpoint** (`d2m`, → relative humidity), **total precipitation** (`tp`), and
**surface solar radiation** (`ssrd`). Everything is the daily aggregate over the
30 days before kickoff.

## Data

All data lives on [Arraylake](https://earthmover.io) and is read live (with a
small on-disk cache of point series):

| role | repo | group | grid | notes |
|---|---|---|---|---|
| reanalysis (history) | `earthmover-public/era5-private` | `single/temporal` | 0.25° | hourly since 1940; ~6-day latency; chunked for point time series |
| forecast (recent + ahead) | `spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription` | root | 0.1° | `(init, step)`; bridges the ERA5 latency gap and looks ahead |

The current 30-day window is **ERA5 reanalysis up to its ~6-day-old cutoff,
spliced with the ECMWF IFS forecast** for the most recent days (and any days
ahead of "today").

### Which Flux service? → EDR

Of the deployed Flux compute services (`edr`, `tiles`, `wms`, `dap2`), the
**EDR** service (OGC *Environmental Data Retrieval*) is the right one for a web
app that needs *"the values at this lat/lon over this time range"*: a `position`
query returns a compact point time series as CoverageJSON, with no Zarr chunk
reads on the client. ERA5 point series use the public EDR deployment
(`edr-bf7f8f8c`) on `earthmover-public`; `tiles`/`wms` are for map rasters and
`dap2` (OPeNDAP) is heavier and array-oriented.

> The `spring-data` forecast repo has **no Flux service deployed**, so the
> forecast bridge uses the Arraylake Python client (reading only the in-window
> steps). Deploy an EDR service on `spring-data` to move that path to HTTP too.

## Timing

ERA5 and the IFS forecast are in **UTC**. To stay robust to "which local hour"
you'd otherwise sample, every variable is aggregated over the whole **UTC
calendar day**: a daily **mean** for instantaneous fields (`t2m`, `d2m`) and a
daily **total** for accumulations (`tp`, `ssrd`).

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) (Python ≥ 3.12 is fetched automatically).

```bash
uv sync                       # install
```

### Offline / demo (no token)

A synthetic provider mimics the *raw hourly* returns from Arraylake — including
a realistic diurnal cycle — so the whole app and notebook run with no token or
network:

```bash
WCC_DATA_SOURCE=fake uv run world-cup-climate
# open http://127.0.0.1:8000
```

### Live data

```bash
export ARRAYLAKE_TOKEN=ema_...        # from https://app.earthmover.io
WCC_DATA_SOURCE=live uv run world-cup-climate
```

(Requires outbound access to `api.earthmover.io` and `compute.earthmover.io`.)

### Demo notebook

```bash
WCC_DATA_SOURCE=fake uv run --extra demo jupyter lab notebooks/demo.ipynb
```

`notebooks/demo.ipynb` walks through raw hourly data → daily aggregation →
ERA5/forecast splice → 10-year climatology → the three-way match comparison.

## Architecture

```
src/world_cup_climate/
  config.py        datasets, variables, window/climatology constants
  arraylake_io.py  real raw-hourly access (ERA5 via EDR/xarray, forecast via xarray)
  edr.py           OGC EDR position-query HTTP client (CoverageJSON -> DataFrame)
  providers.py     raw-hourly dispatch + synthetic provider + daily aggregation + cache
  climate.py       window logic, climatology, derived vars, match report
  fixtures.py      hardcoded fixtures + capital lookup
  app.py           FastAPI backend + static SPA
  static/          index.html, app.js (Chart.js), style.css
data/fixtures.json World Cup fixtures + capital coordinates (edit freely)
notebooks/demo.ipynb
tests/             offline pipeline tests
```

### HTTP API

| endpoint | description |
|---|---|
| `GET /api/health` | token / dataset reachability + active data source |
| `GET /api/matches` | fixtures for the active match day (today, else next) |
| `GET /api/report/{idx}` | full three-way climate report for one fixture |

## Configuration (env vars)

| var | default | meaning |
|---|---|---|
| `ARRAYLAKE_TOKEN` | – | Arraylake API token (`ema_...`), required for live data |
| `WCC_DATA_SOURCE` | `live` | `live` or `fake` |
| `WCC_ERA5_VIA` | `edr` | ERA5 path: `edr` or `xarray` |
| `WCC_TODAY` | system date | pin "today" for reproducible demos |
| `WCC_HOST` / `WCC_PORT` | `127.0.0.1` / `8000` | server bind |
| `WCC_CACHE_DIR` | `./cache` | point-series cache directory |

## Tests

```bash
uv run --extra dev pytest
```

## Notes & caveats

- Fixtures in `data/fixtures.json` are the **real** World Cup 2026 fixtures for
  2026-06-15 (verified from FOX Sports / ESPN / Al Jazeera / Ticketmaster). Add
  more match days as needed, or wire up a fixtures API.
- City climate is sampled at the **nearest grid cell**.
- The synthetic provider is for development/demo only; it is *not* a forecast.
