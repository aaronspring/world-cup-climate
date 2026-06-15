"""world-cup-climate: compare match-venue weather with team capitals and the
10-year historical normal, using ERA5 (earthmover-public/era5-private) for the
recent past and the ECMWF IFS forecast for the gap up to matchday."""

from .climate import LocationClimate, location_climate
from .config import VARIABLES, WINDOW_DAYS
from .fixtures import Match, load_matches
from .locations import Place, capital, venue
from .sports import DAILY_VARS, aggregate_daily, heat_index_celsius, relative_humidity

__all__ = [
    "LocationClimate",
    "location_climate",
    "Match",
    "load_matches",
    "Place",
    "capital",
    "venue",
    "VARIABLES",
    "WINDOW_DAYS",
    "DAILY_VARS",
    "aggregate_daily",
    "heat_index_celsius",
    "relative_humidity",
]
