# TODO

## Naloge

### Prioriteta: VISOKA
- [ ] Resiti ARSO block number problem — kako mapirati tile koordinate na block stevilko v URL
- [ ] Napisati `geo.py` — WGS84 <-> EPSG:3794 pretvorba
- [ ] Napisati `slovenian_downloader.py` — tile discovery + async download
- [ ] Napisati `rasterizer.py` — LAZ -> DSM/DTM numpy arrays
- [ ] Napisati `shadow_engine.py` — ray-marching sencenje

### Prioriteta: SREDNJA
- [ ] Config flow za HA (lokacija, radij, cone)
- [ ] Coordinator + senzorji
- [ ] Integracija z `slovenian_weather_integration` entitetami
- [ ] PV predikcija modul
- [ ] Zalivanje modul

### Prioriteta: NIZKA
- [ ] Frontend panel (3D vizualizacija)
- [ ] Blueprints za avtomatizacije
- [ ] Brands submission (icon za HA)
- [ ] Submission na HACS default repo

---

## Ideje

- [ ] Uporabi nDMP (normaliziran digitalni model povrsja) namesto raw point cloud — ze rasteriziran, GeoTIFF
- [ ] Thermal comfort zona: kombinacija UTCI + sencenje za priporocila
- [ ] Sneg na strehi: CLSS razred 21 (sneg) za detekcijo snega na PV panelih
- [ ] Multi-home podpora: vec lokacij v eni HA instanci
- [ ] Historicni podatki: primerjava LSS (stari) vs CLSS (novi) za detekcijo sprememb (nova stavba, posekano drevo)
- [ ] Integracija z Solcast ali Forecast.Solar za primerjavo PV napovedi

---

## Bugi

(Se ni znanih bugov — projekt se zacenja)

---

## Opombe

- CLSS podatki so CC 4.0 licenca — obvezna atribucija
- ARSO strežnik je rate-limited — paziti na intervale prenosov
- LAZ datoteke so velike (10 pts/m2) — chunk-based procesiranje obvezno
