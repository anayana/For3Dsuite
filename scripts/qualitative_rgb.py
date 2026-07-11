#!/usr/bin/env python3
"""qualitative_rgb.py -- Baustein 4, Stufe 1: qualitative Auswertung je Baum aus RGB.

Zu jedem georeferenzierten Baum-Marker (yaw/pitch aus scene.json) wird ein
Kronen-Crop aus dem Equirectangular-Panorama gnomonisch reprojiziert und
klassisch (ohne Training, keine Blackbox) ausgewertet:

  * Farbindizes  ExG = 2g-r-b, GLI = (2G-R-B)/(2G+R+B)  (g,r,b = normalisiert)
  * Vitalitaetsproxy = Anteil gruener (vitaler) Kronenpixel; Gegenprobe = Anteil
    nicht-gruener Pixel (Verfaerbung/Trockenschaden/Totholz)
  * GLCM-Textur (Kontrast, Homogenitaet, Energie, Entropie, Korrelation) auf dem
    Grauwert-Crop -- Rindentextur/Kronenstruktur, artdiagnostisch nutzbar

Das Ergebnis wird an den Marker zurueckgeschrieben (georeferenziertes
Zustandsattribut), nicht ans Gesamtbild. Weil jeder Baum aus mehreren Setups
sichtbar ist, mehrere (scene, pano)-Paare uebergeben -> Aggregation ueber die
Ansichten (Mittel + Anzahl Ansichten) je Marker-ID.

Konvention wie markers_from_xyz.py / reproject_pano.py:
  yaw == Panorama-Laengengrad (atan2(dy,dx)),  pitch == Breitengrad (asin(dz/|d|)).

Nutzung:
  # eine Ansicht, Attribute in scene.json schreiben, Crops als Beleg ablegen
  python qualitative_rgb.py --scene scene.json --pano pano.jpg --write --out-crops crops/

  # mehrere Setups desselben Bestands -> Multi-View-Aggregation je Marker-ID
  python qualitative_rgb.py --scene s01.json --pano p01.jpg \
                            --scene s02.json --pano p02.jpg --write --csv vital.csv

Nur numpy + Pillow (wie die uebrige Pipeline); bewusst reproduzierbare Baseline.
Stufe 2 (CNN/ViT) und Stufe 3 (VLM zero-shot) sind separate, optionale Beine.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# --- Schwellen (Heuristik, als Parameter offengelegt) ------------------------
GLI_VITAL = 0.02      # GLI >= -> Pixel gilt als gruen/vital
SKY_MIN_LUM = 140     # helle Pixel ...
SKY_BLUE_BIAS = 6     # ... mit B deutlich > R,G  = Himmel -> aus Krone raus
SHADOW_MAX_LUM = 18   # fast schwarze Pixel (Schatten/Nadir) raus
GLCM_LEVELS = 16      # Grauwert-Quantisierung fuer die Co-Occurrence-Matrix


def dir_from_yawpitch(yaw_deg, pitch_deg):
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    return np.array([math.cos(p) * math.cos(y),
                     math.cos(p) * math.sin(y),
                     math.sin(p)], np.float64)


def crop_from_pano(pano, yaw, pitch, hfov, vfov, size):
    """Perspektivischer (gnomonischer) Ausschnitt um (yaw,pitch) aus Equirect."""
    H, W = pano.shape[:2]
    c = dir_from_yawpitch(yaw, pitch)
    right = np.cross(np.array([0.0, 0.0, 1.0]), c)
    n = np.linalg.norm(right)
    right = np.array([1.0, 0.0, 0.0]) if n < 1e-6 else right / n
    up = np.cross(c, right)

    u = ((np.arange(size) + 0.5) / size * 2 - 1) * math.tan(math.radians(hfov) / 2)
    v = (1 - (np.arange(size) + 0.5) / size * 2) * math.tan(math.radians(vfov) / 2)
    uu, vv = np.meshgrid(u, v)
    D = (c[None, None, :] + uu[..., None] * right[None, None, :]
         + vv[..., None] * up[None, None, :])
    D /= np.linalg.norm(D, axis=-1, keepdims=True)

    lon = np.arctan2(D[..., 1], D[..., 0])
    lat = np.arcsin(np.clip(D[..., 2], -1, 1))
    col = (lon + math.pi) / (2 * math.pi) * W - 0.5
    row = (math.pi / 2 - lat) / math.pi * H - 0.5
    ci = np.mod(np.round(col).astype(int), W)
    ri = np.clip(np.round(row).astype(int), 0, H - 1)
    return pano[ri, ci]


def crown_mask(rgb):
    """Kronenpixel = weder Himmel noch tiefer Schatten."""
    r, g, b = (rgb[..., i].astype(np.int32) for i in range(3))
    lum = rgb.mean(-1)
    sky = (lum >= SKY_MIN_LUM) & (b - r > SKY_BLUE_BIAS) & (b - g > SKY_BLUE_BIAS)
    shadow = lum <= SHADOW_MAX_LUM
    return ~(sky | shadow)


def color_indices(rgb, mask):
    """ExG/GLI-Mittel und Vitalanteil ueber die Kronenpixel."""
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    s = r + g + b + 1e-6
    rn, gn, bn = r / s, g / s, b / s
    exg = 2 * gn - rn - bn
    gli = (2 * g - r - b) / (2 * g + r + b + 1e-6)
    m = mask & np.isfinite(gli)
    if m.sum() < 16:
        return None
    vital = float((gli[m] >= GLI_VITAL).mean())
    return {
        "ExG_mean": round(float(exg[m].mean()), 4),
        "GLI_mean": round(float(gli[m].mean()), 4),
        "Vital_gruen": round(vital, 3),
        "Nichtgruen": round(1 - vital, 3),
        "Kronenpixel": int(m.sum()),
    }


def glcm_features(rgb, mask, levels=GLCM_LEVELS):
    """Symmetrische, richtungsgemittelte GLCM (d=1) + Haralick-Kennzahlen."""
    gray = rgb.astype(np.float64).mean(-1)
    q = np.clip((gray / 256 * levels).astype(np.int64), 0, levels - 1)
    valid = mask
    P = np.zeros((levels, levels), np.float64)
    # 0deg (0,1), 45deg (-1,1), 90deg (-1,0), 135deg (-1,-1)
    for dy, dx in ((0, 1), (-1, 1), (-1, 0), (-1, -1)):
        a = q[max(0, -dy):q.shape[0] - max(0, dy),
              max(0, -dx):q.shape[1] - max(0, dx)]
        b = q[max(0, dy):q.shape[0] - max(0, -dy),
              max(0, dx):q.shape[1] - max(0, -dx)]
        va = valid[max(0, -dy):valid.shape[0] - max(0, dy),
                   max(0, -dx):valid.shape[1] - max(0, dx)]
        vb = valid[max(0, dy):valid.shape[0] - max(0, -dy),
                   max(0, dx):valid.shape[1] - max(0, -dx)]
        vm = (va & vb).ravel()
        ai, bi = a.ravel()[vm], b.ravel()[vm]
        if ai.size == 0:
            continue
        idx = ai * levels + bi
        counts = np.bincount(idx, minlength=levels * levels).reshape(levels, levels)
        P += counts + counts.T  # symmetrisch
    total = P.sum()
    if total < 32:
        return None
    P /= total
    i = np.arange(levels)[:, None]
    j = np.arange(levels)[None, :]
    mu_i = (i * P).sum()
    mu_j = (j * P).sum()
    si = math.sqrt(((i - mu_i) ** 2 * P).sum()) or 1e-6
    sj = math.sqrt(((j - mu_j) ** 2 * P).sum()) or 1e-6
    contrast = float(((i - j) ** 2 * P).sum())
    homogen = float((P / (1 + (i - j) ** 2)).sum())
    energy = float((P ** 2).sum())
    entropy = float(-(P[P > 0] * np.log2(P[P > 0])).sum())
    corr = float(((i - mu_i) * (j - mu_j) * P).sum() / (si * sj))
    return {
        "GLCM_Kontrast": round(contrast, 3),
        "GLCM_Homogenitaet": round(homogen, 4),
        "GLCM_Energie": round(energy, 4),
        "GLCM_Entropie": round(entropy, 3),
        "GLCM_Korrelation": round(corr, 4),
    }


def stand_classify(agg):
    """Bestandesrelative Einstufung (robuste Ausreisser-Erkennung).

    Absolute Schadstufen aus einem einzelnen terrestrischen Kronen-Crop sind
    unzuverlaessig (Rindenanteil, Gegenlicht, Domaenenluecke) -- das warnt der
    Baustein selbst. Stufe 1 kann verlaesslich nur *auffaellige Abweichungen vom
    Bestand* markieren. Daher: Median/MAD des Gruenanteils ueber alle Baeume,
    Ausreisser nach unten = 'auffaellig' (Verfaerbung/Trockenschaden pruefen).
    Die Gegenprobe liefert crossvalidate_rgb_lidar.py (RGB <-> Struktur).
    """
    vals = np.array([r["Vital_gruen"] for r in agg.values()])
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) or 1e-6
    for r in agg.values():
        z = (r["Vital_gruen"] - med) / (1.4826 * mad)   # robuster z-Score
        r["Vital_zscore"] = round(z, 2)
        if z <= -1.5:
            r["Vitalitaet"] = "auffaellig"      # deutlich weniger gruen als Bestand
        elif z >= 1.0:
            r["Vitalitaet"] = "vital"
        else:
            r["Vitalitaet"] = "unauffaellig"
    return agg


def crop_geometry(mk, args):
    """Blickmitte + FOV; nutzt Hoehe/Distanz, wenn im Marker vorhanden."""
    attrs = mk.get("attributes", {})
    dist = attrs.get("Distanz_m")
    hoehe = attrs.get("Hoehe_m")
    pitch = mk["pitch"]
    if args.fov:
        return mk["yaw"], pitch, args.fov, args.fov
    if dist and hoehe and dist > 0.5:
        # Kronen-Winkelhoehe grob aus Baumhoehe/Distanz; Crop-Mitte nach oben
        ang = math.degrees(2 * math.atan((hoehe / 2) / dist))
        vfov = float(np.clip(ang * 1.4, 12, 70))
        pitch = pitch + min(vfov / 2, math.degrees(math.atan((hoehe / 2) / dist)))
        return mk["yaw"], float(np.clip(pitch, -85, 85)), vfov, vfov
    return mk["yaw"], pitch, 25.0, 25.0


def evaluate_view(scene_path, pano_path, out_crops, args):
    """Ein Setup: je Marker Crop auswerten -> {marker_id: attribut-dict}."""
    scene = json.loads(Path(scene_path).read_text(encoding="utf-8"))
    pano = np.asarray(Image.open(pano_path).convert("RGB"))
    if out_crops:
        Path(out_crops).mkdir(parents=True, exist_ok=True)
    results = {}
    for mk in scene.get("markers", []):
        yaw, pitch, hfov, vfov = crop_geometry(mk, args)
        crop = crop_from_pano(pano, yaw, pitch, hfov, vfov, args.size)
        mask = crown_mask(crop)
        ci = color_indices(crop, mask)
        if ci is None:
            continue
        tex = glcm_features(crop, mask) or {}
        rec = {**ci, **tex}
        results[mk["id"]] = rec
        if out_crops:
            Image.fromarray(crop).save(Path(out_crops) / f"{mk['id']}.jpg", quality=88)
    return scene, results


def aggregate(per_view):
    """Mittelung je Marker-ID ueber alle Ansichten (Multi-View)."""
    keys = set().union(*(r.keys() for r in per_view)) if per_view else set()
    agg = {}
    for mid in keys:
        recs = [r[mid] for r in per_view if mid in r]
        merged = {}
        for field in recs[0]:
            vals = [r[field] for r in recs if field in r]
            merged[field] = round(float(np.mean(vals)), 4)
        merged["Ansichten"] = len(recs)
        agg[mid] = merged
    return stand_classify(agg)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", action="append", required=True,
                    help="scene.json (mehrfach fuer Multi-View)")
    ap.add_argument("--pano", action="append", required=True,
                    help="zugehoeriges Equirectangular-Bild (Reihenfolge wie --scene)")
    ap.add_argument("--size", type=int, default=192, help="Crop-Kantenlaenge px")
    ap.add_argument("--fov", type=float, default=None,
                    help="feste Crop-FOV in Grad (sonst aus Hoehe/Distanz geschaetzt)")
    ap.add_argument("--out-crops", help="Verzeichnis fuer Kronen-Crops (Beleg)")
    ap.add_argument("--csv", help="Ergebnis zusaetzlich als CSV")
    ap.add_argument("--write", action="store_true",
                    help="Attribute in die (erste) scene.json zurueckschreiben")
    args = ap.parse_args()

    if len(args.scene) != len(args.pano):
        sys.exit("Anzahl --scene und --pano muss uebereinstimmen")

    scenes, per_view = [], []
    for si, (sp, pp) in enumerate(zip(args.scene, args.pano)):
        crops = None
        if args.out_crops:
            crops = Path(args.out_crops) / (Path(sp).parent.name or f"view{si}")
        scene, res = evaluate_view(sp, pp, crops, args)
        scenes.append((sp, scene))
        per_view.append(res)
        print(f"{Path(sp).name}: {len(res)} Baeume ausgewertet")

    agg = aggregate(per_view)
    n_flag = sum(1 for r in agg.values() if r["Vitalitaet"] == "auffaellig")
    print(f"Aggregiert ueber {len(per_view)} Ansicht(en): {len(agg)} Baeume, "
          f"{n_flag} bestandesrelativ 'auffaellig' (weniger gruen als Median)")

    if args.csv:
        fields = ["marker_id"] + sorted({k for r in agg.values() for k in r})
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for mid, rec in agg.items():
                w.writerow({"marker_id": mid, **rec})
        print(f"-> {args.csv}")

    if args.write:
        sp, scene = scenes[0]
        for mk in scene.get("markers", []):
            if mk["id"] in agg:
                mk.setdefault("attributes", {}).update(agg[mk["id"]])
        Path(sp).write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"-> Attribute in {sp} geschrieben")


if __name__ == "__main__":
    main()
