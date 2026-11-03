#!/usr/bin/env python3
"""splat_diag.py -- gsplat-Testbilder (renders/val_step*_NNNN.png: links Foto, rechts Render) auswerten.

Je Bild: PSNR, Anteil "Loecher" (Render fast schwarz, Foto hell), PSNR oberes/unteres Drittel,
Helligkeit Foto vs. Render. Dazu drei Vorschaubilder (bestes, mittleres, schlechtestes) als
base64-JPEG im Log, Zeilen "DIAGIMG <name> <teil>/<n> <daten>" -- lokal wieder zusammensetzbar.

  python scripts/splat_diag.py <result_dir>/renders [--width 480]
"""
import argparse
import base64
import glob
import os
import re

import cv2
import numpy as np


def psnr(a, b):
    mse = np.mean((a - b) ** 2)
    return 10 * np.log10(1.0 / max(mse, 1e-12))


def analyse(path):
    im = cv2.imread(path)[:, :, ::-1].astype(np.float32) / 255
    w = im.shape[1] // 2
    gt, rd = im[:, :w], im[:, w:2 * w]
    h = gt.shape[0]
    lum_gt, lum_rd = gt.mean(2), rd.mean(2)
    holes = float(np.mean((lum_rd < 0.05) & (lum_gt > 0.3)))
    # Belichtung ausgleichen: je Kanal Verstaerkung + Versatz (Render -> Foto) nach kleinsten Quadraten
    cc = np.empty_like(rd)
    for c in range(3):
        A = np.stack([rd[..., c].ravel(), np.ones(rd[..., c].size)], 1)
        g, o = np.linalg.lstsq(A, gt[..., c].ravel(), rcond=None)[0]
        cc[..., c] = np.clip(g * rd[..., c] + o, 0, 1)
    return dict(name=os.path.basename(path), psnr=psnr(gt, rd), psnr_cc=psnr(gt, cc), holes=holes,
                top=psnr(gt[: h // 3], rd[: h // 3]), bottom=psnr(gt[-h // 3:], rd[-h // 3:]),
                mean_gt=float(lum_gt.mean()), mean_rd=float(lum_rd.mean()), path=path)


def dump_image(path, width, chunk=3000):
    im = cv2.imread(path)
    s = width * 2 / im.shape[1]
    im = cv2.resize(im, (width * 2, round(im.shape[0] * s)), interpolation=cv2.INTER_AREA)
    data = base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 70])[1]).decode()
    parts = [data[i:i + chunk] for i in range(0, len(data), chunk)]
    for i, p in enumerate(parts, 1):
        print(f"DIAGIMG {os.path.basename(path)} {i}/{len(parts)} {p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("renders")
    ap.add_argument("--width", type=int, default=480)
    a = ap.parse_args()
    files = glob.glob(os.path.join(a.renders, "val_step*_*.png"))
    if not files:
        raise SystemExit(f"FEHLER: keine Renders in {a.renders}")
    last = max(int(re.search(r"val_step(\d+)_", f).group(1)) for f in files)
    files = sorted(f for f in files if f"val_step{last}_" in f)
    rows = sorted((analyse(f) for f in files), key=lambda r: r["psnr"])
    print(f"DIAG Schritt {last}, {len(rows)} Testbilder")
    for r in rows:
        print(f"DIAG {r['name']}: PSNR {r['psnr']:.2f} (Belichtung ausgeglichen {r['psnr_cc']:.2f}) | oben {r['top']:.2f} unten {r['bottom']:.2f} | "
              f"Loecher {100 * r['holes']:.1f} % | Helligkeit Foto {r['mean_gt']:.3f} Render {r['mean_rd']:.3f}")
    p = np.array([r["psnr"] for r in rows])
    print(f"DIAG Mittel PSNR {p.mean():.2f}, belichtungsausgeglichen {np.mean([r['psnr_cc'] for r in rows]):.2f}, Loecher im Mittel {100 * np.mean([r['holes'] for r in rows]):.1f} %")
    for r in (rows[-1], rows[len(rows) // 2], rows[0]):
        dump_image(r["path"], a.width)


if __name__ == "__main__":
    main()
