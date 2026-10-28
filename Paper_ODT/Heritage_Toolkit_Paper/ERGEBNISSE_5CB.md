# Erster 3DGS-Lauf: Gebäude 5_CB (28.10.2026)

Pod: RunPod Community RTX A4500 (0,19 $/h), gsplat 1.5.3, 30 000 Schritte, halbe Auflösung (1936×1296),
Initwolke 300 000 Punkte aus `1_point_cloud.txt`. Training 15:21 min. Pod danach gelöscht, kein
Volume übrig. Die PLY (107 MB) wurde **nicht** gesichert (Lauf gilt als Fehlversuch, s. u.).

## Bildqualität (gsplat, Testbilder jedes 8. Foto)

| Schritt | PSNR | SSIM | LPIPS | Gaussians |
|---|---|---|---|---|
| 7 000 | 13,63 | 0,549 | 0,807 | 357 310 |
| 30 000 | 13,39 | 0,521 | 0,710 | 448 304 |

PSNR ~13 dB ist für 3DGS sehr schlecht (übliche Werte 20–30 dB) und steigt nicht mit dem Training →
**die Kameraposen passen nicht sauber zu den Fotos**.

## Geometrie (Splat-Zentren, Deckkraft ≥ 0,5, gegen 11,37 Mio. Referenzpunkte)

| Label | Splats | Median | 95 % | Vollst. 2/5/10 cm |
|---|---|---|---|---|
| alle | 299 108 | 14,9 cm | 223,8 cm | 0,02 / 0,20 / 0,58 |
| 0 | 6 309 | 7,7 cm | 64,3 cm | 0,04 / 0,34 / 0,82 |
| 1 | 29 855 | 13,1 cm | 113,5 cm | 0,08 / 0,55 / 0,96 |
| 2 | 6 011 | 9,2 cm | 44,6 cm | 0,02 / 0,23 / 0,72 |
| 3 | 28 732 | 24,8 cm | 84,8 cm | 0,01 / 0,08 / 0,32 |
| 4 | 5 328 | 12,4 cm | 50,1 cm | 0,02 / 0,22 / 0,72 |
| 5 | 70 012 | 11,1 cm | 65,1 cm | 0,03 / 0,26 / 0,73 |
| 6 | 26 578 | 12,6 cm | 116,5 cm | 0,01 / 0,12 / 0,45 |
| 7 | 26 787 | 12,2 cm | 39,7 cm | 0,02 / 0,24 / 0,73 |
| 8 | 67 337 | 14,8 cm | 456,6 cm | 0,01 / 0,17 / 0,60 |
| 9 | 5 631 | 12,4 cm | 306,7 cm | 0,03 / 0,29 / 0,72 |
| 10 | 26 528 | 57,8 cm | 508,1 cm | 0,00 / 0,01 / 0,04 |

Die Zahlen sind wegen der schlechten Posen **nicht** paperfähig. Bedeutung der Label-Nummern noch
offen (Data-in-Brief-Artikel).

## Verdacht und nächster Schritt

Posenprobe (Tiefenpuffer): Standard-Konvention 0,16 vs. Gegenprobe 0,05 — schwach. Fotos mit
`Orientation = 1` (89 von 166, z. B. 040–049, 054–056, 063–139) haben KAPPA ≈ ±90°. Verdacht: diese
Bilddateien sind gegenüber den Posen um 90° gedreht gespeichert (oder umgekehrt). Prüfung ohne GPU:
SIFT-Relativpose an zwei Fotos mit `Orientation = 1` (wie bei 001/002), einmal wie gespeichert,
einmal um ±90° gedreht. Kosten 0 $.

## Korrektur (28.10.2026)

Nutzer: 040/041 (Orientation = 1) sind wie 001/002 aufrecht quer. Die Posen dieser Fotos enthalten
aber KAPPA ±90°: am Übergang 039 → 040 (Blickwinkeländerung nur 40°) springt die Rolle um +89,6°,
049 → 050 um −98,6°, 056 → 057 um −96,4°. → Fotos mit Orientation = 1 bekommen eine Rolle von −90°
(`pellis_to_colmap.py --orientation-roll -90`, im Trainingsskript Standard). Zweiter Lauf folgt.

**Zurückgenommen (28.10.2026):** Die vom Nutzer gezeigten Fotos mit Orientation = 1 sind hochkant
gehaltene Aufnahmen, quer gespeichert (Szene liegt seitlich). Die KAPPA-±90°-Posen passen also zu den
Dateien; `--orientation-roll` bleibt 0. Die Ursache für PSNR 13 ist damit weiter offen.

## Diagnose-Lauf: nur die 77 quer aufgenommenen Fotos (28.10.2026)

Pod Tesla V100 (0,23 $/h), sonst wie Lauf 1, `ONLY_ORIENT=0`. Bei Schritt 7 000:
**PSNR 13,57 · SSIM 0,529 · LPIPS 0,754** (Lauf 1 mit allen 166 Fotos: 13,63 · 0,549 · 0,807).
Abgebrochen nach 7 000 Schritten (Lauf 1 wurde bis 30 000 nicht besser), Pod gelöscht.

→ Die hochkant aufgenommenen Fotos sind **nicht** die Ursache. Auch die quer aufgenommenen
Fotos allein trainieren schlecht. Ursache weiter offen; ausgeschlossen: Orientation-Flag,
Achsenkonvention (001/002 relativ 0,7°), Transformationsrichtung (Posenprobe).

## Diagnose-Lauf: ohne Startwolke (`INIT=random`, 7 000 Schritte, 28.10.2026)

Pod Tesla V100, 12:55–13:14 UTC. Lauf fertig; **PSNR nicht abgelesen** — der Pod wurde gelöscht,
bevor die PSNR-Zeile aus dem Log gelesen war (Fehler des Agenten; Logs eines gelöschten Pods sind
nicht mehr abrufbar). Erhalten ist nur die Geometrie: 160 902 Gaussians, Zentren weit außerhalb der
Szene verteilt, Median 41,6 cm, Vollständigkeit 10 cm 0,06 — bei Zufallsstart nach 7 000 Schritten
erwartbar und für die Ursachenfrage nicht aussagekräftig. Test damit **ohne Ergebnis**.

## Diagnose-Lauf 2: ohne Startwolke, Wiederholung (28.10.2026, 13:31–13:50 UTC)

Tesla V100, `INIT=random`, 7 000 Schritte, alle 166 Fotos: **PSNR 13,92 · SSIM 0,553 · LPIPS 0,801**
(147 487 Gaussians). Pod gelöscht.

→ Auch die Startwolke ist **nicht** die Ursache (mit Wolke 13,6 dB, ohne 13,9 dB).
Ausgeschlossen damit: Orientation-Flag, Startwolke/Transformation, Achsenkonvention.
Übrig: Fotos passen nicht zu den gelieferten Kameraparametern (Posen und/oder Brennweite/
Verzeichnung je Foto). Prüfung: eigene Posen per COLMAP aus den Fotos rechnen, damit trainieren;
liefert das deutlich höhere PSNR, sind die gelieferten Parameter die Ursache. Die COLMAP-Posen
lassen sich anschließend über die gelieferten Kamerazentren ins System der Punktwolke bringen.

## Diagnose-Lauf: eigene Posen per COLMAP (`POSES=colmap`, 28.10.2026, 16:00–17:28 UTC)

Tesla V100 (0,23 $/h, ca. 0,34 $), Skript-Stand d8ecd95. COLMAP 3.7 (CPU) auf den entzerrten Fotos in
halber Auflösung: SIFT 4096 Merkmale, alle Paare, PINHOLE mit Startwerten aus den gelieferten
Parametern, Brennweite frei, Hauptpunkt fest. Dauer: Merkmale 10 min, Zuordnung 56 min (CPU), Mapper 2 min.

- **Nur 97 von 166 Fotos** registriert (ein Modell).
- Ausrichtung auf die gelieferten Kamerazentren (`colmap_align.py`), 96/97 genutzt.
  Abweichung SfM vs. geliefert: Zentren Median **0,32 m** (95 % 0,63 m, max 1,08 m),
  Blickrichtung Median **2,0°** (95 % 4,8°, max 6,4°; größte: 017, 019, 109, 122, 059).
- Brennweite SfM **1432 / 1417 px** gegenüber geliefert 3054,5 / 2 = **1527 px** (−6 %, fx ≠ fy um 1 %).
- Training 7 000 Schritte auf den 97 Fotos: **PSNR 14,02 · SSIM 0,566 · LPIPS 0,728** (391 743 Gaussians).
- Geometrie (gegen Referenz, Posen ins System der Punktwolke ausgerichtet): Median 11,8 cm, 95 % 299,5 cm,
  Vollständigkeit 2/5/10 cm 0,01 / 0,13 / 0,47.

→ Mit **eigenen, in sich stimmigen Posen** ist die Bildqualität praktisch gleich (14,0 statt 13,6–13,9 dB).
Die gelieferten Posen sind also **nicht** die Hauptursache für PSNR ~14. Sie weichen zwar messbar ab
(0,3 m / 2°, Brennweite 6 %), das erklärt aber das schlechte Ergebnis nicht.
Ausgeschlossen damit: Orientation-Flag, Startwolke, Achsenkonvention, gelieferte Posen.
Offen: Ursache liegt in den Bildern bzw. der Szene oder im Ablauf (Entzerrung/Umwandlung der Fotos,
Testaufteilung, Belichtungsunterschiede). Nächster Schritt ohne GPU: entzerrte Fotos stichprobenartig
ansehen und Trainings- gegen Test-PSNR vergleichen.

## Diagnose-Lauf: Testbilder angesehen (`splat_diag.py`, 28.10.2026, 17:30–17:40 UTC)

RTX A4500, gelieferte Posen, 7 000 Schritte: PSNR 13,75 (Trainingsverlust am Ende 0,140 — hoch).
21 Testbilder, PSNR 9,0–16,9; **keine Löcher** (0,3 %), Helligkeit Foto/Render ähnlich.
Vorschaubilder (Foto | Render): Bauteile stehen **an der richtigen Stelle**, aber der Render ist überall
**stark verschmiert**, Fenstergitter und Bank nur als Schlieren.
→ Posen grob richtig, aber kein einziges Kameramodell passt sauber zu allen Fotos. Verdacht: die
Entzerrung. Hinweis darauf: COLMAP fand eine um 6 % kleinere Brennweite (typisch, wenn eine
falsche Verzeichnung in die Brennweite gedrückt wird) und registrierte nur 97/166 Fotos.
Test: Lauf ohne Entzerrung (`UNDIST=0`).

## Diagnose-Lauf: ohne Entzerrung (`UNDIST=0`, 28.10.2026, 18:37–19:05 UTC)

Tesla V100, gelieferte Posen, 7 000 Schritte: **PSNR 14,31 · SSIM 0,573 · LPIPS 0,718**, Verlust 0,133
(mit Entzerrung 13,75). Renders weiter verschmiert. → Entzerrung **nicht** die Ursache.
Nächster Verdacht: Brennweite je Foto verschieden (Zoom) — eine gemeinsame Kamera passt dann zu keinem
Foto richtig; passt zu COLMAP (Brennweite 6 % daneben, nur 97/166 registriert). Test: COLMAP mit eigener
Brennweite und k1 je Foto (`POSES=colmap CAMS=per UNDIST=0`), dazu Fotometadaten.

## Diagnose-Lauf: COLMAP mit Kamera je Foto (`POSES=colmap CAMS=per UNDIST=0`, 28.10.2026, 19:30–19:55 UTC)

RTX A4500, Originalfotos **ohne** Entzerrung, SIMPLE_RADIAL je Foto (Brennweite + k1 frei), SIFT 2048.
- Fotos tragen keine Metadaten (PNG ohne EXIF).
- 90/166 Fotos registriert.
- Brennweite je Foto: 1511–1568 px, Median **1526,9 px** = geliefert 1527,2 px → **kein Zoom**.
- k1 je Foto: Median **0,0000** (−0,04 … +0,04) → **die Fotos sind bereits entzerrt**. Unsere zusätzliche
  Entzerrung mit den gelieferten k1/k2/p hat sie verzerrt (daher früher Brennweite −6 % bei COLMAP).
- Abweichung zu den gelieferten Posen jetzt nur noch **2,3 cm** (Median) und **0,12°** → gelieferte
  Posen und Brennweite **stimmen**.
- 7 000 Schritte: **PSNR 15,55 · SSIM 0,633 · LPIPS 0,624**; Testbilder 10,8–20,1 dB.
  Geometrie: Label 4–7, 9 Median 3,6–6,4 cm.

→ Kameraparameter sind jetzt geklärt: **Fotos nicht entzerren** (`UNDIST=0`), gelieferte Posen nutzen.
PSNR bleibt aber niedrig. Auffällig: Helligkeit Foto/Render weicht je Testbild stark ab (z. B. 0,456 vs.
0,243) → Belichtung wechselt von Foto zu Foto. Nächster Lauf: gelieferte Posen, `UNDIST=0`,
Belichtungsausgleich beim Training (`APP=1`), 30 000 Schritte; PSNR zusätzlich belichtungsausgeglichen.
