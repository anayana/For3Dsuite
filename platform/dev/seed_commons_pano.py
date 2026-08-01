#!/usr/bin/env python3
"""seed_commons_pano.py -- frei lizenziertes 360-Grad-Equirect von Wikimedia
Commons als Consumer-360-Szene (der "equirect"-Eingang der Pipeline).

Belegt den Consumer-Geraetezweig (Ricoh Theta / Insta360 u.ae.) mit FREI
verfuegbaren Daten: ein bodennahes, mit einer 360-Grad-Kamera aufgenommenes
Panorama unter CC-BY-SA. Attribution (Autor + Lizenz) wird aus der Commons-API
gezogen und in die scene.json geschrieben -- CC-BY-SA verlangt Namensnennung.

  python platform/dev/seed_commons_pano.py

Konfiguration unten (ASSETS): Commons-Dateititel, Szenen-ID, Kurzbeschreibung.
"""
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import re

from PIL import Image

# Lokale Python-Zertifikate sind hier abgelaufen; oeffentliche Commons-Downloads
# ungeprueft holen (nur oeffentliche, unkritische Bilddaten).
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
CACHE = REPO / "input" / "commons"
sys.path.insert(0, str(REPO / "scripts"))
from pano_variants import make_variants                         # noqa: E402

UA = "For3Dsuite-research/1.0 (open-source panorama pipeline)"
MAX_W = 4096

# (Commons-Dateititel ohne "File:", Szenen-ID, Kurzbeschreibung)
ASSETS = [
    ("Battery Point Beach, Crescent City, California May 2023.jpg",
     "consumer360-battery-point",
     "Consumer-360-Kamera-Aufnahme (bodennah, Strand). Belegt den "
     "equirektangularen Eingang der Pipeline mit frei lizenzierten Daten"),
    ("Chopfholz Adliswil panosphere 20200616.jpg",
     "consumer360-chopfholz-wald",
     "Schweizer Bergwald (Chopfholz bei Adliswil, ZH) als bodennahes "
     "360-Grad-Panorama -- domaenennaher Consumer-360-Fall mit freien Daten"),
    ("Wald am Wilden Kaiser, Tirol, 360x180, 160620, ako.jpg",
     "consumer360-wilder-kaiser-wald",
     "Bergwald am Wilden Kaiser (Tirol) als 360-Grad-Panorama -- "
     "Wald-Anwendung des equirektangularen Eingangs mit frei lizenzierten Daten"),
]


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=60, context=_SSL).read())


def strip(v):
    return re.sub("<[^>]+>", "", v or "").strip()


def fetch(title):
    d = api({"action": "query", "format": "json", "titles": "File:" + title,
             "prop": "imageinfo", "iiprop": "url|size|extmetadata"})
    ii = list(d["query"]["pages"].values())[0]["imageinfo"][0]
    md = ii["extmetadata"]
    return {"url": ii["url"], "w": ii["width"], "h": ii["height"],
            "artist": strip(md.get("Artist", {}).get("value")),
            "license": strip(md.get("LicenseShortName", {}).get("value")),
            "license_url": strip(md.get("LicenseUrl", {}).get("value")),
            "descurl": ii.get("descriptionurl", "")}


def main():
    for title, sid, blurb in ASSETS:
        meta = fetch(title)
        CACHE.mkdir(parents=True, exist_ok=True)
        raw = CACHE / (sid + "_raw.jpg")
        if not raw.exists():
            req = urllib.request.Request(meta["url"], headers={"User-Agent": UA})
            raw.write_bytes(urllib.request.urlopen(req, timeout=180, context=_SSL).read())
        dest = MEDIA / "scenes" / sid
        dest.mkdir(parents=True, exist_ok=True)
        with Image.open(raw) as im:
            im = im.convert("RGB")
            if im.width > MAX_W:
                im = im.resize((MAX_W, MAX_W // 2), Image.LANCZOS)
            w, h = im.size
            im.save(dest / "pano.jpg", quality=90)
            im.resize((640, 320), Image.LANCZOS).save(dest / "thumb.jpg", quality=85)
        variants = [{"id": vid, "label": label, "pano": f"scenes/{sid}/{name}"}
                    for vid, label, name in make_variants(dest / "pano.jpg", dest)]
        attrib = f"{meta['artist'] or 'unbekannt'}, {meta['license']}"
        scene = {
            "id": sid,
            "title": f"{title.rsplit('.',1)[0]} — Consumer-360 ({meta['license']})",
            "description": (f"{blurb}. 360-Grad-Equirektangular-Panorama, aufgenommen "
                            f"mit einer Consumer-360-Kamera. Quelle: Wikimedia Commons, "
                            f"{attrib}. Auf {w}x{h} skaliert."),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pano": f"scenes/{sid}/pano.jpg", "thumb": f"scenes/{sid}/thumb.jpg",
            "width": w, "height": h, "variants": variants,
            "source": {"type": "wikimedia-commons", "url": meta["descurl"],
                       "license": meta["license"], "license_url": meta["license_url"],
                       "attribution": attrib, "authors": [meta["artist"]]},
            "pointcloud": None, "markers": [],
        }
        (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        print(f"  Szene '{sid}' veroeffentlicht ({w}x{h}), Attribution: {attrib}")


if __name__ == "__main__":
    main()
