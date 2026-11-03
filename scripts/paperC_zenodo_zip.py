#!/usr/bin/env python3
"""paperC_zenodo_zip.py -- schlankes Zenodo-Archiv fuer Paper C: nur Rechenskripte,
Ergebnistabellen, README und Lizenz (keine Abbildungen, keine Fremddaten).

  python scripts/paperC_zenodo_zip.py out/paperC_code_results.zip
"""
import glob
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P = REPO / "Paper_ODT" / "Forst_Benchmark_Paper"
SCRIPTS = ["arc_error_mc.py", "arc_error_mc_real.py", "dbh_methods.py", "inventory_from_cloud.py",
           "validate_detection_gt.py", "helios_run.py", "ext_band.py",
           "paperC_scene.py", "paperC_run.py", "paperC_pack.py", "paperC_eval.py", "paperC_real.py",
           "paperC_laut.py", "paperC_3dfin_real.py", "paperC_bootstrap.py", "paperC_figures.py"]


def main():
    out = Path(sys.argv[1]); out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(P / "zenodo" / "README.md", "paperC/README.md")
        z.write(REPO / "LICENSE", "paperC/LICENSE")
        for s in SCRIPTS:
            z.write(REPO / "scripts" / s, f"paperC/scripts/{s}")
        for f in sorted(glob.glob(str(P / "results" / "**" / "*.csv"), recursive=True)):
            rel = Path(f).relative_to(P)
            if rel.parts[1] == "recompute":
                continue
            z.write(f, f"paperC/{rel.as_posix()}")
        print(out, len(z.namelist()), "Dateien")


if __name__ == "__main__":
    main()
