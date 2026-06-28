# How `data/fixtures.json` was sourced

`data/fixtures.json` holds all **72 group-stage matches** of the 2026 FIFA World Cup
(2026-06-11 → 2026-06-27) plus the first two knockout rounds: **16 Round-of-32 matches**
(2026-06-28 → 2026-07-03) and **8 Round-of-16 matches** (2026-07-04 → 2026-07-07).

## Sources

- **Teams, venues, groups, match order** — [Al Jazeera full schedule](https://www.aljazeera.com/sports/2026/6/11/world-cup-2026-full-match-schedule-groups-teams-and-start-times)
  (post-draw, real team names).
- **Kickoff-time ground truth** — [KickoffAdventures UTC schedule](https://www.kickoffadventures.com/events/world-cup-26/schedule/)
  and per-match confirmations from [FIFA match centre](https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums)
  and [ESPN](https://www.espn.com/soccer/story/_/id/48939282/).

## How kickoff_utc was derived

Al Jazeera lists a wall-clock time per match but its timezone labels are unreliable
(it labeled the Seattle Belgium–Egypt match as Vancouver, and the Canada–Bosnia row as
"8:00 PM PT"). The number printed, however, is the **venue-local kickoff**. So:

```
kickoff_utc = venue_local_time + venue_offset
```

June 2026 venue offsets (DST in effect in US/Canada; Mexico has no DST):

| Zone | Venues | Offset to add |
|------|--------|---------------|
| US Eastern / Toronto (EDT) | Atlanta, Boston, Miami, NY/NJ, Philadelphia, Toronto | +4 |
| US Central (CDT) | Dallas, Houston, Kansas City | +5 |
| US/Canada Pacific (PDT) | Los Angeles, San Francisco Bay, Seattle, Vancouver | +7 |
| Mexico (CST, no DST) | Mexico City, Guadalajara, Monterrey | +6 |

This rule was validated against ground-truth UTC times for the Mexico opener (19:00 UTC),
USA–Paraguay (01:00 UTC), and every June 14–15 match.

### Manual corrections

- **Canada vs Bosnia & Herzegovina (Jun 12)** — Al Jazeera's row was corrupted
  ("8:00 PM PT" at a Toronto venue). Overrode to the confirmed 15:00 ET kickoff → 19:00 UTC.
- **Belgium vs Egypt (Jun 15)** — Al Jazeera placed it at BC Place Vancouver;
  FIFA/ticketing confirm **Lumen Field, Seattle**. Time (12:00 PT) unaffected.
- **South Korea vs Czechia (Jun 11, Guadalajara)** — missing from Al Jazeera's list;
  added from the KickoffAdventures slot (19:00 local → 01:00 UTC Jun 12).

## Knockout rounds (Round of 32 + Round of 16)

- **Schedule (dates, venues, kickoff times)** — the predetermined FIFA knockout bracket
  is fixed before the group stage ends, sourced from the public schedules
  ([Al Jazeera](https://www.aljazeera.com/sports/2026/6/28/which-teams-are-in-world-cup-last-32-knockouts-and-what-is-the-schedule),
  [Olympics.com](https://www.olympics.com/en/news/fifa-world-cup-2026-bracket-round-32-full-schedule-live-updates),
  [SI](https://www.si.com/soccer/every-confirmed-round-of-32-match-2026-world-cup),
  [NBC Sports](https://www.nbcsports.com/soccer/news/2026-world-cup-round-of-32-confirmed-schedule-predictions-for-knockout-round)).
  Kickoff times were published in US Eastern; `kickoff_utc = ET + 4h` (EDT) — e.g.
  3pm ET → `19:00Z`.
- **Round-of-32 teams** — the actual matchups, determined once the group stage finished
  (2026-06-27). All 32 are real teams that already have a capital in `locations.json`,
  so these cards behave exactly like the group stage (full venue-vs-home comparison).
- **Round-of-16 teams** — these depend on Round-of-32 results, so they are encoded as
  **bracket placeholders**: `team_a`/`team_b` are `"A/B"` slot labels (the two teams that
  could advance, e.g. `"South Africa/Canada"`). A placeholder has no capital, so the
  recompute job and the frontend drop the home comparison and render the match
  **venue-only** (venue forecast + kickoff numbers + map pin). Replace a slot with the
  single winning team's name (a `capitals` key) once a Round-of-32 result is in, and the
  full comparison appears automatically on the next recompute.

The 16 Round-of-32 winners feed the 8 Round-of-16 matches one-to-one, so each placeholder
slot maps to exactly one earlier fixture.

### Caveats on the knockout data

- Matchups and times reflect the published schedule at sourcing time; spot-check against
  FIFA official before any high-stakes use. The same Al Jazeera venue caveat applies.
- Quarter-finals, semi-finals, third-place, and the final are **not** included yet — the
  same placeholder mechanism would extend to them.

## Regenerating

The file was produced by a one-off script (`/tmp/gen_fixtures.py`, not committed —
the schedule is now static). To rebuild, re-encode the schedule table with venue-local
times and apply the offsets above.

## Caveats

- Times are the published schedule, not necessarily exact broadcast kickoffs.
- Venue assignments should be spot-checked against FIFA official before any high-stakes use;
  Al Jazeera had at least one venue error (see above).
- Round-of-16 teams are bracket placeholders (see "Knockout rounds" above); quarter-finals
  onward are not yet included.
