# 360Pano3D Growth Service — TreeGrOSS/BWINPro als JSON-Webdienst (Baustein 5)

Nimmt eine **Baumliste + Bestandesmetadaten** als JSON an, simuliert *n* Jahre mit
**TreeGrOSS** (Kern von BWINPro/ForestSimulator, NW-FVA) und gibt die
**Zukunftsbestände** zurück. Damit läuft der Nutzer im 3D-Viewer nicht nur durch
den heutigen, sondern durch den prognostizierten Wald.

```
LiDAR + RGB  ──►  Bestandesbeschreibung (Position, BHD, Höhe, Art)
             ──►  treegross_export.py  ──►  POST /simulate  ──►  Zukunftsbestände
             ──►  treegross_export.py import  ──►  scene.json (begehbar im Viewer)
```

## Warum ein eigener Dienst? — GPL-Isolation

TreeGrOSS steht unter **GPLv3**. Direktes Einbinden würde die gesamte Suite
ableitungsbedingt unter die GPL zwingen. Deshalb ist die Wachstumssimulation
**bewusst als eigenständiger Prozess** ausgelegt und selbst GPLv3; die übrige Suite
(Python-Pipeline, JS-Viewer) spricht ihn nur über **HTTP/JSON** an und bleibt
entkoppelt und modular. Ohnehin nötige Sprachtrennung: TreeGrOSS = Java,
Verarbeitung = R/Python, Viewer = JS.

Die einzige Stelle, die GPL-Code berührt, ist
[`TreeGrossGrowthEngine`](src/main/java/de/for3dsuite/growth/engine/TreeGrossGrowthEngine.java)
— bewusst dünn gehalten. Die TreeGrOSS-JAR wird **nicht mitgeliefert** (nicht
redistribuiert).

## JSON-Kontrakt

**Anfrage** `POST /simulate` (erzeugt von `scripts/treegross_export.py export`):

```json
{
  "stand":   { "id": "renon-setup01", "area_ha": 0.07, "age_years": 200,
               "site_index": 32.0, "latitude": 46.587, "longitude": 11.434 },
  "simulate":{ "years": 20, "step_years": 5 },
  "trees":   [ { "id": "t001", "species": 511, "dbh_cm": 75.8, "height_m": 26.8,
                 "x": 3.16, "y": 9.45, "crown_base_m": null, "age_years": null,
                 "out_of_stand": false } ]
}
```

**Antwort** (gelesen von `scripts/treegross_export.py import`):

```json
{
  "stand": { ... },
  "periods": [
    { "year": 2044,
      "trees": [ { "id": "t001", "dbh_cm": 82.8, "height_m": 30.4,
                   "alive": true, "removed": false } ] }
  ]
}
```

`species` = BWINPro/TreeGrOSS-Artcode (z. B. 511 = Fichte); Klarnamen ↔ Codes in
der `SPECIES`-Tabelle von `scripts/treegross_export.py`, an die SpeciesDef der
eingesetzten TreeGrOSS-Version anzupassen.

`GET /health` liefert `{ "status": "ok", "engine": "stub" | "treegross" }`.

## Bauen & Starten

Voraussetzung: JDK 17+ und Maven.

```bash
cd growth-service
mvn spring-boot:run          # startet auf Port 8362 (Default-Engine: stub)
```

Test des ganzen Weges gegen eine Demo-Szene:

```bash
# 1. Baumliste aus der Szene erzeugen
python scripts/treegross_export.py export \
    --scene platform/dev-data/media/scenes/renon-setup01/scene.json \
    --out trees.json --default-species "Picea abies" \
    --age 200 --site-index 32 --area-ha 0.07 --years 20 --step 5

# 2. Simulieren
curl -s -X POST localhost:8362/simulate \
     -H "Content-Type: application/json" -d @trees.json > future.json

# 3. Zukunftsbestand (2044) zurück in eine begehbare Szene
python scripts/treegross_export.py import --result future.json \
    --scene platform/dev-data/media/scenes/renon-setup01/scene.json \
    --year 2044 --out-scene scene_2044.json --title-suffix "(Prognose 2044)"
```

## Engines

| `growth.engine` | Klasse | Zweck |
|---|---|---|
| `stub` (Default) | `StubGrowthEngine` | deterministisches Demonstrator-Wachstum **ohne** GPL-JAR — für Entwicklung, Tests, den End-zu-End-Fluss. **Kein wissenschaftliches Modell.** |
| `treegross` | `TreeGrossGrowthEngine` | echte TreeGrOSS/BWINPro-Simulation (GPLv3) |

Umschalten in `src/main/resources/application.properties` oder per
`--growth.engine=treegross`.

### Echte TreeGrOSS-Engine aktivieren

Der Adapter ist **fertig verdrahtet und am realen Lauf verifiziert** (87 Renon-Stämme).
Es fehlt nur die Bibliothek, die aus Lizenzgründen nicht im Repo liegt:

```bash
bash growth-service/lib/fetch_treegross.sh   # holt treegross.zip von der NW-FVA
mvn -f growth-service/pom.xml spring-boot:run -Dspring-boot.run.arguments=--growth.engine=treegross
```

Das Skript lädt die offizielle Distribution (`nw-fva.de`, GPLv3, ~555 kB) und entpackt
`lib/dist/treegross.jar`, die Abhängigkeit `jep-2.4.1.jar` sowie die Modell-Parametersätze
`lib/src/treegross/model/*.xml`. `pom.xml` bindet beide JARs bereits als `system`-scope ein.

**Drei Fallstricke der TreeGrOSS-API** — alle im Adapter berücksichtigt und dokumentiert,
weil sie stillschweigend falsche Ergebnisse liefern statt zu scheitern:

| Fallstrick | Wirkung bei Fehlbedienung | Richtig |
|---|---|---|
| `Tree.out` | `out = 0` ⇒ Baum gilt als **ausgeschieden**, wächst gar nicht | `out = -1` = lebend |
| `Tree.si` (Bonität) | `si = 0` ⇒ **kein Höhenwachstum** | `si = -9` ⇒ Modell leitet die Bonität selbst her |
| Modell-XML | `ForestSimulatorNWGermany.xml` nennt Plugins unqualifiziert ⇒ `ClassNotFoundException: Competition` | `ForestSimulatorNWGermany6.xml` (voll qualifiziert) |

### Verifikation ohne Maven

[`tools/TreeGrossHarness.java`](tools/TreeGrossHarness.java) fährt die Engine ohne Spring:

```bash
cd growth-service/tools
javac -cp ../lib/dist/treegross.jar -d out TreeGrossHarness.java
java -cp "../lib/dist/treegross.jar;out" TreeGrossHarness \
     ../lib/src/treegross/model/ForestSimulatorNWGermany6.xml renon_trees.tsv 20 5 200 0.1
```

Ergebnis am Renon-Bestand (87 Stämme, N/ha 870, G/ha 48 m²) — das Modell reagiert
fachlich plausibel auf das Bestandesalter:

| Bestandesalter | mittl. Höhe nach 20 J. | Zuwachs |
|---|---|---|
| 60 Jahre | 20,0 → **24,5 m** | +4,5 m |
| 120 Jahre | 20,0 → 21,2 m | +1,2 m |
| 200 Jahre | 20,0 → 20,2 m | +0,2 m |

Der geringe Zuwachs am tatsächlichen Renon-Alter (~200 J.) ist damit **echtes
Modellverhalten** eines alten, sehr dichten Bestandes — kein Konfigurationsfehler.

## Ehrliche Einordnung (aus Baustein 5)

- **BHD-Genauigkeit**: TreeGrOSS ist auf **Feld-BHD** kalibriert; LiDAR-BHD hat eine
  andere Fehlerstruktur. Vor belastbaren Prognosen gegen Feldmessung validieren —
  eigener, publikationswürdiger Schritt.
- **Alter/Bonität/Standort** kommen **nicht** aus der Punktwolke (Hauptlücke). Für
  den Renon-Plot dokumentiert in [`data/renon/STANDORT.md`](../data/renon/STANDORT.md);
  für beliebige Flächen extern beizubringen.
- **Dateiformat** ist der kleinste Teil — dieser Kontrakt + der Adapter erledigen ihn.

## Lizenz

GPLv3 (wegen der TreeGrOSS-Abhängigkeit). Siehe GPL-Isolation oben.
