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
- ~~Zone: definicija con za streho, vrt, teraso~~ RESENO: auto-detekcija iz LiDAR klasifikacije
- ~~Integracija z slovenian_weather_integration~~ RESENO: weather_bridge.py
- ~~PV predikcija modul~~ RESENO: estimate_pv_power()
- ~~Zalivanje modul~~ RESENO: estimate_irrigation_need()

### Naslednji koraki
- ~~Dodati zone support~~ DONE
- ~~Povezati z ARSO vremenskimi podatki~~ DONE
- ~~PV predikcija senzor~~ DONE
- ~~README.md~~ DONE

---

## Seja 1 (zakljucek) — 2026-03-24

### Narejeno
- **zones.py**: avtomatska detekcija con iz LiDAR klasifikacije
  - 4 cone: roof (stavbe), garden (tla blizu stavb), trees (vegetacija), open (odprto)
  - Dilacija maske za "blizina stavbe" prek distance_transform_edt
  - Podpora za krožne ročne cone (create_circular_zone)
  - Per-zone shade% in sun% izračuni
- **weather_bridge.py**: branje ARSO entitet iz slovenian_weather_integration
  - Auto-discovery ARSO senzorjev v HA (solar radiation, ETP, vodna bilanca, padavine)
  - estimate_pv_power(): shadow map + ARSO sevanje → ocena PV proizvodnje v W
  - estimate_irrigation_need(): shadow + ETP + vodna bilanca + padavine → L/dan
- **coordinator.py**: posodobljen z zone detekcijo, ARSO bridge, PV/irrigation
- **sensor.py**: 7 globalnih + 2 per-zone senzorjev (~15 skupaj)
  - Novi: pv_power_estimate (W), irrigation_need (L)
  - Per-zone: shade% in sun% za vsako auto-detektirano cono
  - Extra atributi: area_m2, solar_radiation, ETP
- **README.md**: 430 vrstic, v celoti v slovenščini
  - Badges, HACS gumb, podroben opis delovanja
  - Ray-marching algoritem, sezonski model, PV in zalivanje formule
  - 4 primeri avtomatizacij (rolete, zalivanje, PV opozorilo, dashboard)
  - Tehnicni podatki, atribucija (GURS, ARSO, Flycom, LawPaul)
- **git config**: nastavljeno na andrejs2 za prihodnje commite
- **10 commitov** pushanih na GitHub

### Statistika seje
- **Datoteke**: 20+ ustvarjenih/posodobljenih
- **Koda**: ~2500 vrstic Python + JSON + Markdown
- **Testi**: 25+ testov (geo, downloader, rasterizer, shadow engine, zones, weather bridge)
- **Realni podatki**: testiran z dejanskim LiDAR tile-om Ljubljanskega gradu
- **Zmogljivost**: shadow engine 1.3s per frame na 800×800 gridu

### Stanje projekta
Faza 1 (temelj), Faza 2 (shadow engine), Faza 3 (HA integracija) in vecji del
Faze 4 (napredne funkcije) so zakljuceni. Integracija je pripravljena za testiranje
v Home Assistant instanci.

Preostane:
- Testiranje v pravi HA instanci
- Dopolnitev con (rocne cone prek config flow)
- Frontend panel (opcijsko)
- Objava: HACS default repo, brands submission
- Screenshots za README
