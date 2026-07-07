# Data model

Two static files under `data/` drive the whole app. Editing them for the real
event is the main authoring task. The backend reads them and emits a static JSON
contract under `frontend/public/data/` that the SPA fetches.

```
data/events.json ──location/compare (keys)──▶ data/locations.json
        │
        └─ backend/recompute.py ─▶ frontend/public/data/{cycles,days,events}/*.json ─▶ SPA
```

## Input 1 — `data/locations.json`

A flat map of **key → point**. Keys are referenced by `events.json`.

```jsonc
{
  "mercedes_benz": {
    "name": "Mercedes-Benz Stadium",   // display name
    "sublabel": "Atlanta",              // optional secondary line
    "country": "United States",
    "lat": 33.755, "lon": -84.401,      // WGS84 decimal degrees, lon in -180..180
    "role": "venue"                     // free label: venue | home | start | finish | ...
  },
  "Spain": {
    "name": "Madrid", "country": "Spain",
    "lat": 40.417, "lon": -3.703, "role": "home"
  }
}
```

- `lat`/`lon` are real coordinates. `role` is a free-text label used in the UI
  (e.g. "start"/"finish" for cycling, "venue"/"home" for football).
- Every key referenced by an occasion's `location` or `compare` **must** exist here.
  Unused keys are harmless.

## Input 2 — `data/events.json`

The schedule: a list of **occasions**.

```jsonc
{
  "event": "FIFA World Cup 2026",     // shown in the footer
  "sport": "football",                 // football | cycling | generic (label only)
  "occasions": [
    {
      "id": "2026-06-15_spain-vs-cape-verde",  // optional; derived from date+title if absent
      "date": "2026-06-15",                    // local calendar day (YYYY-MM-DD), drives the date strip
      "start_utc": "2026-06-15T16:00:00Z",     // ISO 8601, always Z (kickoff / stage start)
      "title": "Spain vs Cape Verde",          // card + list heading
      "subtitle": "Group H",                   // stage / category
      "location": "mercedes_benz",             // -> locations key: the map pin
      "compare": ["Spain", "Cape Verde"]       // -> locations keys: chart overlays (0..N)
    }
  ]
}
```

| Field | Notes |
| --- | --- |
| `date` | Calendar day at the venue. `start_utc` may roll to the next UTC day for evening events. |
| `start_utc` | Always `Z`. The chart draws a dashed marker here; the "at start" stat is the 2 h window mean from it. |
| `location` | Exactly one key — the map pin, colored by temperature at start. |
| `compare` | 0..N keys. Football: the two home cities. Cycling: `[stage_start]`. Empty ⇒ venue-only (no delta stats), which is how you render knockout placeholders whose teams aren't known yet. |

The window built per occasion is `date − 1 day … date + 5 days`, hourly.

## Output — the JSON contract (`frontend/public/data/`)

Written by `recompute.py`; the frontend types in `frontend/src/types.ts` mirror it.

- `cycles/latest.json` — `{cycle, source, event, sport, generated_at, dates[], variables{}}`.
  `variables` is `key → {label, unit, color}` and drives which chart series exist.
- `days/{date}.json` — `{date, events: [pin]}`. A **pin** is the lightweight subset
  used on the map/list: `id, title, subtitle, start_local, location{lat,lon,name,…},
  t2m_at_start, heat_index_at_start`.
- `events/{id}.json` — the full doc: everything in the pin plus `window`,
  `series {time[], location{var→values[]}, compare[{key,name,role,vars}]}`, and
  `stats[{key,name,role,country,tz_diff_h,deltas{var→Δ}}]`.

### JSON rules the backend already enforces

- **Never emit a bare `NaN`** (invalid JSON). Values beyond the forecast horizon
  are `null`; the UI renders those as "—"/pending. `round_series`/`_safe_round`
  handle this.
- Series arrays are aligned 1:1 with `series.time`. The self-check
  (`test_recompute.py`) verifies length alignment, JSON-validity, and pin/stat
  presence — run it after any change to the builders.
