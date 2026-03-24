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
- `https://api.open-meteo.com/v1/forecast`
- Soncno sevanje (GHI, DNI, DHI) — backup ce ARSO ni na voljo
- Brezplacen, brez API kljuca

### E-prostor OGC servisi
- WMS/WFS/WMTS na `https://www.e-prostor.gov.si/`
- Predvsem za vektorske/katastrske podatke, ne za tockovni oblak
- Morda uporabno za parcele, stavbe (kot dopolnilo LiDAR)
