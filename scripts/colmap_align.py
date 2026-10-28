#!/usr/bin/env python3
"""colmap_align.py -- eigene COLMAP-Posen ins System der Punktwolke bringen und mit den
gelieferten Posen vergleichen.

Eingaben (COLMAP-Textformat):
  sfm      Ordner(n) mit cameras.txt/images.txt aus `colmap mapper` + `model_converter`;
           bei mehreren Teilmodellen wird das mit den meisten Bildern genommen
  ref      gelieferte Posen im System der Punktwolke (pellis_to_colmap.py, sparse/0)
Ablauf:  Kamerazentren beider Modelle ueber den Bildnamen (ohne Endung) paaren, robuste
         Aehnlichkeitstransformation (Umeyama, Ausreisser > 3x Median verworfen), SfM-Posen
         damit ins System der Punktwolke rechnen. Ausgabe: <out>/{cameras,images,points3D}.{txt,bin}
         mit den Initpunkten aus ref.
Diagnose: Abstand der Kamerazentren (m) und Winkel der Blickrichtungen (Grad) zwischen
         ausgerichteten SfM-Posen und gelieferten Posen -- grosse Werte heissen: die gelieferten
         Kameraparameter passen nicht zu den Fotos.

  python scripts/colmap_align.py <sfm_txt_ordner>... --ref <ref/sparse/0> --out <ziel/sparse/0>
"""
import argparse
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pellis_to_colmap as p2c  # noqa: E402


def quat_to_R(w, x, y, z):
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def read_images(path):
    """images.txt -> {stem: (R_w2c, t, name, camera_id)}; jede zweite Zeile ist die POINTS2D-Zeile."""
    out = {}
    lines = [l.rstrip("\n") for l in open(path) if not l.startswith("#")]
    for i in range(0, len(lines), 2):
        p = lines[i].split()
        if len(p) < 10:
            continue
        R = quat_to_R(*map(float, p[1:5]))
        out[os.path.splitext(p[9])[0]] = (R, np.array(list(map(float, p[5:8]))), p[9], int(p[8]))
    return out


def read_camera(path):
    for l in open(path):
        if l.startswith("#") or not l.strip():
            continue
        p = l.split()
        model, W, H, par = p[1], int(p[2]), int(p[3]), list(map(float, p[4:]))
        if model == "PINHOLE":
            fx, fy, cx, cy = par[:4]
        elif model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
            fx = fy = par[0]
            cx, cy = par[1], par[2]
        else:
            sys.exit(f"FEHLER: Kameramodell {model} nicht unterstuetzt (PINHOLE erwartet)")
        return dict(W=W, H=H, fx=fx, fy=fy, cx=cx, cy=cy)


MODEL_IDS = {"SIMPLE_PINHOLE": 0, "PINHOLE": 1, "SIMPLE_RADIAL": 2, "RADIAL": 3, "OPENCV": 4}


def read_cameras(path):
    """cameras.txt -> {id: (model, W, H, [params])}."""
    cams = {}
    for l in open(path):
        if l.startswith("#") or not l.strip():
            continue
        p = l.split()
        if p[1] not in MODEL_IDS:
            sys.exit(f"FEHLER: Kameramodell {p[1]} nicht unterstuetzt")
        cams[int(p[0])] = (p[1], int(p[2]), int(p[3]), list(map(float, p[4:])))
    return cams


def write_model(out, cams, recs, xyz, rgb):
    """COLMAP-Text- und Binaerformat; recs = [(image_id, q, t, camera_id, name)], Spuren leer."""
    with open(os.path.join(out, "cameras.txt"), "w") as fh:
        for cid, (m, W, H, par) in sorted(cams.items()):
            fh.write(f"{cid} {m} {W} {H} " + " ".join(f"{v:.6f}" for v in par) + "\n")
    with open(os.path.join(out, "cameras.bin"), "wb") as fh:
        fh.write(struct.pack("<Q", len(cams)))
        for cid, (m, W, H, par) in sorted(cams.items()):
            fh.write(struct.pack("<iiQQ", cid, MODEL_IDS[m], W, H))
            fh.write(struct.pack(f"<{len(par)}d", *par))
    with open(os.path.join(out, "images.txt"), "w") as fh:
        for i, q, t, cid, name in recs:
            fh.write(f"{i} {q[0]:.9f} {q[1]:.9f} {q[2]:.9f} {q[3]:.9f} "
                     f"{t[0]:.6f} {t[1]:.6f} {t[2]:.6f} {cid} {name}\n\n")
    with open(os.path.join(out, "images.bin"), "wb") as fh:
        fh.write(struct.pack("<Q", len(recs)))
        for i, q, t, cid, name in recs:
            fh.write(struct.pack("<I4d3dI", i, *q, *t, cid))
            fh.write(name.encode() + b"\x00")
            fh.write(struct.pack("<Q", 0))
    with open(os.path.join(out, "points3D.txt"), "w") as fh:
        for j in range(len(xyz)):
            fh.write(f"{j+1} {xyz[j,0]:.4f} {xyz[j,1]:.4f} {xyz[j,2]:.4f} "
                     f"{rgb[j,0]} {rgb[j,1]} {rgb[j,2]} 1.0\n")
    with open(os.path.join(out, "points3D.bin"), "wb") as fh:
        fh.write(struct.pack("<Q", len(xyz)))
        for j in range(len(xyz)):
            fh.write(struct.pack("<Q3d3BdQ", j + 1, *xyz[j], *rgb[j], 1.0, 0))


def umeyama(src, dst):
    """dst ~ s R src + t (Kleinste Quadrate)."""
    ms, md = src.mean(0), dst.mean(0)
    a, b = src - ms, dst - md
    U, S, Vt = np.linalg.svd(b.T @ a / len(src))
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    s = np.trace(np.diag(S) @ D) / (a ** 2).sum(1).mean()
    return s, R, md - s * R @ ms


def robust_sim3(src, dst, iters=5):
    keep = np.ones(len(src), bool)
    for _ in range(iters):
        s, R, t = umeyama(src[keep], dst[keep])
        res = np.linalg.norm(src @ (s * R).T + t - dst, axis=1)
        new = res <= max(3 * np.median(res[keep]), 1e-9)
        if (new == keep).all():
            break
        keep = new
    return s, R, t, res, keep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sfm", nargs="+", help="Textmodell-Ordner aus colmap model_converter")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    models = [(d, read_images(os.path.join(d, "images.txt"))) for d in a.sfm
              if os.path.exists(os.path.join(d, "images.txt"))]
    if not models:
        sys.exit("FEHLER: kein SfM-Modell gefunden")
    sfm_dir, sfm = max(models, key=lambda m: len(m[1]))
    ref = read_images(os.path.join(a.ref, "images.txt"))
    common = sorted(set(sfm) & set(ref))
    print(f"SfM-Modelle: {[len(m[1]) for m in models]} Bilder; genommen {sfm_dir} "
          f"({len(sfm)} Bilder, {len(common)} mit gelieferter Pose)")
    if len(common) < 5:
        sys.exit("FEHLER: zu wenige gemeinsame Bilder fuer die Ausrichtung")

    centre = lambda R, t: -R.T @ t  # noqa: E731
    src = np.array([centre(*sfm[k][:2]) for k in common])
    dst = np.array([centre(*ref[k][:2]) for k in common])
    s, Ra, ta, res, keep = robust_sim3(src, dst)
    angs = []
    for k in common:
        Rs = sfm[k][0] @ Ra.T                       # SfM-Pose im System der Punktwolke
        Rr = ref[k][0]
        angs.append(np.degrees(np.arccos(np.clip((np.trace(Rs @ Rr.T) - 1) / 2, -1, 1))))
    angs = np.array(angs)
    print(f"Ausrichtung: s={s:.4f}, {keep.sum()}/{len(common)} Zentren genutzt")
    print(f"Abweichung Kamerazentren SfM vs. geliefert: Median {np.median(res):.3f} m, "
          f"95 % {np.percentile(res, 95):.3f} m, max {res.max():.3f} m")
    print(f"Abweichung Blickrichtung: Median {np.median(angs):.2f} Grad, "
          f"95 % {np.percentile(angs, 95):.2f} Grad, max {angs.max():.2f} Grad")
    worst = np.argsort(-angs)[:8]
    print("Groesste Winkel: " + ", ".join(f"{common[i]} {angs[i]:.1f}" for i in worst))

    cams = read_cameras(os.path.join(sfm_dir, "cameras.txt"))
    rc = read_camera(os.path.join(a.ref, "cameras.txt"))
    f = np.array([par[0] for _, _, _, par in cams.values()])
    W = next(iter(cams.values()))[1]
    print(f"Kameras SfM: {len(cams)}, Brennweite (erster Wert) min {f.min():.1f} Median {np.median(f):.1f} "
          f"max {f.max():.1f} px bei Breite {W}; geliefert {rc['fx']:.1f} px bei Breite {rc['W']} "
          f"(= {rc['fx'] * W / rc['W']:.1f} px)")
    if len(cams) > 1:
        fs = sorted((cams[sfm[k][3]][3][0], k) for k in sfm)
        print("Kleinste Brennweiten: " + ", ".join(f"{k} {v:.0f}" for v, k in fs[:5]))
        print("Groesste Brennweiten: " + ", ".join(f"{k} {v:.0f}" for v, k in fs[-5:]))
        extra = [par[3] for m, _, _, par in cams.values() if m in ("SIMPLE_RADIAL", "RADIAL")]
        if extra:
            print(f"k1 SfM: min {min(extra):.4f} Median {np.median(extra):.4f} max {max(extra):.4f}")
    os.makedirs(a.out, exist_ok=True)
    recs = []
    for i, k in enumerate(sorted(sfm), 1):
        R, t, name, cid = sfm[k]
        Rn = R @ Ra.T
        Cn = s * Ra @ centre(R, t) + ta
        recs.append((i, p2c.R_to_quat(Rn), -Rn @ Cn, cid, name))
    pts = np.loadtxt(os.path.join(a.ref, "points3D.txt"), comments="#", usecols=range(1, 7), ndmin=2)
    xyz, rgb = pts[:, :3], pts[:, 3:6].astype(np.uint8)
    write_model(a.out, cams, recs, xyz, rgb)
    print(f"-> {a.out}: {len(recs)} Posen im System der Punktwolke, {len(xyz):,} Initpunkte")


if __name__ == "__main__":
    main()
