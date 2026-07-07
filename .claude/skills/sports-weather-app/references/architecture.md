# Architecture

A static site. No always-on server: a scheduled job precomputes JSON, and a
static SPA renders it. This is the world-cup-climate architecture generalized to
arbitrary sports.

```
Forecast source (ECMWF IFS via Arraylake, or synthetic demo)
        │
        ▼
backend/recompute.py  ── every push / twice daily (GitHub Actions) ──►  static JSON contract
   • load occasions (data/events.json + data/locations.json)              (cycles/ days/ events/)
   • extract a weather series per unique location point
   • derive heat-stress indices, compute compare deltas
   • write compact JSON to frontend/public/data/
        │
        ▼
React + MapLibre SPA (Vite build) ─────────────────────────────────►  GitHub Pages
   • date strip bound to cycles/latest.json dates
   • pins from days/{date}.json, colored by temperature at start
   • click → events/{id}.json → stat tiles + per-variable Recharts chart
```

Three primitives, each matched to a decision:

1. **Precomputed JSON** — per-occasion cards. Point timeseries are extracted
   server-side because the forecast store is chunked for maps, not points (a
   naive browser read of one point over 145 steps would pull hundreds of MB).
2. **Static SPA** — glues it together, cheap to host, no backend at request time.
3. **(Optional) raster overlay** — a downsampled temperature field painted under
   the pins. Not in the scaffold baseline; see below.

## Backend (`backend/`)

- `model.py` — loads the two input files into `Occasion`/`Place` dataclasses. The
  `Occasion` (time + one `location` + N `compare`) is the abstraction that makes
  one codebase serve football and cycling.
- `recompute.py` — orchestrates: pick a series function (`synth_series` for demo,
  `make_ifs_series_fn` for real IFS), build each occasion over a `date−1d … date+5d`
  hourly window, compute per-compare deltas around start, write the contract.
  `VARIABLES` (top of the file) is the single source of truth for which series and
  chart entries exist.
- `sports.py` — heat-stress formulas: relative humidity (Magnus), NOAA heat index
  (Rothfusz), WBGT (Stull/ISO 7243). Pure numpy, so the demo needs no heavy deps.
  humidex/UTCI live here too (behind the `ifs` extra, via xclim).
- `weather_ifs.py` — real ECMWF IFS point extraction: joins the step-0 analysis
  history with the latest init's 15-day forecast into one continuous hourly series
  per point. One bulk `.load()` for all points (chunk-aware), not one read per point.

## Frontend (`frontend/`)

Vite + React + TypeScript, MapLibre GL for the map, Recharts for charts, plain CSS
(no build-time CSS framework — keeps the build robust and dependency-light).

- `data.ts` — fetches the three JSON kinds relative to Vite's `BASE_URL`.
- `types.ts` — the contract, mirroring `recompute.py` output.
- `colors.ts` — the perceptual cold→hot temperature ramp (pins, tiles).
- `MapView.tsx` — MapLibre map, CARTO Positron basemap, a GeoJSON circle layer of
  pins colored by `t2m_at_start`, click → select, fit-bounds to the day's pins.
- `App.tsx` — date strip + selection state; loads cycle → day → event.
- `EventCard.tsx` / `Chart.tsx` — stat tiles, variable chips, the overlaid line
  chart (primary location vs each compare) with a dashed start marker.

## Optional: raster temperature overlay

The scaffold ships pins only. To add a filled temperature field like the parent
app: in the IFS branch, extract a downsampled field over the event's bounding box
at each occasion's valid time, write it as `t2m/{hour}.json` (`bounds`, `nx`,
`ny`, row-major °C), and add it in `MapView` as a MapLibre **image source** under
the pins, colorized on a canvas with the same `tempColor` ramp. See
`world-cup-climate`'s `ifs.na_t2m_fields` and `docs/ARCHITECTURE.md` §1 for the
reference implementation.
