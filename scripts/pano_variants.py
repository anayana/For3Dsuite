#!/usr/bin/env python3
"""pano_variants.py -- drei Farbstufen eines Panoramas erzeugen (PIL, headless).

Ersetzt den GIMP-Batch (make_variants.ps1) durch reines Pillow, damit die
Varianten auch im Worker-Container entstehen koennen:

  natur     Original (nur neu kodiert)
  kraeftig  mehr Saettigung + Kontrast
  hell      aufgehellt, leicht entsaettigt ausgeglichen

Nutzung:
  python pano_variants.py <pano.jpg> <outdir> [--quality 88]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageEnhance

Image.MAX_IMAGE_PIXELS = None

# id -> (Label, Verarbeitungsfunktion)
VARIANTS = {
    "natur": ("Natur", lambda im: im),
    "kraeftig": ("Kräftig", lambda im: ImageEnhance.Contrast(
        ImageEnhance.Color(im).enhance(1.35)).enhance(1.12)),
    "hell": ("Hell", lambda im: ImageEnhance.Brightness(
        ImageEnhance.Color(im).enhance(1.05)).enhance(1.22)),
}


def make_variants(pano_path, outdir, quality=88, stem="pano"):
    """Erzeugt die Varianten-JPEGs; gibt [(id, label, dateiname), ...] zurueck."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = []
    with Image.open(pano_path) as im:
        im = im.convert("RGB")
        for vid, (label, fn) in VARIANTS.items():
            name = f"{stem}.jpg" if vid == "natur" else f"{stem}_{vid}.jpg"
            fn(im).save(outdir / name, quality=quality)
            out.append((vid, label, name))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pano")
    ap.add_argument("outdir")
    ap.add_argument("--quality", type=int, default=88)
    args = ap.parse_args()
    for vid, label, name in make_variants(args.pano, args.outdir, args.quality):
        size = (Path(args.outdir) / name).stat().st_size / 1e6
        print(f"  {vid:9s} ({label}) -> {name}  {size:.1f} MB")


if __name__ == "__main__":
    main()
