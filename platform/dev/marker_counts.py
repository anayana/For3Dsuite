#!/usr/bin/env python3
"""marker_counts.py -- Markerzahl je Szene in docs/data/ (Vorher/Nachher-Vergleich).

Vor und nach jedem Export bzw. jeder Marker-Aenderung laufen lassen
(CLAUDE_CODE_UEBERGABE.md, Abschn. 2 + 6):

  python platform/dev/marker_counts.py                       # nur anzeigen
  python platform/dev/marker_counts.py --save vorher.json    # Stand sichern
  python platform/dev/marker_counts.py --compare vorher.json # vergleichen

Mit --compare endet das Skript mit Code 1, sobald eine Szene Marker verloren
hat oder ganz fehlt -- taugt damit auch als Schranke in Skripten.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "docs" / "data"


def counts(data_dir=DATA):
    out = {}
    for f in sorted(Path(data_dir).glob("scene-*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        out[f.name] = len(s.get("markers") or [])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=str(DATA), help="Ordner mit scene-*.json")
    ap.add_argument("--save", metavar="JSON", help="Zahlen als JSON sichern")
    ap.add_argument("--compare", metavar="JSON", help="mit gesichertem Stand vergleichen")
    a = ap.parse_args()

    now = counts(a.data)
    if a.save:
        Path(a.save).write_text(json.dumps(now, indent=1), encoding="utf-8")
    if not a.compare:
        for name, n in now.items():
            print(f"{name:45s} {n:4d}")
        print(f"{'Summe':45s} {sum(now.values()):4d}")
        return

    before = json.loads(Path(a.compare).read_text(encoding="utf-8"))
    bad = False
    for name in sorted(set(before) | set(now)):
        b, n = before.get(name), now.get(name)
        flag = ""
        if n is None:
            flag, bad = "  !! Szene fehlt", True
        elif b is None:
            flag = "  (neu)"
        elif n < b:
            flag, bad = f"  !! {b - n} Marker weniger", True
        elif n > b:
            flag = f"  (+{n - b})"
        print(f"{name:45s} {'-' if b is None else b:>4} -> {'-' if n is None else n:>4}{flag}")
    print(f"{'Summe':45s} {sum(before.values()):4d} -> {sum(now.values()):4d}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
