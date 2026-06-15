# World Cup Climate — Architecture

A web app that shows ECMWF IFS weather forecasts for FIFA World Cup 2026 match
locations across the USA, Canada, and Mexico. The start page is a date-pickable
map of 2 m temperature (`t2m`) over North America with a pin on each stadium
hosting a match that day. Clicking a pin opens a card with per-match timeseries
and overview stats (time difference to each team's home, difference in mean
`t2m` and `d2m` versus home).

Backend computations are recomputed every 6 hours, as each new IFS forecast
cycle becomes available.

---

## Data layer (Arraylake / `spring-data`)

| Repo | Role |
| --- | --- |
| `spring-data/ecwmf-ifs-15-days-forecast-open` | Primary forecast source |
| `spring-data/ecmwf-ifs-15-day-forecast-low-latency-subscription` | Optional fresher feed |
| `spring-data/era5` | Climatological "home" baseline for the diff stats |

### `ecwmf-ifs-15-days-forecast-open`

- Global **0.1°** grid: `latitude` 1801 × `longitude` 3600.
- `time` — forecast reference time, **6-hourly** init cycles (00/06/12/18z).
- `step` — **hourly** lead times out to **15 days** (145 steps).
- Data variables (subset relevant to this app):
  - `2t` — 2 m temperature (K) → the map overlay (`t2m`).
  - `2d` — 2 m dewpoint temperature (K) → the `d2m` stat.
  - `10u` / `10v` — 10 m wind components (m s⁻¹) → wind speed.
  - `tp` / `cp` — total / convective precipitation (m).
  - `hcc` / `mcc` / `lcc` — high / medium / low cloud cover.
  - `msl`, `ssrd`, `fdir`, `sd`, `100u`, `100v` — available, not in MVP.
- Chunking: `[1 time, 1 step, 900 lat, 900 lon]` (~3.2 MB/chunk). **Implication:**
  a naive single-point timeseries over 145 steps pulls ~145 chunks (~470 MB).
  Point timeseries must therefore be **extracted server-side** (in the recompute
  job), not read from raw Zarr in the browser.

---

## System overview

```
ECMWF IFS 15-day (spring-data, 6-hourly cycles)
   │
   ├─► Flux TILES service  ──►  XYZ t2m tiles  ────────────┐
   │     (live raster overlay)                             │
   │                                                       ▼
   └─► Recompute job (every 6h) ──► static match JSON ──► React + MapLibre SPA
         • bbox-extract stadiums      (per cycle)           (static host)
         • compute stats
         • write JSON + redeploy
```

Three serving primitives, each matched to a design decision:

1. **Flux tiles** — the `t2m` raster overlay.
2. **Precomputed JSON** — the per-match cards.
3. **Static SPA** — glues it together. No always-on application server required.

---

## 1. Serving layer — Flux tiles

- Deploy a Flux **tiles** compute service in `spring-data` over
  `ecwmf-ifs-15-days-forecast-open`, exposing `2t` (extensible later to `tp`,
  cloud, wind).
- The frontend consumes the XYZ template (`…/tiles/{z}/{y}/{x}`) as a MapLibre
  **raster layer** over a clean basemap (Positron / dark-matter), with a
  Kelvin→°C rescale and a perceptual temperature colormap, opacity-blended over
  North America.
- The tile request carries `time` (cycle) and `step` / valid-time, so the date
  picker drives which forecast hour is painted.
- **Tile-URL freshness:** `get_tile_url` mints a *ticketed* URL that expires
  after ~1 hour — unsuitable for a public site. Resolution: make the tiles
  service **public** so the SPA fetches tiles directly, or add a tiny
  token-minting endpoint. The plan assumes a public service.

## 2. Backend recompute job (every 6 h)

Triggered when a new IFS cycle commit lands (poll the repo's latest `time`, or
schedule at init + latency). Runs as a container or scheduled CI job.

Per run:

1. Detect the latest `time` (forecast cycle).
2. Load fixtures — stadiums, match schedule, and each team's home location /
   timezone.
3. **Efficient extraction:** subset *one* small North-America bbox
   (≈ lon −125…−65, lat 14…60) across the needed steps once — touching only a
   few of the 900×900 chunks — then pull each stadium point from it via
   `.sel(method="nearest")`. This avoids the ~470 MB/match cost of naive
   per-point reads.
4. Build per-match **timeseries**: `2t`, `2d`, wind speed
   (`√(10u² + 10v²)`), `tp`, cloud cover over the match-day window (with a
   full 15-day toggle).
5. Compute **overview stats** per match:
   - **Time difference to home** (both teams) — stadium timezone vs each team's
     home timezone (timezone-database math).
   - **Δ mean t2m vs home** and **Δ d2m vs home** (per team) — match-window mean
     minus the team's **ERA5 climatological normal** at home. Normals are
     computed once and cached as a lookup.
6. Write compact JSON:
   - `cycles/latest.json` — cycle metadata + index of available dates.
   - `days/{date}.json` — pins for that date (lat/lon, teams, kickoff).
   - `matches/{matchId}.json` — full timeseries + stats for the card.

   Written to object storage with CORS, or committed to `frontend/public/data`
   for a fully static deploy.

## 3. Frontend — React + MapLibre SPA

- **Vite + React + TypeScript + Tailwind**, deployed as a static site.
- **MapLibre GL**: basemap + `t2m` raster overlay; North-America initial view.
- **Date picker** bound to available match-days → swaps the pins source and the
  overlay's valid-time.
- **Pins**: GeoJSON symbol layer from `days/{date}.json` (team flags as
  markers), clustered if dense.
- **Click → card / drawer** (Framer Motion glass card over the map):
  - Match header (teams, stadium, local kickoff).
  - Stat tiles: time-diff-to-home ×2, Δ mean `t2m`, Δ `d2m`.
  - **Timeseries charts** (uPlot or Recharts) for t2m / dewpoint / wind /
    precip / cloud.
- Modern and fresh: glassmorphism, smooth transitions, responsive / mobile,
  with proper loading / empty / error states.

## 4. Shared data contract

TypeScript types + JSON Schema for every precomputed file, so the frontend and
the recompute job can be built in parallel against fixtures before live data is
wired.

---

## Repository layout

```
/frontend            # Vite React SPA
/backend             # python: xarray + icechunk + arraylake + pandas
/schemas             # shared JSON Schema + generated TS types
/docs                # this document
/.github/workflows   # 6h recompute cron + deploy
```

## Phasing

| Phase | Deliverable |
| --- | --- |
| **P0** | Scaffold repo + data contract + sample fixture/match JSON (unblocks both sides). |
| **P1** | Deploy Flux `t2m` tiles service; verify XYZ render over NA in a MapLibre sandbox. |
| **P2** | Recompute job: bbox extract + stats + JSON for the latest cycle; commit samples. |
| **P3** | Frontend MVP wired to sample JSON: map + overlay + picker + pins + card + charts. |
| **P4** | Automate: 6h cron recompute + redeploy; public tiles service for URL freshness. |
| **P5** | Polish: design pass, ERA5 home baselines, mobile. |

## Open decisions

- **Fixtures source** — schema/location for stadiums, schedule, and team home
  locations/timezones.
- **IFS feed** — open (simplest) vs. low-latency subscription (freshest) for the
  6 h cadence.
- **Hosting** — static site + JSON target (Vercel / Cloudflare Pages / GitHub
  Pages) and object storage for the precomputed data.
