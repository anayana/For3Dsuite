"""pellis_to_colmap.py: Lesen der Pellis-Kameraparameter und COLMAP-Ausgabe.

Testdaten: zwei Zeilen aus 5_CB (Pellis et al. 2025, Zenodo 14626611, CC BY 4.0).
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import pellis_to_colmap as p2c  # noqa: E402

INTERIOR = """K = [3054.45715 0 3872/2+7.11827; 0 3054.45715 2592/2-10.6372; 0 0 1];
ks = [-0.0821528 -0.00131558 0.0190999];
ps = [-5.76325e-05 0.000540635];
"""
EXTERIOR = """PhotoID,X,Y,K,OMEGA,PHI,KAPPA,R11,R12,R13,R21,R22,R23,R31,R32,R33,Orientation
5_CB_001,28.7480020583811,-4.94338174043841,6.91094169652336,7.52939655983178,57.5890402193028,-11.19930748481,0.525781736336641,-0.0840314468078544,-0.846458670982941,0.104100983179603,0.993984919930736,-0.0340141772108164,0.844225414824659,-0.0702331467162582,0.531366873324321,0
5_CB_040,-4.23073398236596,-0.471132755285636,-17.7378005216142,174.511231704865,-68.3025655523554,-88.7081491523174,0.0083350545818421,0.993158289439222,-0.116478062240389,0.369611183391831,-0.111292873624679,-0.922497408880942,-0.929149126877278,-0.0353625281692268,-0.368010042831269,1
"""


def write_inputs(tmp_path):
    i, e = tmp_path / "interior.txt", tmp_path / "exterior.txt"
    i.write_text(INTERIOR)
    e.write_text(EXTERIOR)
    return i, e


def test_interior(tmp_path):
    i, _ = write_inputs(tmp_path)
    cam = p2c.parse_interior(i)
    assert (cam["W"], cam["H"]) == (3872, 2592)
    assert abs(cam["cx"] - 1943.11827) < 1e-6 and abs(cam["cy"] - 1285.3628) < 1e-6
    assert np.allclose(cam["dist"], [-0.0821528, -0.00131558, -5.76325e-05, 0.000540635, 0.0190999])


def test_exterior_rotation_matches_angles(tmp_path):
    _, e = write_inputs(tmp_path)
    poses = p2c.parse_exterior(e)
    assert [p["name"] for p in poses] == ["5_CB_001", "5_CB_040"]
    for p in poses:
        assert np.allclose(p["R"] @ p["R"].T, np.eye(3), atol=1e-9)


def test_colmap_output_recovers_centers(tmp_path):
    i, e = write_inputs(tmp_path)
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(REPO / "scripts" / "pellis_to_colmap.py"),
                    str(i), str(e), str(out)], check=True, capture_output=True)
    cams = (out / "sparse/0/cameras.txt").read_text().splitlines()[1].split()
    assert cams[1] == "PINHOLE" and cams[2:4] == ["3872", "2592"]
    rows = [l.split() for l in (out / "sparse/0/images.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    assert len(rows) == 2
    poses = p2c.parse_exterior(e)
    for row, p in zip(rows, poses):
        w, x, y, z = map(float, row[1:5])
        R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        t = np.array(list(map(float, row[5:8])))
        assert np.allclose(-R.T @ t, p["C"], atol=1e-4)
        # Blickrichtung (OpenCV +z) = Gegenrichtung der photogrammetrischen -Z-Achse
        assert np.allclose(R[2], -p["R"][2], atol=1e-6)
