#!/usr/bin/env python3
"""Stativ am Nadir der Barberini-Panos per Exemplar-Inpainting (Criminisi-Prinzip)
entfernen: Boden flach entzerren -> Loch mit echten Parkett-Stuecken aus der
direkten Umgebung fuellen (Orientierung passt lokal) -> zurueck ins Panorama.
Kein Weichzeichner, kein Klon-Flicken mit falscher Maserung."""
import numpy as np
import cv2
from pathlib import Path
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "platform" / "dev-data" / "media" / "scenes"
RAW = REPO / "input" / "commons"


def sample(arr, sx, sy):
    Hh, Ww = arr.shape[:2]
    sx = np.clip(sx, 0, Ww - 1); sy = np.clip(sy, 0, Hh - 1)
    x0 = np.floor(sx).astype(int); y0 = np.floor(sy).astype(int)
    x1 = np.minimum(x0 + 1, Ww - 1); y1 = np.minimum(y0 + 1, Hh - 1)
    wx = (sx - x0)[..., None]; wy = (sy - y0)[..., None]
    return (arr[y0, x0] * (1 - wx) * (1 - wy) + arr[y0, x1] * wx * (1 - wy)
            + arr[y1, x0] * (1 - wx) * wy + arr[y1, x1] * wx * wy)


def flat(a, R, alpha):
    H, W, _ = a.shape; D = np.tan(alpha); c = (R - 1) / 2
    ys, xs = np.mgrid[0:R, 0:R].astype(np.float32); X = (xs - c) / c * D; Y = (ys - c) / c * D
    d = np.sqrt(X * X + Y * Y); th = np.arctan(d); phi = np.arctan2(Y, X); lat = th - np.pi / 2
    ex = ((phi / (2 * np.pi)) + 0.5) * (W - 1); ey = (0.5 - lat / np.pi) * (H - 1)
    return sample(a, ex, ey), (th <= alpha), d, D, c


def exemplar(F, mask, P=11, search=90, max_steps=60000):
    H, W = mask.shape; pr = P // 2
    img = np.clip(F, 0, 255).astype(np.uint8)
    known = (mask == 0).astype(np.uint8)
    full = cv2.erode(known, np.ones((P, P), np.uint8))
    steps = 0
    while known.sum() < H * W and steps < max_steps:
        holem = (known == 0).astype(np.uint8)
        if holem.sum() == 0:
            break
        bnd = holem * (cv2.dilate(known, np.ones((3, 3), np.uint8)) > 0)
        kc = cv2.boxFilter(known.astype(np.float32), -1, (P, P), normalize=False) * bnd
        py, px = np.unravel_index(np.argmax(kc), kc.shape)
        y0, y1, x0, x1 = py - pr, py + pr + 1, px - pr, px + pr + 1
        if y0 < 0 or x0 < 0 or y1 > H or x1 > W:
            known[py, px] = 1; continue
        tp = img[y0:y1, x0:x1]; tm = (known[y0:y1, x0:x1] * 255).astype(np.uint8)
        sy0, sy1 = max(pr, py - search), min(H - pr, py + search)
        sx0, sx1 = max(pr, px - search), min(W - pr, px + search)
        reg = img[sy0 - pr:sy1 + pr, sx0 - pr:sx1 + pr]
        res = cv2.matchTemplate(reg, tp, cv2.TM_SQDIFF, mask=tm).astype(np.float32)
        fr = full[sy0:sy1, sx0:sx1]
        res[fr[:res.shape[0], :res.shape[1]] == 0] = 1e18   # nur voll-bekannte Quellen
        my, mx = np.unravel_index(np.argmin(res), res.shape)
        syc, sxc = sy0 + my, sx0 + mx
        sp = img[syc - pr:syc + pr + 1, sxc - pr:sxc + pr + 1]
        unk = known[y0:y1, x0:x1] == 0
        blk = img[y0:y1, x0:x1].copy(); blk[unk] = sp[unk]; img[y0:y1, x0:x1] = blk
        known[y0:y1, x0:x1][unk] = 1
        full = cv2.erode(known, np.ones((P, P), np.uint8))
        steps += 1
    return img.astype(np.float32)


def tripod_mask(F, d, valid, c, alpha):
    """Das Stativ per Black-Top-Hat finden: hebt DUENNE DUNKLE Strukturen hervor,
    unabhaengig vom Bodenton (findet die Beine auch auf hellem Nussbaum-Laeufer).
    Nur zentrale Komponenten behalten, dann auf die volle Beinbreite ausdehnen."""
    lum = np.clip(F.mean(2), 0, 255).astype(np.uint8)
    bh = cv2.morphologyEx(lum, cv2.MORPH_BLACKHAT,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45)))
    region = (d < 0.5 * np.tan(alpha)) & valid
    resp = bh.astype(np.float32); resp[~region] = 0
    T = max(9, np.percentile(resp[region], 98.5))
    m = (resp > T).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8); keep = np.zeros_like(m)
    for k in range(1, n):
        if stats[k, 4] >= 25 and ((cent[k][0] - c) ** 2 + (cent[k][1] - c) ** 2) ** 0.5 < 0.45 * c:
            keep[lab == k] = 1
    keep = cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)), 1)
    return keep * 255


def heal(a, alpha_deg=50, R=1100):
    H, W, _ = a.shape; alpha = np.radians(alpha_deg)
    F, valid, d, D, c = flat(a, R, alpha)
    mask = tripod_mask(F, d, valid, c, alpha)
    filled = exemplar(F, mask, P=13, search=50)
    soft = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), 2)[..., None]
    Ff = filled * soft + F * (1 - soft)
    yb = int((0.5 - (-np.pi / 2 + alpha) / np.pi) * (H - 1))
    Yy, Xx = np.mgrid[yb:H, 0:W].astype(np.float32)
    lat2 = (0.5 - Yy / (H - 1)) * np.pi; lon2 = (Xx / (W - 1) - 0.5) * 2 * np.pi
    th2 = np.clip(lat2 + np.pi / 2, 0, alpha); d2 = np.tan(th2)
    gx = c + (d2 / D) * c * np.cos(lon2); gy = c + (d2 / D) * c * np.sin(lon2)
    hv = sample(Ff, gx, gy); mv = np.clip(sample(soft, gx, gy), 0, 1)
    out = a.copy(); out[yb:H] = hv * mv + a[yb:H] * (1 - mv)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def main():
    for i in range(1, 11):
        a = np.asarray(Image.open(RAW / f"barberini-{i:02d}_raw.jpg").convert("RGB")
                       .resize((4096, 2048), Image.LANCZOS)).astype(np.float32)
        fx = heal(a); d = BASE / f"barberini-{i:02d}"
        fx.save(d / "pano.jpg", quality=90)
        fx.resize((640, 320), Image.LANCZOS).save(d / "thumb.jpg", quality=85)
        print(f"  barberini-{i:02d}: Stativ per Exemplar-Inpainting entfernt", flush=True)
    print("Fertig.")


if __name__ == "__main__":
    main()
