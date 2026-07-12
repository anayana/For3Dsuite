#!/usr/bin/env python3
"""build_colmap.py -- COLMAP-Datensatz fuer 3D Gaussian Splatting aus E57.

3DGS braucht normalerweise COLMAP-SfM, um Kameraposen zu schaetzen. Hier liegen
die Posen exakt vor (E57-pinholeRepresentation) und eine dichte LiDAR-Wolke zur
Initialisierung -- wir schreiben das COLMAP-Modell also direkt, ohne SfM.

Erzeugt:
  <out>/images/sNNN_cMM.jpg            (Pinhole-Bilder, Nadir optional weggelassen)
  <out>/sparse/0/cameras.txt           (PINHOLE-Intrinsics)
  <out>/sparse/0/images.txt            (Extrinsics world->camera, OpenCV-Konvention)
  <out>/sparse/0/points3D.txt          (LiDAR-Initialwolke mit RGB)

Konvention (aus reproject_pano.py abgeleitet, dort visuell verifiziert):
  E57-Kamera: optische Achse = -Z, Bildachsen sx=+1, sy=-1.
  -> OpenCV-Kamerabasis in Welt = Spalten [R@(1,0,0), R@(0,-1,0), R@(0,0,-1)]
     also  R_c2w_cv = R_e57 @ diag(1,-1,-1).
  COLMAP will world->camera:  R = R_c2w_cv^T,  t = -R @ C   (C = Pose-Translation).

Nutzung:
  python scripts/build_colmap.py "data/renon/e57/*.e57" data/renon/colmap \
      [--init-points 300000] [--keep-nadir]
"""
import sys, os, re, json, glob, struct, argparse, shutil, subprocess
import numpy as np
import pye57

HERE = os.path.dirname(os.path.abspath(__file__))

def quat_to_R(q):
    w, x, y, z = q
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)],
        [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)]])

def R_to_quat(R):
    """Rotationsmatrix -> Quaternion (w,x,y,z), COLMAP-Konvention."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w = 0.25 * s; x = (R[2,1]-R[1,2])/s; y = (R[0,2]-R[2,0])/s; z = (R[1,0]-R[0,1])/s
    elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
        s = np.sqrt(1.0 + R[0,0]-R[1,1]-R[2,2]) * 2
        w = (R[2,1]-R[1,2])/s; x = 0.25*s; y = (R[0,1]+R[1,0])/s; z = (R[0,2]+R[2,0])/s
    elif R[1,1] > R[2,2]:
        s = np.sqrt(1.0 + R[1,1]-R[0,0]-R[2,2]) * 2
        w = (R[0,2]-R[2,0])/s; x = (R[0,1]+R[1,0])/s; y = 0.25*s; z = (R[1,2]+R[2,1])/s
    else:
        s = np.sqrt(1.0 + R[2,2]-R[0,0]-R[1,1]) * 2
        w = (R[1,0]-R[0,1])/s; x = (R[0,2]+R[2,0])/s; y = (R[1,2]+R[2,1])/s; z = 0.25*s
    q = np.array([w, x, y, z]); return q / np.linalg.norm(q)

CV = np.diag([1.0, -1.0, -1.0])   # E57-Kamera -> OpenCV-Kamera

def setup_id(path):
    m = re.search(r'(\d{2,3})', os.path.basename(path))
    return m.group(1) if m else "000"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("e57", nargs="+")
    ap.add_argument("out")
    ap.add_argument("--init-points", type=int, default=300000)
    ap.add_argument("--keep-nadir", action="store_true",
                    help="Nadir-Kamera (Bild 6, meist maskiert) NICHT weglassen")
    ap.add_argument("--per-setup-points", type=int, default=100000,
                    help="LiDAR-Punkte je Setup vor Zusammenfuehrung")
    args = ap.parse_args()

    files = sorted({f for pat in args.e57 for f in glob.glob(pat)})
    if not files:
        sys.exit("Keine E57 gefunden.")

    out = args.out
    imgdir = os.path.join(out, "images")
    sparse = os.path.join(out, "sparse", "0")
    os.makedirs(imgdir, exist_ok=True); os.makedirs(sparse, exist_ok=True)

    # 1) Bilder + Posen je Setup extrahieren (nutzt vorhandenes Skript)
    tmp = os.path.join(out, "_tmp")
    cam_params = None
    images_lines = []
    img_id = 0
    rng = np.random.default_rng(0)
    all_pts, all_col = [], []

    for f in files:
        sid = setup_id(f)
        d = os.path.join(tmp, sid)
        subprocess.run([sys.executable, os.path.join(HERE, "e57_extract_images.py"), f, d], check=True)
        stem = os.path.splitext(os.path.basename(f))[0]
        poses = json.load(open(os.path.join(d, f"{stem}_poses.json")))

        for e in poses:
            if e.get("representation") != "pinholeRepresentation" or "file" not in e:
                continue
            cam_idx = e["index"]
            if not args.keep_nadir and cam_idx == 6:      # Nadir = maskierte Kamera
                continue
            ph = e["pinhole"]
            fpx = ph["focalLength"] / ph["pixelWidth"]
            cx, cy = ph["principalPointX"], ph["principalPointY"]
            W, H = e["width"], e["height"]
            if cam_params is None:
                cam_params = (W, H, fpx, cx, cy)

            q = e["pose"]["quaternion_wxyz"]; C = np.array(e["pose"]["translation_xyz"], float)
            R_c2w_cv = quat_to_R(q) @ CV
            R_w2c = R_c2w_cv.T
            tvec = -R_w2c @ C
            qw, qx, qy, qz = R_to_quat(R_w2c)

            img_id += 1
            name = f"s{sid}_c{cam_idx:02d}.jpg"
            shutil.copyfile(os.path.join(d, e["file"]), os.path.join(imgdir, name))
            images_lines.append(
                f"{img_id} {qw:.9f} {qx:.9f} {qy:.9f} {qz:.9f} "
                f"{tvec[0]:.6f} {tvec[1]:.6f} {tvec[2]:.6f} 1 {name}")
            images_lines.append("")   # leere POINTS2D-Zeile (fuer 3DGS nicht noetig)

        # LiDAR-Punkte dieses Setups (ROH-E57-Weltkoordinaten) fuer die Init-Wolke
        e57 = pye57.E57(f)
        scan = e57.read_scan(0, ignore_missing_fields=True, colors=True)
        x = scan["cartesianX"]; y = scan["cartesianY"]; z = scan["cartesianZ"]
        r = scan["colorRed"]; g = scan["colorGreen"]; b = scan["colorBlue"]
        k = min(args.per_setup_points, x.size)
        idx = rng.choice(x.size, k, replace=False)
        all_pts.append(np.stack([x[idx], y[idx], z[idx]], 1))
        all_col.append(np.stack([r[idx], g[idx], b[idx]], 1).astype(np.uint8))
        print(f"  Setup {sid}: {img_id} Bilder gesamt, +{k:,} Initpunkte")

    W, H, fpx, cx, cy = cam_params
    with open(os.path.join(sparse, "cameras.txt"), "w") as fh:
        fh.write("# Camera list: CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        fh.write(f"1 PINHOLE {W} {H} {fpx:.6f} {fpx:.6f} {cx:.6f} {cy:.6f}\n")

    with open(os.path.join(sparse, "images.txt"), "w") as fh:
        fh.write("# Image list: IMAGE_ID, QW,QX,QY,QZ, TX,TY,TZ, CAMERA_ID, NAME\n")
        fh.write("\n".join(images_lines) + "\n")

    pts = np.concatenate(all_pts); col = np.concatenate(all_col)
    if pts.shape[0] > args.init_points:
        sel = rng.choice(pts.shape[0], args.init_points, replace=False)
        pts, col = pts[sel], col[sel]
    with open(os.path.join(sparse, "points3D.txt"), "w") as fh:
        fh.write("# 3D point list: POINT3D_ID, X,Y,Z, R,G,B, ERROR, TRACK[]\n")
        for i in range(pts.shape[0]):
            fh.write(f"{i+1} {pts[i,0]:.4f} {pts[i,1]:.4f} {pts[i,2]:.4f} "
                     f"{col[i,0]} {col[i,1]} {col[i,2]} 1.0\n")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n-> COLMAP-Modell: {out}")
    print(f"   Kameras: 1 (PINHOLE {W}x{H}, f={fpx:.1f}px)")
    print(f"   Bilder: {img_id}")
    print(f"   Initpunkte: {pts.shape[0]:,}")

if __name__ == "__main__":
    main()
