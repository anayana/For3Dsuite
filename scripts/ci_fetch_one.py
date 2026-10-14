#!/usr/bin/env python3
"""ci_fetch_one.py -- fuer den CI-Workflow: Eintraege eines entfernten ZIPs per
Regex auswaehlen, per Range-Request holen und als Brusthoehenband speichern.

  python scripts/ci_fetch_one.py <zip-url> --match 'plot_06\\.laz$' --out extdata/segforests --name plot_06
"""
import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from zenodo_zip_pick import HttpFile                       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("--match", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--raw", default="raw")
    a = ap.parse_args()
    rx = re.compile(a.match, re.I)
    z = zipfile.ZipFile(HttpFile(a.url))
    hits = [i for i in z.infolist() if rx.search(i.filename) and not i.is_dir()]
    print("Treffer:", [(h.filename, round(h.file_size / 1e6, 1)) for h in hits], flush=True)
    if not hits:
        print("Inhalt:", [i.filename for i in z.infolist()][:80]); sys.exit(1)
    Path(a.raw).mkdir(exist_ok=True); Path(a.out).mkdir(parents=True, exist_ok=True)
    for k, h in enumerate(hits):
        dst = Path(a.raw) / Path(h.filename).name
        with z.open(h) as src, open(dst, "wb") as fh:
            while True:
                b = src.read(8 << 20)
                if not b:
                    break
                fh.write(b)
        print("geladen:", dst, flush=True)
        if dst.suffix.lower() in (".laz", ".las"):
            suffix = "" if len(hits) == 1 else f"_{k}"
            subprocess.run([sys.executable, str(REPO / "scripts" / "ext_band.py"), str(dst),
                            "--out", str(Path(a.out) / f"{a.name}{suffix}_band.npz")], check=True)
        else:
            (Path(a.out) / dst.name).write_bytes(dst.read_bytes())


if __name__ == "__main__":
    main()
