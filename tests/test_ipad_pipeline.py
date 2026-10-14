"""Tests der iPad-LiDAR-Pipeline (ipad_capture.py, gsplat_export_metric.py).

Kern ist ein synthetischer Raum (tests/synth_room.py) mit bekannter Geometrie:
4 x 3 m, 2,5 m hoch. Daran wird geprueft, dass Posen, LiDAR-Rueckprojektion,
COLMAP-Ausgabe, Raummasse und die metrische Rueckrechnung des Splats stimmen.
Nur numpy + Pillow, keine GPU, kein COLMAP.
"""
import json
import sqlite3
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ipad_capture as ic                              # noqa: E402
import gsplat_export_metric as gx                      # noqa: E402

PIL = pytest.importorskip("PIL")
import synth_room as sr                                # noqa: E402


# ---- Konventionen ------------------------------------------------------------
def test_pose_layout_row_and_column_major():
    c2w = sr.look_at(np.array([1.0, 1.2, 0.5]), [3, 1, 2])
    assert np.allclose(ic.pose_from_16(c2w.reshape(-1)), c2w)
    assert np.allclose(ic.pose_from_16(c2w.T.reshape(-1)), c2w)   # simd spaltenweise


def test_intrinsics_layout():
    K = np.array([[1400.0, 0, 960], [0, 1400, 720], [0, 0, 1]])
    assert np.allclose(ic.K_from_9(K.reshape(-1)), K)
    assert np.allclose(ic.K_from_9(K.T.reshape(-1)), K)


def test_qvec_roundtrip():
    rng = np.random.default_rng(3)
    for _ in range(200):
        R = ic.qvec_to_R(rng.standard_normal(4))
        assert np.allclose(ic.qvec_to_R(ic.R_to_qvec(R)), R, atol=1e-9)
    R180 = np.diag([1.0, -1, -1])                      # 180 Grad: Vorzeichenfalle
    assert np.allclose(ic.qvec_to_R(ic.R_to_qvec(R180)), R180)


def test_umeyama_recovers_similarity_and_drops_outliers():
    rng = np.random.default_rng(1)
    src = rng.standard_normal((50, 3))
    R = ic.qvec_to_R(rng.standard_normal(4))
    dst = 0.37 * src @ R.T + [1.0, -2.0, 0.5]
    dst[:3] += 2.0                                     # drei grobe Ausreisser
    s, R2, t, res, keep = ic.robust_umeyama(src, dst)
    assert s == pytest.approx(0.37, rel=1e-6)
    assert np.allclose(R2, R, atol=1e-6)
    assert not keep[:3].any() and keep[3:].all()


# ---- LiDAR-Rueckprojektion -----------------------------------------------------
def test_backproject_plane_metric_and_edges():
    # Kamera im Ursprung, Blick +Z, Wand bei z = 2 m; rechte Haelfte: Kante auf 1 m
    K = np.array([[200.0, 0, 80], [0, 200, 60], [0, 0, 1]])
    depth = np.full((24, 32), 2.0, np.float32)
    depth[:, 16:] = 1.0
    xw, uv = ic.backproject(depth, K, (160, 120), np.eye(4), max_depth=4.0)
    assert set(np.round(xw[:, 2], 4)) == {1.0, 2.0}
    # Pixel an der Sprungkante (Spalten 15/16) sind verworfen
    cols = np.floor(uv[:, 0] / 5).astype(int)
    assert not np.isin(cols, [15, 16]).any()
    # Rueckprojektion trifft die Pixel wieder (K skaliert von 32x24 auf 160x120)
    uvp, z = ic.project(xw, K, np.eye(4))
    assert np.allclose(uvp, uv, atol=1e-3)


def test_backproject_confidence_filter():
    K = np.array([[200.0, 0, 80], [0, 200, 60], [0, 0, 1]])
    depth = np.full((24, 32), 2.0, np.float32)
    conf = np.full((24, 32), 2, np.uint8)
    conf[:12] = 1
    xw, _ = ic.backproject(depth, K, (160, 120), np.eye(4), conf=conf, min_conf=2)
    assert len(xw) == 12 * 32


def test_room_dimensions_rotated_box():
    rng = np.random.default_rng(0)
    pts = []
    for ax in range(3):                                # Punkte auf allen 6 Flaechen
        for side in (0, 1):
            p = rng.uniform(0, 1, (4000, 3)) * [5.0, 2.6, 3.5]
            p[:, ax] = side * [5.0, 2.6, 3.5][ax]
            pts.append(p)
    pts = np.concatenate(pts)
    a = np.radians(27)                                 # Raum im Grundriss gedreht
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    d = ic.room_dimensions(pts @ Ry.T, [0, 1, 0], q=0.0)
    assert d["laenge_m"] == pytest.approx(5.0, abs=0.03)
    assert d["breite_m"] == pytest.approx(3.5, abs=0.03)
    assert d["hoehe_m"] == pytest.approx(2.6, abs=0.01)


def test_select_keyframes_motion_windows():
    frames = []
    for i in range(30):                                # 1 cm je Frame -> alle 5 ein Fenster
        c2w = np.eye(4)
        c2w[0, 3] = 0.01 * i
        frames.append({"c2w": c2w, "t": float(i)})
    pick = ic.select_keyframes(frames, min_move=0.05, min_turn=90, max_frames=100)
    assert len(pick) == 6
    pick = ic.select_keyframes(frames, min_move=0.05, min_turn=90, max_frames=3)
    assert len(pick) == 3


# ---- Ende-zu-Ende: synthetischer Raum ---------------------------------------------
def read_colmap_bin(sparse):
    """Minimaler Leser fuer die geschriebenen .bin-Dateien (Pruefzweck)."""
    sparse = Path(sparse)
    b = (sparse / "cameras.bin").read_bytes()
    n, o, cams = struct.unpack_from("<Q", b)[0], 8, {}
    for _ in range(n):
        cid, mid, w, h = struct.unpack_from("<iiQQ", b, o)
        o += 24
        npar = {m[0]: m[1] for m in ic.CAMERA_MODELS.values()}[mid]
        cams[cid] = (w, h, struct.unpack_from(f"<{npar}d", b, o))
        o += 8 * npar
    b = (sparse / "images.bin").read_bytes()
    n, o, imgs = struct.unpack_from("<Q", b)[0], 8, {}
    for _ in range(n):
        iid, *qt, cid = struct.unpack_from("<i7di", b, o)
        o += 64
        e = b.index(b"\x00", o)
        name = b[o:e].decode()
        o = e + 1
        npt = struct.unpack_from("<Q", b, o)[0]
        o += 8
        pts = np.frombuffer(b, [("x", "<f8"), ("y", "<f8"), ("id", "<i8")], npt, o)
        o += 24 * npt
        w2c = np.eye(4)
        w2c[:3, :3], w2c[:3, 3] = ic.qvec_to_R(qt[:4]), qt[4:]
        imgs[iid] = {"name": name, "cam": cid, "w2c": w2c, "pts": pts}
    b = (sparse / "points3D.bin").read_bytes()
    n, o, pts3 = struct.unpack_from("<Q", b)[0], 8, {}
    for _ in range(n):
        pid, x, y, z, r, g, bl, err, tl = struct.unpack_from("<Q3d3BdQ", b, o)
        o += 51
        tr = struct.unpack_from(f"<{2 * tl}i", b, o)
        o += 8 * tl
        pts3[pid] = (np.array([x, y, z]), list(zip(tr[::2], tr[1::2])))
    return cams, imgs, pts3


def _prepare_args(capture, out, stills=None):
    return ["prepare", str(capture), str(out), "--points-per-frame", "300",
            "--min-move", "0.01"] + (["--stills", str(stills)] if stills else [])


@pytest.fixture(scope="module")
def room(tmp_path_factory):
    base = tmp_path_factory.mktemp("room")
    gt = sr.write_capture(base / "capture", n=24, size=(160, 120), depth_size=(48, 36),
                          stills=4, still_size=(200, 150))
    report = ic.main(_prepare_args(base / "capture", base / "out", base / "capture" / "stills"))
    return base, gt, report


def test_prepare_room_dimensions(room):
    _, _, report = room
    d = report["raummasse_naeherung"]
    assert d["laenge_m"] == pytest.approx(4.0, abs=0.03)
    assert d["breite_m"] == pytest.approx(3.0, abs=0.03)
    assert d["hoehe_m"] == pytest.approx(2.5, abs=0.03)
    assert report["frames"] == 24 and report["up"] == [0.0, 1.0, 0.0]


def test_prepare_cloud_lies_on_walls(room):
    base, _, _ = room
    b = (base / "out" / "lidar_points.ply").read_bytes()
    hdr, data = b.split(b"end_header\n", 1)
    n = int([l for l in hdr.decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
    rec = np.frombuffer(data, [("p", "<f4", 3), ("c", "u1", 3)], n)
    p = rec["p"].astype(float)
    dist = np.minimum(np.abs(p - sr.ROOM_LO), np.abs(p - sr.ROOM_HI)).min(1)
    assert np.percentile(dist, 99) < 0.01               # Punkte liegen auf den Waenden


def test_prepare_colmap_model_consistent(room):
    base, gt, _ = room
    cams, imgs, pts3 = read_colmap_bin(base / "out" / "sparse" / "0")
    assert len(imgs) == 24 and len(cams) == 1           # Fotos erst nach refine
    w, h, (fx, fy, cx, cy) = cams[1]
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])
    assert np.allclose(K, gt["K"])
    for iid, im in imgs.items():                        # Posen = GT
        i = int(im["name"][2:7])
        assert np.allclose(np.linalg.inv(im["w2c"]), gt["frames"][i], atol=1e-6)
        assert len(im["pts"]) == 300
    # jeder Track-Eintrag reprojiziert exakt auf seinen 2D-Punkt
    for pid in list(pts3)[::97]:
        X, track = pts3[pid]
        for iid, k in track:
            im = imgs[iid]
            uv, z = ic.project(X[None], K, im["w2c"])
            assert z[0] > 0
            assert np.allclose(uv[0], [im["pts"][k]["x"], im["pts"][k]["y"]], atol=0.01)
            assert im["pts"][k]["id"] == pid


def test_prepare_readable_by_pycolmap(room):
    pycolmap = pytest.importorskip("pycolmap")
    if not hasattr(pycolmap, "Reconstruction"):        # alter rmbrualla-pycolmap
        pytest.skip("pycolmap ohne Reconstruction")
    base, _, _ = room
    rec = pycolmap.Reconstruction(str(base / "out" / "sparse" / "0"))
    assert len(rec.images) == 24 and len(rec.points3D) == 24 * 300


def test_known_uses_database_ids(room, tmp_path):
    base, gt, _ = room
    db = tmp_path / "database.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE images (image_id INTEGER, name TEXT, camera_id INTEGER)")
    names = [f"f_{i:05d}.jpg" for i in range(24)] + ["s_IMG_0000.jpg"]
    con.executemany("INSERT INTO images VALUES (?,?,?)",
                    [(100 + k, n, 7 if n.startswith("f_") else 8) for k, n in enumerate(names)])
    con.commit()
    con.close()
    ic.main(["known", str(base / "out"), str(db), str(tmp_path / "known")])
    cams, imgs = ic.read_colmap_text(tmp_path / "known")
    assert list(cams) == [7] and len(imgs) == 24        # Foto bleibt fuer den Registrator
    first = (tmp_path / "known" / "images.txt").read_text().split()[0]
    assert first == "100"
    assert np.allclose(np.linalg.inv(imgs["f_00003.jpg"]["w2c"]), gt["frames"][3], atol=1e-9)


def test_refine_places_stills_metric(room, tmp_path):
    """Simuliertes COLMAP-Ergebnis in beliebigem Rahmen (Massstab 0,4, gedreht):
    refine muss Fotos in den metrischen ARKit-Rahmen bringen."""
    base, gt, _ = room
    rng = np.random.default_rng(5)
    R = ic.qvec_to_R(rng.standard_normal(4))
    s, t = 0.4, np.array([3.0, -1.0, 2.0])

    def to_sfm(c2w):                                   # Welt -> SfM-Rahmen
        out = np.eye(4)
        out[:3, :3] = R @ c2w[:3, :3]
        out[:3, 3] = s * R @ c2w[:3, 3] + t
        return np.linalg.inv(out)

    sfm = tmp_path / "sfm"
    sfm.mkdir()
    sw, sh = 200, 150
    Ks = gt["stills"][0][2]
    (sfm / "cameras.txt").write_text(
        "1 PINHOLE 160 120 " + " ".join(map(str, gt["K"][[0, 1, 0, 1], [0, 1, 2, 2]])) + "\n"
        + f"2 OPENCV {sw} {sh} {Ks[0, 0]} {Ks[1, 1]} {Ks[0, 2]} {Ks[1, 2]} 0 0 0 0\n")
    lines = []
    entries = [(f"f_{i:05d}.jpg", c, 1) for i, c in enumerate(gt["frames"])] \
        + [(n, c, 2) for n, c, _, _ in gt["stills"]]
    for k, (name, c2w, cam) in enumerate(entries, 1):
        w2c = to_sfm(c2w)
        q = ic.R_to_qvec(w2c[:3, :3])
        lines.append(f"{k} " + " ".join(f"{v:.12f}" for v in (*q, *w2c[:3, 3]))
                     + f" {cam} {name}\n\n")
    (sfm / "images.txt").write_text("".join(lines))

    out = tmp_path / "out"
    ic.main(_prepare_args(base / "capture", out, base / "capture" / "stills"))
    ic.main(["refine", str(out), str(sfm)])
    rep = json.loads((out / "capture_report.json").read_text())
    assert rep["ausrichtung"]["massstab"] == pytest.approx(1 / s, rel=1e-6)
    assert rep["ausrichtung"]["rms_cm"] < 0.01
    cams, imgs, pts3 = read_colmap_bin(out / "sparse" / "0")
    stills = {im["name"]: im for im in imgs.values() if im["name"].startswith("s_")}
    assert len(stills) == 4
    for name, c2w, _, _ in gt["stills"]:
        assert np.allclose(np.linalg.inv(stills[name]["w2c"]), c2w, atol=1e-6)
        assert len(stills[name]["pts"]) >= 50             # LiDAR-Tiefe auch fuer Fotos
    # sichtbar markierte Punkte liegen vor der Kamera und im Bild
    im = next(iter(stills.values()))
    w, h, p = cams[im["cam"]]
    K = np.array([[p[0], 0, p[2]], [0, p[1], p[3]], [0, 0, 1]])
    X = np.array([pts3[int(i)][0] for i in im["pts"]["id"]])
    uv, z = ic.project(X, K, im["w2c"])
    assert (z > 0).all() and (uv[:, 0] >= 0).all() and (uv[:, 0] < w).all()


# ---- metrischer Splat-Export ----------------------------------------------------------
def _similarity(seed, s=0.23):
    rng = np.random.default_rng(seed)
    T = np.eye(4)
    T[:3, :3] = s * ic.qvec_to_R(rng.standard_normal(4))
    T[:3, 3] = rng.standard_normal(3)
    return T


def test_export_to_metric_geometry():
    rng = np.random.default_rng(2)
    T = _similarity(2)
    s = np.cbrt(np.linalg.det(T[:3, :3]))
    R = T[:3, :3] / s
    N = 50
    means_n = rng.standard_normal((N, 3)).astype(np.float32)
    ls_n = rng.normal(-3, 0.5, (N, 3)).astype(np.float32)
    q_n = rng.standard_normal((N, 4)).astype(np.float32)
    m, ls, q, _ = gx.to_metric(means_n, ls_n, q_n, None, T)
    assert np.allclose(s * m @ R.T + T[:3, 3], means_n, atol=1e-5)
    for i in range(5):                                 # Kovarianz: R^T S_n R / s^2
        Rn = gx.quat_to_R(q_n[i])
        Sn = Rn @ np.diag(np.exp(2 * ls_n[i])) @ Rn.T
        Rw = gx.quat_to_R(q[i])
        Sw = Rw @ np.diag(np.exp(2 * ls[i].astype(float))) @ Rw.T
        assert np.allclose(Sw, R.T @ Sn @ R / s ** 2, rtol=1e-4, atol=1e-12)


def test_export_sh_rotation_preserves_view_colors():
    rng = np.random.default_rng(4)
    T = _similarity(4)
    R = T[:3, :3] / np.cbrt(np.linalg.det(T[:3, :3]))
    shN = rng.standard_normal((3, 15, 3))
    _, _, _, shN_w = gx.to_metric(np.zeros((3, 3)), np.zeros((3, 3)),
                                  np.tile([1.0, 0, 0, 0], (3, 1)), shN, T)
    d = rng.standard_normal((40, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    Yw = gx.sh_basis(d, 3)[:, 1:]
    Yn = gx.sh_basis(d @ R.T, 3)[:, 1:]               # gleiche Blickrichtung, normalisiert
    for n in range(3):
        assert np.allclose(Yw @ shN_w[n], Yn @ shN[n], atol=1e-4)


def test_export_ply_readable(tmp_path):
    from ply_reduce import read_header
    N = 10
    rng = np.random.default_rng(0)
    gx.write_ply(tmp_path / "s.ply", rng.standard_normal((N, 3)), rng.standard_normal((N, 3)),
                 rng.standard_normal((N, 4)), rng.standard_normal(N),
                 rng.standard_normal((N, 1, 3)), rng.standard_normal((N, 15, 3)))
    with open(tmp_path / "s.ply", "rb") as f:
        n, props, _ = read_header(f)
    assert n == N and len(props) == 62 and props[-1] == "rot_3"


def test_newest_ckpt_is_numeric(tmp_path):
    for st in (6999, 29999):
        (tmp_path / f"ckpt_{st}_rank0.pt").write_bytes(b"")
    assert gx.newest_ckpt(str(tmp_path)).endswith("ckpt_29999_rank0.pt")
