# Plan: Paper B (3DGS gegen photogrammetrische Referenz + Rundgang-Werkzeug)

Stand 13.10.2026 · Grundlage: `UEBERGABE.md`, `Heritage_Toolkit_Konzept.md`

## Rahmen

- Daten: **Pellis et al. (2025)**, Zenodo 14626611, **CC BY 4.0** (vom Nutzer auf Zenodo
  bestätigt am 13.10.2026). Nur dieser Datensatz und die in `UEBERGABE.md` Abschn. 2 genannten
  CC-BY-Alternativen.
- GPU: RunPod (Nutzer-Entscheidung 13.10.2026), Colab/Kaggle Free als Alternative. Nur FOSS.
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

Inhalt der RAR-Archive unbekannt → Schritt 0b. Start mit `5_CB.rar` (kleinstes).

## Schritte

| # | Schritt | Ergebnis | Wer |
|---|---|---|---|
| 0 | Dateiliste (Namen und Größen) von Zenodo 14626611 ablesen | Format und Größe bekannt | Nutzer |
| 0b | `5_CB.rar` laden, md5 prüfen, Inhalt auflisten (ohne Entpacken): `scripts/pellis_inspect.sh` (RunPod) oder `scripts/pellis_inspect.ipynb` (Colab) | Ordner und Dateitypen bekannt | Nutzer startet, Agent wertet aus |
| 1 | Pellis-Eintrag in `DATA_SOURCES.md` (CC BY 4.0, ✅) | Lizenz dokumentiert | Agent |
| 2 | Formatwandler: Pellis-Kameraparameter → COLMAP-Textformat (`cameras.txt`, `images.txt`, `points3D.txt` aus Referenzwolke), Test mit kleinem Ausschnitt | `scripts/pellis_to_colmap.py` + Test | Agent |
| 3 | Trainings-Rezept `scripts/train_pellis_runpod.sh` nach Muster `train_runpod.sh` (gsplat, vorhandene Posen, ein Befehl im RunPod-Terminal) | Skript, das der Nutzer mit einem Befehl startet | Agent baut, Nutzer startet |
| 4 | Training: zunächst 1 Gebäude, danach die übrigen 4 | `.ply` je Gebäude | Nutzer (RunPod) |
| 5 | Geometrie-Prüfung: Splat-Zentren (nach `clean_splat.py`) gegen Referenzwolke, C2C-Abstände (Median, 95 %), Vollständigkeit bei Schwellen 2/5/10 cm, je Gebäude und Bauteilklasse | `scripts/eval_splat_geometry.py` + Tabelle/Abbildungen | Agent |
| 6 | Demo-Rundgang: ein Gebäude als Splat mit Medien-Markern im Browser-Studio `create.html`, als eine offline lauffähige HTML-Datei | Demo-Datei + Bildschirmfotos | Agent, Nutzer prüft am Handy |
| 7 | Journal festlegen: APC-Regel von *J. Cultural Heritage*, *DAACH*, *PFG*, *VAR* prüfen | Zieljournal | Nutzer liest die Gebühren-Seite ab, Agent wertet aus |
| 8 | Manuskript (Gliederung → Methoden/Ergebnisse → Rest) unter `Paper_ODT/Heritage_Toolkit_Paper/` | Entwurf | Agent |

## Offene Punkte

- Dateiformat der Kameraparameter und Punktwolken (hängt an Schritt 0b).
- Speicher: Gebäude einzeln laden (größtes Archiv 10,5 GB + entpackt). Beim RunPod-Pod
  Container-/Volume-Disk ≥ 50 GB wählen; Schritt 0b zeigt den freien Platz mit `df -h`.
- Splat-Zentren oder gerenderte Tiefe als Messgröße: Start mit Zentren (einfacher, keine GPU),
  Tiefe nur, falls die Zentren zu verrauscht sind.
