#!/usr/bin/env python3
"""pellis_to_colmap.py -- COLMAP-Modell aus den Kameraparametern des Pellis-Datensatzes.

Pellis, Masiero, Betti, Tucci, Grussenmeyer (2025), Data in Brief 60,
doi 10.1016/j.dib.2025.111661, Daten Zenodo 14626611 (CC BY 4.0).
Je Gebaeude liegen zwei Textdateien bei (Format am Beispiel 5_CB geprueft):

  *_interior_parameters.txt   (MATLAB-Syntax)
      K  = [f 0 W/2+dx; 0 f H/2+dy; 0 0 1];
      ks = [k1 k2 k3];        radial
      ps = [p1 p2];           tangential
  *_exterior_parameters.txt   (CSV)
      PhotoID,X,Y,K,OMEGA,PHI,KAPPA,R11..R33,Orientation
      X,Y,K = Projektionszentrum (Spalte "K" ist die dritte Koordinate),
      OMEGA,PHI,KAPPA in Grad, R = (Rx(omega) Ry(phi) Rz(kappa))^T.
  *_transformation_matrix.txt (3x4, MATLAB-Syntax)
      [sR | t]: Aehnlichkeitstransformation vom Kamerasystem (lokal, Y oben) ins
      System der Punktwolke (Z oben). Bei 5_CB: s = 1.3441, R orthonormal (Abw. 5e-7).
      Mit --transform werden die Posen in das System der Punktwolke gebracht:
      C' = sR C + t,  R_cam' = R_cam R^T  (s faellt bei der Projektion heraus).

Konvention (aus den Daten abgeleitet, Projektion gegen die Punktwolke steht noch aus):
  R ist world->camera in photogrammetrischer Kamerabasis (Blick entlang -Z, y nach oben).
  -> OpenCV/COLMAP:  R_cv = diag(1,-1,-1) @ R,  t = -R_cv @ C.
  Mit --no-flip wird R unveraendert uebernommen (falls die Projektionsprobe das verlangt).
  Mit --orientation-roll DEG werden Fotos mit Orientation = 1 um DEG Grad um die optische Achse
  korrigiert (5_CB: Bilddateien sind aufrecht quer, die Posen enthalten aber KAPPA +-90; am
  Uebergang 039 -> 040 springt die Rolle um +89,6 Grad, Korrektur -90 macht ihn ~0).
  Mit --invert-transform wird die Matrix als Punktwolke -> Kamerasystem gelesen und invertiert
  (welche Richtung stimmt, entscheidet scripts/pellis_posecheck.py an Fotos + Punktwolke).

Die Verzeichnung (k1,k2,k3,p1,p2) kann COLMAP-PINHOLE nicht abbilden. Mit --images
werden die Fotos mit OpenCV entzerrt (gleiche K) und als PINHOLE geschrieben;
ohne --images entsteht nur das Kameramodell (Probe/Trockenlauf).

  *_point_cloud.txt (Ordner 2_PointCloud, bei 5_CB 0,94 GB)
      Kopfzeile "//X Y Z R G B label Nx Ny Nz", dann eine Zeile je Punkt, Leerzeichen.
      Liegt im System der Punktwolke -> nur zusammen mit --transform als Initwolke nutzen.

Erzeugt:
  <out>/sparse/0/cameras.txt   (PINHOLE)
  <out>/sparse/0/images.txt    (world->camera, OpenCV-Konvention)
  <out>/sparse/0/points3D.txt  (mit --cloud: Stichprobe der Referenzwolke mit RGB, sonst leer)
  <out>/sparse/0/*.bin         (dasselbe binaer -- der COLMAP-Leser von gsplat 1.5.3,
                                rmbrualla/pycolmap, bricht im Textformat an der ersten
                                Leerzeile ab und liest daher nur die .bin-Dateien richtig)
  <out>/images/<PhotoID>.jpg   (nur mit --images, entzerrt)

Nutzung:
  python scripts/pellis_to_colmap.py 1_interior_parameters.txt 2_exterior_parameters.txt \
      out/5_CB [--transform 2_transformation_matrix.txt] [--cloud 1_point_cloud.txt] \
      [--init-points 300000] [--images <ordner_mit_fotos>] [--no-flip]
"""
import argparse
import csv
import os
import re
import struct
import sys

import numpy as np

FLIP = np.diag([1.0, -1.0, -1.0])


def parse_interior(path):
    """MATLAB-Zeilen K=[..]; ks=[..]; ps=[..] -> dict mit W,H,fx,fy,cx,cy,dist."""
    txt = open(path, encoding="utf-8").read()
    def block(name):
        m = re.search(rf"\b{name}\s*=\s*\[([^\]]*)\]", txt)
        if not m:
            sys.exit(f"FEHLER: '{name}' nicht in {path}")
        return m.group(1)
    rows = [r.split() for r in block("K").split(";")]
    if len(rows) != 3 or any(len(r) != 3 for r in rows):
        sys.exit(f"FEHLER: K ist keine 3x3-Matrix: {rows}")
    # cx/cy stehen als Ausdruck "W/2+dx" da -- W und H daraus ablesen
    mx = re.fullmatch(r"(\d+)/2([+-][\d.eE+-]+)?", rows[0][2])
    my = re.fullmatch(r"(\d+)/2([+-][\d.eE+-]+)?", rows[1][2])
    if not (mx and my):
        sys.exit(f"FEHLER: Bildmitte nicht als W/2+dx lesbar: {rows[0][2]}, {rows[1][2]}")
    W, H = int(mx.group(1)), int(my.group(1))
    cx = W / 2 + float(mx.group(2) or 0)
    cy = H / 2 + float(my.group(2) or 0)
    ks = [float(v) for v in block("ks").split()]
    ps = [float(v) for v in block("ps").split()]
    ks += [0.0] * (3 - len(ks))
    # OpenCV-Reihenfolge: k1 k2 p1 p2 k3
    dist = np.array([ks[0], ks[1], ps[0], ps[1], ks[2]])
    return dict(W=W, H=H, fx=float(rows[0][0]), fy=float(rows[1][1]),
                cx=cx, cy=cy, dist=dist)


def angles_to_R(omega, phi, kappa):
    o, p, k = np.radians([omega, phi, kappa])
    Rx = np.array([[1, 0, 0], [0, np.cos(o), -np.sin(o)], [0, np.sin(o), np.cos(o)]])
    Ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
    Rz = np.array([[np.cos(k), -np.sin(k), 0], [np.sin(k), np.cos(k), 0], [0, 0, 1]])
    return (Rx @ Ry @ Rz).T


def parse_exterior(path):
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            R = np.array([[float(r[f"R{i}{j}"]) for j in (1, 2, 3)] for i in (1, 2, 3)])
            dev = np.abs(R - angles_to_R(float(r["OMEGA"]), float(r["PHI"]),
                                         float(r["KAPPA"]))).max()
            if dev > 1e-6:
                sys.exit(f"FEHLER: {r['PhotoID']}: R passt nicht zu OMEGA/PHI/KAPPA "
                         f"(Abw. {dev:.2e}) -- Konvention anders als erwartet")
            C = np.array([float(r["X"]), float(r["Y"]), float(r["K"])])
            out.append(dict(name=r["PhotoID"], R=R, C=C,
                            orientation=r.get("Orientation", "").strip()))
    return out


def parse_transform(path):
    """3x4-Matrix [sR | t] -> (s, R, t); bricht ab, wenn sR keine Aehnlichkeit ist."""
    nums = [float(v) for v in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?",
                                          open(path, encoding="utf-8").read())]
    if len(nums) != 12:
        sys.exit(f"FEHLER: {path}: 12 Zahlen (3x4) erwartet, {len(nums)} gefunden")
    T = np.array(nums).reshape(3, 4)
    A, t = T[:, :3], T[:, 3]
    s = np.cbrt(np.linalg.det(A))
    R = A / s
    dev = np.abs(R @ R.T - np.eye(3)).max()
    if s <= 0 or dev > 1e-4:
        sys.exit(f"FEHLER: {path}: keine Aehnlichkeitstransformation (s={s:.4f}, Abw. {dev:.1e})")
    return s, R, t


def sample_cloud(path, n, seed=0, chunk=1_000_000):
    """Gleichverteilte Stichprobe von n Punkten (X Y Z R G B) aus der Text-Wolke.

    Liest blockweise (die Datei ist ~1 GB), Reservoir je Block; Speicher ~ n + chunk Zeilen.
    """
    rng = np.random.default_rng(seed)
    keep_xyz, keep_rgb, seen = np.empty((0, 3)), np.empty((0, 3), np.uint8), 0
    pool_keys = np.empty(0)
    with open(path, encoding="utf-8") as fh:
        while True:
            lines = [l for _, l in zip(range(chunk), fh)]
            if not lines:
                break
            lines = [l for l in lines if l.strip() and not l.lstrip().startswith(("//", "#"))]
            if not lines:
                continue
            a = np.loadtxt(lines, usecols=range(6), ndmin=2)
            xyz, rgb = a[:, :3], np.clip(a[:, 3:6], 0, 255).astype(np.uint8)
            # Zufallsschluessel je Punkt; die n kleinsten ueber alle Bloecke = Gleichverteilung
            keys = rng.random(len(xyz))
            pool_keys = np.concatenate([pool_keys, keys])
            keep_xyz = np.concatenate([keep_xyz, xyz])
            keep_rgb = np.concatenate([keep_rgb, rgb])
            if len(pool_keys) > n:
                sel = np.argpartition(pool_keys, n)[:n]
                pool_keys, keep_xyz, keep_rgb = pool_keys[sel], keep_xyz[sel], keep_rgb[sel]
            seen += len(xyz)
    return keep_xyz, keep_rgb, seen


def R_to_quat(R):
    """Rotationsmatrix -> Quaternion (w,x,y,z), COLMAP-Konvention."""
    t = np.trace(R)
    if t > 0:
        s = 0.5 / np.sqrt(t + 1.0)
        q = [0.25 / s, (R[2, 1] - R[1, 2]) * s, (R[0, 2] - R[2, 0]) * s, (R[1, 0] - R[0, 1]) * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q if q[0] >= 0 else -q


def write_binary(sparse, cam, images, xyz, rgb):
    """COLMAP-Binaerformat (cameras/images/points3D.bin), Spuren leer."""
    with open(os.path.join(sparse, "cameras.bin"), "wb") as fh:
        fh.write(struct.pack("<Q", 1))
        fh.write(struct.pack("<iiQQ", 1, 1, cam["W"], cam["H"]))   # id 1, Modell 1 = PINHOLE
        fh.write(struct.pack("<4d", cam["fx"], cam["fy"], cam["cx"], cam["cy"]))
    with open(os.path.join(sparse, "images.bin"), "wb") as fh:
        fh.write(struct.pack("<Q", len(images)))
        for image_id, q, t, name in images:
            fh.write(struct.pack("<I4d3dI", image_id, *q, *t, 1))
            fh.write(name.encode() + b"\x00")
            fh.write(struct.pack("<Q", 0))                          # keine 2D-Punkte
    with open(os.path.join(sparse, "points3D.bin"), "wb") as fh:
        fh.write(struct.pack("<Q", len(xyz)))
        for i in range(len(xyz)):
            fh.write(struct.pack("<Q3d3BdQ", i + 1, *xyz[i], *rgb[i], 1.0, 0))


def find_image(folder, name):
    for ext in (".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG", ".tif", ".TIF"):
        p = os.path.join(folder, name + ext)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("interior")
    ap.add_argument("exterior")
    ap.add_argument("out")
    ap.add_argument("--transform", help="*_transformation_matrix.txt: Posen ins System der Punktwolke")
    ap.add_argument("--cloud", help="*_point_cloud.txt: Stichprobe als Initwolke (points3D.txt)")
    ap.add_argument("--init-points", type=int, default=300_000)
    ap.add_argument("--images", help="Ordner mit den Originalfotos (<PhotoID>.jpg)")
    ap.add_argument("--orientation-roll", type=float, default=0.0,
                    help="Rolle [Grad] fuer Fotos mit Orientation = 1 (5_CB: -90)")
    ap.add_argument("--invert-transform", action="store_true",
                    help="Matrix bildet Punktwolke -> Kamerasystem ab; vor Gebrauch invertieren")
    ap.add_argument("--no-flip", action="store_true",
                    help="R ohne Achsenumkehr uebernehmen (nur falls die Projektionsprobe es zeigt)")
    args = ap.parse_args()
    if args.cloud and not args.transform:
        sys.exit("FEHLER: --cloud liegt im System der Punktwolke -> --transform mit angeben")

    cam = parse_interior(args.interior)
    poses = parse_exterior(args.exterior)
    flip = np.eye(3) if args.no_flip else FLIP
    if args.transform:
        s_t, R_t, t_t = parse_transform(args.transform)
        if args.invert_transform:
            s_t, R_t, t_t = 1.0 / s_t, R_t.T, -(R_t.T @ t_t) / s_t
        for p in poses:
            p["C"] = s_t * R_t @ p["C"] + t_t
            p["R"] = p["R"] @ R_t.T
        print(f"   Transformation: s={s_t:.6f}, t={t_t.round(3)}")

    sparse = os.path.join(args.out, "sparse", "0")
    os.makedirs(sparse, exist_ok=True)
    with open(os.path.join(sparse, "cameras.txt"), "w") as fh:
        fh.write("# Camera list: CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        fh.write(f"1 PINHOLE {cam['W']} {cam['H']} {cam['fx']:.6f} {cam['fy']:.6f} "
                 f"{cam['cx']:.6f} {cam['cy']:.6f}\n")

    lines, records, missing, odd_size = [], [], [], []
    if args.images:
        import cv2
        Kcv = np.array([[cam["fx"], 0, cam["cx"]], [0, cam["fy"], cam["cy"]], [0, 0, 1]])
        img_out = os.path.join(args.out, "images")
        os.makedirs(img_out, exist_ok=True)
    for i, p in enumerate(poses, 1):
        Rcv = flip @ p["R"]
        if args.orientation_roll and p["orientation"] == "1":
            a = np.radians(args.orientation_roll)
            Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            Rcv = Rz @ Rcv
        t = -Rcv @ p["C"]
        q = R_to_quat(Rcv)
        fname = p["name"] + ".jpg"
        if args.images:
            src = find_image(args.images, p["name"])
            if src is None:
                missing.append(p["name"])
                continue
            img = cv2.imread(src, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
            h, w = img.shape[:2]
            if (w, h) != (cam["W"], cam["H"]):
                odd_size.append(f"{p['name']} {w}x{h} (Orientation={p['orientation']})")
                continue
            cv2.imwrite(os.path.join(img_out, fname), cv2.undistort(img, Kcv, cam["dist"]),
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
        records.append((i, q, t, fname))
        lines.append(f"{i} {q[0]:.9f} {q[1]:.9f} {q[2]:.9f} {q[3]:.9f} "
                     f"{t[0]:.6f} {t[1]:.6f} {t[2]:.6f} 1 {fname}")
        lines.append("")
    with open(os.path.join(sparse, "images.txt"), "w") as fh:
        fh.write("# Image list: IMAGE_ID, QW,QX,QY,QZ, TX,TY,TZ, CAMERA_ID, NAME\n")
        fh.write("\n".join(lines) + "\n")
    xyz, rgb = np.empty((0, 3)), np.empty((0, 3), np.uint8)
    with open(os.path.join(sparse, "points3D.txt"), "w") as fh:
        fh.write("# 3D point list: POINT3D_ID, X,Y,Z, R,G,B, ERROR, TRACK[]\n")
        if args.cloud:
            xyz, rgb, total = sample_cloud(args.cloud, args.init_points)
            for i in range(len(xyz)):
                fh.write(f"{i+1} {xyz[i,0]:.4f} {xyz[i,1]:.4f} {xyz[i,2]:.4f} "
                         f"{rgb[i,0]} {rgb[i,1]} {rgb[i,2]} 1.0\n")
            print(f"   Initwolke: {len(xyz):,} von {total:,} Punkten, "
                  f"min {xyz.min(0).round(2)} max {xyz.max(0).round(2)}")
    write_binary(sparse, cam, records, xyz, rgb)

    C = np.array([p["C"] for p in poses])
    print(f"-> COLMAP-Modell: {args.out}")
    print(f"   Kamera: PINHOLE {cam['W']}x{cam['H']}, f={cam['fx']:.2f}px, "
          f"c=({cam['cx']:.2f}, {cam['cy']:.2f}), Verzeichnung k1 k2 p1 p2 k3 = {cam['dist']}")
    print(f"   Posen: {len(poses)} gelesen, {len(lines) // 2} geschrieben")
    print(f"   Zentren min {C.min(0).round(2)}  max {C.max(0).round(2)}")
    if missing:
        print(f"   FEHLT ({len(missing)}): {', '.join(missing[:10])}")
    if odd_size:
        print(f"   ANDERE BILDGROESSE ({len(odd_size)}), uebersprungen: {'; '.join(odd_size[:5])}")


if __name__ == "__main__":
    main()
