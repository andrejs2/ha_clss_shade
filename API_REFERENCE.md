# API Reference — Viri podatkov

## 1. ARSO LiDAR strežnik (LSS — stari podatki)

### Base URL
```
http://gis.arso.gov.si/lidar/
```

### Produkti

| Produkt | Pot | Koncnica | Opis |
|---------|-----|----------|------|
| GKOT (LAZ) | `GKOT/laz/b_{block}/D96TM/` | `.laz` | Georeferencirani klasificirani oblak tock |
| GKOT (ZLAS) | `GKOT/b_{block}/D96TM/` | `.zlas` | Isto, ZLAS format |
| OTR (LAZ) | `OTR/laz/b_{block}/D96TM/` | `.laz` | Odmera terena |
| DMR | `dmr1/b_{block}/D96TM/` | `.asc` | Digitalni model reliefa (ASCII grid) |

### URL vzorec
```
http://gis.arso.gov.si/lidar/GKOT/laz/b_{block}/D96TM/TM_{tileE}_{tileN}.laz
```

### Tile poimenovanje
- Format: `TM_{eastingKm}_{northingKm}.laz`
- Velikost: 1 x 1 km
- Koordinatni sistem: EPSG:3794 (D96/TM)
- eastingKm = floor(easting / 1000)
- northingKm = floor(northing / 1000)

### Block number
Reseno z avtomatskim HEAD probingom (concurrent, 5 hkrati, range b_1-b_60).
Rezultat se kesira v `block_cache.json`. Mapiranje odkrito 2026-03-24:

| Block | Priblizno obmocje | Vzorcni tili |
|-------|-------------------|--------------|
| b_11 | Notranjska | TM_400_80 |
| b_12 | Dolenjska/Bela krajina | TM_420_80, TM_440_60, TM_460_60 |
| b_13 | Posavje | TM_460_80, TM_480_60 |
| b_14 | Stajerska jug | TM_500_80, TM_520_100, TM_540_100 |
| b_15 | Kocevje | TM_420_40, TM_440_40 |
| b_16 | Obsotelje | TM_480_80, TM_500_40, TM_520_60 |
| b_21 | Koper/Primorska | TM_400_40 |
| b_22 | Stajerska sever | TM_500_120, TM_540_120 |
| b_23 | Ptuj/Ormoz | TM_500_140, TM_540_160 |
| b_24 | Pomurje JV | TM_580_140, TM_600_180 |
| b_25 | Pomurje JZ | TM_560_140, TM_560_160 |
| b_26 | Maribor | TM_560_120 |
| b_31 | Gorenjska sever | TM_440_140, TM_480_140 |
| b_32 | Skofja Loka/Cerkno | TM_420_100, TM_440_100 |
| b_33 | Idrija/Tolmin | TM_380_120, TM_400_100 |
| b_34 | Zasavje/Trbovlje | TM_480_120 |
| b_35 | Ljubljana | TM_460_100, TM_480_100 |
| b_36 | Kranj | TM_440_120, TM_460_120 |
| b_37 | Goriska/Bovec | TM_400_140, TM_420_140 |

---

## 2. CLSS portal (novi podatki 2023-2025)

### Pregledovalnik
- URL: `https://lift.clss.si/`
- Uporablja GMS SDK za vizualizacijo
- Sharelinks: base64-encoded state v URL

### Podatki
- Tockovni oblak: LAZ 1.4, 10 pts/m2
- DMR: Digitalni model reliefa (LAZ)
- DMP: Digitalni model povrsja (LAZ)
- **nDMP: Normaliziran DMP (GeoTIFF)** — ze rasteriziran, morda uporaben namesto raw LAZ
- PAS: Analiticno sencenje (GeoTIFF)
- POF: Ortofoto RGB+NIR (GeoTIFF)

### Prenos podatkov
- JGP portal: `https://ipi.eprostor.gov.si/jgp` (JavaScript app, ni REST API)
- Bulk narocilo: `gic.gu@gov.si`
- E-prostor: `https://www.e-prostor.gov.si/dostopnost/`

---

## 3. CLSS klasifikacija (21 razredov)

| Razred | Opis | Uporaba v shadow engine |
|--------|------|------------------------|
| 0 | Nerazvrsceno (izven obmocja) | Ignoriraj |
| 1 | Nerazvrsceno (splosno) | Ignoriraj |
| 2 | Tla | DTM, 100% prepustnost |
| 3 | Nizka vegetacija (<3m) | 60% prepustnost |
| 4 | Srednja vegetacija (3-10m) | 40% prepustnost |
| 5 | Visoka vegetacija (>10m) | 15-65% sezonsko |
| 6 | Stavbe (strehe + fasade) | 0% prepustnost |
| 7 | Nizke tocke (garaze, stopnice) | Filtriraj |
| 9 | Voda | 100% prepustnost |
| 17 | Mostovi in viadukti | Filtriraj |
| 18 | Sum (odboji napak) | Filtriraj |
| 21 | Sneg | Filtriraj (ali uporabi za PV sneg detekcijo) |

---

## 4. Koordinatni sistem EPSG:3794 (D96/TM)

### Parametri
- Projekcija: Transverzalni Merkator
- Centralni meridian: 15°E
- Faktor merila: 0.9999
- False easting: 500000 m
- False northing: -5000000 m
- Elipsoid: GRS80
- Datum: Slovenia Geodetic Datum 1996

### Obmocje Slovenije (priblizno)
- Lat: 45.42° — 46.88° N
- Lon: 13.38° — 16.61° E
- Easting: ~374000 — ~626000
- Northing: ~32000 — ~195000

---

## 5. ARSO vremenski API-ji (prek slovenian_weather_integration)

Te podatke beremo iz HA entitet, ne neposredno iz API-ja.

### Kljucne entitete za nas projekt

| Entiteta | Podatek | Enota |
|----------|---------|-------|
| `sensor.arso_weather_{loc}_globalno_soncno_sevanje` | Globalno soncno sevanje | W/m2 |
| `sensor.arso_weather_{loc}_difuzno_soncno_sevanje` | Difuzno soncno sevanje | W/m2 |
| `sensor.arso_agrometeo_{sta}_evapotranspiracija` | Evapotranspiracija | mm |
| `sensor.arso_agrometeo_{sta}_vodna_bilanca` | Vodna bilanca (proxy vlaga tal) | mm |
| `sensor.arso_weather_{loc}_temperatura` | Temperatura | °C |
| `sensor.arso_weather_{loc}_relativna_vlaznost` | Relativna vlaznost | % |
| `sensor.arso_weather_{loc}_oblacnost` | Oblacnost | % |

### Napovedi (prek weather entitete)
- Urne napovedi (3h intervali, 6 dni)
- Dnevne napovedi (10 dni)
- Padavine: `tp_acc` (mm per interval)

### Agrometeo API (za referenco)
- Opazovanja: `https://meteo.arso.gov.si/.../agromet/json/sl/observationKlima_si-agro.json`
- Napovedi: `https://meteo.arso.gov.si/.../agromet/json/sl/forecastKlima_si-agro.json`
- 36 postaj po Sloveniji
- Update interval: 60 minut

---

## 6. Uporabni zunanji viri

### QGIS plugin za prenos LiDAR
- GitHub: `https://github.com/nejcd/LidarSloveniaDataDownloader`
- Avtomatizira prenos iz ARSO streznika
- Zahteva tile koordinate IN block number kot vnos

### HA_Solar_Shade (referenca za shadow engine)
- GitHub: `https://github.com/LawPaul/HA_Solar_Shade`
- Shadow engine: ray-marching, transmitanca, raised canopy model
- Manual LAZ mode ze podpira poljubne LAZ datoteke

### Open-Meteo (globalni vremenski API)
- **Forecast**: `https://api.open-meteo.com/v1/forecast`
  - Trenutni GHI (15-min): `?minutely_15=shortwave_radiation_instant`
  - Urni forecast (5 dni): `?hourly=shortwave_radiation,temperature_2m,cloud_cover&forecast_days=5`
  - Primarni vir za PV forecast (neposreden GHI namesto cloud modela)
- **Elevation**: `https://api.open-meteo.com/v1/elevation`
  - Copernicus 30m DEM, batch query (comma-separated lat/lon)
  - Uporabljen za horizon profil (72 azimutov × 20 razdalj)
  - Rate limit: ~100 točk/request, potreben delay med requesti
- Brezplacen, brez API kljuca, globalna pokritost

### E-prostor OGC servisi
- WMS/WFS/WMTS na `https://www.e-prostor.gov.si/`
- Predvsem za vektorske/katastrske podatke, ne za tockovni oblak
- Morda uporabno za parcele, stavbe (kot dopolnilo LiDAR)

---

## 7. ARSO INCA — Nowcasting (za Fazo 3 PV napoved)

### Pregled
INCA (Integrated Nowcasting through Comprehensive Analysis) — ARSO sistem za
kratkorocno vremensko napoved z visoko resolucijo.
- **Resolucija**: 1 km grid cez celo Slovenijo
- **Posodobitev**: vsake 5-15 minut
- **Napoved**: do +6 ur (nowcasting)
- **Spletni pregledovalnik**: https://meteo.arso.gov.si/uploads/meteo/app/inca/

### JSON API endpointi

Base URL: `https://meteo.arso.gov.si/uploads/probase/www/nowcast/inca/`

| Endpoint | Podatek | Interval |
|----------|---------|----------|
| `inca_si0zm_data.json?prod=si0zm` | **Soncno sevanje (GHI)** | 5 min |
| `inca_t2m_data.json?prod=t2m` | Temperatura 2m | 1 ura |
| `inca_hp_data.json?prod=hp` | Padavine | 5 min |
| `inca_sp_data.json?prod=sp` | Tlak | ? |
| `inca_wind_data.json?prod=wind` | Veter | ? |

### Struktura JSON odgovora

```json
[
  {
    "mode": "ANL",
    "path": "/uploads/probase/www/nowcast/inca/inca_si0zm_20260325-1240+0000.png",
    "date": "202603251240",
    "hhmm": "1240",
    "bbox": "44.67,12.1,47.42,17.44",
    "width": "800",
    "height": "600",
    "valid": "2026-03-25T12:40:00Z"
  }
]
```

- `mode`: "ANL" (analiza/meritev) ali potencialno "FC" (napoved)
- `path`: pot do PNG slike na ARSO strezniku
- `bbox`: lat_min,lon_min,lat_max,lon_max (WGS84)
- `width/height`: velikost PNG v pikslih

### Branje vrednosti za specificno lokacijo

Podatki so zakodirani kot piksel vrednosti v PNG slikah.
Za branje za doloceno lat/lon:

```python
# 1. Izracunaj pixel koordinato iz bbox
bbox = [44.67, 12.1, 47.42, 17.44]  # lat_min, lon_min, lat_max, lon_max
pixel_x = int((lon - bbox[1]) / (bbox[3] - bbox[1]) * width)
pixel_y = int((bbox[2] - lat) / (bbox[2] - bbox[0]) * height)

# 2. Prenesi PNG in preberi pixel
# 3. Pretvori pixel vrednost v fizikalno enoto (barvna skala)
```

### Odprta vprasanja
- Barvna skala: kako pretvoriti pixel RGB v W/m2 (sevanje) ali mm (padavine)?
- Ali obstajajo FC (forecast) endpointi poleg ANL (analiza)?
- Ali je morda kje GeoTIFF ali NetCDF verzija namesto PNG?
- Rate limiting: koliko pogosto smemo klicati?

### Uporaba za CLSS Shade (Faza 3)
`si0zm` (soncno sevanje na 5 min / 1 km) je idealen vir za PV nowcast:
- Lokacijsko specificen (ne ena postaja za celo mesto)
- Visoka casovna resolucija (5 min vs 30 min za ARSO postaje)
- Zdruziti z shadow engine + POA model = natancna PV napoved za +6h

---

## 5. SolarEdge Monitoring API

### Base URL
```
https://monitoringapi.solaredge.com
```

### Avtentikacija
API kljuc kot URL parameter: `?api_key=XXXXXXXX`
Kljuc se dobi v: Monitoring portal → Admin → Site Access → API Access

### Site ID
`2115036` (MSE TINA SERŠEN, Ljubljana-Dobrunje)

### Podatki sistema
- Peak power: 11.06 kWp
- Paneli: JinkoSolar JKM-395N-6RL3-V Tiger (395 Wp)
- Temp. koeficient: -0.34 %/°C
- Inverter: SolarEdge SE16K-RW0T0BNN4 (S/N: 7E09AD66-9A)
- Lokacija: lat=46.0383376, lon=14.6116002
- Podatki od: 2021-03-02

### Ključni endpointi

| Endpoint | Path | Resolucija | Max period |
|----------|------|------------|------------|
| Overview | `/site/{id}/overview` | Trenutno | - |
| Data Period | `/site/{id}/dataPeriod` | - | - |
| Energy | `/site/{id}/energy?timeUnit=X&startDate=Y&endDate=Z` | 15min/H/D/M/Y | 1 leto (D) |
| Energy Details | `/site/{id}/energyDetails?timeUnit=X&...&meters=M` | 15min/H/D/M | 1 mesec |
| Power | `/site/{id}/power?startTime=Y&endTime=Z` | 15 min | 1 mesec |
| Inverter Data | `/equipment/{id}/{serial}/data?startTime=Y&endTime=Z` | 5 min | 1 teden |

Meters za energyDetails: `Production,Consumption,SelfConsumption,FeedIn,Purchased`

### Omejitve
- 300 requestov/dan
- Max 300 parallel per site

### Podatki sistema
- Paneli: 35° nagib, 220° azimut (SSW)
- Temp. koeficient: -0.34 %/°C (JinkoSolar Tiger spec)

### Mesečni vremenski faktorji (iz 5 let podatkov 2021-2026)
```
weather_factor = dejanska_proizvodnja / Haurwitz_clearsky(35°/220°)
```

| Mesec | Weather factor | Best day PR | Opis |
|-------|---------------|-------------|------|
| Jan | 0.356 | 108% | Megla, oblačno |
| Feb | 0.458 | 106% | Megla/oblačno |
| Mar | 0.598 | 111% | Zmerno oblačno |
| Apr | 0.624 | 110% | Zmerno oblačno |
| Maj | 0.576 | 107% | Zmerno oblačno |
| Jun | 0.707 | 99% | Jasni meseci |
| Jul | 0.710 | 96% | Jasni meseci |
| Avg | 0.695 | 98% | Jasni meseci |
| Sep | 0.620 | 105% | Zmerno oblačno |
| Okt | 0.499 | 102% | Zmerno oblačno |
| Nov | 0.364 | 98% | Megla, oblačno |
| Dec | 0.251 | 98% | Megla, oblačno |

Letni weather factor: 57.6%
Letni specifični donos: ~1121 kWh/kWp

### Ključna opažanja iz profila
- **Jutranje sencenje**: ob 8:00 samo 11-38% modela → ovira na vzhodu
- **Opoldne**: model se ujema 95-110% → Haurwitz natančen
- **Best day PR > 100%** (spomladi): mogoče albedo od snega ali višja prozornost
