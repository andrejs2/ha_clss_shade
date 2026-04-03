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

# CLSS Shade — Analiza sencenja na podlagi LiDAR podatkov za Home Assistant

> **EKSPERIMENTALNO / BETA (v0.0.1)**
>
> Ta integracija je v **zgodnji fazi razvoja**. Deluje, vendar pricakujte:
> - Obcasne napake in spremembe v konfiguraciji med posodobitvami
> - Nepopolno dokumentacijo za nekatere napredne funkcije
> - Moznost, da se API ali senzorji spremenijo brez predhodnega opozorila
>
> Povratne informacije in porocila o napakah so zelo dobrodosli — odprite [issue](https://github.com/andrejs2/ha_clss_shade/issues).

---

## Kaj je to?

**CLSS Shade** je Home Assistant integracija, ki na podlagi **pravih 3D podatkov** vase okolice izracuna, kateri deli vasega doma, vrta in strehe so na soncu in kateri v senci — v realnem casu, vsake 5 minut.

Namesto poenostavljenih modelov ali rocnega nastavljanja kotov, integracija uporabi **dejanski 3D model terena, stavb in dreves**, ki ga pridobi iz javno dostopnih LiDAR podatkov. Rezultat je natancna analiza sencenja, ki uposteva vse okoliske objekte: sosednje stavbe, drevesa, teren, napusce, ograje...

### Primeri uporabe

- **Avtomatizacija rolet/zaluzij** — samodejno zapri, ko sonce osvetli okno; odpri, ko je v senci
- **PV napoved** — koliko elektrike bodo vasi soncni paneli danes/jutri/ta teden dejansko proizvedli, z upostevanjem sencenja
- **Pametno zalivanje** — koliko vode posamezna cona vrta potrebuje glede na osoncenje, evapotranspiracijo in napoved padavin
- **3D vizualizacija** — ogled vase okolice v 3D neposredno v Home Assistant brskalniku

---

## Samo za Slovenijo

Ta integracija je **prilagojena za Slovenijo** in zaenkrat deluje **samo na obmocju Republike Slovenije**.

Razlog: podatkovni vir so **LiDAR podatki** iz projekta **CLSS (Ciklicno Lasersko Skeniranje Slovenije)**, ki ga izvaja Geodetska uprava RS (GURS). Gre za sistematicno lasersko skeniranje celotne drzave iz letala — vsak kvadratni meter Slovenije je poskeniran z gostoto **10 tock/m2**, kar pomeni, da integracija pozna vsako stavbo, drevo in teren v vasi okolici na priblizno 10 cm natancno.

Ti podatki so **javno dostopni in brezplacni** (licenca CC 4.0, obvezna atribucija), ampak obstajajo samo za Slovenijo. Ce zivite zunaj Slovenije, ta integracija zaenkrat ne bo delovala.

> **Tehnicno:** Podatki so v formatu LAZ 1.4, koordinatni sistem EPSG:3794 (D96/TM), z 21 ASPRS klasifikacijskimi razredi (tla, stavbe, vegetacija, voda, mostovi...). Posamezna ploscica pokriva 1x1 km in je velika ~30-50 MB.

---

## Zahteve in opozorila

### Prenos podatkov in obremenitev streznika

Ob prvi nastavitvi integracija **prenese LiDAR ploscico** s streznika ARSO (gis.arso.gov.si):

| Parameter | Vrednost |
|-----------|---------|
| Velikost prenosa | ~30-50 MB (ena ploscica 1x1 km) |
| Cas prenosa | 30-90 sekund |
| Streznik | gis.arso.gov.si (ARSO, javni) |
| Frekvenca | **Enkratno** — podatki se kesirajo lokalno |

**Pomembno:**
- Prenos se zgodi **samo enkrat** ob namestitvi (ali ob spremembi lokacije/radija). Integracija podatkov **ne prenaša veckrat**.
- Ce izberete vecji radij (500-1000 m) ali vklopite "sosednje ploscice", se prenese vec podatkov (do 9 ploscic, ~300+ MB). Priporocamo zaceti z **radijem 200 m** in po potrebi povecati.
- Ne obremenjujte streznika z nepotrebnimi ponovnimi namestitvami.

### Sistemske zahteve

| Zahteva | Priporocilo |
|---------|-------------|
| **RAM** | ~50 MB za radij 200 m; ~200 MB za 500 m; **3-4 GB za 9 ploscic** (sosednje ploscice) |
| **Disk** | ~50-300 MB za kesirane podatke |
| **CPU** | Izracun sencenja traja 1-2 s vsakih 5 min (zanemarljivo) |
| **Home Assistant** | 2024.4.0 ali novejsi |

### Odvisnosti

| Paket | Uporaba |
|-------|---------|
| `numpy` | Numericne operacije, shadow engine |
| `laspy` + `laszip` | Branje in dekompresija LAZ datotek |
| `pyproj` | Koordinatne pretvorbe (WGS84 <-> EPSG:3794) |
| `scipy` | Interpolacija praznih celic v gridu |

Vse odvisnosti se namestijo samodejno prek HACS.

---

## Kako deluje

### V 60 sekundah

```
1. Prenos LiDAR podatkov (enkratno)
   ARSO streznik --> LAZ datoteka --> 3D grid (DSM + DTM + klasifikacija)

2. Izracun sencenja (vsakih 5 minut)
   Trenutni polozaj sonca + 3D grid --> Ray-marching --> Sencna mapa

3. Analiza po conah
   LiDAR klasifikacija --> Avtomatske cone: Streha / Vrt / Drevesa / Odprto
   + Uporabniske cone: poljubni poligoni, ki jih narisite na karti

4. Napredne funkcije (opcijsko)
   + ARSO Weather --> PV napoved, zalivanje
   + 3D editor --> Analiza fasad, oken, nadstreskov
```

### Ray-marching algoritem

Za vsako celico v gridu integracija "izstreli" zarek proti soncu in preveri, ali kaksen objekt (stavba, drevo) prepreci pot svetlobe. Uposteva tudi sezonske spremembe — pozimi, ko drevesa nimajo listov, prepuscajo vec svetlobe.

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

### Zakaj prihaja do nenadnih sprememb (spic) v sencenju?

Ce opazite, da se sencenje nenadoma spremeni (npr. iz 20% na 80% v 15 minutah), to **ni napaka** — je posledica realnih razmer:

- **Stavbe in drevesa mecejo ostre sence.** Ko sonce potuje po nebu, senca sosednje stavbe ali drevesa lahko v nekaj minutah "preskoce" cez vaso cono. V naravi je enako — razlika je, da integracija to izracuna na 5 minut natancno.
- **Pozimi so sence dolge.** Pri nizkem kotu sonca (december, januar) ze manjsa stavba vrze senco 50+ m dalec. Sonce je nad obzorjem le 8-9 ur, zato so spremembe hitrejse.
- **Sezonski prehodi.** V aprilu in oktobru se model vegetacije spremeni (drevesa dobijo/izgubijo liste), kar lahko povzroci skok v sencenju na conah blizu dreves.
- **Napusci in strehe.** Ce imate napusc ali nadstresek, ta poleti (visoko sonce) senci okno, pozimi (nizko sonce) pa sonce pride pod njim. To je namerno in pravilno upostevan v modelu.

**Namig:** Uporabite `history-graph` kartico za pregled gibanja sencenja cez dan — hitro boste prepoznali vzorce, ki se ponavljajo vsak jasen dan.

---

## Namestitev

### HACS (priporoceno)

[![Odprite HACS repozitorij](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrejs2&repository=ha_clss_shade&category=integration)

1. Odprite HACS v Home Assistant.
2. Poiscite **CLSS Shade** ali kliknite gumb zgoraj.
3. Kliknite **Prenesi** (Download).
4. Ponovo zazenite Home Assistant.

### Rocna namestitev

1. Prenesite ali klonirajte ta repozitorij.
2. Kopirajte mapo `custom_components/ha_clss_shade` v vaso Home Assistant `custom_components` mapo.
3. Ponovo zazenite Home Assistant.

---

## Nastavitev — korak po korak

### 1. Dodajte integracijo

1. Pojdite na **Nastavitve** > **Naprave in storitve** > **Dodaj integracijo**.
2. Poiscite **CLSS Shade**.
3. Vnesite podatke:

| Polje | Opis | Privzeto |
|-------|------|----------|
| **Ime lokacije** | Poljubno ime (npr. "Dom", "Vikend") | — |
| **Zemljepisna sirina** | Samodejno iz HA nastavitev | Vasa HA lokacija |
| **Zemljepisna dolzina** | Samodejno iz HA nastavitev | Vasa HA lokacija |
| **Radij analize** | V metrih — koliko dalec od vase lokacije naj se racuna sencenje | 200 m |
| **Vkljuci sosednje ploscice** | Prenese 9 ploscic namesto 1 (za robne lokacije ali vecji radij) | Ne |

4. Pocakajte 1-2 minuti, da se prenesejo LiDAR podatki.
5. Integracija samodejno zgradi 3D model in zacne izracunavati sencenje.

> **Opomba:** Lokacija mora biti znotraj Slovenije (lat 45.42-46.88, lon 13.38-16.61).

### 2. Senzorji — kaj dobite "iz skatle"

Po namestitvi se samodejno ustvarijo naslednji senzorji:

#### Globalni senzorji

| Senzor | Enota | Opis |
|--------|-------|------|
| **Senca** | % | Povprecni delez sence na celotnem obmocju |
| **Sonce** | % | Povprecni delez sonca na celotnem obmocju |
| **Visina sonca** | deg | Kot sonca nad obzorjem |
| **Azimut sonca** | deg | Smer sonca (0=S, 90=V, 180=J, 270=Z) |
| **Dnevna svetloba** | da/ne | Ali je sonce nad obzorjem |

#### Senzorji po conah (samodejno zaznane iz LiDAR)

| Cona | Opis | Senzorji |
|------|------|----------|
| **Streha** (roof) | Celice klasificirane kot stavba | Senca %, Sonce % |
| **Vrt** (garden) | Tla in nizka vegetacija blizu stavb | Senca %, Sonce % |
| **Drevesa** (trees) | Srednja in visoka vegetacija | Senca %, Sonce % |
| **Odprto** (open) | Tla dalec od stavb | Senca %, Sonce % |

### 3. Zone Editor — narisite lastne cone

V stranski vrstici Home Assistant se pojavi **CLSS Shade** panel z interaktivnim urejevalnikom con:

- **2D pogled:** Satelitska karta (Leaflet) z moznostjo risanja poligonov
- **3D pogled:** Three.js 3D vizualizacija vase okolice z dejanskimi viskami stavb in dreves

Za vsako uporabnisko cono se ustvarijo senzorji `{ime}_shade_percent` in `{ime}_sun_percent`.

**Primeri uporabniskih con:**
- Fasade (ozke cone pred okni za avtomatizacijo zaluzij)
- Vrtne cone (zelenjava, borovnice, trata, bazen)
- PV paneli (natancen poligon na strehi)
- Terasa, parkirisce, igrisca

### 4. PV napoved (opcijsko)

Ce imate soncne panele, lahko nastavite PV napovedovanje:

1. V **Nastavitve > Naprave > CLSS Shade > Nastavi** vnesite:

| Polje | Opis | Primer |
|-------|------|--------|
| **PV cone in kapaciteta** | `cona:Wp` pari, loceni z vejico | `pv-visja:5925,pv-nizja:5135` |
| **Nagib panelov** | Stopinje od vodoravne (0-90) | `30` |
| **Azimut panelov** | Smer panelov (0=S, 90=V, 180=J, 270=Z) | `180` |
| **Realna PV moc senzor** | Entity ID inverterja (opcijsko) | `sensor.solaredge_current_power` |

2. Narisite PV cone na karti (Zone Editor) — loceno cono za vsako skupino panelov.

**Dobite naslednje senzorje:**

| Senzor | Enota | Opis |
|--------|-------|------|
| **Ocena PV moci** | W | Trenutna ocena proizvodnje |
| **PV napoved danes** | kWh | Skupna napovedana proizvodnja danes |
| **PV napoved jutri** | kWh | Skupna napovedana proizvodnja jutri |
| **PV napoved 5 dni** | kWh | Sestevek 5-dnevne napovedi |
| **PV naslednja ura** | W | Ocenjena moc v naslednji uri |
| **PV naslednja 1h / 3h** | Wh | Energija v naslednjih 1 oz. 3 urah |
| **PV preostanek danes** | kWh | Preostala napovedana proizvodnja |

Napoved se izracuna z kombinacijo shadow forecast (5 dni, 30-min resolucija) + vremenska napoved (oblacnost/GHI iz Open-Meteo ali ARSO) + dinamicni POA faktor.

> **Namig:** Ce povezete realni PV senzor (SolarEdge, Fronius, Enphase...), integracija samodejno kalibrira napoved z EMA (eksponentno drsecim povprecjem).

### 5. ARSO Weather integracija (opcijsko, priporoceno)

Ce imate namesceno [ARSO Weather (slovenian_weather_integration)](https://github.com/andrejs2/slovenian_weather_integration), CLSS Shade samodejno prebere vremenske podatke:

| Podatek | Uporaba |
|---------|---------|
| Globalno soncno sevanje | PV ocena |
| Oblacnost | Napoved |
| Evapotranspiracija | Zalivanje |
| Vodna bilanca | Zalivanje |
| Temperatura | PV derating |

Za PV oceno in zalivanje je **priporocena** namestitev ARSO Weather z omogocenim modulom Agrometeo.

---

## Primeri avtomatizacij

### Avtomatizacija rolet glede na sencenje

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

### Pametno zalivanje vrta

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

### Opozorilo ob senci na PV panelih

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

### Avtomatizacija zaluzij po fasadah (napredna uporaba)

Za natancno upravljanje zaluzij/sencil po fasadah narisite **ozke cone** (1-2 m sirine) tik pred vsako fasado hise v Zone Editorju. Shadow engine bo na podlagi dejanskega 3D modela (vkljucno z napusci, drevesi, sosednjimi stavbami) izracunal ali sonce pada na posamezno fasado.

```
          SV fasada (kuhinja)
          +----------------+
          |                |
JV fasada |      HISA      | JZ fasada
(panorama)|                | (panoramsko okno
          |                |  z napuscem)
          +----------------+
          Cone: fasada_sv, fasada_jv, fasada_jz
```

**Zakaj ozke cone pred fasado?** Ker vas zanima ali sonce pada na okno, ne na cel vrt. Ozka cona 1-2 m pred fasado simulira natancno to — vkljucno z napusci, ki poleti zasenčijo okna, pozimi pa sonce pride pod napusc.

```yaml
automation:
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

  # Vse fasade: odpri ko je oblacno
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
```

---

## Dashboard — primeri Lovelace kartic

Zamenjajte `dom` z imenom vase lokacije.

### Pregled — sonce in senca (gauge kartice)

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

### Sencenje po conah

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
```

### Zgodovina sencenja cez dan

```yaml
type: history-graph
title: "Sencenje danes"
hours_to_show: 24
entities:
  - entity: sensor.dom_sonce
    name: "Skupno sonce"
  - entity: sensor.dom_roof_sun_percent
    name: "Streha"
  - entity: sensor.dom_garden_sun_percent
    name: "Vrt"
```

### PV napoved — danes vs realno (ApexCharts)

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

### 5-dnevna napoved (stolpci)

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

### Priporocena razporeditev dashboarda

```
+-------------------+--------------------+-------------------+
|  Gauge: Sonce     |  Gauge: Senca      | Gauge: Oblacnost  |
+-------------------+--------------------+-------------------+
|  Polozaj sonca (entities)                                  |
+-----------------------------+------------------------------+
|  Cone — sence (entities)    |  Fasade — glance             |
+-----------------------------+------------------------------+
|  Zgodovina sencenja         |  Fasade cez dan (graf)       |
|  (history-graph)            |  (history-graph)             |
+-----------------------------+------------------------------+
|  PV ocena (gauge +          |  Zalivanje (gauge +          |
|  entities)                  |  agrometeo atributi)         |
+-----------------------------+------------------------------+
|  PV napoved danes/jutri/5d (apexcharts)                    |
+------------------------------------------------------------+
```

**Namig:** Za se lepse kartice namestite prek HACS se:
- [mushroom-cards](https://github.com/piitaya/lovelace-mushroom) — kompaktne entity kartice
- [mini-graph-card](https://github.com/kalkih/mini-graph-card) — lepi inline grafi
- [apexcharts-card](https://github.com/RomRider/apexcharts-card) — napredni grafi (PV napoved, sonce/senca area chart)

Za celovit PV dashboard z ApexCharts in Mushroom karticami glejte **[docs/pv_dashboard.yaml](docs/pv_dashboard.yaml)**.

---

## Razhroscevanje

Ce naletite na tezave, omogocite razhroscevalno belezenje:

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

## Zmogljivost

| Operacija | Cas | Opomba |
|-----------|-----|--------|
| Prenos LiDAR ploscice | 30-90 s | Enkratno, ~30-50 MB |
| Rasterizacija LAZ -> grid | 5-15 s | Enkratno, rezultat se kesira |
| Izracun sencenja | 1-2 s | Vsake 5 minut |
| PV napoved 5 dni | ~2.7 min | V ozadju, vsako uro |
| Poraba pomnilnika | ~50 MB | Za 800x800 grid (200 m radij) |

---

## Podatkovni viri in atribucija

| Vir | Podatki | Licenca |
|-----|---------|---------|
| **[GURS / E-prostor](https://www.e-prostor.gov.si/)** | LiDAR podatki (CLSS) | CC 4.0 (obvezna atribucija) |
| **[ARSO](https://www.arso.gov.si/)** | LiDAR streznik, vremenske meritve | Javni podatki |
| **[Flycom Technologies](https://flycom.si/)** | Izvajalec CLSS 2023-2025 | — |
| **[Open-Meteo](https://open-meteo.com/)** | GHI napoved, DEM horizont | Free tier |
| **[CLSS pregledovalnik](https://clss.si)** | 3D pregled LiDAR podatkov | — |

### Inspiracija

- [HA_Solar_Shade](https://github.com/LawPaul/HA_Solar_Shade) avtorja LawPaul — ideja za uporabo LiDAR podatkov za analizo sencenja v Home Assistant

---

## Znane omejitve (beta)

- **Samo Slovenija** — podatki CLSS/GURS obstajajo le za RS
- **INCA nowcasting** (soncno sevanje) pokriva le JV Slovenijo — za ostalo se uporablja Open-Meteo
- **Sosednje ploscice** potrebujejo 3-4 GB RAM — uporabite previdno
- **POF ortophoto** (16cm resolucija za 3D) zahteva rocen prenos s CLSS pregledovalnika
- **Sezonski model** je poenostavljen — predpostavlja listavce povsod (ne razlikuje med iglavci in listavci)

---

## Prispevanje

Ce najdete napake ali imate predloge za izboljsave, odprite [issue](https://github.com/andrejs2/ha_clss_shade/issues) ali posljite pull request. Ker je integracija v beta fazi, so vsi prispevki se posebej dobrodosli!

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
| **[HA Assist — Slovenscina](https://github.com/home-assistant/intents/tree/main/sentences/sl)** | Slovenscina za glasovnega pomocnika Home Assistant |

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
