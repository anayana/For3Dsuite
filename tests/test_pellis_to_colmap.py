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


TRANSFORM = """[ 0.717069 -0.152697 -1.126580 88.883987
-1.134626 -0.012270 -0.720528 99.851013
0.071570 1.335373 -0.135442 7.296434];
"""


def test_transform_keeps_projection(tmp_path):
    """Ein Punkt projiziert vor und nach der Transformation auf dasselbe Pixel."""
    tr = tmp_path / "transformation_matrix.txt"
    tr.write_text(TRANSFORM)
    s, R_t, t_t = p2c.parse_transform(tr)
    assert abs(s - 1.34413) < 1e-4
    i, e = write_inputs(tmp_path)
    cam = p2c.parse_interior(i)
    K = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]])
    p = p2c.parse_exterior(e)[0]
    X = p["C"] + 5 * (p2c.FLIP @ p["R"])[2]          # 5 Einheiten vor der Kamera
    def proj(R, C, X):
        x = K @ (p2c.FLIP @ R @ (X - C))
        return x[:2] / x[2]
    before = proj(p["R"], p["C"], X)
    after = proj(p["R"] @ R_t.T, s * R_t @ p["C"] + t_t, s * R_t @ X + t_t)
    assert np.allclose(before, after, atol=1e-6)
    assert 0 < before[0] < cam["W"] and 0 < before[1] < cam["H"]


def test_cloud_sample(tmp_path):
    cloud = tmp_path / "1_point_cloud.txt"
    rows = ["//X Y Z R G B label Nx Ny Nz"]
    rows += [f"{100+i*0.01:.8f} 108.7 7.15 {i % 256} 32 27 1.000000 0 0 1" for i in range(50)]
    cloud.write_text("\n".join(rows) + "\n")
    xyz, rgb, total = p2c.sample_cloud(cloud, 20, chunk=7)
    assert total == 50 and len(xyz) == 20 and len(set(xyz[:, 0])) == 20
    assert rgb.dtype == np.uint8 and np.all(rgb[:, 1] == 32)
    xyz, _, _ = p2c.sample_cloud(cloud, 100)
    assert len(xyz) == 50


def test_binary_matches_pycolmap_layout(tmp_path):
    """.bin-Dateien so lesen, wie es rmbrualla/pycolmap (gsplat 1.5.3) tut."""
    import struct
    i, e = write_inputs(tmp_path)
    tr = tmp_path / "t.txt"
    tr.write_text(TRANSFORM)
    cloud = tmp_path / "c.txt"
    cloud.write_text("//X Y Z R G B label Nx Ny Nz\n" + "".join(
        f"{100+k:.3f} 108.7 7.1 {k} 2 3 1.0 0 0 1\n" for k in range(5)))
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(REPO / "scripts" / "pellis_to_colmap.py"),
                    str(i), str(e), str(out), "--transform", str(tr), "--cloud", str(cloud)],
                   check=True, capture_output=True)
    sp = out / "sparse/0"
    with open(sp / "cameras.bin", "rb") as f:
        assert struct.unpack("<Q", f.read(8))[0] == 1
        cid, model, w, h = struct.unpack("<IiQQ", f.read(24))
        assert (cid, model, w, h) == (1, 1, 3872, 2592)
        assert abs(struct.unpack("<4d", f.read(32))[2] - 1943.11827) < 1e-6
    with open(sp / "images.bin", "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        names = []
        for _ in range(n):
            d = struct.Struct("<I 4d 3d I").unpack(f.read(64))
            name = b"".join(iter(lambda: f.read(1), b"\x00")).decode()
            assert struct.unpack("<Q", f.read(8))[0] == 0
            names.append(name)
            assert d[8] == 1
        assert names == ["5_CB_001.jpg", "5_CB_040.jpg"] and f.read() == b""
    with open(sp / "points3D.bin", "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        ds = struct.Struct("<Q 3d 3B d Q")
        pts = [ds.unpack(f.read(ds.size)) for _ in range(n)]
        assert n == 5 and f.read() == b""
        assert sorted(p[4] for p in pts) == [0, 1, 2, 3, 4]


def test_orientation_roll_only_flag1(tmp_path):
    """--orientation-roll dreht nur Fotos mit Orientation = 1, Zentren bleiben gleich."""
    i, e = write_inputs(tmp_path)
    def run(extra):
        out = tmp_path / ("o" + "_".join(extra))
        subprocess.run([sys.executable, str(REPO / "scripts" / "pellis_to_colmap.py"),
                        str(i), str(e), str(out)] + extra, check=True, capture_output=True)
        return [l.split() for l in (out / "sparse/0/images.txt").read_text().splitlines()
                if l.strip() and not l.startswith("#")]
    a, b = run([]), run(["--orientation-roll", "-90"])
    assert a[0][1:8] == b[0][1:8]                       # 5_CB_001: Orientation 0
    assert a[1][1:5] != b[1][1:5]                       # 5_CB_040: Orientation 1
    def center(row):
        w, x, y, z = map(float, row[1:5])
        R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        return -R.T @ np.array(list(map(float, row[5:8])))
    assert np.allclose(center(a[1]), center(b[1]), atol=1e-4)
