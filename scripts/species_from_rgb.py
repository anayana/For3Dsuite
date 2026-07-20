#!/usr/bin/env python3
"""species_from_rgb.py -- Baumartenerkennung aus RGB (Rinde/Stamm-Textur+Farbe).

Trainiert und validiert einen Klassifikator auf den FinnWoodlands-Stammsegmenten
(COCO-Panoptic-Masken mit echten Labels Fichte/Birke/Kiefer). Merkmale je Stamm:
Farbstatistik (RGB/HSV, beleuchtungsrobuste Farbverhaeltnisse) + Rindentextur
(Sobel-Gradienten, Horizontal/Vertikal-Verhaeltnis -> Birken-Lentizellen).

Hinweis: die offizielle val-Teilung enthaelt nur Fichte -> unbrauchbar fuer eine
Mehrklassen-Validierung. Daher stratifizierter Hold-out-Split ueber die
train-Segmente (alle 3 Arten).

  python scripts/species_from_rgb.py --train    # Dataset bauen, trainieren, validieren
  (Modell -> data/species_model.pkl, Report -> data/species_report.json)
"""
import argparse
import json
import os
import pickle
from collections import Counter

import cv2
import numpy as np

FW = "data/FinnWoodlands"
SPECIES = {6: "Fichte", 7: "Birke", 8: "Kiefer"}   # COCO-category_id -> Art (dt.)
MIN_PIXELS = 300


def decode_panoptic(png_path):
    """COCO-Panoptic-PNG -> Segment-ID-Karte (id = R + 256*G + 256^2*B)."""
    p = cv2.imread(png_path, cv2.IMREAD_COLOR)          # BGR
    p = p[:, :, ::-1].astype(np.int64)                  # -> RGB
    return p[:, :, 0] + 256 * p[:, :, 1] + 256 * 256 * p[:, :, 2]


def features(rgb, mask):
    """Merkmalsvektor aus den maskierten Stammpixeln + Textur der Bounding-Box."""
    ys, xs = np.where(mask)
    if len(xs) < MIN_PIXELS:
        return None
    px = rgb[ys, xs].astype(np.float32)                 # (n,3) RGB
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    s = px.sum(1) + 1e-6
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[ys, xs].astype(np.float32)
    feat = []
    feat += list(px.mean(0)) + list(px.std(0))                      # RGB mean/std (6)
    feat += list(hsv.mean(0)) + list(hsv.std(0))                    # HSV mean/std (6)
    feat += [np.percentile(px.mean(1), q) for q in (10, 50, 90)]    # Helligkeit (3)
    feat += [(r/s).mean(), (g/s).mean(), (b/s).mean()]             # Farbverhaeltnisse (3)
    feat += [(r/(g+1e-6)).mean(), (b/(g+1e-6)).mean()]             # R/G, B/G (2)
    # Textur auf der Bounding-Box (Graustufen), gewichtet mit der Maske
    y0, y1, x0, x1 = ys.min(), ys.max()+1, xs.min(), xs.max()+1
    crop = cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY).astype(np.float32)
    m = mask[y0:y1, x0:x1]
    gx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
    gmag = np.hypot(gx, gy)
    mm = m & (gmag < 1e4)
    if mm.sum() < 20:
        return None
    ex, ey = np.abs(gx[mm]).mean(), np.abs(gy[mm]).mean()
    feat += [gmag[mm].mean(), gmag[mm].std(),
             ex / (ey + 1e-6),                                      # horiz/vert (Birke!)
             float((gmag[mm] > gmag[mm].mean()).mean())]           # Kantenanteil
    return np.array(feat, np.float32)


def build_dataset(split="train"):
    d = json.load(open(f"{FW}/forest_coco_panoptic_{split}.json"))
    X, y, groups = [], [], []
    bark_px = []                                         # fuer die globale Rinden-Farbstatistik
    for ann in d["annotations"]:
        stem = os.path.splitext(os.path.basename(ann["file_name"]))[0]
        seg2cat = {s["id"]: s["category_id"] for s in ann["segments_info"]}
        wanted = {sid: SPECIES[c] for sid, c in seg2cat.items() if c in SPECIES}
        if not wanted:
            continue
        rgb = cv2.imread(f"{FW}/rgb/{split}/{stem}.jpg")
        if rgb is None:
            continue
        rgb = rgb[:, :, ::-1]                            # BGR->RGB
        idmap = decode_panoptic(f"{FW}/annotations/{split}/forest_coco_panoptic/{stem}.png")
        for sid, sp in wanted.items():
            mask = idmap == sid
            f = features(rgb, mask)
            if f is not None:
                X.append(f); y.append(sp); groups.append(stem)
                ys, xs = np.where(mask)
                take = np.random.default_rng(0).choice(len(xs), min(500, len(xs)), replace=False)
                bark_px.append(rgb[ys[take], xs[take]].astype(np.float32))
    bark = np.concatenate(bark_px) if bark_px else np.zeros((1, 3), np.float32)
    stats = {"mean": bark.mean(0).tolist(), "std": bark.std(0).tolist()}
    return np.array(X), np.array(y), np.array(groups), stats


def train():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import StratifiedGroupKFold

    print("Baue Datensatz aus FinnWoodlands (train-Segmente) ...")
    X, y, groups, bark_stats = build_dataset("train")
    print(f"{len(X)} Stammsegmente mit Merkmalen: {dict(Counter(y))}")

    # Gruppiert nach Bild splitten (kein Bildleck zwischen Train/Test)
    sgkf = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=0)
    tr, te = next(sgkf.split(X, y, groups))
    clf = RandomForestClassifier(n_estimators=300, max_depth=None,
                                 class_weight="balanced", random_state=0, n_jobs=-1)
    clf.fit(X[tr], y[tr])
    pred = clf.predict(X[te])
    labels = ["Fichte", "Birke", "Kiefer"]
    cm = confusion_matrix(y[te], pred, labels=labels)
    acc = float((pred == y[te]).mean())
    print(f"\nHold-out ({len(te)} Segmente aus separaten Bildern): "
          f"Genauigkeit {acc:.1%}")
    print("Konfusionsmatrix (Zeile=wahr, Spalte=erkannt):")
    print("            " + "  ".join(f"{l:>7}" for l in labels))
    for i, l in enumerate(labels):
        print(f"  {l:>7} " + "  ".join(f"{v:7d}" for v in cm[i]))
    print("\n" + classification_report(y[te], pred, labels=labels, digits=3))

    # Finales Modell auf ALLEN Daten fuer die Anwendung
    clf_full = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                      random_state=0, n_jobs=-1).fit(X, y)
    os.makedirs("data", exist_ok=True)
    with open("data/species_model.pkl", "wb") as fh:
        pickle.dump({"model": clf_full, "labels": labels, "bark_stats": bark_stats}, fh)
    report = {
        "n_segmente": len(X),
        "verteilung": dict(Counter(y.tolist())),
        "holdout_genauigkeit": round(acc, 3),
        "konfusionsmatrix": {"labels": labels, "matrix": cm.tolist()},
        "merkmale": X.shape[1],
        "quelle": "FinnWoodlands (Tampere Univ.), COCO-Panoptic-Stammlabels",
    }
    json.dump(report, open("data/species_report.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("-> data/species_model.pkl + data/species_report.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    args = ap.parse_args()
    if args.train:
        train()
    else:
        print(__doc__)
