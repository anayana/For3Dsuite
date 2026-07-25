"""Unit-Tests der puren Kernfunktionen (numpy-only, kein GPU, keine Rohdaten).

Deckt die Bausteine ab, auf denen die Inventur steht: Kreis-Fit (BHD),
PCD-Leser, Voxel-Ausduennung und Hoehen-Farbverlauf. Alles deterministisch und
schnell -- taugt fuer CI.
"""
import numpy as np
import pytest

from inventory_from_cloud import fit_circle
from pcd_io import read_pcd
from pointcloud_web import voxel_downsample, height_ramp


# ---- fit_circle: der Kern der BHD-Bestimmung -----------------------------
def test_fit_circle_recovers_known_circle():
    # Punkte exakt auf einem Kreis r=0.11 um (5.0, 3.0) -> BHD 22 cm
    ang = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    cx0, cy0, r0 = 5.0, 3.0, 0.11
    px = cx0 + r0 * np.cos(ang)
    py = cy0 + r0 * np.sin(ang)
    cx, cy, r, rms, arc = fit_circle(px, py)
    assert cx == pytest.approx(cx0, abs=1e-3)
    assert cy == pytest.approx(cy0, abs=1e-3)
    assert r == pytest.approx(r0, abs=1e-3)
    assert rms < 1e-3          # perfekter Kreis -> minimales Residuum
    assert arc == pytest.approx(360.0)   # volle Abdeckung


def test_fit_circle_partial_arc():
    # Nur ein Viertelbogen -> arc deutlich unter 360 (Teilsicht erkennbar)
    ang = np.linspace(0, np.pi / 2, 20)
    px = np.cos(ang); py = np.sin(ang)
    _cx, _cy, _r, _rms, arc = fit_circle(px, py)
    assert arc < 180.0


# ---- read_pcd: IO fuer TreeScope-Wolken ----------------------------------
def test_read_pcd_ascii(tmp_path):
    p = tmp_path / "t.pcd"
    p.write_text(
        "# .PCD v0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n"
        "WIDTH 3\nHEIGHT 1\nPOINTS 3\nDATA ascii\n"
        "1.0 2.0 3.0\n4.0 5.0 6.0\n-1.0 0.0 2.5\n")
    x, y, z, rgb = read_pcd(str(p))
    assert len(x) == 3
    assert x[0] == pytest.approx(1.0)
    assert z[2] == pytest.approx(2.5)
    assert rgb is None          # kein rgb-Feld deklariert


# ---- voxel_downsample: ein Punkt je belegter Zelle ------------------------
def test_voxel_downsample_collapses_cell():
    # Drei Punkte in derselben 0.1-m-Zelle -> genau einer bleibt
    xyz = np.array([[0.01, 0.01, 0.01],
                    [0.02, 0.03, 0.04],
                    [0.09, 0.05, 0.02]], np.float32)
    rgb = np.array([[10, 20, 30], [11, 21, 31], [12, 22, 32]], np.float32)
    o_xyz, o_rgb = voxel_downsample(xyz, rgb, voxel=0.1)
    assert len(o_xyz) == 1
    assert len(o_rgb) == 1


def test_voxel_downsample_keeps_separate_cells():
    xyz = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], np.float32)
    o_xyz, _ = voxel_downsample(xyz, None, voxel=0.1)
    assert len(o_xyz) == 2


# ---- height_ramp: Farbverlauf fuer Wolken ohne RGB -----------------------
def test_height_ramp_shape_and_range():
    z = np.linspace(0, 30, 100, dtype=np.float32)
    rgb = height_ramp(z)
    assert rgb.shape == (100, 3)
    assert rgb.min() >= 0 and rgb.max() <= 255
    # niedrige Hoehen dunkler (kleinere Summe) als hohe
    assert rgb[0].sum() < rgb[-1].sum()
