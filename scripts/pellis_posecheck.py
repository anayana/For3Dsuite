#!/usr/bin/env python3
"""pellis_posecheck.py -- welche Pose-Konvention passt zu Fotos und Punktwolke?

Testet vier Varianten: Achsenumkehr ja/nein x Transformationsmatrix vorwaerts/invertiert.
Je Variante werden die Initpunkte (points3D.txt, System der Punktwolke) in eine Auswahl
entzerrter Fotos projiziert -- mit Tiefenpuffer auf einem groben Raster, damit nur der
vorderste Punkt je Zelle zaehlt (Verdeckung durch Baeume/Mauern). Kennzahl: Korrelation
der Grauwerte Punkt vs. Foto; Gegenprobe: dasselbe mit um 25 Zellen verschobenem Foto.

Schreibt die Flags der besten Variante (z. B. "--no-flip --invert-transform") nach --out.
Exit 1, wenn die beste Variante sich nicht klar abhebt: Abstand zur Gegenprobe und zur
zweitbesten Variante je mindestens --margin (Absolutwerte sind wegen Vegetation/Verdeckung
niedrig; an synthetischen Daten liefert die richtige Variante ~0,3, die falschen ~0).

  python scripts/pellis_posecheck.py interior.txt exterior.txt transformation.txt \
      <colmap>/sparse/0/points3D.txt <colmap>/images --out /tmp/flags
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pellis_to_colmap as p2c  # noqa: E402

CELL = 8


def load_points(path):
    a = np.loadtxt(path, comments="#", usecols=range(1, 7), ndmin=2)
    return a[:, :3], a[:, 3:6] @ [0.299, 0.587, 0.114]


def score(K, W, H, R, C, xyz, gray_p, img):
    Xc = (xyz - C) @ R.T
    z = Xc[:, 2]
    ok = z > 0.3
    u = K[0, 0] * Xc[ok, 0] / z[ok] + K[0, 2]
    v = K[1, 1] * Xc[ok, 1] / z[ok] + K[1, 2]
    m = (u >= 0) & (u < W) & (v >= 0) & (v < H)
    if m.sum() < 500:
        return None, int(m.sum())
    cu = (u[m] // CELL).astype(int)
    cv_ = (v[m] // CELL).astype(int)
    zz = z[ok][m]
    gp = gray_p[ok][m]
    gw, gh = W // CELL + 1, H // CELL + 1
    cell = cv_ * gw + cu
    order = np.lexsort((zz, cell))                      # je Zelle aufsteigend nach Tiefe
    first = np.ones(len(order), bool)
    first[1:] = cell[order][1:] != cell[order][:-1]
    sel = order[first]                                  # vorderster Punkt je Zelle
    small = cv2.resize(img, (gw, gh), interpolation=cv2.INTER_AREA).astype(float)
    gi = small[cv_[sel], cu[sel]]
    c = np.corrcoef(gi, gp[sel])[0, 1]
    gs = small[cv_[sel], np.clip(cu[sel] + 25, 0, gw - 1)]
    c0 = np.corrcoef(gs, gp[sel])[0, 1]
    return (float(c), float(c0)), int(len(sel))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("interior")
    ap.add_argument("exterior")
    ap.add_argument("transform")
    ap.add_argument("points3d")
    ap.add_argument("images")
    ap.add_argument("--n", type=int, default=10, help="Anzahl Testfotos")
    ap.add_argument("--margin", type=float, default=0.1)
    ap.add_argument("--out")
    a = ap.parse_args()

    cam = p2c.parse_interior(a.interior)
    K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]])
    poses = p2c.parse_exterior(a.exterior)
    s, Rt, t = p2c.parse_transform(a.transform)
    xyz, gray_p = load_points(a.points3d)
    pick = poses[:: max(1, len(poses) // a.n)][: a.n]
    imgs = {p["name"]: cv2.imread(os.path.join(a.images, p["name"] + ".jpg"), cv2.IMREAD_GRAYSCALE)
            for p in pick}

    variants = []
    for inv in (False, True):
        si, Ri, ti = (1 / s, Rt.T, -(Rt.T @ t) / s) if inv else (s, Rt, t)
        for flip in (True, False):
            F = p2c.FLIP if flip else np.eye(3)
            cs, c0s = [], []
            for p in pick:
                img = imgs[p["name"]]
                if img is None:
                    continue
                R = F @ p["R"] @ Ri.T
                C = si * Ri @ p["C"] + ti
                r, n = score(K, cam["W"], cam["H"], R, C, xyz, gray_p, img)
                if r:
                    cs.append(r[0])
                    c0s.append(r[1])
            med = float(np.median(cs)) if cs else 0.0
            med0 = float(np.median(c0s)) if c0s else 0.0
            flags = " ".join(f for f, on in (("--invert-transform", inv), ("--no-flip", not flip)) if on)
            variants.append((med, med0, len(cs), flags))
            print(f"  Variante [{flags or 'Standard'}]: Median-Korrelation {med:.2f} "
                  f"(verschoben {med0:.2f}) aus {len(cs)} Fotos")
    variants.sort(key=lambda v: v[0], reverse=True)
    best, second = variants[0], variants[1]
    print(f"BESTE: [{best[3] or 'Standard'}] Korrelation {best[0]:.2f}, verschoben {best[1]:.2f}, "
          f"zweitbeste {second[0]:.2f}")
    if a.out:
        open(a.out, "w").write(best[3])
    ok = best[0] - best[1] >= a.margin and best[0] - second[0] >= a.margin
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
