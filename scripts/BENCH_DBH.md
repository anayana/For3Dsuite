# BHD-Methoden-Benchmark gegen Feld-Ground-Truth

Vergleicht die **BHD-Genauigkeit** mehrerer TLS-Verfahren auf denselben dichten
Einzelbaum-Wolken (SYSSIFOSS) gegen die **unabhängige Feld-Inventur**.

## Methoden
| Methode | Sprache | Kurz |
|---|---|---|
| `baseline` | Python | numpy-Kreisfit an der Brusthöhen-Scheibe, **laubbelaubte** ganze Wolke |
| `qsm_wood` | Python | derselbe Fit, aber nur **Holzpunkte** (Classification 0, SYSSIFOSS-GT) — das ist per Definition das QSM-BHD (2·Median-Stammradius bei 1,3 m) |
| `3dfin` | Python | [3DFin](https://github.com/3DFin/3DFin) (dendromatics-Bibliothek) |
| `csp` | R | [CspStandSegmentation](https://github.com/JulFrey/CspStandSegmentation) (Frey & Schindler, Uni Freiburg), baut auf lidR |

**FORTLS** ist bewusst NICHT dabei: es setzt Einzelscan-Radialgeometrie voraus und
lässt sich auf die kombinierten Mehr-Scan-Wolken nicht anwenden (`normalize()`
lehnt sie ab). **aRchi** (die R-QSM-Bibliothek der Suite) ist aus CRAN archiviert —
das QSM-BHD ist aber definitionsgemäß der Holz-Stamm-Fit, den `qsm_wood` liefert.

## Ergebnis (5 Bäume mit Feld-BHD, cm)
Siehe [`docs/bench_dbh_results.csv`](../docs/bench_dbh_results.csv).

| Baum | Art | **Feld** | baseline | qsm_wood | 3dfin | csp |
|---|---|--:|--:|--:|--:|--:|
| FagSyl_BR05 | Buche | **61,7** | 58,2 | 59,5 | 51,9 | 67,7 |
| PinSyl_KA09 | Kiefer | **49,7** | 45,1 | 45,8 | 44,5 | 44,9 |
| PinSyl_KA10 | Kiefer | **35,0** | 49,3 | 50,8 | 46,1 | 49,9 |
| QueRub_KA09 | Roteiche | **11,1** | 228 ✗ | 91,8 ✗ | — | — |
| QueRub_KA11 | Roteiche | **34,7** | 35,5 | 33,8 | 29,5 | 22,4 |
| **MAE** (ohne 11-cm-Jungbaum) | | | **5,8** | **5,7** | **7,8** | **9,5** |

**Befunde:** Alle Verfahren scheitern am 11-cm-Jungbaum (Stamm zu dünn, Krone in
Brusthöhe). PinSyl_KA10 (35 cm) überschätzen ALLE (→ Baum/Messhöhe, kein Methoden-
fehler). `qsm_wood` (Holz-only) ist am genauesten und am Jungbaum weit besser als
der laubbelaubte `baseline` (91,8 statt 228). Zur Einordnung: das SYSSIFOSS-Paper
nennt für seine sorgfältige TLS-Methode 3,5 cm RMSE. **n = 5** (nur so viele lokale
Bäume haben Feld-BHD in pytreedb) — klein, aber echt.

## Setup
```bash
# Python
pip install laspy numpy 3DFin        # 3DFin stuft pydantic/laspy -> v1 herunter;
                                     # fuer die uebrige Suite ggf. eigenes venv

# R 4.4.x (NICHT 4.6 -- CRAN-Binaries fehlen), Pakete in eine Nutzer-Lib:
Rscript -e '.libPaths("~/R/lib"); install.packages(c("lidR","CspStandSegmentation"), type="binary")'
```
Feld-GT wird zur Laufzeit aus der öffentlichen pytreedb geladen (geojsons.zip,
Quelle „FI" = Field Inventory). SYSSIFOSS-Wolken: `data/dataverse_files/*.laz`
(mit Classification 0 = Holz / 1 = Laub).

## Laufen
```bash
# Csp (R) zuerst -> CSV
Rscript scripts/bench_dbh_csp.R data/dataverse_files data/_bench_csp.csv ~/R/lib

# Rest + Zusammenfuehrung (Feld-GT, baseline, qsm_wood, 3DFin, + Csp-CSV)
python scripts/bench_dbh.py --csp-csv data/_bench_csp.csv
# -> docs/bench_dbh_results.csv + MAE je Methode
```
