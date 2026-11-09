# Versuchsplan Paper D — Hedge Vertical Index aus offenem ALS

Stand 07.11.2026 (Lizenzen geprüft) · Entwurf zur Bestätigung · noch nichts gerechnet ·
`shrub_div` ist öffentlich auf GitHub (GPL-3.0, Stand 08.11.2026), Demo läuft. Analyse nur in R.

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

## 7. Ergebnisse F2 (Sensitivität, gerechnet 08.11.2026)

Daten: AHN4 (CC0), GeoTiles 28FN2_16 + 28FN2_21, Ausschnitt 1 km², 25,9 Mio. Punkte
nach Gebäude-/Wasserfilter. Heckennetz 64 Teile, 19 210 m². Skript `R/hvi_sensitivity.R`,
Tabellen in `results/sensitivitaet/`.

- Segmente: 10 m → 500, 20 m → 173, 40 m → 44.
- **Segmentlänge ist der größte Hebel:** Rangkorrelation (Spearman, 1-m-Zellen) gegen die Basis
  (20 m, lokal, arithmetisch) nur 0,55–0,58 bei 10 m und 0,65–0,66 bei 40 m. Überlappung der
  Top-25 % nur 38–41 % (10 m) bzw. 57–63 % (40 m).
- **Normierung und Aggregation verschieben die Rangfolge kaum** (Spearman 0,96–0,97 bei 20 m),
  senken aber das Niveau: Das geometrische Mittel drückt den Median um 0,04–0,05. Die feste
  Normierung staucht die Spannweite (p05–p95 0,54–0,69 statt 0,48–0,73).
- Varianzanteile (Zellwerte): Lage der Zelle 54 %, Aggregation 9 %, Normierung 1 %,
  Segmentlänge 0,4 % als Haupteffekt, Wechselwirkungen 35 %. Die Segmentlänge wirkt also nicht
  auf das Mittel, sondern auf die Rangfolge.
- Arteignung: Streng gegen tolerant ändert stärker als die Segmentlänge (Goldammer 0 % → 7–14 %,
  Neuntöter 4–12 % → 20–26 %). Fledermaus bleibt bei 92–100 %.

## 8. Adaptive Segmente statt festem Raster (gerechnet 08.11.2026)

Idee des Nutzers: Ein 40-m-Stück nicht mitteln, sondern weiter teilen, z. B. 5 m geeignet und
Rest. Umsetzung `R/hvi_adaptiv.R`: Grundeinheit sind 5-m-Zellen (Median 432 Punkte je Zelle,
5 %-Quantil 164). Benachbarte geeignete Zellen werden je Art zu Flecken zusammengefasst
(Ergebnisse in `results/adaptiv/`, Flecken als GeoPackage).

**Feste Segmente verlieren den größten Teil der kleinen geeigneten Abschnitte.** Bezug ist die
geeignete Fläche laut 5-m-Zellen, Aggregation tolerant:

| Art | verpasst mit 20 m | verpasst mit 40 m |
|---|---|---|
| Neuntöter | 43 % | 57 % |
| Dorngrasmücke | 56 % | 91 % |
| Goldammer | 65 % | 81 % |
| Wildbienen | 82 % | 84 % |
| Fledermaus | 0 % | 0 % |

Ursache: Die geeigneten Flecken für Hecken-Vögel sind kurz. Der Median liegt bei 5 m, der größte
Fleck misst 60–80 m. Nach dem Mitteln in 20/40 m kippen sie unter 0,5. Die Fledermaus-Leitstruktur
dagegen ist durchgehend (Flecken bis über 500 m) und deshalb unempfindlich.

Vorbehalte:
- 5-m-Zellen sind verrauschter, ein Teil der kleinen Flecken kann Messrauschen sein.
- Die Länge ist über die Zahl der Zellen geschätzt; diagonal verlaufende Hecken überschätzen sie.
- Strukturbezogenes Verschmelzen (Region-Merging) ergibt 503–1060 Einheiten mit Median 5 m.
  Die geringe Streuung innen ist durch das Verfahren vorgegeben und kein unabhängiger Beleg.

Nächster Schritt: Mindestlänge je Art aus der Literatur (Revier bzw. Nistplatz), Flecken
darunter verwerfen. Stabilität der 5-m-Zellen prüfen (Zellen um 2,5 m verschieben und vergleichen).

## 9. Stabilität der eignungsbasierten Flecken (gerechnet 08.11.2026)

`R/hvi_stabilitaet.R`. Gemessen wird die Übereinstimmung der geeigneten Fläche (Jaccard,
1-m-Zellen), wenn das Raster verschoben wird:

| Art (tolerant) | festes 5-m-Raster | festes 20-m-Raster | gleitendes 5-m-Fenster |
|---|---|---|---|
| Neuntöter | 0,61 | 0,67 | **0,75** |
| Dorngrasmücke | 0,51 | 0,45 | **0,69** |
| Goldammer | 0,51 | 0,58 | **0,70** |
| Wildbienen | 0,39 | 0,42 | **0,59** |
| Fledermaus | 0,98 | 1,00 | 0,99 |

Ein festes Raster (egal ob 5 m oder 20 m) liefert Flecken, die zur Hälfte von der Rasterlage
abhängen. **Gleitendes Fenster** (Eignung je 1-m-Zelle gemittelt über 4 verschobene
5-m-Raster, danach Schwelle 0,5) hebt die Übereinstimmung auf 0,6–0,75. → Hauptverfahren.
Goldammer streng bleibt instabil (0,28), weil fast nichts geeignet ist (53 m²).

## 10. Zeigerarten — Entscheidung 08.11.2026 (Nutzer)

- **Wildbienen gestrichen.** Sie hängen an Blüten und offenem Boden, das sieht ALS kaum.
- **Fledermaus kein Art-Eignungswert mehr**, sondern Netz-Kennwert „Leitstruktur“:
  Lückenlängen, zusammenhängende Netzlänge, Anteil hoher Bäume. Begründung: Die Hecke ist für
  Fledermäuse eine Flugroute (Verboom & Huitema 1997, Landscape Ecology; Boughey et al. 2011,
  Biological Conservation — im Volltext prüfen). Entscheidend ist die Durchgängigkeit, nicht die
  Struktur je 5 m. Pro Stück war der Wert gesättigt (92–100 %).
- **Neu:** Haselmaus (dicht, vernetzt, mehrschichtig), Heckenbraunelle (dichter Unterwuchs
  0,5–2 m), Bluthänfling (jung, niedrig, lückig), Steinkauz (alt, Überhälter/Kopfbäume).
  Damit deckt die Auswahl den Bereich von jung und niedrig bis alt und baumreich ab.
- **Bleiben:** Neuntöter, Goldammer, Dorngrasmücke.
- **Alle Eignungskurven mit Literaturquelle** (Schwellenwerte aus Studien, nicht geschätzt).
  Neue Spalte `quelle` in `species_requirements.csv`.
- Mehrskaliger Ansatz: Nistplatz (~1 m, Dichte-Hotspot je Schicht, Mean Shift/Kerndichte mit
  mehreren Radien; Dichte als Trefferanteil, nicht als Punktzahl, wegen Flugstreifen-Überlappung)
  und Revier (gleitendes Fenster, Zehner-Meter).

## 11. Externe Validierung, Dorngrasmücke Rotterdam (gerechnet 08.11.2026)

`R/hvi_validierung.R`. Das Verfahren lief unverändert auf 12 AHN4-Teilkacheln (je ca. 1,25 km²)
am Nordostrand von Rotterdam. Unabhängige Funde: NHM Rotterdam Observations 2 (GBIF, CC BY 4.0,
Fachökologen, ±5 m), Dorngrasmücke, Mai–Juli 2018–2024. Vergleich: Eignung am Fundpunkt
(Maximum im 5-m-Umkreis) gegen 5000 Zufallspunkte auf Heckenzellen. Kennzahl AUC
(0,5 = Zufall, 1 = perfekt).

- 329 Funde im Gebiet, davon nur **126 (38 %) an einer Hecke** laut unserer Maske. Die übrigen
  liegen in Schilf, Brachen oder breitem Gebüsch, das die Schmalheitsmaske nicht als Hecke zählt.
- **Dorngrasmücke-Kurve: AUC 0,58–0,59** (p < 0,003). Signifikant, aber schwach.
- Die Neuntöter-Kurve trennt die Dorngrasmücken-Funde **besser** (AUC 0,60–0,63) als die eigene
  Kurve → Die Dorngrasmücken-Kurve ist falsch eingestellt. Die Funde liegen an niedrigeren
  Hecken: Fledermaus-Leitstruktur (hohe Hecken) AUC 0,35, d. h. Funde meiden hohe Hecken. Das
  passt zur Literatur (Stoate & Szczur 2001: Heckenhöhe wirkt negativ).
- Folgerung: Struktur aus ALS trägt messbar Information über das Vorkommen, aber die von Hand
  gesetzten Kurven sind nicht artspezifisch genug. → Kurven aus Literatur belegen und mit
  Funddaten kalibrieren (Kalibrier- und Testgebiet getrennt halten, sonst Überanpassung).
- Vorbehalte: Beobachterfehler (Funde häufen sich an Wegen), Hintergrund nur Heckenzellen,
  Dorngrasmücke ist keine reine Heckenart.

## 12. Literaturkurven und neue Kennwerte (09.11.2026)

- Neue Eignungstabelle `data/arten_eignung.csv` mit Beleg und Quelle je Kurve (siehe
  `lit/eignungskurven_quellen.md`). Arten: Dorngrasmücke, Goldammer, Neuntöter, Bluthänfling,
  Heckenbraunelle, Haselmaus. Wildbienen gestrichen, Fledermaus als Netz-Kennwert.
- Neue Kennwerte in `R/hecken_funs.R` (`extra_metrics`): Breite, Dichte 0,2–2 m (Trefferanteil),
  Baumanteil, Krautsaum-Breite, Grabentiefe (aus DTM), Abstand zum Wald, Verbundlänge
  (Lücken ≤ 3 m).
- **Fehler gefunden: Die Heckenmaske (CHM 1–8 m) erfasst auch Unterholz und Ränder im Wald.**
  Im Twente-Ausschnitt lagen 356 von 1206 5-m-Zellen (30 %) im Wald. Wald = Gehölz > 30 m breit
  und ≥ 1 ha, nachdem Lücken bis 3 m im laubfreien Kronendach geschlossen sind. Waldzellen werden
  jetzt ausgeschlossen. → Sensitivität (§ 7), adaptive Segmente (§ 8) und Stabilität (§ 9)
  müssen mit Waldausschluss neu gerechnet werden.
- **Krautsaum in AHN kaum sichtbar:** In der Hälfte der Zellen ist er 0 (laubfreie Befliegung).
  Das schwächt genau den Kennwert, der für Dorngrasmücke und Goldammer am stärksten belegt ist
  (Stoate & Szczur 2001). Im Paper als Grenze nennen; Alternative prüfen: Sommerbefliegung
  oder Sentinel-2.
- Validierung Rotterdam läuft neu mit Literaturkurven (`valid2`).
