"""Matplotlib helpers: current 30-day window (ERA5 + IFS) vs the 10-year normal.

Kept dependency-light (matplotlib only) so it works in the notebook now; the
web frontend can reuse the same `LocationClimate` data later.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from .climate import LocationClimate
from .sports import DAILY_VARS

HIGHLIGHT = "#e4572e"   # this-year highlight
HIST = "#b0b0b0"        # previous years (gray)
NORMAL = "#3a3a3a"      # climatological median


def plot_window_vs_climatology(
    lc: LocationClimate,
    var: str,
    era5_end: pd.Timestamp,
    ax: plt.Axes | None = None,
    show_outlook: bool = True,
):
    """Plot one variable: gray lines = each of the last 10 years' 30-day window,
    highlight = this year's window (ERA5 solid up to today-6d, IFS forecast dashed),
    aligned on day-offset so matchday = 0.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4.2))

    label, unit = DAILY_VARS.get(var, (var, ""))

    # previous 10 years in gray
    for i, (year, df) in enumerate(sorted(lc.hist_years.items())):
        s = df.set_index("offset")[var]
        ax.plot(s.index, s.values, color=HIST, lw=1.0, alpha=0.7,
                zorder=1, label="Previous 10 years" if i == 0 else None)

    # climatological median for orientation
    clim = lc.climatology.get(var)
    if clim is not None:
        ax.plot(clim.index, clim["p50"], color=NORMAL, lw=2.0, ls=(0, (4, 2)),
                zorder=2, label="10-yr median")

    # this year, split at the ERA5 / forecast boundary
    cur = lc.current
    e_part = cur[cur.index <= era5_end]
    f_part = cur[cur.index >= era5_end]  # overlap one point for a continuous line
    ax.plot(e_part["offset"], e_part[var], color=HIGHLIGHT, lw=2.6,
            zorder=4, label="This year — ERA5")
    if len(f_part) > 1:
        ax.plot(f_part["offset"], f_part[var], color=HIGHLIGHT, lw=2.6,
                ls=(0, (2, 1.5)), zorder=4, label="This year — IFS forecast")

    # forward outlook beyond matchday
    if show_outlook and lc.outlook is not None and var in lc.outlook:
        out = lc.outlook
        ax.plot(out["offset"], out[var], color=HIGHLIGHT, lw=1.6, ls=":",
                alpha=0.6, zorder=3, label="IFS outlook")

    ax.axvline(0, color="k", lw=0.8, alpha=0.4)
    ax.scatter([0], [lc.matchday_now[var]], color=HIGHLIGHT, s=55,
               zorder=6, ec="white", lw=1.2)
    ax.set_xlabel("days relative to matchday")
    ax.set_ylabel(f"{label} [{unit}]")
    ax.set_title(f"{lc.place.name} — {label}", fontsize=11)
    ax.margins(x=0.01)
    return ax


def plot_match_overview(match_climates: dict, var: str, era5_end: pd.Timestamp):
    """One row of panels (venue + two capitals) for a single variable."""
    n = len(match_climates)
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 4.2), sharey=True)
    if n == 1:
        axes = [axes]
    for ax, (_, lc) in zip(axes, match_climates.items()):
        plot_window_vs_climatology(lc, var, era5_end, ax=ax)
    axes[0].legend(fontsize=8, loc="best", framealpha=0.9)
    fig.tight_layout()
    return fig
