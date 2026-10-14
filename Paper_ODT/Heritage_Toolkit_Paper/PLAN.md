# Plan: Paper B (3DGS gegen photogrammetrische Referenz + Rundgang-Werkzeug)

Stand 13.10.2026 · Grundlage: `UEBERGABE.md`, `Heritage_Toolkit_Konzept.md`

## Rahmen

- Daten: **Pellis et al. (2025)**, Zenodo 14626611, **CC BY 4.0** (vom Nutzer auf Zenodo
  bestätigt am 13.10.2026). Nur dieser Datensatz und die in `UEBERGABE.md` Abschn. 2 genannten
  CC-BY-Alternativen.
- GPU nur RunPod. **Kein Google** (kein Colab, kein Kaggle) — Nutzer-Entscheidung 13.10.2026. Nur FOSS.
- Kein Oral-History-Teil (keine eigene Erhebung).
- `platform/dev/export_static.py` nur mit `--html-only`.

## Dateien (Zenodo 14626611, 31,3 GB, vom Nutzer abgelesen)

| Datei | Größe | md5 |
|---|---|---|
| `1_SC.rar` | 7,2 GB | a41d08054beb7b1675fbadaa2abafd9f |
| `2_OSA.rar` | 7,3 GB | 6d8eb0a68339d17935c0039dca961f25 |
| `3_SS.rar` | 4,2 GB | 42d55c23c4c5ec148b8b045826b0fb14 |
| `4_CG.rar` | 10,5 GB | 0a0c3576e1a233651dff36e92873ad04 |
| `5_CB.rar` | 2,1 GB | 1814a907a649ef500ee90e19679615d1 |

Inhalt `5_CB.rar` (vom Nutzer entpackt, 14.10.2026): Bilder, Punktwolke, `1_interior_parameters.txt`
(MATLAB: K, ks=[k1 k2 k3], ps=[p1 p2]; 3872×2592, f = 3054,46 px) und `2_exterior_parameters.txt`
(CSV, 166 Fotos: X,Y,K = Zentrum, OMEGA/PHI/KAPPA in Grad, R = (Rx·Ry·Rz)ᵀ, Spalte Orientation 0/1).

## Schritte

| # | Schritt | Ergebnis | Wer |
|---|---|---|---|
| 0 | Dateiliste (Namen und Größen) von Zenodo 14626611 ablesen | Format und Größe bekannt | Nutzer |
| 0b | `5_CB.rar` per Handy laden und entpacken, Parameterdateien hochladen | Format bekannt | ✅ 14.10.2026 |
| 1 | Pellis-Eintrag in `DATA_SOURCES.md` (CC BY 4.0, ✅) | Lizenz dokumentiert | ✅ |
| 2 | Formatwandler: Pellis-Kameraparameter → COLMAP (PINHOLE, Fotos mit OpenCV entzerrt) | `scripts/pellis_to_colmap.py` + `tests/test_pellis_to_colmap.py` | ✅ Posen; offen: Projektionsprobe gegen Punktwolke, Init-Wolke, Bedeutung `Orientation` |
| 3 | Trainings-Rezept `scripts/train_pellis_runpod.sh` nach Muster `train_runpod.sh` (gsplat, vorhandene Posen, ein Befehl im RunPod-Terminal) | Skript, das der Nutzer mit einem Befehl startet | Agent baut, Nutzer startet |
| 4 | Training: zunächst 1 Gebäude, danach die übrigen 4 | `.ply` je Gebäude | Nutzer (RunPod) |
| 5 | Geometrie-Prüfung: Splat-Zentren (nach `clean_splat.py`) gegen Referenzwolke, C2C-Abstände (Median, 95 %), Vollständigkeit bei Schwellen 2/5/10 cm, je Gebäude und Bauteilklasse | `scripts/eval_splat_geometry.py` + Tabelle/Abbildungen | Agent |
| 6 | Demo-Rundgang: ein Gebäude als Splat mit Medien-Markern im Browser-Studio `create.html`, als eine offline lauffähige HTML-Datei | Demo-Datei + Bildschirmfotos | Agent, Nutzer prüft am Handy |
| 7 | Journal: **1. J. Cultural Heritage**, 2. *PFG* — beide Hybrid, Abo-Weg ohne Gebühr (geprüft 13.10.2026, s. u.) | Zieljournal | erledigt; vor Einreichung erneut prüfen |
| 8 | Manuskript (Gliederung → Methoden/Ergebnisse → Rest) unter `Paper_ODT/Heritage_Toolkit_Paper/` | Entwurf | Agent |

## Journal (geprüft 13.10.2026)

| Journal | IF (Drittseiten, nicht JCR) | bestes Q (SJR) | ohne Gebühr? |
|---|---|---|---|
| J. Cultural Heritage (Elsevier) | 3,3–3,5 | Q1 | ja, Abo-Weg; OA-APC 3580 USD (Elsevier-Seite „open-access-options") |
| PFG (Springer) | 3,3 | Q1 | ja, Abo-Weg, Wahl erst nach Annahme; OA-APC 2790 € (Springer „how-to-publish-with-us") |

## Erfahrungswerte

- Zenodo liefert auf RunPod ca. 1 MB/s je Verbindung (13.10.2026 gemessen) → 2,1 GB ≈ 35 min,
  alle 31,3 GB ≈ 9 h. Für das Training jedes Archiv nur einmal laden.
- RunPod-Preise (13.10.2026, Katalog): CPU `cpu3c` 2 vCPU 0,06 $/h; RTX 4000 Ada 0,20 $/h,
  RTX 4090 0,34 $/h (Community). Guthaben ca. 4 $. Jeden Pod sofort nach dem Lauf löschen.

## Offene Punkte

- Format der Punktwolke (Endung, Koordinatensystem gleich wie Kamerazentren?).
- Achsenkonvention (photogrammetrisch −Z → OpenCV +Z) nur aus den Daten abgeleitet; mit
  `validate_colmap.py` gegen die Punktwolke bestätigen.
- `Orientation` 0/1 (77/89 Fotos): vermutlich Quer-/Hochformat — an den Bildgrößen prüfen.
- Speicher: Gebäude einzeln laden (größtes Archiv 10,5 GB + entpackt). Beim RunPod-Pod
  Container-/Volume-Disk ≥ 50 GB wählen; Schritt 0b zeigt den freien Platz mit `df -h`.
- Splat-Zentren oder gerenderte Tiefe als Messgröße: Start mit Zentren (einfacher, keine GPU),
  Tiefe nur, falls die Zentren zu verrauscht sind.
