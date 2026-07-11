# Renon / ICOS IT-Ren — Standort, Bonität, Alter (Eingang für Baustein 5)

Schließt die **Hauptlücke** aus Baustein 5: Alter, Bonität und Standort kommen
**nicht** aus der Punktwolke, müssen also extern beigebracht werden. Für den
Renon-Plot (Setup 001) hier dokumentiert; für beliebige Flächen bleibt dies der
externe Aufwand vor jeder Wachstumssimulation.

## Standort

| Größe | Wert | Quelle / Sicherheit |
|-------|------|---------------------|
| Site (ICOS) | **IT-Ren "Renon/Ritten"**, ICOS-Ecosystem, Klasse 2 | ICOS-Stationskennung |
| Lage | Ritten, Südtirol (IT) | — |
| Seehöhe | **~1735 m ü. NN** | Stationsangabe (subalpin) |
| Koordinaten (ca.) | **46.587° N, 11.434° O** | ICOS-Stationsstandort, gerundet |
| Bestandestyp | ungleichaltriger, mehrschichtiger **Fichtenbestand** | Zenodo-Datensatz / Standortbeschreibung |
| Baumart | **Picea abies** (Quasi-Reinbestand) | dito → Artcode **511** |
| Alter | **~200 Jahre** (Oberschicht, ungleichaltrig) | Standortbeschreibung; ungleichaltrig → Alter je Schicht |

## Bonität (site index) — noch zu belegen

TreeGrOSS/BWINPro braucht eine **Oberhöhenbonität** (site index = Oberhöhe im
Referenzalter, meist H100). Sie ist hier **nicht gesichert** und muss über einen
der folgenden Wege bestimmt werden — das ist ein eigener Schritt, kein
Formatierungsproblem:

1. **Ertragstafel-Rückschluss**: aus einer verlässlichen Alter-/Oberhöhen-Angabe
   des Bestands (Oberhöhe = Mittel der ~100 stärksten Bäume/ha) über die
   Fichten-Ertragstafel (z. B. Assmann/Franz) den site index ablesen.
2. **Standortkartierung / forstliche Standortdaten** der Provinz Südtirol.
3. **Feldreferenz**: dendrometrische Aufnahme am Plot.

Aus der abgeleiteten Inventur (`scene.json`) lässt sich die **beobachtete Oberhöhe**
als Anhalt schätzen (Mittel der höchsten Bäume), **ersetzt aber keine Bonität** —
ohne belastbares Alter der Oberschicht bleibt der site index eine Annahme.

> Platzhalter in den Beispielen unten: `site_index = 32.0`. **Vor jeder
> publizierten Prognose durch einen belegten Wert ersetzen.**

## Fertige Bestandeskonfiguration (Eingang treegross_export.py)

`data/renon/renon_stand.json` (Bonität als kenntlich gemachter Platzhalter):

```json
{
  "id": "renon-setup01",
  "area_ha": 0.07,
  "age_years": 200,
  "site_index": 32.0,
  "latitude": 46.587,
  "longitude": 11.434
}
```

`area_ha` = Auswertungskreis der Inventur (Radius 18 m → ~0,10 ha; effektiv
belegter Kreis kleiner). Verwendung:

```bash
python scripts/treegross_export.py export \
    --scene platform/dev-data/media/scenes/renon-setup01/scene.json \
    --out trees.json --default-species "Picea abies" \
    --stand-config data/renon/renon_stand.json --years 20 --step 5
```

## Offen

- [ ] Bonität (site index) belegen statt Platzhalter (Ertragstafel oder Feldreferenz).
- [ ] Oberschicht-Alter je Schicht differenzieren (ungleichaltriger Bestand).
- [ ] `area_ha` gegen den tatsächlich belegten Auswertungskreis präzisieren.
- [ ] LiDAR-BHD gegen Feld-BHD validieren (Kalibrierungsbasis von TreeGrOSS).
