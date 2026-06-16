# Data model

Two static JSON files in `data/` drive the app. Fixtures reference locations by key.

```
fixtures.json ──venue──▶ locations.json["venues"]
              ──team_a/team_b──▶ locations.json["capitals"]
```

Every `team_a`/`team_b` in fixtures **must** exist as a key in `capitals`, and every
`venue` **must** exist as a key in `venues`. (Enforced informally; see the validation
snippet at the bottom.)

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
| `stage` | string | Currently group labels; would extend to "Round of 32" etc. |
| `team_a`, `team_b` | string | Exact `capitals` keys. Naming follows the source (`USA`, `South Korea`, `Czechia`, `Turkiye`, `DR Congo`, `Ivory Coast`). |
| `venue` | string | Exact `venues` key. |

Scope: 72 group-stage matches (2026-06-11 → 2026-06-27). No knockouts (teams TBD).

## `data/locations.json`

```jsonc
{
  "venues": {
    "mercedes_benz": {
      "city":    "Atlanta",
      "country": "United States",
      "stadium": "Mercedes-Benz Stadium",
      "lat": 33.755, "lon": -84.401          // stadium coordinates, decimal degrees
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
| `venues` | venue slug (kebab-ish, e.g. `estadio_azteca`) | `city`, `country`, `stadium`, `lat`, `lon` |
| `capitals` | country/team display name | `capital`, `lat`, `lon` |

- `lat`/`lon` are decimal degrees, WGS84; `lon` is the conventional −180..180 (not the
  IFS-store bare-integer convention — see the IFS forecast-store notes).
- 16 venues across US/Mexico/Canada. `capitals` covers every team in `fixtures.json`
  plus extras; unused capital entries are harmless.

## Coupling the two

The app pairs each match's two team capitals and its venue to compare "home climate" vs
"match-day climate". The only contract is **key existence**:

```python
import json
loc = json.load(open("data/locations.json"))
fx  = json.load(open("data/fixtures.json"))
caps, ven = set(loc["capitals"]), set(loc["venues"])
for m in fx["matches"]:
    assert m["team_a"] in caps and m["team_b"] in caps, m
    assert m["venue"] in ven, m
```
