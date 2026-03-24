# Session Log

## Seja 1 — 2026-03-24

### Povzetek
Zacetek projekta ha_clss_shade. Dolocena smer: svoja integracija iz nule (ne fork HA_Solar_Shade).
Kombinacija s slovenian_weather_integration za napredno sencenje, PV predikcijo, zalivanje.

### Narejeno
- Raziskava CLSS podatkov (format, API, tile shema)
- Raziskava HA_Solar_Shade arhitekture (shadow engine, rasterizer, downloader)
- Raziskava slovenian_weather_integration (agrometeo, soncno sevanje, vodna bilanca)
- Raziskava HA developer docs + HACS zahteve
- Odlocitev: svoja integracija iz nule (ne fork)
- Inicializacija projekta: git, venv, projektna struktura
- Kreiran implementacijski nacrt (IMPLEMENTATION_PLAN.md)
- Kreirana projektna dokumentacija (CLAUDE.md, TODO.md, SESSION_LOG.md, API_REFERENCE.md)
- Vzpostavljena HACS-kompatibilna struktura
- GitHub private repo ustvarjen, initial commit pushano

### Odprta vprasanja
- ~~ARSO block number: kako mapirati tile -> block v URL za prenos LAZ~~ RESENO: auto HEAD probing
- Ali uporabiti raw point cloud ali ze pripravljen nDMP (GeoTIFF)?
- Kaksne cone definirati privzeto (streha, vrt, fasada)?

### Naslednji koraki
- ~~Implementacija geo.py~~ DONE
- ~~Implementacija slovenian_downloader.py~~ DONE
- ~~Test prenos ene LAZ ploscice~~ DONE

---

## Seja 1 (nadaljevanje) — 2026-03-24

### Narejeno
- **geo.py**: WGS84 <-> EPSG:3794 pretvorba, tile izracun, testi z realnimi koordinatami
- **slovenian_downloader.py**: auto block discovery (HEAD probing), async download, cache
  - Odkrito block mapiranje za vso Slovenijo (18 blokov)
  - Ljubljana=b_35, Maribor=b_26, Koper=b_21
- **rasterizer.py**: LAZ -> DSM/DTM numpy grids, chunk-based, gap-fill
  - Testiran z realnim Ljubljana tile: 800x800 grid, 0.5m resolucija
  - DSM 291-412m, stavbe 8.6%, visoka vegetacija 13.9%
- **shadow_engine.py**: sun position, vectorized ray-march, sezonska transmitanca
  - Optimiziran: 13.4s -> 2.0s (early termination, height-based step limit)
  - Realni podatki: 1.28s, 9.3% senca ob poletnem poldnevu
- **HA integracija**: config_flow, coordinator, sensor, __init__
  - 5 senzorjev: shade%, sun%, sun elevation, sun azimuth, daylight
  - Config flow z lokacijo, radijem, neighbor tiles opcijo
  - Coordinator: LiDAR download, site model caching, shadow vsake 5 min
  - Slovenscina: strings.json + translations/sl.json
- **HACS struktura**: hacs.json, CI workflows, manifest.json
- **GitHub repo**: https://github.com/andrejs2/ha_clss_shade (private), 6 commitov

### Odprta vprasanja
- Testiranje v HA instanci (instalacija, config flow, senzorji)
- Zone: definicija con (poligoni) za streho, vrt, teraso
- Integracija z slovenian_weather_integration (branje ARSO entitet)
- PV predikcija modul
- Zalivanje modul

### Naslednji koraki
- Testirati integracijo v HA
- Dodati zone support (poligoni)
- Povezati z ARSO vremenskimi podatki (soncno sevanje, oblacnost)
- PV predikcija senzor
