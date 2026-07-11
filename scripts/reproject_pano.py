#!/usr/bin/env python3
"""reproject_pano.py -- Equirectangular-Panorama aus posierten Pinhole-Bildern.

Nutzt die im E57 mitgelieferten Kamera-Posen (Quaternion + Translation) und
Intrinsics direkt: fuer jede Ausgaberichtung (lon/lat) wird der Weltstrahl in
jede Kamera projiziert und der beste (zentrumsnaechste) Treffer gesampelt.
Keine Kontrollpunkte, keine Feature-Suche -- deterministisch und robust bei
merkmalsarmen Kronendach-/Himmelbildern.

Konvention (empirisch aus img5=oben / img6=unten bestimmt):
  R = Kamera->Welt (aus Quaternion), optische Achse = Kamera -Z.
  Welt: z = oben. Bild-Achsen-Vorzeichen via --sx/--sy einstellbar.

Nutzung:
  python reproject_pano.py <poses.json> <imgdir> <out.jpg> [--w 4096] [--sx 1] [--sy -1] [--flip]
"""
import sys, os, json, argparse
import numpy as np
from PIL import Image

def quat_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2*(y*y+z*z), 2*(x*y-z*w),     2*(x*z+y*w)],
        [2*(x*y+z*w),     1 - 2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w),     2*(y*z+x*w),     1 - 2*(x*x+y*y)]])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("poses"); ap.add_argument("imgdir"); ap.add_argument("out")
    ap.add_argument("--w", type=int, default=4096, help="Panoramabreite (Hoehe = w/2)")
    ap.add_argument("--sx", type=int, default=1)
    ap.add_argument("--sy", type=int, default=-1)
    ap.add_argument("--fwd", default="-z", choices=["+z", "-z"], help="optische Achse im Kamera-Frame")
    ap.add_argument("--fovpad", type=float, default=1.0,
                    help="erlaubter Bildradius-Faktor (1.0 = exakt Sensor, >1 leicht darueber)")
    args = ap.parse_args()

    poses = json.load(open(args.poses))
    W = args.w; H = W // 2
    fsign = 1.0 if args.fwd == "+z" else -1.0

    # Kameras einmal vorbereiten (Bild + Basisvektoren + Intrinsics)
    cams = []
    for e in poses:
        if e.get("representation") != "pinholeRepresentation" or "file" not in e:
            continue
        ph = e["pinhole"]; R = quat_to_R(e["pose"]["quaternion_wxyz"])
        cams.append(dict(
            img=np.asarray(Image.open(os.path.join(args.imgdir, e["file"])).convert("RGB")),
            right=(R @ np.array([1, 0, 0])).astype(np.float32),
            up=(R @ np.array([0, 1, 0])).astype(np.float32),
            fwd=(R @ np.array([0, 0, fsign])).astype(np.float32),
            fpx=np.float32(ph["focalLength"] / ph["pixelWidth"]),
            cx=ph["principalPointX"], cy=ph["principalPointY"],
            iw=e["width"], ih=e["height"]))
    if not cams:
        sys.exit("Keine pinholeRepresentation-Bilder in poses.json")

    out = np.zeros((H, W, 3), np.uint8)
    lon = ((np.arange(W, dtype=np.float32) + 0.5) / W * 2*np.pi - np.pi)
    coslon = np.cos(lon); sinlon = np.sin(lon)
    covered = 0

    BAND = 256  # Zeilenblock -> begrenzt den Speicher auch bei 8192px
    for y0 in range(0, H, BAND):
        y1 = min(H, y0 + BAND)
        lat = (np.pi/2 - (np.arange(y0, y1, dtype=np.float32) + 0.5) / H * np.pi)
        cl = np.cos(lat)[:, None]; sl = np.sin(lat)[:, None]
        dx = cl * coslon[None, :]; dy = cl * sinlon[None, :]
        dz = np.broadcast_to(sl, dx.shape)
        D = np.stack([dx, dy, dz], -1)                       # (band,W,3) float32
        acc = np.zeros((y1 - y0, W, 3), np.float32)
        wsum = np.zeros((y1 - y0, W), np.float32)
        for c in cams:
            along = D @ c["fwd"]
            a = D @ c["right"]; b = D @ c["up"]
            with np.errstate(divide="ignore", invalid="ignore"):
                col = c["cx"] + args.sx * c["fpx"] * (a / along)
                row = c["cy"] + args.sy * c["fpx"] * (b / along)
            inb = (along > 1e-6) & (col >= 0) & (col < c["iw"]) & (row >= 0) & (row < c["ih"])
            if not inb.any():
                continue
            ci = np.clip(np.where(inb, col, 0).astype(np.int32), 0, c["iw"]-1)
            ri = np.clip(np.where(inb, row, 0).astype(np.int32), 0, c["ih"]-1)
            sample = c["img"][ri, ci].astype(np.float32)     # (band,W,3)
            lum = sample.mean(-1)
            w = np.where(inb, np.clip(along, 0, 1)**3, 0.0).astype(np.float32)
            w *= (lum > 8)                                    # schwarze Nadir-Maske raus
            acc += sample * w[..., None]
            wsum += w
        nz = wsum > 0
        band = np.zeros((y1 - y0, W, 3), np.uint8)
        band[nz] = np.clip(acc[nz] / wsum[nz, None], 0, 255).astype(np.uint8)
        out[y0:y1] = band
        covered += int(nz.sum())

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    Image.fromarray(out).save(args.out, quality=92)
    cov = 100.0 * covered / (H * W)
    print(f"-> {args.out}  {W}x{H}  Abdeckung {cov:.1f}%  (sx={args.sx} sy={args.sy} fwd={args.fwd})")

if __name__ == "__main__":
    main()
