#!/usr/bin/env python3
"""migrate_markers.py -- Marker in Szenen-JSONs auf das einheitliche Schema heben.

Standard ist ein Probelauf: zeigt je Datei, wie viele Marker umgestellt wuerden,
und prueft, dass keiner verloren geht und jede Position gleich bleibt.
Geschrieben wird nur mit --write.

  # auf dem Notebook (Quelle):
  python platform/dev/migrate_markers.py platform/dev-data/media/scenes/*/scene.json
  # Ausgabe in docs/ (nur wenn noetig -- dann auf dem Notebook zurueckspielen!):
  python platform/dev/migrate_markers.py docs/data/scene-*.json

Die Viewer lesen alte und neue Marker gleichermassen (marker-card.js); die
Migration ist also nicht noetig, um etwas anzuzeigen. --strip-legacy entfernt
die alten Felder erst, wenn Studio-Editor und API (Aufgaben B/C) das neue
Schema sprechen -- vorher wuerde ein Speichern im Studio die Anker verwerfen.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from marker_schema import anchor_view, normalize_marker  # noqa: E402


def migrate_file(path, strip_legacy=False, write=False):
    s = json.loads(path.read_text(encoding="utf-8"))
    old = s.get("markers") or []
    new = [normalize_marker(m, strip_legacy=strip_legacy) for m in old]
    if len(new) != len(old):
        raise SystemExit(f"{path}: Markerzahl {len(old)} -> {len(new)}")
    for a, b in zip(old, new):
        if anchor_view(a) != anchor_view(b):
            raise SystemExit(f"{path}: Position von Marker {a.get('id')!r} veraendert")
    changed = sum(a != b for a, b in zip(old, new))
    if write and changed:
        s["markers"] = new
        # scene.json wie die Seed-Skripte (indent=2), docs/data kompakt wie der Export
        indent = 2 if path.name == "scene.json" else None
        path.write_text(json.dumps(s, ensure_ascii=False, indent=indent), encoding="utf-8")
    return len(old), changed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", type=Path, help="scene.json bzw. scene-*.json")
    ap.add_argument("--write", action="store_true", help="Aenderungen schreiben")
    ap.add_argument("--strip-legacy", action="store_true",
                    help="alte Felder (yaw/pitch/pos/image/...) entfernen")
    a = ap.parse_args()
    for f in a.files:
        n, changed = migrate_file(f, a.strip_legacy, a.write)
        verb = "umgestellt" if a.write else "wuerden umgestellt"
        print(f"{str(f):60s} {n:4d} Marker, {changed:4d} {verb}")
    if not a.write:
        print("Probelauf -- nichts geschrieben (--write zum Schreiben).")


if __name__ == "__main__":
    main()
