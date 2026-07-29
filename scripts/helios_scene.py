#!/usr/bin/env python3
"""helios_scene.py -- Inventur -> HELIOS++-Szene + TLS-Survey (synthetischer Scan).

Baut aus einer Einzelbaum-Inventur (x, y, BHD, Hoehe) eine HELIOS++-Szene aus
prozeduralen Baummodellen (Stamm-Zylinder + Kronen-Ellipsoid, aus BHD/Hoehe
skaliert) und ein TLS-Survey mit verteilten Standpunkten. HELIOS++ simuliert
daraus eine Punktwolke -- die Grundlage fuer den Strang "Wuchsmodell -> synthetische
Fernerkundung" (Exposé 2g): dieselbe Inventur, heute oder TreeGrOSS-projiziert,
wird zu einem Scan mit BEKANNTER Wahrheit (jeder Baum-Parameter ist gesetzt).

  python scripts/helios_scene.py <inventur.csv> <outdir> [--scanner riegl_vz400]
      [--positions 6] [--height 1.5]

CSV-Spalten: x, y, BHD_cm, Hoehe_m (weitere werden ignoriert). Ausgabe in <outdir>:
  trees/tree_NNN.obj   prozedurale Baummodelle
  ground.obj           Bodenebene
  scene.xml            HELIOS++-Szene (Baeume an ihren Positionen + Boden)
  survey.xml           TLS-Survey (Scanner + Standpunkte)
  LAUFEN.md            Ausfuehr-Rezept (helios survey.xml ...)

Der Scanner/Platform-Verweis in survey.xml zeigt auf die mitgelieferten
HELIOS++-Definitionen (data/scanners_tls.xml, data/platforms.xml) -- diese
liegen in der HELIOS++-Installation, nicht hier.
"""
import argparse
import csv
import math
import os
from pathlib import Path

import numpy as np


def cylinder(r, h, z0=0.0, seg=10):
    """Mantel-Zylinder (ohne Deckel) als (verts, faces)."""
    v, f = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append((r * math.cos(a), r * math.sin(a), z0))
        v.append((r * math.cos(a), r * math.sin(a), z0 + h))
    for i in range(seg):
        b0, t0 = 2 * i, 2 * i + 1
        b1, t1 = 2 * ((i + 1) % seg), 2 * ((i + 1) % seg) + 1
        f.append((b0, b1, t1)); f.append((b0, t1, t0))
    return v, f


def ellipsoid(rx, rz, cz, seg_u=12, seg_v=7):
    """Kronen-Ellipsoid (rx horizontal, rz vertikal, Mitte cz)."""
    v, f = [], []
    for j in range(seg_v + 1):
        phi = math.pi * j / seg_v - math.pi / 2      # -90..90
        for i in range(seg_u):
            th = 2 * math.pi * i / seg_u
            v.append((rx * math.cos(phi) * math.cos(th),
                      rx * math.cos(phi) * math.sin(th),
                      cz + rz * math.sin(phi)))
    for j in range(seg_v):
        for i in range(seg_u):
            a = j * seg_u + i
            b = j * seg_u + (i + 1) % seg_u
            c = (j + 1) * seg_u + i
            d = (j + 1) * seg_u + (i + 1) % seg_u
            f.append((a, b, d)); f.append((a, d, c))
    return v, f


def tree_obj(dbh_cm, height_m):
    """Prozeduraler Baum: Stamm + Kronen-Ellipsoid, Basis bei z=0."""
    height = max(height_m, 1.0)
    crown_base = 0.32 * height
    trunk_r = max(dbh_cm / 200.0, 0.02)               # BHD in m -> Radius
    crown_r = min(max(height * 0.22, 0.6), 4.0)       # grobe Allometrie
    crown_h = height - crown_base
    tv, tf = cylinder(trunk_r, crown_base * 1.05)
    cv, cf = ellipsoid(crown_r, crown_h / 2.0, crown_base + crown_h / 2.0)
    verts = tv + cv
    faces = tf + [(a + len(tv), b + len(tv), c + len(tv)) for a, b, c in cf]
    lines = [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts]
    lines += [f"f {a+1} {b+1} {c+1}" for a, b, c in faces]
    return "\n".join(lines) + "\n"


def ground_obj(xmin, ymin, xmax, ymax, pad=5.0):
    v = [(xmin - pad, ymin - pad, 0), (xmax + pad, ymin - pad, 0),
         (xmax + pad, ymax + pad, 0), (xmin - pad, ymax + pad, 0)]
    lines = [f"v {x:.3f} {y:.3f} {z:.3f}" for x, y, z in v]
    lines += ["f 1 2 3", "f 1 3 4"]
    return "\n".join(lines) + "\n"


def scan_positions(xs, ys, n, height):
    """n TLS-Standpunkte moeglichst gleichmaessig ueber die Plotflaeche."""
    cx, cy = xs.mean(), ys.mean()
    rx, ry = (xs.max() - xs.min()) / 2 * 0.7, (ys.max() - ys.min()) / 2 * 0.7
    pts = [(cx, cy, height)]
    for k in range(n - 1):
        a = 2 * math.pi * k / (n - 1)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a), height))
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("outdir")
    ap.add_argument("--scanner", default="riegl_vz400")
    ap.add_argument("--positions", type=int, default=6)
    ap.add_argument("--height", type=float, default=1.5, help="Scanner-Hoehe (m)")
    ap.add_argument("--res", type=float, default=0.04, help="Winkelaufloesung (Grad)")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    out = Path(args.outdir); (out / "trees").mkdir(parents=True, exist_ok=True)
    xs = np.array([float(r["x"]) for r in rows])
    ys = np.array([float(r["y"]) for r in rows])

    # --- prozedurale Baeume + Szene ---------------------------------------
    parts = []
    for i, r in enumerate(rows, 1):
        obj = f"trees/tree_{i:03d}.obj"
        (out / obj).write_text(tree_obj(float(r["BHD_cm"]), float(r["Hoehe_m"])))
        parts.append(f'''  <part id="{i}">
    <filter type="objloader"><param type="string" key="filepath" value="{obj}" /></filter>
    <filter type="translate"><param type="vec3" key="offset" value="{float(r['x']):.3f};{float(r['y']):.3f};0" /></filter>
  </part>''')
    (out / "ground.obj").write_text(ground_obj(xs.min(), ys.min(), xs.max(), ys.max()))
    parts.append('''  <part id="ground">
    <filter type="objloader"><param type="string" key="filepath" value="ground.obj" /></filter>
  </part>''')
    scene = ('<?xml version="1.0" encoding="UTF-8"?>\n<document>\n'
             f'<scene id="renon_stand" name="Renon Bestand ({len(rows)} Baeume)">\n'
             + "\n".join(parts) + "\n</scene>\n</document>\n")
    (out / "scene.xml").write_text(scene, encoding="utf-8")

    # --- TLS-Survey -------------------------------------------------------
    pos = scan_positions(xs, ys, args.positions, args.height)
    legs = "\n".join(
        f'    <leg><platformSettings x="{x:.2f}" y="{y:.2f}" z="{z:.2f}" '
        f'onGround="false" /><scannerSettings template="tls" /></leg>'
        for x, y, z in pos)
    survey = f'''<?xml version="1.0" encoding="UTF-8"?>
<document>
  <scannerSettings id="tls" active="true" pulseFreq_hz="300000"
    scanAngle_deg="180" headRotatePerSec_deg="30"
    headRotateStart_deg="0" headRotateStop_deg="360"
    verticalResolution_deg="{args.res}" horizontalResolution_deg="{args.res}" />
  <survey name="renon_tls_synth" scene="scene.xml#renon_stand"
    platform="data/platforms.xml#tripod"
    scanner="data/scanners_tls.xml#{args.scanner}">
{legs}
  </survey>
</document>
'''
    (out / "survey.xml").write_text(survey, encoding="utf-8")

    (out / "LAUFEN.md").write_text(f'''# Synthetischen Scan rechnen (HELIOS++)

Voraussetzung: HELIOS++ installiert (`conda install -c conda-forge helios`).
Die `survey.xml` verweist auf die HELIOS++-eigenen Scanner-/Plattform-Definitionen
(`data/scanners_tls.xml#{args.scanner}`, `data/platforms.xml#tripod`) -- daher aus
dem HELIOS++-Wurzelverzeichnis heraus laufen lassen oder `--assets` setzen.

```bash
helios {out.name}/survey.xml --output {out.name}/output
```

Ergebnis: eine synthetische Punktwolke unter `{out.name}/output/.../points/`.
Danach in die Suite holen:

```bash
python scripts/helios_import.py {out.name}/output <szenen-id>
```
''', encoding="utf-8")

    print(f"-> {out}: {len(rows)} Baeume, {len(pos)} Scan-Standpunkte, "
          f"Scanner {args.scanner}")
    print(f"   scene.xml, survey.xml, trees/, ground.obj, LAUFEN.md")


if __name__ == "__main__":
    main()
