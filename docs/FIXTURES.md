# How `data/fixtures.json` was sourced

`data/fixtures.json` holds all **72 group-stage matches** of the 2026 FIFA World Cup
(2026-06-11 → 2026-06-27). Knockout matches are excluded: their teams are TBD, so they
can't be keyed to a national capital, which the app requires.

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

## Regenerating

The file was produced by a one-off script (`/tmp/gen_fixtures.py`, not committed —
the schedule is now static). To rebuild, re-encode the schedule table with venue-local
times and apply the offsets above.

## Caveats

- Times are the published schedule, not necessarily exact broadcast kickoffs.
- Venue assignments should be spot-checked against FIFA official before any high-stakes use;
  Al Jazeera had at least one venue error (see above).
- Knockout stage is intentionally absent until teams are known.
