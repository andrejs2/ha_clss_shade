# TODO

## Naloge

### Prioriteta: VISOKA
- [x] Resiti ARSO block number problem — reseno z auto HEAD probing + cache
- [x] Napisati `geo.py` — WGS84 <-> EPSG:3794 pretvorba
- [x] Napisati `slovenian_downloader.py` — tile discovery + async download
- [x] Napisati `rasterizer.py` — LAZ -> DSM/DTM numpy arrays
- [x] Napisati `shadow_engine.py` — ray-marching sencenje
- [x] Config flow za HA (lokacija, radij)
- [x] Coordinator + senzorji (shade%, sun%, azimut, elevacija, daylight)
- [x] Testirati integracijo v pravi HA instanci
- [x] Dodati zone support (poligoni za streho, vrt, teraso) — auto-detect + custom polygon/circle cone v options flow
- [x] Integracija z `slovenian_weather_integration` entitetami (soncno sevanje, oblacnost)

### Prioriteta: SREDNJA
- [x] PV ocena — per-zone kapaciteta (pv_visja:5000,pv_nizja:6000)
- [x] PV real vs estimate — performance factor senzor (Faza 2)
- [x] Zalivanje modul (senca + evapotranspiracija + vodna bilanca + padavine)
- [x] Oblacnost senzor + PV fallback iz oblacnosti
- [x] Agrometeo branje iz overview senzorja `dnevi` atribut (multi-day)
- [ ] Dnevne ure sonca senzor (compute_daily_sun_hours ze implementiran)
- [ ] Napoved sencenja: kdaj bo sonce prislo/slo na posamezno cono
- [ ] Options flow: moznost ponovnega prenosa LiDAR podatkov

### Prioriteta: NIZKA
- [x] Frontend panel — interaktivni zone editor s karto (Leaflet + Leaflet.draw)
- [x] README.md z navodili, dashboard primeri, avtomatizacije
- [ ] Blueprints za avtomatizacije (rolete, zalivanje)
- [ ] Brands submission (icon za HA)
- [ ] Submission na HACS default repo
- [ ] Screenshots za README

---

## Faza 3 — PV napoved

### Cilj
Shadow engine izracuna senco za prihodnje ure/dni → kombinacija z vremensko
napovedjo (oblacnost) in performance faktorjem → natancna napoved PV proizvodnje.

### Implementirano (2026-03-26)

#### 3.0 Per-zone panel tilt + azimut za natancen POA izracun
- [x] POA (plane-of-array) irradiance izracun iz GHI + sun position + panel orientacija
- [x] `cos(theta_incidence) / cos(theta_zenith)` za vsako uro → dinamicen tilt faktor
- [x] Zamenja fiksni tilt_factor z izracunanim per-zone per-hour
- [ ] Razsiriti PV config format: `cona:Wp:nagib:azimut` (npr. `pv-visja:5925:30:185`) — per-zone tilt/azimut

#### 3.1 Shadow engine za prihodnje casovne tocke
- [x] `compute_shadow_forecast(site, zones, lat, lon, target_date, interval_minutes=30)`
- [x] Za vsako casovno tocko: izracunaj polozaj sonca + shadow map + per-zone sun%
- [x] Izracun v executor threadu, kesiranje, osvezitev vsako uro
- [x] Background task (fire-and-forget) — ne blokira 5-min update cikla

#### 3.2 Kalibracija z performance faktorjem
- [x] Tekoci povprecni performance_factor (EMA, alpha=0.1)
- [x] Samo dnevni podatki (sun_elevation > 10°) za robustno kalibracijo
- [ ] Shranjevanje EMA v persistent datoteko (zdaj se resetira ob restartu)
- [ ] Loceni faktorji za razlicne pogoje (pf_clear, pf_cloudy, pf_mixed)

#### 3.3 Vremenski podatki za napoved
- [x] `weather.get_forecasts` service iz slovenian_weather_integration (3h intervali, 6 dni)
- [x] Linearna interpolacija 3h vremenskih na 30min shadow korake
- [x] Oblacnost napoved → cloud_factor za PV izracun
- [ ] **ARSO INCA nowcasting** — cakamo odgovor ARSO za API dostop
  - 1 km resolucija, posodobitev vsake 15 min, napoved +6h
  - Soncno sevanje (GHI) — specificno za lokacijo uporabnika
  - Ko bo na voljo, zamenja cloud-based model z dejanskim GHI
- [ ] Padavine napoved — ce dezi, PV = 0 (zdaj ne upostevamo)

#### 3.4 Novi senzorji
- [x] `sensor.*_pv_forecast_today_kwh` — skupna napovedana proizvodnja danes (kWh)
- [x] `sensor.*_pv_forecast_tomorrow_kwh` — skupna napovedana proizvodnja jutri (kWh)
- [x] `sensor.*_pv_forecast_next_hour_w` — napoved za naslednjo uro (W)
- [x] Atribut `forecast_hourly` z urno razporeditvijo (za ApexCharts grafe)

### Se za implementirati

#### 3.5 Tracking: realno vs napoved
- [ ] `sensor.dom_pv_napoved_natancnost` — dnevna natancnost napovedi (%)
  - Formula: `1 - abs(napoved_kwh - realno_kwh) / realno_kwh`
  - Atributi: zadnjih 7 dni natancnosti, povprecje
- [ ] `sensor.dom_pv_danes_realno_kwh` — realna kumulativna proizvodnja danes
  - Iz SolarEdge daily energy ali utility_meter
- [ ] History graph: napoved vs realno za vsak dan

#### 3.6 Uporaba napovedi
- Energetski management: kdaj pognati pomivalnik, sušilec, EV polnjenje
- Baterijski sistemi: kdaj shraniti, kdaj porabiti
- Prodaja na omrezje: optimizacija glede na urno tarifo
- Dashboard: graf napovedane proizvodnje za danes/jutri

---

## Ideje

- [ ] Uporabi nDMP (normaliziran digitalni model povrsja) namesto raw point cloud — ze rasteriziran, GeoTIFF
- [ ] Thermal comfort zona: kombinacija UTCI + sencenje za priporocila
- [ ] Sneg na strehi: CLSS razred 21 (sneg) za detekcijo snega na PV panelih
- [ ] Multi-home podpora: vec lokacij v eni HA instanci (ze podprto prek config flow)
- [ ] Historicni podatki: primerjava LSS (stari) vs CLSS (novi) za detekcijo sprememb
- [ ] Integracija z Solcast ali Forecast.Solar za primerjavo PV napovedi
- [ ] INCA/forecast blending — INCA za 0-2h, ARSO forecast za 2-48h (utežen prehod)
- [ ] Sklearn korekcija na rezidualih (ko imamo mesec+ podatkov) — à la EMHASS ML adjustment
- [ ] Clustering po vremenskih tipih — ločene cloud krivulje za jasno/delno oblačno/oblačno
- [ ] WebSocket API za real-time shadow map streaming v frontend
- [ ] **Faza 5: 3D zone editor** — Three.js viewer + skirt walls + 3D raycasting za cone
  - [ ] DSM→Three.js mesh + satelitska tekstura + barvanje po klasifikaciji
  - [ ] Skirt walls za stavbe (vertikalne stene, klikljive na katerikoli višini)
  - [ ] 3D zone drawing z raycasting (tla, streha, fasada, pod napuščem)
  - [ ] Shadow engine razširitev: `is_point_in_sun_3d(x, y, z, sun, dsm)`
  - [ ] Use cases: žaluzije (fasada), terasa pod napuščem, PV na bloku, okna v nadstropju

---

## Bugi

- [x] Blocking I/O v event loop (slovenian_downloader.py: write_text, open) — popravljeno z run_in_executor
- [x] Zone editor: cone so se mesale (index-based → name-based fix)
- [ ] GURS DOF WMS layer ne dela v panelu (napacni parametri)

---

## Opombe

- CLSS podatki so CC 4.0 licenca — obvezna atribucija
- ARSO streznik je rate-limited — paziti na intervale prenosov
- LAZ datoteke so velike (~48 MB per tile) — privzeto prenesi samo 1 tile
- Shadow engine: ~1.3s per frame na 800x800 gridu — sprejemljivo za 5-min interval
- scipy je potreben za gap-fill (distance_transform_edt) — dodati v manifest requirements
- Performance factor kalibracija: potrebuje vsaj 3-5 soncnih dni za zanesljiv EMA
