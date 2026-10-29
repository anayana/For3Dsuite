# Datenquellen und Lizenzen

Alle Daten der Suite sind **Fremddaten**: frei verfügbare Datensätze Dritter.
Diese Tabelle ist die Grundlage für „Data availability" / „Acknowledgements" in
den Papern und für die Namensnennung in der Galerie. Der **Code** steht unter
GPL-3.0-or-later ([LICENSE](LICENSE)); die Daten behalten ihre eigenen Lizenzen.

Stand: 12.10.2026.

**Status**

| | Bedeutung |
|---|---|
| ✅ | offene Lizenz, mit Quell-URL in der `scene.json` bzw. beim Anbieter belegt |
| 🔎 | offene Lizenz laut Repo; die Quelle (Zenodo/heiDATA) war bei der Prüfung nicht abrufbar → **einmal im Browser bestätigen** |
| ⚠️ | **keine Lizenz gefunden** (Forschungs-Benchmark). Als Benchmark zitieren ist üblich, **öffentliches Weitergeben** (Hosting abgeleiteter Modelle) ist nicht gedeckt |
| ❌ | ausdrücklich eingeschränkt |

---

## 1. Szenen in der öffentlichen Galerie (`docs/`, `publish.json`)

| Szene(n) | Datensatz / Urheber | Lizenz | Quelle | Status |
|---|---|---|---|---|
| `renon-setup01`, `-setup02`, `-combined` | Renon (ICOS IT-Ren), Leica BLK360, E57; Chang, Candotti, von Ellenrieder, Tomelleri, Camurri (2025), „A multi-platform LiDAR dataset for standardized forest inventory measurement at long term ecological monitoring sites" | CC BY 4.0 | [10.5281/zenodo.17186174](https://doi.org/10.5281/zenodo.17186174) | ✅ |
| `renon-splat` | eigenes 3DGS-Training aus demselben E57 | CC BY 4.0 (abgeleitet) | wie oben | ✅ |
| `renon-helios-synth`, `renon-occlusion` | synthetischer Scan (HELIOS++) aus der Renon-Inventur | abgeleitet von Renon, CC BY 4.0 | [HELIOS++](https://github.com/3dgeo-heidelberg/helios) | ✅ |
| `segforests-vienna-spruce`, `-beech` | SegmentedForests plot_07/06 (Laino et al. 2025) | MIT | [10.5281/zenodo.17396681](https://doi.org/10.5281/zenodo.17396681) | 🔎 |
| `syssifoss-arboretum`, `-br01` | SYSSIFOSS, Einzelbäume Blatt-Holz-getrennt (RIEGL VZ-400) | CC BY 4.0 | [10.11588/DATA/UUMEDI](https://doi.org/10.11588/DATA/UUMEDI) | 🔎 |
| `hedgerow-be-alder` | Belgische Hecken und Baumreihen (RIEGL VZ-1000) | CC BY 4.0 | [zenodo.org/records/4487116](https://zenodo.org/records/4487116) | 🔎 |
| `forestvr-eifel-pano`, `-tree` | Zürcher, Zhao, Lau, Brede, Klippel (2023), WUR | CC BY 4.0 | [10.5281/zenodo.7632474](https://doi.org/10.5281/zenodo.7632474) | 🔎 |
| `hvi-ahn-hedges` | AHN (Actueel Hoogtebestand Nederland), ALS | **CC0** laut Earth-Engine-Katalog; im Repo als CC BY 4.0 geführt | [ahn.nl](https://www.ahn.nl/) | 🔎 Lizenz in der `scene.json` auf CC0 korrigieren, falls ahn.nl das bestätigt |
| `ph-mossy-forest` | Poly Haven, Greg Zaal | CC0 | [polyhaven.com/a/mossy_forest](https://polyhaven.com/a/mossy_forest) | ✅ |
| `ph-nature-reserve-forest` | Poly Haven, Dimitrios Savva, Jarod Guest | CC0 | [polyhaven.com/a/nature_reserve_forest](https://polyhaven.com/a/nature_reserve_forest) | ✅ |
| `ph-rainforest-trail` | Poly Haven, Dimitrios Savva, Jarod Guest | CC0 | [polyhaven.com/a/rainforest_trail](https://polyhaven.com/a/rainforest_trail) | ✅ |
| `ph-sunset-forest` | Poly Haven, Andreas Mischok | CC0 | [polyhaven.com/a/sunset_forest](https://polyhaven.com/a/sunset_forest) | ✅ |
| `ph-quadrangle-sunny` | Poly Haven, Savva Zakharov | CC0 | [polyhaven.com/a/quadrangle_sunny](https://polyhaven.com/a/quadrangle_sunny) | ✅ |
| `consumer360-wilder-kaiser-wald` | Ansgar Koreng, Wikimedia Commons | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Wald_am_Wilden_Kaiser,_Tirol,_360x180,_160620,_ako.jpg) | ✅ |
| `consumer360-chopfholz-wald` | Daniel Kraft, Wikimedia Commons | CC BY-SA 3.0 | [Commons](https://commons.wikimedia.org/wiki/File:Chopfholz_Adliswil_panosphere_20200616.jpg) | ✅ |
| `consumer360-battery-point` | Ckoerner, Wikimedia Commons | CC BY-SA 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Battery_Point_Beach,_Crescent_City,_California_May_2023.jpg) | ✅ |
| `a7r-rathaus-hof` | PantheraLeo1359531, Wikimedia Commons | CC BY 4.0 | [Commons](https://commons.wikimedia.org/wiki/File:Kugelpanorama_der_Ratsstuben_im_Rathaus_Hof_(Hauptraum)_20250125.jpg) | ✅ |
| `barberini-01` … `-10` | Raimond Spekking, Wikimedia Commons (Kugelpanorama 005–015) | CC BY-SA 4.0 | URLs je Szene in der `scene.json` | ✅ |
| `finnwoods-walk` | FinnWoodlands (Lagos, Lempiö, Rahtu 2023, Tampere University) | im Repo als „CC-BY" geführt; im [GitHub-Repo](https://github.com/juanb09111/FinnForest) und auf der Datensatzkarte **keine Datenlizenz** gefunden | [github.com/juanb09111/finnforest](https://github.com/juanb09111/finnforest) | ⚠️ |
| `stump-3dgs` | Mip-NeRF 360, Szene „stump" (Barron et al. 2022) | **keine Lizenz gefunden** (eine Sekundärquelle nennt Apache 2.0, nicht bestätigt) | jonbarron.info/mipnerf360 | ⚠️ trainiertes Modell öffentlich auf Hugging Face |
| `drjohnson-3dgs` | Deep Blending, Szene „drjohnson" (Hedman et al. 2018) | **keine Datenlizenz gefunden**; der Code im [Repo](https://github.com/phog/deepblending) ist Apache-2.0, das deckt die Bilder nicht ab | repo-sam.inria.fr (3DGS-Bündel `tandt_db.zip`) | ⚠️ trainiertes Modell öffentlich auf Hugging Face |
| `petra-3dgs` | CULTURE3D, „Petra – Treasury Face" (Zheng et al., ICCV 2025) | **keine Lizenz gefunden**; eigener Vermerk in `scripts/train_petra_runpod.sh`: „Nur Forschungs-/Demo-Nutzung" | [arXiv 2501.06927](https://arxiv.org/abs/2501.06927) | ❌ trainiertes Modell öffentlich auf Hugging Face |

**Bilder hinter den Dr-Johnson-Markern** (`docs/media/scenes/drjohnson-3dgs/story/`, Wikimedia Commons):
Reynolds (Johnson-Porträt), Titelseite des Dictionary (1755), Northcote zugeschr.
(Francis Barber), Reynolds (Boswell): gemeinfrei. Hodge-Statue: Foto Elliott Brown,
**CC BY 2.0**. Status ✅; die Namensnennung steht schon in der Karte.

## 2. Nur als Referenz/Benchmark genutzt (nicht öffentlich gehostet)

| Datensatz | Verwendung | Lizenz | Quelle | Status |
|---|---|---|---|---|
| PASSTA LunchRoom (Meneghetti, Danelljan, Felsberg 2015) | Paper A: realer Aufnahmesatz (72 Fotos) | CC BY 4.0 | [10.5281/zenodo.19663081](https://doi.org/10.5281/zenodo.19663081) | ✅ |
| Images&PointClouds Cultural Heritage Dataset (Pellis, Masiero, Betti, Tucci, Grussenmeyer 2025, Data in Brief 60, [10.1016/j.dib.2025.111661](https://doi.org/10.1016/j.dib.2025.111661)) | Paper B: 3DGS gegen Referenzwolke (`pellis_to_colmap.py`) | CC BY 4.0 (Zenodo-Seite, vom Nutzer bestätigt 13.10.2026) | [zenodo.org/records/14626611](https://zenodo.org/records/14626611) | ✅ |
| Wytham Woods (Calders et al.) | QSM-Benchmark (`bench_qsm_wytham.py`) | CC BY 4.0 | [10.5281/zenodo.7307956](https://doi.org/10.5281/zenodo.7307956) | 🔎 |
| TreeScope v1.0 ([arXiv 2310.02162](https://arxiv.org/abs/2310.02162)) | Detektions-/BHD-Benchmark (`validate_treescope.py`) | **keine Lizenz gefunden** ([GitHub](https://github.com/KumarRobotics/treescope)) | tnl.treescope.org | ⚠️ als Benchmark zitieren ok, nicht weitergeben |
| `hechingen-site3` | eigene Aufnahme, nur lokal | nicht freigegeben | — | bewusst zurückgehalten |

## 3. Geodienste (`geo_enrich.py`, `ndvi_pdok.py`)

| Dienst | Lizenz | Status |
|---|---|---|
| SoilGrids v2.0 (ISRIC) | CC BY 4.0 | ✅ |
| OpenStreetMap (Overpass) | ODbL 1.0 (Namensnennung, Weitergabe unter gleichen Bedingungen) | ✅ |
| Open-Elevation (SRTM) | SRTM gemeinfrei (US-Regierungswerk) | ✅ |
| PDOK Luchtfoto CIR (Beeldmateriaal Nederland, Kadaster) | CC BY 4.0, laut [data.overheid.nl](https://data.overheid.nl/dataset/78617-luchtfoto-beeldmateriaal-2026-5cm---8cm-infrarood-open-data) | ✅ |

---

## 4. Handlungsbedarf

1. **Petra, Dr Johnson, Stump: öffentliches Hosting klären.** Für ein Paper ist es
   üblich und unproblematisch, Standard-Benchmarks (Mip-NeRF 360, Deep Blending)
   zu **verwenden und zu zitieren**. Nicht gedeckt ist es, daraus trainierte
   Modelle öffentlich weiterzugeben (Hugging Face, Galerie). Optionen je Szene:
   (a) aus `publish.json` nehmen und die HF-Dateien auf privat stellen, oder
   (b) die Autoren um Erlaubnis bitten. **Petra zuerst**: der eigene Vermerk sagt
   „nur Forschungs-/Demo-Nutzung".
   **Erledigt (Galerie):** Petra, Dr Johnson, Stump und FinnWoodlands stehen jetzt
   unter `_zurueckgehalten` in `publish.json`; der nächste Notebook-Export nimmt sie
   aus `docs/`. **Noch offen:** die Hugging-Face-Dateien auf privat stellen.
2. **FinnWoodlands:** Lizenz bei den Autoren erfragen oder die Szene zurückhalten.
3. **🔎-Einträge** einmal im Browser bestätigen (die Zenodo-Seite zeigt die Lizenz
   oben rechts), etwa 10 Minuten. Dabei für Renon die **Urheber** des Zenodo-Datensatzes
   notieren; die braucht das Zitat in Paper A.
4. **AHN:** Lizenzangabe auf ahn.nl prüfen. Falls CC0, die Szene auf dem Notebook
   in `platform/dev-data/` korrigieren (nicht in `docs/data/`, siehe
   `CLAUDE_CODE_UEBERGABE.md`, Abschn. 0).
5. **CC BY-SA (Barberini, Wilder Kaiser, Chopfholz, Battery Point):** Abgeleitete
   Bilder (Farbvarianten, Kacheln) stehen ebenfalls unter BY-SA; Urheber und
   Lizenz müssen beim Betrachten sichtbar sein. Prüfen, ob die Galerie das je
   Szene anzeigt.
6. **Heritage-Paper:** braucht eine 3DGS-Kulturerbe-Szene mit klar offener Lizenz
   (statt Petra/Dr Johnson), z. B. eine CC-BY-Bildserie eines Bauwerks.

## 5. Textbaustein für Paper A (Computers & Geosciences)

> **Data availability.** All data used in this work are third-party open data.
> Terrestrial laser scans: Renon / ICOS IT-Ren (Leica BLK360, E57; CC BY 4.0,
> https://doi.org/10.5281/zenodo.17186174) and SegmentedForests (MIT,
> https://doi.org/10.5281/zenodo.17396681). Reference panoramas for the
> quantitative evaluation: eleven Poly Haven HDRIs (CC0, https://polyhaven.com).
> Real multi-image capture: PASSTA LunchRoom (CC BY 4.0,
> https://doi.org/10.5281/zenodo.19663081). Source code, container recipe and
> evaluation scripts: https://github.com/anayana/For3Dsuite (GPL-3.0-or-later),
> archived at [Zenodo DOI].

Vor dem Einsetzen: die 🔎-Angaben bestätigen und abgleichen, welche Datensätze
das Manuskript tatsächlich verwendet.
