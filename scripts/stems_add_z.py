#!/usr/bin/env python3
"""stems_add_z.py -- Stammliste um die z-Koordinate der Brusthoehe ergaenzen.

3DFin gibt Stammpositionen nur in x/y aus. markers_from_xyz.py braucht aber x,y,z,
weil die Marker im 3D-Viewer auf Brusthoehe schweben sollen. z ergibt sich aus dem
Bodenmodell der Wolke: z = Boden(x, y) + 1,3 m -- dieselbe Definition, die
inventory_from_cloud.py fuer seine eigenen Staemme benutzt.

  python scripts/stems_add_z.py <wolke.npz> <stems.csv> <out.csv>
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dbh_methods import ground_grid, ground_at, CELL_GROUND   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud")
    ap.add_argument("stems")
    ap.add_argument("out")
    ap.add_argument("--bh", type=float, default=1.3)
    args = ap.parse_args()

    d = np.load(args.cloud)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    ground = ground_grid(xyz)
    fallback = float(np.median(list(ground.values()))) if ground else float(xyz[:, 2].min())

    rows = list(csv.DictReader(open(args.stems, encoding="utf-8-sig")))
    fields = ["label", "x", "y", "z"] + [k for k in rows[0]
                                         if k not in ("label", "x", "y", "z")]
    n_fb = 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            x, y = float(r["x"]), float(r["y"])
            g = ground_at(ground, x, y)
            if g is None:
                g, n_fb = fallback, n_fb + 1
            r["z"] = round(g + args.bh, 3)
            w.writerow(r)
    print(f"-> {args.out}: {len(rows)} Staemme"
          + (f", {n_fb} ohne lokales Bodenmodell (Median genommen)" if n_fb else ""))


if __name__ == "__main__":
    main()
