[![Python][python-shield]][python]
[![License][license-shield]][license]
[![Maintainer][maintainer-shield]][maintainer]
[![Home Assistant][homeassistant-shield]][homeassistant]
[![HACS][hacs-shield]][hacs]

![Hassfest](https://img.shields.io/github/actions/workflow/status/andrejs2/ha_clss_shade/hassfest.yaml?branch=main&label=Hassfest&style=for-the-badge&logo=home-assistant)
![HACS Validation](https://img.shields.io/github/actions/workflow/status/andrejs2/ha_clss_shade/validate.yaml?branch=main&label=HACS%20Validation&style=for-the-badge&logo=home-assistant)
[![GitHub Release](https://img.shields.io/github/v/release/andrejs2/ha_clss_shade?style=for-the-badge)](https://github.com/andrejs2/ha_clss_shade/releases)

![Made in Slovenia](https://img.shields.io/badge/Made_in-Slovenia-005DA4?style=for-the-badge&logo=flag&logoColor=white)

[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![GitHub Sponsors][github-shield]][github]

[<img src="https://em-content.zobj.net/thumbs/240/microsoft/319/rocket_1f680.png" alt="Install" width="30"/> ![Install via HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrejs2&repository=ha_clss_shade&category=integration)

# CLSS Shade — Analiza senčenja na podlagi LiDAR podatkov za Home Assistant

## Pregled

**CLSS Shade** je Home Assistant integracija, ki uporablja podatke **Cikličnega laserskega skeniranja Slovenije (CLSS)** za natančno analizo senčenja vašega doma in okolice. Na podlagi visoko-resolucijskega 3D oblaka točk (10 tock/m², resolucija 0.5 m) integracija izračuna, kateri deli vasega doma, vrta in strehe so v danem trenutku na soncu in kateri v senci.

V kombinaciji z vremenskimi podatki iz integracije [ARSO Weather (slovenian_weather_integration)](https://github.com/andrejs2/slovenian_weather_integration) ponuja:

- **Natančno analizo senčenja** na podlagi dejanskega 3D modela okolice (stavbe, drevesa, teren)
- **Oceno PV proizvodnje** — koliko električne energije vaš sončni sistem dejansko proizvaja glede na senčenje strehe in izmerjeno sončno sevanje
- **Pametno zalivanje** — koliko vode potrebuje posamezna cona vrta glede na osončenje, evapotranspiracijo in napoved padavin
- **Avtomatizacijo senčil in rolet** — katera okna so osončena in kdaj bo sonce vzšlo ali zašlo

---

## Kako deluje

Integracija ob prvi nastavitvi prenese LiDAR podatke iz strežnika Portala Prostor (Geodetska uprava RS) — en LiDAR tile velikosti 1×1 km (~30-50 MB), ki pokriva izbrano lokacijo. Iz oblaka točk zgradi digitalni model površja (DSM) in terena (DTM), nato pa vsakih 5 minut izvede izračun senčenja na podlagi trenutnega položaja sonca.

### Princip delovanja

```
1. Prenos LiDAR podatkov (enkratno)
   ARSO streznik → LAZ datoteka → DSM/DTM grid (800×800 celic pri 200m radiju)

2. Izračun senčenja (vsakih 5 minut)
   Polozaj sonca + DSM grid → Ray-marching → Senčna mapa

3. Analiza po conah (avtomatska detekcija)
   LiDAR klasifikacija → Streha / Vrt / Drevesa / Odprto

4. Kombinacija z vremenskimi podatki (opcijsko)
   Senca mapa + ARSO sončno sevanje → PV ocena
   Senca mapa + ARSO agrometeo → Zalivanje
```

### Ray-marching algoritem

Za vsako celico v gridu integracija "streli" zarek proti soncu in preveri, ali kaksen objekt (stavba, drevo) prepreci pot svetlobe. Uposteva tudi sezonske spremembe — pozimi, ko drevesa nimajo listov, prepuscajo vec svetlobe (65%) kot poleti z listi (15%).

| Razred | Opis | Prepustnost |
|--------|------|-------------|
| Stavbe | Strehe, fasade | 0% (popolnoma neprepustne) |
| Visoka vegetacija (>10 m) | Drevesa | 15-65% (sezonsko) |
| Srednja vegetacija (3-10 m) | Grmovje, mlada drevesa | 40% |
| Nizka vegetacija (<3 m) | Trava, grmicevje | 60% |
| Tla | Tla, ceste | 100% (prepustna) |

**Sezonski model vegetacije:**

| Obdobje | Meseci | Prepustnost dreves | Opis |
|---------|--------|---------------------|------|
| Polno listje | jun-sep | 15% | Gosta krona |
| Delno listje | apr, maj, okt, nov | 40% | Prehodno obdobje |
| Brez listja | dec-mar | 65% | Gola drevesa |

---

## Podatkovni viri

### LiDAR podatki — CLSS (Ciklicno Lasersko Skeniranje Slovenije)

Integracija uporablja podatke iz projekta **CLSS 2023-2025**, ki ga izvaja Flycom Technologies po narocilu Geodetske uprave RS (GURS). Gre za drugo sistematicno lasersko skeniranje celotne Slovenije.

| Lastnost | Vrednost |
|----------|---------|
| Gostota tock | 10 tock/m² |
| Format | LAZ 1.4 |
| Koordinatni sistem | EPSG:3794 (D96/TM) |
| Velikost ploscice | 1×1 km |
| Pokritost | Celotna Slovenija |
| Klasifikacija | 21 razredov (ASPRS) |
| Licenca | Creative Commons 4.0 (obvezna atribucija) |

Podatki so na voljo na strežniku ARSO: `gis.arso.gov.si/lidar/`. Integracija avtomatsko doloci pravo ploscico in jo prenese.

Pregled podatkov: [CLSS pregledovalnik](https://clss.si) | [E-prostor](https://www.e-prostor.gov.si/dostopnost/) | [Navodila za pregledovalnik (PDF)](https://assets.flycom.si/clss/navodila_pregledovalnik_clss.pdf)

### Vremenski podatki — ARSO (opcijsko)

Ce imate nameščeno integracijo [ARSO Weather](https://github.com/andrejs2/slovenian_weather_integration), CLSS Shade samodejno prebere naslednje senzorje:

| Podatek | Entiteta | Uporaba |
|---------|----------|---------|
| Globalno soncno sevanje | `sensor.arso_weather_*_globalno_soncno_sevanje` | PV ocena |
| Difuzno soncno sevanje | `sensor.arso_weather_*_difuzno_soncno_sevanje` | PV ocena |
| Evapotranspiracija | `sensor.arso_agrometeo_*_evapotranspiracija` | Zalivanje |
| Vodna bilanca | `sensor.arso_agrometeo_*_vodna_bilanca` | Zalivanje |
| Oblacnost | `sensor.arso_weather_*_oblacnost` | Napoved |
| Temperatura | `sensor.arso_weather_*_temperatura` | Kontekst |

Za PV oceno in zalivanje je **priporocena** namestitev ARSO Weather integracije z omogocenim modulom Agrometeo.

---

## Funkcionalnosti

### Senzorji

Integracija ustvari naslednje senzorje:

#### Globalni senzorji (vedno na voljo)

| Senzor | Enota | Opis |
|--------|-------|------|
| **Senca** | % | Povprecni delez sence na celotnem obmocju |
| **Sonce** | % | Povprecni delez sonca na celotnem obmocju |
| **Visina sonca** | ° | Kot sonca nad obzorjem (0° = obzorje, 90° = zenit) |
| **Azimut sonca** | ° | Smer sonca (0° = sever, 90° = vzhod, 180° = jug, 270° = zahod) |
| **Dnevna svetloba** | da/ne | Ali je sonce nad obzorjem |
| **Oblacnost** | % | Oblacnost iz ARSO vremenskih podatkov |
| **Ocena PV moci** | W | Ocena trenutne proizvodnje z dinamicnim POA izracunom |
| **Realna PV moc** | W | Dejanska proizvodnja iz inverterja (opcijsko) |
| **PV faktor ucinkovitosti** | - | Razmerje realno/ocena (1.0 = idealno) |
| **Potreba po zalivanju** | L | Ocenjena dnevna potreba po zalivanju za vrt |

#### Senzorji napovedi PV proizvodnje

| Senzor | Enota | Opis |
|--------|-------|------|
| **PV napoved danes** | kWh | Napovedana skupna proizvodnja danes |
| **PV napoved jutri** | kWh | Napovedana skupna proizvodnja jutri |
| **PV napoved 5 dni** | kWh | Skupni sesteved 5-dnevne napovedi |
| **PV napoved naslednja ura** | W | Ocenjena moc v naslednji uri |
| **PV naslednja ura Wh** | Wh | Energija v naslednji 1 uri |
| **PV naslednje 3 ure Wh** | Wh | Energija v naslednjih 3 urah |
| **PV preostanek danes** | kWh | Preostala napovedana proizvodnja danes |

Vsak senzor napovedi danes/jutri/5-dni ima atribut `forecast_hourly` z urno razporeditvijo za grafe (ApexCharts).

#### Senzorji po conah (avtomatska detekcija)

Integracija samodejno prepozna cone iz LiDAR klasifikacije in za vsako ustvari dva senzorja:

| Cona | Opis | Senzorji |
|------|------|----------|
| **Streha** (roof) | Celice klasificirane kot stavba (razred 6) | Senca %, Sonce % |
| **Vrt** (garden) | Tla in nizka vegetacija v radiju 50 m od stavbe | Senca %, Sonce % |
| **Drevesa** (trees) | Srednja in visoka vegetacija | Senca %, Sonce % |
| **Odprto** (open) | Tla dalec od stavb | Senca %, Sonce % |

Vsak senzor cone ima tudi atribute: `area_m2` (povrsina v m²) in `cell_count` (stevilo celic v gridu).

#### Uporabniske cone (Zone Editor)

Poleg avtomatsko zaznanih con lahko v **Zone Editorju** (CLSS Shade panel v stranski vrstici) narisite lastne poligone na satelitski karti. Podprtih je vec kartografskih slojev (Google Satelit, Google Hybrid, Esri, OpenStreetMap) z visoko resolucijo za natancno risanje.

Primeri uporabniskih con:
- **Fasadne cone** — ozke cone pred okni za avtomatizacijo zaluzij
- **Vrtne cone** — borovnice, zelenjava, trata
- **PV paneli** — natancen poligon namesto celotne strehe
- **Terasa, parkirisce, bazen** — poljubne cone

Po shranjevanju in ponovnem zagonu se za vsako cono ustvarijo senzorji `{ime}_shade_percent` in `{ime}_sun_percent`.

### PV ocena

Integracija izracuna oceno PV proizvodnje z uporabo **dinamicnega POA (Plane-of-Array)** izracuna, ki uposteva orientacijo panelov in trenutni polozaj sonca.

#### Nastavitev PV sistema

V **Nastavitve > Naprave > CLSS Shade > Nastavi** vnesite:

| Polje | Opis | Primer |
|-------|------|--------|
| **PV cone in kapaciteta** | `cona:Wp` pari, loceni z vejico | `pv-visja:5925,pv-nizja:5135` |
| **Nagib panelov** | Stopinje od vodoravne (0-90°) | `30` |
| **Azimut panelov** | Smer panelov (0°=S, 90°=V, 180°=J, 270°=Z) | `180` |
| **Realna PV moc senzor** | Entity ID inverterja (opcijsko) | `sensor.solaredge_current_power` |

**Namig:** Narisite loceno PV cono za vsako gruco panelov na karti (Zone Editor), da bo izracun natancen.

#### Izracun

```
1. POA faktor = f(polozaj_sonca, nagib_panelov, azimut_panelov)
   — dinamicen, izracunan vsake 5 minut
   — uposteva da nagnjeni paneli lovijo vec sevanja kot horizontalni senzor

2. Za vsako PV cono:
   POA_sevanje = ARSO_GHI × POA_faktor
   Efektivno = POA_sevanje × (sonce% × 0.8 + 0.2)
   Moc = Kapaciteta_Wp × (Efektivno / 1000) × (1 - Izgube)

3. Skupna ocena = vsota vseh PV con
```

Kjer:
- **ARSO_GHI** = globalno horizontalno sevanje iz ARSO Weather (W/m²)
- **POA faktor** = `cos(θ_vpad) / sin(θ_elevacija)` × 0.7 + difuzni_faktor × 0.3
- **Sonce%** = delez direktnega sonca na PV coni iz shadow engine
- **Izgube** = 8% (inverter, kabliranje; privzeto za sisteme z optimizerji)

#### Faktor ucinkovitosti

Ce povezete realni PV senzor (SolarEdge, Fronius, Enphase...), integracija izracuna **faktor ucinkovitosti**:

```
Faktor = Realna_moc / Ocena_moci
```

| Faktor | Status | Pomen |
|--------|--------|-------|
| 0.85 – 1.15 | **Normalno** | Model se ujema z realnostjo |
| < 0.70 | **Nizka ucinkovitost** | Umazani paneli, okvara, nov objekt ki senci |
| > 1.30 | **Ocena prenizka** | Preverite nastavitve (nagib, azimut, kapaciteta) |

**Uporaba:** Faktor se uporablja za kalibracijo PV napovedi (EMA - eksponentno drsece povprecje).

### PV napoved proizvodnje (5 dni)

Integracija izracuna napoved PV proizvodnje za **5 dni naprej** z kombinacijo:

1. **Shadow forecast** — za vsako prihodnjo uro izracuna senco na PV conah iz 3D modela
2. **Vremenska napoved** — urna oblacnost iz ARSO Weather (`weather.get_forecasts`)
3. **POA faktor** — orientacija panelov glede na prihodnji polozaj sonca
4. **Performance factor EMA** — kalibracija iz preteklih meritev (realno vs ocena)

```
Za vsako uro v naslednjih 5 dneh:
  1. Polozaj sonca → senčna mapa → % sonca na PV conah
  2. Oblačnost napoved → cloud_factor (0.25 - 1.0)
  3. POA faktor iz kota sonca + nagib/azimut panelov
  4. Moč = kapaciteta × (sevanje × sonce% × 0.8 + 0.2) / 1000 × performance_factor
  5. Energija = vsota urnih moči → kWh/dan
```

#### Tiered intervali

Za optimalno ravnovesje med natancnostjo in zmogljivostjo:

| Dnevi | Interval korakov | Stevilo korakov | Natancnost |
|-------|-----------------|-----------------|------------|
| Danes + jutri | 30 min | 36 per dan | Visoka — za urne grafe |
| Dan 3-5 | 60 min | 18 per dan | Dovolj za dnevne skupne |

Skupni cas izracuna: ~2.7 min v ozadju, osvezitev vsako uro. Oddaljeni dnevi (3-5) se re-uporabijo iz cache-a do 3 ure.

#### Casovna okna

Poleg dnevnih skupnih vrednosti integracija izracuna tudi:

| Senzor | Opis | Uporaba |
|--------|------|---------|
| **Naslednja 1h** | Wh v naslednji uri | Kratkorocno planiranje |
| **Naslednje 3h** | Wh v naslednjih 3 urah | Kdaj pognati pomivalnik |
| **Preostanek danes** | kWh do konca dneva | Koliko energije se pricakujemo |

#### Atributi za grafe (ApexCharts)

Senzorji `pv_forecast_today_kwh`, `pv_forecast_tomorrow_kwh` in `pv_forecast_5day_kwh` imajo atribut `forecast_hourly` (oz. `forecast_hourly_5day`) z urno razporeditvijo:

```json
{
  "forecast_hourly": [
    {"time": "2026-03-26T06:00:00Z", "estimate_w": 450, "cloud_factor": 0.85, "cloud_coverage": 20, "sun_elevation": 12.5, "poa_factor": 1.15},
    {"time": "2026-03-26T06:30:00Z", "estimate_w": 920, "cloud_factor": 0.85, "cloud_coverage": 20, "sun_elevation": 18.3, "poa_factor": 1.22},
    ...
  ],
  "total_kwh": 18.5,
  "performance_factor_ema": 0.92
}
```

5-dnevni senzor ima dodatno `days` atribut:

```json
{
  "days": [
    {"date": "2026-03-26", "total_kwh": 18.5, "label": "danes"},
    {"date": "2026-03-27", "total_kwh": 14.2, "label": "jutri"},
    {"date": "2026-03-28", "total_kwh": 16.8, "label": "pet 28.03."},
    {"date": "2026-03-29", "total_kwh": 10.1, "label": "sob 29.03."},
    {"date": "2026-03-30", "total_kwh": 12.3, "label": "ned 30.03."}
  ]
}
```

### Pametno zalivanje

Ce je na voljo agrometeo podatki iz ARSO Weather, integracija izracuna dnevno potrebo po zalivanju:

```
Potreba = (ETP × Faktor_sence - Napoved_padavin) × Povrsina_vrta
```

Kjer:
- **ETP** = evapotranspiracija iz ARSO agrometeo (mm/dan)
- **Faktor sence** = 1.0 - (% sence × 0.4) — senceni predeli potrebujejo do 40% manj vode
- **Napoved padavin** = pricakovane padavine v naslednjih 24 urah (mm)
- Ce je **vodna bilanca** mocno negativna (suha tla), se potreba poveca za 20%

---

## Namestitev

### HACS (priporoceno)

[![Odprite HACS repozitorij](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrejs2&repository=ha_clss_shade&category=integration)

1. Odprite HACS v Home Assistant.
2. Poiscite **CLSS Shade** ali kliknite gumb zgoraj.
3. Kliknite **Prenesi** (Download).
4. Ponovo zaženite Home Assistant.

### Rocna namestitev

1. Prenesite ali klonirajte ta repozitorij.
2. Kopirajte mapo `custom_components/ha_clss_shade` v vaso Home Assistant `custom_components` mapo.
3. Ponovo zazenite Home Assistant.

---

## Nastavitev

1. Pojdite na **Nastavitve** > **Naprave in storitve**.
2. Kliknite **Dodaj integracijo** in poiscite **CLSS Shade**.
3. Vnesite podatke:
   - **Ime lokacije** — poljubno ime (npr. "Dom")
   - **Zemljepisna sirina in dolzina** — samodejno izpolnjeno iz HA nastavitev
   - **Radij analize** — v metrih (privzeto 200 m, najvec 1000 m)
   - **Vkljuci sosednje ploscice** — ce potrebujete vec kot 1 km² pokritost (prenese 9 ploscic namesto 1)
4. Ob prvi nastavitvi se prenese LiDAR ploscica (~30-50 MB). To lahko traja 1-2 minuti.
5. Po prenosu integracija samodejno zgradi 3D model in zacne izracunavati sencenje.

**Opomba:** Lokacija mora biti znotraj Slovenije (lat 45.42°-46.88°, lon 13.38°-16.61°).

### Nastavitve (Options)

Po namestitvi lahko spremenite radij in opcijo sosednjih ploscic prek **Nastavi** na integracijski kartici. Sprememba nastavitev povzroci ponoven prenos in obdelavo LiDAR podatkov.

---

## Primeri uporabe

### 1. Avtomatizacija rolet glede na sencenje

```yaml
automation:
  - alias: "Zapri rolete ko sonce osvetli okno"
    trigger:
      - platform: numeric_state
        entity_id: sensor.clss_shade_home_sonce
        above: 80
    condition:
      - condition: numeric_state
        entity_id: sensor.clss_shade_home_visina_sonca
        above: 15
      - condition: numeric_state
        entity_id: sensor.arso_weather_ljubljana_temperatura
        above: 25
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.dnevna_soba_rolete

  - alias: "Odpri rolete ko je v senci"
    trigger:
      - platform: numeric_state
        entity_id: sensor.clss_shade_home_senca
        above: 70
    action:
      - service: cover.open_cover
        target:
          entity_id: cover.dnevna_soba_rolete
```

### 2. Pametno zalivanje vrta

```yaml
automation:
  - alias: "Jutranje zalivanje glede na sencenje in vreme"
    trigger:
      - platform: time
        at: "06:00:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.clss_shade_home_potreba_po_zalivanju
        above: 10
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.zalivanje_vrt
      - delay:
          minutes: >
            {{ (states('sensor.clss_shade_home_potreba_po_zalivanju') | float / 10) | round }}
      - service: switch.turn_off
        target:
          entity_id: switch.zalivanje_vrt
      - service: notify.mobile_app_telefon
        data:
          title: "Zalivanje koncano"
          message: >
            Vrt je bil zalivan {{ states('sensor.clss_shade_home_potreba_po_zalivanju') }} L.
            Senca na vrtu: {{ states('sensor.clss_shade_home_garden_shade_percent') }}%.
```

### 3. Opozorilo ob nizki PV proizvodnji

```yaml
automation:
  - alias: "Opozorilo ob senci na PV panelih"
    trigger:
      - platform: numeric_state
        entity_id: sensor.clss_shade_home_roof_shade_percent
        above: 50
        for:
          minutes: 30
    condition:
      - condition: state
        entity_id: sensor.clss_shade_home_dnevna_svetloba
        state: "True"
    action:
      - service: notify.mobile_app_telefon
        data:
          title: "PV sistem v senci"
          message: >
            Streha je {{ states('sensor.clss_shade_home_roof_shade_percent') }}% v senci.
            Ocena proizvodnje: {{ states('sensor.clss_shade_home_ocena_pv_moci') }} W.
```

### 4. Avtomatizacija zaluzij po fasadah (napredna uporaba)

Za natancno upravljanje zaluzij/sencil po fasadah narisite **ozke cone** (1-2 m sirine) tik pred vsako fasado hiše v Zone Editorju. Shadow engine bo na podlagi dejanskega 3D modela (vkljucno z napusci, drevesi, sosednjimi stavbami) izracunal ali sonce pada na posamezno fasado.

**Primer razporeditve:**

```
          SV fasada (kuhinja)
          ┌────────────┐
          │            │
JV fasada │    HISA    │ JZ fasada
(panorama)│            │ (panoramsko okno
          │            │  z napuscem)
          └────────────┘
          Cone: fasada_sv, fasada_jv, fasada_jz
```

**Zakaj ozke cone pred fasado?** Ker vas zanima ali sonce pada na okno, ne na cel vrt. Ozka cona 1-2 m pred fasado simulira natancno to — vkljucno z napusci, ki poleti zasenčijo okna, pozimi pa sonce pride pod napusc.

```yaml
automation:
  # ── JZ fasada: panoramsko okno z napuscem ──
  # Poleti: zapri ko sonce sveti skozi (napusc ne zadosca)
  - alias: "Zaluzije JZ — zapri ob soncu poleti"
    trigger:
      - platform: numeric_state
        entity_id: sensor.dom_fasada_jz_sun_percent
        above: 60
        for: "00:05:00"
    condition:
      - condition: template
        value_template: "{{ now().month in [5,6,7,8,9] }}"
      - condition: numeric_state
        entity_id: sensor.dom_oblacnost
        below: 60
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.zaluzije_dnevna_soba

  # Pozimi: pusti sonce noter za ogrevanje prostorov
  - alias: "Zaluzije JZ — odpri za solarno ogrevanje pozimi"
    trigger:
      - platform: numeric_state
        entity_id: sensor.dom_fasada_jz_sun_percent
        above: 50
    condition:
      - condition: template
        value_template: "{{ now().month in [10,11,12,1,2,3] }}"
      - condition: numeric_state
        entity_id: sensor.dom_oblacnost
        below: 50
    action:
      - service: cover.open_cover
        target:
          entity_id: cover.zaluzije_dnevna_soba

  # ── SV fasada: kuhinja — jutranjo sonce ──
  - alias: "Zaluzije SV — zapri ob jutranjem soncu"
    trigger:
      - platform: numeric_state
        entity_id: sensor.dom_fasada_sv_sun_percent
        above: 60
    condition:
      - condition: numeric_state
        entity_id: sensor.dom_oblacnost
        below: 50
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.zaluzije_kuhinja

  # ── Vse fasade: odpri ko je oblacno ──
  - alias: "Zaluzije — odpri ob oblacnem vremenu"
    trigger:
      - platform: numeric_state
        entity_id: sensor.dom_oblacnost
        above: 70
        for: "00:10:00"
    action:
      - service: cover.open_cover
        target:
          entity_id:
            - cover.zaluzije_dnevna_soba
            - cover.zaluzije_kuhinja
            - cover.zaluzije_spalnica

  # ── Ponocna ponastavitev ──
  - alias: "Zaluzije — odpri ob zori"
    trigger:
      - platform: state
        entity_id: sensor.dom_dnevna_svetloba
        to: "True"
    action:
      - service: cover.open_cover
        target:
          entity_id: all
```

**Senzorji za upravljanje zaluzij:**

| Senzor | Opis | Uporaba |
|--------|------|---------|
| `fasada_*_sun_percent` | % sonca na fasadi | Ali sonce sveti na okno (z upostevanjem napusca!) |
| `oblacnost` | Oblacnost (%) iz ARSO | Odpri zaluzije ko je oblacno |
| `sun_elevation` | Kot sonca nad obzorjem | Razlikovanje poletje/zima (nizek kot = daljse sence) |
| `sun_azimuth` | Smer sonca | Za debugging in dodatne pogoje |
| `is_day` | Dan/noc | Ponocna logika |

**Namig:** Napusc, ki poleti zasenči JZ okno, je ze v LiDAR modelu! Shadow engine samodejno uposteva, da poleti (visoko sonce) napusc meče senco na okno, pozimi (nizko sonce) pa sonce pride pod napusc. Ni potrebe po rocnem nastavljanju kotov.

### 5. Dashboard — primeri Lovelace kartic

Spodaj so primeri kartic za celovit CLSS Shade dashboard. Zamenjajte `dom` z imenom vase lokacije.

#### 5.1 Pregled — sonce in senca (gauge kartice)

```yaml
type: horizontal-stack
cards:
  - type: gauge
    entity: sensor.dom_sonce
    name: Sonce
    min: 0
    max: 100
    severity:
      green: 60
      yellow: 30
      red: 0
    needle: true
  - type: gauge
    entity: sensor.dom_senca
    name: Senca
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 30
      red: 60
    needle: true
  - type: gauge
    entity: sensor.dom_oblacnost
    name: Oblacnost
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 40
      red: 70
    needle: true
```

#### 5.2 Polozaj sonca

```yaml
type: entities
title: "Polozaj sonca"
icon: mdi:white-balance-sunny
entities:
  - entity: sensor.dom_visina_sonca
    name: "Visina (elevacija)"
    icon: mdi:angle-acute
  - entity: sensor.dom_azimut_sonca
    name: "Smer (azimut)"
    icon: mdi:compass
  - entity: sensor.dom_dnevna_svetloba
    name: "Dan / noc"
    icon: mdi:theme-light-dark
  - entity: sensor.dom_oblacnost
    name: "Oblacnost"
    icon: mdi:weather-cloudy
```

#### 5.3 Sencenje po conah — primerjava

```yaml
type: entities
title: "Sencenje po conah"
icon: mdi:select-group
show_header_toggle: false
entities:
  - type: section
    label: "Avtomatske cone (LiDAR)"
  - entity: sensor.dom_roof_sun_percent
    name: "Streha — sonce"
    icon: mdi:home-roof
  - entity: sensor.dom_garden_sun_percent
    name: "Vrt — sonce"
    icon: mdi:flower
  - entity: sensor.dom_trees_sun_percent
    name: "Drevesa — sonce"
    icon: mdi:tree
  - type: section
    label: "Uporabniske cone"
  - entity: sensor.dom_borovnice_sun_percent
    name: "Borovnice — sonce"
    icon: mdi:fruit-grapes
  - entity: sensor.dom_zelenjava_sun_percent
    name: "Zelenjava — sonce"
    icon: mdi:sprout
  - entity: sensor.dom_jz_terasa_sun_percent
    name: "JZ terasa — sonce"
    icon: mdi:deck
  - entity: sensor.dom_jv_terasa_sun_percent
    name: "JV terasa — sonce"
    icon: mdi:deck
```

#### 5.4 Fasade — stanje za zaluzije

```yaml
type: glance
title: "Fasade — osoncenje"
columns: 3
show_state: true
entities:
  - entity: sensor.dom_fasada_sv_sun_percent
    name: "SV (kuhinja)"
    icon: mdi:blinds
  - entity: sensor.dom_fasada_jv_sun_percent
    name: "JV (panorama)"
    icon: mdi:blinds-open
  - entity: sensor.dom_fasada_jz_sun_percent
    name: "JZ (dnevna)"
    icon: mdi:blinds
```

#### 5.5 Zgodovina sencenja — graf cez dan

```yaml
type: history-graph
title: "Sencenje danes"
hours_to_show: 24
entities:
  - entity: sensor.dom_sonce
    name: "Skupno sonce"
  - entity: sensor.dom_roof_sun_percent
    name: "Streha"
  - entity: sensor.dom_borovnice_sun_percent
    name: "Borovnice"
  - entity: sensor.dom_zelenjava_sun_percent
    name: "Zelenjava"
```

#### 5.6 Fasade cez dan — kdaj sonce pride na katero stran

```yaml
type: history-graph
title: "Fasade — sonce cez dan"
hours_to_show: 24
entities:
  - entity: sensor.dom_fasada_sv_sun_percent
    name: "SV (kuhinja)"
  - entity: sensor.dom_fasada_jv_sun_percent
    name: "JV (panorama)"
  - entity: sensor.dom_fasada_jz_sun_percent
    name: "JZ (dnevna soba)"
```

#### 5.7 PV in energija

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.dom_ocena_pv_moci
    name: "PV ocena"
    min: 0
    max: 5000
    unit: "W"
    severity:
      green: 2000
      yellow: 500
      red: 0
    needle: true
  - type: entities
    entities:
      - entity: sensor.dom_roof_sun_percent
        name: "Streha — sonce"
        icon: mdi:home-roof
      - entity: sensor.dom_oblacnost
        name: "Oblacnost"
        icon: mdi:weather-cloudy
      - entity: sensor.dom_visina_sonca
        name: "Visina sonca"
        icon: mdi:angle-acute
```

#### 5.8 Zalivanje — agrometeo

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.dom_potreba_po_zalivanju
    name: "Potreba po zalivanju"
    min: 0
    max: 500
    unit: "L"
    severity:
      green: 0
      yellow: 100
      red: 300
    needle: true
  - type: entities
    title: "Agrometeo podatki"
    entities:
      - type: attribute
        entity: sensor.dom_potreba_po_zalivanju
        attribute: evapotranspiration_mm
        name: "Evapotranspiracija"
        suffix: " mm"
        icon: mdi:water-thermometer
      - type: attribute
        entity: sensor.dom_potreba_po_zalivanju
        attribute: water_balance_mm
        name: "Vodna bilanca"
        suffix: " mm"
        icon: mdi:water-percent
      - type: attribute
        entity: sensor.dom_potreba_po_zalivanju
        attribute: vir_podatkov
        name: "Vir podatkov"
        icon: mdi:database
      - entity: sensor.dom_garden_shade_percent
        name: "Vrt — senca"
        icon: mdi:flower
      - entity: sensor.dom_borovnice_shade_percent
        name: "Borovnice — senca"
        icon: mdi:fruit-grapes
```

#### 5.9 Polozaj sonca — kompas in pot cez dan

```yaml
type: history-graph
title: "Pot sonca cez dan"
hours_to_show: 24
entities:
  - entity: sensor.dom_visina_sonca
    name: "Elevacija (°)"
  - entity: sensor.dom_azimut_sonca
    name: "Azimut (°)"
```

#### 5.10 Celoten dashboard — priporocena razporeditev

Za celovit CLSS Shade dashboard priporocamo razporeditev v 2-3 stolpce:

```
┌─────────────────┬──────────────────┬─────────────────┐
│  Gauge: Sonce   │  Gauge: Senca    │ Gauge: Oblacnost│
├─────────────────┴──────────────────┴─────────────────┤
│  Polozaj sonca (entities)                            │
├──────────────────────────┬───────────────────────────┤
│  Cone — sence (entities) │  Fasade — glance          │
├──────────────────────────┼───────────────────────────┤
│  Zgodovina sencenja      │  Fasade cez dan (graf)    │
│  (history-graph)         │  (history-graph)           │
├──────────────────────────┼───────────────────────────┤
│  PV ocena (gauge +       │  Zalivanje (gauge +        │
│  entities)               │  agrometeo atributi)       │
├──────────────────────────┴───────────────────────────┤
│  Pot sonca cez dan (history-graph)                   │
└──────────────────────────────────────────────────────┘
```

**Namig:** Za se lepse kartice namestite prek HACS se:
- [mushroom-cards](https://github.com/piitaya/lovelace-mushroom) — za kompaktne entity kartice
- [mini-graph-card](https://github.com/kalkih/mini-graph-card) — za lepe inline grafe
- [apexcharts-card](https://github.com/RomRider/apexcharts-card) — za napredne grafe (npr. sonce/senca area chart)

### 6. PV napoved — dashboard

Za celovit PV napoved dashboard z ApexCharts in Mushroom karticami glejte **[docs/pv_dashboard.yaml](docs/pv_dashboard.yaml)** — pripravljen YAML za kopiranje v Lovelace.

Vsebuje:
- Status chips (realno, ocena, faktor, naslednja ura)
- Casovna okna (1h, 3h, preostanek danes, jutri)
- Danes — urna krivulja napovedi + realno
- Jutri — urna krivulja napovedi
- 5-dnevni stolpicni graf (kWh/dan)
- Performance gauge + 5-dnevna zvezna krivulja

#### Hitri primeri za ApexCharts

**Danes — napoved vs realno:**

```yaml
type: custom:apexcharts-card
header:
  title: "Danes — PV proizvodnja"
  show: true
graph_span: 18h
span:
  start: day
  offset: "+5h"
series:
  - entity: sensor.dom_pv_napoved_danes
    name: Napoved
    type: area
    color: "#FFA726"
    opacity: 0.3
    stroke_width: 2
    data_generator: |
      const data = entity.attributes.forecast_hourly;
      if (!data) return [];
      return data.map(e => [new Date(e.time).getTime(), e.estimate_w]);
  - entity: sensor.dom_realna_pv_moc
    name: Realno
    type: line
    color: "#66BB6A"
    stroke_width: 3
    group_by:
      func: avg
      duration: 30min
```

**5-dnevni stolpci:**

```yaml
type: custom:apexcharts-card
header:
  title: "5-dnevna napoved (kWh/dan)"
  show: true
apex_config:
  chart:
    type: bar
    height: 250
series:
  - entity: sensor.dom_pv_napoved_5_dni
    name: kWh
    type: column
    color: "#FFA726"
    data_generator: |
      const days = entity.attributes.days;
      if (!days) return [];
      return days.map(d => [d.label, d.total_kwh]);
```

**5-dnevna zvezna krivulja:**

```yaml
type: custom:apexcharts-card
header:
  title: "5-dnevna krivulja"
  show: true
series:
  - entity: sensor.dom_pv_napoved_5_dni
    name: Napoved
    type: area
    color: "#AB47BC"
    opacity: 0.2
    stroke_width: 2
    data_generator: |
      const data = entity.attributes.forecast_hourly_5day;
      if (!data) return [];
      return data.map(e => [new Date(e.time).getTime(), e.estimate_w]);
```

---

## Tehnicni podatki

### Zmogljivost

| Operacija | Cas | Opomba |
|-----------|-----|--------|
| Prenos LiDAR ploscice | 30-90 s | Enkratno, ~30-50 MB |
| Rasterizacija LAZ → grid | 5-15 s | Enkratno, rezultat se kesira |
| Izracun sencenja | 1-2 s | Vsake 5 minut |
| PV napoved 5 dni | ~2.7 min | V ozadju, vsako uro |
| Poraba pomnilnika | ~50 MB | Za 800×800 grid (200 m radij) |

### Odvisnosti

| Paket | Uporaba |
|-------|---------|
| `numpy` | Numericne operacije, shadow engine |
| `laspy` | Branje LAZ datotek |
| `laszip` | LAZ dekompresija |
| `pyproj` | Koordinatne pretvorbe (WGS84 ↔ EPSG:3794) |
| `scipy` | Interpolacija praznih celic v gridu |

### Koordinatni sistem

Slovenija uporablja koordinatni sistem **EPSG:3794 (D96/TM)** — transverzalni Merkator s centralnim meridianom 15°E. Integracija samodejno pretvarja med WGS84 (lat/lon) in D96/TM.

### ARSO LiDAR streznik

Ploscice se prenesejo s streznika `gis.arso.gov.si`. Integracija samodejno doloci pravilni "block number" za vsako ploscico prek HEAD probinga in rezultat kesira lokalno, da se izogne ponovnim poizvedbam.

URL vzorec: `http://gis.arso.gov.si/lidar/GKOT/laz/b_{block}/D96TM/TM_{e}_{n}.laz`

---

## Razhroscevanje

Ce naletite na tezave, omogocite razhroscevalno beleženje:

```yaml
logger:
  default: info
  logs:
    custom_components.ha_clss_shade: debug
```

Uporabni dnevniski zapisi:
- `Downloading TM_461_101.laz` — prenos LiDAR ploscice
- `Tile TM_461_101 found in block b_35` — odkritje block stevilke
- `Grid 800x800, 87.5% filled, res=0.50m` — rasterizacija
- `Shadow map: mean shade=9.3%` — izracun sencenja
- `Detected zones: ['roof', 'garden', 'trees', 'open']` — zaznane cone
- `Found 5 ARSO weather entities` — povezava z vremenskimi podatki

---

## Zahvala in atribucija

- **LiDAR podatki**: [Geodetska uprava RS (GURS)](https://www.e-prostor.gov.si/) / [ARSO](https://www.arso.gov.si/), licenca CC 4.0
- **CLSS projekt**: [Flycom Technologies](https://flycom.si/), ciklicno lasersko skeniranje Slovenije 2023-2025
- **Inspiracija**: [HA_Solar_Shade](https://github.com/LawPaul/HA_Solar_Shade) avtorja LawPaul — ideja za uporabo LiDAR podatkov za analizo sencenja v Home Assistant
- **Vremenski podatki**: [slovenian_weather_integration](https://github.com/andrejs2/slovenian_weather_integration) — ARSO Weather za Home Assistant
- **CLSS pregledovalnik**: [clss.si](https://clss.si) — 3D pregledovalnik LiDAR podatkov

---

## Prispevanje

Ce najdete napake ali imate predloge za izboljsave, odprite [issue](https://github.com/andrejs2/ha_clss_shade/issues) ali posljite pull request.

---

## Podprite moje delo

Ce vam ta integracija koristi, me lahko podprete:

<a href="https://www.buymeacoffee.com/andrejs2" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

[![GitHub Sponsors](https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=#EA4AAA)](https://github.com/sponsors/andrejs2)

---

## Sorodni projekti

| Projekt | Opis |
|---------|------|
| **[ARSO Weather](https://github.com/andrejs2/slovenian_weather_integration)** | Home Assistant integracija za vremenske podatke ARSO — 12 modulov, 247 lokacij |
| **[ARSO Potresi](https://github.com/andrejs2/arso_potresi)** | Home Assistant integracija za podatke o potresih iz ARSO |
| **[HA Assist — Slovenscina](https://github.com/home-assistant/intents/tree/main/sentences/sl)** | Slovenscina za glasovnega pomicnika Home Assistant |

[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[python]: https://www.python.org/
[license-shield]: https://img.shields.io/github/license/andrejs2/ha_clss_shade?style=for-the-badge
[license]: ./LICENSE
[maintainer-shield]: https://img.shields.io/badge/MAINTAINER-%40andrejs2-41BDF5?style=for-the-badge
[maintainer]: https://github.com/andrejs2
[homeassistant-shield]: https://img.shields.io/badge/home%20assistant-%2341BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white
[homeassistant]: https://www.home-assistant.io/
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[hacs]: https://hacs.xyz/
[buymecoffee-shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[buymecoffee]: https://www.buymeacoffee.com/andrejs2
[github-shield]: https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=#EA4AAA
[github]: https://github.com/sponsors/andrejs2
