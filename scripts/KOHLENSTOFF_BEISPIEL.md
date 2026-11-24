# Kohlenstoff aus TLS: Beispiel Wienerwald-Buche

Skript: `scripts/kohlenstoff_beispiel.py` · Ergebnis: `scripts/kohlenstoff_beispiel.json`
Daten: Szene `segforests-vienna-beech` (SegmentedForests plot_06, Rotbuche, ~0,13 ha, TLS Riegl VZ-2000i).

## Bestand
66 Bäume (508 je ha), Grundfläche 42,3 m²/ha, Stammvolumen 467 m³/ha.

## Befund zum QSM
- **Stammvolumen aus dem QSM ist plausibel:** In der Bestandessumme liegt es nah an der Formzahl-Schätzung (π/4·D²·H·0,5). Bei 43 von 66 Bäumen liegt es im plausiblen Bereich, bei den übrigen (vor allem dünne Bäume) wird das Volumen aus der lokal angepassten Allometrie geschätzt.
- **Kronenholz aus dem QSM ist im belaubten Scan unbrauchbar:** Das Verhältnis Gesamtholz zu Stamm liegt im Median bei 3,2, plausibel wären für Buche ca. 1,15–1,40. Blätter werden als dicke Zylinder modelliert. Äste deshalb über einen Expansionsfaktor.
- **Offen:** Das Suite-QSM ist noch nicht gegen TreeQSM geprüft (`bench_qsm_wytham.py`). Für Kronenholz braucht es unbelaubte Scans (vgl. Calders et al. 2022).

## Ergebnis (Annahmen in Klammern)
| Weg | oberirdisch t/ha | t CO₂/ha (mit Wurzeln) |
|---|---|---|
| TLS: Stamm aus QSM × Dichte × Astfaktor | 327 | **713** (Spanne 612–867) |
| Generische Allometrie (Jenkins et al. 2003, BHD) | 400 | 874 |

Annahmen: Raumdichte 0,56 t/m³ (0,54–0,58), Astfaktor 1,25 (1,15–1,40), Kohlenstoffanteil 0,48, Wurzel/Spross 0,24 (0,20–0,30).

## Lokale Allometrie
Stammvolumen V = 7,75·10⁻⁵ · D^1,73 · H^1,08 (m³; D in cm, H in m). Angepasst per nichtlinearer Regression mit heteroskedastischer Varianz Var ∝ f^(2·0,69).

Fehler je Baum (Leave-one-out, relativer RMSE / Bias):
| Prädiktoren | RMSE | Bias |
|---|---|---|
| BHD + Höhe (TLS), log-OLS + Baskerville | 23,5 % | +0,5 % |
| BHD + Höhe (TLS), NLS heteroskedastisch | 24,7 % | −0,3 % |
| Höhe × Kronendurchmesser (ALS-artig) | 29,4 % | +0,4 % |
| nur Höhe | 38,1 % | −1,3 % |

## Senke aus der TreeGrOSS-Prognose (2026–2056, ohne Störungen)
713 → 1.291 t CO₂/ha, also ca. **19 t CO₂/ha/Jahr**. Zum UBA-Satz (350 €/t) entspricht das ca. 6.700 €/ha/Jahr.
Das ist eine reine Modellprojektion: Dürre-Mortalität und Totholzabbau sind nicht enthalten.
