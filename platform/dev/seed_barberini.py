#!/usr/bin/env python3
"""seed_barberini.py -- Street-View-Rundgang durch das Museum Barberini (Potsdam)
aus der frei lizenzierten 360-Grad-Panoramaserie von Raimond Spekking
(Wikimedia Commons, CC BY-SA 4.0).

Erzeugt je Panorama eine reine Pano-Szene und verknuepft sie ueber PORTAL-Marker
zu einem begehbaren Rundgang: Klick auf ein Portal springt in den naechsten/
vorherigen Saal (wie Google Street View). Reihenfolge = Aufnahmereihenfolge.

  python platform/dev/seed_barberini.py

Attribution (CC BY-SA verlangt Namensnennung) wird aus der Commons-API gezogen.
Portal-Blickrichtungen (yaw) sind sinnvolle Vorgaben und lassen sich je Szene
nachjustieren, sobald man die Tueren in den Panos verortet.
"""
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import re

import numpy as np
import cv2
from PIL import Image

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE
Image.MAX_IMAGE_PIXELS = None

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
CACHE = REPO / "input" / "commons"
UA = "For3Dsuite-research/1.0 (open-source panorama pipeline)"
MAX_W = 4096
API = "https://commons.wikimedia.org/w/api.php"

# Commons-Dateititel (ohne "File:") in Aufnahme-/Rundgangsreihenfolge.
PANOS = [
    "Museum Barberini, Potsdam, Kugelpanorama-005.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-006.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-008.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-009.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-010.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-011.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-012.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-013.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-014.jpg",
    "Museum Barberini, Potsdam, Kugelpanorama-015.jpg",
]


def strip(s):
    return re.sub("<[^>]+>", "", s or "").strip()


def fetch(title):
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "titles": "File:" + title,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata"})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    d = json.load(urllib.request.urlopen(req, timeout=120, context=_SSL))
    ii = list(d["query"]["pages"].values())[0]["imageinfo"][0]
    md = ii["extmetadata"]
    return {"url": ii["url"], "w": ii["width"], "h": ii["height"],
            "artist": strip(md.get("Artist", {}).get("value")) or "Raimond Spekking",
            "license": strip(md.get("LicenseShortName", {}).get("value")) or "CC BY-SA 4.0",
            "license_url": strip(md.get("LicenseUrl", {}).get("value"))
            or "https://creativecommons.org/licenses/by-sa/4.0",
            "descurl": ii.get("descriptionurl", "")}


def sid_for(i):
    return f"barberini-{i+1:02d}"


def _sample(arr, sx, sy):
    Hh, Ww = arr.shape[:2]
    sx = np.clip(sx, 0, Ww - 1); sy = np.clip(sy, 0, Hh - 1)
    x0 = np.floor(sx).astype(int); y0 = np.floor(sy).astype(int)
    x1 = np.minimum(x0 + 1, Ww - 1); y1 = np.minimum(y0 + 1, Hh - 1)
    wx = (sx - x0)[..., None]; wy = (sy - y0)[..., None]
    return (arr[y0, x0] * (1 - wx) * (1 - wy) + arr[y0, x1] * wx * (1 - wy)
            + arr[y1, x0] * (1 - wx) * wy + arr[y1, x1] * wx * wy)


def fill_nadir(im, alpha_deg=42, R=1500):
    """Stativ/Fotograf am Nadir wegretuschieren wie GIMP "Heal Selection":
    in die Draufsicht (senkrecht nach unten) projizieren, das Stativ per
    adaptivem Schwellwert (deutlich dunkler als der Boden) maskieren, mit
    cv2.inpaint heilen und nur den Maskenbereich ins Equirect zurueckrechnen."""
    a = np.asarray(im.convert("RGB")).astype(np.float32); H, W, _ = a.shape
    alpha = np.radians(alpha_deg); c = (R - 1) / 2
    ys, xs = np.mgrid[0:R, 0:R].astype(np.float32); dx = (xs - c) / c; dy = (ys - c) / c
    rr = np.sqrt(dx * dx + dy * dy); lat = np.clip(rr, 0, 1) * alpha - np.pi / 2
    phi = np.arctan2(dy, dx)
    ex = ((phi / (2 * np.pi)) + 0.5) * (W - 1); ey = (0.5 - lat / np.pi) * (H - 1)
    down = _sample(a, ex, ey); luma = down.mean(2)
    floor_med = np.median(luma[(rr > 0.5) & (rr < 0.92)]); thr = floor_med * 0.60
    mask = ((luma < thr) & (rr < 0.48)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8); keep = np.zeros_like(mask)
    for k in range(1, n):
        if stats[k, 4] >= 30 and ((cent[k][0] - c) ** 2 + (cent[k][1] - c) ** 2) ** 0.5 < 0.5 * c:
            keep[lab == k] = 1
    mask = cv2.dilate(keep * 255, np.ones((7, 7), np.uint8), 1)
    healed = cv2.inpaint(np.clip(down, 0, 255).astype(np.uint8), mask, 4,
                         cv2.INPAINT_TELEA).astype(np.float32)
    yb = int((0.5 - (-np.pi / 2 + alpha) / np.pi) * (H - 1))
    yy, xx = np.mgrid[yb:H, 0:W].astype(np.float32)
    lat2 = (0.5 - yy / (H - 1)) * np.pi; lon2 = (xx / (W - 1) - 0.5) * 2 * np.pi
    rr2 = np.clip((lat2 + np.pi / 2) / alpha, 0, 1)
    u = c + rr2 * c * np.cos(lon2); v = c + rr2 * c * np.sin(lon2)
    hv = _sample(healed, u, v)
    mv = np.clip(_sample(mask[..., None].astype(np.float32), u, v)[..., 0] / 255.0, 0, 1)[..., None]
    a[yb:H] = hv * mv + a[yb:H] * (1 - mv)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# Aus Sichtpruefung der 10 Panos verortete Tuer-Winkel (yaw) je Saal (1-basiert):
# 'next' = Durchgang Richtung naechster Saal, 'prev' = Durchgang zurueck.
DOORS = {
    1: {"next": 0},
    2: {"next": 0, "prev": 180},
    3: {"next": 153, "prev": -157},
    4: {"next": 153, "prev": -157},
    5: {"next": 173, "prev": -173},
    6: {"next": 85, "prev": -108},
    7: {"next": 72, "prev": 180},
    8: {"next": 173, "prev": -140},
    9: {"next": 144, "prev": -154},
    10: {"prev": -112},
}
PORTAL_PITCH = -10   # in der Tueroeffnung (nicht am Boden)


def portals(i, n):
    """Portal-Marker als Boden-Pfeile, ausgerichtet auf die tatsaechlichen
    Durchgaenge (DOORS). i ist 0-basiert."""
    d = DOORS[i + 1]
    ms = []
    if i > 0 and "prev" in d:
        ms.append({"id": "prev", "type": "portal", "label": "Zurück",
                   "yaw": d["prev"], "pitch": PORTAL_PITCH,
                   "target": sid_for(i - 1), "target_yaw": 180})
    if i < n - 1 and "next" in d:
        ms.append({"id": "next", "type": "portal", "label": "Weiter",
                   "yaw": d["next"], "pitch": PORTAL_PITCH,
                   "target": sid_for(i + 1), "target_yaw": 0})
    return ms


def main():
    n = len(PANOS)
    CACHE.mkdir(parents=True, exist_ok=True)
    for i, title in enumerate(PANOS):
        sid = sid_for(i)
        meta = fetch(title)
        raw = CACHE / (sid + "_raw.jpg")
        if not raw.exists():
            req = urllib.request.Request(meta["url"], headers={"User-Agent": UA})
            raw.write_bytes(urllib.request.urlopen(req, timeout=300, context=_SSL).read())
        dest = MEDIA / "scenes" / sid
        dest.mkdir(parents=True, exist_ok=True)
        with Image.open(raw) as im:
            im = im.convert("RGB")
            if im.width > MAX_W:
                im = im.resize((MAX_W, MAX_W // 2), Image.LANCZOS)
            w, h = im.size
            im = fill_nadir(im)                     # Stativ am Nadir wegretuschieren
            im.save(dest / "pano.jpg", quality=90)
            im.resize((640, 320), Image.LANCZOS).save(dest / "thumb.jpg", quality=85)
        attrib = f"{meta['artist']}, {meta['license']}"
        num = title.rsplit("-", 1)[-1].rsplit(".", 1)[0]
        scene = {
            "id": sid,
            "title": f"Museum Barberini — Rundgang {i+1}/{n} (CC BY-SA 4.0)",
            "description": (
                f"Museum Barberini, Potsdam — Saal {i+1} von {n} im begehbaren "
                f"Street-View-Rundgang. 360-Grad-Equirektangular-Panorama (Kugelpanorama "
                f"{num}). Klick auf ein Portal springt in den naechsten/vorherigen Saal. "
                f"Quelle: Wikimedia Commons, {attrib}. Auf {w}x{h} skaliert."),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pano": f"scenes/{sid}/pano.jpg", "thumb": f"scenes/{sid}/thumb.jpg",
            "width": w, "height": h, "variants": [],
            "source": {"type": "wikimedia-commons", "url": meta["descurl"],
                       "license": meta["license"], "license_url": meta["license_url"],
                       "attribution": attrib, "authors": [meta["artist"]]},
            "tour": {"index": i + 1, "count": n,
                     "prev": sid_for(i - 1) if i > 0 else None,
                     "next": sid_for(i + 1) if i < n - 1 else None},
            "pointcloud": None,
            "markers": portals(i, n),
        }
        (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        print(f"  {sid}: {w}x{h}  Portale: {[m['id'] for m in scene['markers']]}")
    print(f"Fertig: {n} Barberini-Szenen (Rundgang). Attribution: {attrib}")


if __name__ == "__main__":
    main()
