#!/usr/bin/env python3
"""run_3dfin_ini.py -- 3DFin mit einer mitgelieferten .ini auf einer Plot-Wolke.

SegmentedForests liefert zu jedem Plot die 3DFin-Konfiguration MIT, mit der die
Autoren ihn ausgewertet haben. Das ist selten und wertvoll: der Vergleich misst
dann das Verfahren, nicht meine Parameterwahl. Am Renon-Bestand musste ich die
Sektorenforderung selbst absenken und konnte nicht belegen, ob das noch 3DFin ist
oder schon Tuning -- hier stellt sich die Frage nicht.

  python scripts/run_3dfin_ini.py <wolke.npz|plot.laz> <plot.ini> <arbeitsverzeichnis>
      [--voxel 0.02]

Ausgabe: <arbeitsverzeichnis>/stems_3dfin.csv mit x,y,DBH_cm,Hoehe_m in den
Koordinaten der Eingabewolke.
"""
import argparse
import configparser
import sys
from pathlib import Path

import numpy as np


def load_cloud(path, voxel):
    p = Path(path)
    if p.suffix == ".npz":
        d = np.load(p)
        xyz = d["xyz"].astype(np.float64) + d["shift"]
    else:
        import laspy
        las = laspy.read(str(p))
        xyz = np.c_[las.x, las.y, las.z].astype(np.float64)
    if voxel:
        k = np.floor(xyz / voxel).astype(np.int64)
        _, keep = np.unique((k[:, 0] * 73856093) ^ (k[:, 1] * 19349663)
                            ^ (k[:, 2] * 83492791), return_index=True)
        xyz = xyz[keep]
    return xyz


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud")
    ap.add_argument("ini")
    ap.add_argument("workdir")
    ap.add_argument("--voxel", type=float, default=0.02)
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):        # 3DFin druckt Sonderzeichen
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    import laspy
    from three_d_fin.processing.configuration import FinConfiguration
    from three_d_fin.processing.standalone_processing import StandaloneLASProcessing

    xyz = load_cloud(args.cloud, args.voxel)
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    off = xyz.min(axis=0)
    hdr = laspy.LasHeader(point_format=3)
    hdr.offsets = [0.0, 0.0, 0.0]
    hdr.scales = [0.001] * 3
    las = laspy.LasData(hdr)
    loc = xyz - off
    las.x, las.y, las.z = loc[:, 0], loc[:, 1], loc[:, 2]
    plot_las = work / "plot.las"
    las.write(str(plot_las))
    print(f"{len(loc):,} Punkte -> {plot_las}")

    # Die .ini der Autoren laden -- aber der misc-Block darin zeigt auf deren
    # Rechner ("F:\\classification"). Der wird beim Laden validiert und bricht ab,
    # bevor man ihn ueberschreiben koennte. Also VOR dem Laden auf unsere Pfade
    # umbiegen. Die fachlichen Abschnitte (basic/advanced/expert -- Sektoren,
    # Punktzahlen, Bodenmodell) bleiben unangetastet; nur darum geht es hier.
    cp = configparser.ConfigParser()
    cp.read(args.ini)
    fach = {s: dict(cp[s]) for s in cp.sections() if s != "misc"}
    cp["misc"] = {"is_normalized": cp.get("misc", "is_normalized", fallback="False"),
                  "is_noisy": cp.get("misc", "is_noisy", fallback="False"),
                  "export_txt": "True",
                  "input_file": str(plot_las), "output_dir": str(work)}
    used = work / "used.ini"
    with open(used, "w") as f:
        cp.write(f)

    # From_config_file() ist hier NICHT brauchbar: es verwirft den misc-Block der
    # Datei in jedem Fall und setzt MiscParameters() mit Voreinstellungen ein --
    # input_file bleibt None und 3DFin stirbt spaeter mit AttributeError auf
    # 'NoneType'. Nachweis in der Quelle des Pakets (three_d_fin/processing/
    # configuration.py): der Zweig, der die Datei-misc behaelt, wird nur bei
    # config.misc IS None erreicht. Also fachliche Abschnitte von dort holen und
    # misc selbst bauen.
    from three_d_fin.processing.configuration import MiscParameters
    base = FinConfiguration.From_config_file(used, init_misc=True)
    cfg = FinConfiguration(
        basic=base.basic, advanced=base.advanced, expert=base.expert,
        misc=MiscParameters(
            is_normalized=cp.getboolean("misc", "is_normalized", fallback=False),
            is_noisy=cp.getboolean("misc", "is_noisy", fallback=False),
            export_txt=True, input_file=plot_las, output_dir=work))
    print(f"Konfiguration der Autoren uebernommen: {Path(args.ini).name} "
          f"({', '.join(f'{s}:{len(v)}' for s, v in fach.items())} Parameter)")

    StandaloneLASProcessing(cfg).process()

    # Spalten: Hoehe[m], BHD[m], x, y  (lokal zur LAS)
    dbh_f = work / "plot_dbh_and_heights.txt"
    if not dbh_f.exists():
        raise SystemExit(f"3DFin hat {dbh_f.name} nicht geschrieben")
    rows = [list(map(float, r.split())) for r in dbh_f.read_text().splitlines()
            if r.strip()]
    out = work / "stems_3dfin.csv"
    n_dbh = 0
    with open(out, "w", encoding="utf-8") as f:
        f.write("label,x,y,DBH_cm,Hoehe_m\n")
        for i, r in enumerate(rows, 1):
            d_cm = r[1] * 100.0
            if d_cm > 0:
                n_dbh += 1
            f.write(f"3dfin {i:03d},{r[2]+off[0]:.3f},{r[3]+off[1]:.3f},"
                    f"{d_cm:.1f},{r[0]:.1f}\n")
    print(f"-> {out}: {len(rows)} Detektionen, {n_dbh} mit akzeptiertem BHD")


if __name__ == "__main__":
    main()
