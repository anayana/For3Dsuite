#!/usr/bin/env python3
"""e57_to_pointsbin.py -- RGB-Punktwolke aus E57 in ein kompaktes Web-Binaer.

Liest die Punktwolke (cartesianXYZ + colorRGB) via pye57, rezentriert auf den
Scan-/Kameraursprung (damit sie mit dem Layer-1-Panorama denselben Nullpunkt
teilt), dreht z-up (E57) nach y-up (three.js) und schreibt ein schlankes Binaer:

  Magic  'PCB1'                (4 Byte)
  count  uint32                (Anzahl Punkte N)
  pos    float32[N*3]          (x,y,z, y-up, rezentriert, Meter)
  col    uint8[N*3]            (r,g,b)

Nutzung:
  python e57_to_pointsbin.py <datei.e57> <out.bin> [--max 2000000] [--origin x,y,z]
"""
import sys, os, struct, argparse
import numpy as np
import pye57

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("e57"); ap.add_argument("out")
    ap.add_argument("--max", type=int, default=2_000_000,
                    help="max. Punktzahl (Zufalls-Downsampling); 0 = alle")
    ap.add_argument("--origin", default=None,
                    help="Rezentrierungs-Ursprung 'x,y,z' (Default: Punktwolken-Schwerpunkt-frei = Scanzentrum aus Pose, sonst Mittel)")
    args = ap.parse_args()

    e = pye57.E57(args.e57)
    d = e.read_scan(0, ignore_missing_fields=True, colors=True)
    x = d["cartesianX"]; y = d["cartesianY"]; z = d["cartesianZ"]
    r = d["colorRed"].astype(np.uint8)
    g = d["colorGreen"].astype(np.uint8)
    b = d["colorBlue"].astype(np.uint8)
    n0 = x.size
    print(f"gelesen: {n0:,} Punkte")

    # Ursprung: aus --origin, sonst der im E57 hinterlegte Scan-Translation-Vektor,
    # sonst Bounding-Box-Mitte.
    if args.origin:
        ox, oy, oz = (float(v) for v in args.origin.split(","))
    else:
        try:
            h = e.get_header(0)
            t = np.asarray(h.translation, float)
            ox, oy, oz = t[0], t[1], t[2]
        except Exception:
            ox, oy, oz = x.mean(), y.mean(), z.mean()
    print(f"Ursprung (rezentriert auf): ({ox:.3f}, {oy:.3f}, {oz:.3f})")

    if args.max and n0 > args.max:
        idx = np.random.default_rng(42).choice(n0, args.max, replace=False)
        idx.sort()
        x, y, z, r, g, b = x[idx], y[idx], z[idx], r[idx], g[idx], b[idx]
        print(f"downsampled: {x.size:,} Punkte")

    # rezentrieren + z-up (E57) -> y-up (three.js): (x,y,z) -> (x-ox, z-oz, -(y-oy))
    px = (x - ox).astype(np.float32)
    py = (z - oz).astype(np.float32)
    pz = (-(y - oy)).astype(np.float32)
    pos = np.empty((x.size, 3), np.float32)
    pos[:, 0] = px; pos[:, 1] = py; pos[:, 2] = pz
    col = np.empty((x.size, 3), np.uint8)
    col[:, 0] = r; col[:, 1] = g; col[:, 2] = b

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as fh:
        fh.write(b"PCB1")
        fh.write(struct.pack("<I", x.size))
        fh.write(pos.tobytes())
        fh.write(col.tobytes())
    mb = os.path.getsize(args.out) / 1e6
    lo = pos.min(0); hi = pos.max(0)
    print(f"-> {args.out}  {x.size:,} Punkte  {mb:.1f} MB")
    print(f"   BBox (y-up, m): x[{lo[0]:.1f},{hi[0]:.1f}] y[{lo[1]:.1f},{hi[1]:.1f}] z[{lo[2]:.1f},{hi[2]:.1f}]")

if __name__ == "__main__":
    main()
