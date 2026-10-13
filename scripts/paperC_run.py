#!/usr/bin/env python3
"""paperC_run.py -- Standpunkt-Pool einer Szene Leg fuer Leg simulieren und packen.

Ein HELIOS-Lauf ueber alle 40 Legs haelt zu viel im Speicher (bad_alloc bei 15 GB)
und braucht ~10 GB Plattenplatz fuer die Textausgabe. Daher: je Leg ein eigenes
Survey, rechnen, sofort aufs Brusthoehenband packen (paperC_pack.py), Rohdaten
loeschen. Bereits gepackte Legs werden uebersprungen (Wiederaufnahme).

  python scripts/paperC_run.py data/paperC/S1b
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from paperC_pack import pack                               # noqa: E402

PYHELIOS = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "pyhelios"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    args = ap.parse_args()
    sc = Path(args.scene)
    survey = (sc / "survey.xml").read_text()
    legs = re.findall(r"    <leg>.*?</leg>\n", survey)
    (sc / "legs").mkdir(exist_ok=True)
    for k, leg in enumerate(legs):
        dest = sc / "legs" / f"leg{k:03d}.npz"
        if dest.exists():
            continue
        t0 = time.time()
        one = sc / f"survey_leg{k:03d}.xml"
        one.write_text(survey.replace("".join(legs), leg))
        out = sc / f"out_leg{k:03d}"
        subprocess.run([sys.executable, str(REPO / "scripts" / "helios_run.py"), str(one), str(out),
                        "--assets", str(PYHELIOS), "--assets", str(sc)], check=True, stdout=subprocess.DEVNULL)
        f = next(out.rglob("leg000_points.xyz"))
        n = pack(f, dest)
        shutil.rmtree(out); one.unlink()
        print(f"leg {k:3d}: {n} Punkte im Band, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
