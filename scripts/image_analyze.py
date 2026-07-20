#!/usr/bin/env python3
"""image_analyze.py -- lokale Bildanalyse eines 360-Equirectangular-Panoramas.

Fuellt die Provenienz-Ebene 'image_derived' (und observed.sun_position) rein
lokal, ohne Fremdquelle -- numpy + Pillow, keine schweren ML-Modelle. Bewusst
heuristisch und als solche gekennzeichnet; SAM/Depth-Anything-Haken bleiben
offen (species_guess/depth = None), damit nichts vorgetaeuscht wird.

Berechnet:
  * gap_fraction / canopy_openness  Himmelsanteil der oberen Hemisphaere
      (solid-angle-gewichtet mit cos(lat)) -- analog hemisphaerischer
      Canopy-Fotografie; Himmel per Helligkeits-/Blau-Heuristik
  * Greenness VARI / GLI / ExG      Mittel ueber Nicht-Himmel-Pixel (RGB-Proxy,
      kein echtes NDVI mangels NIR)
  * sun_position                    hellste Bildregion -> Azimut (lon) / Hoehe (lat),
      mit Konfidenz (klarer Sonnenpeak vs. bedeckt)

Nutzung:
  python image_analyze.py <pano.jpg> [--width 1024] [--out block.json]
"""
import argparse
import json

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SKY_V_MIN = 140       # Mindesthelligkeit fuer Himmel
SKY_SAT_MAX = 0.20    # weiss-/grau-Himmel: geringe Saettigung


def analyze(path, width=1024):
    im = Image.open(path).convert("RGB")
    H0 = max(1, round(im.height * width / im.width))
    im = im.resize((width, H0), Image.BILINEAR)
    a = np.asarray(im, np.float32)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    W, H = width, H0

    lat = 90.0 - (np.arange(H, dtype=np.float32) + 0.5) / H * 180.0   # +90 oben
    w_lat = np.clip(np.cos(np.radians(lat)), 0, None)[:, None]        # Flaechenkorrektur
    upper = (lat > 0)[:, None]

    mx = a.max(-1); mn = a.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    bluish = (B >= R) & (B >= G)
    sky = (mx > SKY_V_MIN) & (bluish | (sat < SKY_SAT_MAX))

    # Gap Fraction: Himmelsanteil der oberen Hemisphaere, solid-angle-gewichtet
    wu = (w_lat * upper)
    denom = float((wu * np.ones_like(R)).sum())
    gap = float((wu * sky).sum() / denom) if denom > 0 else None

    # Greenness ueber Nicht-Himmel-Pixel (Vegetation/Boden/Stamm)
    veg = ~sky
    s = np.maximum(R + G + B, 1.0)
    r, g, b = R / s, G / s, B / s
    with np.errstate(divide="ignore", invalid="ignore"):
        vari = np.where((G + R - B) != 0, (G - R) / (G + R - B), np.nan)
        gli = np.where((2 * G + R + B) != 0, (2 * G - R - B) / (2 * G + R + B), np.nan)
    exg = 2 * g - r - b
    def vmean(x):
        v = x[veg]
        v = v[np.isfinite(v)]
        return round(float(v.mean()), 3) if v.size else None

    # Sonnenstand: hellste Region der (leicht geglaetteten) Luminanz
    L = 0.299 * R + 0.587 * G + 0.114 * B
    idx = int(np.argmax(L)); ry, cx = divmod(idx, W)
    peak = float(L[ry, cx]); med = float(np.median(L))
    lon = (cx + 0.5) / W * 360.0 - 180.0
    azimuth = (lon + 360.0) % 360.0
    elevation = float(90.0 - (ry + 0.5) / H * 180.0)
    # Konfidenz: klarer, heller Peak deutlich ueber Median -> Sonne sichtbar
    sun_conf = round(min(1.0, max(0.0, (peak - med) / 255.0) * (peak / 255.0) * 1.6), 2)

    image_derived = {
        "_note": "algorithmisch aus dem Bild (heuristisch, RGB-only)",
        "canopy_openness_pct": round(gap * 100, 1) if gap is not None else None,
        "gap_fraction": round(gap, 3) if gap is not None else None,
        "greenness_vari": vmean(vari),
        "greenness_gli": vmean(gli),
        "greenness_exg": vmean(exg),
        "leaf_type_visual": None,       # braucht Textur-/VLM-Modell -> offen
        "species_guess": None,          # braucht CLIP/VLM -> offen (nicht vorgetaeuscht)
        "depth_map_ref": None,          # braucht Depth-Anything -> offen
        "sky_fraction_total": round(float((w_lat * sky).sum() /
                                          float((w_lat * np.ones_like(R)).sum())), 3),
        "method": {"sky": "Helligkeit/Blau-Heuristik", "greenness": "RGB-Indizes",
                   "resized_width": width},
    }
    sun_position = {"azimuth_deg": round(azimuth, 1),
                    "elevation_deg": round(elevation, 1), "confidence": sun_conf}
    return image_derived, sun_position


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pano")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--out")
    args = ap.parse_args()
    img, sun = analyze(args.pano, args.width)
    out = {"image_derived": img, "sun_position": sun}
    if args.out:
        open(args.out, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"-> {args.out}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
