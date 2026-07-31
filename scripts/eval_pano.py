#!/usr/bin/env python3
"""eval_pano.py -- rekonstruiertes Panorama gegen die Referenz messen.

Gehoert zur Evaluation aus dem Paper-Konzept (5.1/5.2): aus einem CC0-Panorama
werden synthetische Aufnahmen erzeugt (pano_to_views.py), die Pipeline baut daraus
wieder ein Panorama, und hier wird gemessen, wie weit es vom Original abweicht.

Zwei Dinge muessen dabei beruecksichtigt werden, sonst ist die Zahl wertlos:

  1. ORIENTIERUNG. Stitching legt den Nullmeridian beliebig -- ein gestitchtes
     Panorama kann inhaltlich perfekt sein und trotzdem einen katastrophalen
     PSNR liefern, nur weil es um 37 Grad verdreht ist. Deshalb wird der
     Yaw-Versatz zuerst geschaetzt (Kreuzkorrelation der Spaltenmittel ueber die
     zyklische Achse) und kompensiert. Der gefundene Versatz wird mitberichtet --
     er ist selbst eine Kennzahl.
  2. ABDECKUNG. Rekonstruktionen haben Loecher (Nadir, Randbereiche). Gemessen
     wird nur, wo BEIDE Bilder Inhalt haben; der Abdeckungsgrad steht daneben.

Metriken: PSNR und SSIM (Wang et al., Gauss-Fenster) auf Graustufen, dazu der
mittlere absolute Farbfehler je Kanal. SSIM ist selbst implementiert (OpenCV
statt scikit-image -- eine Abhaengigkeit weniger).

  python scripts/eval_pano.py referenz.jpg rekonstruktion.jpg [--json out.json]
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def load(path, size=None):
    im = Image.open(path).convert("RGB")
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return np.asarray(im)


def content_mask(img, thresh=6):
    """Wo hat das Bild ueberhaupt Inhalt? Schwarz = Loch der Rekonstruktion."""
    return img.max(axis=2) > thresh


def estimate_yaw_shift(ref, rec, mask):
    """Spaltenversatz zwischen Referenz und Rekonstruktion (zyklisch).

    VOLLFLAECHIGE Kreuzkorrelation ueber die zyklische Laengenachse: die FFT
    laeuft zeilenweise, die Korrelationen aller Zeilen werden aufsummiert.

    Der naheliegende Weg -- nur die spaltenweisen HELLIGKEITSMITTEL zu
    korrelieren -- ist an Waldpanoramen unbrauchbar: ueber die Zeilen gemittelt
    sieht jede Spalte wie jede andere aus, das Maximum wandert ins Rauschen.
    Gemessen an einem korrekt gestitchten Panorama lieferte das +142,7 Grad statt
    der wahren Drehung und damit PSNR 11 dB fuer ein einwandfreies Bild.
    Die Zeilenstruktur muss also erhalten bleiben.
    """
    W = ref.shape[1]
    g_ref = cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY).astype(np.float32)
    g_rec = cv2.cvtColor(rec, cv2.COLOR_RGB2GRAY).astype(np.float32)
    g_rec = g_rec * mask                       # Loecher tragen nichts bei
    a = g_ref - g_ref.mean(axis=1, keepdims=True)
    b = g_rec - (g_rec.sum(axis=1, keepdims=True)
                 / np.maximum(mask.sum(axis=1, keepdims=True), 1))
    b = b * mask
    corr = np.fft.irfft(np.fft.rfft(a, axis=1) * np.conj(np.fft.rfft(b, axis=1)),
                        n=W, axis=1).sum(axis=0)
    shift = int(np.argmax(corr))
    if shift > W // 2:
        shift -= W
    return shift


def ssim(a, b, mask=None):
    """SSIM nach Wang et al. mit 11x11-Gaussfenster (sigma 1.5)."""
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    k = (11, 11)
    mu_a = cv2.GaussianBlur(a, k, 1.5)
    mu_b = cv2.GaussianBlur(b, k, 1.5)
    saa = cv2.GaussianBlur(a * a, k, 1.5) - mu_a * mu_a
    sbb = cv2.GaussianBlur(b * b, k, 1.5) - mu_b * mu_b
    sab = cv2.GaussianBlur(a * b, k, 1.5) - mu_a * mu_b
    m = ((2 * mu_a * mu_b + C1) * (2 * sab + C2)
         / ((mu_a ** 2 + mu_b ** 2 + C1) * (saa + sbb + C2)))
    if mask is not None:
        # Rand der Maske ausnehmen: dort mischt das Fenster Inhalt und Loch
        er = cv2.erode(mask.astype(np.uint8), np.ones((11, 11), np.uint8))
        return float(m[er > 0].mean()) if er.any() else float("nan")
    return float(m.mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reference")
    ap.add_argument("reconstruction")
    ap.add_argument("--json", help="Ergebnis als JSON")
    ap.add_argument("--no-align", action="store_true",
                    help="Yaw-Versatz NICHT kompensieren (fuer den posen-basierten "
                         "Zweig, der die Orientierung halten muss)")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    rec = load(args.reconstruction)
    ref = load(args.reference, size=(rec.shape[1], rec.shape[0]))
    mask = content_mask(rec)
    cov = 100.0 * mask.mean()

    shift = 0
    if not args.no_align:
        shift = estimate_yaw_shift(ref, rec, mask)
        if shift:
            rec = np.roll(rec, -shift, axis=1)
            mask = np.roll(mask, -shift, axis=1)
    yaw_deg = shift / rec.shape[1] * 360.0

    both = mask
    if not both.any():
        raise SystemExit("Rekonstruktion ist leer")
    g_ref = cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY)
    g_rec = cv2.cvtColor(rec, cv2.COLOR_RGB2GRAY)
    diff = (ref.astype(np.float64) - rec.astype(np.float64))[both]
    mse = float((diff ** 2).mean())
    psnr = 10 * math.log10(255.0 ** 2 / mse) if mse > 0 else float("inf")

    res = {
        "label": args.label or Path(args.reconstruction).stem,
        "referenz": Path(args.reference).name,
        "rekonstruktion": Path(args.reconstruction).name,
        "groesse": [rec.shape[1], rec.shape[0]],
        "abdeckung_pct": round(cov, 2),
        "yaw_versatz_deg": round(yaw_deg, 2),
        "psnr_db": round(psnr, 2),
        "ssim": round(ssim(g_ref, g_rec, both), 4),
        "mae_grauwert": round(float(np.abs(diff).mean()), 2),
    }
    print(f"{res['label']:28} Abdeckung {res['abdeckung_pct']:5.1f}%  "
          f"Yaw {res['yaw_versatz_deg']:+7.2f}°  PSNR {res['psnr_db']:5.2f} dB  "
          f"SSIM {res['ssim']:.4f}  MAE {res['mae_grauwert']:.1f}")
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return res


if __name__ == "__main__":
    main()
