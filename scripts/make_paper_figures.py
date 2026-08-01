#!/usr/bin/env python3
"""make_paper_figures.py -- Abbildungen fuers Paper erzeugen (reproduzierbar).

SoftwareX erwartet mindestens ein Architekturschema. Die Abbildung wird hier aus
Code erzeugt statt in einem Zeichenprogramm gebaut, damit sie sich mit der
Software mitaendert und im Repository nachvollziehbar bleibt.

  fig1_architektur.svg   Zwei Eingangsklassen, eine Kette (Abschnitt 2.1/3.1)
  fig2_evaluation.svg    Ergebnis der Panorama-Evaluation (Abschnitt 3/5)

  python scripts/make_paper_figures.py --out Paper_ODT/Panorama_Pipeline_Paper/figures
"""
import argparse
from pathlib import Path

BG, FG, MUTED = "#ffffff", "#1b1f24", "#5c6570"
BLUE, GREEN, ORANGE, GREY = "#1f6feb", "#1a7f4b", "#b8590f", "#8b949e"


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(x, y, w, h, title, lines, accent=BLUE, dashed=False):
    d = ' stroke-dasharray="5 4"' if dashed else ""
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#fff" '
         f'stroke="{accent}" stroke-width="1.6"{d}/>'
         f'<text x="{x+12}" y="{y+22}" font-size="13" font-weight="600" '
         f'fill="{FG}">{esc(title)}</text>')
    for i, ln in enumerate(lines):
        s += (f'<text x="{x+12}" y="{y+42+i*16}" font-size="11.5" fill="{MUTED}">'
              f'{esc(ln)}</text>')
    return s


def arrow(x1, y1, x2, y2, label="", colour=GREY):
    s = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" '
         f'stroke-width="1.6" marker-end="url(#a)"/>')
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        s += (f'<text x="{mx}" y="{my-6}" font-size="11" fill="{MUTED}" '
              f'text-anchor="middle">{esc(label)}</text>')
    return s


def fig_architektur():
    W, H = 900, 560
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="system-ui,-apple-system,sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{BG}"/>',
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
         'markerWidth="7" markerHeight="7" orient="auto">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{GREY}"/></marker></defs>']

    p.append(f'<text x="24" y="30" font-size="15" font-weight="700" fill="{FG}">'
             'Zwei Eingangsklassen, eine Kette</text>')

    # Eingaenge
    p.append(box(24, 52, 250, 92, "Aufnahmen OHNE Pose",
                 ["Consumer-360°, DSLR + Fisheye", "Pose muss geschätzt werden"], ORANGE))
    p.append(box(24, 166, 250, 92, "Aufnahmen MIT Pose",
                 ["TLS-Scanner, E57-Container", "Pose + Kalibrierung enthalten"], GREEN))

    # Erkennung
    p.append(box(320, 100, 200, 110, "Autoerkennung",
                 ["detect_input_class()", ".e57 → Reprojektion", "1 Bild 2:1 → übernehmen",
                  "mehrere → Stitching"], BLUE))
    p.append(arrow(274, 98, 318, 130))
    p.append(arrow(274, 212, 318, 180))

    # Zweige
    p.append(box(566, 44, 280, 82, "Stitching (Hugin)",
                 ["cpfind → autooptimiser → nona → enblend",
                  "Kontrollpunkte, Bündelausgleich"], ORANGE))
    p.append(box(566, 140, 280, 82, "Reprojektion",
                 ["Weltstrahl je Ausgaberichtung in jede Kamera",
                  "keine Kontrollpunkte, nahtlos"], GREEN))
    p.append(arrow(520, 130, 562, 92))
    p.append(arrow(520, 168, 562, 178))

    # Ausgabe
    p.append(box(566, 250, 280, 66, "Equirektangulares Panorama",
                 ["+ Kacheln / Auflösungsstufen"], BLUE))
    # Der Stitching-Zweig muss AUSSEN am Reprojektions-Kasten vorbei; eine
    # senkrechte Linie von y=126 nach y=246 liefe mitten hindurch.
    p.append(f'<polyline points="866,126 884,126 884,238 760,238 760,246" '
             f'fill="none" stroke="{GREY}" stroke-width="1.6" marker-end="url(#a)"/>')
    p.append(arrow(680, 222, 680, 246))

    # Fachdaten
    p.append(box(24, 300, 500, 96, "Fachdaten aus derselben Punktwolke (nur TLS)",
                 ["Stammdetektion (3DFin) · BHD nach mehreren Verfahren · Höhe",
                  "Kronenmetriken · QSM-Zylindermodell · Wachstumsprognose (TreeGrOSS)",
                  "→ als georeferenzierte Marker in die Szene"], GREEN, dashed=True))
    p.append(arrow(150, 262, 150, 296))

    # Viewer + Hosting
    p.append(box(24, 424, 380, 104, "Begehbare Web-Szene",
                 ["Pannellum (Panorama) + three.js (Punktwolke, QSM, Marker)",
                  "Umschalter: RGB · Ground Truth · Einzelbäume",
                  "Zeithorizont-Regler für die Prognose"], BLUE))
    p.append(box(440, 424, 436, 104, "Self-Hosting (Docker Compose)",
                 ["Caddy — TLS, Routing, Basic-Auth für das Studio",
                  "Garage — S3-Objektspeicher, liefert /media direkt aus",
                  "FastAPI — Upload, Job-Queue, Szenen-Manifest"], BLUE))
    p.append(arrow(214, 400, 214, 420))
    p.append(arrow(700, 320, 700, 420))

    p.append('</svg>')
    return "\n".join(p)


def fig_evaluation():
    W, H = 900, 380
    bars = [("Stitching\n(Pose geschätzt)", 22.98, 6, 11, ORANGE),
            ("Reprojektion\n(Pose bekannt)", 26.87, 11, 11, GREEN)]
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="system-ui,-apple-system,sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{BG}"/>']
    p.append(f'<text x="24" y="30" font-size="15" font-weight="700" fill="{FG}">'
             'Panorama-Evaluation gegen 11 CC0-Referenzen</text>')
    p.append(f'<text x="24" y="50" font-size="11.5" fill="{MUTED}">'
             'Synthetische Aufnahmen mit exakt bekannter Geometrie; gemessen gegen '
             'das Originalpanorama</text>')

    # PSNR-Balken
    x0, y0, bw, maxv = 150, 90, 320, 30.0
    for i, (name, psnr, ok, tot, col) in enumerate(bars):
        y = y0 + i * 62
        w = int(bw * psnr / maxv)
        p.append(f'<rect x="{x0}" y="{y}" width="{w}" height="30" rx="4" fill="{col}"/>')
        p.append(f'<text x="{x0+w+10}" y="{y+20}" font-size="12.5" font-weight="600" '
                 f'fill="{FG}">{psnr:.2f} dB</text>')
        for j, ln in enumerate(name.split("\n")):
            p.append(f'<text x="{x0-12}" y="{y+13+j*15}" font-size="11.5" fill="{FG}" '
                     f'text-anchor="end">{esc(ln)}</text>')
        p.append(f'<text x="{x0+8}" y="{y+20}" font-size="11.5" fill="#fff">'
                 f'{ok}/{tot} brauchbar</text>')
    p.append(f'<text x="{x0}" y="{y0-8}" font-size="11" fill="{MUTED}">PSNR (höher ist besser)</text>')

    # Nahtversatz
    y1 = 240
    p.append(f'<text x="24" y="{y1}" font-size="13" font-weight="600" fill="{FG}">'
             'Nahtversatz — trennt schärfer als PSNR</text>')
    rows = [("Reprojektion", "0,10 px", GREEN),
            ("Stitching, gelungen", "0,14 px", ORANGE),
            ("Stitching, misslungen", "5,95 – 6,14 px", "#b02a2a"),
            ("real, mit Parallaxe (PASSTA)", "3,95 px", "#b02a2a")]
    for i, (lbl, val, col) in enumerate(rows):
        y = y1 + 26 + i * 24
        p.append(f'<circle cx="34" cy="{y-4}" r="5" fill="{col}"/>')
        p.append(f'<text x="50" y="{y}" font-size="12" fill="{FG}">{esc(lbl)}</text>')
        p.append(f'<text x="330" y="{y}" font-size="12" font-weight="600" '
                 f'fill="{FG}" text-anchor="end">{esc(val)}</text>')
    p.append(f'<text x="380" y="{y1+50}" font-size="11.5" fill="{MUTED}">'
             'Faktor ~40 zwischen gelungenem und misslungenem Stitch —</text>')
    p.append(f'<text x="380" y="{y1+68}" font-size="11.5" fill="{MUTED}">'
             'ohne Kenntnis der Wahrheit interpretierbar, daher als</text>')
    p.append(f'<text x="380" y="{y1+86}" font-size="11.5" fill="{MUTED}">'
             'automatischer Qualitätsflag verwendbar (&gt; 1 px).</text>')
    p.append(f'<text x="380" y="{y1+112}" font-size="11.5" fill="{MUTED}">'
             'Reale Aufnahmen liegen ~56× über dem synthetischen Fall:</text>')
    p.append(f'<text x="380" y="{y1+130}" font-size="11.5" fill="{MUTED}">'
             'die synthetischen Zahlen sind eine Untergrenze.</text>')
    p.append('</svg>')
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="Paper_ODT/Panorama_Pipeline_Paper/figures")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, svg in (("fig1_architektur.svg", fig_architektur()),
                      ("fig2_evaluation.svg", fig_evaluation())):
        (out / name).write_text(svg, encoding="utf-8")
        print(f"  {name} ({len(svg)/1000:.1f} kB)")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
