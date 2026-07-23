#!/usr/bin/env python3
"""ndvi_pdok.py -- CIR-Pseudo-NDVI aus offenem niederlaendischem Luftbild (PDOK).

Laedt das aktuelle 25-cm-Infrarot-Orthophoto (PDOK Luchtfoto CIR, Open Data) fuer
eine RD-New-Bounding-Box und rechnet daraus ein Vegetations-NDVI-Analog. Ergebnis
ist ein georeferenziertes ESRI-ASCII-Grid (.asc), das terra/lidR ohne rasterio
lesen koennen.

WICHTIG -- das ist PSEUDO-NDVI, nicht kalibriertes Oberflaechenreflexions-NDVI:
Das CIR-Composite ist ein 8-Bit-JPEG (NIR im Rot-, Rot im Gruenkanal). Berechnet
wird (NIR-Rot)/(NIR+Rot) aus diesen Kanaelen. Der Wertebereich ist niedriger und
anders skaliert als echtes Sentinel-NDVI -- taugt als relative Greenness, nicht
als absoluter Vegetationsindex.

  python scripts/ndvi_pdok.py <xmin> <ymin> <xmax> <ymax> <out.asc> [--res 0.5]

Bbox in EPSG:28992 (RD New), Meter.
"""
import argparse
import io
import sys
import urllib.parse as up
import urllib.request as ur

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
WMS = "https://service.pdok.nl/hwh/luchtfotocir/wms/v1_0"
LAYER = "Actueel_ortho25IR"
MAX_PX = 2000          # PDOK-GetMap-Grenze je Achse; groesser -> kacheln


def fetch(bbox, w, h):
    p = {"service": "WMS", "request": "GetMap", "version": "1.1.1",
         "layers": LAYER, "styles": "", "srs": "EPSG:28992",
         "format": "image/png", "width": w, "height": h,
         "bbox": ",".join(f"{v:.1f}" for v in bbox)}
    url = WMS + "?" + up.urlencode(p)
    with ur.urlopen(url, timeout=120) as r:
        ct = r.headers.get("content-type", "")
        data = r.read()
    if "image" not in ct:
        raise SystemExit(f"WMS lieferte kein Bild ({ct}): {data[:200]!r}")
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xmin", type=float); ap.add_argument("ymin", type=float)
    ap.add_argument("xmax", type=float); ap.add_argument("ymax", type=float)
    ap.add_argument("out")
    ap.add_argument("--res", type=float, default=0.5, help="Bodenaufloesung (m)")
    args = ap.parse_args()

    W = int(round((args.xmax - args.xmin) / args.res))
    H = int(round((args.ymax - args.ymin) / args.res))
    # In Kacheln <= MAX_PX herunterbrechen und zusammensetzen (Nord oben)
    nx = (W + MAX_PX - 1) // MAX_PX
    ny = (H + MAX_PX - 1) // MAX_PX
    print(f"CIR {W}x{H} px ({args.res} m) in {nx}x{ny} Kachel(n)")
    img = np.empty((H, W, 3), np.float32)
    for iy in range(ny):
        for ix in range(nx):
            x0, x1 = ix * MAX_PX, min((ix + 1) * MAX_PX, W)
            y0, y1 = iy * MAX_PX, min((iy + 1) * MAX_PX, H)
            # Bild-Zeile 0 = Norden = ymax; WMS-bbox in Weltkoordinaten
            bbox = (args.xmin + x0 * args.res, args.ymax - y1 * args.res,
                    args.xmin + x1 * args.res, args.ymax - y0 * args.res)
            tile = fetch(bbox, x1 - x0, y1 - y0)
            img[y0:y1, x0:x1] = tile
            print(f"  Kachel ({ix},{iy}) {x1-x0}x{y1-y0}")

    nir, red = img[..., 0], img[..., 1]
    ndvi = (nir - red) / (nir + red + 1e-6)
    # Sehr dunkle Flaechen (Schatten/Wasser) sind unzuverlaessig -> NoData
    dark = (nir + red) < 40
    ndvi[dark] = -9999.0

    valid = ndvi[ndvi > -9990]
    print(f"Pseudo-NDVI: median {np.median(valid):.2f}  "
          f"p90 {np.percentile(valid, 90):.2f}  NoData {100*dark.mean():.1f} %")

    # ESRI-ASCII: Zeile 0 = oberste (noerdlichste), yllcorner = Suedrand
    hdr = (f"ncols {W}\nnrows {H}\n"
           f"xllcorner {args.xmin:.3f}\nyllcorner {args.ymin:.3f}\n"
           f"cellsize {args.res}\nNODATA_value -9999\n")
    with open(args.out, "w") as f:
        f.write(hdr)
        np.savetxt(f, ndvi, fmt="%.4f")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
