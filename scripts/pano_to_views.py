#!/usr/bin/env python3
"""pano_to_views.py -- Equirect-Panorama -> synthetische Kamerabilder MIT bekannter Pose.

Das fehlende Bindeglied fuer die Evaluation aus dem Paper-Konzept (Abschnitt 5.1):
ein CC0-Panorama ist die WAHRHEIT, aus der sich Einzelaufnahmen mit exakt
bekannter Geometrie erzeugen lassen. Laesst man die Pipeline daraus wieder ein
Panorama bauen, ist der Vergleich mit dem Original ein echter Genauigkeitstest --
ohne Feldmessung, ohne Referenzkamera, beliebig oft wiederholbar.

Zwei Kameramodelle, passend zu den zwei Eingangsklassen des Papers:

  pinhole   Lochkamera mit rechteckigem Sensor -- das Modell der TLS-RGB-Bilder
            (Renon-E57: 6 Pinhole-Kameras je Standpunkt). Die geschriebene
            poses.json hat exakt das Format, das reproject_pano.py liest; damit
            laesst sich der posen-basierte Zweig gegen dieselbe Wahrheit pruefen.

  fisheye   AEQUIDISTANTES Fisheye (r = f*theta) -- das Modell der
            Consumer/DSLR-Aufnahme (Samyang 8 mm o. ae.), also der Fall, in dem
            die Pose NICHT bekannt ist und gestitcht werden muss.

Die Blickrichtungen werden als Ring aus --n Aufnahmen bei --pitch Grad angelegt,
optional mit Zenit- und Nadiraufnahme (--zenith/--nadir) -- die uebliche
Aufnahmeroutine mit Nodalpunktadapter.

Konvention: optische Achse = Kamera -Z, Welt z = oben. Die Bildachsen-Vorzeichen
sind SX = -1, SY = -1 -- und das SX ist keine Geschmacksfrage:

Mit der Kamerabasis right = cross(fwd, world_up) zeigt "right" fuer Blickrichtung
+x nach -y. Im Equirect (lon = atan2(Dy,Dx), Spalte waechst mit lon) hiesse
SX = +1 dann "nach rechts im Bild = nach LINKS im Panorama" -- die Aufnahmen
waeren spiegelverkehrt gegenueber dem, was eine echte Kamera liefert. Der
Rundlauf ueber reproject_pano.py faellt darauf NICHT herein, weil beide
Richtungen dieselbe Konvention benutzen und der Fehler sich heraushebt; Hugin
schon: es stitchte ein inhaltlich einwandfreies, aber gespiegeltes Panorama
(PSNR 13,3 dB normal gegen 30,2 dB gespiegelt).

Deshalb rendert dieses Skript mit SX = -1. Die Rueckprojektion muss folglich mit
  reproject_pano.py --sx -1 --sy -1
aufgerufen werden; die geschriebene poses.json vermerkt das unter "sx"/"sy".

  python scripts/pano_to_views.py pano.jpg out/ --model pinhole --n 6 --fov 90
  python scripts/pano_to_views.py pano.jpg out/ --model fisheye --n 6 --fov 180
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def look_at(yaw_deg, pitch_deg):
    """Rotationsmatrix Kamera->Welt fuer eine Blickrichtung (yaw, pitch).

    Spalten sind (right, up, -fwd): reproject_pano.py liest fwd = R @ [0,0,-1].

    Diese Basis MUSS eine echte Rotation bleiben (Determinante +1), sonst laesst
    sie sich nicht als Quaternion schreiben und reproject_pano.py bekommt Unsinn.
    Mit right = cross(world_up, fwd) waere (right, up, -fwd) eine Spiegelung --
    ein Versuch in diese Richtung liess die Abdeckung der Rueckprojektion von
    99 % auf 52 % einbrechen. Die noetige Spiegelung gehoert deshalb NICHT in die
    Pose, sondern in die Bildachse (SX unten).
    """
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(fwd, world_up)) > 0.999:          # Zenit/Nadir: Referenz drehen
        world_up = np.array([1.0, 0.0, 0.0])
    right = np.cross(fwd, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return np.column_stack([right, up, -fwd])


def R_to_quat(R):
    """Rotationsmatrix -> Quaternion (w, x, y, z), Umkehrung von quat_to_R."""
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x = 0.25 * s, (R[2, 1] - R[1, 2]) / s
        y, z = (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x = (R[2, 1] - R[1, 2]) / s, 0.25 * s
        y, z = (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s
        y, z = 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s
        y, z = (R[1, 2] + R[2, 1]) / s, 0.25 * s
    return [float(w), float(x), float(y), float(z)]


SX, SY = -1.0, -1.0        # Bildachsen-Vorzeichen, siehe Modulkopf


def sample_equirect(pano, D):
    """Weltrichtungen (..,3) -> bilinear aus dem Equirect gesampelt."""
    H, W = pano.shape[:2]
    n = np.linalg.norm(D, axis=-1, keepdims=True)
    D = D / np.maximum(n, 1e-12)
    lon = np.arctan2(D[..., 1], D[..., 0])
    lat = np.arcsin(np.clip(D[..., 2], -1, 1))
    col = (lon + math.pi) / (2 * math.pi) * W - 0.5
    row = (math.pi / 2 - lat) / math.pi * H - 0.5

    x0 = np.floor(col).astype(np.int64)
    y0 = np.clip(np.floor(row).astype(np.int64), 0, H - 2)
    fx = (col - x0)[..., None]
    fy = (row - y0)[..., None]
    x0m, x1m = x0 % W, (x0 + 1) % W          # zyklisch ueber die Panoramanaht
    p = pano.astype(np.float32)
    top = p[y0, x0m] * (1 - fx) + p[y0, x1m] * fx
    bot = p[y0 + 1, x0m] * (1 - fx) + p[y0 + 1, x1m] * fx
    return np.clip(top * (1 - fy) + bot * fy, 0, 255).astype(np.uint8)


def render_pinhole(pano, R, size, fov_deg):
    W = H = size
    f = (size / 2) / math.tan(math.radians(fov_deg) / 2)
    cx = cy = size / 2
    u = (np.arange(W) + 0.5)[None, :]
    v = (np.arange(H) + 0.5)[:, None]
    a = (u - cx) / (SX * f)
    b = (v - cy) / (SY * f)
    right, up, fwd = R[:, 0], R[:, 1], -R[:, 2]
    D = (right * a[..., None] + up * b[..., None] + fwd)
    return sample_equirect(pano, D), f, cx, cy


def render_fisheye(pano, R, size, fov_deg):
    """Aequidistantes Fisheye: Bildradius linear im Winkel zur optischen Achse."""
    f = (size / 2) / (math.radians(fov_deg) / 2)
    cx = cy = size / 2
    u = (np.arange(size) + 0.5)[None, :] - cx
    v = (np.arange(size) + 0.5)[:, None] - cy
    r = np.hypot(u, v)
    theta = r / f
    phi = np.arctan2(v, u)
    inside = theta <= math.radians(fov_deg) / 2
    right, up, fwd = R[:, 0], R[:, 1], -R[:, 2]
    st, ct = np.sin(theta), np.cos(theta)
    D = (right * (SX * st * np.cos(phi))[..., None]
         + up * (SY * st * np.sin(phi))[..., None]
         + fwd * ct[..., None])
    img = sample_equirect(pano, D)
    img[~inside] = 0
    return img, f, cx, cy, inside


def directions(n, pitch, zenith, nadir):
    dirs = [(i * 360.0 / n, pitch) for i in range(n)]
    if zenith:
        dirs.append((0.0, 89.9))
    if nadir:
        dirs.append((0.0, -89.9))
    return dirs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pano")
    ap.add_argument("outdir")
    ap.add_argument("--model", choices=["pinhole", "fisheye"], default="fisheye")
    ap.add_argument("--n", type=int, default=6, help="Aufnahmen im Ring")
    ap.add_argument("--fov", type=float, default=180.0, help="Bildfeld in Grad")
    ap.add_argument("--size", type=int, default=1600, help="Kantenlaenge je Bild")
    ap.add_argument("--pitch", type=float, default=0.0, help="Neigung des Rings [Grad]")
    ap.add_argument("--zenith", action="store_true")
    ap.add_argument("--nadir", action="store_true")
    args = ap.parse_args()

    pano = np.asarray(Image.open(args.pano).convert("RGB"))
    if abs(pano.shape[1] / pano.shape[0] - 2.0) > 0.02:
        raise SystemExit(f"Kein 2:1-Panorama: {pano.shape[1]}x{pano.shape[0]}")
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    dirs = directions(args.n, args.pitch, args.zenith, args.nadir)
    poses, cover = [], np.zeros(pano.shape[:2], bool)
    for i, (yaw, pitch) in enumerate(dirs, 1):
        R = look_at(yaw, pitch)
        if args.model == "pinhole":
            img, f, cx, cy = render_pinhole(pano, R, args.size, args.fov)
        else:
            img, f, cx, cy, _ = render_fisheye(pano, R, args.size, args.fov)
        name = f"view{i:02d}.jpg"
        Image.fromarray(img).save(out / name, quality=95)
        poses.append({
            "file": name, "width": args.size, "height": args.size,
            "representation": "pinholeRepresentation",
            "camera_model": args.model, "fov_deg": args.fov,
            "yaw_deg": yaw, "pitch_deg": pitch,
            "pinhole": {"focalLength": float(f), "pixelWidth": 1.0, "pixelHeight": 1.0,
                        "principalPointX": float(cx), "principalPointY": float(cy)},
            "pose": {"quaternion_wxyz": R_to_quat(R), "translation_xyz": [0.0, 0.0, 0.0]},
            "sx": SX, "sy": SY,
        })
        print(f"  {name}: yaw {yaw:6.1f}  pitch {pitch:5.1f}  f={f:.1f}px")

    meta = {"source": str(Path(args.pano).name),
            "source_size": [pano.shape[1], pano.shape[0]],
            "model": args.model, "fov_deg": args.fov, "n_views": len(dirs),
            "view_size": args.size, "sx": SX, "sy": SY,
            "reprojektion_aufruf": "reproject_pano.py --sx -1 --sy -1",
            "hinweis": ("Synthetisch aus einem Equirect gerendert -- die Posen sind "
                        "exakt bekannt und dienen als Wahrheit. Alle Kameras teilen "
                        "denselben Nodalpunkt (Translation 0), es gibt also KEINE "
                        "Parallaxe. Das ist der Idealfall fuer Stitching: gemessene "
                        "Fehler sind untere Schranken, reale Aufnahmen mit "
                        "Nodalpunktversatz sind schlechter."),
            "cameras": poses}
    (out / "poses.json").write_text(json.dumps(poses, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    print(f"-> {out}: {len(dirs)} Ansichten ({args.model}, FOV {args.fov:g}°), "
          f"poses.json + meta.json")


if __name__ == "__main__":
    main()
