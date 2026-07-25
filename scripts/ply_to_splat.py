#!/usr/bin/env python3
"""ply_to_splat.py -- trainiertes 3DGS-.ply -> kompaktes .splat fuer den Web-Viewer.

Ein 30k-Iterationen-3DGS liefert schnell 600 MB (Millionen Gaussians mit vollem
SH Grad 3) -- das laedt kein Browser. Dieses Skript filtert Ausreisser und
reduziert auf ein Web-Budget, dann schreibt es das schlanke .splat-Format
(antimatter15 / GaussianSplats3D): 32 Byte je Gaussian --
  Position float32[3] · Skala(linear) float32[3] · RGBA uint8[4] · Rot uint8[4].

Reduktion: Gaussians mit zu geringer Opazitaet (sig<--opac) oder zu grosser
Achse (>--max-scale m, Floater) fliegen raus; vom Rest werden die --max opaksten
behalten. 700k ergeben ~22 MB und bleiben scharf.

  python ply_to_splat.py <in.ply> <out.splat> [--max 700000] [--opac 0.15] [--max-scale 1.5]
"""
import argparse

import numpy as np

SH_C0 = 0.28209479177387814   # DC-Term der Kugelflaechenfunktionen


def read_ply_header(path):
    with open(path, "rb") as f:
        raw = b""
        while b"end_header\n" not in raw:
            chunk = f.read(1024)
            if not chunk:
                raise SystemExit("kein PLY-Header gefunden")
            raw += chunk
    hdr = raw.split(b"end_header\n")[0].decode()
    hlen = len(raw.split(b"end_header\n")[0]) + len(b"end_header\n")
    props = [l.split()[-1] for l in hdr.splitlines() if l.startswith("property float")]
    n = int(next(l for l in hdr.splitlines() if l.startswith("element vertex")).split()[-1])
    return props, n, hlen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ply"); ap.add_argument("out")
    ap.add_argument("--max", type=int, default=700_000)
    ap.add_argument("--opac", type=float, default=0.15)
    ap.add_argument("--max-scale", type=float, default=1.5)
    args = ap.parse_args()

    props, n, hlen = read_ply_header(args.ply)
    idx = {p: i for i, p in enumerate(props)}
    a = np.memmap(args.ply, np.float32, "r", offset=hlen, shape=(n, len(props)))

    sig = 1 / (1 + np.exp(-np.array(a[:, idx["opacity"]])))
    smax = np.exp(np.array(a[:, [idx["scale_0"], idx["scale_1"], idx["scale_2"]]])).max(1)
    keep = np.flatnonzero((sig > args.opac) & (smax < args.max_scale))
    if len(keep) > args.max:
        keep = keep[np.argsort(-sig[keep])[:args.max]]   # die opaksten behalten
    keep.sort()
    M = len(keep)

    def col(names):
        return np.ascontiguousarray(np.array(a[keep][:, [idx[c] for c in names]]), "<f4")

    xyz = col(["x", "y", "z"])
    scl = np.ascontiguousarray(np.exp(col(["scale_0", "scale_1", "scale_2"])), "<f4")
    fdc = col(["f_dc_0", "f_dc_1", "f_dc_2"])
    op = 1 / (1 + np.exp(-col(["opacity"]).ravel()))
    q = col(["rot_0", "rot_1", "rot_2", "rot_3"])
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    rgb = np.clip(0.5 + SH_C0 * fdc, 0, 1)

    buf = np.zeros((M, 32), np.uint8)
    buf[:, 0:12] = xyz.view(np.uint8).reshape(M, 12)
    buf[:, 12:24] = scl.view(np.uint8).reshape(M, 12)
    buf[:, 24:27] = (rgb * 255).astype(np.uint8)
    buf[:, 27] = (op * 255).astype(np.uint8)
    buf[:, 28:32] = np.clip(np.round(q * 128) + 128, 0, 255).astype(np.uint8)
    buf.tofile(args.out)

    import os
    print(f"{n:,} -> {M:,} Gaussians  ({os.path.getsize(args.out)/1e6:.1f} MB)  {args.out}")


if __name__ == "__main__":
    main()
