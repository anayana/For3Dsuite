"""Synthetischer Raum als iPad-Aufnahme (3d-Scanner-App-Format) fuer Tests.

Ein Quader-Raum (4 x 2,5 x 3 m, +Y oben wie ARKit) mit Flicken-Textur wird per
Strahlverfolgung gerendert: RGB, LiDAR-Tiefe (16 bit mm, niedrig aufgeloest),
Konfidenz und ARKit-Posen (OpenGL-Konvention). Die Textur hat harte Kanten,
damit auch COLMAP-SIFT darauf Merkmale findet.

  python tests/synth_room.py <ordner> [--frames 40] [--size 480 360] [--stills 8]
"""
import argparse
import json
from pathlib import Path

import numpy as np

ROOM_LO = np.array([0.0, 0.0, 0.0])
ROOM_HI = np.array([4.0, 2.5, 3.0])
GL_TO_CV = np.diag([1.0, -1.0, -1.0, 1.0])


def _hash(ix, iy, face, scale):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (face * 83492791) ^ (scale * 2654435761)
    return (h & 0xFFFFFF).astype(np.float64) / 0xFFFFFF


def _value_noise(u, v, s, seed):
    """Glattes Wertrauschen (bilinear, smoothstep) mit s Zellen je Meter."""
    x, y = u * s, v * s
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    n00, n10 = _hash(ix, iy, seed, s), _hash(ix + 1, iy, seed, s)
    n01, n11 = _hash(ix, iy + 1, seed, s), _hash(ix + 1, iy + 1, seed, s)
    return (n00 * (1 - fx) + n10 * fx) * (1 - fy) + (n01 * (1 - fx) + n11 * fx) * fy


def texture(p, face):
    """Fraktales Rauschen, je Wandflaeche und Farbkanal anders -- eindeutige
    Nachbarschaften, auf denen SIFT verlaessliche Merkmale findet."""
    axes = [a for a in range(3) if a != face // 2]
    u, v = p[:, axes[0]], p[:, axes[1]]
    col = np.zeros((len(p), 3))
    for c in range(3):
        for s, w in ((3, 0.4), (9, 0.3), (27, 0.2), (61, 0.1)):
            col[:, c] += w * _value_noise(u, v, s, face * 3 + c + 1)
    col = (col - 0.5) * 2.2 + 0.5                       # Kontrast
    return (np.clip(col, 0, 1) * 255).astype(np.uint8)


def look_at(eye, target, up=(0, 1, 0)):
    """c2w in OpenCV-Konvention (x rechts, y unten, z Blick)."""
    z = np.asarray(target, float) - eye
    z /= np.linalg.norm(z)
    x = np.cross(z, up)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    c2w = np.eye(4)
    c2w[:3, :3] = np.stack([x, y, z], 1)
    c2w[:3, 3] = eye
    return c2w


def render(c2w, K, w, h):
    """RGB (h,w,3) und z-Tiefe (h,w) im Raum-Inneren."""
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    d_cam = np.stack([(u - K[0, 2]) / K[0, 0], (v - K[1, 2]) / K[1, 1], np.ones_like(u)], -1)
    d = d_cam.reshape(-1, 3) @ c2w[:3, :3].T
    o = c2w[:3, 3]
    with np.errstate(divide="ignore"):
        tb = np.where(d > 0, (ROOM_HI - o) / d, (ROOM_LO - o) / d)
    tb[~np.isfinite(tb)] = np.inf
    axis = np.argmin(tb, 1)
    t = tb[np.arange(len(d)), axis]
    p = o + d * t[:, None]
    face = axis * 2 + (d[np.arange(len(d)), axis] > 0)
    rgb = np.zeros((len(d), 3), np.uint8)
    for f in range(6):
        m = face == f
        rgb[m] = texture(p[m], f)
    z = t * d_cam.reshape(-1, 3)[:, 2]               # z-Tiefe = t * (d_cam . e_z)
    return rgb.reshape(h, w, 3), z.reshape(h, w)


def trajectory(n, seed=0):
    """Umlauf im Raum, Blick nach aussen auf die Waende (typischer Raumscan)."""
    rng = np.random.default_rng(seed)
    c = (ROOM_LO + ROOM_HI) / 2
    poses = []
    for i in range(n):
        a = 2 * np.pi * i / n
        eye = c + np.array([0.7 * np.cos(a), -0.1 + 0.15 * np.sin(3 * a), 0.5 * np.sin(a)])
        tilt = 0.8 * np.sin(5 * a) + 0.1 * rng.standard_normal()   # Boden + Decke
        tgt = eye + np.array([np.cos(a + 0.6), tilt, np.sin(a + 0.6)])
        poses.append(look_at(eye, tgt))
    return poses


def write_capture(folder, n=40, size=(480, 360), depth_size=(64, 48), stills=0,
                  still_size=(800, 600), seed=0):
    """Schreibt eine 3d-Scanner-App-artige Aufnahme. Rueckgabe: GT-Posen (OpenCV)."""
    from PIL import Image

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    w, h = size
    K = np.array([[0.85 * w, 0, w / 2], [0, 0.85 * w, h / 2], [0, 0, 1.0]])
    dw, dh = depth_size
    poses = trajectory(n, seed)
    for i, c2w in enumerate(poses):
        rgb, _ = render(c2w, K, w, h)
        Kd = np.diag([dw / w, dh / h, 1]) @ K
        _, z = render(c2w, Kd, dw, dh)
        Image.fromarray(rgb).save(folder / f"frame_{i:05d}.jpg", quality=95)
        Image.fromarray(np.round(z * 1000).astype(np.uint16)).save(folder / f"depth_{i:05d}.png")
        Image.fromarray(np.full((dh, dw), 2, np.uint8)).save(folder / f"conf_{i:05d}.png")
        gl = c2w @ GL_TO_CV                            # ARKit-Pose (OpenGL-Kamera)
        (folder / f"frame_{i:05d}.json").write_text(json.dumps({
            "cameraPoseARFrame": gl.reshape(-1).tolist(),     # zeilenweise
            "intrinsics": K.reshape(-1).tolist(), "time": i / 10.0}))
    still_poses = []
    if stills:
        sd = folder / "stills"
        sd.mkdir(exist_ok=True)
        sw, sh = still_size
        Ks = np.array([[0.8 * sw, 0, sw / 2], [0, 0.8 * sw, sh / 2], [0, 0, 1.0]])
        for j, c2w in enumerate(trajectory(stills, seed + 1)):
            c2w = c2w.copy()
            c2w[:3, 3] += [0.05, 0.02, -0.04]
            rgb, _ = render(c2w, Ks, sw, sh)
            Image.fromarray(rgb).save(sd / f"IMG_{j:04d}.jpg", quality=95)
            still_poses.append((f"s_IMG_{j:04d}.jpg", c2w, Ks, (sw, sh)))
    return {"frames": poses, "K": K, "stills": still_poses}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--size", type=int, nargs=2, default=[480, 360])
    ap.add_argument("--stills", type=int, default=0)
    a = ap.parse_args()
    write_capture(a.out, a.frames, tuple(a.size), stills=a.stills)
    print(f"synthetische Aufnahme: {a.out}")
