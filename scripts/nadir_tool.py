"""Nadir-Werkzeug fuer Equirectangular-Panoramen.

Der Boden (Nadir) ist im Equirectangular-Format extrem verzerrt - Retusche
macht man deshalb in einer entzerrten Draufsicht (gnomonische Projektion):

    extract:  Equirect -> quadratische Draufsicht (zum Retuschieren)
    insert:   retuschierte Draufsicht -> zurueck ins Equirect
    inpaint:  Stativ im Zentrum der Draufsicht automatisch wegrechnen (OpenCV)

Verwendung:
    python nadir_tool.py extract <pano.jpg> <nadir.png> [--size 2048] [--fov 120]
    python nadir_tool.py inpaint <nadir.png> <nadir_clean.png> [--radius 0.30]
    python nadir_tool.py insert  <pano.jpg> <nadir_clean.png> <pano_neu.jpg> [--fov 120]

  --radius  Radius des zu ersetzenden Kreises im Zentrum, als Anteil der
            halben Bildbreite (0.30 = 30%).
"""
import sys

import cv2
import numpy as np


def _arg(name: str, default: float) -> float:
    if name in sys.argv:
        return float(sys.argv[sys.argv.index(name) + 1])
    return default


def extract(pano_path: str, out_path: str, size: int, fov_deg: float) -> None:
    pano = cv2.imread(pano_path)
    H, W = pano.shape[:2]
    t = np.tan(np.radians(fov_deg) / 2.0)

    lin = np.linspace(-t, t, size, dtype=np.float32)
    x, y = np.meshgrid(lin, lin)
    # Blick senkrecht nach unten, z zeigt nach oben
    dx, dy, dz = x, y, -np.ones_like(x)
    norm = np.sqrt(dx * dx + dy * dy + dz * dz)
    lon = np.arctan2(dy, dx)
    lat = np.arcsin(dz / norm)

    map_x = ((lon / (2 * np.pi) + 0.5) * W).astype(np.float32)
    map_y = ((0.5 - lat / np.pi) * H).astype(np.float32)
    nadir = cv2.remap(pano, map_x, map_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_WRAP)
    cv2.imwrite(out_path, nadir)
    print(f"Nadir-Draufsicht ({size}x{size}, FOV {fov_deg} Grad) -> {out_path}")


def inpaint(nadir_path: str, out_path: str, radius_frac: float) -> None:
    img = cv2.imread(nadir_path)
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.circle(mask, (w // 2, h // 2), int(radius_frac * w / 2), 255, -1)
    result = cv2.inpaint(img, mask, inpaintRadius=11, flags=cv2.INPAINT_TELEA)
    cv2.imwrite(out_path, result)
    print(f"Stativ-Bereich (Radius {radius_frac:.0%}) weggerechnet -> {out_path}")


def clone(nadir_path: str, out_path: str, radius_frac: float, dx: int, dy: int) -> None:
    """Ersetzt den Kreis im Zentrum durch eine geklonte Bodenregion
    (Poisson-Blending passt Helligkeit/Farbe am Rand automatisch an)."""
    img = cv2.imread(nadir_path)
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    r = int(radius_frac * w / 2)

    src_x, src_y = cx + dx, cy + dy
    if not (r <= src_x < w - r and r <= src_y < h - r):
        raise SystemExit(f"Quellregion ({src_x},{src_y}) r={r} liegt ausserhalb des Bildes")

    pad = int(r * 1.3)
    patch = img[src_y - pad:src_y + pad, src_x - pad:src_x + pad].copy()
    mask = np.zeros(patch.shape[:2], np.uint8)
    cv2.circle(mask, (pad, pad), r, 255, -1)

    result = cv2.seamlessClone(patch, img, mask, (cx, cy), cv2.NORMAL_CLONE)
    cv2.imwrite(out_path, result)
    print(f"Zentrum (r={r}px) durch Klon von Offset ({dx},{dy}) ersetzt -> {out_path}")


def insert(pano_path: str, nadir_path: str, out_path: str, fov_deg: float) -> None:
    pano = cv2.imread(pano_path)
    nadir = cv2.imread(nadir_path)
    H, W = pano.shape[:2]
    N = nadir.shape[0]
    t = np.tan(np.radians(fov_deg) / 2.0)

    # Nur der untere Bildbereich kann betroffen sein
    lat_min = -np.pi / 2
    lat_max = -np.arctan(1.0 / t)  # ausserhalb des FOV-Kegels keine Aenderung
    y0 = int((0.5 - lat_max / np.pi) * H)

    ys = np.arange(y0, H, dtype=np.float32)
    xs = np.arange(0, W, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)
    lon = (xg / W - 0.5) * 2 * np.pi
    lat = (0.5 - yg / H) * np.pi

    dz = np.sin(lat)
    r = np.cos(lat)
    dx = r * np.cos(lon)
    dy = r * np.sin(lon)

    scale = -1.0 / np.minimum(dz, -1e-6)  # Schnitt mit Ebene z=-1
    px = dx * scale
    py = dy * scale

    map_x = ((px + t) / (2 * t) * (N - 1)).astype(np.float32)
    map_y = ((py + t) / (2 * t) * (N - 1)).astype(np.float32)
    patch = cv2.remap(nadir, map_x, map_y, cv2.INTER_LANCZOS4,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # Weiche Blende am Rand des Kegels, damit kein harter Uebergang entsteht
    rad = np.sqrt(px * px + py * py)
    alpha = np.clip((t * 0.98 - rad) / (t * 0.10), 0, 1)[..., None]
    inside = ((np.abs(px) <= t) & (np.abs(py) <= t))[..., None]
    alpha = alpha * inside

    region = pano[y0:H].astype(np.float32)
    blended = region * (1 - alpha) + patch.astype(np.float32) * alpha
    pano[y0:H] = blended.astype(np.uint8)
    cv2.imwrite(out_path, pano, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"Nadir zurueckprojiziert -> {out_path}")


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(sys.argv[2], sys.argv[3], int(_arg("--size", 2048)), _arg("--fov", 120))
    elif cmd == "inpaint":
        inpaint(sys.argv[2], sys.argv[3], _arg("--radius", 0.30))
    elif cmd == "clone":
        clone(sys.argv[2], sys.argv[3], _arg("--radius", 0.30),
              int(_arg("--dx", -300)), int(_arg("--dy", 300)))
    elif cmd == "insert":
        insert(sys.argv[2], sys.argv[3], sys.argv[4], _arg("--fov", 120))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
