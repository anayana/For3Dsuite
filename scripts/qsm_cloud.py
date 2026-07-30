#!/usr/bin/env python3
"""qsm_cloud.py -- Zylindermodell (QSM) je Baum aus einer Plot-Punktwolke.

Python-Gegenstueck zu qsm_tree.R/qsm_export.R (aRchi). Notwendig, weil aRchi aus
CRAN archiviert ist und auf diesem Rechner keine R-Umgebung laeuft -- und weil
aRchi Einzelbaum-Wolken erwartet, hier aber ein ganzer Bestand vorliegt.

Verfahren (Ringe entlang der Pfadlaenge, wie in TreeQSM/SimpleForest ueblich):
  1. Baumweise Punkte aus der ITCD-Segmentierung (itcd_cloud.py)
  2. HOLZFILTER (siehe unten), Voxel-Ausduennung
  3. Voxelgraph, kuerzeste Wege vom Stammfuss -> Pfadlaenge je Voxel
  4. Ringe konstanter Pfadlaenge, darin Zusammenhangskomponenten = Querschnitte
  5. je Querschnitt ein Zylinder zum Schwerpunkt des Elternquerschnitts;
     Verzweigungsordnung steigt beim Abzweig, nicht bei der Fortsetzung
     (Fortsetzung = punktreichster Kindquerschnitt)
  6. Radius: am STAMM (Ordnung 1) per Kreisfit in der achssenkrechten Ebene,
     an Aesten als Median-Abstand zur Achse

EHRLICHE EINORDNUNG -- der entscheidende Unterschied zu qsm_tree.R:
Dort liefert SYSSIFOSS eine MANUELL ANNOTIERTE Blatt-Holz-Trennung, das Modell
startet also auf gemessener Wahrheit. Fuer Renon gibt es die nicht. Der Holzfilter
hier ist eine Geometrie-Heuristik (lokale PCA: Holz ist linear/flaechig, Nadeln
sind isotrop) -- brauchbar am Stamm und an starken Aesten, unsicher im Feinreisig.
Fichtennadeln, die als Holz durchgehen, treiben die Radien feiner Zweige nach
oben; das Kronen-Holzvolumen ist damit eine OBERGRENZE. Stammvolumen und QSM-BHD
sind davon kaum betroffen (Kreisfit am dicht gescannten Stamm) -- was sie wert
sind, zeigt der Vergleich mit den anderen BHD-Verfahren (dbh_methods.py).

Ausgabe (Format wie platform/dev/seed_syssifoss.py, damit der Viewer es kennt):
  <out>.bin   float32 Start n*3, Ende n*3, Radius n, dann uint8 Ordnung n
  <out>.json  {count, order_max, ramp, off} + Metriken je Baum

  python scripts/qsm_cloud.py data/Renon/_analysis.npz data/Renon/itcd_combined.npz \\
      --stems data/Renon/trees_combined.csv --out data/Renon/qsm_combined \\
      --origin 27.9916 -0.4349 0.2688
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

import sys
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from inventory_from_cloud import fit_circle                      # noqa: E402
from itcd_cloud import height_above_ground, voxel_graph          # noqa: E402
from dbh_methods import stem_shell                               # noqa: E402

RAMP = [[150, 108, 68], [150, 130, 70], [120, 165, 80],
        [100, 190, 95], [150, 215, 120]]


def wood_filter(pts, radius=0.12, k=10, sphericity_max=0.16):
    """Geometrischer Holzfilter: lokale PCA je Punkt. Holz ist FLAECHIG oder
    LINEAR, Nadelwerk ist isotrop.

    Entscheidend ist, welches Merkmal man nimmt. Linearitaet (l1-l2)/l1 waere
    falsch: die Oberflaeche eines 62-cm-Stammes ist im 12-cm-Umfeld eine EBENE
    (l1 ~ l2 >> l3), also gerade nicht linear -- ein Linearitaetsfilter wirft
    genau den Stamm weg und behaelt die Zweige. Genau das ist hier zuerst
    passiert: QSM-BHD 6,6 cm an einem 62-cm-Stamm, weil das Modell einem Zweig
    nach oben folgte.

    Richtig ist die Kugelform l3/l1: klein an jeder Holzoberflaeche (Ebene ODER
    Linie), gross im Nadelbueschel, das in alle drei Richtungen streut.

    KEINE Ground Truth, nur Heuristik: siehe Modulkopf.
    """
    if len(pts) < k + 1:
        return np.ones(len(pts), bool)
    tree = cKDTree(pts)
    idx = tree.query_ball_point(pts, radius)
    sph = np.ones(len(pts))
    for i, nb in enumerate(idx):
        if len(nb) < k:
            continue
        p = pts[nb]
        p = p - p.mean(0)
        ev = np.linalg.eigvalsh(p.T @ p / len(p))[::-1]
        if ev[0] > 1e-12:
            sph[i] = max(ev[2], 0.0) / ev[0]
    return sph <= sphericity_max


def cyl_radius(pts, a, b, trunk):
    """Radius eines Querschnitts. Am Stamm per Kreisfit senkrecht zur Achse
    (genauer, weil der Stamm dicht und rund gescannt ist), am Ast als
    Median-Abstand zur Achse (ein Kreisfit haette dort zu wenig Bogen)."""
    d = b - a
    L = np.linalg.norm(d)
    if L < 1e-6 or len(pts) < 3:
        return None
    d = d / L
    rel = pts - a
    perp = rel - np.outer(rel @ d, d)
    dist = np.linalg.norm(perp, axis=1)
    if trunk and len(pts) >= 12:
        u = np.cross(d, [0, 0, 1.0])
        if np.linalg.norm(u) < 1e-8:
            u = np.array([1.0, 0, 0])
        u = u / np.linalg.norm(u)
        v = np.cross(d, u)
        fit = fit_circle(perp @ u, perp @ v)
        if fit is not None and 0.01 <= fit[2] <= 1.0:
            return float(fit[2])
    return float(np.median(dist)) if len(dist) else None


def trunk_model(wp, wh, sx, sy, dz=0.5, max_fail=3):
    """Stamm als Stapel gefitteter Kreise, von unten nach oben.

    Warum der Stamm NICHT aus der Skelett-Logik kommt: dort ist er nur "das
    punktreichste Kind" -- und an einer Fichte mit Aesten bis unten reisst diese
    Regel ab, sobald ein Ast in derselben Pfadlaenge mehr Punkte hat als der
    Stamm. Gemessen ist das kein Randfall gewesen, sondern der Normalfall: die
    Ordnung-1-Kette folgte an drei von fuenf Testbaeumen einem Ast, QSM-BHD kam
    mit 13 statt 62 cm heraus.

    Hier wird der Stamm stattdessen dort gesucht, wo er nachweislich steht: an
    der Position aus der Stammdetektion. Je 0,5-m-Schicht wird die Mantelschale
    um die laufende Achse genommen (Modus des Abstandshistogramms, wie in
    dbh_methods.stem_shell) und ein Kreis gefittet; die Achse wandert mit dem
    gefitteten Zentrum mit, damit Neigung und Schaftkruemmung nicht als
    Durchmesserfehler landen. Nach max_fail Schichten ohne Fit ist der Schaft zu
    Ende (Wipfel oder Verdeckung).

    Rueckgabe (Zylinderliste [(start, end, r)], Achspunkte, Taper [(h, d_cm)]).
    """
    axis_x, axis_y = sx, sy
    cyls, taper, prev = [], [], None
    fails = 0
    hmax = float(wh.max())
    z0 = float(wp[:, 2].min())
    k = 0
    while z0 + (k + 1) * dz <= z0 + hmax and fails <= max_fail:
        lo, hi = k * dz, (k + 1) * dz
        band = wp[(wh >= lo) & (wh < hi)]
        k += 1
        if len(band) < 12:
            fails += 1
            continue
        sl, _ = stem_shell(band, axis_x, axis_y, tol=0.08)
        fit = fit_circle(sl[:, 0], sl[:, 1]) if len(sl) >= 12 else None
        if fit is None or not (0.02 <= fit[2] <= 0.9) or fit[3] > 0.05:
            fails += 1
            continue
        cx, cy, r = fit[0], fit[1], fit[2]
        if math.hypot(cx - axis_x, cy - axis_y) > 0.4:       # Ausreisser-Achse
            fails += 1
            continue
        fails = 0
        zc = float(np.median(sl[:, 2]))
        node = np.array([cx, cy, zc])
        if prev is not None and np.linalg.norm(node - prev[0]) > 1e-3:
            cyls.append((prev[0], node, 0.5 * (prev[1] + r)))
        prev = (node, r)
        axis_x, axis_y = cx, cy
        taper.append((round(0.5 * (lo + hi), 2), round(200 * r, 1)))
    return cyls, taper


def qsm_tree(pts, h, seg_len, voxel, sph_max, sx, sy, pre_voxel=0.02):
    """QSM eines Baumes. Rueckgabe (Liste von Zylindern, Info-Dict).

    Zylinder: (start xyz, end xyz, radius, ordnung, n_punkte)
    """
    info = {"punkte": int(len(pts))}
    # Vor dem Filter ausduennen: die PCA-Merkmale haengen am Punktabstand, und
    # ein Stamm, der von vier Standpunkten getroffen wurde, hat dort sonst eine
    # andere Dichte als eine einseitig gesehene Kronenspitze.
    k = np.floor(pts / pre_voxel).astype(np.int64)
    _, keep = np.unique((k[:, 0] * 73856093) ^ (k[:, 1] * 19349663)
                        ^ (k[:, 2] * 83492791), return_index=True)
    pts, h = pts[keep], h[keep]
    info["punkte_ausgeduennt"] = int(len(pts))
    wood = wood_filter(pts, sphericity_max=sph_max)
    info["holz_punkte"] = int(wood.sum())
    info["holz_anteil_pct"] = round(100.0 * wood.sum() / max(len(pts), 1), 1)
    wp, wh = pts[wood], h[wood]
    if len(wp) < 200:
        return [], info

    # ---- Stamm zuerst, explizit an der detektierten Position ------------------
    trunk_cyls, taper = trunk_model(wp, wh, sx, sy)
    if not trunk_cyls:
        return [], info
    axis = np.array([c[1] for c in trunk_cyls])                # Achsknoten
    axis_r = np.array([c[2] for c in trunk_cyls])
    info["stammlaenge_m"] = round(float(axis[-1][2] - trunk_cyls[0][0][2]), 1)
    info["taper_cm"] = taper

    # Stammpunkte aus dem Astteil heraushalten: alles im Umkreis des gefitteten
    # Radius + 12 cm um die Achse in der jeweiligen Hoehe gehoert zum Schaft.
    atree = cKDTree(axis[:, :2])
    _, near = atree.query(wp[:, :2])
    on_trunk = (np.hypot(wp[:, 0] - axis[near, 0], wp[:, 1] - axis[near, 1])
                <= axis_r[near] + 0.12) & (wp[:, 2] <= axis[-1][2] + 0.2)
    bp, bh_ = wp[~on_trunk], wh[~on_trunk]
    info["stamm_punkte"] = int(on_trunk.sum())
    if len(bp) < 200:
        return [(c[0], c[1], c[2], 1, 0) for c in trunk_cyls], _finish(
            info, [(c[0], c[1], c[2], 1, 0) for c in trunk_cyls], taper)

    centres, vox_of_pt, g = voxel_graph(bp, voxel, 1)
    if len(centres) < 20:
        return [(c[0], c[1], c[2], 1, 0) for c in trunk_cyls], _finish(
            info, [(c[0], c[1], c[2], 1, 0) for c in trunk_cyls], taper)
    vh = np.zeros(len(centres))
    np.add.at(vh, vox_of_pt, bh_)
    vh /= np.maximum(np.bincount(vox_of_pt, minlength=len(centres)), 1)

    # Astansaetze: Voxel, die den Schaft beruehren -- von dort laufen die Wege los
    _, an = atree.query(centres[:, :2])
    d_axis = np.hypot(centres[:, 0] - axis[an, 0], centres[:, 1] - axis[an, 1])
    base = np.flatnonzero(d_axis <= axis_r[an] + 0.3)
    if not len(base):
        base = np.array([int(np.argmin(d_axis))])
    n = len(centres)
    link = csr_matrix((np.full(len(base), 1e-6, np.float32),
                       (np.zeros(len(base), np.int64), base)), shape=(1, n))
    big = vstack([hstack([csr_matrix((1, 1)), link]),
                  hstack([link.T, g])], format="csr")
    dist, pred = dijkstra(big, directed=False, indices=0, return_predecessors=True)
    dist, pred = dist[1:], pred[1:] - 1
    reach = np.isfinite(dist)
    if reach.sum() < 20:
        return [], info

    # ---- Ringe konstanter Pfadlaenge, darin Zusammenhangskomponenten ----------
    ring = np.full(n, -1, np.int64)
    ring[reach] = np.floor(dist[reach] / seg_len).astype(np.int64)
    seg_of_vox = np.full(n, -1, np.int64)
    segs = []            # je Segment: (ring, voxelindizes)
    for rg in range(0, int(ring[reach].max()) + 1):
        sel = np.flatnonzero(ring == rg)
        if len(sel) < 2:
            if len(sel) == 1:
                seg_of_vox[sel] = len(segs)
                segs.append((rg, sel))
            continue
        sub = g[sel][:, sel]
        ncomp, lab = connected_components(sub, directed=False)
        for c in range(ncomp):
            vox = sel[lab == c]
            seg_of_vox[vox] = len(segs)
            segs.append((rg, vox))

    # ---- Elternsegment + Verzweigungsordnung ---------------------------------
    parent = np.full(len(segs), -1, np.int64)
    for si, (rg, vox) in enumerate(segs):
        if rg == 0:
            continue
        # Eltern = Segment des Vorgaengers im Wegebaum (Mehrheitsentscheid)
        pv = pred[vox]
        pv = pv[pv >= 0]
        cand = seg_of_vox[pv]
        cand = cand[(cand >= 0) & (cand != si)]
        if len(cand):
            vals, cnt = np.unique(cand, return_counts=True)
            parent[si] = int(vals[cnt.argmax()])

    npts = np.array([len(v) for _, v in segs])
    children = {}
    for si, p in enumerate(parent):
        if p >= 0:
            children.setdefault(int(p), []).append(si)
    # Astansaetze sind Ordnung 2 (der Schaft ist 1); ab jedem weiteren Abzweig
    # eine Ordnung hoeher, die Fortsetzung (punktreichstes Kind) behaelt ihre.
    order = np.zeros(len(segs), np.int64)
    roots = [si for si in range(len(segs)) if parent[si] < 0]
    for r in roots:
        order[r] = 2
    stack = list(roots)
    while stack:
        si = stack.pop()
        kids = children.get(si, [])
        if kids:
            main = max(kids, key=lambda c: npts[c])
            for c in kids:
                order[c] = order[si] if c == main else order[si] + 1
                stack.append(c)

    # ---- Zylinder: Schaft (Ordnung 1) + Aeste --------------------------------
    cyls = [(c[0], c[1], c[2], 1, 0) for c in trunk_cyls]
    for si, (rg, vox) in enumerate(segs):
        if len(vox) < 1:
            continue
        end = centres[vox].mean(axis=0)
        p = parent[si]
        if p >= 0:
            start = centres[segs[p][1]].mean(axis=0)
        else:
            # Astansatz: am Schaft in gleicher Hoehe beginnen
            _, a = atree.query(end[None, :2])
            start = np.array([axis[a[0]][0], axis[a[0]][1], end[2]])
        if np.linalg.norm(end - start) < 1e-3:
            continue
        m = np.isin(vox_of_pt, vox)
        sub = bp[m]
        r = cyl_radius(sub if len(sub) >= 3 else centres[vox], start, end, False)
        if r is None or not (0.004 <= r <= 0.5):
            continue
        cyls.append((start, end, r, int(min(order[si], 255)), int(len(sub))))

    return cyls, _finish(info, cyls, taper)


def _finish(info, cyls, taper):
    """Ganzbaum-Metriken aus der Zylinderliste."""
    if not cyls:
        return info

    def vol(cs):
        return sum(math.pi * c[2] ** 2 * float(np.linalg.norm(c[1] - c[0])) for c in cs)

    trunk = [c for c in cyls if c[3] <= 1]
    info.update({
        "zylinder": len(cyls),
        "zylinder_stamm": len(trunk),
        "max_ordnung": int(max(c[3] for c in cyls)),
        "holzvolumen_l": round(vol(cyls) * 1000, 1),
        "stammvolumen_l": round(vol(trunk) * 1000, 1),
        "kronenholz_l": round(vol([c for c in cyls if c[3] > 1]) * 1000, 1),
        "oberflaeche_m2": round(sum(
            2 * math.pi * c[2] * float(np.linalg.norm(c[1] - c[0])) for c in cyls), 2),
    })
    # QSM-BHD direkt aus der Schafttaper: der 1,3-m-Wert der Kreisfits.
    # Unabhaengige Gegenprobe zu den BHD-Verfahren in dbh_methods.py.
    if taper:
        near = min(taper, key=lambda t: abs(t[0] - 1.3))
        if abs(near[0] - 1.3) <= 0.5:
            info["bhd_qsm_cm"] = near[1]
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud", help="Analyse-Wolke (.npz aus e57_merge.py)")
    ap.add_argument("itcd", help="ITCD-Label (.npz aus itcd_cloud.py)")
    ap.add_argument("--stems", required=True, help="Stammliste (CSV)")
    ap.add_argument("--out", required=True, help="Ausgabe-Prefix (.bin + .json)")
    ap.add_argument("--origin", nargs=3, type=float, required=True,
                    metavar=("X", "Y", "Z"), help="Szenen-Ursprung (source.origin_xyz)")
    ap.add_argument("--radius", type=float, default=22.0)
    ap.add_argument("--seg-len", type=float, default=0.35, help="Ringbreite [m]")
    ap.add_argument("--voxel", type=float, default=0.035, help="Voxelweite je Baum [m]")
    ap.add_argument("--sphericity-max", dest="sph_max", type=float, default=0.16,
                    help="max. Kugelform l3/l1 des Holzfilters (0..1)")
    ap.add_argument("--max-trees", type=int, help="nur die ersten N Baeume (Test)")
    args = ap.parse_args()

    d = np.load(args.cloud)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    ox, oy, oz = args.origin
    xyz = xyz[np.hypot(xyz[:, 0] - ox, xyz[:, 1] - oy) <= args.radius]
    lab = np.load(args.itcd, allow_pickle=True)["label"]
    if len(lab) != len(xyz):
        raise SystemExit(f"Label ({len(lab)}) passen nicht zur Wolke ({len(xyz)}) "
                         "-- gleiche --origin/--radius verwenden wie bei itcd_cloud.py")
    h, _ = height_above_ground(xyz)

    stems = list(csv.DictReader(open(args.stems, encoding="utf-8-sig")))
    names = [s.get("label") or s.get("id") for s in stems]
    origin = np.array([ox, oy, oz])

    S, E, R, O = [], [], [], []
    metrics = {}
    todo = range(len(names) if args.max_trees is None else min(args.max_trees, len(names)))
    for i in todo:
        m = lab == i
        if m.sum() < 500:
            print(f"  {names[i]}: {int(m.sum())} Punkte -- zu wenig, uebersprungen")
            continue
        cyls, info = qsm_tree(xyz[m], h[m], args.seg_len, args.voxel, args.sph_max,
                              float(stems[i]["x"]), float(stems[i]["y"]))
        metrics[names[i]] = info
        if not cyls:
            print(f"  {names[i]}: kein Modell ({info.get('holz_punkte', 0)} Holzpunkte)")
            continue
        for st, en, r, o, _ in cyls:
            S.append(st - origin); E.append(en - origin); R.append(r); O.append(o)
        print(f"  {names[i]}: {info['zylinder']:4} Zylinder, Ordnung bis "
              f"{info['max_ordnung']}, Holz {info['holz_anteil_pct']:4.1f}%, "
              f"Volumen {info['holzvolumen_l']:7.1f} l, "
              f"BHD(QSM) {info.get('bhd_qsm_cm', '--')}")

    if not S:
        raise SystemExit("Keine Zylinder erzeugt")
    S = np.asarray(S, np.float32); E = np.asarray(E, np.float32)
    R = np.asarray(R, np.float32); O = np.asarray(O, np.uint8)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".bin").write_bytes(
        np.ascontiguousarray(S, "<f4").tobytes()
        + np.ascontiguousarray(E, "<f4").tobytes()
        + np.ascontiguousarray(R, "<f4").tobytes()
        + O.tobytes())
    meta = {"count": int(len(S)), "order_max": int(O.max()), "ramp": RAMP,
            "origin_xyz": [ox, oy, oz], "seg_len_m": args.seg_len,
            "voxel_m": args.voxel, "holzfilter_sphericity_max": args.sph_max,
            "baeume": metrics,
            "limits": ("Holzfilter ist eine Geometrie-Heuristik (lokale PCA), KEINE "
                       "annotierte Blatt-Holz-Trennung wie bei SYSSIFOSS. Nadeln, die "
                       "als Holz durchgehen, treiben die Radien feiner Zweige nach "
                       "oben -- das Kronen-Holzvolumen ist eine Obergrenze. Verdeckte "
                       "Kronenteile fehlen ganz, das wirkt gegenlaeufig. Stamm und "
                       "QSM-BHD stammen aus Kreisfits am dicht gescannten Stamm und "
                       "sind belastbarer als das Kronenvolumen.")}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    n_tr = sum(1 for v in metrics.values() if v.get("zylinder"))
    print(f"-> {out.with_suffix('.bin')} ({len(S):,} Zylinder aus {n_tr} Baeumen, "
          f"Ordnung bis {O.max()})")
    print(f"-> {out.with_suffix('.json')}")


if __name__ == "__main__":
    main()
