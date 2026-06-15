---
name: era5
description: Query and analyze ERA5 reanalysis data in Arraylake repos. Use when working with ERA5 temperature, wind, pressure, precipitation, or other variables from the single-level or pressure-level datasets. Covers choosing the right group (spatial vs temporal chunking), common analysis patterns (max temp at last timestep, time series at a point, spatial maps), and the repo layout.
---

# ERA5

## Dual-group chunking: spatial vs temporal

ERA5 repos store data in two parallel chunking layouts per variable group. Choosing the wrong one causes terrible performance.

- **`spatial`** -- chunked as `(1, lat, lon)` (one timestep per chunk, full spatial slice). Use for **spatial queries**: maps, global max/min, extracting a single timestep's field.
- **`temporal`** -- chunked as `(time, small_lat, small_lon)` (many timesteps, small spatial patches). Use for **time series at a point**: historical max at a coordinate, trends, seasonal cycles.

### Decision guide

| Task | Group | Why |
|---|---|---|
| "Highest temperature on Earth right now" | `*/spatial` | Need full spatial field at one time; spatial group has one timestep per chunk |
| "Is this the hottest ever at this location?" | `*/temporal` | Need all timesteps at one grid cell; temporal group has time slices |
| "Map of 500hPa geopotential" | `*/spatial` | Full spatial field at a single time level |
| "Temperature trend at a city" | `*/temporal` | Point time series spanning decades |

## Which repo to use

Two ERA5 repos exist -- pick based on access:

- **`earthmover-public/era5-private`** -- private repo, requires a paying Arraylake subscription. Use if the user has confirmed access.
- **`earthmover-public/era5`** -- authenticated-public repo (free access via marketplace). Use for anyone without a paid subscription.

Both repos have identical data and structure. The only difference is access control.

## Repo layout

Groups under each ERA5 repo root:

```
single/        -- single-level variables (t2m, tp, msl, u10, v10, ssrd, etc.)
  spatial/     -- chunked (valid_time, latitude, longitude) with native lat/lon coords
  temporal/    -- same variables, chunked for time series
pressure/      -- pressure-level variables (u, v, w, t, q, r, z, pv) at 13 levels
  spatial/     -- chunked (valid_time, pressure_level, latitude, longitude)
  temporal/    -- same, chunked for time series
500hPa/        -- subset of pressure variables at 500hPa only
  spatial/
  temporal/
```

Each group has coordinate arrays (`latitude`, `longitude`, `valid_time`) and a static `lsm` (land-sea mask).

`valid_time` is in `hours since 1940-01-01` (int64) with `proleptic_gregorian` calendar.

## Common patterns

### Open dataset

```python
import xarray as xr
from arraylake import Client

client = Client(token="ema_...")
repo = client.get_repo("earthmover-public/era5-private")
session = repo.readonly_session(branch="main")

ds = xr.open_zarr(session.store, group="single/temporal", consolidated=False, chunks={})
```

### Max temperature at the last timestamp (spatial group)

```python
session = repo.readonly_session(branch="main")
ds = xr.open_zarr(session.store, group="single/spatial", consolidated=False, chunks={})
last = ds.isel(valid_time=-1)
t2m = last["t2m"].compute()
max_val = float(t2m.max())
max_idx = int(t2m.argmax(dim=["latitude", "longitude"]))
lat = float(t2m.latitude.values.flat[max_idx])
lon = float(t2m.longitude.values.flat[max_idx])
```

### Time series at a point (temporal group)

```python
session = repo.readonly_session(branch="main")
ds = xr.open_zarr(session.store, group="single/temporal", consolidated=False, chunks={})
ts = ds["t2m"].sel(latitude=28.25, longitude=250.25, method="nearest").compute()
```

### Variable reference

See `references/variables.md` for the full list of available variables in single-level and pressure-level groups.

## Applications

| Use Case | Key variables | Group |
|---|---|---|
| Climate change analysis | `t2m`, `tp`, `msl` | `temporal` for point trends |
| ML for weather prediction | Full surface + pressure fields | `temporal` for training data loading |
| Extreme weather studies | `t2m`, `tp`, `cape`, `fg10` | `spatial` for event maps, `temporal` for return periods |
| Renewable energy assessment | `u10`, `v10`, `u100`, `v100`, `ssrd`, `fdir` | `temporal` for site resource, `spatial` for regional |
| Agriculture / food security | `stl1`-`stl4`, `tp`, `sd`, `sf` | `temporal` for time series |
| Hydrological modeling | `tp`, `sf`, `sd`, `lsp` | `temporal` for catchment |
| Climate model validation | `t2m`, `msl`, `z@500hPa` | `spatial` for spatial skill scores |
| Synoptic / dynamical meteorology | `z@500hPa`, full pressure `u`,`v`,`t`,`z` | `spatial` for maps, `temporal` for wave activity indices |
| Air quality modeling | `blh`, `sp`, `u10`, `v10` | `temporal` for boundary layer evolution |
| Ocean-atmosphere studies | `sst`, `slhf`, `ssr` | `temporal` for coupling analysis |

## Querying via Arraylake MCP

ERA5 data can be queried through Arraylake's Flux compute services using MCP tools -- no Python code required.

### Discover compute services

```python
# Use the list_compute_services MCP tool to find available services
# for the earthmover-public org. Typical deployments: "edr", "tiles".
```

### Spatial maps (tiles)

```python
# Use render_dataset_map or get_tile_url to visualize variables on a map.
# Example: t2m on the last available timestep via the tiles deployment.
# Pass style="raster/viridis", colorscalerange=[220, 320].
```

### Point queries (EDR position)

```python
# Use query_edr with type="position" to get a time series at a coordinate.
# Example: coords="POINT(250.25 28.25)", parameter-name="t2m",
# group="single/temporal" -- returns CSV or CoverageJSON.
```

### Gridded extraction (EDR cube)

```python
# Use query_edr with type="cube" to extract a spatial bounding-box.
# Example: bbox=[-10, 35, 30, 60], parameter-name="t2m,z",
# group="single/spatial", datetime="2025-06-01".
```

### Required parameters for all queries

| Parameter | Value for ERA5 |
|---|---|
| `org` | `earthmover-public` |
| `repo` | `era5-private` or `era5` |
| `group` | `single/spatial`, `single/temporal`, `pressure/spatial`, etc. |

Always call `list_compute_services` first to discover the `deployment` name, then `get_service_dataset_info` to list available dimensions (datetime, pressure_level, etc.) before querying.

## Session management

- `Session` does NOT support the context manager protocol. Close explicitly or keep as a local variable.
- The Arraylake `client.get_repo()` returns an Icechunk `Repository`, which returns `Session` objects from `repo.readonly_session(branch="main")`.
- Always pass `consolidated=False` to `xr.open_zarr()` -- Icechunk manages metadata internally.
