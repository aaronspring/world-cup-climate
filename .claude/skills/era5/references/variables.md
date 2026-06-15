# ERA5 Variables

## Single-level variables (`single/spatial`, `single/temporal`)

| Variable | Short name | Units | Description |
|----------|------------|-------|-------------|
| `t2m` | 2t | K | 2 metre temperature |
| `d2m` | 2d | K | 2 metre dewpoint temperature |
| `u10` | 10u | m s-1 | 10 metre U wind component |
| `v10` | 10v | m s-1 | 10 metre V wind component |
| `u100` | 100u | m s-1 | 100 metre U wind component |
| `v100` | 100v | m s-1 | 100 metre V wind component |
| `fg10` | 10fg | m s-1 | Maximum 10 metre wind gust since previous post-processing |
| `sp` | sp | Pa | Surface pressure |
| `msl` | msl | Pa | Mean sea level pressure |
| `tp` | tp | m | Total precipitation (accumulated) |
| `cp` | cp | m | Convective precipitation (accumulated) |
| `lsp` | lsp | m | Large-scale precipitation (accumulated) |
| `sf` | sf | m of water equivalent | Snowfall (accumulated) |
| `sd` | sd | m of water equivalent | Snow depth |
| `skt` | skt | K | Skin temperature |
| `sst` | sst | K | Sea surface temperature |
| `stl1` | stl1 | K | Soil temperature level 1 (0-7 cm) |
| `stl2` | stl2 | K | Soil temperature level 2 (7-28 cm) |
| `stl3` | stl3 | K | Soil temperature level 3 (28-100 cm) |
| `stl4` | stl4 | K | Soil temperature level 4 (100-289 cm) |
| `ssr` | ssr | J m-2 | Surface net short-wave (solar) radiation (accumulated) |
| `ssrd` | ssrd | J m-2 | Surface short-wave (solar) radiation downwards (accumulated) |
| `fdir` | fdir | J m-2 | Surface direct short-wave (solar) radiation (accumulated) |
| `tisr` | tisr | J m-2 | TOA incident short-wave (solar) radiation (accumulated) |
| `cape` | cape | J kg-1 | Convective available potential energy |
| `blh` | blh | m | Boundary layer height |
| `slhf` | slhf | J m-2 | Time-integrated surface latent heat net flux (accumulated) |
| `tcc` | tcc | (0-1) | Total cloud cover |
| `fsr` | fsr | m | Forecast surface roughness |
| `ie` | ie | kg m-2 s-1 | Instantaneous moisture flux |
| `zust` | zust | m s-1 | Friction velocity |
| `tcw` | tcw | kg m-2 | Total column water |
| `swvl1` | swvl1 | m3 m-3 | Volumetric soil water layer 1 (0-7 cm) |
| `tsr` | tsr | J m-2 | Top net short-wave (solar) radiation (accumulated) |
| `tcwv` | tcwv | kg m-2 | Total column water vapour |

Accumulated variables (tp, cp, lsp, sf, ssr, ssrd, fdir, tisr, tsr, slhf) cover the 1-hour window ending at `valid_time`.

## Pressure-level variables (`pressure/spatial`, `pressure/temporal`)

13 pressure levels: 1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50 hPa.

| Variable | Short name | Units | Description |
|----------|------------|-------|-------------|
| `u` | u | m s-1 | U component of wind |
| `v` | v | m s-1 | V component of wind |
| `w` | w | m s-1 | Vertical velocity |
| `t` | t | K | Temperature |
| `q` | q | kg kg-1 | Specific humidity |
| `r` | r | % | Relative humidity |
| `z` | z | m2 s-2 | Geopotential |
| `pv` | pv | K m2 kg-1 s-1 | Potential vorticity |

## 500hPa subset (`500hPa/spatial`, `500hPa/temporal`)

Only `z` (geopotential) at the single 500hPa level, plus `lsm`.

## Spatial reference

- Grid: 0.25 degree regular lat/lon
- Latitude: 721 values, 90 to -90 (decreasing)
- Longitude: 1440 values, 0 to 359.75 (increasing, 0-360 convention)
- Time: hourly from 1940-01-01, in `hours since 1940-01-01`
- Extent: global
