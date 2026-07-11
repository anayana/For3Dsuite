#!/usr/bin/env python3
"""Befuellt den lokalen Dev-Storage (platform/dev-data/media) mit Demo-Szenen
aus den vorhandenen Pipeline-Ausgaben in output/.

  python platform/dev/seed_demo.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
sys.path.insert(0, str(REPO / "scripts"))
from pano_variants import make_variants  # noqa: E402


def publish(sid, pano_src, title, description, source, markers, max_w=8192,
            pointcloud=None):
    dest = MEDIA / "scenes" / sid
    dest.mkdir(parents=True, exist_ok=True)
    with Image.open(pano_src) as im:
        im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, max_w // 2), Image.LANCZOS)
        w, h = im.size
        im.save(dest / "pano.jpg", quality=90)
        im.resize((640, 320), Image.LANCZOS).save(dest / "thumb.jpg", quality=85)
    # Drei Farbstufen (natur ersetzt pano.jpg)
    variants = [{"id": vid, "label": label, "pano": f"scenes/{sid}/{name}"}
                for vid, label, name in make_variants(dest / "pano.jpg", dest)]
    # Punktwolken-Stufen (aus pointcloud_web.py) uebernehmen: lite = Default
    if pointcloud is None:
        levels = []
        for lid, label, fname in (("lite", "Ausgedünnt", "cloud_lite.bin"),
                                  ("full", "Voll", "cloud.bin")):
            mj = dest / Path(fname).with_suffix(".json").name
            if mj.is_file():
                meta = json.loads(mj.read_text())
                levels.append({"id": lid, "label": label,
                               "bin": f"scenes/{sid}/{fname}", "count": meta["count"],
                               "bbox_min": meta["bbox_min"], "bbox_max": meta["bbox_max"]})
        if levels:
            pointcloud = {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                          "levels": levels}
    scene = {
        "id": sid, "title": title, "description": description,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": f"scenes/{sid}/pano.jpg", "thumb": f"scenes/{sid}/thumb.jpg",
        "width": w, "height": h, "variants": variants,
        "source": source, "pointcloud": pointcloud, "markers": markers,
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"Szene '{sid}' veroeffentlicht ({w}x{h}, {len(markers)} Marker)")


def demo_marker(mid, label, yaw, pitch, attrs, xyz=None):
    return {"id": mid, "label": label, "yaw": yaw, "pitch": pitch, "xyz": xyz,
            "attributes": {**attrs, "Hinweis": "Demo-Werte (nicht gemessen)"},
            "demo": True}


def markers_from_csv(csv_path, origin):
    """Reale Inventur-Marker aus einer trees_*.csv (inventory_from_cloud.py)."""
    import subprocess
    import sys
    tmp = REPO / "platform" / "dev-data" / "_markers_tmp.json"
    subprocess.run([sys.executable, str(REPO / "scripts" / "markers_from_xyz.py"),
                    str(csv_path), "--origin", *map(str, origin), "--out", str(tmp)],
                   check=True)
    markers = json.loads(tmp.read_text(encoding="utf-8"))
    tmp.unlink()
    return markers


RENON_ORIGIN = [31.803, -4.557, 3.858]
RENON_TREES = REPO / "data" / "renon" / "trees_setup001.csv"
renon_markers = (markers_from_csv(RENON_TREES, RENON_ORIGIN) if RENON_TREES.is_file()
                 else [demo_marker("t001", "Fichte A", 15.0, 4.0,
                       {"Baumart": "Picea abies", "BHD_cm": 48.2, "Hoehe_m": 31.5})])


publish(
    "renon-setup01",
    REPO / "output" / "renon_setup01" / "pano_equirect.jpg",
    "Renon / ICOS IT-Ren — Setup 01",
    "Ungleichaltriger ~200-jaehriger Fichtenbestand, Renon (Suedtirol), 1735 m. "
    "Rekonstruiert aus den 6 Pinhole-Kameras eines Leica BLK360 (E57, Zenodo "
    "10.5281/zenodo.17186174, CC-BY-4.0) per direkter sphaerischer Reprojektion.",
    {"type": "e57", "origin_xyz": RENON_ORIGIN},
    renon_markers,
)

publish(
    "hechingen-site3",
    REPO / "output" / "scene01" / "pano_v1_natural.jpg",
    "Hechingen — Duerrstaendige Baeume (Site 3)",
    "360-Grad-Panorama aus 6 Fisheye-Einzelbildern (Sony ARW), gestitcht mit der "
    "Hugin-CLI-Pipeline; Nadir retuschiert, Variante 'natural'.",
    {"type": "fisheye", "origin_xyz": None},
    [],
)
