# CLSS Shade — Implementacijski nacrt

## Pregled

Home Assistant custom integracija, ki uporablja slovenske CLSS (Ciklicno Lasersko Skeniranje Slovenije)
LiDAR podatke za analizo sencenja/osoncenja. Kombinira se s `slovenian_weather_integration` za
napredno upravljanje sencenja, zalivanja in predikcijo PV proizvodnje.

---

## Faza 1: Temelj (geo + download)

### 1.1 `geo.py` — Koordinatne pretvorbe
- [ ] WGS84 (lat/lon) <-> EPSG:3794 (D96/TM) pretvorba
- [ ] Izracun tile koordinat iz lat/lon: `tileE = floor(easting/1000)`, `tileN = floor(northing/1000)`
- [ ] Dolocitev potrebnih tilov za dani radij okoli lokacije
- [ ] Unit testi za znane koordinate (Ljubljana, Maribor, Koper)

### 1.2 `slovenian_downloader.py` — Pridobivanje LAZ podatkov
- [ ] Tile discovery: lat/lon -> seznam potrebnih LAZ datotek
- [ ] Sestava ARSO URL: `http://gis.arso.gov.si/lidar/GKOT/laz/b_{block}/D96TM/TM_{tileE}_{tileN}.laz`
- [ ] Resitev problema block numberja (lookup tabela / scraping / CLSS API)
- [ ] Async download z progress reportingom
- [ ] Lokalno kesirnaje (ne prenasaj znova)
- [ ] Fallback na manual LAZ (uporabnik polozi datoteko)
- [ ] Preverjanje CLSS novih podatkov vs stari LSS

### 1.3 `rasterizer.py` — LAZ -> numpy arrays
- [ ] Branje LAZ 1.4 z laspy (chunk-based za velike datoteke)
- [ ] Clip na radij okoli lokacije (privzeto 500m)
- [ ] DSM (Digital Surface Model) — max Z per cell
- [ ] DTM (Digital Terrain Model) — mean Z razreda 2 (tla)
- [ ] Klasifikacijski grid (razred najvisje tocke per cell)
- [ ] Canopy base grid (najnizji non-ground return >2m nad DTM)
- [ ] Auto-izracun resolucije iz gostote tock (~4 tocke/celico)
- [ ] Gap-filling z interpolacijo
- [ ] Filtriranje razredov 7,17,18,21 (sum, mostovi, nizke tocke, sneg)
- [ ] Shranjevanje v .npz format (DSM, DTM, classification, canopy_base, resolution, extents)

---

## Faza 2: Shadow engine

### 2.1 `shadow_engine.py` — Izracun sencenja
- [ ] Izracun polozaja sonca (azimut, elevacija) iz lokacije in casa
- [ ] Ray-marching po DSM gridu proti soncu
- [ ] Transmitanca glede na klasifikacijo:
  - Stavbe (6): 0% prepustnost
  - Visoka vegetacija (5): 15-65% sezonsko
  - Srednja vegetacija (4): 40%
  - Nizka vegetacija (3): 60%
  - Tla (2): 100%
- [ ] "Raised canopy" model: zarki pod krono dreves (trunk zona) prosti
- [ ] Sezonski model vegetacije (leaf-on/leaf-off glede na datum)
- [ ] Output: float shadow map (0.0=polno sonce, 1.0=polna senca)
- [ ] Optimizacija: numpy vectorized operacije

### 2.2 Zone in senzorji
- [ ] Definicija con (poligoni) — streha, vrt, terasa, itd.
- [ ] Rasterizacija poligonov na grid
- [ ] Izracun sencnega deleza per cona
- [ ] Casovna serija sencenja skozi dan (za napoved)

---

## Faza 3: HA integracija

### 3.1 `config_flow.py` — Konfiguracija
- [ ] Step 1: Lokacija (lat/lon ali izberi iz HA config)
- [ ] Step 2: Radij LiDAR podatkov (privzeto 500m)
- [ ] Step 3: Definicija con (streha PV, vrt, terasa)
- [ ] Options flow za posodabljanje nastavitev

### 3.2 `coordinator.py` — Data coordinator
- [ ] DataUpdateCoordinator za periodicno posodabljanje shadow map
- [ ] Privzeti interval: 5 minut
- [ ] Branje vremenskih podatkov iz slovenian_weather_integration entitet
- [ ] Trigger ob spremembi soncnega polozaja

### 3.3 `sensor.py` — Senzorji
- [ ] `sensor.clss_shade_{zone}_shade_percent` — % sence per cona
- [ ] `sensor.clss_shade_{zone}_sun_hours_today` — ure sonca danes
- [ ] `sensor.clss_shade_{zone}_sun_hours_forecast` — napoved ur sonca
- [ ] `sensor.clss_shade_pv_estimate` — ocena PV proizvodnje (W)
- [ ] `sensor.clss_shade_irrigation_need` — potreba po zalivanju (mm)
- [ ] `sensor.clss_shade_next_shade_change` — kdaj se senca spremeni

### 3.4 `__init__.py` — Setup
- [ ] async_setup_entry / async_unload_entry
- [ ] Background download ob prvem setupu
- [ ] Cache management
- [ ] Runtime data pattern (ArsoRuntimeData vzorec)

---

## Faza 4: Napredne funkcije

### 4.1 PV predikcija
- [ ] Kombinacija shadow map + ARSO globalno soncno sevanje
- [ ] Upostevanje napovedi oblacnosti
- [ ] Urna napoved proizvodnje za naslednje dni
- [ ] Integracija z energy dashboard

### 4.2 Pametno zalivanje
- [ ] Evapotranspiracija iz agrometeo + shadow map per cona
- [ ] Vodna bilanca iz agrometeo
- [ ] Napoved padavin -> zmanjsaj zalivanje
- [ ] Output: priporocena kolicina zalivanja per cona (mm)

### 4.3 Pametno sencenje
- [ ] Soncni polozaj + shadow map -> katera okna so osoncena
- [ ] Napoved: kdaj bo sonce prislo/slo na posamezno okno
- [ ] Temperaturni podatki -> ali je sencenje zazeleno
- [ ] Avtomatizacija rolet/zunanjih sencil

### 4.4 Frontend panel (opcijsko)
- [ ] WebSocket API za interaktivni prikaz
- [ ] 3D vizualizacija sencenja na karti
- [ ] Casovna os: animacija sence skozi dan

---

## Faza 5: HACS in objava

### 5.1 HACS kompatibilnost
- [ ] hacs.json konfiguracija
- [ ] GitHub Actions (hassfest + HACS validation)
- [ ] Brands submission (icon)
- [ ] README z HACS install gumbom

### 5.2 Testiranje
- [ ] Unit testi za geo.py, rasterizer.py, shadow_engine.py
- [ ] Integration testi za config_flow
- [ ] Test z realnimi CLSS podatki (Ljubljana)

### 5.3 Dokumentacija
- [ ] README.md z navodili za namestitev
- [ ] Primeri avtomatizacij (blueprints)
- [ ] Screenshots

---

## Odvisnosti

```
numpy>=1.21          # Numericne operacije, shadow engine
laspy>=2.0,<3.0      # Branje LAZ datotek
laszip>=0.2.1        # LAZ dekompresija
pyproj>=3.0          # Koordinatne pretvorbe (EPSG:3794)
```

## Povezane integracije

- `slovenian_weather_integration` — ARSO vremeski podatki, agrometeo, soncno sevanje
- Branje prek HA state machine: `hass.states.get("sensor.arso_*")`
