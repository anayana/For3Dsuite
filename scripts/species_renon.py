#!/usr/bin/env python3
"""species_renon.py -- Baumart je Renon-Stamm aus den RGB-Fotos bestimmen.

Fuer jeden LiDAR-erkannten Stamm (stand_inventory.py) wird die Brusthoehen-
Position ueber die validierten COLMAP-Posen ins beste Pinhole-Foto projiziert,
ein Rinden-Streifen ausgeschnitten und mit dem FinnWoodlands-Modell
(species_from_rgb.py) klassifiziert. Schreibt Art + Konfidenz in die Inventur.

WICHTIG (Ehrlichkeit): Das Modell kennt nur Fichte/Birke/Kiefer (borealer
Trainingsdatensatz). Renon ist fichtendominiert; Laerche (Larix) ist NICHT
trainiert und wird zwangslaeufig fehlklassifiziert -> Ergebnis ist ein
Transfer-Experiment mit Domaenenluecke, keine gesicherte Kartierung.

  python scripts/species_renon.py viewer/data/renon_stand.json data/renon/colmap \
      [--montage data/renon/_species_check.png]
"""
import argparse
import json
import os
import pickle

import cv2
import numpy as np

from validate_colmap import quat_to_R, read_cameras, read_images


def best_view(cam, images, imgdir, P):
    """Bild waehlen, in dem der Punkt P am naechsten + gut im Bild liegt."""
    best = None
    for name, (q, t) in images.items():
        R = quat_to_R(q)
        Xc = R @ P + t
        z = Xc[2]
        if z <= 0.5:
            continue
        u = cam["fx"] * Xc[0] / z + cam["cx"]
        v = cam["fy"] * Xc[1] / z + cam["cy"]
        marg = 40
        if not (marg <= u < cam["W"]-marg and marg <= v < cam["H"]-marg):
            continue
        if best is None or z < best[0]:
            best = (z, name, u, v)
    return best


def bark_patch(rgb, u, v, stempx):
    """Vertikaler Rinden-Streifen um (u,v); Maske = Rechteck ~ Stammbreite."""
    H, W = rgb.shape[:2]
    hw = max(4, int(0.40 * stempx))        # halbe Breite (< Stamm, Rand vermeiden)
    hh = max(10, int(1.4 * stempx))        # halbe Hoehe (vertikaler Streifen)
    x0, x1 = max(0, int(u)-hw), min(W, int(u)+hw)
    y0, y1 = max(0, int(v)-hh), min(H, int(v)+hh)
    if x1-x0 < 6 or y1-y0 < 12:
        return None, None
    mask = np.zeros((H, W), bool)
    mask[y0:y1, x0:x1] = True
    return mask, (x0, y0, x1, y1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stand"); ap.add_argument("colmap")
    ap.add_argument("--model", default="data/species_model.pkl")
    ap.add_argument("--montage", default=None)
    args = ap.parse_args()

    import species_from_rgb as S
    mdl = pickle.load(open(args.model, "rb"))
    clf, labels = mdl["model"], mdl["labels"]
    tgt = mdl.get("bark_stats")                    # FinnWoodlands-Rinden-Farbstatistik

    sparse = os.path.join(args.colmap, "sparse", "0")
    cam = read_cameras(os.path.join(sparse, "cameras.txt"))
    images = read_images(os.path.join(sparse, "images.txt"))
    imgdir = os.path.join(args.colmap, "images")
    tex_cache = {}

    data = json.load(open(args.stand, encoding="utf-8"))
    trees = data["trees"]
    from collections import Counter

    # --- Durchlauf 1: beste Sicht + Rinden-Crop je Baum sammeln ---
    crops = []                                     # (tree, crop_rgb)
    for tr in trees:
        tr["Baumart"] = None; tr["Baumart_konfidenz"] = None
        bv = best_view(cam, images, imgdir, np.array(tr["e57"], float))
        if bv is None:
            continue
        z, name, u, v = bv
        if name not in tex_cache:
            im = cv2.imread(os.path.join(imgdir, name))
            tex_cache[name] = im[:, :, ::-1] if im is not None else None
        rgb = tex_cache[name]
        if rgb is None:
            continue
        stempx = cam["fx"] * (tr["BHD_cm"]/100.0) / z
        mask, box = bark_patch(rgb, u, v, stempx)
        if mask is None:
            continue
        x0, y0, x1, y1 = box
        crops.append((tr, rgb[y0:y1, x0:x1].astype(np.float32)))

    # --- Farb-/Beleuchtungsangleichung (Reinhard) Renon -> FinnWoodlands ---
    src_px = np.concatenate([c.reshape(-1, 3) for _, c in crops]) if crops else np.zeros((1, 3))
    src_mean, src_std = src_px.mean(0), src_px.std(0) + 1e-6
    if tgt:
        tmean, tstd = np.array(tgt["mean"]), np.array(tgt["std"])
        def transfer(c): return np.clip((c - src_mean) * (tstd/src_std) + tmean, 0, 255)
        print(f"Farbangleichung Renon->FinnWoodlands (Rinde): "
              f"Renon-Mittel {src_mean.round(1)} -> Ziel {tmean.round(1)}")
    else:
        def transfer(c): return c

    # --- Durchlauf 2: angleichen, Merkmale, klassifizieren ---
    tiles, done, votes = [], 0, Counter()
    for tr, crop in crops:
        tc = transfer(crop).astype(np.uint8)
        feat = S.features(tc, np.ones(tc.shape[:2], bool))
        if feat is None:
            continue
        proba = clf.predict_proba([feat])[0]
        k = int(proba.argmax()); sp = str(clf.classes_[k])
        tr["Baumart"] = sp
        tr["Baumart_konfidenz"] = round(float(proba[k]), 2)
        votes[sp] += 1; done += 1
        if args.montage and len(tiles) < 24:
            tile = cv2.resize(tc, (60, 160))
            lab = np.zeros((18, 60, 3), np.uint8)
            cv2.putText(lab, f"{sp[:3]} {proba[k]:.2f}", (2, 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)
            tiles.append(np.vstack([tile, lab]))

    # Bestandes-Artenzusammensetzung
    comp = {sp: round(100*n/done) for sp, n in votes.most_common()} if done else {}
    data.setdefault("stand", {})["artenzusammensetzung_rgb"] = {
        "anteile_prozent": comp,
        "n_klassifiziert": done,
        "modell": "FinnWoodlands-RGB (Fichte/Birke/Kiefer), 87% Hold-out-Genauigkeit",
        "hinweis": "Transfer boreal->subalpin; Laerche nicht im Modell. "
                   "Fichtendominanz erwartet (Standortdoku).",
    }
    json.dump(data, open(args.stand, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{done}/{len(trees)} Staemme klassifiziert. Artenanteile: {comp}")

    if args.montage and tiles:
        cols = 12
        rows = [np.hstack(tiles[i:i+cols] + [np.zeros_like(tiles[0])]*(cols-len(tiles[i:i+cols])))
                for i in range(0, len(tiles), cols)]
        cv2.imwrite(args.montage, np.vstack(rows)[:, :, ::-1])
        print(f"-> Kontroll-Montage: {args.montage}")


if __name__ == "__main__":
    main()
