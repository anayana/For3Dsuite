#!/usr/bin/env python3
"""seed_walk.py -- FinnWoodlands-Waldspaziergang als Video-Szene einspielen.

Erwartet ein bereits gebautes walk.mp4 (scripts/build_walk.py) unter
platform/dev-data/media/scenes/finnwoods-walk/. Erzeugt Thumbnail + scene.json.

  python platform/dev/seed_walk.py
"""
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
FRAMES = REPO / "data" / "FinnWoodlands" / "rgb_all"
SID = "finnwoods-walk"


def main():
    dest = MEDIA / "scenes" / SID
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / "walk.mp4").is_file():
        raise SystemExit("walk.mp4 fehlt — zuerst scripts/build_walk.py laufen lassen")

    frames = sorted(glob.glob(str(FRAMES / "*.jpg")))
    mid = frames[len(frames) // 2] if frames else None
    if mid:
        with Image.open(mid) as im:
            im.convert("RGB").resize((640, 360), Image.LANCZOS).crop((0, 20, 640, 340)) \
              .resize((640, 320)).save(dest / "thumb.jpg", quality=85)

    scene = {
        "id": SID,
        "title": "FinnWoodlands — Waldspaziergang",
        "description": "Flüssiger Spaziergang entlang eines borealen Waldwegs "
                       "(FinnWoodlands, Tampere Univ., CC-BY). Aus 300 sequenziellen "
                       "Trail-Aufnahmen mit optischem-Fluss-Interpolation zu einer "
                       "durchgehenden Fahrt ohne Sprünge morphend berechnet.",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{SID}/thumb.jpg",
        "video": f"scenes/{SID}/walk.mp4",
        "width": 960, "height": 540, "variants": [],
        "source": {"type": "finnwoodlands",
                   "dataset": "FinnWoodlands (Tampere University)",
                   "url": "https://github.com/juanb09111/finnforest"},
        "pointcloud": None, "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    mb = (dest / "walk.mp4").stat().st_size / 1e6
    print(f"Szene '{SID}' veroeffentlicht (walk.mp4 {mb:.1f} MB)")


if __name__ == "__main__":
    main()
