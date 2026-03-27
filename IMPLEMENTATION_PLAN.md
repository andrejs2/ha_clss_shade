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

### 4.4 Frontend panel — 2D editor (obstoječe)
- [x] Leaflet karta s satelitsko podlago
- [x] Leaflet.Draw za risanje poligonov
- [x] WebSocket API za shranjevanje/nalaganje con
- [x] Shadow overlay na karti
- [ ] Casovna os: animacija sence skozi dan

---

## Faza 5: 3D zone editor — KILLER FEATURE

Edinstvena funkcionalnost v HA ekosistemu: interaktivno 3D zoniranje na LiDAR modelu.
Omogoca zoniranje na **katerikoli povrsini** — tla, streha, fasada, pod napuscem, okna v bloku.

### 5.1 Three.js 3D viewer (osnova)
- [ ] DSM heightmap → Three.js PlaneGeometry mesh (800×800 grid, ~640K trikotnikov)
- [ ] DTM kot locen spodnji mesh (za tla pod stavbami)
- [ ] Barvanje po klasifikaciji: stavbe=siva, vegetacija=zelena, tla=rjava
- [ ] Satelitska tekstura iz WMS (DOF ali Esri) na ground mesh
- [ ] OrbitControls: vrtenje, zoom, pan z misko
- [ ] Preklop [2D] ↔ [3D] gumb v panelu
- [ ] Base64 prenos DSM/DTM/classification iz backend-a prek WebSocket

### 5.2 Skirt walls — vertikalne povrsine stavb
- [ ] Detekcija robov v DSM: celice z veliko vissinsko razliko (>1.5m)
- [ ] Generiranje vertikalnih quad meshev (stene) od DTM do DSM
  ```
  DSM[i,j]=8m, DSM[i+1,j]=0m → stena 0m→8m na robu
  ```
- [ ] Stene so del raycasting mesha — klikljive na katerikoli visini
- [ ] LOD: stene samo za stavbe blizje od 100m (performance)

### 5.3 3D zone drawing
- [ ] Raycasting iz miske na mesh (tla + streha + stene): Three.js Raycaster
  ```javascript
  raycaster.setFromCamera(mouse, camera);
  const hit = raycaster.intersectObjects([groundMesh, wallMesh, roofMesh]);
  // hit[0].point = {x, y, z} — tocen 3D polozaj klika
  ```
- [ ] Rezim "Nova cona": klik za postavljanje tock, double-klik za zakljucek
- [ ] Vizualizacija: tocke kot sfere, povezave kot crte, zapolnjen poligon
- [ ] Poligon se "prilepi" na mesh povrsino (tla, stena, streha)
- [ ] Podpora za razlicne tipe con:
  - **Horizontalna** (tla, streha, terasa) — kot zdaj
  - **Vertikalna** (fasada, okna) — tocke na steni
  - **Pod napuscem** — tocke na tleh pod streho
  - **Mesana** — tocke na razlicnih povrsninah
- [ ] Shranjevanje: 3D koordinate [{x, y, z}, ...] v config entry
- [ ] WebSocket endpoint za CRUD operacije nad 3D conami

### 5.4 Shadow engine razsiritev za 3D cone
- [ ] Nova funkcija: `is_point_in_sun_3d(x, y, z, sun, dsm)`
  - Zacne ray-march na (x, y, z) namesto dsm[y][x]
  - Sledi zarku proti soncu cez DSM grid
  - Vrne True/False (sonce/senca)
- [ ] `compute_zone_sun_3d(zone_points_3d, dsm, sun)` → sun_percent
  - Za vsako tocko v coni: trace ray iz (x,y,z)
  - Vkljucuje interpolacijo med tockami za vecjo natancnost
- [ ] Backward compatible: obstojoce 2D cone delajo kot prej
- [ ] Vertikalne cone: sun_percent na fasadi za zaluzije

### 5.5 Primeri uporabe — 3D cone

```
Stolpnica (blok), fasada JZ:
  Tocke na steni od z=9m do z=12m (4. nadstropje)
  → Senzor: "okna_4nadstropje_sun_percent: 67%"
  → Avtomatizacija: zapri zaluzije ko sun% > 50

Hisa, terasa pod napuscem:
  Tocke na tleh (z=0) pod stresnim napuscem (3.5m)
  → Senzor: "terasa_napusc_sun_percent: 0%" (poleti)
  → Senzor: "terasa_napusc_sun_percent: 85%" (pozimi)

PV paneli na strehi bloka:
  Tocke na strehi (z=15m) → natancna senca od sosednjega bloka
  → Boljse kot 2D ker uposteva visino obeh stavb
```

### 5.6 UI/UX
- [ ] Toolbar: [2D] [3D] [Sonce/Senca] [Napoved] [+ Cona]
- [ ] Casovni drsnik: pomikaj cas, glej kako se senca premika v 3D
- [ ] Seznam con v stranskem panelu z sun% in barvnim indikatorjem
- [ ] Fly mode (WASD + miska) za "sprehod" skozi model (opcijsko)
- [ ] Mobilna podpora: touch orbit controls

### 5.7 Tehnicni stack
| Komponenta | Tehnologija |
|---|---|
| 3D rendering | Three.js (ES modules, CDN) |
| Kamera | OrbitControls + opcijski FlyControls |
| 2D karta | Leaflet (obstoječe) |
| Raycasting | Three.js Raycaster |
| Podatkovni prenos | WebSocket + base64 float32 arrayi |
| Panel hosting | HA async_register_built_in_panel (iframe) |
| Brez build toolchaina | En HTML file, CDN knjiznice |

---

## Faza 6: HACS in objava

### 6.1 HACS kompatibilnost
- [ ] hacs.json konfiguracija
- [ ] GitHub Actions (hassfest + HACS validation)
- [ ] Brands submission (icon)
- [ ] README z HACS install gumbom

### 6.2 Testiranje
- [ ] Unit testi za geo.py, rasterizer.py, shadow_engine.py
- [ ] Integration testi za config_flow
- [ ] Test z realnimi CLSS podatki (Ljubljana)

### 6.3 Dokumentacija
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
