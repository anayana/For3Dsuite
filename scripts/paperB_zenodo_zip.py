#!/usr/bin/env python3
"""paperB_zenodo_zip.py -- schlankes Zenodo-Archiv fuer Paper B: Rechenskripte, Tests, Ergebnistabellen,
README und Lizenz (keine Fremddaten, keine Abbildungen).

  python scripts/paperB_zenodo_zip.py out/paperB_code_results.zip
"""
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P = REPO / "Paper_ODT" / "Heritage_Toolkit_Paper"
SCRIPTS = ["pellis_to_colmap.py", "pellis_posecheck.py", "train_pellis_runpod.sh", "pellis_batch.sh",
           "pellis_pod.sh", "eval_splat_geometry.py", "colmap_align.py", "splat_diag.py", "paperB_figures.py"]
TESTS = ["test_pellis_to_colmap.py", "test_eval_splat_geometry.py", "test_colmap_align.py"]


def main():
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(P / "zenodo" / "README.md", "paperB/README.md")
        z.write(REPO / "LICENSE", "paperB/LICENSE")
        for s in SCRIPTS:
            z.write(REPO / "scripts" / s, f"paperB/scripts/{s}")
        for t in TESTS:
            z.write(REPO / "tests" / t, f"paperB/tests/{t}")
        for f in sorted((P / "results").glob("*.csv")):
            z.write(f, f"paperB/results/{f.name}")
        print(out, len(z.namelist()), "Dateien")


if __name__ == "__main__":
    main()
