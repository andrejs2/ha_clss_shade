# HA CLSS Shade

## Project
Home Assistant custom integration that uses Slovenia's CLSS (Cyclical Laser Scanning) LiDAR data
for solar/shade analysis — shade management, irrigation, PV prediction.
Designed for HACS distribution, modeled after slovenian_weather_integration.

## Structure
```
ha_clss_shade/
  custom_components/ha_clss_shade/     # HA integration
    clss_data/                         # API client sub-package (pure Python, no HA deps)
      geo.py                           # WGS84 <-> EPSG:3794 coordinate transforms
      slovenian_downloader.py          # ARSO tile discovery + async LAZ download
      rasterizer.py                    # LAZ -> DSM/DTM/classification numpy arrays
    shadow_engine.py                   # Ray-marching shadow computation
    coordinator.py                     # HA DataUpdateCoordinator
    sensor.py                          # Sensor entities (shade%, PV, irrigation)
    config_flow.py                     # UI configuration
    const.py                           # Constants, domain, runtime data
    __init__.py                        # Entry setup
    manifest.json                      # HA integration manifest
    strings.json                       # English UI strings
    translations/sl.json               # Slovenian UI strings
  scripts/                             # Standalone utility scripts
  data/                                # Local LiDAR data (gitignored)
  tests/                               # Test suite
  docs/                                # Documentation, research
```

## Key Technical Details
- Slovenian LiDAR: LAZ 1.4, EPSG:3794 (D96/TM), 10 pts/m2, 1x1 km tiles
- ARSO download URL: `http://gis.arso.gov.si/lidar/GKOT/laz/b_{block}/D96TM/TM_{tileE}_{tileN}.laz`
- ASPRS classification: 2=ground, 3-5=vegetation, 6=buildings
- Inspired by HA_Solar_Shade (github.com/LawPaul/HA_Solar_Shade) — own implementation
- Shadow engine is CRS-agnostic (numpy arrays in meters)
- Reads weather data from slovenian_weather_integration via HA state machine

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
```

## Related Projects
- slovenian_weather_integration: https://github.com/andrejs2/slovenian_weather_integration
- HA_Solar_Shade (inspiration): https://github.com/LawPaul/HA_Solar_Shade
- CLSS viewer: https://clss.si / https://lift.clss.si/
- E-prostor: https://www.e-prostor.gov.si/dostopnost/
