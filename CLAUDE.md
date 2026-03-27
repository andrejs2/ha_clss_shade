# HA CLSS Shade

## Project
Home Assistant custom integration that uses Slovenia's CLSS (Cyclical Laser Scanning) LiDAR data
for solar/shade analysis — shade management, irrigation, PV prediction, 3D zone editing.
Designed for HACS distribution, modeled after slovenian_weather_integration.

## Structure
```
ha_clss_shade/
  custom_components/ha_clss_shade/     # HA integration
    clss_data/                         # API client sub-package (pure Python, no HA deps)
      geo.py                           # WGS84 <-> EPSG:3794 coordinate transforms
      slovenian_downloader.py          # ARSO tile discovery + async LAZ download
      rasterizer.py                    # LAZ -> DSM/DTM/classification numpy arrays
      horizon.py                       # DEM horizon profile (Open-Meteo elevation API)
    frontend/                          # Panel UI files
      panel.html                       # Zone editor (Leaflet 2D + Three.js 3D)
      viewer3d.js                      # Three.js terrain viewer + 3D zone drawing
    shadow_engine.py                   # Ray-marching shadow computation (2D + 3D)
    coordinator.py                     # HA DataUpdateCoordinator
    sensor.py                          # Sensor entities (shade%, PV, irrigation, 3D zones)
    forecast.py                        # PV forecast: shadow + weather + Haurwitz clear-sky
    weather_bridge.py                  # ARSO weather + compute_clearsky_ghi + temp derating
    inca_client.py                     # ARSO INCA nowcasting (si0zm PNG → GHI)
    openmeteo_client.py                # Open-Meteo GHI current + hourly forecast (free, global)
    websocket_api.py                   # WebSocket endpoints (config, zones, terrain, 3D zones)
    config_flow.py                     # UI configuration
    const.py                           # Constants, domain, runtime data
    zones.py                           # Zone creation, polygon/circle rasterization
    __init__.py                        # Entry setup, panel registration
    manifest.json                      # HA integration manifest
    strings.json                       # English UI strings
    translations/sl.json               # Slovenian UI strings
  scripts/                             # Standalone utility scripts
  data/                                # Local LiDAR + SolarEdge data (gitignored)
  tests/                               # Test suite
  docs/                                # Documentation, research
```

## Key Technical Details
- Slovenian LiDAR: LAZ 1.4, EPSG:3794 (D96/TM), 10 pts/m², 1x1 km tiles
- ARSO download URL: `http://gis.arso.gov.si/lidar/GKOT/laz/b_{block}/D96TM/TM_{tileE}_{tileN}.laz`
- ASPRS classification: 2=ground, 3-5=vegetation, 6=buildings
- Inspired by HA_Solar_Shade (github.com/LawPaul/HA_Solar_Shade) — own implementation
- Shadow engine is CRS-agnostic (numpy arrays in meters)
- Horizon profile: Open-Meteo elevation API (Copernicus 30m DEM), 5km radius, 72 azimuths
- Reads weather data from slovenian_weather_integration via HA state machine

## Current Capabilities (as of Seja 5, 2026-03-27)

### Shadow & Shade Analysis
- Ray-marching shadow computation over LiDAR DSM grid
- Per-zone shade/sun percentage (auto-detected + custom polygon zones)
- Seasonal vegetation transmittance (leaf-on/leaf-off)
- Shadow forecast: 5-day, 30-min resolution (days 0-1), 60-min (days 2-4)
- **DEM horizon profile**: distant hill occlusion via Open-Meteo elevation API (5km radius, 72 azimuths)
- **Improved DTM**: ground-only interpolation under dense vegetation (no artificial bumps)

### PV Forecast
- Haurwitz clear-sky GHI model (replaces fixed 800 W/m², validated ±5% on clear days)
- **Open-Meteo hourly GHI forecast** (primary, replaces cloud model when available)
- EMHASS-style cloud formula (35% diffuse floor — fallback when no GHI data)
- Temperature derating (-0.34%/°C, JinkoSolar Tiger spec)
- POA (Plane-of-Array) factor per zone per hour
- Performance factor EMA calibration (alpha=0.1, **persistent across restarts**)
- GHI priority: Open-Meteo hourly forecast (primary) → INCA (1km) → cloud model fallback
- Forecast GHI: Open-Meteo hourly → ARSO cloud model fallback
- Sensors: today/tomorrow/5-day kWh, next hour W, next 1h/3h Wh, rest-of-day kWh

### 3D Zone Editor (Phase 5 — unique in HA ecosystem)
- Three.js 3D terrain viewer from LiDAR DSM heightmap
- Satellite texture (Esri World Imagery) on ground mesh
- Layer toggles: ground, buildings, vegetation, walls
- Skirt walls for buildings (clickable at any height)
- 3D zone drawing: click points on any surface → finish polygon
- 3D zone persistence via WebSocket + HA config
- 3D zone sensors: ray-trace from arbitrary (x,y,z) → sun%/shade%
- Use cases: facades, windows, under overhangs, apartment buildings

### Weather Integration
- ARSO weather sensors (solar radiation, cloud coverage, temperature)
- ARSO agrometeo (evapotranspiration, water balance, multi-day)
- ARSO forecast (3h intervals, 6 days via weather.get_forecasts)
- INCA nowcasting (si0zm PNG → GHI, only covers SE Slovenia)
- Open-Meteo GHI: current (15-min fallback) + hourly forecast (5-day, primary for PV forecast)

### Frontend Panel
- 2D: Leaflet map with satellite basemaps, Leaflet.Draw zone editing
- 3D: Three.js viewer with OrbitControls, raycasting, zone drawing
- [2D]/[3D] toggle, layer controls, zone sidebar with delete
- WebSocket API: get_config, save_zones, get_terrain, save_3d_zones, get_3d_zones

### SolarEdge Integration (analysis)
- Site 2115036: 11.06 kWp, JinkoSolar 395W Tiger, 35°/220° (SSW)
- 5 years of production data (1822 days) analyzed for model validation
- Monthly weather factors derived: 25% (Dec) to 71% (Jul)
- System PR on clear days: ~97%

## Key Files — Quick Reference
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Detailed implementation plan with phases
- [TODO.md](TODO.md) — Tasks, ideas, bugs tracker
- [SESSION_LOG.md](SESSION_LOG.md) — Session-by-session work log
- [API_REFERENCE.md](API_REFERENCE.md) — API endpoints, data formats, coordinate systems

## Session Protocol

### Session Log (SESSION_LOG.md)
At the end of each session, append an entry with:
- Date and session number
- Summary of what was discussed/decided
- What was implemented
- Open questions
- Next steps

### TODO Tracking (TODO.md)
Living document with three sections:
- **Naloge** (Tasks): prioritized implementation tasks, check off when done
- **Ideje** (Ideas): new ideas and enhancements to evaluate
- **Bugi** (Bugs): discovered issues to fix

When discovering new tasks/ideas/bugs during work, add them immediately to TODO.md.

### API Reference (API_REFERENCE.md)
Central place for all external data sources:
- API endpoints and URL patterns
- Data formats and schemas
- Coordinate systems and projections
- Entity names from slovenian_weather_integration

### Commit Protocol
- Commit after each meaningful unit of work
- Short descriptive commit message in English
- Push to GitHub regularly for sync
- Tag releases with semantic versioning

## Language
- Code: English (variables, functions, comments)
- User communication: Slovenian
- Commit messages: English
- Documentation files: Slovenian (except CLAUDE.md)

## Dependencies
```
numpy>=1.21       # Numeric operations, shadow engine
laspy>=2.0,<3.0   # LAZ file reading
laszip>=0.2.1     # LAZ decompression
pyproj>=3.0       # Coordinate transforms (EPSG:3794)
scipy              # Gap-fill (distance_transform_edt)
aiohttp            # INCA + Open-Meteo HTTP clients
Pillow             # INCA PNG pixel reading
```

## Frontend Dependencies (CDN, no build step)
```
Three.js 0.170.0   # 3D rendering (esm.sh)
Leaflet 1.9.4      # 2D maps (unpkg)
Leaflet.Draw 1.0.4 # Polygon drawing (unpkg)
Esri World Imagery  # Satellite tiles (REST export)
```

## Known Limitations
- ~~Shadow engine only covers LiDAR radius (200m)~~ — FIXED: DEM horizon profile via Open-Meteo elevation API (5km, 72 azimuths)
- ~~DTM gap-fill uses DSM under dense trees~~ — FIXED: interpolation from ground cells only
- ~~Performance factor EMA resets on HA restart~~ — FIXED: persisted to JSON file
- INCA si0zm covers only SE Slovenia — Open-Meteo used as fallback
- 3D viewer: satellite texture quality limited by Esri export resolution

## Related Projects
- slovenian_weather_integration: https://github.com/andrejs2/slovenian_weather_integration
- HA_Solar_Shade (inspiration): https://github.com/LawPaul/HA_Solar_Shade
- CLSS viewer: https://clss.si / https://lift.clss.si/
- E-prostor: https://www.e-prostor.gov.si/dostopnost/
- EMHASS: https://github.com/davidusb-geek/emhass (PV forecast reference)
- SolarEdge API: https://monitoringapi.solaredge.com (site 2115036)
