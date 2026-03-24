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
- ARSO block number: kako mapirati tile -> block v URL za prenos LAZ
- Ali uporabiti raw point cloud ali ze pripravljen nDMP (GeoTIFF)?
- Kaksne cone definirati privzeto (streha, vrt, fasada)?

### Naslednji koraki
- Implementacija geo.py (koordinatne pretvorbe)
- Implementacija slovenian_downloader.py (tile discovery + download)
- Test prenos ene LAZ ploscice
