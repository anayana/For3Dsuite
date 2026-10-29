"""colmap_align.py: SfM-Posen per Aehnlichkeitstransformation ins Referenzsystem."""
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import colmap_align as ca  # noqa: E402
import pellis_to_colmap as p2c  # noqa: E402


def rot(ax, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    i, j = [(1, 2), (0, 2), (0, 1)][ax]
    R = np.eye(3)
    R[i, i] = R[j, j] = c
    R[i, j], R[j, i] = -s, s
    return R


def write_model(d, poses, cam="1 PINHOLE 100 80 90 90 50 40\n", points=True):
    d.mkdir(parents=True)
    (d / "cameras.txt").write_text("# Kamera\n" + cam)
    lines = ["# Bilder"]
    for i, (name, R, t) in enumerate(poses, 1):
        q = p2c.R_to_quat(R)
        lines += [f"{i} {q[0]} {q[1]} {q[2]} {q[3]} {t[0]} {t[1]} {t[2]} 1 {name}", ""]
    (d / "images.txt").write_text("\n".join(lines) + "\n")
    if points:
        (d / "points3D.txt").write_text("1 0.5 1.0 2.0 10 20 30 0.1\n2 1.0 0.0 0.0 1 2 3 0.1\n")


def test_umeyama_recovers_sim3():
    rng = np.random.default_rng(0)
    src = rng.normal(size=(20, 3))
    R = rot(2, 30) @ rot(0, 10)
    dst = src @ (2.5 * R).T + [1, 2, 3]
    s, Ra, t = ca.umeyama(src, dst)
    assert abs(s - 2.5) < 1e-9 and np.allclose(Ra, R) and np.allclose(t, [1, 2, 3])


def test_align_end_to_end(tmp_path):
    rng = np.random.default_rng(1)
    s, Ra, ta = 1.7, rot(1, 40) @ rot(2, -25), np.array([5.0, -2.0, 1.0])
    sfm, ref = [], []
    for k in range(10):
        R = rot(0, rng.uniform(-30, 30)) @ rot(1, rng.uniform(-180, 180))
        C = rng.normal(size=3) * 4
        sfm.append((f"img_{k:03d}.png", R, -R @ C))
        Rr, Cr = R @ Ra.T, s * Ra @ C + ta
        ref.append((f"img_{k:03d}.jpg", Rr, -Rr @ Cr))
    write_model(tmp_path / "sfm", sfm)
    write_model(tmp_path / "ref", ref)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "colmap_align.py"), str(tmp_path / "sfm"),
                        "--ref", str(tmp_path / "ref"), "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "10 mit gelieferter Pose" in r.stdout
    got = ca.read_images(out / "images.txt")
    want = ca.read_images(tmp_path / "ref" / "images.txt")
    assert sorted(got) == sorted(want)
    for k in got:
        assert np.allclose(got[k][0], want[k][0], atol=1e-6)
        assert np.allclose(got[k][1], want[k][1], atol=1e-4)
        assert got[k][2].endswith(".png")
    for f in ("cameras.bin", "images.bin", "points3D.bin", "points3D.txt"):
        assert (out / f).exists()


def test_write_model_multi_camera(tmp_path):
    cams = {1: ("SIMPLE_RADIAL", 100, 80, [90.0, 50.0, 40.0, -0.05]),
            2: ("SIMPLE_RADIAL", 100, 80, [95.0, 50.0, 40.0, -0.04])}
    recs = [(1, [1.0, 0, 0, 0], np.zeros(3), 1, "a.png"), (2, [1.0, 0, 0, 0], np.ones(3), 2, "b.png")]
    ca.write_model(tmp_path, cams, recs, np.zeros((1, 3)), np.zeros((1, 3), np.uint8))
    assert ca.read_cameras(tmp_path / "cameras.txt") == cams
    imgs = ca.read_images(tmp_path / "images.txt")
    assert imgs["a"][3] == 1 and imgs["b"][3] == 2
    assert (tmp_path / "cameras.bin").stat().st_size == 8 + 2 * (24 + 4 * 8)
