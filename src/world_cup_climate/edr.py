"""Minimal OGC EDR (Environmental Data Retrieval) HTTP client for Flux.

Flux exposes each Arraylake dataset as an EDR collection. A ``position`` query
returns a point time series as CoverageJSON — compact and web-app friendly,
with no Zarr chunk reads on the client side.

Why EDR for this app: of the deployed Flux services (edr, tiles, wms, dap2),
**EDR** is the one designed for "give me the values at this lat/lon over this
time range" — exactly the capital/venue point series we need. ``tiles``/``wms``
are for map rasters; ``dap2`` (OPeNDAP) is heavier and array-oriented.

Notes / EDR pitfalls handled here:
* datetime is sent **timezone-naive** (``...T00:00:00``, no ``Z``) — Flux rejects
  ``Z`` on tz-naive coords with a 500.
* The collection URL layout can vary by deployment; it's templated via
  ``WCC_EDR_COLLECTION_TEMPLATE`` so it can be corrected without code changes.

This module only handles the single-dimension-time case (ERA5 ``valid_time``).
The forecast's multi-dim ``(time, step)`` is not EDR-friendly and uses xarray.
"""

from __future__ import annotations

import os

import pandas as pd
import requests

# Templated so the exact path can be tuned per deployment without code edits.
# `{service}` already includes the org; `{repo}` is the bare repo name.
DEFAULT_COLLECTION_TEMPLATE = "{service}/{repo}/{ref}/{group}"

REQUEST_TIMEOUT = 60


def _collection_base(service_url: str, repo: str, ref: str, group: str) -> str:
    template = os.environ.get("WCC_EDR_COLLECTION_TEMPLATE", DEFAULT_COLLECTION_TEMPLATE)
    repo_bare = repo.split("/", 1)[-1]  # drop "org/" — org is in the service URL
    return template.format(
        service=service_url.rstrip("/"), repo=repo_bare, ref=ref, group=group.strip("/")
    ).rstrip("/")


def position_timeseries(
    *,
    service_url: str,
    repo: str,
    ref: str,
    group: str,
    lat: float,
    lon: float,
    start: str,
    end: str,
    variables: tuple[str, ...],
    token: str | None,
) -> pd.DataFrame:
    """Run an EDR ``position`` query and return an hourly DataFrame.

    Index is the time axis; columns are the requested variables in native units.
    """
    base = _collection_base(service_url, repo, ref, group)
    # tz-naive datetimes (no trailing Z); EDR range syntax is "start/end".
    dt_start = pd.Timestamp(start).strftime("%Y-%m-%dT%H:%M:%S")
    dt_end = (pd.Timestamp(end) + pd.Timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "coords": f"POINT({lon % 360.0} {lat})",
        "datetime": f"{dt_start}/{dt_end}",
        "parameter-name": ",".join(variables),
        "f": "CoverageJSON",
    }
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(
        f"{base}/position", params=params, headers=headers, timeout=REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    return _coveragejson_to_frame(resp.json(), variables)


def _coveragejson_to_frame(doc: dict, variables: tuple[str, ...]) -> pd.DataFrame:
    """Parse a CoverageJSON document into a time-indexed DataFrame."""
    axes = doc["domain"]["axes"]
    times = pd.to_datetime(axes["t"]["values"]).tz_localize(None)
    ranges = doc.get("ranges", {})
    data = {
        var: ranges[var]["values"]
        for var in variables
        if var in ranges
    }
    return pd.DataFrame(data, index=times).sort_index()
