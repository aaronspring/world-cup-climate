# How `data/fixtures.json` was sourced

`data/fixtures.json` holds all **104 matches** of the 2026 FIFA World Cup: the
**72 group-stage matches** (2026-06-11 → 2026-06-27) and the full **knockout bracket** —
16 Round of 32 (2026-06-28 → 2026-07-03), 8 Round of 16 (2026-07-04 → 2026-07-07),
4 quarter-finals (2026-07-09 → 2026-07-11), 2 semi-finals (2026-07-14 / 15), the
third-place play-off (2026-07-18) and the final (2026-07-19).

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
- **Round of 16** — resolved to the **actual teams** once the Round of 32 finished
  (2026-07-03). Each tie's two feeder-match winners were filled in (`team_a` = winner of
  the first feeder R32 match, `team_b` = winner of the second), so all 16 are real teams
  with a capital in `locations.json` and the cards render the full venue-vs-home
  comparison like the group stage. Winners were sourced from the published Round-of-32
  results ([Wikipedia](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_round_of_32),
  [CBS Sports](https://www.cbssports.com/soccer/news/2026-fifa-world-cup-bracket-round-of-32-results-round-of-16-matchups-final/)):
  Canada, Morocco, Paraguay, France, Brazil, Norway, Mexico, England, Spain, Portugal,
  USA, Belgium, Argentina, Egypt, Switzerland, Colombia.
- **Quarter-finals** — resolved to the **actual teams** once the Round of 16 finished
  (2026-07-07). Each tie's two feeder R16 winners were filled in (`team_a` = winner of the
  lower-numbered feeder, `team_b` = winner of the higher-numbered feeder per the bracket
  map below), so all 8 are real teams with a capital in `locations.json` and the cards
  render the full venue-vs-home comparison like the group stage. Winners were sourced from
  the published Round-of-16 results ([CBS Sports](https://www.cbssports.com/soccer/news/2026-fifa-world-cup-bracket-round-of-32-results-round-of-16-matchups-final/),
  [Olympics.com](https://www.olympics.com/en/news/fifa-world-cup-2026-bracket-quarter-finals-full-schedule-live-updates)):
  Morocco, France, Spain, Belgium, Norway, England, Argentina, Switzerland. The last R16
  tie (Switzerland vs Colombia, Vancouver) went to extra time; Switzerland advanced.
- **Semi-final onward** — these still depend on results not yet in, so the teams are
  encoded as **bracket placeholders**: `team_a`/`team_b` are slot labels with no capital,
  so the recompute job and the frontend drop the home comparison and render the match
  **venue-only** (venue forecast + kickoff numbers + map pin). They read
  `"Winner QF1"`, `"Loser SF1"`, `"Winner SF1"`, since the team pool is too large to
  enumerate.

  Replace a slot with the winning (or losing) team's name (a `capitals` key) once a result
  is in, and the full comparison appears automatically on the next recompute.

### Bracket map (which slot feeds which match)

`R16-n` numbers the eight Round-of-16 ties **in kickoff order** (R16-1 = first, Houston
Jul 4 … R16-8 = last, Vancouver Jul 7). The back half then follows the FIFA bracket:

| Match | Venue | Feeds from |
| --- | --- | --- |
| QF1 | Boston (`gillette`) | Winner R16-1 vs Winner R16-2 |
| QF2 | Los Angeles (`sofi`) | Winner R16-5 vs Winner R16-6 |
| QF3 | Miami (`hard_rock`) | Winner R16-3 vs Winner R16-4 |
| QF4 | Kansas City (`arrowhead`) | Winner R16-7 vs Winner R16-8 |
| SF1 | Dallas (`att_stadium`) | Winner QF1 vs Winner QF2 |
| SF2 | Atlanta (`mercedes_benz`) | Winner QF3 vs Winner QF4 |
| Third place | Miami (`hard_rock`) | Loser SF1 vs Loser SF2 |
| Final | New York/New Jersey (`metlife`) | Winner SF1 vs Winner SF2 |

QF1..QF4 and SF1/SF2 are the FIFA bracket positions (match order), not the file's display
order — e.g. QF4 (Kansas City) kicks off before QF3 (Miami) on 2026-07-11.

### Caveats on the knockout data

- Matchups, venues and times reflect the published schedule at sourcing time; spot-check
  against FIFA official before any high-stakes use. The same Al Jazeera venue caveat applies.
- Quarter-final-onward kickoff times were reported inconsistently across sources (often in
  UK time); they were normalised to US Eastern and may be off by an hour for some matches.
  For semi-final onward the teams are placeholders regardless, so this only shifts which
  forecast hour is marked.

## Regenerating

The file was produced by a one-off script (`/tmp/gen_fixtures.py`, not committed —
the schedule is now static). To rebuild, re-encode the schedule table with venue-local
times and apply the offsets above.

## Caveats

- Times are the published schedule, not necessarily exact broadcast kickoffs.
- Venue assignments should be spot-checked against FIFA official before any high-stakes use;
  Al Jazeera had at least one venue error (see above).
- Round-of-16 and quarter-final teams are the actual advancing sides (Round of 16 resolved
  once the Round of 32 finished on 2026-07-03; quarter-finals resolved once the Round of 16
  finished on 2026-07-07; see "Knockout rounds" above). Semi-finals onward are included but
  their teams are still bracket placeholders until those results are in.
