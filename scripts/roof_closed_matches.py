"""List the World Cup 2026 matches most likely to be played with the roof
closed and air conditioning on.

This is a *heuristic*, not an official schedule. The decision combines two
things:

  1. Venue capability — only Atlanta, Dallas and Houston have a retractable
     roof AND a climate-controlled bowl (``air_conditioned: true`` in
     ``data/locations.json``). Vancouver has a roof but no AC; everything else
     is open-air.
  2. Heat — operators close the roof and run AC to beat the heat. We flag a
     match when the forecast match-day WBGT at the venue clears FIFA's
     cooling-break threshold (32 °C; FIFPRO recommends action from 28 °C).

FIFA does not publish a per-match "roof closed" list — it mandates a 3-minute
hydration break in every match regardless of roof or temperature
(https://inside.fifa.com/organisation/news/hydration-breaks-world-cup-2026-player-welfare).
So this script is the practical way to "find out" which matches are candidates.

Usage:
    uv run python scripts/roof_closed_matches.py                  # demo forecast
    uv run python scripts/roof_closed_matches.py --source ifs     # real IFS (needs auth)
    uv run python scripts/roof_closed_matches.py --wbgt 28        # FIFPRO threshold
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from recompute import WINDOW_AFTER, WINDOW_BEFORE, make_ifs_series_fn, synth_series  # noqa: E402

from world_cup_climate.fixtures import load_matches  # noqa: E402

FIFA_WBGT = 32.0  # °C — FIFA mandatory cooling-break threshold (2014–2025)


def matchday_max(series_fn, place, date: str) -> float:
    """Daily-max WBGT at a location on the match day."""
    md = pd.Timestamp(date)
    times = pd.date_range(md - WINDOW_BEFORE, md + WINDOW_AFTER, freq="1h")
    wbgt = pd.Series(series_fn(place, times)["wbgt"], index=times)
    day = wbgt[(times >= md) & (times < md + pd.Timedelta(days=1))]
    return float(day.max())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["demo", "ifs"], default="demo")
    ap.add_argument("--wbgt", type=float, default=FIFA_WBGT,
                    help=f"WBGT threshold in °C (default {FIFA_WBGT}, FIFA cooling break)")
    args = ap.parse_args()

    matches = load_matches()
    ac_matches = [m for m in matches if m.venue.air_conditioned]
    print(f"{len(ac_matches)} matches at air-conditioned venues "
          f"(of {len(matches)} total); WBGT threshold {args.wbgt}°C\n")

    series_fn = make_ifs_series_fn(ac_matches) if args.source == "ifs" else synth_series

    hot = []
    for m in ac_matches:
        wbgt = matchday_max(series_fn, m.venue, m.date)
        if wbgt >= args.wbgt:
            hot.append((m, wbgt))

    hot.sort(key=lambda x: -x[1])
    if not hot:
        print("No air-conditioned-venue match clears the threshold in this forecast.")
        return

    print("Likely roof-closed + AC (forecast WBGT ≥ threshold):")
    for m, wbgt in hot:
        print(f"  {m.date}  {m.stage:<8}  {m.venue.name:<22}  "
              f"{m.team_a} vs {m.team_b:<16}  WBGT {wbgt:4.1f}°C")


if __name__ == "__main__":
    main()
