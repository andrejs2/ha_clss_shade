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

## Faza 3 — PV napoved (naslednja seja)

### Cilj
Shadow engine izracuna senco za prihodnje ure/dni → kombinacija z vremensko
napovedjo (oblacnost) in performance faktorjem → natancna napoved PV proizvodnje.

### Nacrt implementacije

#### 3.1 Shadow engine za prihodnje casovne tocke
- [ ] `compute_shadow_forecast(site, lat, lon, hours_ahead=24, step_minutes=30)`
- Za vsako casovno tocko: izracunaj polozaj sonca + shadow map
- Vrne array: `[{time, sun_elevation, sun_azimuth, pv_zone_sun_pct}, ...]`
- Optimizacija: izracun v executor threadu, kesiranje ce se DSM ne spremeni
- ~1.3s per frame × 48 tock (24h po 30 min) = ~62s → pocasi v ozadju

#### 3.2 Kalibracija z performance faktorjem
- [ ] Tekoci povprecni performance_factor (EMA - exponential moving average)
- [ ] Shranjevanje v config entry ali persistent datoteko
- [ ] Samo dnevni podatki (sun_elevation > 10°) za robustno kalibracijo
- [ ] Loceni faktorji za razlicne pogoje:
  - `pf_clear` — jasno vreme (oblacnost < 20%)
  - `pf_cloudy` — oblacno (oblacnost > 60%)
  - `pf_mixed` — mešano
- Formula: `napoved = ocena_shadow × pf_pogoj`

#### 3.3 Vremenski podatki za napoved
- [ ] Oblacnost napoved iz ARSO (urna napoved za +24h iz weather entity)
- [ ] Ali uporabiti `weather.get_forecasts` service iz slovenian_weather_integration
- [ ] Padavine napoved — ce dezi, PV = 0
- [ ] Kombinacija: `pv_napoved = shadow_estimate × cloud_factor × performance_factor`

#### 3.4 Novi senzorji
- [ ] `sensor.dom_pv_napoved_danes_kwh` — skupna napovedana proizvodnja danes (kWh)
- [ ] `sensor.dom_pv_napoved_jutri_kwh` — skupna napovedana proizvodnja jutri (kWh)
- [ ] `sensor.dom_pv_napoved_naslednja_ura` — napoved za naslednjo uro (W)
- [ ] Atributi: urna razporeditev proizvodnje (za grafe)
  ```
  forecast_today:
    - time: "08:00"
      estimate_w: 2100
      cloud_factor: 0.85
    - time: "08:30"
      estimate_w: 3400
      cloud_factor: 0.85
    ...
  ```

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

### Odprta vprasanja
- Ali racunati shadow za 48 casovnih tock blokirno ali async v ozadju?
- Kako pogosto osvezevati napoved? Ob vsakem coordinator update (5min) ali redkeje?
- Ali shraniti performance factor v HA storage ali v datoteko?
- Ali integrirati z energy dashboard (HA native)?

---

## Ideje

- [ ] Uporabi nDMP (normaliziran digitalni model povrsja) namesto raw point cloud — ze rasteriziran, GeoTIFF
- [ ] Thermal comfort zona: kombinacija UTCI + sencenje za priporocila
- [ ] Sneg na strehi: CLSS razred 21 (sneg) za detekcijo snega na PV panelih
- [ ] Multi-home podpora: vec lokacij v eni HA instanci (ze podprto prek config flow)
- [ ] Historicni podatki: primerjava LSS (stari) vs CLSS (novi) za detekcijo sprememb
- [ ] Integracija z Solcast ali Forecast.Solar za primerjavo PV napovedi
- [ ] WebSocket API za real-time shadow map streaming v frontend
- [ ] 3D vizualizacija sencenja v frontend panelu (kot clss.si pregledovalnik)

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
