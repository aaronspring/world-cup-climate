"""Plot the IFS-only comparison: venue vs both capitals, one variable per chart."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from .ifs import latest_init, location_series

COLORS = ["#e4572e", "#1f77b4", "#2a9d8f"]  # venue, capital A, capital B

VAR_LABELS = {
    "t2m_c": ("2 m temperature", "degC"),
    "heat_index_c": ("Heat index (feels like)", "degC"),
    "rh": ("Relative humidity", "%"),
    "d2m_c": ("Dewpoint", "degC"),
}


def plot_match(places, col: str = "t2m_c", kickoff=None, ax=None):
    """One chart: best-estimate + 15-day forecast for the match's 3 locations.

    `places` is an iterable of Place (venue, capital_a, capital_b).
    Solid = best estimate (analysis), dashed = latest forecast.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 4.6))
    label, unit = VAR_LABELS.get(col, (col, ""))
    init = latest_init()
    places = list(places)
    venue_city = places[0].label.split(" — ")[-1]  # "Match venue — {city}"

    for place, color in zip(places, COLORS):
        s = location_series(place.lat, place.lon)
        # share the seam point so solid and dashed connect (no gap at init)
        obs = s[s.index <= init]
        fc = s[s.index >= init]
        ax.plot(obs.index, obs[col], color=color, lw=2.4,
                label=f"{place.name} ({place.label.split(' — ')[0]})")
        ax.plot(fc.index, fc[col], color=color, lw=2.0, ls=(0, (3, 2)), alpha=0.9)

    ax.axvline(init, color="k", lw=0.9, alpha=0.45)
    ax.text(init, ax.get_ylim()[1], "  forecast →", va="top", fontsize=8, alpha=0.6)
    if kickoff is not None:
        ko = pd.Timestamp(kickoff)
        if ko.tz is not None:  # series index is tz-naive UTC
            ko = ko.tz_convert(None)
        ax.axvspan(ko, ko + pd.Timedelta(hours=2), color="gold", alpha=0.25, label="match time")

    ax.set_ylabel(f"{label} [{unit}]")
    ax.set_title(f"{label} in {venue_city} — IFS best estimate (solid) + 15-day forecast (dashed)", fontsize=11)
    ax.legend(fontsize=8, loc="best", framealpha=0.9)
    ax.margins(x=0.01)
    return ax
