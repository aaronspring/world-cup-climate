---
name: sports-weather-app
description: Scaffold and ship a "weather at a sports event" web app deployed to GitHub Pages — a date-pickable MapLibre map with one temperature-colored pin per event and per-variable forecast charts. Use when the user wants to build a sports-weather site for a football tournament (World Cup, Euro), a cycling grand tour (Tour de France, Giro, Vuelta), a marathon/race series, or any event that is a schedule of dated occasions at geographic locations. Generalizes the world-cup-climate app: a Python recompute backend (synthetic demo + real ECMWF IFS) writes a static JSON contract that a React SPA renders. Covers the domain abstraction, the data contract, wiring real forecast data, and the gh-pages deploy.
---

# Sports weather app

Build a static site that shows the weather forecast at the locations of a sports
event. It is one pattern applied to many sports:

- **Football tournament** — a schedule of **matches**; each has a **venue** (the
  map pin) and two **team home cities** (compared against the venue on the chart).
- **Cycling grand tour** — a schedule of **stages**; each has a **finish** (the
  pin) and a **start** (the compare point).
- **Anything else** — a schedule of dated **occasions**, each with one primary
  location and 0..N compare locations.

The three pieces are always the same:

```
data/*.json  ──►  backend/recompute.py  ──►  frontend/public/data/*.json  ──►  React + MapLibre SPA  ──►  GitHub Pages
 (schedule)        (weather layer)             (static contract)                (this repo's frontend)
```

`scaffold.py` in this skill directory emits **all of it**, runnable and
deployable. Your job is mostly to (1) run the scaffolder, (2) fill in the real
schedule + coordinates, and (3) deploy.

## The core abstraction: occasions

Everything reduces to an **occasion** = a dated thing with a time, one primary
`location`, and a list of `compare` locations. This single shape is why football
and cycling share one codebase. Map the sport onto it before writing any data:

| Sport | occasion | `location` (pin) | `compare` |
| --- | --- | --- | --- |
| Football | a match | the stadium/venue | the two teams' home cities |
| Cycling | a stage | the stage finish | the stage start (add key waypoints if useful) |
| Marathon / F1 / tennis | a race / session | the course / circuit / arena | usually none, or a reference city |

The pin color and the "at start" stat come from the primary location; the chart
overlays the primary against each compare location.

## Workflow

Follow these steps in order. Do not hand-write files the scaffolder already
produces — generate first, then edit only the data.

1. **Confirm the essentials** with the user if unstated: the event name, the
   sport (`football` | `cycling` | `generic`), and the **GitHub repo**
   (`owner/name`) — the repo name becomes the Vite base path (project pages live
   at `https://<owner>.github.io/<name>/`).

2. **Scaffold** into a sibling directory (its own repo):

   ```bash
   python .claude/skills/sports-weather-app/scaffold.py \
     --out ../tour-de-france-weather \
     --slug tour-de-france-weather \
     --title "Tour de France Weather" \
     --repo aaronspring/tour-de-france-weather \
     --sport cycling
   ```

   This writes the backend, the React frontend, the deploy workflow, and **seed**
   `data/events.json` + `data/locations.json` for that sport.

3. **Replace the seed data** with the real event. This is the main work. Edit the
   two files under `data/` — see `references/data-model.md` for the exact schema.
   - `data/locations.json`: every key → `{name, lat, lon, role, country, sublabel?}`.
     Use real WGS84 decimal degrees (`lon` in −180..180). For venues/stadiums use
     the actual coordinates; for team homes use the capital or the team's home
     city; for cycling use the finish-town and start-town coordinates.
   - `data/events.json`: the `occasions` list — one entry per match/stage with
     `date`, `start_utc` (ISO 8601 `Z`), `title`, `subtitle`, `location`, `compare`.
   - Keep it small first (a handful of occasions) to validate, then expand to the
     full schedule.

4. **Build and verify locally** (the demo source needs no auth):

   ```bash
   cd <out>
   uv run python backend/recompute.py --source demo    # writes frontend/public/data
   uv run python backend/test_recompute.py             # self-checks (JSON valid, series aligned)
   cd frontend && npm install && npm run build         # tsc + vite must pass
   npm run dev                                          # eyeball http://localhost:5173
   ```

   The `verify`/`run` project skills also apply. A green `npm run build` plus the
   backend self-check is the bar before committing.

5. **Wire real forecast data** when the demo looks right — see
   `references/weather-data.md`. In short: `uv sync --extra ifs`, authenticate to
   Arraylake, and run `recompute.py --source ifs`. The demo and ifs sources emit
   the **same** contract, so the frontend does not change.

6. **Deploy to GitHub Pages.** Create the `owner/name` repo, push, and set
   **Settings → Pages → Source → GitHub Actions**. `.github/workflows/pages.yml`
   builds the demo data + frontend on every push to `main` (and twice daily). To
   serve live data, add an `ARRAYLAKE_TOKEN` repo secret and switch the workflow's
   recompute step to `--source ifs`. See `references/deploy.md`.

## What the scaffolder produces

- `backend/` — `recompute.py` (demo + ifs), `sports.py` (heat index, WBGT),
  `weather_ifs.py` (IFS point extraction), `model.py` (occasion loader),
  `test_recompute.py`.
- `frontend/` — Vite + React + TypeScript + MapLibre + Recharts SPA reading the
  static JSON. Dark glassy card, date strip, temperature-colored pins, per-variable
  charts. Plain CSS (no build-time CSS framework), so the build is robust.
- `data/` — seed `events.json` + `locations.json` for the chosen sport.
- `.github/workflows/pages.yml`, `pyproject.toml`, `README.md`, `.gitignore`.

## Extending beyond the defaults

The scaffold is a correct baseline, not a ceiling. Common upgrades, each with a
pointer to how the parent `world-cup-climate` app does it:

- **A raster weather overlay on the map** (a `t2m` field, not just pins) —
  `references/architecture.md` §overlay and `world-cup-climate`'s `na_t2m_fields`.
- **More/derived variables** (humidex, UTCI, precip, cloud) — add to `VARIABLES`
  in `recompute.py` and the series builders; `sports.py` already carries the
  formulas behind the `ifs` extra.
- **Bracket placeholders** (knockout teams not yet known) — render an occasion
  with an empty `compare` list; it degrades to venue-only automatically.
- **Roof / air-conditioning badges, i18n, flags** — see the parent repo's
  `frontend/src` for a richer, shipped implementation to copy from.

Read the reference files as needed:
`references/architecture.md` (system shape), `references/data-model.md` (the two
input files + the output contract), `references/weather-data.md` (demo vs IFS,
Arraylake auth), `references/deploy.md` (GitHub Pages).
