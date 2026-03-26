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
- ~~Dopolnitev con (rocne cone prek config flow)~~ DONE
- ~~Frontend panel (opcijsko)~~ DONE
- Objava: HACS default repo, brands submission
- Screenshots za README

---

## Seja 2 — 2026-03-25

### Povzetek
Prva realna namestitev na HA. Analiza logov, popravki bugov, implementacija
interaktivnega Zone Editor panela s karto, agrometeo integracija, oblacnost senzor.

### Narejeno
- **Analiza HA loga**: identificirani blocking I/O bugi v downloader-ju, vse ostalo OK
- **Blocking I/O fix**: `_save_block_cache()` in file write z `run_in_executor`
- **Custom zone support (poligoni + krogi)**:
  - `zones.py`: `create_polygon_zone()` z ray-casting rasterizacijo, `parse_vertices()`, podpora za lat/lng
  - `config_flow.py`: options flow za dodajanje/brisanje con (poligon ali krog)
  - `coordinator.py`: nalaganje custom con iz config entry options
- **Interaktivni Zone Editor panel** (frontend/panel.html):
  - Leaflet + Leaflet.draw v iframe panelu v HA stranski vrstici
  - Risanje poligonov in pravokotnikov na satelitski karti
  - Dialog za ime, tip, barvo cone ob risanju
  - Urejanje oglisc, brisanje, zoom na cono
  - WebSocket API (websocket_api.py): get_config / save_zones
  - Vec iteracij: vertex markerji (rdece pike), toolbar ikone, dark theme
  - Vec kartografskih slojev: Google Satellite, Google Hybrid, Esri, OSM (layer switcher)
  - Stabilni zone ID-ji (name-based namesto index-based) — cone se ne mesajo vec
- **Agrometeo izboljsave**:
  - Branje iz overview senzorja `dnevi` atribut (multi-day napoved)
  - Prioriteta: danes meritev > danes napoved > zadnja napoved > fallback
  - Dinamicno iskanje overview senzorja ob vsakem update ciklu
  - Irrigation senzor prikazuje napoved po dnevih v atributih
- **Oblacnost senzor**: nov `cloud_coverage` senzor iz ARSO weather
- **PV ocena z oblacnostjo**: fallback ko ni merjenega sevanja (clear sky ~800 W/m2)
- **HACS/hassfest popravki**: manifest key order, hacs.json, brand icon
- **README.md**: fasadne cone avtomatizacija (5 primerov), Zone Editor docs, oblacnost
- **18 commitov** pushanih (c50cd6b → 98f912f)

### Odprta vprasanja
- GURS DOF WMS ne dela (napacni parametri ali ni javno dostopen)
- Agrometeo: preveriti ali `needs_po_zalivanju` pravilno deluje z novimi podatki
- Panel: mogoce dodati 3D pogled v prihodnosti (kot clss.si pregledovalnik)

### Naslednji koraki
- Testirati agrometeo senzor po osvezitvi podatkov (~10:00)
- Zarisati fasadne cone za avtomatizacijo zaluzij
- Repo narediti public za HACS validacijo
- Screenshots za README
- Objaviti na HACS default repo

---

## Seja 3 — 2026-03-26

### Povzetek
PV napoved proizvodnje (Faza 3): shadow forecast + weather.get_forecasts + POA + EMA kalibracija.
Razširitev na 5 dni, časovna okna, dashboard YAML. INCA nowcasting za lokacijsko sevanje.
Popravki: senzorji ponoči, race condition, avalanche treeline bug.

### Narejeno

#### Popravki
- **Senzorji ponoči**: ločen nighttime od site-not-loaded; ponoči zone=100% senca, PV=0, weather se bere
- **Race condition**: lazy entity discovery za ARSO senzorje in weather entiteto (retry ob vsakem update)
- **sensor state_class warning**: odstranjen `device_class=ENERGY` za forecast senzorje (nezdružljivo z MEASUREMENT)
- **slovenian_weather_integration avalanche bug**: `int("treeline")` crash → PR #31

#### PV napoved (forecast.py — nov modul)
- `compute_shadow_forecast()`: shadow engine za prihodnje ure, per-zone sun% za vsak 30-min korak
- `interpolate_weather()`: linearna interpolacija 3h ARSO napovedi na 30-min korake
- `assemble_pv_forecast()`: shadow × cloud × POA × capacity × performance_factor = power/uro
- `update_performance_ema()`: EMA kalibracija (alpha=0.1, samo ko sun_elevation > 10°)
- `compute_time_windows()`: next 1h/3h Wh, rest-of-today kWh iz urnih podatkov
- `ForecastData`: `days: list[PvForecastDay]` z backward-compatible `today`/`tomorrow` properties

#### 5-dnevna napoved
- Tiered intervali: dni 0-1 na 30 min (36 korakov), dni 2-4 na 60 min (18 korakov)
- Skupaj ~2.7 min CPU v ozadju vsako uro
- Smart caching: oddaljeni dnevi se re-uporabijo do 3 ure
- Cache cleanup: avtomatska odstranitev zastarelih dni

#### Novi senzorji (7 novih)
- `pv_forecast_today_kwh` + `forecast_hourly` atribut za ApexCharts
- `pv_forecast_tomorrow_kwh` + `forecast_hourly` atribut
- `pv_forecast_next_hour_w`
- `pv_forecast_5day_kwh` + `days` + `forecast_hourly_5day` atributi
- `pv_forecast_next_1h_wh`, `pv_forecast_next_3h_wh`, `pv_forecast_rest_of_today_kwh`

#### Weather forecast
- `fetch_weather_forecast()`: klic HA `weather.get_forecasts` servisa (3h intervali, 6 dni)
- `find_weather_entity()`: lazy discovery `weather.arso_*` entitete
- Refresh vsake 30 min

#### INCA nowcasting (inca_client.py — nov modul)
- INCA si0zm: lokacijsko specifično sončno sevanje (GHI) na 1km gridu
- PNG download (~50 KB) + pixel branje s Pillow
- RGB → HSV hue → GHI W/m² (rainbow barvna skala)
- Prioritetna veriga: INCA GHI > ARSO postaja > cloud model
- Refresh vsake 10 min

#### Dashboard
- `docs/pv_dashboard.yaml`: kompletna dashboard konfiguracija
- 6 sekcij: status chips, časovna okna, danes/jutri krivulje, 5-dnevni stolpci, performance gauge
- ApexCharts + Mushroom kartice (HACS)

#### README posodobitev
- Tabela napoved senzorjev, 5-dnevna napoved razlaga, tiered intervali
- ApexCharts primeri (danes, 5-dnevni stolpci, 5-dnevna krivulja)
- Link na docs/pv_dashboard.yaml

### Statistika seje
- **Nove datoteke**: 3 (forecast.py, inca_client.py, docs/pv_dashboard.yaml)
- **Spremembe**: 8 datotek, ~1500+ vrstic nove kode
- **Commiti**: 8 (bfcca64 → 1103bb2)

### Odprta vprasanja
- INCA barvna skala: kalibracija z dejanskimi dnevnimi PNG-ji (potrebujemo opoldanski PNG)
- Performance factor EMA: ni perzistenten (resetira ob restartu HA)
- ALADIN GRIB: 72h oblačnost napoved — pretežek za HA (30 MB + eccodes)
- Avalanche PR #31 čaka na merge

### Naslednji koraki
- Testirati INCA GHI kodo z dnevnim PNG (kalibracija)
- Testirati 5-dnevno napoved in dashboard na HA instanci
- Perzistenten performance factor (shranjevanje v datoteko)
- Per-zone panel tilt/azimut (format `cona:Wp:nagib:azimut`)
- Natančnost tracking: napoved vs realno (dnevna primerjava)
