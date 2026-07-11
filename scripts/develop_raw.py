"""Entwickelt Sony-ARW-RAWs zu TIFFs fuer das Hugin-Stitching.

Verwendung:
    python develop_raw.py <ausgabe_ordner> <arw_datei> [<arw_datei> ...] [--half] [--bit16]

  --half   halbe Aufloesung (schneller Testlauf)
  --bit16  16-bit TIFF statt 8-bit (beste Qualitaet, grosse Dateien)
"""
import sys
import os

import numpy as np
import rawpy
from PIL import Image


def develop(arw_path: str, out_dir: str, half: bool, bit16: bool) -> str:
    name = os.path.splitext(os.path.basename(arw_path))[0]
    out_path = os.path.join(out_dir, name + ".tif")
    if os.path.exists(out_path):
        print(f"  {name}: existiert schon, uebersprungen")
        return out_path

    with rawpy.imread(arw_path) as raw:
        rgb = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=True,
            output_bps=16 if bit16 else 8,
            half_size=half,
            output_color=rawpy.ColorSpace.sRGB,
        )

    if bit16:
        # Pillow kann kein 16-bit RGB-TIFF schreiben -> tifffile noetig;
        # wir speichern stattdessen via imageio (nutzt tifffile, falls installiert)
        import imageio.v3 as iio
        iio.imwrite(out_path, rgb)
    else:
        Image.fromarray(rgb).save(out_path, compression="tiff_lzw")

    h, w = rgb.shape[:2]
    print(f"  {name}: {w}x{h} -> {out_path}")
    return out_path


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    half = "--half" in sys.argv
    bit16 = "--bit16" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    out_dir, files = args[0], args[1:]
    os.makedirs(out_dir, exist_ok=True)
    print(f"Entwickle {len(files)} RAWs nach {out_dir} (half={half}, 16bit={bit16})")
    for f in files:
        develop(f, out_dir, half, bit16)


if __name__ == "__main__":
    main()
