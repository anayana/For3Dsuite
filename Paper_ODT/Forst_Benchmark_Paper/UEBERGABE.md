# Übergabe: Forst-Paper (Paper C) — Stammdetektion in Abhängigkeit von der Umfangsabdeckung

Stand 13.10.2026 · Repo `anayana/For3Dsuite` · Autor: Angel Naya, Independent Researcher, Berlin
(angel.naya@posteo.de)

## 0. Arbeitsweise mit dem Nutzer (verbindlich)

- Deutsch, **kurz und konkret**. Kein Füllstoff, keine langen Optionslisten. Nur exakte
  Bezeichnungen/Links; nichts raten — wenn etwas nicht prüfbar ist, das in einem Satz sagen.
- Nutzer arbeitet **vom Handy**, ohne lokales Docker. PRs mergt **der Nutzer** (Agent darf nicht mergen).
- **Kein Geld:** nur Journals ohne Pflicht-Publikationsgebühr (Abo-/Hybrid-Weg ohne Kosten oder
  Diamond-OA). Keine kostenpflichtigen Dienste (RunPod, HF-Spaces o. ä.).
- **Nur offene Fremddaten und FOSS**, keine eigenen Feldaufnahmen. Lizenzen prüfen
  (`DATA_SOURCES.md`); Daten ohne Lizenz nur zitieren/als Benchmark nutzen, nie weitergeben.
- **Nicht `platform/dev/export_static.py` ohne `--html-only` ausführen** (siehe
  `CLAUDE_CODE_UEBERGABE.md`, Abschn. 0) — würde die Galerie in `docs/` löschen.
- Aus der Cloud-Umgebung gesperrt: zenodo.org, sciencedirect.com, arxiv.org, huggingface.co,
  crossref. **Umweg für offene Daten:** Workflow `.github/workflows/fetch-data.yml` — läuft auf
  GitHub Actions (freies Netz), startet automatisch bei Änderung von `.github/fetch-request.txt`,
  schneidet die benötigten Teile aus und committet nach `extdata/`. Neue Quellen dort ergänzen.
  Erreichbar aus der Cloud: conda-forge (micromamba unter `/opt/mm`, Env `helios` mit HELIOS++ 2.2.2),
  PyPI, raw.githubusercontent.com. Für Texte/PDFs weiter den Nutzer fragen.

## 1. Ziel des Papers

Technisches Methoden-Paper: **Wie viel Umfangsabdeckung des Stammes brauchen TLS-Stammdetektoren
und BHD-Verfahren, um verlässlich zu sein?** Kontrolliertes Experiment mit **HELIOS++**
(synthetische Scans mit variierender Zahl/Anordnung der Scanner-Standpunkte), gestützt durch
echte, gelabelte Wolken.

Auslöser (Befund aus Paper A, `scripts/BENCH_DETECTION.md`): 3DFin erreicht auf SegmentedForests
94–100 % Precision, verweigert aber am Renon-Bestand (Median-Bogen 180°) für 29/37 Stämme den BHD;
3DFin verlangt ≥ 9/16 Sektoren (≈ 202°). Wiener Plots: Median 280–360°.

## 2. Was im Repo schon da ist

| Baustein | Datei |
|---|---|
| Detektions-Benchmark (Baseline, Stammkontinuität, lidR, CSP, 3DFin) auf SegmentedForests | `scripts/BENCH_DETECTION.md`, `validate_detection_gt.py`, `inventory_from_cloud.py`, `run_3dfin_ini.py`, `bench_stems_r.R` |
| BHD-Verfahren (Kreisfit, qsm_wood, 3DFin, CSP) gegen Feld-GT (SYSSIFOSS, nur 5 Bäume!) | `scripts/BENCH_DBH.md`, `bench_dbh.py`, `dbh_methods.py`, `bench_dbh_csp.R` |
| Renon kombiniert (4 Standpunkte, ITCD, BHD nach 6 Verfahren, QSM) | `scripts/RENON_COMBINED.md` |
| HELIOS++-Szene aus Inventur (prozedurale Bäume), Survey mit n Standpunkten, Import | `scripts/helios_scene.py`, `helios_run.py`, `helios_import.py` |
| Verdeckungskarte (Punkte je Standpunkt sichtbar) | `scripts/occlusion_map.py` |
| QSM-Benchmark Wytham | `scripts/bench_qsm_wytham.py` |
| Gelände-Rauheit | `scripts/terrain_probe.py` |

## 3. Offene Daten (Lizenz laut `DATA_SOURCES.md`)

- SegmentedForests (MIT, Zenodo 17396681; Laino et al. 2026, Forestry 99(2)) — Punktlabels Stamm/Äste/Boden/…
- SYSSIFOSS (CC BY 4.0, doi 10.11588/DATA/UUMEDI) — Einzelbäume mit Feld-BHD
- Wytham Woods (CC BY 4.0, Zenodo 7307956) — QSM-Referenz
- Renon / ICOS IT-Ren (CC BY 4.0, Chang et al. 2025, Zenodo 17186174) — kein GT
- TreeScope: **keine Lizenz gefunden** → nur zitieren, nicht weitergeben

## 4. Vorschlag Versuchsaufbau (zu prüfen und zu schärfen)

1. Szenen: Bäume mit bekannter Wahrheit (prozedural aus Inventuren via `helios_scene.py`;
   besser realistische Stammgeometrie, z. B. aus SegmentedForests-Stämmen oder QSM-Zylindern).
2. Variiere Scan-Konfiguration: 1, 2, 3, 4, 6, 9 Standpunkte; Raster vs. Zufall; Abstand.
3. Je Stamm Abdeckungsbogen in Brusthöhe messen (wie in `BENCH_DETECTION.md`).
4. Detektoren/BHD-Verfahren laufen lassen → Recall, Precision, BHD-Bias/RMSE **als Funktion der
   Abdeckung**; Schwellen ableiten (ab wann ist welches Verfahren verlässlich?).
5. Gegenprobe auf echten Daten (SegmentedForests, SYSSIFOSS, Renon).

Rechnen: CPU genügt (HELIOS++, 3DFin, lidR). Keine GPU nötig.

## 5. Journals (Pflicht: ohne Gebühr) — vor Einreichung APC-Regel prüfen

Kandidaten (Hybrid, Abo-Weg i. d. R. kostenlos): *European Journal of Forest Research* (Springer),
*Forestry* (Oxford), *Canadian Journal of Forest Research*, *ISPRS Journal of Photogrammetry and
Remote Sensing* (Elsevier), *PFG* (Springer). **Nicht:** MDPI (Forests, Remote Sensing), Silva
Fennica (APC laut Drittquelle), reine Gold-OA-Journals.

## 6. Bezug zu anderen Papern

- Paper A (Software, Computers & Geosciences, eingereicht/in Einreichung):
  `Paper_ODT/Panorama_Pipeline_Paper/Manuscript_EN.md` — dort nur ein Absatz zum Gültigkeitsbereich.
- Dissertationsrahmen: `DISSERTATION.md` (P1 ≈ dieses Paper, angepasst auf offene Daten statt Feldinventur).

## 7. Erster Schritt für die neue Sitzung

`scripts/BENCH_DETECTION.md`, `BENCH_DBH.md`, `helios_scene.py` lesen → konkreten Versuchsplan
(Szenen, Konfigurationen, Kennzahlen, Rechenaufwand) als `Paper_ODT/Forst_Benchmark_Paper/PLAN.md`
vorlegen und vom Nutzer bestätigen lassen, bevor gerechnet wird.
