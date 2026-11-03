"""eval_splat_geometry.py an einer kuenstlichen Ebene mit bekanntem Versatz."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# CI installiert nur numpy + pytest (tests.yml) -> ohne plyfile/scipy ueberspringen
plyfile = pytest.importorskip("plyfile")
pytest.importorskip("scipy")
PlyData, PlyElement = plyfile.PlyData, plyfile.PlyElement

REPO = Path(__file__).resolve().parents[1]


def test_offset_plane(tmp_path):
    g = np.stack(np.meshgrid(np.arange(0, 2, 0.01), np.arange(0, 1, 0.01)), -1).reshape(-1, 2)
    ref = np.c_[g, np.zeros(len(g))]
    lab = np.where(g[:, 0] < 1, 1, 2)
    (tmp_path / "ref.txt").write_text("//X Y Z R G B label Nx Ny Nz\n" + "".join(
        f"{x:.3f} {y:.3f} {z:.3f} 0 0 0 {l}.000000 0 0 1\n" for (x, y, z), l in zip(ref, lab)))
    spl = ref[lab == 1] + [0, 0, 0.03]                 # nur Label 1 abgedeckt, 3 cm hoeher
    el = np.empty(len(spl) + 1, dtype=[(c, "f4") for c in ("x", "y", "z", "opacity")])
    el["x"][:-1], el["y"][:-1], el["z"][:-1] = spl.T
    el["opacity"][:-1] = 5.0                           # sigmoid ~ 1
    el[-1] = (0.5, 0.5, 0.0, -5.0)                     # durchsichtig -> wird verworfen
    PlyData([PlyElement.describe(el, "vertex")]).write(str(tmp_path / "m.ply"))
    subprocess.run([sys.executable, str(REPO / "scripts" / "eval_splat_geometry.py"),
                    str(tmp_path / "m.ply"), str(tmp_path / "ref.txt"),
                    "--out", str(tmp_path / "r.json")], check=True, capture_output=True)
    r = json.loads((tmp_path / "r.json").read_text())
    assert r["splats_used"] == len(spl)
    l1, l2 = r["per_label"]["1"], r["per_label"]["2"]
    assert abs(l1["genauigkeit"]["median_m"] - 0.03) < 1e-4
    assert l1["vollstaendigkeit"]["2cm"] == 0.0 and l1["vollstaendigkeit"]["5cm"] == 1.0
    assert l2["vollstaendigkeit"]["10cm"] < 0.15
