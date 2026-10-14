#!/usr/bin/env python3
"""ipad_capture.py -- iPhone/iPad-LiDAR-Aufnahme -> metrischer 3DGS-Datensatz (COLMAP).

Idee (wie XGRIDS PortalCam, nur mit dem iPad): ARKit liefert je Frame Kamerapose
(visuell-inertiale Odometrie) und ein LiDAR-Tiefenbild im METRISCHEN Massstab.
Daraus schreiben wir direkt ein COLMAP-Modell -- ohne SfM:

  <out>/images/f_00000.jpg ...        ausgewaehlte, scharfe Keyframes
  <out>/images/s_<name>.jpg ...       optionale hochaufgeloeste Fotos (--stills)
  <out>/sparse/0/{cameras,images,points3D}.bin
        points3D = LiDAR-Punkte. Jeder Punkt hat einen Track auf "sein" Bild ->
        gsplat --depth_loss nutzt damit die LiDAR-Tiefe als Tiefen-Prior, die
        Initialisierung startet auf der LiDAR-Geometrie.
  <out>/lidar_points.ply              dichte, metrische Punktwolke zum MESSEN
                                      (CloudCompare, MeshLab ...)
  <out>/capture_report.json           Raummasse (Naeherung), Statistik
  <out>/capture.json                  Zwischenstand fuer "refine"

Masse immer an lidar_points.ply ablesen, nicht am Splat. Erwartbar: +-1-3 cm.

Unterstuetzte Exporte (--format auto erkennt sie):
  scanner3d   3d Scanner App (Laan Labs), Export "All Data": frame_*.jpg/.json,
              depth_*.png (16 bit, mm), conf_*.png
  record3d    Record3D, Export "EXR + JPG": metadata.json, rgbd/<i>.jpg/.exr
  polycam     Polycam Raw Data (Developer Mode): keyframes/{images,cameras,depth,confidence}
  nerfstudio  transforms.json (OpenGL-Posen, optional depth_file_path)
  arkitscenes Apple ARKitScenes (frei, iPad Pro; mit Laserscanner-Referenz)

Zwei Schritte:
  prepare  Aufnahme lesen -> Datensatz mit ARKit-Posen (sofort trainierbar)
  known    COLMAP-Modell mit den festen ARKit-Posen (fuer point_triangulator)
  refine   COLMAP-Modell, in dem die Fotos registriert sind, per Aehnlichkeits-
           transformation an die ARKit-Kamerazentren haengen (Kontrolle: Massstab
           ~1, RMS ~0) -> Fotos im metrischen ARKit-Rahmen, mit LiDAR-Tiefe.
  Die COLMAP-Schritte dazwischen erledigt scripts/ipad_sfm.sh.

  python scripts/ipad_capture.py prepare <export> <out> [--stills DIR]
  bash   scripts/ipad_sfm.sh <out>

Nur numpy + Pillow. Optional: pillow-heif (HEIC-Fotos), opencv (EXR-Tiefe).
"""
import argparse
import json
import math
import re
import shutil
import struct
import sys
from pathlib import Path

import numpy as np

try:
    from PIL import Image, ImageOps
except ImportError:                                  # Tests ohne Pillow: Geometrie geht
    Image = ImageOps = None

ONE_FOCAL = {"SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL", "SIMPLE_RADIAL_FISHEYE",
             "RADIAL_FISHEYE", "FOV"}
GL_TO_CV = np.diag([1.0, -1.0, -1.0, 1.0])           # OpenGL/ARKit-Kamera -> OpenCV-Kamera
IMG_EXT = (".jpg", ".jpeg", ".png", ".heic", ".heif")


# ---- Geometrie ------------------------------------------------------------
def pose_from_16(vals):
    """16 Werte (ARKit simd_float4x4, Zeilen- ODER Spaltenfolge) -> 4x4 c2w.

    Die Translation steht entweder in der letzten Spalte (zeilenweise) oder in
    der letzten Zeile (spaltenweise); erkannt an der homogenen Zeile 0,0,0,1.
    """
    M = np.asarray(vals, float).reshape(4, 4)
    if np.allclose(M[3, :3], 0) and not np.allclose(M[:3, 3], 0):
        return M
    if np.allclose(M[:3, 3], 0) and not np.allclose(M[3, :3], 0):
        return M.T
    return M if np.allclose(M[3], [0, 0, 0, 1]) else M.T


def K_from_9(vals):
    """3x3-Intrinsik aus 9 Werten (zeilen- oder spaltenweise)."""
    K = np.asarray(vals, float).reshape(3, 3)
    if K[2, 0] != 0 or K[2, 1] != 0:                 # cx/cy in der letzten Zeile
        K = K.T
    return K


def quat_xyzw_to_R(q):
    x, y, z, w = np.asarray(q, float) / np.linalg.norm(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def R_to_qvec(R):
    """Rotationsmatrix -> COLMAP-Quaternion (w, x, y, z)."""
    K = np.array([
        [R[0, 0] - R[1, 1] - R[2, 2], 0, 0, 0],
        [R[1, 0] + R[0, 1], R[1, 1] - R[0, 0] - R[2, 2], 0, 0],
        [R[2, 0] + R[0, 2], R[2, 1] + R[1, 2], R[2, 2] - R[0, 0] - R[1, 1], 0],
        [R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1],
         R[0, 0] + R[1, 1] + R[2, 2]]]) / 3.0
    w, V = np.linalg.eigh(K)
    q = V[[3, 0, 1, 2], np.argmax(w)]
    return -q if q[0] < 0 else q


def qvec_to_R(q):
    w, x, y, z = np.asarray(q, float) / np.linalg.norm(q)
    return quat_xyzw_to_R([x, y, z, w])


def umeyama(src, dst):
    """Aehnlichkeit (s, R, t) mit dst ~ s * R @ src + t (kleinste Quadrate)."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    U, S, Vt = np.linalg.svd(xd.T @ xs / len(src))
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1
    R = U @ D @ Vt
    s = np.trace(np.diag(S) @ D) / xs.var(0).sum()
    return s, R, mu_d - s * R @ mu_s


def robust_umeyama(src, dst, iters=3, min_tol=0.03):
    """Umeyama mit Ausreisser-Abwurf (> max(3*Median, min_tol))."""
    keep = np.ones(len(src), bool)
    for _ in range(iters):
        s, R, t = umeyama(src[keep], dst[keep])
        res = np.linalg.norm((s * src @ R.T + t) - dst, axis=1)
        new = res <= max(3 * np.median(res[keep]), min_tol)
        if new.sum() < 3 or (new == keep).all():
            break
        keep = new
    s, R, t = umeyama(src[keep], dst[keep])
    res = np.linalg.norm((s * src @ R.T + t) - dst, axis=1)
    return s, R, t, res, keep


def backproject(depth, K, img_wh, c2w, conf=None, min_conf=2, max_depth=4.0,
                edge_rel=0.05):
    """LiDAR-Tiefenbild -> Weltpunkte (metrisch) + Pixelkoordinaten im RGB-Bild.

    K gehoert zum RGB-Bild (img_wh); das Tiefenbild hat meist 256x192 und wird
    ueber das Seitenverhaeltnis skaliert. Pixelzentren bei +0.5 (COLMAP-Konvention).
    Kanten (Tiefenspruenge > edge_rel) werden verworfen -- dort liefert der
    LiDAR "fliegende Pixel" zwischen Vorder- und Hintergrund.
    """
    Hd, Wd = depth.shape
    W, H = img_wh
    sx, sy = Wd / W, Hd / H
    fx, fy = K[0, 0] * sx, K[1, 1] * sy
    cx, cy = K[0, 2] * sx, K[1, 2] * sy
    d = np.asarray(depth, np.float32)
    m = np.isfinite(d) & (d > 0.05) & (d < max_depth)
    if conf is not None:
        m &= conf >= min_conf
    if edge_rel:
        dd = np.where(np.isfinite(d), d, 0)
        for dy, dx in ((0, 1), (1, 0)):
            a, b = dd[:Hd - dy, :Wd - dx], dd[dy:, dx:]
            bad = np.abs(a - b) > edge_rel * np.minimum(a, b)
            m[:Hd - dy, :Wd - dx] &= ~bad
            m[dy:, dx:] &= ~bad
    v, u = np.nonzero(m)
    z = d[v, u]
    xc = np.stack([(u + 0.5 - cx) / fx * z, (v + 0.5 - cy) / fy * z, z], 1)
    xw = xc @ c2w[:3, :3].T + c2w[:3, 3]
    uv = np.stack([(u + 0.5) / sx, (v + 0.5) / sy], 1)
    return xw.astype(np.float32), uv.astype(np.float32)


def project(points, K, w2c):
    xc = points @ w2c[:3, :3].T + w2c[:3, 3]
    z = xc[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = (xc[:, :2] / z[:, None]) * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
    return uv, z


def visible_points(points, K, w2c, wh, occluders=None, tol=0.05):
    """Welche Punkte sieht eine Kamera? Z-Puffer aus den (dichten) Verdeckern.

    Fuer die hochaufgeloesten Fotos ohne eigene Tiefe: ein LiDAR-Punkt zaehlt als
    sichtbar, wenn er in seiner Rasterzelle hoechstens tol (relativ) hinter der
    vordersten Flaeche liegt.
    """
    W, H = wh
    cell = max(4, W // 160)
    gw, gh = W // cell + 1, H // cell + 1
    occ = points if occluders is None else occluders
    uv_o, z_o = project(occ, K, w2c)
    ok = (z_o > 0.05) & (uv_o[:, 0] >= 0) & (uv_o[:, 0] < W) & (uv_o[:, 1] >= 0) & (uv_o[:, 1] < H)
    zbuf = np.full(gw * gh, np.inf)
    cid = (uv_o[ok, 1] // cell).astype(int) * gw + (uv_o[ok, 0] // cell).astype(int)
    np.minimum.at(zbuf, cid, z_o[ok])
    uv, z = project(points, K, w2c)
    inside = (z > 0.05) & (uv[:, 0] >= 0) & (uv[:, 0] < W) & (uv[:, 1] >= 0) & (uv[:, 1] < H)
    vis = np.zeros(len(points), bool)
    idx = np.flatnonzero(inside)
    c = (uv[idx, 1] // cell).astype(int) * gw + (uv[idx, 0] // cell).astype(int)
    vis[idx] = z[idx] <= zbuf[c] * (1 + tol) + 0.01
    return vis, uv


def voxel_downsample(xyz, rgb, voxel):
    keys = np.floor(xyz / voxel).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    return xyz[idx], rgb[idx]


def room_dimensions(xyz, up, q=0.5):
    """Naeherung der Raummasse aus der Punktwolke: Hoehe entlang up, Grundriss
    als kleinstes gedrehtes Rechteck (q..100-q Perzentil, robust gegen Ausreisser).
    Gilt nur, wenn Boden, Decke und alle Waende im Scan sind."""
    if len(xyz) > 200_000:                           # Perzentile auf Stichprobe
        xyz = xyz[np.random.default_rng(0).choice(len(xyz), 200_000, replace=False)]
    up = np.asarray(up, float) / np.linalg.norm(up)
    ref = np.array([1.0, 0, 0]) if abs(up[0]) < 0.9 else np.array([0, 0, 1.0])
    a = np.cross(up, ref); a /= np.linalg.norm(a)
    b = np.cross(up, a)
    h = xyz @ up
    pa, pb = xyz @ a, xyz @ b
    best = None
    for deg in np.arange(0, 90, 0.5):
        r = math.radians(deg)
        u = pa * math.cos(r) + pb * math.sin(r)
        v = -pa * math.sin(r) + pb * math.cos(r)
        eu = np.percentile(u, 100 - q) - np.percentile(u, q)
        ev = np.percentile(v, 100 - q) - np.percentile(v, q)
        if best is None or eu * ev < best[0]:
            best = (eu * ev, eu, ev, deg)
    _, eu, ev, deg = best
    height = np.percentile(h, 100 - q) - np.percentile(h, q)
    L, B = max(eu, ev), min(eu, ev)
    return {"laenge_m": round(float(L), 3), "breite_m": round(float(B), 3),
            "hoehe_m": round(float(height), 3), "flaeche_m2": round(float(L * B), 2),
            "volumen_m3": round(float(L * B * height), 2), "grundriss_drehung_grad": float(deg)}


# ---- Bilder / Tiefen lesen --------------------------------------------------
def _need_pil():
    if Image is None:
        sys.exit("Pillow fehlt: pip install pillow")


def open_image(path):
    _need_pil()
    p = Path(path)
    if p.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            sys.exit(f"{p.name}: HEIC braucht 'pip install pillow-heif' "
                     "(oder am iPhone Kamera -> Formate -> 'Maximale Kompatibilitaet').")
    return Image.open(p)


def image_size(path):
    with open_image(path) as im:
        return im.size


def read_depth(path, scale=0.001):
    """Tiefenbild in Metern. PNG 16 bit: Millimeter (scale), EXR/NPY: Meter."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".npy":
        return np.load(p).astype(np.float32)
    if ext == ".exr":
        import os
        os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
        try:
            import cv2
        except ImportError:
            sys.exit("EXR-Tiefe braucht OpenCV: pip install opencv-python-headless")
        d = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if d is None:
            sys.exit(f"EXR nicht lesbar: {p}")
        return (d[..., 0] if d.ndim == 3 else d).astype(np.float32)
    _need_pil()
    with Image.open(p) as im:
        a = np.array(im)
    if a.dtype.kind == "f":
        return a.astype(np.float32)
    return a.astype(np.float32) * scale


def read_conf(path, shape):
    """Konfidenz 0/1/2 (ARKit low/medium/high). PNG 0..2 oder 0..255, Rohbytes."""
    if path is None:
        return None
    p = Path(path)
    if p.suffix.lower() in (".png", ".jpg"):
        _need_pil()
        with Image.open(p) as im:
            c = np.array(im)
        c = c[..., 0] if c.ndim == 3 else c
    elif p.suffix.lower() == ".npy":
        c = np.load(p)
    else:                                             # Record3D: rohe uint8-Bytes
        raw = np.fromfile(p, np.uint8)
        if raw.size != shape[0] * shape[1]:
            return None
        c = raw.reshape(shape)
    if c.shape != tuple(shape):
        return None
    if c.max() > 2:
        c = np.round(c.astype(np.float32) / 255 * 2)
    return c.astype(np.uint8)


def sharpness(path):
    """Varianz des Laplace-Operators auf verkleinertem Graubild (hoeher = schaerfer)."""
    with open_image(path) as im:
        g = np.asarray(im.convert("L").reduce(4), np.float32)
    lap = g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


# ---- Loader je App ------------------------------------------------------------
def _num(s):
    m = re.findall(r"\d+", s)
    return int(m[-1]) if m else None


def _sidecars(folder, kind):
    """{Nummer: Pfad} fuer Dateien wie depth_00012.png, conf_12.png, 12.exr ..."""
    out = {}
    for f in Path(folder).iterdir():
        n = f.name.lower()
        if kind in n and f.suffix.lower() in (".png", ".exr", ".npy", ".tiff", ".conf"):
            k = _num(f.stem)
            if k is not None:
                out.setdefault(k, f)
    return out


def load_scanner3d(root):
    root = Path(root)
    depth = _sidecars(root, "depth")
    conf = _sidecars(root, "conf")
    frames = []
    for js in sorted(root.glob("frame_*.json")):
        img = next((js.with_suffix(e) for e in (".jpg", ".jpeg", ".png")
                    if js.with_suffix(e).exists()), None)
        if img is None:
            continue
        d = json.loads(js.read_text())
        pose = d.get("cameraPoseARFrame") or d.get("cameraPose")
        K = d.get("intrinsics")
        if pose is None or K is None:
            continue
        n = _num(js.stem)
        frames.append({"src": str(img), "K": K_from_9(K),
                       "c2w": pose_from_16(pose) @ GL_TO_CV,
                       "depth": str(depth[n]) if n in depth else None,
                       "conf": str(conf[n]) if n in conf else None,
                       "t": float(d.get("time", n))})
    return frames


def load_record3d(root):
    root = Path(root)
    meta = json.loads((root / "metadata.json").read_text())
    K = np.array(meta["K"], float).reshape(3, 3).T      # spaltenweise gespeichert
    W, H = int(meta["w"]), int(meta["h"])
    rgbd = root / "rgbd" if (root / "rgbd").is_dir() else root
    frames = []
    for i, p in enumerate(meta["poses"]):
        img = rgbd / f"{i}.jpg"
        if not img.exists():
            continue
        c2w = np.eye(4)
        c2w[:3, :3] = quat_xyzw_to_R(p[:4])
        c2w[:3, 3] = p[4:7]
        dep = next((rgbd / f"{i}{e}" for e in (".exr", ".png", ".npy")
                    if (rgbd / f"{i}{e}").exists()), None)
        cf = rgbd / f"{i}.conf"
        frames.append({"src": str(img), "K": K.copy(), "K_wh": (W, H),
                       "c2w": c2w @ GL_TO_CV, "depth": str(dep) if dep else None,
                       "conf": str(cf) if cf.exists() else None, "t": float(i)})
    return frames


def load_polycam(root):
    root = Path(root)
    kf = root / "keyframes" if (root / "keyframes").is_dir() else root
    pre = "corrected_" if (kf / "corrected_cameras").is_dir() else ""
    cams, imgs = kf / f"{pre}cameras", kf / f"{pre}images"
    if not imgs.is_dir():
        imgs = kf / "images"
    frames = []
    for js in sorted(cams.glob("*.json")):
        img = next((imgs / (js.stem + e) for e in (".jpg", ".png")
                    if (imgs / (js.stem + e)).exists()), None)
        if img is None:
            continue
        d = json.loads(js.read_text())
        K = np.array([[d["fx"], 0, d["cx"]], [0, d["fy"], d["cy"]], [0, 0, 1]], float)
        c2w = np.eye(4)
        c2w[:3, :4] = [[d[f"t_{r}{c}"] for c in range(4)] for r in range(3)]
        dep = kf / "depth" / f"{js.stem}.png"
        cf = kf / "confidence" / f"{js.stem}.png"
        frames.append({"src": str(img), "K": K, "K_wh": (int(d["width"]), int(d["height"])),
                       "c2w": c2w @ GL_TO_CV, "depth": str(dep) if dep.exists() else None,
                       "conf": str(cf) if cf.exists() else None,
                       "t": float(_num(js.stem) or len(frames))})
    return frames


def load_nerfstudio(root):
    root = Path(root)
    meta = json.loads((root / "transforms.json").read_text())
    scale = float(meta.get("depth_unit_scale_factor", 1e-3))
    frames = []
    for i, fr in enumerate(meta["frames"]):
        g = {**meta, **fr}
        img = root / fr["file_path"]
        if not img.exists():
            continue
        if "w" not in g:
            g["w"], g["h"] = image_size(img)
        if "fl_x" in g:
            fx, fy = g["fl_x"], g.get("fl_y", g["fl_x"])
        else:
            fx = fy = 0.5 * g["w"] / math.tan(0.5 * g["camera_angle_x"])
        K = np.array([[fx, 0, g.get("cx", g["w"] / 2)], [0, fy, g.get("cy", g["h"] / 2)],
                      [0, 0, 1]], float)
        dp = fr.get("depth_file_path")
        frames.append({"src": str(img), "K": K, "K_wh": (int(g["w"]), int(g["h"])),
                       "c2w": np.array(fr["transform_matrix"], float) @ GL_TO_CV,
                       "depth": str(root / dp) if dp else None, "conf": None,
                       "depth_scale": scale, "t": float(i)})
    return frames


def axis_angle_to_R(aa):
    """Rodrigues: Drehvektor (rad) -> Rotationsmatrix."""
    aa = np.asarray(aa, float)
    th = np.linalg.norm(aa)
    if th < 1e-12:
        return np.eye(3)
    k = aa / th
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx


def slerp(q0, q1, a):
    q0, q1 = np.asarray(q0, float), np.asarray(q1, float)
    d = float(np.dot(q0, q1))
    if d < 0:
        q1, d = -q1, -d
    if d > 0.9995:
        q = q0 + a * (q1 - q0)
    else:
        th = math.acos(d)
        q = (math.sin((1 - a) * th) * q0 + math.sin(a * th) * q1) / math.sin(th)
    return q / np.linalg.norm(q)


class Trajectory:
    """Posen-Zeitreihe (c2w) mit Interpolation (Slerp + linear)."""

    def __init__(self, ts, c2ws):
        o = np.argsort(ts)
        self.ts = np.asarray(ts, float)[o]
        self.q = np.array([R_to_qvec(c2ws[i][:3, :3]) for i in o])
        self.C = np.array([c2ws[i][:3, 3] for i in o])

    def at(self, t, max_gap=0.25):
        i = int(np.searchsorted(self.ts, t))
        for j in (i - 1, i):                          # (fast) exakter Treffer
            if 0 <= j < len(self.ts) and abs(self.ts[j] - t) < 5e-4:
                return self._pose(self.q[j], self.C[j])
        if i == 0 or i == len(self.ts) or self.ts[i] - self.ts[i - 1] > max_gap + 1e-6:
            return None
        a = (t - self.ts[i - 1]) / (self.ts[i] - self.ts[i - 1])
        return self._pose(slerp(self.q[i - 1], self.q[i], a),
                          (1 - a) * self.C[i - 1] + a * self.C[i])

    @staticmethod
    def _pose(q, C):
        c2w = np.eye(4)
        c2w[:3, :3], c2w[:3, 3] = qvec_to_R(q), C
        return c2w


def _ts_files(folder, ext=".png"):
    """{Zeitstempel: Pfad} fuer ARKitScenes-Namen wie 41069021_305.244.png."""
    out = {}
    if folder.is_dir():
        for f in folder.glob(f"*{ext}"):
            m = re.search(r"_(\d+\.\d+)$", f.stem)
            if m:
                out[round(float(m.group(1)), 3)] = f
    return out


def _nearest(index, keys, t, tol):
    if not len(keys):
        return None
    i = int(np.clip(np.searchsorted(keys, t), 1, len(keys) - 1)) if len(keys) > 1 else 0
    cand = [k for k in (keys[max(i - 1, 0)], keys[i]) if abs(k - t) <= tol]
    return min(cand, key=lambda k: abs(k - t)) if cand else None


def load_arkitscenes(root):
    """Apple ARKitScenes (iPad Pro, frei fuer nicht-kommerzielle Nutzung).

    Ein Ordner je video_id mit lowres_wide.traj (Welt->Kamera als Drehvektor +
    Translation, OpenCV-Kamera), lowres_depth/ + confidence/ (256x192, mm) und
    Bildern: color/ (Upsampling-Teil, 1920x1440), wide/, vga_wide/ oder
    lowres_wide/. Intrinsik aus <bild>_intrinsics/ oder lowres_wide_intrinsics/
    (*.pincam: w h fx fy cx cy), wird auf die Bildgroesse skaliert. Optional
    highres_depth/: Tiefe aus dem Faro-Laserscanner -> Genauigkeitspruefung.
    """
    root = Path(root)
    traj = np.loadtxt(root / "lowres_wide.traj", ndmin=2)
    c2ws = []
    for row in traj:
        w2c = np.eye(4)
        w2c[:3, :3], w2c[:3, 3] = axis_angle_to_R(row[1:4]), row[4:7]
        c2ws.append(np.linalg.inv(w2c))
    tr = Trajectory(np.round(traj[:, 0], 3), c2ws)
    img_dir = next((root / d for d in ("color", "wide", "vga_wide", "lowres_wide")
                    if _ts_files(root / d)), None)
    if img_dir is None:
        sys.exit(f"{root}: keine Bilder (color/, wide/, vga_wide/ oder lowres_wide/)")
    intr_dir = root / f"{img_dir.name}_intrinsics"
    intr = _ts_files(intr_dir if intr_dir.is_dir() else root / "lowres_wide_intrinsics", ".pincam")
    depth, conf = _ts_files(root / "lowres_depth"), _ts_files(root / "confidence")
    gt = _ts_files(root / "highres_depth")
    ki, kd = np.array(sorted(intr)), np.array(sorted(depth))
    frames = []
    for t, img in sorted(_ts_files(img_dir).items()):
        c2w = tr.at(t)
        k = _nearest(intr, ki, t, 0.2)
        if c2w is None or k is None:
            continue
        w, h, fx, fy, cx, cy = np.loadtxt(intr[k])
        f = {"src": str(img), "K": np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]),
             "K_wh": (int(w), int(h)), "c2w": c2w, "depth": None, "conf": None, "t": t}
        dk = _nearest(depth, kd, t, 0.02)
        if dk is not None:
            f["depth"] = str(depth[dk])
            f["conf"] = str(conf[dk]) if dk in conf else None
            if abs(dk - t) > 5e-4:                     # Tiefe minimal frueher/spaeter
                dc = tr.at(dk)
                if dc is not None:
                    f["depth_c2w"] = dc
        if t in gt:
            f["gt_depth"] = str(gt[t])
        frames.append(f)
    return frames


LOADERS = {"scanner3d": load_scanner3d, "record3d": load_record3d,
           "polycam": load_polycam, "nerfstudio": load_nerfstudio,
           "arkitscenes": load_arkitscenes}
# ARKit-Weltrahmen: Schwerkraft-ausgerichtet, +Y oben (sonst: aus den Daten schaetzen)
ARKIT_UP = {"scanner3d": True, "record3d": True, "polycam": True, "nerfstudio": False,
            "arkitscenes": False}


def detect_format(path):
    """Format + Wurzelordner finden (Exporte liegen oft eine Ebene tiefer)."""
    path = Path(path)
    cands = [path] + sorted(p for p in path.glob("*") if p.is_dir()) \
        + sorted(p for p in path.glob("*/*") if p.is_dir())
    for p in cands:
        if (p / "transforms.json").exists():
            return "nerfstudio", p
        if (p / "metadata.json").exists() and ((p / "rgbd").is_dir() or any(p.glob("*.exr"))):
            return "record3d", p
        if (p / "keyframes").is_dir() or (p / "corrected_cameras").is_dir():
            return "polycam", p
        if any(p.glob("frame_*.json")):
            return "scanner3d", p
        if (p / "lowres_wide.traj").exists():
            return "arkitscenes", p
    sys.exit(f"Kein bekanntes Aufnahmeformat in {path} gefunden "
             "(scanner3d / record3d / polycam / nerfstudio / arkitscenes).")


# ---- Keyframe-Auswahl ---------------------------------------------------------
def select_keyframes(frames, min_move=0.05, min_turn=5.0, max_frames=300, sharp=None):
    """Bewegungsfenster bilden (neues Fenster ab min_move m oder min_turn Grad),
    je Fenster das schaerfste Bild; danach gleichmaessig auf max_frames kappen."""
    frames = sorted(frames, key=lambda f: f["t"])
    if not frames:
        return []
    windows, cur, ref = [], [frames[0]], frames[0]
    for f in frames[1:]:
        move = np.linalg.norm(f["c2w"][:3, 3] - ref["c2w"][:3, 3])
        cosang = (np.trace(ref["c2w"][:3, :3].T @ f["c2w"][:3, :3]) - 1) / 2
        turn = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
        if move >= min_move or turn >= min_turn:
            windows.append(cur)
            cur, ref = [f], f
        else:
            cur.append(f)
    windows.append(cur)
    pick = [max(w, key=sharp) if (sharp and len(w) > 1) else w[len(w) // 2] for w in windows]
    if len(pick) > max_frames:
        pick = [pick[i] for i in np.linspace(0, len(pick) - 1, max_frames).round().astype(int)]
    return pick


# ---- Ausgabe ---------------------------------------------------------------
def group_cameras(frames, tol=0.005):
    """Gemeinsame Kamera, wenn alle Intrinsiken (je Bildgroesse) < tol relativ abweichen
    -- ARKit-Brennweiten schwanken durch den Autofokus minimal."""
    cams, groups = [], {}
    for f in frames:
        groups.setdefault(tuple(f["wh"]), []).append(f)
    for wh, fs in groups.items():
        P = np.array([[f["K"][0, 0], f["K"][1, 1], f["K"][0, 2], f["K"][1, 2]] for f in fs])
        med = np.median(P, 0)
        if np.all(np.abs(P - med) <= tol * med):
            cams.append({"model": "PINHOLE", "wh": wh, "params": med.tolist()})
            for f in fs:
                f["cam"] = len(cams)
        else:
            for f, p in zip(fs, P):
                cams.append({"model": "PINHOLE", "wh": wh, "params": p.tolist()})
                f["cam"] = len(cams)
    return cams


CAMERA_MODELS = {"SIMPLE_PINHOLE": (0, 3), "PINHOLE": (1, 4), "SIMPLE_RADIAL": (2, 4),
                 "RADIAL": (3, 5), "OPENCV": (4, 8), "OPENCV_FISHEYE": (5, 8),
                 "FULL_OPENCV": (6, 12), "FOV": (7, 5), "SIMPLE_RADIAL_FISHEYE": (8, 4),
                 "RADIAL_FISHEYE": (9, 5), "THIN_PRISM_FISHEYE": (10, 12)}


def write_colmap(sparse, cams, images, xyz, rgb, tracks):
    """COLMAP-Binaermodell. images: [{name, cam, w2c}], tracks: Liste je Punkt
    [(bildindex, u, v), ...] -- daraus entstehen POINTS2D und die Punkt-Tracks.

    Binaer statt Text: der aeltere pycolmap-SceneManager (gsplat <= 1.5) liest
    unter Python 3 nur die .bin-Dateien fehlerfrei.
    """
    sparse = Path(sparse)
    sparse.mkdir(parents=True, exist_ok=True)
    with open(sparse / "cameras.bin", "wb") as f:
        f.write(struct.pack("<Q", len(cams)))
        for i, c in enumerate(cams, 1):
            mid, npar = CAMERA_MODELS[c["model"]]
            f.write(struct.pack("<iiQQ", i, mid, int(c["wh"][0]), int(c["wh"][1])))
            f.write(struct.pack(f"<{npar}d", *c["params"][:npar]))
    p2d = [[] for _ in images]                       # je Bild: (u, v, point3D_id)
    trk = []
    for pid, tr in enumerate(tracks, 1):
        el = []
        for ii, u, v in tr:
            el.append((ii + 1, len(p2d[ii])))
            p2d[ii].append((u, v, pid))
        trk.append(el)
    with open(sparse / "images.bin", "wb") as f:
        f.write(struct.pack("<Q", len(images)))
        for i, im in enumerate(images, 1):
            q, t = R_to_qvec(im["w2c"][:3, :3]), im["w2c"][:3, 3]
            f.write(struct.pack("<i7di", i, *q, *t, im["cam"]))
            f.write(im["name"].encode() + b"\x00")
            pts = np.array(p2d[i - 1], dtype=[("x", "<f8"), ("y", "<f8"), ("id", "<i8")]) \
                if p2d[i - 1] else np.zeros(0, [("x", "<f8"), ("y", "<f8"), ("id", "<i8")])
            f.write(struct.pack("<Q", len(pts)))
            f.write(pts.tobytes())
    with open(sparse / "points3D.bin", "wb") as f:
        f.write(struct.pack("<Q", len(xyz)))
        buf = []
        for pid, (p, c, el) in enumerate(zip(xyz, rgb, trk), 1):
            buf.append(struct.pack("<Q3d3BdQ", pid, *map(float, p), *map(int, c), 0.01, len(el)))
            buf.append(struct.pack(f"<{2 * len(el)}i", *[v for e in el for v in e]))
        f.write(b"".join(buf))


def read_colmap_text(folder):
    """Minimaler Leser fuer cameras.txt + images.txt (Posen, keine Punkte)."""
    folder = Path(folder)
    cams = {}
    for line in (folder / "cameras.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            s = line.split()
            cams[int(s[0])] = {"model": s[1], "wh": (int(s[2]), int(s[3])),
                               "params": [float(v) for v in s[4:]]}
    images = {}
    lines = [l for l in (folder / "images.txt").read_text().splitlines()
             if not l.startswith("#")]
    for k in range(0, len(lines), 2):
        s = lines[k].split()
        if len(s) < 10:
            continue
        w2c = np.eye(4)
        w2c[:3, :3] = qvec_to_R([float(v) for v in s[1:5]])
        w2c[:3, 3] = [float(v) for v in s[5:8]]
        images[" ".join(s[9:])] = {"cam": int(s[8]), "w2c": w2c}
    return cams, images


def write_ply_points(path, xyz, rgb):
    hdr = ("ply\nformat binary_little_endian 1.0\n"
           f"element vertex {len(xyz)}\nproperty float x\nproperty float y\nproperty float z\n"
           "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    rec = np.empty(len(xyz), [("p", "<f4", 3), ("c", "u1", 3)])
    rec["p"], rec["c"] = xyz, rgb
    with open(path, "wb") as f:
        f.write(hdr.encode())
        f.write(rec.tobytes())


def lidar_points(frames, args, rng):
    """Je Frame: Trainingspunkte (mit Track) + Beitrag zur dichten Messwolke."""
    xyz_t, rgb_t, trk_t, cloud_x, cloud_c, errs = [], [], [], [], [], []
    n_cloud = 0
    for i, f in enumerate(frames):
        if not f.get("depth"):
            continue
        d = read_depth(f["depth"], f.get("depth_scale", args.depth_scale))
        conf = read_conf(f["conf"], d.shape) if f.get("conf") else None
        if f.get("gt_depth"):                         # Referenz (Laserscanner)
            errs.append(depth_errors(d, conf, f["gt_depth"], args.min_conf, args.max_depth))
        if f.get("depth_c2w") is not None:            # Tiefe zu leicht anderem Zeitpunkt
            xw, _ = backproject(d, f["K"], f["wh"], f["depth_c2w"], conf,
                                args.min_conf, args.max_depth)
            uv, z = project(xw, f["K"], np.linalg.inv(f["c2w"]))
            ok = (z > 0.05) & (uv[:, 0] >= 0) & (uv[:, 0] < f["wh"][0]) \
                & (uv[:, 1] >= 0) & (uv[:, 1] < f["wh"][1])
            xw, uv = xw[ok], uv[ok].astype(np.float32)
        else:
            xw, uv = backproject(d, f["K"], f["wh"], f["c2w"], conf,
                                 args.min_conf, args.max_depth)
        if not len(xw):
            continue
        with open_image(f["out"]) as im:
            img = np.asarray(im.convert("RGB"))
        ui = np.clip(uv[:, 0].astype(int), 0, img.shape[1] - 1)
        vi = np.clip(uv[:, 1].astype(int), 0, img.shape[0] - 1)
        col = img[vi, ui]
        sel = rng.choice(len(xw), min(args.points_per_frame, len(xw)), replace=False)
        xyz_t.append(xw[sel]); rgb_t.append(col[sel])
        trk_t += [[(i, float(u), float(v))] for u, v in uv[sel]]
        cloud_x.append(xw); cloud_c.append(col); n_cloud += len(xw)
        if n_cloud > 4_000_000:                       # Speicher begrenzen
            x, c = voxel_downsample(np.concatenate(cloud_x), np.concatenate(cloud_c),
                                    args.cloud_voxel)
            cloud_x, cloud_c, n_cloud = [x], [c], len(x)
    if not xyz_t:
        sys.exit("Keine LiDAR-Tiefe gefunden -- Export enthaelt keine Tiefenbilder? "
                 "(3d Scanner App: 'All Data' exportieren; Polycam: Raw Data)")
    cx, cc = voxel_downsample(np.concatenate(cloud_x), np.concatenate(cloud_c), args.cloud_voxel)
    ref = None
    if errs and sum(len(e) for e in errs):
        e = np.concatenate(errs)
        ref = {"frames": len(errs), "pixel": int(len(e)),
               "median_abs_cm": round(float(np.median(np.abs(e))) * 100, 2),
               "p90_abs_cm": round(float(np.percentile(np.abs(e), 90)) * 100, 2),
               "mittel_cm": round(float(np.mean(e)) * 100, 2),
               "hinweis": "iPad-LiDAR-Tiefe minus Laserscanner-Tiefe (hohe Konfidenz)"}
    return (np.concatenate(xyz_t), np.concatenate(rgb_t), trk_t, cx, cc, ref)


def depth_errors(depth, conf, gt_path, min_conf=2, max_depth=4.0):
    """LiDAR-Tiefe gegen hochaufgeloeste Referenztiefe (gleiche Kamera/Zeit), in m."""
    gt = read_depth(gt_path)
    Hd, Wd = depth.shape
    v, u = np.mgrid[0:Hd, 0:Wd]
    gu = ((u + 0.5) * gt.shape[1] / Wd).astype(int)   # Pixelzentrum im Referenzbild
    gv = ((v + 0.5) * gt.shape[0] / Hd).astype(int)
    g = gt[gv, gu]
    m = (depth > 0.05) & (depth < max_depth) & (g > 0.05) & np.isfinite(g)
    if conf is not None:
        m &= conf >= min_conf
    return (depth[m] - g[m]).astype(np.float32)


def build(out, frames, stills, cams, args, up, extra_report=None):
    """sparse/0 + Messwolke + Bericht schreiben. frames/stills tragen c2w, wh, cam."""
    out = Path(out)
    rng = np.random.default_rng(0)
    xyz, rgb, tracks, cloud_x, cloud_c, ref = lidar_points(frames, args, rng)
    if up is None:                                    # kein ARKit-Rahmen bekannt
        up = estimate_up(frames, cloud_x)
    images = [{"name": f["name"], "cam": f["cam"], "w2c": np.linalg.inv(f["c2w"])}
              for f in frames]
    kept_stills = []
    for s in stills:                                  # Fotos: Tiefe ueber Sichtbarkeit
        w2c = np.linalg.inv(s["c2w"])
        vis, uv = visible_points(xyz, s["K"], w2c, s["wh"], occluders=cloud_x)
        idx = np.flatnonzero(vis)
        if len(idx) < 50:
            print(f"  ! {s['name']}: sieht kaum LiDAR-Punkte ({len(idx)}) -- weggelassen")
            continue
        ii = len(images)
        images.append({"name": s["name"], "cam": s["cam"], "w2c": w2c})
        for k in idx:
            tracks[k].append((ii, float(uv[k, 0]), float(uv[k, 1])))
        kept_stills.append(s)
    sparse = out / "sparse" / "0"
    if sparse.exists():
        shutil.rmtree(sparse)
    write_colmap(sparse, cams, images, xyz, rgb, tracks)
    write_ply_points(out / "lidar_points.ply", cloud_x, cloud_c)

    dims = room_dimensions(cloud_x, up)
    centers = np.array([f["c2w"][:3, 3] for f in frames])
    report = {
        "frames": len(frames), "stills": len(kept_stills),
        "trainingspunkte_lidar": int(len(xyz)), "messwolke_punkte": int(len(cloud_x)),
        "messwolke_voxel_m": args.cloud_voxel, "up": [float(v) for v in up],
        "kameraweg_m": round(float(np.linalg.norm(np.diff(centers, axis=0), axis=1).sum()), 2),
        "raummasse_naeherung": dims,
        **({"lidar_vs_laserscanner": ref} if ref else {}),
        "hinweis": "Raummasse = robuste Huellmasse der LiDAR-Wolke (0,5-99,5 %), nur "
                   "aussagekraeftig, wenn Boden, Decke und alle Waende gescannt sind. "
                   "Genaue Masse in lidar_points.ply messen (CloudCompare). "
                   "Erwartbar +-1-3 cm; mit Laser-Entfernungsmesser gegenpruefen.",
    }
    report.update(extra_report or {})
    (out / "capture_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
    print(f"  {len(frames)} Frames + {len(kept_stills)} Fotos, {len(xyz):,} LiDAR-Trainingspunkte, "
          f"Messwolke {len(cloud_x):,} Punkte")
    print(f"  Raum (Naeherung): {dims['laenge_m']:.2f} x {dims['breite_m']:.2f} m, "
          f"Hoehe {dims['hoehe_m']:.2f} m")
    if ref:
        print(f"  LiDAR gegen Laserscanner: Median {ref['median_abs_cm']:.1f} cm, "
              f"90 % unter {ref['p90_abs_cm']:.1f} cm ({ref['frames']} Frames)")
    return report


def frame_record(f):
    return {"name": f["name"], "out": f["out"], "wh": list(f["wh"]), "K": f["K"].tolist(),
            "c2w": f["c2w"].tolist(), "depth": f.get("depth"), "conf": f.get("conf"),
            "depth_scale": f.get("depth_scale"), "t": f["t"],
            "depth_c2w": None if f.get("depth_c2w") is None else f["depth_c2w"].tolist(),
            "gt_depth": f.get("gt_depth")}


def from_record(r):
    f = dict(r)
    f["K"], f["c2w"], f["wh"] = np.array(r["K"]), np.array(r["c2w"]), tuple(r["wh"])
    if f.get("depth_scale") is None:
        f.pop("depth_scale")
    if f.get("depth_c2w") is not None:
        f["depth_c2w"] = np.array(f["depth_c2w"])
    return f


# ---- Befehle ----------------------------------------------------------------
def cmd_prepare(args):
    fmt, root = (args.format, Path(args.capture)) if args.format != "auto" \
        else detect_format(args.capture)
    root = root.resolve()
    print(f"== Format: {fmt} ({root})")
    frames = LOADERS[fmt](root)
    if not frames:
        sys.exit("Keine Frames mit Pose gefunden.")
    n_all = len(frames)
    sharp = None if args.no_sharpness else (lambda f: sharpness(f["src"]))
    frames = select_keyframes(frames, args.min_move, args.min_turn, args.max_frames, sharp)
    print(f"  {n_all} Frames gelesen -> {len(frames)} Keyframes")

    out = Path(args.out).resolve()
    imgdir = out / "images"
    if imgdir.exists():
        shutil.rmtree(imgdir)
    imgdir.mkdir(parents=True)
    for i, f in enumerate(frames):
        ext = Path(f["src"]).suffix.lower()
        f["name"] = f"f_{i:05d}{ext}"
        f["out"] = str(imgdir / f["name"])
        shutil.copyfile(f["src"], f["out"])
        f["wh"] = image_size(f["out"])
        if "K_wh" in f and tuple(f["K_wh"]) != tuple(f["wh"]):   # K auf echte Bildgroesse
            sx, sy = f["wh"][0] / f["K_wh"][0], f["wh"][1] / f["K_wh"][1]
            f["K"] = np.diag([sx, sy, 1.0]) @ f["K"]

    stills = []
    if args.stills:
        for p in sorted(Path(args.stills).iterdir()):
            if p.suffix.lower() not in IMG_EXT:
                continue
            name = f"s_{p.stem}.jpg"
            with open_image(p) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                if max(im.size) > args.still_max:      # auf Trainingsgroesse
                    r = args.still_max / max(im.size)
                    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
                im.save(imgdir / name, quality=95)
            stills.append(name)
        print(f"  {len(stills)} Fotos uebernommen (Posen erst mit 'refine')")
    (out / "frames.txt").write_text("\n".join(f["name"] for f in frames) + "\n")
    (out / "stills.txt").write_text("\n".join(stills) + ("\n" if stills else ""))

    up = [0.0, 1.0, 0.0] if ARKIT_UP[fmt] else None
    cams = group_cameras(frames)
    report = build(out, frames, [], cams, args, up,
                   {"format": fmt, "posen": "ARKit", "frames_gelesen": n_all})
    (out / "capture.json").write_text(json.dumps({
        "format": fmt, "up": report["up"], "frames": [frame_record(f) for f in frames],
        "stills": stills, "args": {k: v for k, v in vars(args).items() if k != "func"},
    }, indent=1))
    print(f"== fertig: {out}/sparse/0 (Posen: ARKit, metrisch)")
    return report


def estimate_up(frames, cloud=None):
    """Oben-Richtung ohne ARKit-Rahmen schaetzen.

    Achse: die Weltachse, zu der die Blickrichtungen am senkrechtesten stehen
    (man schaut ueberwiegend waagerecht). Vorzeichen: aus der Bild-unten-Richtung
    der Kameras (Querformat); bei Hochformat-Aufnahmen ist sie waagerecht, dann
    entscheidet die Punktwolke (am Boden liegen mehr Punkte als an der Decke).
    """
    Z = np.array([f["c2w"][:3, 2] for f in frames])
    Y = np.array([f["c2w"][:3, 1] for f in frames])
    ax = int(np.argmin(np.abs(Z).mean(0)))
    m = float(Y[:, ax].mean())
    if abs(m) > 0.3:
        sign = -np.sign(m)
    elif cloud is not None and len(cloud):
        h = cloud[:, ax]
        lo, hi = np.percentile(h, 1), np.percentile(h, 99)
        band = 0.1 * max(hi - lo, 1e-6)
        sign = 1.0 if (h < lo + band).sum() >= (h > hi - band).sum() else -1.0
    else:
        sign = 1.0
    up = np.zeros(3)
    up[ax] = sign
    return [float(v) for v in up]


def cmd_known(args):
    """COLMAP-Modell mit den festen ARKit-Posen der Frames, Bild-/Kamera-IDs aus
    der COLMAP-Datenbank (Voraussetzung fuer point_triangulator)."""
    import sqlite3
    out = Path(args.out)
    st = json.loads((out / "capture.json").read_text())
    frames = {r["name"]: from_record(r) for r in st["frames"]}
    db = sqlite3.connect(args.database)
    rows = db.execute("SELECT image_id, name, camera_id FROM images").fetchall()
    db.close()
    known = Path(args.known)
    known.mkdir(parents=True, exist_ok=True)
    cams, lines = {}, []
    for iid, name, cid in sorted(rows):
        f = frames.get(name)
        if f is None:                                   # Foto -> spaeter registrieren
            continue
        K = f["K"]
        cams.setdefault(cid, (f["wh"], []))[1].append([K[0, 0], K[1, 1], K[0, 2], K[1, 2]])
        w2c = np.linalg.inv(f["c2w"])
        q = R_to_qvec(w2c[:3, :3])
        lines.append(f"{iid} " + " ".join(f"{v:.12f}" for v in (*q, *w2c[:3, 3]))
                     + f" {cid} {name}\n\n")
    with open(known / "cameras.txt", "w") as fh:
        for cid, (wh, P) in sorted(cams.items()):
            p = np.median(np.array(P), 0)
            fh.write(f"{cid} PINHOLE {wh[0]} {wh[1]} " + " ".join(f"{v:.6f}" for v in p) + "\n")
    (known / "images.txt").write_text("".join(lines))
    (known / "points3D.txt").write_text("")
    print(f"  Modell mit {len(lines)} festen ARKit-Posen: {known}")


def cmd_refine(args):
    out = Path(args.out)
    st = json.loads((out / "capture.json").read_text())
    for k, v in st["args"].items():                  # Parameter aus prepare uebernehmen
        if k not in ("out", "sfm") and not hasattr(args, k):
            setattr(args, k, v)
    frames = [from_record(r) for r in st["frames"]]
    sfm_cams, sfm_imgs = read_colmap_text(args.sfm)

    reg = [f for f in frames if f["name"] in sfm_imgs]
    if len(reg) < 8:
        sys.exit(f"SfM hat nur {len(reg)} ARKit-Frames registriert -- zu wenig fuer die "
                 "Ausrichtung. Ohne 'refine' (ARKit-Posen) trainieren.")
    src = np.array([np.linalg.inv(sfm_imgs[f["name"]]["w2c"])[:3, 3] for f in reg])
    dst = np.array([f["c2w"][:3, 3] for f in reg])
    s, R, t, res, keep = robust_umeyama(src, dst)
    rms = float(np.sqrt(np.mean(res[keep] ** 2)))
    print(f"== SfM -> ARKit: {len(reg)}/{len(frames)} Frames, Massstab {s:.4f}, "
          f"RMS {rms * 100:.1f} cm, {int((~keep).sum())} Ausreisser")
    if rms > args.max_rms:
        sys.exit(f"Ausrichtung zu ungenau (RMS {rms * 100:.1f} cm > {args.max_rms * 100:.0f} cm) "
                 "-- SfM vermutlich zerfallen. Ohne 'refine' trainieren.")

    S = np.eye(4)
    S[:3, :3], S[:3, 3] = R, t

    def aligned_c2w(w2c):                            # SfM-Pose -> metrischer ARKit-Rahmen
        c2w = np.linalg.inv(w2c)
        c2w[:3, 3] = s * c2w[:3, 3]
        return S @ c2w

    cams, cam_ids = [], {}

    def sfm_cam(cid):
        if cid not in cam_ids:
            cams.append(dict(sfm_cams[cid]))
            cam_ids[cid] = len(cams)
        return cam_ids[cid]

    n_ref = 0
    for f in frames:
        if f["name"] in sfm_imgs and keep[[g["name"] for g in reg].index(f["name"])]:
            im = sfm_imgs[f["name"]]
            f["c2w"] = aligned_c2w(im["w2c"])
            f["cam"] = sfm_cam(im["cam"])
            n_ref += 1
        else:                                          # ARKit-Pose + ARKit-Intrinsik behalten
            cams.append({"model": "PINHOLE", "wh": tuple(f["wh"]),
                         "params": [f["K"][0, 0], f["K"][1, 1], f["K"][0, 2], f["K"][1, 2]]})
            f["cam"] = len(cams)
    stills = []
    for name in st["stills"]:
        if name not in sfm_imgs:
            print(f"  ! Foto {name} nicht registriert -- weggelassen")
            continue
        im = sfm_imgs[name]
        c = sfm_cams[im["cam"]]
        p = c["params"]
        fx, fy, cx, cy = (p[0], p[0], p[1], p[2]) if c["model"] in ONE_FOCAL \
            else (p[0], p[1], p[2], p[3])
        stills.append({"name": name, "c2w": aligned_c2w(im["w2c"]), "wh": c["wh"],
                       "K": np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]),
                       "cam": sfm_cam(im["cam"])})
    build(out, frames, stills, cams, args, st["up"],
          {"format": st["format"], "posen": "COLMAP-SfM, an ARKit ausgerichtet",
           "ausrichtung": {"massstab": round(s, 5), "rms_cm": round(rms * 100, 2),
                           "frames_verfeinert": n_ref, "ausreisser": int((~keep).sum())}})
    print(f"== fertig: {out}/sparse/0 (verfeinert, metrisch)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="Aufnahme -> Datensatz mit ARKit-Posen")
    p.add_argument("capture", help="entpackter App-Export (Ordner)")
    p.add_argument("out")
    p.add_argument("--format", default="auto", choices=["auto", *LOADERS])
    p.add_argument("--stills", help="Ordner mit hochaufgeloesten Fotos (JPG/HEIC)")
    p.add_argument("--max-frames", type=int, default=300)
    p.add_argument("--min-move", type=float, default=0.05, help="m bis zum naechsten Keyframe")
    p.add_argument("--min-turn", type=float, default=5.0, help="Grad bis zum naechsten Keyframe")
    p.add_argument("--no-sharpness", action="store_true", help="ohne Schaerfe-Auswahl (schneller)")
    p.add_argument("--points-per-frame", type=int, default=1500,
                   help="LiDAR-Trainingspunkte je Frame (Init + Tiefen-Loss)")
    p.add_argument("--min-conf", type=int, default=2, help="ARKit-Konfidenz 0..2 (2 = hoch)")
    p.add_argument("--max-depth", type=float, default=4.0, help="LiDAR-Tiefe bis (m)")
    p.add_argument("--depth-scale", type=float, default=0.001, help="PNG-Tiefe -> m (mm: 0.001)")
    p.add_argument("--cloud-voxel", type=float, default=0.01, help="Raster der Messwolke (m)")
    p.add_argument("--still-max", type=int, default=2400, help="lange Kante der Fotos (px)")
    p.set_defaults(func=cmd_prepare)
    r = sub.add_parser("refine", help="SfM-Posen (inkl. Fotos) metrisch an ARKit haengen")
    r.add_argument("out", help="Ausgabeordner von prepare")
    r.add_argument("sfm", help="COLMAP-Modell als TXT (cameras.txt, images.txt)")
    r.add_argument("--max-rms", type=float, default=0.08,
                   help="max. Ausrichtungsfehler SfM->ARKit (m)")
    r.set_defaults(func=cmd_refine)
    k = sub.add_parser("known", help="COLMAP-Modell mit festen ARKit-Posen (IDs aus der DB)")
    k.add_argument("out", help="Ausgabeordner von prepare")
    k.add_argument("database", help="COLMAP database.db nach feature_extractor")
    k.add_argument("known", help="Zielordner fuer cameras/images/points3D.txt")
    k.set_defaults(func=cmd_known)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
