# Versuchsplan Paper D — Hedge Vertical Index aus offenem ALS

Stand 07.11.2026 · Entwurf zur Bestätigung · noch nichts gerechnet ·
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

## 2. Daten (Lizenzstand)

| Daten | Rolle | Lizenz | Status |
|---|---|---|---|
| Belgische Hecken-TLS, Zenodo 4487116 (RIEGL VZ-1000, Erle/Birke, Standorte M und T) | Referenz F1 | CC BY 4.0 (laut `seed_hedgerow.py`) | **Erneut prüfen**: zenodo.org ist in der Cloud gesperrt. Lage der Standorte (Koordinaten/CRS) muss für den ALS-Abgleich geklärt sein. |
| DHMV II, flämisches ALS (LAZ, 500-m-Kacheln, Portal EODaS OpenLidar) | ALS am TLS-Standort F1 | **Unklar.** Abgeleitete DHMV-Produkte stehen unter der „Modellicentie Gratis Hergebruik“. Für die Roh-Punktwolke heißt es im Metadatensatz, man solle den Eigentümer kontaktieren. | **Prüfen**, bevor gerechnet wird. Ist die Lizenz nicht offen, Abschnitt 3.1 umbauen (siehe Plan B). |
| AHN (NL), Kachel `C_28FN2.LAZ` | Anwendung F3, Sensitivität F2 | AHN1–4: CC0. AHN5/6: CC BY 4.0. | Prüfen, aus welcher AHN-Version die Kachel stammt, und im Paper richtig zitieren. Im README steht bisher pauschal CC-BY-4.0. |
| PDOK CIR-Luftbild | Pseudo-NDVI (Zusatz) | PDOK-Luftbilder offen (CC BY 4.0 / CC0 je Dienst) | Lizenz des genutzten Dienstes notieren. |

**Plan B, falls DHMV II nicht offen ist:** TLS künstlich zu ALS ausdünnen (Punktdichte und
Einfallswinkel wie bei AHN, ~20 Pkt/m², nur von oben sichtbare Treffer) → F1 wird zur Frage
„Was verliert der Index durch die ALS-Geometrie?“. Das ist schwächer, braucht aber keine weiteren
Daten.

## 3. Versuchsaufbau

### 3.1 Validierung ALS gegen TLS (F1)
- TLS-Bäume je Standort zur Heckenreihe zusammensetzen (Koordinaten sind ko-registriert).
- ALS-Kachel ausschneiden: Puffer um die Reihe, gleiche 20-m-Segmente wie bei TLS.
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
2. Lizenz DHMV II und Lage der TLS-Standorte klären → entscheidet zwischen 3.1 und Plan B.
3. Sensitivität (3.2) auf AHN. Läuft schon mit vorhandenen Daten.
4. Validierung (3.1), Abbildungen, Manuskript nach dem Vorbild von Paper B/C.
