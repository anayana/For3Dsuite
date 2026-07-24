#!/usr/bin/env python3
"""export_static.py -- statischer Gallery-Export fuer GitHub Pages o. ae.

Baut aus dem lokalen Dev-Storage (platform/dev-data/media) eine komplett
statische Site in docs/: die Gallery-HTML-Dateien werden kopiert und ihre
API-Aufrufe auf vorbereitete JSON-Dateien umgebogen (relative Pfade, laeuft
daher auch unter einem Sub-Pfad wie /For3Dsuite/). Das Studio entfaellt --
Upload/Verarbeitung brauchen das Backend (siehe platform/README.md).

  python platform/dev/export_static.py
"""
import json
import shutil
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
MAX_PANO_W = 4096   # Web-Viewer braucht kein 8k; haelt docs/ schlank + pushbar
JPEG_Q = 82

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
GALLERY = REPO / "platform" / "web" / "gallery"
OUT = REPO / "docs"


def dataset_tags(s):
    """Welche Datenarten die Szene bietet -- fuer die Extrazeile je Galerie-Karte.

    Rein aus dem Manifest abgeleitet, damit neue Szenen automatisch die richtigen
    Marken bekommen. Reihenfolge = Anzeigereihenfolge (Rohdaten zuerst, daraus
    Abgeleitetes danach).
    """
    markers = s.get("markers") or []
    attr_keys = {k for m in markers for k in (m.get("attributes") or {})}
    tags = []
    if s.get("pano_url"):
        tags.append("RGB-Panorama")
    if s.get("video_url"):
        tags.append("Video-Rundgang")
    if s.get("splat"):
        tags.append("Gaussian Splatting")
    if s.get("pointcloud"):
        tags.append("LiDAR-Punktwolke")
    if any(k.startswith("QSM_") for k in attr_keys):
        tags.append("QSM")
    if any("ExG" in k or k == "Vitalitaet" for k in attr_keys):
        tags.append("RGB-Bildanalyse")
    if s.get("canopy"):
        tags.append("Kronenanalyse (LAI)")
    if any(m.get("prognosis") for m in markers):
        tags.append("Wachstumsprognose")
    if s.get("hedge_colorings"):
        tags += ["NDVI (CIR)", "Arteignung"]
    if markers:
        tags.append("Inventur-Marker")
    return tags


def load_publish_list():
    """Kuratierung aus publish.json: (Menge der IDs | None, Liste fuer Notizen).

    None heisst 'keine Datei da' -- dann wird wie frueher alles exportiert.
    """
    pf = Path(__file__).with_name("publish.json")
    if not pf.is_file():
        return None, []
    ids = set(json.loads(pf.read_text(encoding="utf-8"))["publish"])
    return ids, []


def patch(text, replacements, name):
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"Patch-Anker nicht gefunden in {name}: {old!r}")
        text = text.replace(old, new)
    return text


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    (OUT / ".nojekyll").write_text("")

    # ---- HTML/JS kopieren und API-Aufrufe auf statische JSONs umbiegen ----
    index = patch((GALLERY / "index.html").read_text(encoding="utf-8"), [
        ("fetch('/api/scenes')", "fetch('data/scenes.json')"),
        ('Im <a href="/admin/">Studio</a> Bilder hochladen.', "&nbsp;"),
        ('— <a href="/admin/">Studio (Login)</a>',
         '— <a href="https://github.com/anayana/For3Dsuite">Quellcode auf GitHub</a>'),
    ], "index.html")
    (OUT / "index.html").write_text(index, encoding="utf-8")

    scene = patch((GALLERY / "scene.html").read_text(encoding="utf-8"), [
        ("fetch('/api/scenes/' + encodeURIComponent(sid))",
         "fetch('data/scene-' + encodeURIComponent(sid) + '.json')"),
    ], "scene.html")
    (OUT / "scene.html").write_text(scene, encoding="utf-8")

    walk = patch((GALLERY / "walk.html").read_text(encoding="utf-8"), [
        ("(await fetch('/api/scenes/' + encodeURIComponent(id))).json()",
         "(await fetch('data/scene-' + encodeURIComponent(id) + '.json')).json()"),
    ], "walk.html")
    (OUT / "walk.html").write_text(walk, encoding="utf-8")

    splat = patch((GALLERY / "splat.html").read_text(encoding="utf-8"), [
        ("fetch('/api/scenes/' + encodeURIComponent(sid))",
         "fetch('data/scene-' + encodeURIComponent(sid) + '.json')"),
    ], "splat.html")
    (OUT / "splat.html").write_text(splat, encoding="utf-8")

    shutil.copyfile(GALLERY / "cloudviewer.js", OUT / "cloudviewer.js")

    # ---- Szenen-JSONs + Medien ----
    publish, held = load_publish_list()
    listing = []
    for sj in sorted(MEDIA.glob("scenes/*/scene.json")):
        s = json.loads(sj.read_text(encoding="utf-8"))
        sid = s["id"]
        if publish is not None and sid not in publish:
            held.append(sid)
            continue
        src = sj.parent
        dst = OUT / "media" / "scenes" / sid
        dst.mkdir(parents=True)
        for f in src.iterdir():   # alle Medien (Panos, Varianten, Wolken, Video, QSM, Splat)
            if not (f.is_file() and f.suffix in (".jpg", ".bin", ".mp4", ".ply")):
                continue
            # Panos auf MAX_PANO_W begrenzen (Thumbs/kleine Bilder bleiben unberuehrt)
            if f.suffix == ".jpg" and f.name != "thumb.jpg":
                with Image.open(f) as im:
                    if im.width > MAX_PANO_W:
                        h = round(im.height * MAX_PANO_W / im.width)
                        im.convert("RGB").resize((MAX_PANO_W, h), Image.LANCZOS) \
                          .save(dst / f.name, quality=JPEG_Q)
                        continue
            shutil.copyfile(f, dst / f.name)

        rel = f"media/scenes/{sid}"
        # Panorama nur setzen, wenn vorhanden (wolken-only-Szenen wie TreeScope
        # haben keins -> pano_url = null, Viewer startet direkt in 3D)
        s["pano_url"] = f"{rel}/pano.jpg" if s.get("pano") and (src / "pano.jpg").is_file() else None
        s["thumb_url"] = f"{rel}/thumb.jpg" if (src / "thumb.jpg").is_file() else None
        if s.get("video") and (src / Path(s["video"]).name).is_file():
            s["video_url"] = f"{rel}/{Path(s['video']).name}"
        for v in s.get("variants") or []:
            v["pano_url"] = rel + "/" + v["pano"].rsplit("/", 1)[-1]
        can = s.get("canopy")
        if can and can.get("fisheye") and (src / "hemi.jpg").is_file():
            can["fisheye_url"] = f"{rel}/hemi.jpg"
        qsm = s.get("qsm")
        if qsm and (src / "qsm.bin").is_file():
            qsm["bin_url"] = f"{rel}/qsm.bin"
        elif qsm:
            s["qsm"] = None
        sp = s.get("splat")
        if sp and sp.get("file") and (src / sp["file"]).is_file():
            sp["url"] = f"{rel}/{sp['file']}"      # lokal im Repo
        elif sp and sp.get("url"):
            pass                                    # extern gehostet (Release/CDN)
        elif sp:
            s["splat"] = None
        pc = s.get("pointcloud")
        if pc and (src / pc["bin"].rsplit("/", 1)[-1]).is_file():
            pc["bin_url"] = rel + "/" + pc["bin"].rsplit("/", 1)[-1]
            for lv in pc.get("levels") or []:
                lv["bin_url"] = rel + "/" + lv["bin"].rsplit("/", 1)[-1]
                # ITCD-Einfaerbung (segment_itcd.py), falls erzeugt
                seg = lv.get("bin_itcd")
                if seg and (src / seg.rsplit("/", 1)[-1]).is_file():
                    lv["bin_itcd_url"] = rel + "/" + seg.rsplit("/", 1)[-1]
        elif pc:
            s["pointcloud"] = None
        (OUT / "data" / f"scene-{sid}.json").write_text(
            json.dumps(s, ensure_ascii=False), encoding="utf-8")

        entry = {
            "id": sid, "title": s.get("title"),
            "description": s.get("description", ""),
            "created": s.get("created"),
            "thumb_url": s["thumb_url"],
            "markers": len(s.get("markers", [])),
            "source_type": (s.get("source") or {}).get("type"),
            "has_3d": bool(s.get("pointcloud")),
            "kind": "walk" if s.get("video") else "splat" if s.get("splat") else "scene",
            "datasets": dataset_tags(s),
        }
        # Koordinate fuer die Uebersichtskarte (source.gps, sonst metadata.geometry)
        gps = (s.get("source") or {}).get("gps") or {}
        geom = ((s.get("metadata") or {}).get("geometry") or {}).get("coordinates")
        if gps.get("lat") is not None:
            entry["lat"], entry["lon"] = gps["lat"], gps["lon"]
        elif geom:
            entry["lon"], entry["lat"] = geom[0], geom[1]
        listing.append(entry)
    listing.sort(key=lambda x: x.get("created") or "", reverse=True)
    (OUT / "data" / "scenes.json").write_text(
        json.dumps(listing, ensure_ascii=False), encoding="utf-8")

    if publish is not None:
        fehlt = publish - {e["id"] for e in listing}
        if fehlt:
            print(f"!! in publish.json gelistet, aber nicht gebaut: {sorted(fehlt)}")
        print(f"   zurueckgehalten ({len(held)}): {', '.join(sorted(held))}")

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"-> {OUT}  ({len(listing)} Szenen, {total/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
