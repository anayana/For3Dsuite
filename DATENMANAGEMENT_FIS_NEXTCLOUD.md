# Nationalpark Hainich: Datenmanagement, Forschungsinformation und Zusammenarbeit

Stand 25.11.2026. Grundsatz: Jede Information hat genau einen Ort. Gearbeitet wird in Nextcloud,
Geodaten laufen über QGIS, dauerhaft veröffentlicht wird auf Zenodo bzw. REFODAT und im Geoportal
Thüringen. Alles ist freie Software.

## Was wohin gehört

| Inhalt | Ort | Automatisch |
|---|---|---|
| Forschungsantrag | Nextcloud Forms | Ein Antrag legt Projekt, Ordner, Seite und Prüfkarte an |
| Projekte, Genehmigungen, Personen, Einrichtungen, Flächen, Ergebnisse (das eigentliche FIS) | Nextcloud Tables, eine Tabelle je Typ, verknüpft über IDs | wird von den Skripten befüllt |
| Prüfung und Genehmigung | Nextcloud Deck (Spalten: neu → in Prüfung → genehmigt → läuft → abgeschlossen) | Karte entsteht mit dem Antrag |
| Bescheid, Vorlagen | Nextcloud Office (Collabora), Vorlage mit Platzhaltern | Bescheid aus Tabellenwerten erzeugt |
| Fristen (Zwischenbericht, Datenablage höchstens 2 Jahre nach Ende) | Nextcloud Kalender | Termine mit Erinnerung angelegt |
| Projektarbeit, Rohdaten, Dokumente | Nextcloud Team-Ordner je Projekt (feste Struktur) | Ordner aus Vorlage angelegt, Versionen automatisch |
| Projektbeschreibung, Wissen, Kompetenzen | Nextcloud Collectives (Wiki) | Seite aus Vorlage, Änderungen mit Name und Zeit |
| Absprachen | Nextcloud Talk | Benachrichtigungen, KI-Bot |
| Fragen „Wer weiß was?“ | Nextcloud Assistant mit Context Chat, lokales Modell | liest Collectives und Tabellen |
| Datenmanagementplan | Vorlage im Projektordner (optional RDMO) | Pflichtfeld im Antrag |
| Untersuchungsflächen | GeoPackage bzw. PostGIS, Bearbeitung in QGIS | Upload geprüft und in Ebene „Projekte“ übernommen |
| Öffentliche Karten | Geoportal Thüringen über den Geoproxy | Knopf-Pipeline aus QGIS |
| Fertige Daten und Code | Zenodo (oder REFODAT mit Hochschulpartner), DOI | Upload über API, DOI zurück in die Tabelle |
| Artfunde | TLUBN-Artdaten, GBIF | Export aus den Projektdaten, sensible Funde vergröbert |
| Publikationen | Tabelle „Ergebnisse“ | wöchentliche Abfrage bei OpenAlex und ORCID nach „Hainich“ |
| Rohdatenarchiv (TB) | Landesrechenzentrum oder NAS | Sicherung nachts |

## Wie alles zusammenspielt (Lebenslauf eines Projekts)

1. **Antrag:** Die Forschenden füllen das Formular aus: Thema, Personen (ORCID), Einrichtung (ROR), Zeitraum, Flächen, Datenmanagementplan.
   Automatisch angelegt werden:
   - Zeile in „Projekte“ mit fortlaufender ID, z. B. HAI-2026-014
   - Team-Ordner aus Vorlage, Gastzugang für die Forschenden
   - Projektseite in Collectives
   - Karte in Deck „neu“
   - Nachricht in Talk an die Forschungskoordination
2. **Prüfung:** Die Flächen erscheinen in QGIS automatisch neben Zonen, Wegen und laufenden Projekten. Konflikte und Doppelungen sind dort sichtbar.
3. **Genehmigung:** Wird die Karte nach „genehmigt“ gezogen, erzeugt das System:
   - den Bescheid aus der Vorlage
   - Fristen im Kalender
   - eine Info an die Ranger, wer wann wo draußen ist
4. **Laufzeit:** Gearbeitet wird im Team-Ordner. Beiträge und Ansprechpartner stehen auf der Projektseite, wer was wann geändert hat, protokolliert Nextcloud. Erinnerungen gehen automatisch raus.
5. **Abschluss:** Die Forschenden markieren fertige Daten mit dem Schlagwort „veröffentlichen“. Dann läuft automatisch:
   - Prüfung (Lizenz, Metadaten vollständig, sensible Fundorte)
   - Upload nach Zenodo mit Metadaten aus der Tabelle, die DOI kommt zurück in Tabelle und Projektseite
   - Geodaten über die Pipeline ins Geoportal, Artfunde an TLUBN und GBIF
6. **Nachlauf:** Die wöchentliche Literaturabfrage findet Publikationen und ordnet sie dem Projekt zu, die Koordination bestätigt.
7. **Berichte:** Jahresbericht, Forschungsbericht und Listen für FFH, Welterbe und Wiederherstellungsverordnung entstehen aus den Tabellen.

## Automatisierung

| Baustein | Werkzeug (frei) |
|---|---|
| Auslöser | Nextcloud Webhooks bzw. Flow (Regeln), daneben zeitgesteuerte Skripte (systemd-Timer) |
| Logik | Python-Skripte, alternativ Node-RED (Apache-2.0). n8n ist keine freie Software |
| Schnittstellen | Nextcloud (WebDAV, Tables-, Forms- und Deck-API), Zenodo-API, OpenAlex-API, ORCID-API, PyQGIS bzw. qgis_process, GDI-DE-Testsuite |
| Vorlagen | Ordnerstruktur, Projektseite, Bescheid, Datenmanagementplan, Metadaten (DataCite-Felder) |

Die Skripte laufen auf demselben Server wie Nextcloud, gepflegt in einem Git-Repositorium.

## Zusammenspiel der drei Bereiche
- **Forschungsinformation (Tables):** wer, was, wo, wann, mit welcher Genehmigung, mit welchem Ergebnis.
- **Datenmanagement (Ordner, Datenmanagementplan, Zenodo, Geoportal):** wo die Daten liegen, in welcher Form, ab wann offen.
- **Zusammenarbeit (Collectives, Talk, Deck, Whiteboard, KI-Bot):** wie gearbeitet und gefragt wird.

Verbunden über eine Projekt-ID, ORCID für Personen, ROR für Einrichtungen und DOI für Ergebnisse.

## Betrieb und Regeln
- **Hosting:** Nextcloud im Landesrechenzentrum oder bei einem deutschen Anbieter. Keine US-Clouds wegen der DSGVO. openDesk enthält Nextcloud.
- **Rechte:**
  - Interne Gruppen für Koordination, Ranger und Fachbereiche
  - Gastkonten für Forschende
  - Öffentlich ist nur, was über Zenodo und das Geoportal geht
- **Datenschutz und Personalrat:** Das Protokoll, wer was geschrieben hat, und die Steckbriefe sind mitbestimmungspflichtig. Die Steckbriefe sind freiwillig.
- **Forschungsgenehmigung als Hebel:** Datenablage und Veröffentlichung als Auflage festschreiben.
- **Personal:** Forschungskoordination ca. 0,25–0,5 Stellen. Technik: Aufbau ca. 2–3 Monate, danach wenige Stunden pro Monat.

## Reihenfolge
1. Nextcloud mit Team-Ordnern, Collectives, Talk und Deck einrichten. Die Projektseiten (Hainich_Collective.zip) hochladen.
2. Tabellen für das FIS anlegen, Antragsformular erstellen, Altbestand seit 1997 eintragen.
3. Automatisierung: zuerst Antrag → Anlage, dann Fristen, Literaturabfrage, Zenodo-Upload.
4. QGIS-Ebene „Projekte“ und Geoportal-Pipeline.
5. KI-Bot, wenn genug Inhalt da ist.
