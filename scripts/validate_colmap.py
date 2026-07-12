#!/usr/bin/env python3
"""validate_colmap.py -- COLMAP-Posen visuell pruefen (vor dem GPU-Training).

Projiziert die points3D (LiDAR-Initwolke, RGB) durch die berechneten
world->camera-Extrinsics + PINHOLE-Intrinsics in jede angeforderte Kamera und
legt das Ergebnis neben das echte Foto. Deckt sich die projizierte Wolke mit dem
Bild, sind Intrinsics + Extrinsics (und damit die Cross-Setup-Registrierung, da
alle Punkte im gemeinsamen Weltframe liegen) korrekt.

  python scripts/validate_colmap.py data/renon/colmap <bild1> [<bild2> ...] [--out cmp.png]
  z.B.  ... s001_c01.jpg s003_c03.jpg
"""
import argparse
import os

import numpy as np
from PIL import Image


def quat_to_R(q):
    w, x, y, z = q
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)],
        [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)]])


def read_cameras(path):
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        # ID MODEL W H fx fy cx cy
        return dict(W=int(p[2]), H=int(p[3]), fx=float(p[4]), fy=float(p[5]),
                    cx=float(p[6]), cy=float(p[7]))


def read_images(path):
    imgs = {}
    lines = [l for l in open(path) if not l.startswith("#")]
    for i in range(0, len(lines), 2):        # jede 2. Zeile ist die (leere) POINTS2D-Zeile
        p = lines[i].split()
        if len(p) < 10:
            continue
        q = list(map(float, p[1:5])); t = list(map(float, p[5:8])); name = p[9]
        imgs[name] = (np.array(q), np.array(t))
    return imgs


def read_points(path, max_pts=300000):
    xyz, rgb = [], []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        xyz.append([float(p[1]), float(p[2]), float(p[3])])
        rgb.append([int(p[4]), int(p[5]), int(p[6])])
    return np.array(xyz), np.array(rgb, np.uint8)


def project(cam, q, t, xyz, rgb, splat=5):
    R = quat_to_R(q)
    Xc = xyz @ R.T + t                        # world -> camera
    z = Xc[:, 2]
    front = z > 1e-3
    u = cam["fx"] * Xc[:, 0] / z + cam["cx"]
    v = cam["fy"] * Xc[:, 1] / z + cam["cy"]
    inb = front & (u >= 0) & (u < cam["W"]) & (v >= 0) & (v < cam["H"])
    ui = u[inb].astype(int); vi = v[inb].astype(int)
    zc = z[inb]; cc = rgb[inb]
    img = np.zeros((cam["H"], cam["W"], 3), np.uint8)
    zbuf = np.full((cam["H"], cam["W"]), np.inf, np.float32)
    order = np.argsort(-zc)                    # fern -> nah, nahe ueberschreiben
    ui, vi, zc, cc = ui[order], vi[order], zc[order], cc[order]
    rad = splat // 2
    for dv in range(-rad, rad + 1):           # Disk-Splat mit Z-Buffer
        for du in range(-rad, rad + 1):
            vv = np.clip(vi + dv, 0, cam["H"]-1)
            uu = np.clip(ui + du, 0, cam["W"]-1)
            closer = zc < zbuf[vv, uu]
            vv2, uu2 = vv[closer], uu[closer]
            img[vv2, uu2] = cc[closer]
            zbuf[vv2, uu2] = zc[closer]
    return img, int(inb.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("colmap")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default="data/renon/colmap/_validate.png")
    ap.add_argument("--overlay", action="store_true",
                    help="projizierte Punkte halbtransparent aufs echte Foto legen")
    args = ap.parse_args()

    sparse = os.path.join(args.colmap, "sparse", "0")
    cam = read_cameras(os.path.join(sparse, "cameras.txt"))
    imgs = read_images(os.path.join(sparse, "images.txt"))
    xyz, rgb = read_points(os.path.join(sparse, "points3D.txt"))
    print(f"Kamera PINHOLE {cam['W']}x{cam['H']} f={cam['fx']:.1f}; "
          f"{len(imgs)} Bilder; {len(xyz):,} Punkte")

    rows = []
    for name in args.images:
        if name not in imgs:
            print(f"  {name}: nicht in images.txt"); continue
        q, t = imgs[name]
        proj, n = project(cam, q, t, xyz, rgb)
        real = np.asarray(Image.open(os.path.join(args.colmap, "images", name)).convert("RGB"))
        h = 384
        def rs(a): return np.asarray(Image.fromarray(a).resize((h, h)))
        gap = np.full((h, 8, 3), 30, np.uint8)
        if args.overlay:
            mask = proj.sum(2) > 0                      # wo Punkte liegen
            blend = real.copy()
            blend[mask] = (0.35 * real[mask] + 0.65 * proj[mask]).astype(np.uint8)
            rows.append(np.concatenate([rs(real), gap, rs(blend)], 1))
        else:
            rows.append(np.concatenate([rs(real), gap, rs(proj)], 1))
        print(f"  {name}: {n:,} Punkte im Bild projiziert")

    montage = np.concatenate([r for r in rows], 0) if rows else None
    if montage is not None:
        Image.fromarray(montage).save(args.out)
        print(f"-> {args.out}  (je Zeile: links echtes Foto, rechts projizierte LiDAR-Wolke)")


if __name__ == "__main__":
    main()
