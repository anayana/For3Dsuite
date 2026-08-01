#!/usr/bin/env python3
"""make_usability_testdata.py -- Testdaten-Ordner fuer den Nutzbarkeitstest bauen.

Das Aufgabenblatt (Paper_ODT/.../Nutzbarkeitstest_Aufgabenblatt.md) verweist auf
drei Ordner auf dem Desktop der teilnehmenden Person. Dieses Skript stellt sie aus
den im Repo bzw. lokal vorhandenen Quellen zusammen, damit der Test ohne weitere
Vorbereitung starten kann.

  Testdaten/360/           ein fertiges Kugelpanorama      -> Aufgabe 1 (equirect)
  Testdaten/Einzelbilder/  mehrere ueberlappende Aufnahmen -> Aufgabe 2 (Stitching)
  Testdaten/Laserscan/     eine E57 mit Bildern und Posen  -> Aufgabe 3 (Reprojektion)

Bewusst NUR frei lizenzierte bzw. eigene freigegebene Quellen; die Herkunft jeder
Datei steht in einer QUELLEN.txt daneben. Die Bilder werden auf eine Groesse
gebracht, mit der der Test fluessig laeuft -- ein 20-Minuten-Stitching waere im
Nutzbarkeitstest ein Messfehler, kein Befund.

  python scripts/make_usability_testdata.py --out ~/Desktop/Testdaten
"""
import argparse
import shutil
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[1]
SCENES = REPO / "platform" / "dev-data" / "media" / "scenes"


def copy_scaled(src, dst, max_side, quality=92):
    with Image.open(src) as im:
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side), Image.LANCZOS)
        im.convert("RGB").save(dst, quality=quality)
    return dst.stat().st_size


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path.home() / "Desktop" / "Testdaten"))
    ap.add_argument("--pano-max", type=int, default=4096)
    ap.add_argument("--frame-max", type=int, default=1600,
                    help="Kantenlaenge der Einzelbilder -- klein halten, sonst "
                         "dauert das Stitching im Test zu lange")
    ap.add_argument("--frames", type=int, default=8, help="Anzahl Einzelbilder")
    args = ap.parse_args()

    out = Path(args.out)
    quellen = []
    for sub in ("360", "Einzelbilder", "Laserscan"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    # ---- Aufgabe 1: fertiges Kugelpanorama (Consumer-360, Wikimedia Commons) ----
    cand = [SCENES / "consumer360-chopfholz-wald" / "pano.jpg",
            SCENES / "consumer360-wilder-kaiser-wald" / "pano.jpg",
            SCENES / "consumer360-battery-point" / "pano.jpg"]
    src = next((c for c in cand if c.is_file()), None)
    if src:
        n = copy_scaled(src, out / "360" / "rundblick.jpg", args.pano_max)
        quellen.append(f"360/rundblick.jpg\n    aus Szene '{src.parent.name}' "
                       f"(Wikimedia Commons, CC BY-SA) -- {n/1e6:.1f} MB")
        print(f"  360/          rundblick.jpg ({n/1e6:.1f} MB) aus {src.parent.name}")
    else:
        print("  !! kein Consumer-360-Panorama gefunden")

    # ---- Aufgabe 2: mehrere ueberlappende Aufnahmen (PASSTA, CC-BY-4.0) ----
    passta = sorted((REPO / "data" / "passta" / "LunchRoom").glob("img*.jpg"))
    if not passta:
        passta = sorted((REPO / "data" / "_eval" / "real_passta").glob("*.jpg"))
    if passta:
        step = max(1, len(passta) // args.frames)
        sel = passta[::step][:args.frames]
        tot = 0
        for i, p in enumerate(sel, 1):
            tot += copy_scaled(p, out / "Einzelbilder" / f"aufnahme{i:02d}.jpg",
                               args.frame_max)
        quellen.append(f"Einzelbilder/ ({len(sel)} Stueck)\n    PASSTA LunchRoom, "
                       f"CC-BY-4.0, doi:10.5281/zenodo.19663081 -- "
                       f"auf {args.frame_max} px verkleinert")
        print(f"  Einzelbilder/ {len(sel)} Aufnahmen ({tot/1e6:.1f} MB) aus PASSTA")
    else:
        print("  !! keine Einzelaufnahmen gefunden (PASSTA nicht geladen?)")

    # ---- Aufgabe 3: Laserscan ----
    e57 = sorted((REPO / "data" / "Renon" / "e57").glob("*.e57"))
    if e57:
        dst = out / "Laserscan" / "laserscan.e57"
        shutil.copy2(e57[0], dst)
        quellen.append(f"Laserscan/laserscan.e57\n    Renon (ICOS IT-Ren), CC-BY-4.0 "
                       f"-- {dst.stat().st_size/1e6:.0f} MB")
        print(f"  Laserscan/    laserscan.e57 ({dst.stat().st_size/1e6:.0f} MB)")
    else:
        print("  !! keine E57 gefunden -- Aufgabe 3 entfaellt")

    (out / "QUELLEN.txt").write_text(
        "Testdaten fuer den Nutzbarkeitstest -- Herkunft und Lizenzen\n"
        "=========================================================\n\n"
        + "\n\n".join(quellen)
        + "\n\nAlle Dateien stammen aus frei lizenzierten oder eigenen freigegebenen\n"
          "Quellen und duerfen im Rahmen des Tests verwendet werden.\n",
        encoding="utf-8")
    print(f"\n-> {out}  (QUELLEN.txt mit Lizenzangaben beigelegt)")


if __name__ == "__main__":
    main()
