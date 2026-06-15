# world-cup-climate

Goal: for a World Cup match **today**, compare the climate at the **match venue** with
the climate in **each competing country's capital** temperature and how hot it *feels*
(heat index) for the days around the match.

Data source: **ECMWF IFS-ENS open** (`spring-data/ecwmf-ifs-15-days-forecast-open`) via
[Arraylake](https://docs.earthmover.io) managed Icechunk. One source, clean CF
coordinates, no stitching.

- **Best estimate**: `step="0 days"` across every 6 hourly init, giving recent
  conditions up to today.
- **Forecast**: the latest init, steps `0 ... 15 days`, the outlook ahead.
- Joined into one continuous line per location.

Variables: `2t` (air temperature) and `2d` (dewpoint), combined into relative humidity
and a **heat index** (player heat stress). Both are instantaneous, so they are
meaningful exactly at `step=0`.

## Context Requirements
- Read `README.md` at the start of each session for setup and high-level navigation
  (`AGENTS.md` is loaded automatically).

## Development flow
- Ensure that important changes in setup and architecture are reflected in this
  `AGENTS.md` and, if needed, in the `README.md` which holds setup and usage
  instructions.
- The `README.md` "Ideas / next steps" section is the backlog (xclim heat index, ERA5
  10 year normal overlay, precip/solar deaccumulation, live fixtures API, Streamlit
  frontend). Update it when scope changes.

## Writing
- avoid `-` or `--`

## Package management
- `uv add package` & `uv sync`, no pip commands
- run a python script: `uv run python script.py`

## Data access
- Arraylake auth once: `uv run arraylake auth login` (writes `~/.arraylake/token.json`).
  For headless/CI set `ARRAYLAKE_TOKEN=ema_...` (see `.env.example`).
- Open an Icechunk group: `xr.open_zarr(session.store, group=..., consolidated=False, chunks={})`.
- Point reads pull one 900x900 spatial chunk per step (~30 s/location), so results are
  cached. Prefer the open repo with clean CF coordinates for the app.
- The **low-latency subscription** repo
  (`spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription`) ships *bare
  integer* dimensions (longitude offset by 180 degrees, `step` as an index over ECMWF's
  non uniform schedule). Decoding lives in `client.py`; the app does not need it.

## Git Workflow
- use `gh` cli tool and dont use github MCP server (not installed)
- never `git add .`, only add files changed in the current session

## Repo Structure
- `src/world_cup_climate/`: core library
  - `ifs.py`: IFS point reads, `location_series`, `matchday_value` (the app's data layer)
  - `viz_ifs.py`: Plotly match plots (`plot_match`)
  - `sports.py`: relative humidity and heat index (NOAA Rothfusz; xclim is the planned replacement)
  - `fixtures.py` / `locations.py`: load curated `data/fixtures.json` and `data/locations.json`
  - `client.py`: low-latency subscription repo decoding (bare integer dims)
  - `config.py`: repo names, defaults
  - `era5.py` / `forecast.py` / `climate.py` / `viz.py`: earlier richer ERA5 + stitching
    prototype, kept for the planned historical normal overlay
- `app/`: frontend (Streamlit target)
- `data/`: curated fixtures/locations JSON and local working data
- `notebooks/`: exploratory analysis and experiments
- `scripts/`: operational and one off helper scripts
- `tasks/`: `todo.md` plans and `lessons.md`

## Coding style
- use type hints

### Pre-commit Hooks (prek)
Hooks are defined in `prek.toml` (whitespace, EOF, config syntax, large file and secret
guards, nbstripout, gitleaks incl. a notebook aware pass via
`scripts/gitleaks_notebooks.py`). Install once with `prek install`; run all with
`prek run --all-files`. The notebook gitleaks hook needs `gitleaks` on PATH
(`brew install gitleaks`).

## Tooling
- **Arraylake MCP** (`arraylake`, HTTP at `https://app.earthmover.io/mcp`) is configured
  for this project for repo discovery, EDR point queries, and map tiles. Use it to
  inspect repos/groups before writing Python.
- **`era5` skill** (`.claude/skills/era5/`) covers ERA5 query patterns and the
  spatial vs temporal chunking choice, relevant for the planned historical normal overlay.

## Dev Workflow
- create a `feature:<name>` or `debug:<name>` branch based on `main`
- draft a plan
- critically ask a few understanding questions about the feature
- write a few meaningful unittests about the new feature
- implement the feature, not touching the unittests without user approval
- commit and open PR
