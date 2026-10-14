#!/usr/bin/env python3
"""gsplat_export_metric.py -- gsplat-Checkpoint -> INRIA-.ply im METRISCHEN Aufnahmerahmen.

gsplat normalisiert beim Training die Welt (Parser normalize=True: Verschiebung,
Drehung, Skalierung T). Ein direkt exportierter Splat liegt deshalb NICHT mehr
in Metern und passt nicht auf die LiDAR-Messwolke. Dieses Skript rechnet T
heraus: Positionen, Gauss-Groessen und -Drehungen und die Kugelflaechen-
funktionen (Blickabhaengigkeit, SH-Grad 1-3) werden zurueckgedreht. Ergebnis:
Splat und lidar_points.ply liegen deckungsgleich, 1 Einheit = 1 m.

  python scripts/gsplat_export_metric.py <ckpt.pt|ergebnisordner> <datensatz> <out.ply> \
      --examples gsplat/examples [--factor 1]
  # ohne gsplat-Quellen: --transform T.json (4x4, Welt -> normalisiert)
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np

# Reelle Kugelflaechenfunktionen wie in 3DGS/gsplat (Grad 0..3)
C0 = 0.28209479177387814
C1 = 0.4886025119029199
C2 = [1.0925484305920792, -1.0925484305920792, 0.31539156525252005,
      -1.0925484305920792, 0.5462742152960396]
C3 = [-0.5900435899266435, 2.890611442640554, -0.4570457994644658, 0.3731763325901154,
      -0.4570457994644658, 1.445305721320277, -0.5900435899266435]


def sh_basis(d, degree=3):
    """(N,3) Einheitsrichtungen -> (N,(degree+1)^2) SH-Basis."""
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    out = [np.full_like(x, C0)]
    if degree >= 1:
        out += [-C1 * y, C1 * z, -C1 * x]
    if degree >= 2:
        xx, yy, zz = x * x, y * y, z * z
        out += [C2[0] * x * y, C2[1] * y * z, C2[2] * (2 * zz - xx - yy),
                C2[3] * x * z, C2[4] * (xx - yy)]
    if degree >= 3:
        out += [C3[0] * y * (3 * xx - yy), C3[1] * x * y * z, C3[2] * y * (4 * zz - xx - yy),
                C3[3] * z * (2 * zz - 3 * xx - 3 * yy), C3[4] * x * (4 * zz - xx - yy),
                C3[5] * z * (xx - yy), C3[6] * x * (xx - 3 * yy)]
    return np.stack(out, 1)


def sh_rotation(R, degree):
    """Matrix M ((K-1)x(K-1), ohne DC) mit  sum_k c'_k Y_k(d) = sum_k c_k Y_k(R d).

    Numerisch je Band per kleinsten Quadraten: Rotationen bilden jedes SH-Band
    auf sich selbst ab, die Loesung ist daher exakt (bis auf Rundung).
    """
    K = (degree + 1) ** 2
    rng = np.random.default_rng(0)
    d = rng.standard_normal((256, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    A, B = sh_basis(d, degree), sh_basis(d @ R.T, degree)
    M = np.zeros((K - 1, K - 1))
    for l in range(1, degree + 1):
        sl = slice(l * l, (l + 1) ** 2)
        M[l * l - 1:(l + 1) ** 2 - 1, l * l - 1:(l + 1) ** 2 - 1] = \
            np.linalg.lstsq(A[:, sl], B[:, sl], rcond=None)[0]
    return M


def quat_mul(a, b):
    """Hamilton-Produkt, (w, x, y, z), elementweise ueber Zeilen."""
    aw, ax, ay, az = np.moveaxis(a, -1, 0)
    bw, bx, by, bz = np.moveaxis(b, -1, 0)
    return np.stack([aw * bw - ax * bx - ay * by - az * bz,
                     aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw], -1)


def quat_from_R(R):
    """Rotationsmatrix -> (w, x, y, z); Eigenvektor-Verfahren, auch bei 180 Grad stabil."""
    K = np.array([
        [R[0, 0] - R[1, 1] - R[2, 2], 0, 0, 0],
        [R[1, 0] + R[0, 1], R[1, 1] - R[0, 0] - R[2, 2], 0, 0],
        [R[2, 0] + R[0, 2], R[2, 1] + R[1, 2], R[2, 2] - R[0, 0] - R[1, 1], 0],
        [R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1],
         R[0, 0] + R[1, 1] + R[2, 2]]]) / 3.0
    w, V = np.linalg.eigh(K)
    q = V[[3, 0, 1, 2], np.argmax(w)]
    return -q if q[0] < 0 else q


def quat_to_R(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def to_metric(means, log_scales, quats, shN, T):
    """Gaussians aus dem normalisierten gsplat-Raum zurueck in den Weltrahmen.

    T (4x4) bildet Welt -> normalisiert ab: x_n = s R x + t.
    shN: (N, K-1, 3) Koeffizienten ohne DC (gsplat-Layout).
    """
    A = np.asarray(T[:3, :3], float)
    s = np.cbrt(np.linalg.det(A))
    R, t = A / s, np.asarray(T[:3, 3], float)
    means_w = (means - t) @ R / s                     # = R^T (x_n - t) / s
    scales_w = log_scales - np.log(s)
    q = quats / np.linalg.norm(quats, axis=1, keepdims=True)
    quats_w = quat_mul(np.broadcast_to(quat_from_R(R.T), q.shape), q)
    shN_w = shN
    if shN is not None and shN.shape[1] > 0:
        degree = int(round(np.sqrt(shN.shape[1] + 1))) - 1
        M = sh_rotation(R, degree)                   # Blick d_n = R d_w
        shN_w = np.einsum("ij,njc->nic", M, shN)
    return means_w.astype(np.float32), scales_w.astype(np.float32), \
        quats_w.astype(np.float32), (None if shN_w is None else shN_w.astype(np.float32))


def write_ply(path, means, log_scales, quats, opacities, sh0, shN):
    """INRIA-3DGS-.ply (wie die uebrigen For3Dsuite-Exporte)."""
    N = len(means)
    frest = np.zeros((N, 0), np.float32) if shN is None else \
        shN.transpose(0, 2, 1).reshape(N, -1)        # alle R-, dann G-, dann B-Koeffizienten
    cols = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2"] \
        + [f"f_rest_{i}" for i in range(frest.shape[1])] + ["opacity"] \
        + ["scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    data = np.concatenate([means, np.zeros((N, 3), np.float32), sh0.reshape(N, 3), frest,
                           opacities.reshape(N, 1), log_scales, quats], 1).astype("<f4")
    hdr = "ply\nformat binary_little_endian 1.0\n" + f"element vertex {N}\n" \
        + "".join(f"property float {c}\n" for c in cols) + "end_header\n"
    with open(path, "wb") as f:
        f.write(hdr.encode())
        f.write(np.ascontiguousarray(data).tobytes())


def newest_ckpt(path):
    if os.path.isfile(path):
        return path
    ck = glob.glob(os.path.join(path, "**", "ckpt_*.pt"), recursive=True)
    if not ck:
        sys.exit(f"kein gsplat-Checkpoint unter {path}")
    # numerisch nach Schritt -- lexikografisch waere ckpt_6999 > ckpt_29999
    return max(ck, key=lambda p: int(re.search(r"ckpt_(\d+)", os.path.basename(p)).group(1)))


def parser_transform(examples, data_dir, factor, test_every):
    """Exakt dieselbe Normalisierung wie beim Training (gsplat-Parser)."""
    sys.path.insert(0, os.path.abspath(examples))
    from datasets.colmap import Parser               # noqa: E402
    p = Parser(data_dir=data_dir, factor=factor, normalize=True, test_every=test_every)
    return np.asarray(p.transform, float)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ckpt", help="ckpt_*.pt oder gsplat-Ergebnisordner (neuester Checkpoint)")
    ap.add_argument("data_dir", help="Datensatz (wie beim Training)")
    ap.add_argument("out")
    ap.add_argument("--examples", help="gsplat/examples (fuer den Parser)")
    ap.add_argument("--factor", type=int, default=1)
    ap.add_argument("--test-every", type=int, default=8)
    ap.add_argument("--transform", help="JSON mit 4x4 Welt->normalisiert (statt Parser)")
    args = ap.parse_args()

    if args.transform:
        T = np.array(json.load(open(args.transform)), float)
    elif args.examples:
        T = parser_transform(args.examples, args.data_dir, args.factor, args.test_every)
    else:
        sys.exit("--examples (gsplat/examples) oder --transform angeben")
    s = np.cbrt(np.linalg.det(T[:3, :3]))
    print(f"Normalisierung herausrechnen: Massstab {s:.5f}")

    import torch
    path = newest_ckpt(args.ckpt)
    st = torch.load(path, map_location="cpu")
    sp = st.get("splats", st)
    g = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in sp.items()}
    N = len(g["means"])
    means, scales, quats, shN = to_metric(g["means"], g["scales"], g["quats"],
                                          g.get("shN"), T)
    write_ply(args.out, means, scales, quats, g["opacities"], g["sh0"], shN)
    lo, hi = np.percentile(means, 1, 0), np.percentile(means, 99, 0)
    print(f"-> {args.out}: {N:,} Gaussians aus {os.path.basename(path)}, "
          f"Ausdehnung (1-99 %) {np.round(hi - lo, 2).tolist()} m")


if __name__ == "__main__":
    main()
