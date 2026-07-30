#!/usr/bin/env python3
"""itcd_cloud.py -- Einzelbaum-Segmentierung (ITCD) auf der dichten Analyse-Wolke.

Verfahren: Kuerzeste Wege im Punktgraphen ("comparative shortest path", Tao et al.
2015) statt Naechster-Stamm-Zuordnung. Der Unterschied ist der Punkt der Uebung:

  segment_itcd.py ordnet jeden Punkt dem in der Draufsicht naechsten Stamm zu.
  Das schneidet gerade Grenzen durch verzahnte Kronen -- ein Ast, der 3 m weit
  ueber den Nachbarn ragt, wird dem Nachbarn zugeschlagen.

  Hier zaehlt statt der Luftlinie die Entfernung ENTLANG DES HOLZES: der Punktgraph
  verbindet nur benachbarte Voxel, und jeder Punkt geht an den Stamm, zu dem der
  kuerzeste Weg im Graphen fuehrt. Ein ueberhaengender Ast bleibt damit an seinem
  eigenen Stamm, weil der Weg dorthin durch zusammenhaengendes Holz laeuft,
  waehrend zum Nachbarstamm die Luecke dazwischen liegt.

Bodenpunkte muessen vorher weg -- sonst laeuft jeder kuerzeste Weg ueber den Boden
und das Verfahren fiele auf die Luftlinie zurueck.

Ausgabe:
  * <out>.npz   Label je Punkt der Analyse-Wolke (-1 = Boden/nicht erreicht)
  * Kronenmetriken je Baum (CSV): Kronenansatz, -laenge, -durchmesser, -volumen
  * optional die eingefaerbten Web-Bins der Szene (--scene), damit der Viewer
    zwischen "RGB" und "Einzelbaeume" umschalten kann

  python scripts/itcd_cloud.py data/Renon/_analysis.npz data/Renon/trees_combined.csv \\
      --out data/Renon/itcd_combined.npz --crowns data/Renon/crowns_combined.csv \\
      --scene platform/dev-data/media/scenes/renon-combined/scene.json
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

GROUND_CELL = 1.0     # m, Rasterweite des Bodenmodells
GROUND_PCT = 2        # Perzentil je Zelle = Boden
GREY = (110, 114, 120)

# Gut unterscheidbare Farben, zyklisch (identisch zu segment_itcd.py)
PALETTE = np.array([
    [230, 100, 90], [90, 200, 120], [95, 160, 240], [240, 190, 80],
    [200, 120, 230], [90, 210, 210], [240, 140, 60], [160, 210, 90],
    [240, 130, 180], [130, 140, 240], [80, 190, 160], [220, 220, 110],
], np.uint8)


def height_above_ground(xyz, cell=GROUND_CELL):
    ix = np.floor(xyz[:, 0] / cell).astype(np.int64)
    iy = np.floor(xyz[:, 1] / cell).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], xyz[order, 2]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    gmap = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= 5:
            gmap[int(ks[lo])] = float(np.percentile(zs[lo:hi], GROUND_PCT))
    default = float(np.median(list(gmap.values()))) if gmap else float(xyz[:, 2].min())
    ground = np.array([gmap.get(int(k), default) for k in key], np.float32)
    return xyz[:, 2] - ground, ground


def voxel_graph(pts, voxel, reach=1, h_penalty=1.0):
    """Voxelgitter + Kantenliste zwischen benachbarten belegten Voxeln.

    Rueckgabe (centres, vox_of_point, graph). 'reach' ist die Nachbarschaft in
    Voxeln: reach=1 verbindet die 26 direkten Nachbarn, reach=2 ueberbrueckt auch
    einmal ausgefallene Voxel (duenne Zweige, Streifschuesse).

    h_penalty verteuert WAAGERECHTE Kanten (Gewicht = |(kh*dx, kh*dy, dz)|).
    Waagerecht teuer / senkrecht billig entspricht dem Bau eines Baumes: den
    eigenen Schaft hoch ist naeher als quer durch die zusammenhaengende
    Unterschicht in die Nachbarkrone. Fuer Astmodelle (qsm_cloud.py) bleibt es
    bei 1.0 -- Aeste SIND waagerecht.

    Nicht verwechseln: die sehr ungleichen Punktzahlen je Baum (Median 508.000
    innerhalb 5 m, 14.000 bei 15-20 m) kommen NICHT von der Zuordnung, sondern
    von der Scandichte -- sie faellt mit dem Abstandsquadrat zum Standpunkt.
    """
    k = np.floor(pts / voxel).astype(np.int64)
    k -= k.min(axis=0)
    keys, inv = np.unique(k[:, 0] * 4_000_037 ** 2 + k[:, 1] * 4_000_037 + k[:, 2],
                          return_inverse=True)
    n = len(keys)
    # Voxelmittelpunkte als Mittel der enthaltenen Punkte (genauer als Zellmitte)
    centres = np.zeros((n, 3), np.float64)
    np.add.at(centres, inv, pts)
    cnt = np.bincount(inv, minlength=n).astype(np.float64)
    centres /= cnt[:, None]

    # Nachbarschaft ueber die Voxelkoordinaten: fuer jede Verschiebung einmal
    # nachschlagen, ob das verschobene Voxel belegt ist. Nachgeschlagen wird per
    # searchsorted im sortierten Schluesselfeld -- ein Python-dict waere hier
    # zweistellige Millionen Einzelzugriffe je Verschiebungsrichtung.
    kv = np.zeros((n, 3), np.int64)
    kv[inv] = k
    rows, cols, data = [], [], []
    shifts = [(dx, dy, dz)
              for dx in range(-reach, reach + 1)
              for dy in range(-reach, reach + 1)
              for dz in range(-reach, reach + 1)
              if (dx, dy, dz) > (0, 0, 0)]          # jede Kante nur einmal
    for dx, dy, dz in shifts:
        shifted = ((kv[:, 0] + dx) * 4_000_037 ** 2 + (kv[:, 1] + dy) * 4_000_037
                   + (kv[:, 2] + dz))
        pos = np.searchsorted(keys, shifted)
        ok = pos < n
        tgt = np.where(ok & (keys[np.minimum(pos, n - 1)] == shifted), pos, -1)
        m = tgt >= 0
        if not m.any():
            continue
        src = np.flatnonzero(m)
        dst = tgt[m]
        diff = centres[src] - centres[dst]
        if h_penalty != 1.0:
            diff = diff * np.array([h_penalty, h_penalty, 1.0])
        w = np.linalg.norm(diff, axis=1)
        rows.append(src); cols.append(dst); data.append(w)
    rows = np.concatenate(rows); cols = np.concatenate(cols)
    data = np.concatenate(data).astype(np.float32)
    g = coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()
    return centres, inv, g + g.T


def resolve_roots(pred, seeds):
    """Wurzel (Saatvoxel) je Knoten aus dem Vorgaengerbaum -- per Pointer-Jumping.

    dijkstra() gibt nur Vorgaenger zurueck, nicht die Quelle. Der Vorgaengerbaum
    zeigt aber von jedem erreichten Knoten zurueck zu seinem Saatpunkt; mehrfaches
    Verdoppeln des Zeigers (log n Schritte) fuehrt alle Knoten gleichzeitig dorthin.
    """
    root = pred.copy()
    is_seed = np.zeros(len(pred), bool)
    is_seed[seeds] = True
    root[is_seed] = seeds                      # Saatknoten sind ihre eigene Wurzel
    root[root < 0] = -1
    for _ in range(64):
        nxt = np.where(root >= 0, np.where(is_seed[np.maximum(root, 0)], root,
                                           root[np.maximum(root, 0)]), -1)
        nxt = np.where(root < 0, -1, nxt)
        if np.array_equal(nxt, root):
            break
        root = nxt
    return root


def read_bin(path, count):
    raw = np.fromfile(path, dtype=np.uint8)
    xyz = raw[: count * 12].view("<f4").reshape(count, 3)
    rgb = raw[count * 12: count * 12 + count * 3].reshape(count, 3)
    return xyz, rgb


def crown_metrics(pts, h, gz, stem_h):
    """Kronenmetriken eines Baumes aus seinen zugeordneten Punkten.

    Kronenansatz = unterste Hoehe, ab der die horizontale Ausdehnung dauerhaft
    ueber den Stammquerschnitt hinausgeht (in 0,5-m-Schichten gemessen).
    """
    if len(pts) < 50:
        return {}
    top = float(h.max())
    edges = np.arange(0.0, top + 0.5, 0.5)
    idx = np.clip(np.digitize(h, edges) - 1, 0, len(edges) - 2)
    widths = np.full(len(edges) - 1, np.nan)
    for i in range(len(edges) - 1):
        m = idx == i
        if m.sum() >= 10:
            p = pts[m, :2]
            widths[i] = float(np.percentile(np.linalg.norm(p - p.mean(0), axis=1), 95) * 2)
    # Kronenansatz: erste Schicht ueber 2 m, ab der die Breite den 3-fachen
    # Stammdurchmesser ueberschreitet und das auch darueber so bleibt
    thresh = max(3 * stem_h, 1.0)
    base = None
    for i in range(len(widths)):
        if edges[i] < 2.0 or not np.isfinite(widths[i]):
            continue
        rest = widths[i:][np.isfinite(widths[i:])]
        if widths[i] >= thresh and len(rest) and np.nanmean(rest) >= thresh:
            base = float(edges[i])
            break
    out = {"Kronenhoehe_m": round(top, 1)}
    if base is not None:
        out["Kronenansatz_m"] = round(base, 1)
        out["Kronenlaenge_m"] = round(top - base, 1)
        cw = widths[(edges[:-1] >= base)]
        cw = cw[np.isfinite(cw)]
        if len(cw):
            d = float(np.nanmax(cw))
            out["Kronendurchmesser_m"] = round(d, 1)
            # Volumen als Kegel (Nadelbaum-Krone) -- geometrische Naeherung
            out["Kronenvolumen_m3"] = round(
                math.pi * (d / 2) ** 2 * (top - base) / 3.0, 1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud", help="Analyse-Wolke (.npz aus e57_merge.py)")
    ap.add_argument("stems", help="Stammliste (CSV aus inventory_from_cloud.py)")
    ap.add_argument("--out", required=True, help="Ziel-.npz (Label je Punkt)")
    ap.add_argument("--crowns", help="Kronenmetriken je Baum als CSV")
    ap.add_argument("--scene", help="scene.json: Web-Bins einfaerben + bin_itcd eintragen")
    ap.add_argument("--media-dir", help="Verzeichnis der .bin (Default: Ordner der scene.json)")
    ap.add_argument("--voxel", type=float, default=0.08, help="Voxelweite des Graphen [m]")
    ap.add_argument("--reach", type=int, default=1,
                    help="Nachbarschaft in Voxeln; 2 ueberbrueckt Punktluecken, "
                         "kostet aber das Fuenffache an Kanten")
    ap.add_argument("--ground-h", type=float, default=0.4,
                    help="darunter gilt als Boden und bleibt unzugeordnet [m]")
    ap.add_argument("--h-penalty", type=float, default=3.0,
                    help="Aufschlag auf waagerechte Kanten (1 = reiner Euklid)")
    ap.add_argument("--max-path", type=float, default=45.0,
                    help="max. gewichtete Weglaenge im Graphen; darueber unzugeordnet")
    ap.add_argument("--origin", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--radius", type=float, default=22.0)
    args = ap.parse_args()

    d = np.load(args.cloud)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    if args.origin:
        ox, oy, _ = args.origin
        xyz = xyz[np.hypot(xyz[:, 0] - ox, xyz[:, 1] - oy) <= args.radius]
    print(f"{len(xyz):,} Punkte")

    h, ground = height_above_ground(xyz)
    veg = h > args.ground_h
    print(f"{int(veg.sum()):,} Vegetationspunkte (> {args.ground_h} m ueber Boden)")

    stems = list(csv.DictReader(open(args.stems, encoding="utf-8-sig")))
    labels_txt = [s.get("label") or s.get("id") for s in stems]
    sxy = np.array([[float(s["x"]), float(s["y"])] for s in stems])
    sdbh = np.array([float(s["BHD_cm"]) / 100.0 if s.get("BHD_cm") else 0.3
                     for s in stems])
    print(f"{len(stems)} Staemme als Saatpunkte")

    print(f"Voxelgraph ({args.voxel} m, Nachbarschaft {args.reach}) ...")
    centres, vox_of_pt, g = voxel_graph(xyz[veg], args.voxel, args.reach,
                                        args.h_penalty)
    print(f"  {len(centres):,} Voxel, {g.nnz // 2:,} Kanten")

    # Saatvoxel: die Stammvoxel im Band 0,5-2,0 m ueber Boden im Umkreis des
    # halben Stammdurchmessers -- so startet der Weg auf dem Stamm, nicht im Laub.
    vh = np.zeros(len(centres))
    np.add.at(vh, vox_of_pt, h[veg])
    vh /= np.maximum(np.bincount(vox_of_pt, minlength=len(centres)), 1)
    seed_of_vox = np.full(len(centres), -1, np.int32)
    tree = cKDTree(centres[:, :2])
    for i, (sx, sy) in enumerate(sxy):
        # Fenster bewusst weit (Band 0,4-2,5 m, Radius >= 30 cm): mit engeren
        # Grenzen blieben zwei der 82 Staemme ohne Saatvoxel und damit ohne Krone.
        cand = tree.query_ball_point([sx, sy], max(sdbh[i] * 0.8, 0.3))
        cand = [c for c in cand if 0.4 <= vh[c] <= 2.5 and seed_of_vox[c] < 0]
        for c in cand:
            seed_of_vox[c] = i
    seeds = np.flatnonzero(seed_of_vox >= 0)
    got = len(np.unique(seed_of_vox[seeds]))
    print(f"  {len(seeds):,} Saatvoxel, {got}/{len(stems)} Staemme mit Saat")

    print("Kuerzeste Wege ...")
    # Virtueller Startknoten mit Gewicht 0 auf alle Saatvoxel: EIN Dijkstra-Lauf
    # statt 82. Die Zuordnung kommt danach aus dem Vorgaengerbaum.
    n = len(centres)
    from scipy.sparse import hstack, vstack, csr_matrix
    link = csr_matrix((np.full(len(seeds), 1e-6, np.float32),
                       (np.zeros(len(seeds), np.int64), seeds)), shape=(1, n))
    big = vstack([hstack([csr_matrix((1, 1)), link]),
                  hstack([link.T, g])], format="csr")
    dist, pred = dijkstra(big, directed=False, indices=0, return_predecessors=True)
    dist, pred = dist[1:], pred[1:] - 1          # virtuellen Knoten wieder ab
    pred[pred < 0] = -1
    root = resolve_roots(pred, seeds)
    vox_label = np.where((root >= 0) & (dist <= args.max_path),
                         seed_of_vox[np.maximum(root, 0)], -1).astype(np.int32)

    label = np.full(len(xyz), -1, np.int32)
    label[veg] = vox_label[vox_of_pt]
    hit = label >= 0
    print(f"-> {int(hit.sum()):,}/{len(xyz):,} Punkte zugeordnet "
          f"({100.0 * hit.sum() / len(xyz):.1f}%), "
          f"{len(np.unique(label[hit]))} Baeume getroffen")

    np.savez_compressed(args.out, label=label, stems=sxy,
                        labels_txt=np.array(labels_txt, dtype=object),
                        voxel=np.float64(args.voxel))
    print(f"-> {args.out}")

    # ---- Kronenmetriken je Baum ----
    if args.crowns:
        rows = []
        for i, name in enumerate(labels_txt):
            m = label == i
            r = {"label": name, "Punkte_ITCD": int(m.sum())}
            if m.sum() >= 50:
                r.update(crown_metrics(xyz[m], h[m], ground[m], sdbh[i]))
            rows.append(r)
        fields = ["label", "Punkte_ITCD", "Kronenhoehe_m", "Kronenansatz_m",
                  "Kronenlaenge_m", "Kronendurchmesser_m", "Kronenvolumen_m3"]
        with open(args.crowns, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
        n_c = sum(1 for r in rows if r.get("Kronenansatz_m"))
        print(f"-> {args.crowns}: {n_c}/{len(rows)} Baeume mit Kronenansatz")

    # ---- Web-Bins einfaerben ----
    if args.scene:
        spath = Path(args.scene)
        scene = json.loads(spath.read_text(encoding="utf-8"))
        media = Path(args.media_dir) if args.media_dir else spath.parent
        origin = np.array((scene.get("source") or {}).get("origin_xyz") or [0, 0, 0])
        pc = scene.get("pointcloud") or {}
        levels = pc.get("levels") or ([pc] if pc.get("bin") else [])
        # Label der dichten Wolke auf die Web-Punkte uebertragen (naechster Nachbar)
        dense = cKDTree(xyz[hit])
        dense_lab = label[hit]
        for lv in levels:
            src = media / Path(lv["bin"]).name
            if not src.is_file():
                print(f"  {src.name}: nicht gefunden, uebersprungen")
                continue
            bxyz, _ = read_bin(src, lv["count"])
            world = bxyz.astype(np.float64) + origin
            dd, ii = dense.query(world, distance_upper_bound=args.voxel * 1.5)
            lab = np.where(np.isfinite(dd), dense_lab[np.minimum(ii, len(dense_lab) - 1)], -1)
            rgb = np.empty((len(world), 3), np.uint8)
            rgb[:] = GREY
            m = lab >= 0
            rgb[m] = PALETTE[lab[m] % len(PALETTE)]
            out = src.with_name(src.stem + "_seg.bin")
            out.write_bytes(np.ascontiguousarray(bxyz, "<f4").tobytes() + rgb.tobytes())
            lv["bin_itcd"] = str(Path(lv["bin"]).parent / out.name).replace("\\", "/")
            print(f"  {src.name}: {int(m.sum()):,}/{len(world):,} eingefaerbt "
                  f"({100.0 * m.sum() / len(world):.0f}%) -> {out.name}")
        spath.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"-> bin_itcd je Stufe in {spath.name} eingetragen")


if __name__ == "__main__":
    main()
