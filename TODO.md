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
- [ ] Testirati integracijo v pravi HA instanci
- [ ] Dodati zone support (poligoni za streho, vrt, teraso)
- [ ] Integracija z `slovenian_weather_integration` entitetami (soncno sevanje, oblacnost)

### Prioriteta: SREDNJA
- [ ] PV predikcija modul (shadow map + soncno sevanje + oblacnost napoved)
- [ ] Zalivanje modul (senca + evapotranspiracija + vodna bilanca + padavine)
- [ ] Dnevne ure sonca senzor (compute_daily_sun_hours ze implementiran)
- [ ] Napoved sencenja: kdaj bo sonce prislo/slo na posamezno cono
- [ ] Options flow: moznost ponovnega prenosa LiDAR podatkov

### Prioriteta: NIZKA
- [ ] Frontend panel (3D vizualizacija)
- [ ] Blueprints za avtomatizacije (rolete, zalivanje)
- [ ] Brands submission (icon za HA)
- [ ] Submission na HACS default repo
- [ ] README.md z navodili, screenshoti, HACS install badge

---

## Ideje

- [ ] Uporabi nDMP (normaliziran digitalni model povrsja) namesto raw point cloud — ze rasteriziran, GeoTIFF
- [ ] Thermal comfort zona: kombinacija UTCI + sencenje za priporocila
- [ ] Sneg na strehi: CLSS razred 21 (sneg) za detekcijo snega na PV panelih
- [ ] Multi-home podpora: vec lokacij v eni HA instanci (ze podprto prek config flow)
- [ ] Historicni podatki: primerjava LSS (stari) vs CLSS (novi) za detekcijo sprememb
- [ ] Integracija z Solcast ali Forecast.Solar za primerjavo PV napovedi
- [ ] WebSocket API za real-time shadow map streaming v frontend

---

## Bugi

(Se ni znanih bugov — treba testirati v HA)

---

## Opombe

- CLSS podatki so CC 4.0 licenca — obvezna atribucija
- ARSO streznik je rate-limited — paziti na intervale prenosov
- LAZ datoteke so velike (~48 MB per tile) — privzeto prenesi samo 1 tile
- Shadow engine: ~1.3s per frame na 800x800 gridu — sprejemljivo za 5-min interval
- scipy je potreben za gap-fill (distance_transform_edt) — dodati v manifest requirements
