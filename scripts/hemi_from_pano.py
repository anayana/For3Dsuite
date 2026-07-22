#!/usr/bin/env python3
"""hemi_from_pano.py -- Equirectangular-Panorama -> hemisphaerisches Fisheye (Zenit).

Erzeugt aus einem 360x180-Panorama die nach oben gerichtete Halbkugel in
AEQUIDISTANTER (equi-angularer) Projektion -- also genau das Bildformat, das
klassische Kronenaufnahmen mit Fisheye-Objektiv liefern und das hemispheR
(lens='equidistant') erwartet. Damit werden Panorama-Szenen fuer die
Kronenanalyse (Lueckenanteil, Kronenoeffnung, LAI) auswertbar, ohne dass eine
zweite Aufnahme mit Fisheye-Optik noetig waere.

Projektion: Ausgabepixel im Einheitskreis, Radius r in [0,1] -> Zenitwinkel
theta = r * maxVZA, Azimut phi = atan2(dy,dx). Aequidistant heisst: r ist
LINEAR in theta (nicht in sin(theta) wie bei aequisolider Optik) -- deshalb
ist die Ringflaeche pro Zenitwinkel konstant und die Ringstatistik von
hemispheR direkt anwendbar.

Zeilenbezug im Equirect: Zeile 0 = Zenit, Zeile H/2 = Horizont.

  python hemi_from_pano.py <pano.jpg> <out.png> [--size 1400] [--max-vza 90]
      [--north 0]
"""
import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def equirect_to_fisheye(pano, size, max_vza_deg, north_deg=0.0):
    """Aequidistantes Zenit-Fisheye aus einem Equirect-Panorama (bilinear)."""
    H, W = pano.shape[:2]
    # Pixelmitten auf [-1,1]; ausserhalb des Einheitskreises bleibt es schwarz
    g = (np.arange(size) + 0.5) / size * 2 - 1
    dx, dy = np.meshgrid(g, g)
    r = np.hypot(dx, dy)
    inside = r <= 1.0

    theta = r * np.radians(max_vza_deg)          # Zenitwinkel, linear in r
    phi = np.arctan2(dy, dx) + np.radians(north_deg)

    col = (phi / (2 * np.pi) + 0.5) % 1.0 * W    # Azimut -> Spalte
    row = theta / np.pi * H                      # Zenitwinkel -> Zeile

    # Bilinear, in x zyklisch (Panoramanaht), in y geklemmt
    x0 = np.floor(col - 0.5).astype(np.int64)
    y0 = np.clip(np.floor(row - 0.5).astype(np.int64), 0, H - 2)
    fx = (col - 0.5 - x0)[..., None]
    fy = (row - 0.5 - y0)[..., None]
    x0m, x1m = x0 % W, (x0 + 1) % W

    p = pano.astype(np.float32)
    top = p[y0, x0m] * (1 - fx) + p[y0, x1m] * fx
    bot = p[y0 + 1, x0m] * (1 - fx) + p[y0 + 1, x1m] * fx
    out = (top * (1 - fy) + bot * fy)

    out[~inside] = 0
    return np.clip(out, 0, 255).astype(np.uint8), inside


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pano")
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=1400, help="Kantenlaenge der Ausgabe")
    ap.add_argument("--max-vza", type=float, default=90.0,
                    help="Zenitwinkel am Bildrand in Grad (90 = volle Halbkugel)")
    ap.add_argument("--north", type=float, default=0.0,
                    help="Azimut-Versatz in Grad (Nordausrichtung des Bildes)")
    args = ap.parse_args()

    pano = np.asarray(Image.open(args.pano).convert("RGB"))
    if abs(pano.shape[1] / pano.shape[0] - 2.0) > 0.02:
        raise SystemExit(f"Kein 360x180-Panorama: {pano.shape[1]}x{pano.shape[0]} "
                         f"(erwartet Seitenverhaeltnis 2:1)")

    img, inside = equirect_to_fisheye(pano, args.size, args.max_vza, args.north)
    Image.fromarray(img).save(args.out)

    r = args.size / 2
    print(f"{args.pano}: {pano.shape[1]}x{pano.shape[0]} -> {args.out} "
          f"({args.size}x{args.size}, aequidistant, VZA 0-{args.max_vza:g} Grad)")
    print(f"  Kreismaske: xc={r:.1f} yc={r:.1f} rc={r:.1f}  "
          f"({inside.sum():,} Pixel in der Halbkugel)")


if __name__ == "__main__":
    main()
