# Kumulative Dissertation — 3-Paper-Gliederung

Aufbau als kumulative Dissertation (3 begutachtete Paper + Mantel/Synthese), wie an
deutschen Forst-/Fernerkundungsfakultäten üblich. Wissenschaftlicher Rahmen:
[EXPOSE.md](EXPOSE.md); ableitbare Größen: [METRIKEN.md](METRIKEN.md).

Roter Faden: **Messung (P1) → Zustand (P2) → Entscheidung (P3)** — ein prüfbarer,
prognosefähiger, begehbarer Bestandeszwilling. Der wissenschaftliche Kern jedes Papers
ist die **Validierung gegen Referenz**; die Suite liefert die Methode, die Feldarbeit die
Belastbarkeit.

---

## Paper 1 — Methodik & Validierung (Fundament)
**Titelidee:** TLS-Einzelbauminventur mit cross-modaler (RGB↔LiDAR) Absicherung.

- **Forschungsfrage:** Belastbarkeit TLS-abgeleiteter Kennwerte (Position, BHD, Höhe,
  Volumen) gegen Referenz; Beitrag der RGB↔LiDAR-Kreuzvalidierung.
- **Beitrag/neu:** wechselseitige Absicherung Struktur ↔ Zustand am selben Baum; ehrliche
  Fehlerbilanz (Verdeckung, Zylinderfit-Bias, Hang, Teilbogen-Sicht).
- **Datenbedarf:** TLS mehrerer Bestände + **Feld-Referenzinventur** (BHD-Kluppung, Höhe);
  optional Benchmark-Ground-Truth (TreeScope) für die Detektionsgüte.
- **Validierung:** Recall/Precision der Detektion, Bias/RMSE BHD & Höhe vs. Feld.
- **Zieljournale:** ISPRS J. Photogrammetry & RS · Remote Sensing · Forest Ecosystems · MEE.
- **Suite-Bausteine:** `inventory_from_cloud`, `validate_treescope`, `crossvalidate_rgb_lidar`.

## Paper 2 — Zustand & Qualität
**Titelidee:** Fernerkundete Vitalität, Totholz und Wertholzfaktoren aus RGB+LiDAR(+NIR).

- **Forschungsfrage:** automatisierte, geometrisch prüfbare Bestimmung von
  Waldschadenszustand (Kronenverlichtung, Totast-Anteil, Verfärbung), Rindenschäden und
  Qualitätsmerkmalen (astfreie Schaftlänge, Astigkeit).
- **Beitrag/neu:** vertikales Kronenprofil je Baum (Kronenansatz, erster Totast,
  Totast-Anteil als Vitalitätsindikator); RGB-Farbe + LiDAR-Struktur trennt „Laub vs. tot";
  optionale Red-Edge/NIR-Fusion für echtes NDVI/NDRE.
- **Datenbedarf:** RGB+LiDAR + **Experten-Zustandsansprache (ICP-Schema)**; optional
  Multispektral-Panoramen; für Wertholz: Referenz-Gütesortierung.
- **Validierung:** Übereinstimmung mit visueller Ansprache; Konfusionsmatrix Schadstufen.
- **Zieljournale:** Forest Ecology and Management · Ecological Indicators · Remote Sensing.
- **Suite-Bausteine:** `qualitative_rgb`, Blatt-Holz-Trennung, QSM, geplantes Kronenprofil.

## Paper 3 — Anwendung & Entscheidungsunterstützung
**Titelidee:** RS-informierte, zustandsgetriebene Behandlungssteuerung im Einzelbaum-
Wuchsmodell.

- **Forschungsfrage:** Einkopplung des fernerkundeten Zustands in Z-Baum-Auswahl und
  Entnahmeplanung (TreeGrOSS); Deckung der Auto-Auszeichnung mit Experten; Entnahme vs.
  Habitat-Belassung.
- **Beitrag/neu:** RS-Zustand → Behandlung-Kopplung; begehbarer digitaler Zwilling von
  heutigem und prognostiziertem Bestand.
- **Datenbedarf:** Inventur+Zustand aus P1/P2, **Bonität/Alter extern**,
  **Praktiker-Auszeichnung** als Referenz; Ertrags-/Wertparameter.
- **Validierung:** Auto-Auszeichnung vs. Forstpraktiker; Szenario-Plausibilität.
- **Zieljournale:** Forestry · European J. of Forest Research · Forest Ecosystems.
- **Suite-Bausteine:** `treegross_export`, growth-service (TreeGrOSS), Splat-/Marker-Viewer.

## Mantel / Synthese
Verklammert P1–P3 zum Gesamtbeitrag; ordnet Grenzen und Ausblick ein. Optionales
**viertes, leichteres Paper** zur offenen Plattform (SoftwareX / Environmental Modelling
& Software) — Gliederung: [SOFTWAREPAPER.md](SOFTWAREPAPER.md), reproduzierbar via
[docker/](docker/README.md).

---

## Grober Zeitplan (~3,5–4 Jahre)
| Phase | Zeitraum | Inhalt |
|---|---|---|
| 0 | M 0–6 | Literatur, Exposé finalisieren, Standorte + Referenzdesign festlegen |
| 1 | M 4–14 | **Feldaufnahme-Kampagne** (TLS + Feldinventur, mehrere Bestände); P1-Analyse |
| P1 | M 12–20 | Paper 1 schreiben & einreichen |
| 2 | M 16–28 | Zustands-/Qualitäts-Ableitung + Expertenansprache; P2 schreiben & einreichen |
| 3 | M 26–40 | Behandlungskopplung + Praktiker-Auszeichnung; P3 schreiben & einreichen |
| Ende | M 38–46 | Mantel/Synthese, Revisionen, Verteidigung |

## Datenbedarf — der Flaschenhals (ehrlich)
Die Suite ist fertig; die Dissertation ist die **Wissenschaft**. Zwingend zu erheben:
1. **Feld-Referenzinventur** (BHD, Höhe) — Validierungsrückgrat P1.
2. **Experten-Zustandsansprache** (Vitalität/Schäden nach etabliertem Schema) — P2.
3. **Praktiker-Auszeichnung** (Z-Bäume, Entnahme) — P3.
4. **Bonität/Alter/Standort** extern — Prognose P3.
5. **Ausreichende Stichprobe**: Rein- **und** Mischwald, mehrere Bestände, für Statistik.

Ohne diese Referenzdaten bleibt es Tooling, keine Dissertation — sie zu erheben ist die
eigentliche Doktorarbeit.
