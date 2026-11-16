# Projekt: Kronendach, Licht und Mikroklima aus offenen Q-ForestLab-Daten

Ziel: aus offenen TLS-Daten von Q-ForestLab (Universität Gent, CC BY 4.0) zeigen,
wie 3D-Struktur → Lichtdurchgang → Mikroklima-Pufferung zusammenhängen, für
tropischen und gemäßigten Wald. Die Arbeit ist eine Machbarkeitsdemonstration,
keine Validierung, weil es keine eigenen Mikroklima-Messungen gibt.

**Stand wird hier gepflegt.** Bricht eine Sitzung ab: diese Datei lesen und beim
ersten offenen Punkt weitermachen.

## Daten (alle CC BY 4.0, nur Zenodo)

| Baustein | Zenodo | Inhalt |
|---|---|---|
| Instanz-Benchmark | 16875688 | 4 Plots, je Punkt Baum-ID: Robson Creek (Regenwald AUS), Litchfield (Savanne AUS), Wytham Woods (Laubwald UK), Ofental (Nadelwald DE). Teilfläche „test“ je Plot per Range-Request aus dem ZIP (Deflate64 → `pip install zipfile-deflate64`) |
| Große alte Bäume | 15880857 | QSMs (TreeQSM `.mat`) je Baum: nur Bodenscan (`*_tls_wood_qsm.mat`) vs. Boden + Kronenscan (`*_clstls_wood_qsm.mat`); BRA, PER1/2, COL, AUS1/2 |
| ForEdgeClim | 19630260 | Randklima-Modell (R), MIT-Lizenz, Q-ForestLab |

## Schritte und Stand

- [x] 1. Robson Creek als Szene (Detektion + ITCD gegen Ground Truth) — `qforest-robsoncreek`, PR #21
- [x] 2. Strukturprofile + Schichten + Lichtkarte je Plot — `scripts/qforest_profile.py`
      (Robson Creek: PAI-Proxy 10,7, Licht senkrecht 1,1 %, stabil bei 0,1/0,2 m Voxel)
- [ ] 3. **läuft** — Die drei übrigen Plots über GitHub Actions — `.github/workflows/qforest.yml`,
      ausgelöst durch Änderung an `.github/qforest-request.txt`; Ergebnisse landen in
      `extdata/qforest/<plot>_*` und `docs/media/scenes/qforest-<plot>/`.
      Prüfen: Actions-Tab → Workflow „qforest“; danach Kennwerte in
      `extdata/qforest/<plot>_test_kennwerte.json`. Fehlschlag → Log lesen, Skript
      fixen, `.github/qforest-request.txt` ändern und pushen.
- [x] 4. QSM-Szene Brasilien `qforest-qsm-bra` (`scripts/qforest_qsm.py`): Kronenscan bringt
      +38 % Astlänge, +20 % Äste, +5 % Holzvolumen; 23 % der Holzpunkte nur vom
      Kronenscan (`extdata/qforest/bra_qsm_vergleich.json`)
- [ ] 5. ForEdgeClim: Eingaben lesen, an Wytham laufen lassen, virtuelle Störung
      (ein Kronenbaum per Instanz-ID entfernt → Licht/Temperatur vorher/nachher)
- [ ] 6. Vergleich der vier Plots (Profile übereinander, Kennzahlentabelle)

## Methoden (Festlegungen)

- **Voxel:** festes Gitter 0,2 m. Deckung je Voxel = Anzahl 2-cm-Punkte / (0,2/0,02)²,
  höchstens 1. Binär (belegt/leer) verworfen: bei 0,5 m und auch 0,1 m ist im Regenwald
  jede Säule zu, Licht 0 %. Keine schichtabhängigen Voxelgrößen.
- **Profile:** PAI-Proxy (Deckung × Voxelfläche / Bodenfläche) je 1-m-Höhenschicht über Boden (Boden aus den
  Bodenpunkten des Datensatzes). Kennwerte: Kronendachhöhe (P95/P99), Deckungsgrad,
  Effective Number of Layers (Ehbrecht et al.), Foliage Height Diversity (MacArthur).
- **Schichten:** fest, relativ zur Kronendachhöhe H: Boden < 0,5 m, Unterwuchs
  0,5–2 m, untere Schicht 2 m–0,33 H, mittlere Schicht 0,33–0,66 H, Kronendach > 0,66 H.
- **Licht:** Transmission je Bodenzelle (0,5 m) = Produkt (1 − Deckung) der Voxel auf
  dem Strahl: senkrecht und entlang des Sonnenstands (Tagesgang, gewichtet mit
  sin Höhe) zur Tag-und-Nacht-Gleiche und zu beiden Sonnenwenden.
- **Grenzen:** keine Scannerstandorte → keine Strahlverfolgung mit Verdeckungs-
  korrektur; das obere Kronendach (v. a. Tropen) ist unterschätzt. Teilflächen sind
  klein (Robson Creek 0,05 ha). Aussagen relativ, nicht absolut.
