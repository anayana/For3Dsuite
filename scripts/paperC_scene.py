#!/usr/bin/env python3
"""paperC_scene.py -- HELIOS++-Szene mit bekannter Stammwahrheit fuer Paper C.

Erzeugt einen Plot aus Stammzylindern (ohne Kronen: untersucht wird die Brusthoehe),
dazu einen Pool von Scan-Standpunkten. Jeder Standpunkt ist ein eigenes Leg und
damit eine eigene Ausgabedatei; Scan-Konfigurationen (1, 2, 3 ... Standpunkte,
Raster/zufaellig/eng) werden spaeter OFFLINE als Teilmengen zusammengesetzt,
ohne neu zu simulieren.

Stammgeometrie: elliptischer Querschnitt (Achsverhaeltnis U(0.85, 1), zufaellig
gedreht), 32 Segmente, Ringe alle 0,25 m mit +/- 3 mm Rindenrauheit je Vertex,
Hoehe 4 m. Wahrer BHD = Ellipsenumfang/pi bei 1,3 m (Massband-Definition).
Optional Unterwuchs als duenne Zylinder (2-6 cm, 0,5-2,5 m hoch).

  python scripts/paperC_scene.py data/paperC/S1b --dens 800 --seed 2

Ausgabe: scene.xml, survey.xml, stems.obj-Teile unter parts/, truth.csv, pool.csv.
"""
import argparse
import csv
import math
from pathlib import Path

import numpy as np

SEG, RING_DZ, STEM_H = 32, 0.25, 4.0


def ellipse_perimeter(a, b):
    h = ((a - b) / (a + b)) ** 2
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


def stem_obj(rng, a, b, rot, height=STEM_H, bark=0.003, seg=SEG):
    """Elliptischer Mantel mit Rindenrauheit, Basis bei z=0, Ursprung im Zentrum."""
    rings = int(round(height / RING_DZ)) + 1
    v, f = [], []
    th = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    for j in range(rings):
        z = j * RING_DZ
        ang = th - rot
        rad = a * b / np.sqrt((b * np.cos(ang)) ** 2 + (a * np.sin(ang)) ** 2)
        rad = rad + rng.uniform(-bark, bark, seg)
        v += [(float(r * math.cos(t)), float(r * math.sin(t)), z) for r, t in zip(rad, th)]
    for j in range(rings - 1):
        for i in range(seg):
            a0, a1 = j * seg + i, j * seg + (i + 1) % seg
            b0, b1 = a0 + seg, a1 + seg
            f += [(a0, a1, b1), (a0, b1, b0)]
    lines = [f"v {x:.4f} {y:.4f} {z:.3f}" for x, y, z in v] + [f"f {p+1} {q+1} {r+1}" for p, q, r in f]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--dens", type=float, default=600, help="Stammzahl je ha")
    ap.add_argument("--dbh", type=float, default=32); ap.add_argument("--sd", type=float, default=9)
    ap.add_argument("--pattern", default="random", choices=["random", "regular", "cluster"])
    ap.add_argument("--under", type=float, default=0, help="Unterwuchs-Stämmchen je ha")
    ap.add_argument("--L", type=float, default=40, help="Kernplot-Seite (m)")
    ap.add_argument("--B", type=float, default=10, help="Randpuffer (m)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pool-grid", type=int, default=5, help="Raster n x n im Kernplot")
    ap.add_argument("--pool-rand", type=int, default=15)
    ap.add_argument("--res", type=float, default=0.06, help="Winkelaufloesung (Grad)")
    ap.add_argument("--pulse", type=int, default=300000)
    ap.add_argument("--vmin", type=float, default=-40); ap.add_argument("--vmax", type=float, default=20)
    ap.add_argument("--scanner", default="riegl_vz400")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.outdir); (out / "parts").mkdir(parents=True, exist_ok=True)
    lo, hi = -args.B, args.L + args.B
    area_ha = (hi - lo) ** 2 / 1e4
    n = int(round(args.dens * area_ha))
    # BHD vorab ziehen, damit der Mindestabstand die Stammradien kennt
    dbhs = np.clip(rng.normal(args.dbh, args.sd, n), 7, 120)
    order = []
    pts = []
    for d in dbhs:
        rad = d / 200
        for _ in range(200):
            if args.pattern == "cluster" and pts:
                c = pts[rng.integers(len(pts))] if rng.random() < .7 else None
                p = (np.array(c[:2]) + rng.normal(0, 2.5, 2)) if c is not None else rng.uniform(lo, hi, 2)
            elif args.pattern == "regular":
                g = (hi - lo) / math.sqrt(n); k = len(pts); cols = int(math.ceil((hi - lo) / g))
                p = np.array([lo + (k % cols + .5) * g, lo + (k // cols + .5) * g]) + rng.uniform(-.25, .25, 2) * g
            else:
                p = rng.uniform(lo, hi, 2)
            if not (lo <= p[0] <= hi and lo <= p[1] <= hi):
                continue
            if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= q[2] + rad + .1 for q in pts):
                pts.append((float(p[0]), float(p[1]), rad, float(d)))
                break

    truth, parts = [], []
    for i, (x, y, rad, d) in enumerate(pts, 1):
        q = rng.uniform(.85, 1.0)
        a = rad * 2 / (1 + q); b = a * q
        rot = float(rng.uniform(0, math.pi))
        (out / "parts" / f"s{i:04d}.obj").write_text(stem_obj(rng, a, b, rot))
        core = 0 <= x <= args.L and 0 <= y <= args.L
        truth.append({"id": i, "x": round(x, 3), "y": round(y, 3), "dbh_true_cm": round(100 * ellipse_perimeter(a, b) / math.pi, 2),
                      "a_m": round(a, 4), "b_m": round(b, 4), "rot_rad": round(rot, 4), "core": int(core), "kind": "stem"})
        parts.append((i, f"parts/s{i:04d}.obj", x, y))
    nu = int(round(args.under * area_ha))
    for k in range(nu):
        x, y = rng.uniform(lo, hi, 2)
        r = rng.uniform(.01, .03)
        if any(math.hypot(x - q[0], y - q[1]) < q[2] + r for q in pts):
            continue
        i = len(parts) + 1
        (out / "parts" / f"u{i:05d}.obj").write_text(stem_obj(rng, r, r, 0.0, height=float(rng.uniform(.5, 2.5)), bark=0.0, seg=8))
        truth.append({"id": i, "x": round(float(x), 3), "y": round(float(y), 3), "dbh_true_cm": round(200 * r, 2),
                      "a_m": round(r, 4), "b_m": round(r, 4), "rot_rad": 0, "core": 0, "kind": "under"})
        parts.append((i, f"parts/u{i:05d}.obj", float(x), float(y)))

    with open(out / "truth.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(truth[0].keys())); w.writeheader(); w.writerows(truth)

    # Boden
    (out / "parts" / "ground.obj").write_text(
        f"v {lo-5} {lo-5} 0\nv {hi+5} {lo-5} 0\nv {hi+5} {hi+5} 0\nv {lo-5} {hi+5} 0\nf 1 2 3\nf 1 3 4\n")
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<document>", f'<scene id="plot" name="Paper C plot seed {args.seed}">']
    for i, fp, x, y in parts:
        xml.append(f'  <part id="{i}"><filter type="objloader"><param type="string" key="filepath" value="{fp}" /></filter>'
                   f'<filter type="translate"><param type="vec3" key="offset" value="{x:.3f};{y:.3f};0" /></filter></part>')
    xml.append('  <part id="0"><filter type="objloader"><param type="string" key="filepath" value="parts/ground.obj" /></filter></part>')
    xml += ["</scene>", "</document>"]
    (out / "scene.xml").write_text("\n".join(xml) + "\n")

    # Standpunkt-Pool: Raster im Kernplot + Zufall; nicht in einem Stamm
    pool = []
    gsp = args.L / args.pool_grid
    for i in range(args.pool_grid):
        for j in range(args.pool_grid):
            pool.append(("grid", (i + .5) * gsp, (j + .5) * gsp))
    for _ in range(args.pool_rand):
        pool.append(("rand", float(rng.uniform(0, args.L)), float(rng.uniform(0, args.L))))
    fixed = []
    for kind, x, y in pool:
        for q in pts:
            d = math.hypot(x - q[0], y - q[1])
            if d < q[2] + .4:
                f = (q[2] + .45) / max(d, 1e-6); x, y = q[0] + (x - q[0]) * f, q[1] + (y - q[1]) * f
        fixed.append((kind, x, y))
    with open(out / "pool.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["leg", "kind", "x", "y"])
        for k, (kind, x, y) in enumerate(fixed):
            w.writerow([k, kind, round(x, 3), round(y, 3)])
    legs = "\n".join(f'    <leg><platformSettings x="{x:.3f}" y="{y:.3f}" z="0" onGround="false" /><scannerSettings template="tls" /></leg>'
                     for _, x, y in fixed)
    (out / "survey.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<document>
  <scannerSettings id="tls" active="true" pulseFreq_hz="{args.pulse}"
    headRotatePerSec_deg="30" headRotateStart_deg="0" headRotateStop_deg="360"
    verticalAngleMin_deg="{args.vmin}" verticalAngleMax_deg="{args.vmax}"
    verticalResolution_deg="{args.res}" horizontalResolution_deg="{args.res}" />
  <survey name="paperC" scene="scene.xml#plot" platform="data/platforms.xml#tripod" scanner="data/scanners_tls.xml#{args.scanner}">
{legs}
  </survey>
</document>
''')
    nstem = sum(1 for t in truth if t["kind"] == "stem")
    print(f"-> {out}: {nstem} Stämme ({sum(t['core'] for t in truth)} im Kern), {len(truth) - nstem} Unterwuchs, {len(fixed)} Standpunkte")


if __name__ == "__main__":
    main()
