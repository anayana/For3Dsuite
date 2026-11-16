#!/usr/bin/env python3
"""publish_scene.py -- EINE Szene aus platform/dev-data nach docs/ uebernehmen.

Fuer die Cloud (und alle Faelle, in denen nur diese eine Szene lokal gebaut
wurde): export_static.py darf dort nur mit --html-only laufen, weil der
Vollexport docs/ loescht. Dieses Skript fasst ausschliesslich an:

  * docs/media/scenes/<id>/          (neu geschrieben)
  * docs/data/scene-<id>.json        (neu geschrieben)
  * docs/data/scenes.json            (Eintrag ersetzt bzw. vorne eingefuegt)

Alle anderen Szenen in docs/ bleiben unangetastet. Die Umrechnung (Medien-URLs,
Galerie-Eintrag, Daten-Marken) ist dieselbe wie im Vollexport (export_scene).

  python platform/dev/publish_scene.py qforest-robsoncreek
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_static import MEDIA, OUT, REPO, export_scene          # noqa: E402


def main():
    ids = sys.argv[1:]
    if not ids:
        raise SystemExit(__doc__)
    listing_path = OUT / "data" / "scenes.json"
    listing = json.loads(listing_path.read_text(encoding="utf-8"))
    for sid in ids:
        sj = MEDIA / "scenes" / sid / "scene.json"
        if not sj.is_file():
            raise SystemExit(f"Abbruch: {sj.relative_to(REPO)} fehlt -- erst den Seed laufen lassen")
        entry = export_scene(sj)
        have = [e["id"] for e in listing]
        if sid in have:
            listing[have.index(sid)] = entry
        else:
            listing.insert(0, entry)
        print(f"-> {sid}: docs/media/scenes/{sid}/ + docs/data/scene-{sid}.json")
    listing_path.write_text(json.dumps(listing, ensure_ascii=False), encoding="utf-8")
    print(f"-> docs/data/scenes.json ({len(listing)} Szenen)")


if __name__ == "__main__":
    main()
