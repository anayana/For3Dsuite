#!/usr/bin/env python3
"""ply_reduce.py -- INRIA-3DGS-.ply verkleinern: SH-Grad>0 strippen + ausduennen.

Der GaussianSplats3D-Viewer laedt .ply zuverlaessig (der Stumpf laeuft so), das
selbstgebaute .splat dagegen nicht. Deshalb aus dem trainierten Renon-.ply
(2,43 Mio Gauss, 62 Properties, 601 MB) ein schlankes .ply im GENAU gleichen
Format wie stump_walk.ply bauen: 17 float-Properties (x,y,z,nx,ny,nz,f_dc0-2,
opacity,scale0-2,rot0-3), nach Opazitaet auf --keep Gauss ausgeduennt.

  python scripts/ply_reduce.py <in.ply> <out.ply> [--keep 600000]
"""
import argparse
import struct
import sys
from pathlib import Path

import numpy as np

BASE = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
        "opacity", "scale_0", "scale_1", "scale_2",
        "rot_0", "rot_1", "rot_2", "rot_3"]


def read_header(f):
    props, n = [], 0
    assert f.readline().strip() == b"ply"
    fmt = f.readline().strip()
    assert b"binary_little_endian" in fmt, "nur binary_little_endian"
    while True:
        line = f.readline()
        s = line.strip().split()
        if s[0] == b"element" and s[1] == b"vertex":
            n = int(s[2])
        elif s[0] == b"property":
            assert s[1] == b"float", "nur float-Properties unterstuetzt"
            props.append(s[2].decode())
        elif s[0] == b"end_header":
            break
    return n, props, f.tell()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--keep", type=int, default=600000)
    args = ap.parse_args()

    with open(args.inp, "rb") as f:
        n, props, off = read_header(f)
    print(f"{n:,} Gauss, {len(props)} Properties")
    idx = {p: i for i, p in enumerate(props)}
    missing = [p for p in BASE if p not in idx]
    if missing:
        sys.exit(f"fehlende Properties: {missing}")

    data = np.memmap(args.inp, dtype="<f4", mode="r", offset=off,
                     shape=(n, len(props)))
    # nach Opazitaet (sigmoid) auswaehlen -- die solidesten Gauss behalten
    op = data[:, idx["opacity"]]
    keep = min(args.keep, n)
    sel = np.argpartition(op, n - keep)[n - keep:] if keep < n else np.arange(n)
    sel = np.sort(sel)
    cols = [idx[p] for p in BASE]
    out = np.ascontiguousarray(data[np.ix_(sel, cols)], dtype="<f4")
    print(f"behalte {keep:,} (Opazitaet-Top); Zielformat {len(BASE)} Properties")

    header = ("ply\nformat binary_little_endian 1.0\n"
              f"element vertex {keep}\n"
              + "".join(f"property float {p}\n" for p in BASE)
              + "end_header\n").encode()
    with open(args.out, "wb") as f:
        f.write(header)
        out.tofile(f)
    mb = (len(header) + out.nbytes) / 1e6
    print(f"-> {args.out}  ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
