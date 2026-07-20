#!/usr/bin/env python3
"""seed_tour.py -- Renon-Mehrstandpunkt-Tour als Plattform-Szene (kind=tour).

Uebernimmt die von build_scene.py + stand_inventory.py erzeugten Tour-Assets
(Panoramen, Punktwolken, Standpunkt-Manifest, Bestandesinventur) in den
Plattform-Media-Store und baut ein scene.json mit standpoints[] + stand + trees.

  python platform/dev/seed_tour.py
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
VIEWER = REPO / "viewer" / "data"
MEDIA = REPO / "platform" / "dev-data" / "media"
SID = "renon-tour"


def main():
    dest = MEDIA / "scenes" / SID
    dest.mkdir(parents=True, exist_ok=True)
    scene_manifest = json.loads((VIEWER / "renon_scene.json").read_text(encoding="utf-8"))
    inv = json.loads((VIEWER / "renon_stand.json").read_text(encoding="utf-8"))

    standpoints = []
    for nd in scene_manifest["nodes"]:
        for rel in (nd["pano"], nd["points"]):
            src = VIEWER / rel
            if not src.is_file():
                raise SystemExit(f"fehlt: {src} (erst build_scene.py laufen lassen)")
            shutil.copyfile(src, dest / rel)
        standpoints.append({
            "id": nd["id"], "name": nd["name"], "pos": nd["pos"],
            "pano": f"scenes/{SID}/{nd['pano']}",
            "points": f"scenes/{SID}/{nd['points']}",
            "n": nd["n"],
        })

    # Thumbnail aus dem ersten Panorama
    with Image.open(VIEWER / scene_manifest["nodes"][0]["pano"]) as im:
        w, h = im.size
        im.convert("RGB").crop((0, int(h*0.32), w, int(h*0.72))).resize((640, 320)) \
          .save(dest / "thumb.jpg", quality=85)

    q = inv["stand"]["quantitativ"]
    scene = {
        "id": SID,
        "title": "Renon / ICOS IT-Ren — begehbare Tour (4 Standpunkte)",
        "description": f"Vier co-registrierte TLS-Standpunkte (LiDAR + RGB-Panorama), "
                       f"frei begehbar. Bestandeswerte aus {inv['stand']['n_standpunkte']} "
                       f"zusammengeführten Scans berechnet: {q['Stammzahl_N_ha']} Stämme/ha, "
                       f"G {q['Grundflaeche_m2_ha']} m²/ha, Vorrat {q['Vorrat_m3_ha']} m³/ha.",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "tour",
        "pano": None, "thumb": f"scenes/{SID}/thumb.jpg", "video": None,
        "width": None, "height": None, "variants": [], "pointcloud": None,
        "source": {"type": "e57-tour", "n_standpunkte": inv["stand"]["n_standpunkte"],
                   "ref_origin_e57": inv["ref_origin_e57"]},
        "standpoints": standpoints,
        "stand": inv["stand"],
        "trees": inv["trees"],
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    mb = sum(f.stat().st_size for f in dest.iterdir()) / 1e6
    print(f"Szene '{SID}' veroeffentlicht: {len(standpoints)} Standpunkte, "
          f"{len(inv['trees'])} Baeume, {mb:.0f} MB")


if __name__ == "__main__":
    main()
