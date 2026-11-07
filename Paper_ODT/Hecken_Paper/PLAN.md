# Versuchsplan Paper D — Hedge Vertical Index aus offenem ALS

Stand 07.11.2026 (Lizenzen geprüft) · Entwurf zur Bestätigung · noch nichts gerechnet ·
Blocker: `shrub_div` noch nicht auf GitHub (siehe UEBERGABE.md §1)

## 1. Forschungsfrage

**Wie gut bilden Strukturkennwerte aus offenem, landesweitem ALS die Heckenstruktur ab, und wie
stark hängt ein zusammengesetzter Heckenindex (HVI) von den Entscheidungen bei Segmentierung,
Normierung und Aggregation ab?**

Teilfragen:
- F1 (Validierung): Wie gut stimmen h_p95, Schichtzahl, FHD und Breite aus ALS mit TLS am selben
  Heckenabschnitt überein? (Bias, RMSE, Rangkorrelation)
- F2 (Sensitivität): Wie stark verschieben Rastergröße (10/20/40 m), Normierung (lokal 2.–98.
  Perzentil vs. feste Schwellen) und Aggregation (geometrisch/Liebig vs. arithmetisch) die
  Rangfolge der Segmente und die Arteignung?
- F3 (Anwendung): Was zeigt der HVI auf einem AHN-Ausschnitt (NL)? Pseudo-NDVI aus CIR nur als
  Zusatz.

Beitrag: offene, reproduzierbare Kette (R/lidR, CPU) + ehrliche Fehlerbilanz eines Heckenindex —
nicht nur ein weiterer Index.

## 2. Daten (Lizenz geprüft 07.11.2026)

| Daten | Rolle | Lizenz | Befund |
|---|---|---|---|
| Belgische Hecken-TLS, Zenodo 4487116 (Van Den Berge et al. 2021, RIEGL VZ-1000, laubfrei) | Referenz Baumschicht | **CC BY 4.0** (geprüft) | 69 Bäume (39 Eiche, 19 Erle, 11 Birke), Plots M1–M19 in **Meerhout**, T1–T19 in **Turnhout**, Typ Hecke (H) oder Baumreihe (T). **Nur freigestellte Bäume, keine Sträucher.** **Koordinaten nur lokal** (Stammlage relativ zum Plot), keine Lage der Plots. |
| DHMV II, flämisches ALS (LAZ, Portal EODaS OpenLidar) | ALS Flandern | **Offen zur Weiterverwendung.** So steht es im Handbuch des Portals (v3, 06.11.2023), mit Verweis auf die Bedingungen für flämische Open Data. Der ältere Metadatensatz erlaubt die Nutzung dagegen nur für Aufgaben im öffentlichen Interesse nach Registrierung → im Paper das Handbuch zitieren. Rohdaten nicht weitergeben, nur Quelle angeben. | Befliegung 2013–2015, also Jahre vor der TLS-Aufnahme. |
| AHN (NL), Kachel `C_28FN2.LAZ` | Anwendung F3, Sensitivität F2 | AHN1–4: CC0. AHN5/6: CC BY 4.0. | AHN-Version der Kachel prüfen; im README steht bisher pauschal CC-BY-4.0. |
| PDOK CIR-Luftbild | Pseudo-NDVI (Zusatz) | je Dienst CC BY 4.0 oder CC0 | Lizenz des genutzten Dienstes notieren. |

**Folge für F1:** Ohne Plot-Koordinaten lässt sich ALS nicht Segment für Segment mit TLS
vergleichen. Zwei Wege:
- **(a) Hauptweg, ohne weitere Daten:** ALS aus TLS simulieren. Die TLS-Hecke wird ausgedünnt,
  sodass nur Treffer von oben bleiben, wie bei ALS (AHN/DHMV-Dichte ~16–20 Pkt/m²). Dann werden
  die Kennwerte aus der vollen und der ausgedünnten Wolke verglichen. F1 heißt damit: Was verliert
  der Index durch die ALS-Geometrie?
- **(b) Zusatz:** die Autoren (Univ. Gent, Forest & Nature Lab) per E-Mail um die Plot-Koordinaten
  bitten. Mit ihnen ist ein echter Abgleich mit DHMV II möglich, mit Zeitversatz als Vorbehalt.

Grenze in beiden Fällen: Die TLS-Referenz deckt nur die Baumschicht ab. Für die Strauchschicht
(Schichtzahl, Lücken unten) gibt es keine offene Referenz, und das gehört ins Paper.

## 3. Versuchsaufbau

### 3.1 Validierung ALS gegen TLS (F1)
- TLS-Bäume je Plot zusammensetzen (innerhalb des Plots ko-registriert).
- Weg (a): simuliertes ALS (Ausdünnung, Sicht von oben, Dichtestufen 5/10/20 Pkt/m²).
  Weg (b), sobald Koordinaten da sind: DHMV-II-Ausschnitt, Puffer um die Reihe.
- Für beide dieselben Kennwerte mit **demselben Code** (`hvi_metrics.R`) berechnen: h_p95,
  h_mean, Schichtzahl, FHD, Breite, Lückenanteil.
- Auswerten: Bias, RMSE, Spearman je Kennwert. Anschließend HVI aus ALS gegen HVI aus TLS.
- Zeitversatz zwischen TLS- und ALS-Aufnahme notieren (Rückschnitt der Hecke als Fehlerquelle).

### 3.2 Sensitivität (F2), AHN-Ausschnitt 1 km²
Volles Raster, insgesamt 3 × 2 × 2 = 12 Varianten:
- Segmentlänge: 10 / 20 / 40 m
- Normierung: lokal (2.–98. Perzentil) / fest (Schwellen aus der Literatur oder aus TLS)
- Aggregation: geometrisch (Liebig) / arithmetisch

Kennzahlen: Spearman der Segmentränge gegen die Basisvariante (20 m, lokal, Liebig), Anteil der
Segmente, die die Klasse wechseln, und Zahl der geeigneten Segmente je Zielart (> 0,5).
Zusätzlich: Wirkung von `cover_frac` mit und ohne Maskenzirkel. Vegetationsmaske gegen ein
unabhängiges Heckenpolygon, falls ein offenes für NL existiert (z. B. BGT/TOP10NL, Lizenz prüfen).

### 3.3 Anwendung (F3)
Galerie-Szene `scene-hvi-ahn-hedges` als Abbildung; Arteignung streng/tolerant als Tabelle.
NDVI nur deskriptiv.

### 3.4 Offen benannte Grenzen
HVI ist relativ, die Antwortkurven der Arteignung sind unkalibriert (Literaturwerte, keine
Feldvalidierung), der Pseudo-NDVI stammt aus 8-Bit-JPEG.

**Rechnen:** nur CPU (R, lidR, sf), lokal. Keine GPU, kein RunPod.

## 4. Code und Daten im Paper
- `shrub_div` öffentlich (GPL-3.0-or-later) + Release als Zenodo-DOI. Im Text nur die DOI, keine
  GitHub-Links.
- Ergebnistabellen und Skripte als Zenodo-Paket. Rohdaten nur über die Quell-DOIs.

## 5. Zieljournal (ohne Gebühr, Abo-Weg)
1. **Landscape Ecology** (Springer, Hybrid). Passt zu Struktur und Habitat sowie zur
   Landschaftsskala. Erste Wahl.
2. Agriculture, Ecosystems & Environment (Elsevier, Hybrid). Ökologischer Schwerpunkt, F1 allein
   reicht dort nicht.
3. Landscape and Urban Planning (Elsevier, Hybrid). Nur, wenn die Anwendung stärker wird.

Nicht: Ecological Indicators (Gold-OA mit Gebühr), MDPI. Die APC-Regel vor der Einreichung auf der
Journalseite nachprüfen.

## 6. Reihenfolge
1. `shrub_div` auf GitHub → in die Sitzung holen.
2. E-Mail an die Autoren wegen der Plot-Koordinaten (optional, Weg b). Weg (a) läuft ohne.
3. Sensitivität (3.2) auf AHN. Läuft schon mit vorhandenen Daten.
4. Validierung (3.1), Abbildungen, Manuskript nach dem Vorbild von Paper B/C.
