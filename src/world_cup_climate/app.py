"""FastAPI backend + static single-page frontend.

Endpoints
---------
GET /                      -> the SPA (static/index.html)
GET /api/matches           -> fixtures for the active matchday (today, else next)
GET /api/report/{idx}      -> full three-way climate report for one fixture
GET /api/health            -> token / dataset connectivity check

Run with:  uvicorn world_cup_climate.app:app --reload
       or:  world-cup-climate            (console script -> main())
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import climate, fixtures
from . import providers as prov
from .arraylake_io import MissingTokenError

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="World Cup Climate", version="0.1.0")


def _active_matchday() -> dt.date:
    """Today if it has fixtures, otherwise the next fixture date."""
    today = dt.date.fromisoformat(os.environ.get("WCC_TODAY", dt.date.today().isoformat()))
    if fixtures.matches_on(today):
        return today
    nxt = fixtures.next_matchday(today)
    return nxt or today


@app.get("/api/health")
def health():
    """Confirm credentials + dataset reachability without pulling heavy data."""
    try:
        cutoff = prov.era5_cutoff(_active_matchday())
        return {"ok": True, "data_source": prov.data_source(), "era5_cutoff": cutoff.isoformat()}
    except MissingTokenError as exc:
        return JSONResponse(status_code=503, content={"ok": False, "error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.get("/api/matches")
def list_matches():
    matchday = _active_matchday()
    matches = fixtures.matches_on(matchday)
    return {
        "matchday": matchday.isoformat(),
        "matches": [
            {
                "idx": i,
                "home": m["home"],
                "away": m["away"],
                "home_flag": fixtures.capitals().get(m["home"], {}).get("flag", ""),
                "away_flag": fixtures.capitals().get(m["away"], {}).get("flag", ""),
                "stage": m.get("stage"),
                "group": m.get("group"),
                "venue": m["venue"],
            }
            for i, m in enumerate(matches)
        ],
    }


@app.get("/api/report/{idx}")
def report(idx: int):
    matchday = _active_matchday()
    matches = fixtures.matches_on(matchday)
    if idx < 0 or idx >= len(matches):
        raise HTTPException(status_code=404, detail="No such match for the active matchday.")
    try:
        return climate.build_match_report(matches[idx])
    except MissingTokenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "world_cup_climate.app:app",
        host=os.environ.get("WCC_HOST", "127.0.0.1"),
        port=int(os.environ.get("WCC_PORT", "8000")),
        reload=bool(os.environ.get("WCC_RELOAD")),
    )


if __name__ == "__main__":
    main()
