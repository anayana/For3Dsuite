# Plan: Paper B (3DGS gegen photogrammetrische Referenz + Rundgang-Werkzeug)

Stand 13.10.2026 · Grundlage: `UEBERGABE.md`, `Heritage_Toolkit_Konzept.md`

## Rahmen

- Daten: **Pellis et al. (2025)**, Zenodo 14626611, **CC BY 4.0** (vom Nutzer auf Zenodo
  bestätigt am 13.10.2026). Nur dieser Datensatz und die in `UEBERGABE.md` Abschn. 2 genannten
  CC-BY-Alternativen.
- **Keine Downloads über RunPod** (Nutzer-Anweisung 14.10.2026): Nutzer lädt selbst, Agent nennt die Links.
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
(CSV, 166 Fotos: X,Y,K = Zentrum, OMEGA/PHI/KAPPA in Grad, R = (Rx·Ry·Rz)ᵀ, Spalte Orientation 0/1),
`2_transformation_matrix.txt` (3×4 [sR|t], s = 1,3441: Kamerasystem → System der Punktwolke, Z oben;
Kamerahöhen danach 1,8–9,4).

## Schritte

| # | Schritt | Ergebnis | Wer |
|---|---|---|---|
| 0 | Dateiliste (Namen und Größen) von Zenodo 14626611 ablesen | Format und Größe bekannt | Nutzer |
| 0b | `5_CB.rar` per Handy laden und entpacken, Parameterdateien hochladen | Format bekannt | ✅ 14.10.2026 |
| 1 | Pellis-Eintrag in `DATA_SOURCES.md` (CC BY 4.0, ✅) | Lizenz dokumentiert | ✅ |
| 2 | Formatwandler: Pellis-Kameraparameter → COLMAP (PINHOLE, Fotos mit OpenCV entzerrt) | `scripts/pellis_to_colmap.py` + `tests/test_pellis_to_colmap.py` | ✅ Posen; offen: Projektionsprobe gegen Punktwolke, Init-Wolke, Bedeutung `Orientation` |
| 3 | `scripts/train_pellis_runpod.sh`: lokales RAR (kein Download) + md5, Entpacken, `pellis_to_colmap.py` (auch .bin, weil gsplat 1.5.3 Text falsch liest), Posenprobe mit Abbruch, gsplat 1.5.3, PLY im System der Punktwolke, `eval_splat_geometry.py` | ein Befehl | ✅ gebaut, ungetestet auf GPU |
| 4 | Training: zunächst 1 Gebäude (5_CB), dann 3_SS; weitere optional | `.ply` je Gebäude | 5_CB ✅ 28.10.2026: Geometrie Median 12,0 cm, Vollst. 10 cm 0,59 (`ERGEBNISSE_5CB.md`); 3_SS offen |
| 5 | Geometrie-Prüfung: Splat-Zentren (Deckkraft ≥ 0,5, in Hülle der Referenz) gegen Referenzwolke, Abstand Median/95 %, Vollständigkeit 2/5/10 cm, je Bauteil-Label | `scripts/eval_splat_geometry.py` (+ Test) | ✅ Skript; läuft im Trainingsskript mit |
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
- Upload vom Handy in JupyterLab (14.10.2026, Mobilfunk): Bilder + Parameter kamen an, die Punktwolke
  nur ~1 MB/min → nur im WLAN, Bildschirm an, Browser im Vordergrund. Pod nicht neu starten, während
  ein Upload läuft (bricht ihn ab). Netzwerk-Volume erst ab 5 $ Guthaben möglich.
- RunPod-Preise (13.10.2026, Katalog): CPU `cpu3c` 2 vCPU 0,06 $/h; RTX 4000 Ada 0,20 $/h,
  RTX 4090 0,34 $/h (Community). Guthaben ca. 4 $. Jeden Pod sofort nach dem Lauf löschen.

## Erkenntnisse 5_CB (28.10.2026)

- **Pellis-Fotos sind bereits entzerrt** (COLMAP je Foto: k1 ≈ 0, Brennweite = geliefert). Nicht noch einmal
  entzerren: `UNDIST=0`. Die gelieferten Posen stimmen (2,3 cm / 0,12° gegenüber COLMAP).
- Test-PSNR bleibt ~14–16 dB: Aufnahme für Photogrammetrie, Testansichten schlecht abgedeckt. Fürs Paper
  Geometrie mit allen Fotos (`TEST_EVERY=1000`), PSNR als Grenze.
- Pod-Ergebnisse vor dem Löschen lesen; Selbstlöschung nur als Notbremse (60 min).

## Offene Punkte

- Punktwolke: `2_PointCloud/1_point_cloud.txt` (0,94 GB), Spalten `X Y Z R G B label Nx Ny Nz`; Koordinaten
  liegen im Bereich der transformierten Kameras. `--cloud` zieht daraus die Initwolke.
- Achsenkonvention (photogrammetrisch −Z → OpenCV +Z) **an zwei Fotos bestätigt** (14.10.2026):
  SIFT-Zuordnungen (340 Inlier) → relative Pose aus den Bildern; über alle 166×165 Paare und beide
  Konventionen passt am besten 5_CB_001→002 mit Achsenumkehr (Abw. Rotation 0,7°, Richtung 0,7°).
  Probe gegen die Punktwolke mit `validate_colmap.py` steht noch aus.
- `Orientation` 0/1: 1 = hochkant gehaltene Aufnahme, Datei quer gespeichert (Szene seitlich); Posen
  passen dazu, keine Korrektur nötig. Ursache für PSNR 13 im Lauf 5_CB weiter offen.
- Speicher: Gebäude einzeln laden (größtes Archiv 10,5 GB + entpackt). Beim RunPod-Pod
  Container-/Volume-Disk ≥ 50 GB wählen; Schritt 0b zeigt den freien Platz mit `df -h`.
- Splat-Zentren oder gerenderte Tiefe als Messgröße: Start mit Zentren (einfacher, keine GPU),
  Tiefe nur, falls die Zentren zu verrauscht sind.
