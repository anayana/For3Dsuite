# Übergabe: Hecken-Paper (Paper D) — Hedge Vertical Index aus offenem ALS

Stand 07.11.2026 · Repo `anayana/For3Dsuite` · Autor: Angel Naya, Independent Researcher, Berlin

## 0. Regeln

**Zuerst `CLAUDE.md` im Repo-Wurzelverzeichnis lesen — gilt verbindlich** (Kommunikation, Kosten,
RunPod-Regeln, nur offene Daten, `export_static.py` nur mit `--html-only`, keine GitHub-Links im
Paper). Vorbild für Ablauf und Format: Paper B (`Paper_ODT/Heritage_Toolkit_Paper/`) und Paper C
(`Paper_ODT/Forst_Benchmark_Paper/`).

## 1. Blocker zuerst: `shrub_div` fehlt

Der HVI (`hvi_metrics.R`, `hvi_index.R`, `hvi_rescale()`, `hvi_species_suitability()`,
`species_requirements.csv`) liegt im Nachbarrepo **`shrub_div`**, nur lokal beim Nutzer
(`C:/Users/A/Desktop/R/shrub_div`), **nicht auf GitHub**. Ohne den Code kein Paper und keine
Reproduzierbarkeit.
→ Erster Schritt: Nutzer legt `shrub_div` als öffentliches GitHub-Repo an (Lizenz GPL-3.0-or-later
wie For3Dsuite) oder lädt die R-Dateien hoch. Dafür eine kurze Klick-Anleitung geben.

## 2. Was schon da ist (For3Dsuite)

| Baustein | Datei |
|---|---|
| HVI auf AHN-Kachel, Segmentierung (Schmalheitstest + 20-m-Raster), Szene | `platform/dev/hvi_ahn_scene.R`, `platform/dev/seed_hvi_ahn.py` |
| Pseudo-NDVI aus PDOK-CIR-Luftbild | `scripts/ndvi_pdok.py` |
| Befunde, Grenzen, Arteignung streng/tolerant (Liebig vs. arithmetisch) | `platform/README.md`, Abschnitt „Hedge Vertical Index aus offenem ALS" |
| Belgische Hecken-TLS mit Baumzugehörigkeit | `platform/dev/seed_hedgerow.py`, Szene `hedgerow-be-alder` |
| Galerie-Szene (173 Segmente nach Gebäudefilter) | `docs/data/scene-hvi-ahn-hedges.json` |

Rohdaten liegen nicht im Repo (`data/hvi_ahn/` in `.gitignore`); Kachel AHN `C_28FN2.LAZ`,
Ausschnitt RD New 255000–256000 / 494500–495500.

## 3. Bekannte Schwächen (müssen ins Paper oder gelöst werden)

- Segmente aus der Vegetationsmaske → `cover_frac` konstant 1,00; Subindex Volumen/Größe ≈ Höhe.
- HVI ist **relativ** (2.–98.-Perzentil des Ausschnitts) → zwischen Gebieten nicht vergleichbar.
- Antwortkurven der Arteignung **unkalibriert**.
- **Keine Validierung** gegen Referenz bisher.

## 4. Vorschlag Forschungsfrage (zu prüfen und zu schärfen)

Wie gut geben Strukturkennwerte aus offenem landesweitem ALS die Heckenstruktur wieder (Referenz:
TLS), und wie empfindlich reagiert ein zusammengesetzter Index auf Segmentierung, Normierung und
Aggregation (Liebig vs. arithmetisch)?
- Referenz: belgische Hecken-TLS (Zenodo 4487116, CC BY 4.0) gegen offenes flämisches ALS am
  selben Ort (Lizenz und Verfügbarkeit prüfen) — gleiche Kennwerte aus beiden.
- Sensitivität: Rastergröße (10/20/40 m), Normierung (lokal vs. fest), Aggregation.
- Anwendung: AHN-Ausschnitt (NL) als Fallbeispiel; Pseudo-NDVI als Zusatz.
Rechnen: CPU (R/lidR). Keine GPU.

## 5. Journals (ohne Gebühr, Abo-Weg) — APC-Regel vor Einreichung prüfen

Kandidaten: *Landscape Ecology* (Springer, Hybrid), *Agriculture, Ecosystems & Environment*
(Elsevier, Hybrid), *Landscape and Urban Planning* (Elsevier, Hybrid). **Nicht:** *Ecological
Indicators* (inzwischen reines Gold-OA mit Gebühr), MDPI.

## 6. Erster Schritt für die neue Sitzung

`CLAUDE.md`, diese Datei und den HVI-Abschnitt in `platform/README.md` lesen → Nutzer anleiten,
`shrub_div` auf GitHub zu bringen → danach `Paper_ODT/Hecken_Paper/PLAN.md` (Forschungsfrage,
Daten mit geprüfter Lizenz, Versuchsaufbau, Zieljournal) anlegen und kurz vorlegen.
