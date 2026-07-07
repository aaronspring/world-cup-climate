# Weather data: demo vs real IFS

Both sources emit the **identical** JSON contract, so you develop and deploy on
the demo source and swap to real forecast data without touching the frontend.

## `--source demo` (default, no auth)

`synth_series` in `recompute.py` produces a physically plausible synthetic
forecast: a smooth function of lat/lon (mean climate that cools with latitude),
a diurnal cycle in local solar time, and a slow synoptic wave. Nearby points
(e.g. a stadium vs a city 50 km away) stay in phase with a near-zero delta, like
real forecast data. It is deterministic, so rebuilds are stable, and it needs
only numpy + pandas.

Use it for: scaffolding, layout, the whole frontend, and the initial deploy. The
site is fully functional on demo data.

## `--source ifs` (real ECMWF forecast)

`weather_ifs.py` reads `spring-data/ecwmf-ifs-15-days-forecast-open` via
Arraylake (managed Icechunk/Zarr). It joins two slices into one continuous line
per point:

- **best estimate** — `step=0` across every 6-hourly init: recent conditions up
  to now.
- **forecast** — the latest populated init, all steps: the 0…15-day outlook.

Variables pulled: `2t`, `2d` (→ temperature, dewpoint, humidity, heat index),
`10u`/`10v` (→ wind speed), `ssrd` (→ WBGT solar term). Extraction is bulk and
chunk-aware: two `.load()` calls total for all points, not one read per point.

### Enabling it

```bash
uv sync --extra ifs                    # installs xarray, arraylake, xclim, icechunk, zarr
uv run arraylake auth login            # interactive; writes ~/.arraylake/token.json
# or, headless / CI:
export ARRAYLAKE_TOKEN=ema_...
uv run python backend/recompute.py --source ifs
```

The open repo has global coverage, so it serves both venues and any home city
from one store — there is no separate climatology source. The `Place` in
`model.py` carries lat/lon directly, so any point on Earth works with no geocoder.

### Notes and gotchas

- **Forecast horizon (~15 days).** Occasions further out than the latest init has
  data for get `null` scalars and NaN-tail series; the backend nulls them (never a
  bare NaN) and the UI shows "pending". They fill in automatically as recompute
  runs bring the date into range.
- **Nearest-point selection.** `sel(method="nearest")` on the 0.1° grid — good to
  a few km, fine for venues and cities.
- **Coordinates.** The open repo uses clean CF coords (real lat/lon in −180..180).
  Do not use the low-latency subscription repo's bare-integer convention here.
- The parent `world-cup-climate` repo has the fuller extraction (disk cache per
  init cycle, a North-America raster overlay). Copy from `src/world_cup_climate/ifs.py`
  if you need those.

## Adding or changing variables

`VARIABLES` at the top of `recompute.py` is the single source of truth — a `key →
{label, unit, color}` map. Add a key there, produce it in both `synth_series` and
the `_IFS_COL` mapping (and `_derive` in `weather_ifs.py`), and the frontend picks
it up automatically (chips + chart) from `cycles/latest.json`. `sports.py` already
carries humidex and UTCI (behind the `ifs` extra) if you want more heat-stress
indices.
