#!/usr/bin/env python3
"""pcd_io.py -- minimaler PCD-Leser (numpy) fuer XYZ(-RGB)-Punktwolken.

Deckt die in der Praxis haeufigen PCL-Varianten ab: DATA ascii / binary
(nicht binary_compressed). Liest die in FIELDS deklarierten Kanaele und gibt
x, y, z als float32 zurueck, plus optional rgb (uint8 Nx3), falls ein
rgb/rgba-Feld vorhanden ist (PCL-Packung: float/uint32 -> 0xRRGGBB).

Genutzt u. a. fuer den TreeScope-Datensatz (FIELDS x y z, DATA binary).
"""
import numpy as np

_NP = {("F", 4): np.float32, ("F", 8): np.float64,
       ("U", 1): np.uint8, ("U", 2): np.uint16, ("U", 4): np.uint32,
       ("I", 1): np.int8, ("I", 2): np.int16, ("I", 4): np.int32}


def read_pcd(path):
    """Liest eine PCD-Datei. Rueckgabe: (x, y, z, rgb|None) als numpy-Arrays."""
    with open(path, "rb") as f:
        fields, sizes, types, counts = [], [], [], []
        npoints = None
        data_fmt = None
        while True:
            line = f.readline()
            if not line:
                raise ValueError("PCD-Header unvollstaendig")
            txt = line.decode("ascii", "replace").strip()
            if not txt or txt.startswith("#"):
                continue
            key, _, val = txt.partition(" ")
            key = key.upper()
            if key == "FIELDS":
                fields = val.split()
            elif key == "SIZE":
                sizes = [int(v) for v in val.split()]
            elif key == "TYPE":
                types = val.split()
            elif key == "COUNT":
                counts = [int(v) for v in val.split()]
            elif key == "POINTS":
                npoints = int(val)
            elif key == "WIDTH" and npoints is None:
                npoints = int(val)
            elif key == "HEIGHT" and npoints is not None:
                pass
            elif key == "DATA":
                data_fmt = val.split()[0].lower()
                break
        if not counts:
            counts = [1] * len(fields)
        if npoints is None:
            raise ValueError("PCD ohne POINTS/WIDTH")

        # Struktur je Punkt (Feld ggf. mehrfach via COUNT)
        names, formats = [], []
        for fld, sz, tp, cnt in zip(fields, sizes, types, counts):
            dt = _NP.get((tp.upper(), sz))
            if dt is None:
                raise ValueError(f"PCD-Feldtyp nicht unterstuetzt: {tp}{sz}")
            for k in range(cnt):
                names.append(fld if cnt == 1 else f"{fld}_{k}")
                formats.append(dt)

        if data_fmt == "binary":
            dtype = np.dtype({"names": names, "formats": formats})
            buf = f.read(dtype.itemsize * npoints)
            arr = np.frombuffer(buf, dtype=dtype, count=npoints)
        elif data_fmt == "ascii":
            rows = np.loadtxt(f, dtype=np.float64, ndmin=2)
            arr = {n: rows[:, i] for i, n in enumerate(names)}
        else:
            raise ValueError(f"DATA {data_fmt} nicht unterstuetzt (nur ascii/binary)")

        x = np.asarray(arr["x"], np.float32)
        y = np.asarray(arr["y"], np.float32)
        z = np.asarray(arr["z"], np.float32)
        rgb = None
        for cand in ("rgb", "rgba"):
            if cand in names:
                packed = np.asarray(arr[cand])
                u = packed.view(np.uint32) if packed.dtype == np.float32 \
                    else packed.astype(np.uint32)
                r = (u >> 16) & 255
                g = (u >> 8) & 255
                b = u & 255
                rgb = np.stack([r, g, b], -1).astype(np.uint8)
                break
        return x, y, z, rgb


def read_labels(path):
    """TreeScope-.labels: eine Ganzzahl je Zeile (ein Label pro Punkt)."""
    return np.loadtxt(path, dtype=np.int64, ndmin=1)


if __name__ == "__main__":
    import sys
    x, y, z, rgb = read_pcd(sys.argv[1])
    print(f"{len(x):,} Punkte  rgb={'ja' if rgb is not None else 'nein'}")
    print(f"  x [{x.min():.2f}, {x.max():.2f}]  y [{y.min():.2f}, {y.max():.2f}]  "
          f"z [{z.min():.2f}, {z.max():.2f}]")
