#!/usr/bin/env python3
"""stitch_hugin.py -- Bildsatz -> Equirect-Panorama ueber die Hugin-Kommandozeile.

Der Stitching-Zweig der Pipeline (Paper-Konzept 3.1/4): Aufnahmen OHNE bekannte
Pose werden ueber Kontrollpunkte registriert. Bewusst wird hier NICHTS aus der
bekannten Geometrie verraten -- ausser dem Bildfeld und dem Objektivtyp, die ein
Anwender auch aus dem Datenblatt seines Objektivs kennt. Alles andere (Yaw, Pitch,
Roll, Verzeichnung) schaetzt Hugin selbst. Nur so misst der Vergleich gegen den
posen-basierten Zweig etwas Sinnvolles.

Ablauf (Hugin 2024, alle Schritte ohne GUI):
  pto_gen        Projekt anlegen, Objektivtyp + FOV setzen
  cpfind         Kontrollpunkte suchen (--multirow fuer Ringaufnahmen)
  cpclean        Ausreisser unter den Kontrollpunkten entfernen
  autooptimiser  Position, Objektiv und Photometrie ausgleichen
  pano_modify    Ausgabeprojektion equirektangular, Leinwand + FOV festlegen
  nona/enblend   Remappen und ueberblenden

  python scripts/stitch_hugin.py <bilderverzeichnis> <out.jpg> \\
      --fov 180 --lens 2 --width 2048
"""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HUGIN_DEFAULT = r"C:\Program Files\Hugin\bin"
# Hugin-Objektivtypen: 0 rectilinear, 1 zylindrisch, 2 Kreis-Fisheye,
# 3 Vollformat-Fisheye, 4 equirektangular
LENS_NAMES = {0: "rectilinear", 1: "zylindrisch", 2: "Kreis-Fisheye",
              3: "Vollformat-Fisheye", 4: "equirektangular"}


def tool(bindir, name):
    exe = Path(bindir) / (name + (".exe" if os.name == "nt" else ""))
    if not exe.is_file():
        raise SystemExit(f"Hugin-Werkzeug fehlt: {exe}")
    return str(exe)


def run(cmd, cwd, log):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    dt = time.time() - t0
    log.append({"schritt": Path(cmd[0]).stem, "sekunden": round(dt, 1),
                "code": p.returncode})
    print(f"  {Path(cmd[0]).stem:14} {dt:6.1f}s  (exit {p.returncode})", flush=True)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-6:]
        raise SystemExit(f"{Path(cmd[0]).stem} fehlgeschlagen:\n  "
                         + "\n  ".join(tail))
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("imgdir")
    ap.add_argument("out")
    ap.add_argument("--fov", type=float, default=180.0, help="Bildfeld der Aufnahmen")
    ap.add_argument("--lens", type=int, default=2, choices=sorted(LENS_NAMES),
                    help="Hugin-Objektivtyp der EINGANGSbilder")
    ap.add_argument("--width", type=int, default=2048, help="Panoramabreite")
    ap.add_argument("--hugin-bin", default=os.environ.get("HUGIN_BIN", HUGIN_DEFAULT))
    ap.add_argument("--keep", action="store_true", help="Arbeitsdateien behalten")
    args = ap.parse_args()

    src = Path(args.imgdir).resolve()
    imgs = sorted(p.name for p in src.glob("*.jpg"))
    if len(imgs) < 2:
        raise SystemExit(f"Mindestens zwei Bilder noetig, gefunden: {len(imgs)}")
    work = src / "_hugin"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    for n in imgs:
        shutil.copy2(src / n, work / n)

    T = lambda n: tool(args.hugin_bin, n)      # noqa: E731
    log, t0 = [], time.time()
    print(f"Stitching {len(imgs)} Bilder ({LENS_NAMES[args.lens]}, FOV {args.fov:g}°)")

    run([T("pto_gen"), "-o", "p.pto", "-p", str(args.lens), "-f", str(args.fov)]
        + imgs, work, log)
    run([T("cpfind"), "--multirow", "-o", "p.pto", "p.pto"], work, log)
    run([T("cpclean"), "-o", "p.pto", "p.pto"], work, log)
    run([T("autooptimiser"), "-a", "-m", "-l", "-s", "-o", "p.pto", "p.pto"], work, log)
    run([T("pano_modify"), "-p", "2", "--fov=360x180",
         f"--canvas={args.width}x{args.width // 2}", "-o", "p.pto", "p.pto"], work, log)
    run([T("nona"), "-m", "TIFF_m", "-o", "rem", "p.pto"], work, log)

    tiles = sorted(str(p.name) for p in work.glob("rem*.tif"))
    if not tiles:
        raise SystemExit("nona hat keine Kacheln geschrieben")
    run([T("enblend"), "-o", "pano.tif"] + tiles, work, log)

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(work / "pano.tif").convert("RGB")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=92)

    # Wie viele Kontrollpunkte hat Hugin gefunden? Das ist die Kennzahl dafuer,
    # wie gut sich die Aufnahmen ueberhaupt registrieren liessen.
    pto = (work / "p.pto").read_text(errors="replace").splitlines()
    n_cp = sum(1 for r in pto if r.startswith("c "))
    total = time.time() - t0
    meta = {"bilder": len(imgs), "objektiv": LENS_NAMES[args.lens], "fov_deg": args.fov,
            "kontrollpunkte": n_cp, "sekunden_gesamt": round(total, 1),
            "schritte": log, "ausgabe": [im.width, im.height]}
    Path(str(out) + ".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"-> {out}  {im.width}x{im.height}  {n_cp} Kontrollpunkte, "
          f"{total:.0f}s gesamt")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
