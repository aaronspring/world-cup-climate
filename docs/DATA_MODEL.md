# Data model

Two static JSON files in `data/` drive the app. Fixtures reference locations by key.

```
fixtures.json ──venue──▶ locations.json["venues"]
              ──team_a/team_b──▶ locations.json["capitals"]
```

Every `venue` in fixtures **must** exist as a key in `venues`. Group-stage and
Round-of-32 `team_a`/`team_b` **must** exist as a key in `capitals`. Round-of-16 teams
are **bracket placeholders** (`"South Africa/Canada"`, the winner of an earlier match)
with no capital — those matches render venue-only. (Enforced informally; see the
validation snippet at the bottom.)

## `data/fixtures.json`

```jsonc
{
  "tournament": "FIFA World Cup 2026",
  "note": "...",                 // free-text provenance pointer
  "matches": [
    {
      "date":        "2026-06-15",            // local match day (YYYY-MM-DD)
      "kickoff_utc": "2026-06-15T16:00:00Z",  // ISO 8601 UTC; may roll to next day
      "stage":       "Group H",               // free text ("Group A".."Group L")
      "team_a":      "Spain",                 // → capitals key
      "team_b":      "Cape Verde",            // → capitals key
      "venue":       "mercedes_benz"          // → venues key
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `date` | string | Calendar day at the venue. `kickoff_utc` can be the following UTC day for evening kickoffs. |
| `kickoff_utc` | string | ISO 8601, always `Z`. See `FIXTURES.md` for how it was derived. |
| `stage` | string | `"Group A"`..`"Group L"`, `"Round of 32"`, `"Round of 16"`, `"Quarter-final"`, `"Semi-final"`, `"Third-place play-off"`, `"Final"`. |
| `team_a`, `team_b` | string | Group-stage and Round-of-32: exact `capitals` keys (naming follows the source: `USA`, `South Korea`, `Czechia`, `Turkiye`, `DR Congo`, `Ivory Coast`). Round-of-16 onward: a bracket placeholder (no capital) — either an `"A/B"` slot (R16, the two teams that could advance) or a `"Winner R16-1"` / `"Winner QF1"` / `"Loser SF1"` slot (quarter-final onward). |
| `venue` | string | Exact `venues` key. |

Scope: all 104 matches. 72 group-stage (2026-06-11 → 2026-06-27); the 16-match
Round of 32 (2026-06-28 → 2026-07-03, real teams); and the rest of the bracket as
placeholder teams — Round of 16 (2026-07-04 → 2026-07-07), quarter-finals
(2026-07-09 → 2026-07-11), semi-finals (2026-07-14 / 15), third-place play-off
(2026-07-18) and final (2026-07-19).

## `data/locations.json`

```jsonc
{
  "venues": {
    "mercedes_benz": {
      "city":    "Atlanta",
      "country": "United States",
      "stadium": "Mercedes-Benz Stadium",
      "lat": 33.755, "lon": -84.401,         // stadium coordinates, decimal degrees
      "roof": "retractable",                 // "open" | "retractable" | "fixed"
      "air_conditioned": true                // roof closes AND bowl is climate-controlled
    }
  },
  "capitals": {
    "Spain": {
      "capital": "Madrid",
      "lat": 40.417, "lon": -3.703           // capital city coordinates
    }
  }
}
```

| Section | Key | Value fields |
|---------|-----|--------------|
| `venues` | venue slug (kebab-ish, e.g. `estadio_azteca`) | `city`, `country`, `stadium`, `lat`, `lon`, `roof`, `air_conditioned` |
| `capitals` | country/team display name | `capital`, `lat`, `lon` |

- `lat`/`lon` are decimal degrees, WGS84; `lon` is the conventional −180..180 (not the
  IFS-store bare-integer convention — see the IFS forecast-store notes).
- 16 venues across US/Mexico/Canada. `capitals` covers every team in `fixtures.json`
  plus extras; unused capital entries are harmless.
- `roof` is `"open"`, `"retractable"`, or `"fixed"`. `air_conditioned` is `true` only when
  the roof can be closed **and** the bowl/pitch is climate-controlled — for 2026 that is
  Atlanta (`mercedes_benz`), Dallas (`att_stadium`), and Houston (`nrg_stadium`). Vancouver
  (`bc_place`) has a retractable roof but no AC; LA (`sofi`) has a fixed canopy with open
  sides. The webapp shows a ❄️ badge on air-conditioned venues. These are operator
  capabilities, not a per-match schedule — FIFA mandates hydration breaks in every match
  regardless ([player-welfare statement](https://inside.fifa.com/organisation/news/hydration-breaks-world-cup-2026-player-welfare)).

## Coupling the two

The app pairs each match's two team capitals and its venue to compare "home climate" vs
"match-day climate". A team's capital must exist **unless** it is a knockout bracket
placeholder (an `"A/B"` slot), in which case that side is rendered venue-only. The
contract is **key existence**:

```python
import json
loc = json.load(open("data/locations.json"))
fx  = json.load(open("data/fixtures.json"))
caps, ven = set(loc["capitals"]), set(loc["venues"])
placeholder = lambda t: "/" in t or t.split()[0] in {"Winner", "Loser"}  # bracket slot
for m in fx["matches"]:
    for t in (m["team_a"], m["team_b"]):
        assert placeholder(t) or t in caps, m
    assert m["venue"] in ven, m
```

In the precomputed per-match doc (`matches/{id}.json`, see `ARCHITECTURE.md` §4), a
placeholder team has **no** entry under `series.team_a`/`series.team_b` or
`stats.team_a`/`stats.team_b` — the venue series, kickoff numbers, and the map pin are
always present. The frontend keys off the absence of those entries to drop the home
comparison and label the chart "venue forecast".
