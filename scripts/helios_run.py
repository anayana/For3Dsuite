#!/usr/bin/env python3
"""helios_run.py -- HELIOS++-Survey ueber pyhelios rechnen (statt der stummen CLI).

Auf Windows gibt die helios.exe nichts aus und schreibt keine Dateien; der
zuverlaessige Weg ist die pyhelios-Bindung. MUSS mit dem Python der helios-Env
laufen, z.B.:

  ~/mm/root/envs/helios/python.exe scripts/helios_run.py \
      data/helios/survey.xml data/helios/output --assets <pyhelios-dir> --assets data/helios

Schreibt je Standpunkt eine leg*_points.xyz -- Eingang fuer helios_import.py /
occlusion_map.py.
"""
import argparse
import sys
import time

from pyhelios import SimulationBuilder
import pyhelios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("survey")
    ap.add_argument("outdir")
    ap.add_argument("--assets", action="append", default=[])
    args = ap.parse_args()

    pyhelios.loggingQuiet()
    assets = args.assets or ["."]
    # SimulationBuilder(surveyPath, assetsDir_list, outputDir)
    b = SimulationBuilder(args.survey, assets, args.outdir)
    b.setLasOutput(False)          # schlichtes ASCII-XYZ je Leg
    b.setZipOutput(False)
    b.setExportToFile(True)
    b.setRebuildScene(True)
    b.setNumThreads(0)             # alle Kerne
    b.setCallbackFrequency(0)
    sim = b.build()

    sim.start()
    t0 = time.time()
    while sim.isStarted() and not sim.isFinished():
        time.sleep(2)
        print(f"  ... laeuft ({time.time()-t0:.0f}s)", flush=True)
    sim.join()
    print(f"fertig nach {time.time()-t0:.0f}s -> {args.outdir}", flush=True)


if __name__ == "__main__":
    main()
