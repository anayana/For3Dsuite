# Plan: Paper B (3DGS gegen photogrammetrische Referenz + Rundgang-Werkzeug)

Stand 13.10.2026 · Grundlage: `UEBERGABE.md`, `Heritage_Toolkit_Konzept.md`

## Rahmen

- Daten: **Pellis et al. (2025)**, Zenodo 14626611, **CC BY 4.0** (vom Nutzer auf Zenodo
  bestätigt am 13.10.2026). Nur dieser Datensatz und die in `UEBERGABE.md` Abschn. 2 genannten
  CC-BY-Alternativen.
- GPU nur Colab Free oder Kaggle Free. Keine Kosten, nur FOSS.
- Kein Oral-History-Teil (keine eigene Erhebung).
- `platform/dev/export_static.py` nur mit `--html-only`.

## Schritte

| # | Schritt | Ergebnis | Wer |
|---|---|---|---|
| 0 | Dateiliste (Namen und Größen) von Zenodo 14626611 ablesen | Format und Größe bekannt | Nutzer |
| 1 | Pellis-Eintrag in `DATA_SOURCES.md` (CC BY 4.0, ✅) | Lizenz dokumentiert | Agent |
| 2 | Formatwandler: Pellis-Kameraparameter → COLMAP-Textformat (`cameras.txt`, `images.txt`, `points3D.txt` aus Referenzwolke), Test mit kleinem Ausschnitt | `scripts/pellis_to_colmap.py` + Test | Agent |
| 3 | Trainings-Rezept: `scripts/train_colab.ipynb` / `train_kaggle.ipynb` um Pellis-Variante ergänzen (gsplat, vorhandene Posen, Bildgröße an Free-GPU angepasst) | Notebook, das der Nutzer per Klick startet | Agent baut, Nutzer startet |
| 4 | Training: zunächst 1 Gebäude, danach die übrigen 4 | `.ply` je Gebäude | Nutzer (Colab/Kaggle) |
| 5 | Geometrie-Prüfung: Splat-Zentren (nach `clean_splat.py`) gegen Referenzwolke, C2C-Abstände (Median, 95 %), Vollständigkeit bei Schwellen 2/5/10 cm, je Gebäude und Bauteilklasse | `scripts/eval_splat_geometry.py` + Tabelle/Abbildungen | Agent |
| 6 | Demo-Rundgang: ein Gebäude als Splat mit Medien-Markern im Browser-Studio `create.html`, als eine offline lauffähige HTML-Datei | Demo-Datei + Bildschirmfotos | Agent, Nutzer prüft am Handy |
| 7 | Journal festlegen: APC-Regel von *J. Cultural Heritage*, *DAACH*, *PFG*, *VAR* prüfen | Zieljournal | Nutzer liest die Gebühren-Seite ab, Agent wertet aus |
| 8 | Manuskript (Gliederung → Methoden/Ergebnisse → Rest) unter `Paper_ODT/Heritage_Toolkit_Paper/` | Entwurf | Agent |

## Offene Punkte

- Dateiformat der Kameraparameter und Punktwolken (hängt an Schritt 0).
- Passt der Datensatz in Colab-/Kaggle-Speicher? (hängt an Schritt 0; sonst Gebäude einzeln laden)
- Splat-Zentren oder gerenderte Tiefe als Messgröße: Start mit Zentren (einfacher, keine GPU),
  Tiefe nur, falls die Zentren zu verrauscht sind.
