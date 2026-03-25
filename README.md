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
| **Ocena PV moci** | W | Ocena trenutne proizvodnje soncne elektrarne |
| **Potreba po zalivanju** | L | Ocenjena dnevna potreba po zalivanju za vrt |

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

Poleg avtomatsko zaznanih con lahko v **Zone Editorju** (CLSS Shade panel v stranski vrstici) narisite lastne poligone na satelitski karti. Podprtih je vec slojev (Google Satelit, GURS DOF ortofoto, Esri, OpenStreetMap).

Primeri uporabniskih con:
- **Fasadne cone** — ozke cone pred okni za avtomatizacijo zaluzij
- **Vrtne cone** — borovnice, zelenjava, trata
- **PV paneli** — natancen poligon namesto celotne strehe
- **Terasa, parkirisce, bazen** — poljubne cone

Po shranjevanju in ponovnem zagonu se za vsako cono ustvarijo senzorji `{ime}_shade_percent` in `{ime}_sun_percent`.

### PV ocena

Ce je na voljo meritev soncnega sevanja iz ARSO Weather, integracija izracuna oceno PV proizvodnje:

```
PV_ocena = Kapaciteta_Wp × (Efektivno_sevanje / 1000) × (1 - Izgube)
```

Kjer:
- **Efektivno sevanje** = izmerjeno sevanje × (delez_sonca_na_strehi × 0.85 + 0.15) — uposteva, da tudi v senci prispe nekaj difuzne svetlobe
- **Izgube** = 14% (inverter, kabliranje, temperatura)
- **Kapaciteta_Wp** = nastavljena moc sistema (privzeto 5 kWp)

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

### 5. Lovelace kartica — pregled sencenja

```yaml
type: entities
title: "CLSS Shade — Dom"
entities:
  - entity: sensor.clss_shade_home_senca
    name: "Skupna senca"
  - entity: sensor.clss_shade_home_sonce
    name: "Skupno sonce"
  - type: divider
  - entity: sensor.clss_shade_home_roof_shade_percent
    name: "Streha — senca"
    icon: mdi:home-roof
  - entity: sensor.clss_shade_home_garden_shade_percent
    name: "Vrt — senca"
    icon: mdi:flower
  - type: divider
  - entity: sensor.clss_shade_home_ocena_pv_moci
    name: "PV ocena"
  - entity: sensor.clss_shade_home_potreba_po_zalivanju
    name: "Zalivanje"
  - type: divider
  - entity: sensor.clss_shade_home_visina_sonca
  - entity: sensor.clss_shade_home_azimut_sonca
```

---

## Tehnicni podatki

### Zmogljivost

| Operacija | Cas | Opomba |
|-----------|-----|--------|
| Prenos LiDAR ploscice | 30-90 s | Enkratno, ~30-50 MB |
| Rasterizacija LAZ → grid | 5-15 s | Enkratno, rezultat se kesira |
| Izracun sencenja | 1-2 s | Vsake 5 minut |
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
