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

---

## Seja 4 — 2026-03-27

### Povzetek
Raziskava akademskih člankov in EMHASS repo za izboljšave PV forecasta.
Implementacija treh "low-hanging fruit" izboljšav solarnega modela.

### Raziskano
- **Paper 1** (Haupt et al., Energies 18/11/2692): Hybrid TBATS + ML za PV forecast, 2-3% nMAPE
- **Paper 2** (Aksan et al., Energies 18/6/1378): MLP + clustering, RMSE 1.75
- **EMHASS** (github.com/davidusb-geek/emhass): Energijski optimizer za HA s pvlib, ML korekcijo, mixed blending

### Ključne ugotovitve iz raziskave
- EMHASS cloud formula: `ghi = (0.35 + 0.65 * (1 - cloud)) * clearsky_ghi` — bolj realistična
- Haurwitz clear-sky model: preprost, brez dependencyjev, dovolj natančen
- Temperature derating: -0.35%/°C nad STC (25°C) — standardni pristop
- TBATS/ML korekcija: koristno šele ko imamo mesec+ podatkov
- Clustering po vremenskih tipih: ideja za prihodnost

### Implementirano
1. **Haurwitz clear-sky GHI model** — zamenjal fiksnih 800 W/m² z dinamičnim izračunom
   - Poletno opoldne: ~900 W/m², zimsko opoldne: ~300 W/m²
   - Največji vpliv: zimska napoved NI VEČ 2.4x precenjena!
2. **EMHASS-stil cloud formula** — 35% difuzni floor pri popolni oblačnosti (prej 25%)
3. **Temperature derating** — -0.35%/°C z NOCT modelom (cell = ambient + 20°C)
4. **Razdeljene sistemske izgube** — 5% (inverter+wiring) + ločen temp faktor (prej flat 8%)

### Spremembe
- **forecast.py**: clear-sky GHI, nova cloud formula, temp derating v assemble_pv_forecast()
- **weather_bridge.py**: compute_clearsky_ghi(), compute_temperature_derating(), posodobljen estimate_pv_power()
- **coordinator.py**: posredovanje sun_elevation, day_of_year, temperature v estimate_pv_power()
- **Commiti**: 1 (a1e140e)

### SolarEdge API analiza
- Pridobljen API ključ, site ID 2115036 (11.06 kWp, Ljubljana-Dobrunje)
- JinkoSolar JKM-395N-6RL3-V Tiger, temp coef -0.34%/°C
- Potegnjeni podatki: 5 let dnevne proizvodnje (1822 dni), 15-min za 3 mesece
- **Validacija Haurwitz modela**: na jasnih dnevih ratio 95-110% → model je natančen!
- **Jutranje sencenje odkrito**: ob 8:00 samo 11-38% modela → ovira na vzhodni strani
  - To je ravno kar naš LiDAR shadow engine modelira
- **Mesečni weather faktorji** izračunani za orientacijo 35°/220° (SSW):
  - Zima: 25-36%, poletje: 70-71%, letno: 57.6%
- Temp koeficient posodobljen na -0.34% (JinkoSolar spec)
- Paneli: 35° nagib, 220° azimut (SSW) — pojasni popoldanski peak

### Bugi popravljeni
- **INCA aiohttp import** — `aiohttp` je bil le v `TYPE_CHECKING` bloku, kar je povzročilo `NameError` med izvajanjem. Premaknjeno v runtime import.
- **INCA si0zm pokritost** — odkrili da INCA sončno sevanje pokriva le JV Slovenijo (Novo mesto, Posavje). Ljubljana, Maribor, Celje, Koper = brez podatkov (transparent pixel).

### Open-Meteo GHI fallback
- Dodana `openmeteo_client.py` — brezplačen, brez API ključa, globalno pokritje, 15-min resolucija
- Prioritetna veriga: INCA (1km) → **Open-Meteo** (global) → cloud model
- Test: Open-Meteo vrne ~560 W/m² za Ljubljano ob 100% ARSO oblačnosti — bolj realno od cloud modela (240 W/m²)

### Testiranje na HA
- Ob zagonu napovedi "Neznano" ~15 min (shadow forecast se računa v ozadju, 126 korakov)
- Po izračunu: danes=21.9 kWh, jutri=34.8 kWh, 5 dni=139.2 kWh
- PV ocena=428W pri 100% oblačnosti (cloud model) vs realno=1384W → performance factor 3.2
- Z Open-Meteo bo PV ocena bližje realnosti (~560 W/m² GHI namesto 240)

### Odprta vprašanja
- Kaj je jutranja ovira? (drevo, stavba, hrib) — LiDAR shadow engine bo pokazal
- Ali sta oba niza (pv_visja/pv_nizja) istega nagiba in azimuta? → Da, 35°/220°
- Performance EMA se bo moral resetirati po Open-Meteo integraciji
- Ali Open-Meteo GHI zadostuje ali potrebujemo še urni forecast?

### 3D Zone Editor (Faza 5 — implementirana!)
- **Three.js 3D viewer** z DSM heightmap meshom, OrbitControls, raycasting
- **Skirt walls** za stavbe — vertikalne stene na robovih stavb (9950 quadov)
- **Layer toggles**: Tla / Stavbe / Vegetacija / Stene — neodvisno vklapljanje
- **Satelitska tekstura** (Esri World Imagery) na ground mesh — prepoznavne strehe, ceste, trava
- **3D zone drawing**: [+ 3D Cona] → klikaj točke na terenu/stenah → [Zaključi] → poligon
- **3D zone persistence**: shranjevanje/nalaganje prek WebSocket v HA config
- **3D zone senzorji**: `is_point_in_sun_3d()` ray-trace iz (x,y,z) → sun%/shade% senzorji
- **3D zone sidebar**: seznam 3D con z barvno piko, imenom, delete gumbom
- Reusable WebSocket za 3D modul (`callWS3d`)
- Buildings/vegetation kot individual quads (ne PlaneGeometry) — brez prehodnih pobočij

### Bugi popravljeni
- **INCA aiohttp import** — premaknjeno iz TYPE_CHECKING v runtime
- **INCA si0zm pokritost** — Ljubljana brez podatkov, dodana Open-Meteo fallback
- **3D lag** — y=-999 za no-data celice povzročilo ogromne trikotnike, zamenjano z BG barvo
- **Satelitska tekstura nevidna** — building/vegetation layer mesha prekrivala ground, zamenjana s quad-i
- **Tekstura obrnjena** — flipY=false popravljen na default (true)

### Omejitev odkrita
- **Horizon profil**: shadow engine NE zazna hribov izven LiDAR radija (200m)
  - Rešitev: DEM horizon profil (30m Copernicus DEM, 5km radij) → min sun elevation per azimut
  - Potrjeno s SolarEdge podatki: jutranje sonce 11% modela ob 8:00 → vzhodni hribi

### Commiti (15 v tej seji)
- `a1e140e` Replace fixed 800 W/m² with Haurwitz clear-sky model
- `1017c26` Add Session 4 log
- `d866460` Add SolarEdge API docs and monthly weather factors
- `499d6bb` Update temp coefficient to JinkoSolar spec (-0.34%)
- `9faf7bf` Fix INCA client: import aiohttp at runtime
- `d5eb4eb` Add Open-Meteo GHI as fallback
- `e04bba7` Add Phase 5: 3D zone editor plan
- `bedcde6` Add 3D terrain viewer prototype with Three.js
- `1a5c9e7` Add 3D zone drawing UI
- `f198664` Add 3D zone persistence
- `e9a92fa` Show 3D zones in sidebar
- `1654ad3` Add layer visibility toggles
- `66c55ab` Add 3D zone shadow engine + sensors
- `44658f4` Fix lag + satellite texture
- `c54a9ef` Fix satellite texture orientation

### Naslednji koraki (Seja 5)
- ~~Horizon profil iz DEM za daljnje hribe~~ DONE
- ~~DTM gap-fill izboljšava (interpolacija pod drevesi)~~ DONE
- ~~Open-Meteo urni GHI forecast za forecast.py~~ DONE
- ~~Perzistenten performance factor~~ DONE
- Mesečni weather faktorji kot fallback

---

## Seja 5 — 2026-03-27

### Povzetek
Štiri izboljšave: DEM horizon profil za daljnje hribe, DTM gap-fill brez umetnih grbov,
Open-Meteo urni GHI za PV forecast, perzistenten performance factor.

### Narejeno

#### 1. DEM Horizon profil (clss_data/horizon.py — nov modul)
- **Open-Meteo elevation API** (Copernicus 30m DEM, brezplačen, brez API ključa)
- Vzorčenje: 72 azimutov (vsakih 5°) × 20 razdalj (300m–5km, korak 250m) = 1440 točk
- Batch API klici (po 100 točk) → izračun max horizon kota za vsak azimut
- `HorizonProfile` dataclass z `is_sun_visible(azimuth, elevation)` metodo
- Linearna interpolacija med vzorčenimi azimuti
- Cache v `horizon_profile.npz` (naloži se ob zagonu, izračuna enkrat)
- Integriran v:
  - `compute_shadow_map()` — preskočen shadow calc ko sonce pod terenom
  - `compute_shadow_forecast()` — preskočen step ko sonce pod terenom (optimizacija!)
  - `is_point_in_sun_3d()` — 3D cone tudi upoštevajo horizon
  - `compute_3d_zone_sun_percent()` — posreduje horizon
  - `compute_daily_sun_hours()` — posreduje horizon

#### 2. DTM gap-fill izboljšava (rasterizer.py)
- **Prej**: DTM luknje zapolnjene z DSM → pod drevesi DTM = vrh krošnje → umetne grbine
- **Zdaj**: `_fill_nan_nearest()` interpolira samo iz ground-classified celic
- Odstranjena vrstica `dtm[dtm_gaps] = dsm[dtm_gaps]`
- Rezultat: gladek teren pod vegetacijo, brez umetnih grbov

#### 3. Open-Meteo urni GHI forecast (openmeteo_client.py + forecast.py)
- Nova funkcija `fetch_openmeteo_forecast()`:
  - Urna resolucija (24h × 5 dni = 120 podatkovnih točk)
  - Vrne: `shortwave_radiation` (GHI W/m²), `temperature_2m`, `cloud_cover`
  - Brezplačen, brez API ključa, globalna pokritost
  - Isti ECMWF/Copernicus modeli kot profesionalne storitve
- `forecast.py` — `assemble_pv_forecast()` posodobljen:
  - Primarno: Open-Meteo GHI (že vključuje oblačnost!)
  - Fallback: EMHASS-stil cloud model iz ARSO oblačnosti
  - `interpolate_weather()` podpira novo `ghi` polje
- `coordinator.py`:
  - `_merge_weather_sources()`: združi Open-Meteo GHI + ARSO padavine
  - `_async_refresh_openmeteo_forecast()`: fetch vsake 30 min
  - Vzporedni refresh: ARSO weather + Open-Meteo vsak cikel

#### 4. Perzistenten performance factor (coordinator.py)
- `_save_performance_factor()`: JSON z EMA + timestamp v `data_dir/performance_factor.json`
- `_load_performance_factor()`: naloži ob zagonu v `async_setup()`
- Shranjevanje ob vsakem EMA update (po `update_performance_ema()`)
- EMA preživi restart HA brez resetiranja na 1.0

### Bugi popravljeni
- **3D zone izgubljene v options flow** — `config_flow.py` ni ohranjal `zones_3d` ko uporabnik
  spremeni nastavitve (radius, PV config). Dodano ohranjevanje `CONF_3D_ZONES` v `self._options`.
- **3D zone "Unknown" ponoči** — coordinator je vrnil prazen `zones_3d` dict ponoči → senzorji
  kazali "Unknown". Zdaj vrne 0% sonce za vse 3D zone (konsistentno z 2D conami).
- **Open-Meteo HTTP 429** — horizon.py pošiljal requeste prehitro. Dodani:
  - 0.3s delay med batch-i
  - Retry do 3× z eksponentnim backoff-om ob rate limitu
  - Horizon profil zdaj deluje tudi z brezplačnim Open-Meteo limitom

### Testiranje na HA
- Horizon profil se je izračunal (max=9.0° pri az=155° = JJV smer), a z nepopolnimi podatki
  zaradi 429 rate limit — popravek dodan
- Open-Meteo forecast uspešno fetch-an: 120 urnih vstopov za 5 dni
- Shadow forecast izračunan: 36+36+18+18+18 korakov (5 dni)
- 3D zone na novo narisane po options flow bugu

### Spremembe
- **Nova datoteka**: `clss_data/horizon.py` (~230 vrstic)
- **Spremenjene**: rasterizer.py, shadow_engine.py, forecast.py, openmeteo_client.py,
  coordinator.py, config_flow.py, CLAUDE.md, TODO.md
- **Commiti**: 3 (9193ee3, 8df4f12, a1e47ad)

### Odprta vprašanja
- Horizon profil: ali 5km zadostuje za vse lokacije v Sloveniji? (planine morda potrebujejo 10km)
- Open-Meteo forecast: validacija z realnimi SolarEdge podatki (primerjava GHI vs dejanska proizvodnja)
- DTM gap-fill: ali je nearest-neighbor dovolj gladek ali bi potrebovali IDW/kriging?
- Mesečni weather faktorji kot fallback: še ni implementirano
- Horizon profil az=155° (JJV) 9° — ali ujema z dejanskim terenom? (Golovec?)

### Naslednji koraki (Seja 6)
- Testirati jutri po sončnem vzhodu: horizon profil, Open-Meteo GHI, 3D zone senzorji
- Validirati horizon profil s SolarEdge jutranjimi podatki (11% ob 8:00)
- Mesečni weather faktorji kot fallback za dneve brez Open-Meteo
- Per-zone panel tilt/azimut format (cona:Wp:nagib:azimut)
- Natančnost tracking: napoved vs realno

---

## Seja 6 — 2026-03-28

### Povzetek
Popravek senzorja zalivanja (irrigation) — uporaba pravih vrtnih con namesto ogromne avto-detektirane.
Nova funkcionalnost: prikaz surovega LiDAR oblaka točk (point cloud) v 3D viewerju.
Raziskava obstoječih open-source point cloud viewerjev (Potree, potree-core, COPC).

### Narejeno

#### 1. Popravek senzorja zalivanja (coordinator.py, sensor.py)
- **Problem**: senzor `irrigation_need` je prikazoval 97.704 L namesto ~625 L
- **Vzrok**: avto-detektirana "garden" cona pokriva celotno odprto območje (~40.514 m², 162.054 celic)
  namesto dejanskih vrtnih con uporabnika (~260 m², 1.041 celic) — 156× prevelika!
- **Popravek**: nova metoda `_get_irrigation_garden()` v coordinatorju:
  - Prednostno uporabi vsoto custom con z `zone_type="garden"` (borovnice, vrt_zelenjava, maline, jz_vrt, jv_vrt)
  - Uteženo povprečje sence glede na površino cone
  - Avto-detektirana "garden" cona je samo fallback, če ni custom con
- Atributi senzorja: dodano `garden_area_m2` za preverjanje

#### 2. Raziskava 3D vizualizacije
- **CLSS pregledovalnik** (clss.si) uporablja Potree (Three.js) z Flycomovo LIFT platformo
  - Podatki v Potree octree formatu (`cloud.js`), ni surovi LAZ
  - Lastniška koda, ni uporabna za nas
- **Pregled off-the-shelf rešitev**:
  - Potree: najboljši, ampak zahteva pretvorbo LAZ→octree/COPC, iframe embed
  - potree-core: npm paket za Three.js embed, brez COPC, rabi PotreeConverter
  - copc.js: COPC čitalnik (MIT), ampak samo reader brez rendererja
  - Nobena rešitev ni plug&play za HA panel
- **Odločitev**: THREE.Points v obstoječem viewerju (0 novih odvisnosti)

#### 3. Point cloud rendering (websocket_api.py, viewer3d.js, panel.html)
- **Backend**: nov WS endpoint `get_pointcloud`
  - Bere cached LAZ datoteke z `_read_laz_clipped()`
  - Pošlje XYZ + klasifikacijo kot base64 binary
  - Subsampling opcija (1-100), privzeto vsaka 4. točka
  - Koordinate pretvorjene v viewer-local (centrirane, Y=up, north=-Z)
  - ~314k točk pri subsample=4, ~5 MB transfer
- **Frontend**: `loadPointCloud()` metoda v TerrainViewer
  - THREE.Points + THREE.PointsMaterial z vertex colors in sizeAttenuation
  - `setPointSize()`, `togglePointCloud()`, `hasPointCloud()`
- **Razširjene CLSS klasifikacijske barve**:
  - Nove: mostovi (10,17), žice (14), stolpi daljnovodov (15), manjši objekti (20)
- **Panel UI** (v12):
  - "Oblak točk" sekcija v layer controls
  - Gumb za nalaganje, visibility toggle
  - Point size slider (0.5–5.0), subsample slider (1–20)
  - Ko se naloži point cloud, se mesh sloji samodejno skrijejo

#### 4. RGB barve iz POF ortofota (websocket_api.py, rasterizer.py)
- **Ugotovitev**: GKOT LiDAR nima RGB. Barve v CLSS pregledovalniku prihajajo iz **POF** (fotogrametrični ortofoto)
- **Flycom CDN** (`assets.flycom.si`) je zaklenjen (403) — prenos samo prek CLSS pregledovalnika
- **CLSS produkti analizirani**: GKOT, DMR, DMP, nDMP, PAS, POF, POFI — URL vzorci, formati
- **POF format**: GeoTIFF RGB, 6250×6250 px, 0.16m resolucija, 1km tile, D96/TM georeferencirano
- **Implementacija**: `_sample_pof_rgb()` vzorči barve iz POF za vsako LiDAR točko
  - Prebere GeoTIFF tiepoint + pixel scale za koordinatno preslikavo
  - Podpira več POF datotek (sosednji tile-i)
  - Uporabnik ročno prenese POF_*.tif prek CLSS pregledovalnika in ga kopira v data mapo integracije
  - Fallback na klasifikacijske barve če POF ni prisoten
- **Rezultat**: prave barve — rdeče strehe, zelena trava, siv asfalt — kot v CLSS pregledovalniku

#### 5. HAG filter za šumne točke
- Navpične črte (žice, ptice, LiDAR šum) filtrirane z **max height-above-ground = 40m**
- Znotraj site grida: uporabi DTM za natančen HAG
- Zunaj site grida: median Z + 40m prag

#### 6. Vizualizacijski radij (ločen od shadow radija)
- **Problem**: celoten tile (1km) = ~10M točk, 2 tila = 20M+ → prepočasen prenos + rendering
- **Rešitev**: `vis_radius` parameter (100-600m, privzeto 400m) — večji od shadow radija za kontekst
- Slider v panel UI pred nalaganjem
- Pri r=400m/sub=4: ~1.25M točk, ~27 MB — dobro razmerje med pokritostjo in hitrostjo

#### 7. Optimizacija rasterizer-ja za manj RAM (rasterizer.py)
- **Problem**: `include_neighbors` (4 tili) → OOM kill pri ~3 GB RAM
- **Inkrementalna rasterizacija**: procesira en tile naenkrat → posodobi grid → sprosti RAM
  - Prej: preberi vse tile → kopiči vse točke → zgradi grid
  - Zdaj: za vsak tile: preberi → update grid → `gc.collect()` → naslednji
- Chunk size zmanjšan: 500k → 200k za manjši peak memory
- `_build_grids()` odstranjen — logika integrirana v `rasterize_laz()`

#### 8. Razširitve kamere in fog za večje radije (viewer3d.js)
- Camera far plane: 2000 → 3000m
- Fog: 500-1200 → 800-2000m
- OrbitControls maxDistance: 800 → 1500m

### Testiranje na HA
- Popravek zalivanja: po restartu prikazuje 698 L (namesto 97.704 L) ✓
- Point cloud z klasifikacijskimi barvami: deluje, 1.2M točk ✓
- POF RGB barve: deluje, 302.716/302.729 točk obarvanih (100%) ✓
- Navpične črte vidne → HAG filter dodan
- include_neighbors: OOM pri 4 GB RAM → povečano na 8 GB + optimizacija rasterizer-ja
- Celoten tile preveč točk → vis_radius=400m z UI sliderjem

### Spremembe
- **Spremenjene**: coordinator.py, sensor.py, websocket_api.py, viewer3d.js, panel.html, rasterizer.py, TODO.md, CLAUDE.md
- **Commiti**: 8 (f4a6b7c → f460ef2)

### Odprta vprašanja
- HAG filter 40m: ali je dovolj za vse primere? (daljnovodi gredo do ~50m)
- POF za sosednje tile-e: uporabnik mora ročno prenesti — ali avtomatizirati?
- include_neighbors OOM: z optimizacijo bi moralo iti pri 4 GB, ampak ni testirano
- Raycasting na THREE.Points za 3D zone risanje (še ni implementirano)

### Naslednji koraki (Seja 7)
- Testirati optimizirani rasterizer z include_neighbors
- HAG (height-above-ground) barvanje kot alternativa klasifikaciji/RGB
- Dinamična sončna luč iz HA senzorjev (dejanski azimut/elevacija)
- Časovni slider za animacijo senc
- Eye-Dome Lighting (EDL) post-processing
- Raycasting na point cloud za 3D zone

---

## Seja 7 — 2026-04-01

### Povzetek
Bugfix seja: rešena dva produkcijska buga — oblačnost senzor in blokiran HA startup.

### Narejeno

#### 1. Fix: oblačnost senzor "unknown" (weather_bridge.py)
- **Problem**: `sensor.parcela_oblacnost` je kazal "unknown", čeprav ARSO senzor `sensor.arso_weather_ljubljana_oblacnost` deluje (vrednost: 0)
- **Vzrok**: `find_arso_entities()` je uporabil `pattern in eid` za iskanje senzorjev. Vzorec `"oblacnost"` se je ujemal tako z `_oblacnost` (numerični, vrednost 0) kot z `_oblacnost_opis` (besedilni, vrednost "jasno"). Če se je `_opis` entiteta našla prva, je bil ta shranjen pod `cloud_coverage` ključ, `_safe_float("jasno")` je vrnil `None`, pravi numerični senzor pa je bil preskočen (`key not in found`).
- **Popravek**: zamenjava `pattern in eid` z `eid.endswith(f"_{pattern}")` — ujame samo točno ujemanje sufiksa
- **Rezultat**: oblačnost senzor pravilno prikazuje vrednost

#### 2. Fix: HA startup blokiran 5+ minut (coordinator.py, __init__.py)
- **Problem**: HA zagon je bil blokiran 5+ minut, bootstrap timeout, "Something is blocking Home Assistant"
- **Analiza loga**:
  - `async_config_entry_first_refresh()` v `__init__.py` je čakal na prvi coordinator refresh (~57 sekund za shadow map + INCA + Open-Meteo + weather)
  - `_async_refresh_shadow_forecast` je bil ustvarjen z `hass.async_create_task()` — HA bootstrap čaka na te taske
  - Shadow forecast (5 dni × mnogo korakov × ~1s/korak) je trajal minute → bootstrap timeout
- **Popravek 1**: zamenjava `async_config_entry_first_refresh()` z `async_request_refresh()` — neblokirujoč, senzorji kratko časa "unknown" dokler se prvi izračun ne konča
- **Popravek 2**: zamenjava `hass.async_create_task()` z `hass.async_create_background_task()` za shadow forecast — HA bootstrap ne čaka na background taske
- **Rezultat**: HA se požene takoj, senzorji se napolnijo ~1 min po zagonu v ozadju

### Spremembe
- **Spremenjene**: weather_bridge.py, coordinator.py, __init__.py
- **Commiti**: 2 (0613b9d, 95a4f9d)

### Naslednji koraki (Seja 8)
- Testirati optimizirani rasterizer z include_neighbors
- HAG barvanje kot alternativa klasifikaciji/RGB
- Dinamična sončna luč iz HA senzorjev
- Časovni slider za animacijo senc
- HACS priprava za testno verzijo
