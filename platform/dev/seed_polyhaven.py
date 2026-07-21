#!/usr/bin/env python3
"""seed_polyhaven.py -- CC0-Wald-Panoramen von Poly Haven als Plattform-Szenen.

Laedt ueber die offene Poly-Haven-API (api.polyhaven.com) die Tonemapped-JPGs
der unten gelisteten Wald-HDRIs -- das sind normale LDR-JPGs im equirektangularen
2:1-Format, also direkt Viewer-/Pannellum-tauglich (kein .hdr/.exr noetig).
Downloads werden per MD5 geprueft und unter input/polyhaven/ gecacht, dann als
Pano-Szenen im Dev-Storage veroeffentlicht (Varianten + Thumb wie seed_demo).

Alle Assets stehen unter CC0 (keine Attributionspflicht); Autor, Quelle und
GPS-Koordinaten (falls das Asset getaggt ist) landen trotzdem in scene.json.

  python platform/dev/seed_polyhaven.py                      # alle 8 Wald-Szenen
  python platform/dev/seed_polyhaven.py mossy_forest woods   # nur Auswahl
  python platform/dev/seed_polyhaven.py --list-nature        # API: alle nature-HDRIs
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
CACHE = REPO / "input" / "polyhaven"
API = "https://api.polyhaven.com"
sys.path.insert(0, str(REPO / "scripts"))
from pano_variants import make_variants  # noqa: E402

# Asset-ID -> deutsche Kurzcharakteristik (Reihenfolge = Gallery-Reihenfolge)
ASSETS = {
    "mossy_forest": "Moosiger Wald mit Bach, weiches Morgenlicht",
    "sunset_forest": "Kiefernwald mit Weg im Sonnenuntergang",
    "monks_forest": "Wald mit Pfad",
    "forest_slope": "Bewaldeter Hang im Sommer",
    "hochsal_forest": "Herbstwald mit matschigem Trail",
    "niederwihl_forest": "Totholz und Moos",
    "woods": "Herbstliches Waldstueck am Fluss",
    "nature_reserve_forest": "Wald im Naturschutzgebiet",
    # Hecken/Formschnitt -- Gehoelzstrukturen ausserhalb des Waldes
    "symmetrical_garden_02": "Formgarten mit geschnittenen Heckenreihen",
    "quadrangle_sunny": "Innenhof, von hohen Schnitthecken gerahmt",
    "furstenstein": "Schlossgarten mit Formschnitt-Kegeln und Heckenbaendern",
}


def api_json(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "For3Dsuite-seed"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_tonemapped(aid):
    """Tonemapped-JPG in den Cache laden (MD5-geprueft); gibt (pfad, files) zurueck."""
    files = api_json(f"/files/{aid}")
    tm = files["tonemapped"]
    dest = CACHE / f"{aid}.jpg"
    if dest.is_file() and hashlib.md5(dest.read_bytes()).hexdigest() == tm["md5"]:
        print(f"  {aid}: Cache-Treffer ({dest.stat().st_size/1e6:.1f} MB)")
        return dest, tm
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"  {aid}: lade {tm['size']/1e6:.1f} MB ...")
    req = urllib.request.Request(tm["url"], headers={"User-Agent": "For3Dsuite-seed"})
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    if hashlib.md5(data).hexdigest() != tm["md5"]:
        raise SystemExit(f"MD5-Fehler bei {aid} -- Download beschaedigt?")
    dest.write_bytes(data)
    return dest, tm


def publish(aid, blurb, max_w=8192):
    info = api_json(f"/info/{aid}")
    src, tm = fetch_tonemapped(aid)
    sid = "ph-" + aid.replace("_", "-")
    dest = MEDIA / "scenes" / sid
    dest.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, max_w // 2), Image.LANCZOS)
        w, h = im.size
        im.save(dest / "pano.jpg", quality=90)
        im.resize((640, 320), Image.LANCZOS).save(dest / "thumb.jpg", quality=85)
    variants = [{"id": vid, "label": label, "pano": f"scenes/{sid}/{name}"}
                for vid, label, name in make_variants(dest / "pano.jpg", dest)]

    coords = info.get("coords")
    authors = ", ".join(info.get("authors", {}))
    taken = info.get("date_taken")
    taken_s = datetime.fromtimestamp(taken, timezone.utc).strftime("%Y-%m-%d") if taken else None
    desc = (f"{blurb}. 360-Grad-Panorama (Tonemapped-JPG des {info.get('name', aid)}-HDRIs) "
            f"von Poly Haven, Autor: {authors or 'unbekannt'}, Lizenz CC0"
            + (f", aufgenommen {taken_s}" if taken_s else "")
            + (f", GPS {coords[0]:.5f}, {coords[1]:.5f}" if coords else "") + ".")

    scene = {
        "id": sid, "title": f"{info.get('name', aid)} (Poly Haven)",
        "description": desc,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": f"scenes/{sid}/pano.jpg", "thumb": f"scenes/{sid}/thumb.jpg",
        "width": w, "height": h, "variants": variants,
        "source": {
            "type": "polyhaven", "asset": aid,
            "url": f"https://polyhaven.com/a/{aid}",
            "license": "CC0", "authors": info.get("authors"),
            "gps": {"lat": coords[0], "lon": coords[1]} if coords else None,
            "date_taken": taken_s, "tonemapped_md5": tm["md5"],
        },
        "pointcloud": None, "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"  Szene '{sid}' veroeffentlicht ({w}x{h}"
          + (", GPS" if coords else "") + ")")


def list_nature():
    """Alle nature-HDRIs samt Tonemapped-URL ausgeben (API-Beispiel fuer die Pipeline)."""
    assets = api_json("/assets?type=hdris&categories=nature")
    print(f"{len(assets)} nature-HDRIs auf Poly Haven (alle CC0):")
    for aid in sorted(assets):
        a = assets[aid]
        gps = " GPS" if a.get("coords") else ""
        print(f"  {aid:32s} {a.get('name','')}{gps}"
              f"  https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/{aid}.jpg")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("assets", nargs="*", help="Asset-IDs (Default: alle Wald-Assets)")
    ap.add_argument("--list-nature", action="store_true",
                    help="nur auflisten: alle nature-HDRIs der API")
    args = ap.parse_args()
    if args.list_nature:
        list_nature()
        return
    todo = args.assets or list(ASSETS)
    for aid in todo:
        publish(aid, ASSETS.get(aid, "Poly-Haven-Panorama"))


if __name__ == "__main__":
    main()
