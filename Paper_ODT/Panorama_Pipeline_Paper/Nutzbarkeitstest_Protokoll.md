# Nutzbarkeitstest — Protokoll (Abschnitt 5.4)

Ziel: belegen, dass die GUI-gestützte Kette **ohne Fachwissen** von der Aufnahme
zur veröffentlichten, begehbaren Szene führt. Ergebnis fließt als eine Zahl (SUS)
plus Aufgaben-Erfolg/-Zeit ins Paper.

## Design
- **Teilnehmende:** n = 8–12, fachfremd (keine GIS-/Photogrammetrie-Vorkenntnis),
  gemischt nach Computer-Affinität. (SUS ist ab n≈8 stabil interpretierbar.)
- **Aufbau:** lokal laufender Docker-Stack (Studio-GUI), vorbereitete Beispiel-
  Eingänge auf dem Desktop. Moderiert, „Think-aloud", Bildschirmaufnahme.
- **Ethik/Datenschutz:** Einwilligung, keine personenbezogenen Daten in den
  Uploads, Aufnahmen nur lokal, Widerruf jederzeit.

## Aufgaben (jeweils Erfolg ja/nein + Zeit + Anzahl Hilfestellungen)
1. **Consumer-360:** ein Dual-Fisheye-Bild hochladen → als begehbare Szene
   veröffentlichen. *(Zweig: equirect/fisheye-Autoerkennung)*
2. **Sechs Einzelbilder:** die 6 Renon-Setup-Bilder hochladen → Panorama-Szene.
   *(Zweig: Stitching bzw. Reprojektion via Autoerkennung)*
3. **E57:** eine E57 hochladen → Szene mit Punktwolke. *(Zweig: Reprojektion)*
4. **Kuratieren:** Szene benennen, in der Galerie sichtbar/versteckt schalten.
5. **Teilen:** die veröffentlichte Szene im Browser öffnen und einen Baum-Marker
   anklicken (falls Inventur vorhanden).

Erfolgskriterium je Aufgabe: Zielzustand ohne Eingriff der Moderation erreicht.

## Messgrößen
- **SUS** (System Usability Scale, 10 Items, 5-stufig) → Score 0–100.
- **Aufgaben-Erfolgsrate** (% ohne Hilfe gelöst) und **Median-Zeit** je Aufgabe.
- **Fehler/Reibungspunkte** (offene Notizen, für den Diskussionsteil).
- Optional: **SEQ** (Single Ease Question, 1 Item je Aufgabe).

## SUS-Fragebogen (Standard, Brooke 1996 — ungewichtet, abwechselnd polarisiert)
Skala 1 = stimme gar nicht zu … 5 = stimme voll zu.

1. Ich würde dieses System gern regelmäßig nutzen.
2. Ich fand das System unnötig komplex.
3. Ich fand das System einfach zu benutzen.
4. Ich bräuchte fachliche Unterstützung, um das System zu nutzen.
5. Die Funktionen des Systems waren gut integriert.
6. Das System war zu widersprüchlich.
7. Die meisten würden das System schnell zu bedienen lernen.
8. Das System war sehr umständlich zu bedienen.
9. Ich fühlte mich bei der Nutzung sehr sicher.
10. Ich musste viel lernen, bevor ich loslegen konnte.

**Auswertung:** ungerade Items: Wert − 1; gerade Items: 5 − Wert; Summe × 2,5 =
SUS-Score (0–100). Referenz: ≥ 68 = überdurchschnittlich; ≥ 80 = sehr gut.

## Bericht (Platzhalter fürs Paper)
> n = __, SUS-Median = __ (IQR __–__), Aufgaben-Erfolg __ %, Median-Zeit je
> Aufgabe __ s. Häufigste Reibungspunkte: __. Fazit: __.

## Durchführung — was wo liegt

| Datei | Zweck |
|---|---|
| `Nutzbarkeitstest_Protokoll.md` | dieses Dokument: Design, Kriterien, Auswertungsregel |
| `Nutzbarkeitstest_Aufgabenblatt.md` | **Blatt für die teilnehmende Person** — ohne Erfolgskriterien, damit der Test nicht verraten wird |
| `Nutzbarkeitstest_Formular.html` | **Erfassungsbogen** für die Moderation: Stoppuhr je Aufgabe, Erfolg/Hilfen, SUS-Fragebogen mit Live-Score, offene Fragen. Läuft ohne Server (Datei direkt im Browser öffnen), speichert einen JSON-Bogen je Person |
| `scripts/make_usability_testdata.py` | legt die drei Testdaten-Ordner an, auf die das Aufgabenblatt verweist (Consumer-360-Panorama, acht überlappende Aufnahmen, eine E57) — nur frei lizenzierte Quellen, mit `QUELLEN.txt` daneben |
| `scripts/usability_eval.py` | Auswertung über alle Bögen: SUS-Median mit IQR, Erfolgsquote, Median-Zeit je Aufgabe, genannte Reibungspunkte; `--markdown` gibt den fertigen Block fürs Paper aus |

Vorbereitung einmalig:

```bash
python scripts/make_usability_testdata.py --out ~/Desktop/Testdaten
```

Ablauf je Person (ca. 30–40 min): Einwilligung → Aufgabenblatt aushändigen →
Formular öffnen, je Aufgabe Stoppuhr starten/stoppen und Erfolg eintragen →
SUS ausfüllen lassen → JSON sichern. Danach:

```bash
python scripts/usability_eval.py boegen/*.json --markdown
```

**Warum Median statt Mittelwert:** bei n < 10 verzerrt ein einzelner Ausreißer den
Mittelwert stark; der Median ist robuster. Die Referenzschwelle 68 stammt aus
Sauro & Lewis (2016) als Mittel über mehrere Hundert Studien — sie ist ein
Einordnungspunkt, **keine Bestehensgrenze**.

## Reproduzierbarkeit
Die Testdaten werden von `make_usability_testdata.py` aus frei lizenzierten
Quellen erzeugt: ein Consumer-360-Kugelpanorama (Wikimedia Commons, CC BY-SA),
acht überlappende Aufnahmen aus PASSTA (CC-BY-4.0) und eine Renon-E57
(CC-BY-4.0). Die Einzelbilder werden bewusst auf 1600 px verkleinert — ein
20-Minuten-Stitching wäre im Nutzbarkeitstest ein Messfehler, kein Befund.
