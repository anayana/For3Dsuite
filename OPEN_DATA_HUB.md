# Open Data Hub Nationalpark Hainich: Nutzen, Grundlagen, Geld, Aufbau, Hardware

Stand 24.11.2026. Grobe Schätzung, Zahlen gerundet.

## Nutzen
**Gesamtwirtschaftlich (nicht hainich-spezifisch):**
- Der Markt für offene Daten in der EU lag 2019 bei 184 Mrd €, für 2025 werden 199–334 Mrd € erwartet (data.europa.eu 2020).
- Für Deutschland schätzte das Europäische Datenportal 2015 ein Potenzial von ca. 43 Mrd €.

**Für den Nationalpark konkret:**
1. **Weniger Aufwand:** Statt einzelner Datenanfragen von Forschung und Bürgern gibt es Selbstbedienung über Portal und Schnittstelle.
2. **Mehr Forschung pro Euro:** 25 Jahre Zeitreihen werden nachnutzbar und Doppelmessungen entfallen. Gute Daten ziehen Projekte und Drittmittel an.
3. **Pflichten in einem Zug erfüllen:**
   - aktive Verbreitung von Umweltinformationen
   - INSPIRE (Schutzgebiete)
   - FFH-Bericht, Wiederherstellungsverordnung, Welterbe-Bericht
4. **Bildung und Tourismus:** Inhalte für Besucherzentren, Schulen und Ranger, darunter 3D-Rundgänge (For3Dsuite).
5. **Akzeptanz:** Entscheidungen des Nationalparks (Prozessschutz, Verkehrssicherung) sind mit Daten belegt.

Ehrlich: Direkte Einnahmen bringt das nicht. Der Nutzen liegt in gespartem Aufwand, Drittmitteln und Legitimation.

## Grundlagen: Steuergeld soll den Bürgern etwas zurückgeben
| Grundlage | Aussage |
|---|---|
| EU-Open-Data-Richtlinie 2019/1024, Art. 10 | Öffentlich finanzierte Forschungsdaten sollen offen verfügbar sein: so offen wie möglich, so geschlossen wie nötig, nach FAIR-Prinzipien |
| Datennutzungsgesetz (DNG) | setzt die Richtlinie um. Erfasst öffentlich finanzierte Forschungsdaten, die schon in Repositorien liegen |
| EU-Durchführungsverordnung 2023/138 (hochwertige Datensätze) | Daten zu Georaum, Erdbeobachtung und Umwelt kostenfrei über Schnittstellen, seit 2024 |
| Umweltinformationsrichtlinie 2003/4/EG, Aarhus-Konvention, UIG | Recht auf Umweltinformation und Pflicht der Behörden zur aktiven Verbreitung. Beruht auf EU-Recht und bleibt deshalb vom Thüringer Abbau bei der Transparenz unberührt |
| INSPIRE 2007/2/EG | Geodaten zu Schutzgebieten als Dienste bereitstellen |
| DFG-Kodex, Leitlinie 13 | öffentlichen Zugang zu Forschungsergebnissen herstellen |
| Horizon Europe | Open-Science-Pflichten für geförderte Projekte |
| UNESCO-Empfehlung zu Open Science (2021) | Wissenschaft als Gemeingut |
| „Public Money, Public Code“ (FSFE) | öffentlich bezahlte Software als freie Software |

**Thüringen:** Das „Erste Thüringer Entlastungsgesetz“ (Juli 2026) schwächt laut netzpolitik.org die
Veröffentlichungspflichten des Transparenzgesetzes. Die Begründung sollte deshalb auf EU-Recht und
auf die Bedingungen der Forschungsförderer gestützt werden.

**Hebel ohne Kosten:**
- **Forschungsgenehmigung des Nationalparks:** Daten und Ergebnisse nach höchstens 2 Jahren Sperrfrist offen ablegen, mit Lizenz CC BY 4.0, Kurzfassung in einfacher Sprache für das Portal.
- Abschreckendes Beispiel: Die Hainich-Baumdaten im Datensatz LIFE+ PROGNOSES sind bis 2030 gesperrt.

## Geld
| Quelle | Antrag stellt | wofür |
|---|---|---|
| EU LIFE, Bereich Umwelt-Governance und Information (60 %) | Nationalparkverwaltung direkt | Aufbau des Portals, Öffentlichkeit |
| ENL Thüringen (80–100 %, Thüringer Aufbaubank) | Nationalparkverwaltung | Teile mit Bezug zu Natura-2000-Management und Monitoring (bei der Aufbaubank klären) |
| NFDI4Biodiversity Flexfunds 2026, NFDI4Earth Incubator (17.500–35.000 €) | Uni als Mitglied des Konsortiums mit dem Nationalpark | FAIR-Datenflüsse, Schnittstellen |
| Prototype Fund (bis 95.000 € in 6 Monaten) | Einzelpersonen oder Team, nicht die Behörde | freie Software, z. B. Viewer, Schnittstelle, auch für andere Nationalparke nutzbar |
| Horizon Europe, Biodiversa+, Digital Europe (Green Deal Data Space) | Verbund, der Nationalpark als Partner | große Lösung |
| BfN, Nationales Monitoringzentrum zur Biodiversität | Auftrag oder Kooperation | Anbindung an das bundesweite Biodiversitätsmonitoring |
| Landeshaushalt (TMUENF) | Haushaltsanmeldung | Betrieb (Pflichtaufgaben, siehe oben) |

**Multiplikator:** Wird das Portal als Vorlage für alle Nationalen Naturlandschaften gebaut, werden
größere Fördertöpfe und mehr Partner möglich.

## Aufbau
**Was man vorne sieht:**
- Forschung: Ergebnisse in drei Sätzen mit Original und Daten
- Karten: Kohlenstoff, Totholz, Habitatbäume, Lücken
- Messnetz live: Klima, Bodenfeuchte, Turm, Dendrometer
- 3D: For3Dsuite
- Arten: zusammengefasst, sensible Arten unscharf
- Downloads und Schnittstelle
- Mitmachen (Citizen Science)

**Technik dahinter (alles freie Software):**
- **Katalog:** CKAN (DCAT-AP.de, wird von GovData eingesammelt)
- **Karten:** GeoServer oder pygeoapi (OGC-Dienste)
- **Datenbank:** PostgreSQL/PostGIS
- **Messnetz:** FROST-Server (OGC SensorThings API)
- **Rasterdaten und Punktwolken:** Cloud-optimierte Formate COG und COPC, gestreamt über HTTP, so dass kein Rechenserver nötig ist
- **Dauerablage:** Zenodo mit DOI, Artfunde zusätzlich an GBIF

**Nicht öffentlich:**
- Horst- und Brutbäume, Fundorte seltener Arten
- Personen auf Wildkamerabildern (DSGVO)
- Rohdaten ohne Freigabe

## Hardware und Betrieb
**Datenmengen (Schätzung):**

| Quelle | Menge |
|---|---|
| ALS (ca. 75 km², ca. 20 Punkte/m², LAZ) | ca. 5–10 GB je Befliegung |
| TLS, Rucksack | 1–5 GB je Aufnahme. Eine 3D-Gaussian-Splatting-Szene (3DGS) 0,1–0,5 GB |
| Wildkameras (z. B. 50 Kameras × 20.000 Bilder × 3 MB) | ca. 3 TB pro Jahr |
| Akustik (Vögel, Fledermaus-Ultraschall) | 2–10 TB pro Jahr |
| Drohnenbilder | 0,5–2 TB pro Jahr |
| Sensoren, Turm | unter 10 GB pro Jahr |

Das ergibt beim Start ein Rohdatenarchiv von 20–50 TB, das um 5–15 TB pro Jahr wächst.
Öffentlich ausgeliefert werden nur aufbereitete Produkte, ca. 1–5 TB.

**Bedarf:**

| Baustein | Auslegung | Kosten |
|---|---|---|
| Anwendungsserver (oder VM) | 16 Kerne, 64 GB RAM, 2 TB NVMe, 1 Gbit/s | 4.000–6.000 € einmalig oder 100–200 €/Monat |
| Hauptspeicher Archiv | ca. 100 TB nutzbar (NAS, ZFS/RAID6), reicht für ca. 5 Jahre | 8.000–12.000 € |
| Sicherung an zweitem Standort | 100 TB | 5.000–8.000 € oder Cloud-Speicher |
| Auslieferung über CDN | 1–5 TB/Monat (3D-Szenen, Karten) | 10–100 €/Monat |
| GPU (Splats, Auswertung) | nicht kaufen: RunPod Community Cloud bei Bedarf, bis 0,30 $/h | wenige 10 € pro Jahr |

**Günstigste Variante:** die Thüringen-Variante (siehe unten).

**Personal (der größte Posten):**
- Aufbau: 1 Vollzeitstelle Datenmanagement und Entwicklung für 1–2 Jahre
- Betrieb: 0,5 Stellen
- Redaktion (Forschung in einfacher Sprache): 0,25 Stellen
- Je Vollzeitstelle ca. 70.000–90.000 € pro Jahr

**Summe:**
- Aufbau ca. 150.000–200.000 € über 1–2 Jahre
- Betrieb ca. 50.000–70.000 € pro Jahr

## Thüringen-Variante: vorhandene Landesinfrastruktur nutzen (empfohlen)
Der Nationalpark ist eine Thüringer Landesbehörde. Was das Land schon betreibt, wird mitgenutzt
statt nachgebaut:

| Was | Wohin | Wer |
|---|---|---|
| Karten des Nationalparks (Kohlenstoff, Totholz, Habitatbäume, Messpunkte, Zonen) als Darstellungs- und Downloaddienste (WMS/WFS/Atom) | **Geoproxy und Geoportal Thüringen**. Damit stehen sie automatisch auch im Geodatenkatalog von GDI-DE und im INSPIRE-Geoportal, und die INSPIRE-Pflicht ist erfüllt. Der Unstrut-Hainich-Kreis, Gera und Weimar veröffentlichen dort schon | TLBG, Kompetenzzentrum GDI-Th (klären, ob dort auch gehostet oder nur durchgeleitet wird) |
| Grunddaten (DGM, DOM, ALS, Luftbilder) | liegen schon offen im Geoportal Thüringen und werden nur verlinkt | TLBG |
| Artfunde | Landes-Artdaten des TLUBN (Kartendienst), zusätzlich GBIF | TLUBN |
| Forschungsdaten aus Projekten mit Thüringer Hochschulen | **REFODAT**, das Repositorium für Forschungsdaten Thüringen: seit 1.11.2024, mit DOI, kostenfrei für Forschende an Thüringer Hochschulen. Sonst Zenodo | TKFDM: Kompetenznetzwerk FDM der Unis Jena, Erfurt, Ilmenau, Weimar |
| Rohdatenarchiv | Landesrechenzentrum oder NAS im Nationalpark | TMUENF bzw. Nationalpark |

**Was der Nationalpark dann selbst baut:**
- **Schmales Portal** als statische Seite:
  - Forschung in einfacher Sprache
  - 3D-Rundgänge (For3Dsuite)
  - eingebettete Karten aus dem Geoportal
  - Messnetz live (FROST-Server auf einer kleinen VM)
- Das ersetzt den eigenen Katalog und den eigenen Kartenserver.

**Partner in Thüringen** für Hosting und Landesmittel:
- Uni Jena (Zedif, TKFDM)
- MPI für Biogeochemie Jena (Turm DE-Hai)
- FH Erfurt (Forst)

Forschungspartner aus Göttingen (Niedersachsen) bleiben möglich. Für Bund und EU spielt das
Bundesland keine Rolle. Landesmittel und Landesinfrastruktur gibt es aber nur über Thüringer Partner.

**Kosten in der Thüringen-Variante (Schätzung):**
- **Hardware:**
  - Archiv ca. 100 TB, NAS mit Sicherung: 13.000–20.000 € einmalig, oder Landesrechenzentrum
  - kleine VM für Portal und Messnetz: 50–100 €/Monat
  - Content Delivery Network für die 3D-Szenen: 10–100 €/Monat
- **Personal:** Aufbau 0,5–1 Stelle für 1 Jahr, Betrieb 0,25–0,5 Stellen
- **Summe:** Aufbau ca. 80.000–120.000 €, Betrieb ca. 25.000–45.000 € pro Jahr. Das ist etwa die Hälfte der Eigenbau-Variante.

**Bisher nicht gefunden:** ein allgemeines Open-Data-Portal des Landes Thüringen für Daten, die
keine Geodaten sind. Für Geodaten ist das Geoportal der richtige Ort.

## Pipeline „Knopf drücken, Karte erscheint im Geoportal Thüringen“
**Ausgangslage:**
- Andere Stellen (Unstrut-Hainich-Kreis, Gera, Weimar, Geologischer Landesdienst) veröffentlichen schon über den Geoproxy der GDI-Th. Der Weg ist also eingeführt.
- Die GDI-Th wird gerade auf **Geoproxy 4.0** umgebaut: cloud- und containerbasiert, mit neuen OGC-API-Diensten (FOSSGIS 2026).
- Nach ThürGDIG gilt der Nationalpark als geodatenhaltende Stelle des Landes. Für INSPIRE-Themen wie Schutzgebiete, Lebensräume und Artverbreitung muss er Dienste und Metadaten bereitstellen und kann die GDI-Th dafür nutzen.

**Drei technische Wege** (alles freie Software):

| Weg | Ablauf | Aufwand beim Nationalpark |
|---|---|---|
| **A: Dienst beim Nationalpark, Geoproxy leitet weiter** (Standard) | QGIS → Plugin **GeoCat Bridge** (ein Klick) → GeoServer mit Stil und Daten, Metadaten in GeoNetwork. Der Geoproxy bindet den Dienst einmal ein, das Geoportal holt die Metadaten regelmäßig ab. Neue Ebenen erscheinen dann automatisch | Server im Landesnetz oder im Landesrechenzentrum, 2–4 Wochen Einrichtung |
| **A2: QGIS Server statt GeoServer** | Das QGIS-Projekt in einen Ordner speichern, QGIS Server liefert es genau so aus, wie es in QGIS aussieht (WMS, WFS, OGC API) | am einfachsten für „schöne Karten“, kein Umrechnen der Stile |
| **B: Lieferung an die TLBG, Hosting im Geoproxy 4.0** | Datenpaket (GeoPackage oder Cloud-optimiertes GeoTIFF, Stil, Metadaten als ISO-XML) per Skript in einen vereinbarten Eingang (SFTP, S3 oder Git), dann veröffentlicht die TLBG | kein eigener Server. Nur möglich, wenn die TLBG das anbietet |
| **C: Downloaddienst als Atom-Feed bzw. OGC API** | Ein Skript erzeugt Dateien, Atom-Feed und Metadaten und legt sie auf einen Webspeicher. Das Geoportal holt die Metadaten ab | sehr einfach, gut für Rasterkarten (z. B. Kohlenstoffkarte) |

**Was beim Knopfdruck passiert** (als Skript bzw. CI-Job):
1. **Eingabe:** QGIS-Projekt (Ebene und Stil) und ein Metadatenformular. Darin stehen Titel, Kurzfassung, Methode, Zeitbezug, Lizenz, Kontakt und der Link zur Studie bzw. DOI.
2. **Prüfen:**
   - Bezugssystem ETRS89/UTM32 (EPSG:25832)
   - Lizenz (DL-DE BY 2.0 oder CC BY 4.0)
   - sensible Inhalte, z. B. Artfundorte vergröbern
   - Metadaten mit der **GDI-DE-Testsuite** prüfen
3. **Erzeugen:**
   - Cloud-optimiertes GeoTIFF oder GeoPackage
   - Stil (SLD bzw. QGIS-Stil)
   - ISO-19139-Metadaten (Bridge oder `pygeometa`)
   - Vorschaubild
4. **Veröffentlichen:**
   - Dienst (Weg A, B oder C) und Metadaten in den Katalog (CSW)
   - optional die Daten mit DOI auf REFODAT oder Zenodo
5. **Erscheinen:**
   - im Geoportal Thüringen, im Geodatenkatalog von GDI-DE und im INSPIRE-Geoportal
   - Die Metadaten verlinken auf die Seite mit Hintergrund im Portal des Nationalparks.

**Mit der TLBG klären** (Kompetenzzentrum GDI-Th, kompetenzzentrum.gdi-th@tlbg.thueringen.de):
1. Welche Wege Geoproxy 4.0 unterstützt (Weiterleitung, Hosting, OGC API)?
2. Welches Metadatenprofil gilt, und wie oft werden die Metadaten abgeholt?
3. Namensregeln und Server-Adressen im Landesnetz.
4. Ansprechpartner und Freigabeweg.

**Aufwand:**
- Einrichtung ca. 1–2 Monate, davon das Meiste für die Abstimmung mit der TLBG.
- Danach dauert jede neue Karte Minuten. Sie erscheint im Geoportal mit der nächsten Abholung der Metadaten.
