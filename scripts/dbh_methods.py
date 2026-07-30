#!/usr/bin/env python3
"""dbh_methods.py -- BHD je Stamm mit mehreren unabhaengigen Verfahren.

Gegenstueck zu bench_dbh.py: DORT gibt es Feld-Ground-Truth (SYSSIFOSS-
Einzelbaeume, pytreedb), also laesst sich GENAUIGKEIT messen. HIER, am eigenen
Renon-Bestand, gibt es keine Feldmessung -- messbar ist nur die UEBEREINSTIMMUNG
der Verfahren untereinander (Praezision). Genau so wird es auch ausgegeben:
Konsens = Median der Verfahren, dazu je Verfahren die Abweichung davon. Das ist
KEINE Genauigkeitsaussage; die Verfahren koennen gemeinsam falsch liegen (am
SYSSIFOSS-Benchmark ist genau das an einem Baum passiert, s. BENCH_DBH.md).

Verfahren (alle auf derselben Brusthoehen-Scheibe derselben Wolke):
  kreisfit   algebraischer Kreisfit (Kasa) an der 1,05-1,55-m-Scheibe -- die
             Baseline der Suite (inventory_from_cloud.py)
  geofit     geometrischer Kreisfit (Gauss-Newton auf die echten Punkt-Kreis-
             Abstaende). Gegenmittel gegen die bekannte Verzerrung des
             algebraischen Fits bei kurzen Boegen -- und kurz sind sie hier
             (Median 190 Grad Abdeckung).
  ransac     RANSAC-Kreisfit: robust gegen Rindenausreisser, Flechten, Aeste und
             gegen Nachbarpunkte, die in die Scheibe hineinragen
  zylinder   3D-Zylinderfit ueber das 1,0-1,6-m-Band MIT Achsneigung. Der
             Unterschied ist systematisch, nicht kosmetisch: eine waagerechte
             Scheibe schneidet einen geneigten Stamm elliptisch und ueberschaetzt
             den Durchmesser um 1/cos(Neigung).
  3dfin      3DFin (dendromatics, Univ. Santiago de Compostela) auf der ganzen
             Plot-Wolke: EIGENE Stammdetektion und eigener BHD, per Position
             zugeordnet. Damit ist es das einzige Verfahren hier, das nicht auf
             unserer Detektion aufsetzt -- es prueft die Detektion mit.

VERWORFEN: Umfang der konvexen Huelle / pi, das Analogon zum Umfangmassband der
Feldinventur. Es braucht eine geschlossene, DUENNE Mantellinie; beides ist hier
nicht gegeben (Median 190 Grad Abdeckung, und die 16 cm dicke Trennschale von
stem_shell() legt die Huelle auf den Aussenrand). Gemessen ueberschaetzte es um
+10 cm bei n=5 -- als Verfahren im Vergleich waere das irrefuehrend.

Das QSM-BHD (2*Median-Stammradius am Zylindermodell) kommt aus qsm_cloud.py und
wird beim Szenenbau dazugelegt -- es ist das Gegenstueck zu 'qsm_wood' im
Feld-Benchmark (scripts/BENCH_DBH.md).

Eingabe: Analyse-Wolke (e57_merge.py .npz) + Stammliste (inventory_from_cloud.py).

  python scripts/dbh_methods.py data/Renon/_analysis.npz data/Renon/trees_combined.csv \\
      --out data/Renon/dbh_methods_combined.csv --origin 27.9916 -0.4349 0.2688 --radius 22
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from inventory_from_cloud import fit_circle          # noqa: E402

BH_LO, BH_HI = 1.0, 1.6      # Band fuer den Zylinderfit
SLICE_LO, SLICE_HI = 1.05, 1.55   # Scheibe fuer die 2D-Verfahren
R_MIN, R_MAX = 0.04, 0.75
CELL_GROUND = 0.5
# Konsens nur aus den Verfahren, die an praktisch jedem Stamm ein Ergebnis
# liefern -- sonst haette jeder Stamm einen anders zusammengesetzten Konsens und
# die Abweichungen waeren untereinander nicht vergleichbar. '3dfin' bringt eine
# eigene Detektion mit, findet also nicht jeden Stamm, und wird deshalb GEGEN den
# Konsens gehalten statt ihn mitzubilden -- genau das macht es zur Gegenprobe.
CORE = ["kreisfit", "geofit", "ransac", "zylinder"]
EXTRA = ["3dfin"]
METHODS = CORE + EXTRA
# Datenlage-Schwellen (NICHT Uebereinstimmung -- die waere als Guetemass zirkulaer)
GOOD_ARC, GOOD_PTS = 180, 200


# ---------------------------------------------------------------- Bodenmodell
def ground_grid(xyz):
    """Zelle -> Bodenhoehe (2. Perzentil), wie inventory_from_cloud.py."""
    ix = np.floor(xyz[:, 0] / CELL_GROUND).astype(np.int64)
    iy = np.floor(xyz[:, 1] / CELL_GROUND).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], xyz[order, 2]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    g = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= 20:
            g[int(ks[lo])] = float(np.percentile(zs[lo:hi], 2))
    return g


def arc_ok(r):
    return (r.get("Bogen_deg") or 0) >= GOOD_ARC


def stem_continuity(sub, h, sx, sy, r0, lo=1.3, hi=6.0, dz=0.5, min_pts=5,
                    min_share=0.6):
    """Setzt sich der Stamm ueber der Brusthoehe nach oben fort?

    Ein Kreisfit in EINER Scheibe beweist keinen Baum: ein liegender Stamm, ein
    Wurzelteller oder ein dichter Strauch koennen in 1,3 m Hoehe genauso rund
    aussehen. Ein Baum unterscheidet sich davon dadurch, dass in JEDER Schicht
    darueber Holz an derselben Stelle steht.

    Geprueft wird der Anteil der 0,5-m-Schichten zwischen lo und hi, die im
    Umkreis r0 + 20 cm um die Stammachse mindestens min_pts Punkte haben.
    """
    d = np.hypot(sub[:, 0] - sx, sub[:, 1] - sy)
    near = d <= r0 + 0.20
    edges = np.arange(lo, hi + dz, dz)
    hit = 0
    for a, b in zip(edges[:-1], edges[1:]):
        if int(np.count_nonzero(near & (h >= a) & (h < b))) >= min_pts:
            hit += 1
    share = hit / max(len(edges) - 1, 1)
    return round(share, 2), "ja" if share >= min_share else "nein"


def ground_at(g, x, y):
    key = int(math.floor(x / CELL_GROUND)) * 1_000_003 + int(math.floor(y / CELL_GROUND))
    return g.get(key)


# ------------------------------------------------------------ Stamm isolieren
CELL_STEM = 0.04     # m, Belegungsraster wie in inventory_from_cloud.py


def stem_shell(pts, sx, sy, tol=0.08, bin_w=0.02):
    """Mantelpunkte des EINEN Stammes um die bekannte Stammachse (sx, sy).

    Unverzichtbar in diesem Bestand: bei 650 Staemmen/ha liegen im 0,8-m-Umkreis
    einer Brusthoehen-Scheibe regelmaessig Nachbarstamm, Totholz und Aeste mit
    drin. Zusammenhangskomponenten allein reichen dafuer NICHT -- bei 1-cm-Wolke
    und 4-cm-Raster verschmelzen zwei Staemme, deren Rinde sich auf 6 cm naehert,
    zu einer Komponente; ein so verschmolzener 'Stamm' kam hier auf 112 cm BHD.

    Stattdessen: die Abstaende zur Stammachse haeufen sich beim Radius (der Mantel
    ist eine duenne Schale, der Nachbar liegt weiter weg und streut breit). Der
    Modus des Abstandshistogramms ist also der Radius -- ohne Kreisfit, also ohne
    das Ergebnis vorwegzunehmen. Behalten wird die Schale +/- tol darum; tol = 8 cm
    ist bewusst weit gegenueber den 1-3 cm, um die es beim Verfahrensvergleich
    geht: das Fenster grenzt den Nachbarn aus, bestimmt aber nicht den Durchmesser.
    """
    # Alle Rueckgabepfade liefern (Punkte, Schalenradius) -- bei zu wenig Punkten
    # gibt es keinen Radius, dann nan. Zwei der Pfade gaben frueher nur die Punkte
    # zurueck; am Renon-Bestand wurden sie nie erreicht, auf einem duenner
    # besetzten Plot sofort (ValueError beim Entpacken).
    if len(pts) < 8:
        return pts, float("nan")
    d = np.hypot(pts[:, 0] - sx, pts[:, 1] - sy)
    m = (d >= R_MIN) & (d <= R_MAX)
    if m.sum() < 8:
        return pts[m], float("nan")
    hist, edges = np.histogram(d[m], bins=np.arange(R_MIN, R_MAX + bin_w, bin_w))
    r0 = 0.5 * (edges[hist.argmax()] + edges[hist.argmax() + 1])
    keep = m & (np.abs(d - r0) <= tol)
    sel = isolate_component(pts[keep], sx, sy) if keep.sum() >= 8 else pts[m]
    return sel, float(r0)


def isolate_component(pts, sx, sy, near=0.5):
    """Punktreichste Zusammenhangskomponente im 4-cm-Belegungsraster, deren
    Schwerpunkt noch im Umkreis 'near' um die Stammachse liegt.

    Nachgeschaltet zu stem_shell(): faengt den Fall, dass ein Nachbarstamm
    zufaellig im selben Abstandsring liegt. Punktreichste, nicht naechstgelegene:
    bei einem 57-cm-Stamm ist die gescannte Vorderseite ein Bogen, dessen
    Schwerpunkt vor der Stammachse liegt, und eine kleine Zweigwolke direkt an der
    Achse waere naeher als der Stamm selbst.
    """
    if len(pts) < 8:
        return pts
    ix = np.floor(pts[:, 0] / CELL_STEM).astype(np.int64)
    iy = np.floor(pts[:, 1] / CELL_STEM).astype(np.int64)
    cells = {}
    for i, (a, b) in enumerate(zip(ix, iy)):
        cells.setdefault((int(a), int(b)), []).append(i)
    comps = []
    seen = set()
    for start in cells:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            c = stack.pop()
            comp.append(c)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (c[0] + dx, c[1] + dy)
                    if nb in cells and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        idx = np.array([i for c in comp for i in cells[c]])
        cxy = pts[idx, :2].mean(axis=0)
        comps.append((math.hypot(cxy[0] - sx, cxy[1] - sy), len(idx), idx))
    inside = [c for c in comps if c[0] <= near]
    pick = max(inside or comps, key=lambda c: c[1] if inside else -c[0])
    return pts[pick[2]]


# ------------------------------------------------------------------ Verfahren
def m_kreisfit(sl):
    """Kasa-Kreisfit an der Scheibe -> (BHD_cm, RMS_cm, Bogen_deg)."""
    fit = fit_circle(sl[:, 0], sl[:, 1])
    if fit is None:
        return None, None, None
    _, _, r, rms, arc = fit
    if not (R_MIN <= r <= R_MAX):
        return None, round(rms * 100, 1), int(arc)
    return round(200 * r, 1), round(rms * 100, 1), int(arc)


def arc_deg(px, py, cx, cy):
    """Winkelabdeckung eines Punktsatzes um (cx, cy) in Grad (36 Sektoren)."""
    ang = np.degrees(np.arctan2(py - cy, px - cx))
    return float(np.count_nonzero(np.histogram(ang, bins=36, range=(-180, 180))[0])) * 10.0


def m_ransac(sl, tol=0.012, iters=400, seed=0, min_arc=90.0):
    """RANSAC-Kreisfit: bestes Konsensmodell aus Dreipunkt-Umkreisen, dann
    Kasa-Nachfit auf den Inliern.

    Gewertet wird nicht die Inlierzahl allein, sondern nur ein Konsens, dessen
    Inlier mindestens min_arc Grad umspannen. Ohne diese Bedingung gewinnt an
    einem teilverdeckten Stamm regelmaessig ein kleiner Kreis durch eine dichte
    Punkttraube (Ast, Rindenschuppe): viele Inlier auf engstem Bogen, Durchmesser
    grob zu klein. Genau dieser Fehler trat hier an 10 von 39 Staemmen auf.
    """
    n = len(sl)
    if n < 12:
        return None, None
    rng = np.random.default_rng(seed)
    px, py = sl[:, 0], sl[:, 1]
    best = (0, None)
    for _ in range(iters):
        i, j, k = rng.choice(n, 3, replace=False)
        # Umkreis dreier Punkte
        ax, ay, bx, by, cx_, cy_ = px[i], py[i], px[j], py[j], px[k], py[k]
        d = 2 * (ax * (by - cy_) + bx * (cy_ - ay) + cx_ * (ay - by))
        if abs(d) < 1e-9:
            continue
        ux = ((ax**2 + ay**2) * (by - cy_) + (bx**2 + by**2) * (cy_ - ay)
              + (cx_**2 + cy_**2) * (ay - by)) / d
        uy = ((ax**2 + ay**2) * (cx_ - bx) + (bx**2 + by**2) * (ax - cx_)
              + (cx_**2 + cy_**2) * (bx - ax)) / d
        r = math.hypot(ax - ux, ay - uy)
        if not (R_MIN <= r <= R_MAX):
            continue
        inl = np.abs(np.hypot(px - ux, py - uy) - r) <= tol
        cnt = int(inl.sum())
        if cnt > best[0] and arc_deg(px[inl], py[inl], ux, uy) >= min_arc:
            best = (cnt, inl)
    if best[1] is None or best[0] < 10:
        return None, None
    fit = fit_circle(px[best[1]], py[best[1]])
    if fit is None or not (R_MIN <= fit[2] <= R_MAX):
        return None, None
    return round(200 * fit[2], 1), round(100.0 * best[0] / n, 1)


def m_zylinder(band, max_tilt=15.0):
    """Zylinderfit mit Achsneigung: Achsrichtung so drehen, dass der Kreisfit in
    der achssenkrechten Ebene minimal streut. Rueckgabe (BHD_cm, Neigung_deg).

    Die Neigung ist auf max_tilt gedeckelt. Ohne Deckel laeuft der Optimierer an
    Staemmen mit schlechter Abdeckung weg (hier bis 40 Grad) -- er kippt die Achse
    dann in die Richtung des Bogen-Ausschnitts, wo eine schmale Punktwolke immer
    besser auf einen Kreis passt. 15 Grad ist fuer Fichtenstammfuesse ohnehin
    reichlich; wird der Deckel erreicht, ist nicht die Achse geneigt, sondern die
    Datenlage schlecht -- deshalb faellt der Wert dann weg.
    """
    if len(band) < 20:
        return None, None
    tan_max = math.tan(math.radians(max_tilt))
    from scipy.optimize import minimize
    c = band.mean(axis=0)
    p = band - c

    def project(ab):
        d = np.array([ab[0], ab[1], 1.0])
        d /= np.linalg.norm(d)
        # zwei Basisvektoren senkrecht zur Achse
        u = np.cross(d, [0, 0, 1.0])
        if np.linalg.norm(u) < 1e-8:
            u = np.array([1.0, 0, 0])
        u /= np.linalg.norm(u)
        v = np.cross(d, u)
        return p @ u, p @ v, d

    def cost(ab):
        if math.hypot(ab[0], ab[1]) > tan_max:     # Neigung ausserhalb des Deckels
            return 1e3
        a, b, _ = project(ab)
        fit = fit_circle(a, b)
        return 1e3 if fit is None else fit[3]      # RMS der Radien

    res = minimize(cost, np.zeros(2), method="Nelder-Mead",
                   options={"xatol": 1e-3, "fatol": 1e-5, "maxiter": 300})
    a, b, d = project(res.x)
    fit = fit_circle(a, b)
    if fit is None or not (R_MIN <= fit[2] <= R_MAX):
        return None, None
    tilt = math.degrees(math.acos(abs(d[2])))
    if tilt > max_tilt + 0.5:
        return None, round(tilt, 1)
    return round(200 * fit[2], 1), round(tilt, 1)


def m_geofit(sl):
    """Geometrischer Kreisfit: minimiert die ECHTEN Abstaende Punkt-Kreislinie,
    nicht die algebraische Ersatzgroesse wie Kasa. Gleiche Punkte, gleiche
    Kreisannahme, anderes Fehlermass -- der Kasa-Fit gewichtet weit entfernte
    Punkte quadratisch ueber, der geometrische Fit nicht.

    Achse und Radius sind BESCHRAENKT (Zentrum +/- 30 cm um den Startwert, Radius
    im Stammbereich). Ohne diese Grenzen lief der Solver an zwei Staemmen weg und
    erklaerte die 16 cm dicke Mantelschale als EINEN riesigen Kreis, der sie
    tangential durchlaeuft: 121 statt 20 cm, 131 statt 25 cm. Beides sind gueltige
    Minima des Abstandsmasses -- verboten sind sie nicht durch die Mathematik,
    sondern durch die Geometrie: der Stamm steht dort, wo ihn die Detektion
    gefunden hat. Laeuft der Fit in eine Grenze, faellt der Wert weg.
    """
    if len(sl) < 12:
        return None
    from scipy.optimize import least_squares
    px, py = sl[:, 0], sl[:, 1]
    start = fit_circle(px, py)                      # Kasa als Startwert
    if start is None:
        return None
    cx0, cy0, r0 = start[0], start[1], min(max(start[2], R_MIN), R_MAX)
    lo = [cx0 - 0.3, cy0 - 0.3, R_MIN]
    hi = [cx0 + 0.3, cy0 + 0.3, R_MAX]

    def resid(p):
        return np.hypot(px - p[0], py - p[1]) - p[2]

    try:
        res = least_squares(resid, [cx0, cy0, r0], bounds=(lo, hi), max_nfev=300)
    except Exception:
        return None
    r = float(res.x[2])
    at_bound = (abs(r - R_MIN) < 1e-4 or abs(r - R_MAX) < 1e-4
                or min(abs(res.x[0] - lo[0]), abs(res.x[0] - hi[0])) < 1e-4
                or min(abs(res.x[1] - lo[1]), abs(res.x[1] - hi[1])) < 1e-4)
    return None if at_bound else round(200 * r, 1)


# ---------------------------------------------------------------------- 3DFin
def run_3dfin(xyz, workdir, overrides=None, label="default", reuse=False):
    """3DFin auf der Plot-Wolke. Rueckgabe (Liste (x, y, BHD_cm) in Welt, Meta-Dict).

    'overrides' setzt einzelne 3DFin-Parameter. Gebraucht wird das, weil 3DFins
    Voreinstellung 9 von 16 Sektoren fordert (202 Grad Umfangsabdeckung), dieser
    Bestand aber im Median nur 190 Grad hergibt -- die Voreinstellung verwirft
    dann fast jeden Stamm. Beide Laeufe werden berichtet; angepasst heisst
    angepasst an die ABDECKUNG der Wolke, nicht an ein erwuenschtes Ergebnis.
    """
    import laspy
    from three_d_fin.processing.configuration import FinConfiguration
    from three_d_fin.processing.standalone_processing import StandaloneLASProcessing

    # 3DFin gibt seinen Fortschritt mit Sonderzeichen aus und stirbt an der
    # cp1252-Konsole von Windows (UnicodeEncodeError mitten im Lauf, nach Minuten
    # Rechenzeit). Nicht 3DFins Fehler und keiner unserer Daten -- nur die
    # Standardausgabe muss es aushalten.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    workdir = workdir / label
    off = xyz.min(axis=0)
    if reuse and (workdir / "plot_dbh_and_heights.txt").is_file():
        print(f"  [{label}] 3DFin: vorhandenes Ergebnis wiederverwendet")
        return parse_3dfin(workdir, off, label, overrides)
    workdir.mkdir(parents=True, exist_ok=True)
    loc = xyz - off
    hdr = laspy.LasHeader(point_format=3)
    hdr.offsets = [0.0, 0.0, 0.0]
    hdr.scales = [0.001] * 3
    las = laspy.LasData(hdr)
    las.x, las.y, las.z = loc[:, 0], loc[:, 1], loc[:, 2]
    plot_las = workdir / "plot.las"
    las.write(str(plot_las))
    print(f"  [{label}] 3DFin-Eingabe: {len(loc):,} Punkte")

    cfg = FinConfiguration()
    cp = getattr(cfg, "model_copy", None) or cfg.copy
    misc = (getattr(cfg.misc, "model_copy", None) or cfg.misc.copy)(update={
        "input_file": plot_las, "output_dir": workdir,
        "is_normalized": False, "is_noisy": True, "export_txt": True})
    upd = {"misc": misc}
    for group, vals in (overrides or {}).items():
        sub = getattr(cfg, group)
        upd[group] = (getattr(sub, "model_copy", None) or sub.copy)(update=vals)
    try:
        StandaloneLASProcessing(cp(update=upd)).process()
    except Exception as e:                        # 3DFin scheitert an manchen Wolken
        print(f"  [{label}] 3DFin abgebrochen: {type(e).__name__}: {e}")
        return [], {"lauf": label, "fehler": f"{type(e).__name__}: {e}"}

    return parse_3dfin(workdir, off, label, overrides)


def parse_3dfin(workdir, off, label, overrides):
    """Spalten von *_dbh_and_heights.txt: Hoehe[m], BHD[m], x, y (lokal zur LAS).

    BHD = 0 heisst: 3DFin hat den Stamm gefunden, aber keinen Durchmesser
    akzeptiert (Sektor-/Punktzahl-Pruefung durchgefallen).
    """
    dbh_f = workdir / "plot_dbh_and_heights.txt"
    if not dbh_f.exists():
        print(f"  [{label}] 3DFin: Ergebnisdatei fehlt")
        return [], {"lauf": label, "fehler": "plot_dbh_and_heights.txt fehlt"}
    rows = [r.split() for r in dbh_f.read_text().splitlines() if r.strip()]
    out = []
    for f in rows:
        try:
            d_cm = float(f[1]) * 100.0
            x, y = float(f[2]) + off[0], float(f[3]) + off[1]
        except (IndexError, ValueError):
            continue
        if 2 * R_MIN * 100 <= d_cm <= 2 * R_MAX * 100:
            out.append((x, y, round(d_cm, 1)))
    meta = {"lauf": label, "detektionen": len(rows), "mit_bhd": len(out),
            "parameter": overrides or {}}
    print(f"  [{label}] 3DFin: {len(rows)} Staemme detektiert, "
          f"{len(out)} davon mit akzeptiertem BHD")
    return out, meta


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud", help="Analyse-Wolke (.npz aus e57_merge.py)")
    ap.add_argument("stems", help="Stammliste (CSV aus inventory_from_cloud.py)")
    ap.add_argument("--out", required=True, help="Ergebnis-CSV je Stamm")
    ap.add_argument("--summary", help="Ergebnis-JSON (Uebereinstimmung je Verfahren)")
    ap.add_argument("--origin", nargs=3, type=float, metavar=("X", "Y", "Z"),
                    help="Auswertungsmittelpunkt fuer --radius")
    ap.add_argument("--radius", type=float, default=22.0,
                    help="Punkte innerhalb dieses Umkreises verwenden")
    ap.add_argument("--stem-radius", type=float, default=0.9,
                    help="Suchradius um die Stammposition [m]")
    ap.add_argument("--shell-tol", type=float, default=0.08,
                    help="halbe Dicke der Mantelschale um die Stammachse [m]")
    ap.add_argument("--3dfin-voxel", dest="fin_voxel", type=float, default=0.02,
                    help="Voxelweite der 3DFin-Eingabe [m]")
    ap.add_argument("--3dfin-dir", dest="fin_dir",
                    default=str(REPO / "data" / "Renon" / "_3dfin"),
                    help="Arbeitsverzeichnis fuer die 3DFin-Laeufe")
    ap.add_argument("--no-3dfin", action="store_true")
    ap.add_argument("--3dfin-reuse", dest="fin_reuse", action="store_true",
                    help="vorhandene 3DFin-Ergebnisse im Arbeitsverzeichnis nutzen "
                         "statt neu zu rechnen")
    args = ap.parse_args()

    d = np.load(args.cloud)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    if args.origin:
        ox, oy, _ = args.origin
        xyz = xyz[np.hypot(xyz[:, 0] - ox, xyz[:, 1] - oy) <= args.radius]
    print(f"{len(xyz):,} Punkte in der Auswertung")

    stems = list(csv.DictReader(open(args.stems, encoding="utf-8-sig")))
    print(f"{len(stems)} Staemme aus {Path(args.stems).name}")
    ground = ground_grid(xyz)

    fin, fin_meta = [], []
    if not args.no_3dfin:
        print("3DFin auf der Plot-Wolke ...")
        k = np.floor(xyz / args.fin_voxel).astype(np.int64)
        _, keep = np.unique((k[:, 0] * 73856093) ^ (k[:, 1] * 19349663)
                            ^ (k[:, 2] * 83492791), return_index=True)
        fin_dir = Path(args.fin_dir)
        # Lauf 1: 3DFin unveraendert -- das Ergebnis, das ein Nutzer bekommt.
        _, m0 = run_3dfin(xyz[keep], fin_dir, label="default", reuse=args.fin_reuse)
        # Lauf 2: Umfangsforderung auf die tatsaechliche Abdeckung gesenkt
        # (7 von 16 Sektoren = 157 Grad statt 202) und Mindestpunktzahl je
        # Abschnitt halbiert, weil die Eingabe auf Voxelweite ausgeduennt ist.
        fin, m1 = run_3dfin(xyz[keep], fin_dir, label="angepasst",
                            reuse=args.fin_reuse, overrides={
                                "expert": {"m_number_sectors": 7,
                                           "number_points_section": 40}})
        fin_meta = [m0, m1]

    rows = []
    for st in stems:
        sx, sy = float(st["x"]), float(st["y"])
        g = ground_at(ground, sx, sy)
        near = np.hypot(xyz[:, 0] - sx, xyz[:, 1] - sy) <= args.stem_radius
        sub = xyz[near]
        r = {"id": st.get("label") or st.get("id"), "x": round(sx, 3), "y": round(sy, 3)}
        if g is None or len(sub) < 20:
            rows.append(r)
            continue
        h = sub[:, 2] - g
        band, _ = stem_shell(sub[(h >= BH_LO) & (h <= BH_HI)], sx, sy, args.shell_tol)
        sl, r0 = stem_shell(sub[(h >= SLICE_LO) & (h <= SLICE_HI)], sx, sy,
                            args.shell_tol)
        r["Punkte_Scheibe"] = int(len(sl))
        r["Schale_r_cm"] = None if math.isnan(r0) else round(100 * r0, 1)
        # Plausibilitaet der Schale gegen die Detektion: die Stammdetektion hat
        # den Radius schon einmal mit Guetepruefung (Residuum, Bogen) bestimmt.
        # Weicht der Modus des Abstandshistogramms davon stark ab, liegt die
        # Schale nicht auf DIESEM Stamm, sondern auf der Mantelflaeche eines
        # dicken Nachbarn -- dann fitten alle Verfahren einvernehmlich denselben
        # falschen Kreis. Genau so kamen 137 cm an einem Bestand heraus, dessen
        # groesster gepruefter Stamm 62,5 cm hat. Solche Staemme werden hier NICHT
        # mit einer Zahl veroeffentlicht, sondern als unmessbar gekennzeichnet.
        r_det = float(st["BHD_cm"]) / 200.0 if st.get("BHD_cm") else None
        unsicher = bool(r_det and not math.isnan(r0)
                        and abs(r0 - r_det) > max(0.10, 0.5 * r_det))
        if unsicher:
            r["hinweis"] = (f"Mantelschale bei r={100*r0:.0f} cm, Detektion "
                            f"r={100*r_det:.0f} cm -- Scheibe evtl. nicht dieser Stamm")
        # Gerechnet wird trotzdem: einen ermittelten Wert wegzulassen ist keine
        # Vorsicht, sondern ein Datenverlust. Der Vorbehalt gehoert NEBEN die Zahl
        # (Spalte 'guete', im Viewer als Warnung), nicht an ihre Stelle.
        if len(sl) >= 12:
            r["kreisfit"], r["Fit_RMS_cm"], arc = m_kreisfit(sl)
            r["Bogen_deg"] = arc
            r["geofit"] = m_geofit(sl)
            r["ransac"], r["RANSAC_Inlier_pct"] = m_ransac(sl)
        if len(band) >= 20:
            r["zylinder"], r["Neigung_deg"] = m_zylinder(band)
        if fin:
            cand = [(math.hypot(fx - sx, fy - sy), fd) for fx, fy, fd in fin]
            dist, fd = min(cand)
            if dist <= 0.6:
                r["3dfin"], r["3dfin_Abstand_m"] = fd, round(dist, 2)
        vals = [r[m] for m in CORE if r.get(m) is not None]
        if vals:
            r["konsens"] = round(float(np.median(vals)), 1)
            r["n_verfahren"] = len(vals)
            r["spanne_cm"] = round(max(vals) - min(vals), 1)
        r["guete"] = ("unsicher" if unsicher
                      else "gut" if (arc_ok(r) and len(sl) >= GOOD_PTS) else "schwach")
        # Schaftkontrolle: hat der Stamm ueber der Brusthoehe ueberhaupt Bestand?
        # Trennt echte Baeume von Fehldetektionen (Totholz, Wurzelteller, dichtes
        # Gestruepp), die einen sauberen Kreis in EINER Scheibe liefern koennen.
        # Radius fuer die Schaftkontrolle: Schale, sonst die Detektion, sonst ein
        # Mindestmass. Mit nan wuerde jeder Vergleich False und JEDER Stamm als
        # Fehldetektion gelten -- ein stiller Totalausfall des Filters.
        r_cont = r0 if not math.isnan(r0) else (r_det if r_det else 0.15)
        r["schaft_bandanteil"], r["schaft_durchgehend"] = stem_continuity(
            sub, h, sx, sy, max(r_cont, 0.05))
        rows.append(r)

    fields = (["id", "x", "y"] + METHODS
              + ["konsens", "n_verfahren", "spanne_cm", "guete", "Fit_RMS_cm",
                 "Bogen_deg", "RANSAC_Inlier_pct", "Neigung_deg", "3dfin_Abstand_m",
                 "Punkte_Scheibe", "Schale_r_cm", "schaft_bandanteil",
                 "schaft_durchgehend", "hinweis"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k, "")) for k in fields})
    print(f"-> {args.out}: {len(rows)} Staemme")

    # Uebereinstimmung je Verfahren: Abweichung vom Konsens der jeweiligen Zeile.
    # Nur Staemme mit brauchbarer Datenlage ('gut') und vollem Konsens -- an einem
    # Stamm mit 120 Grad Bogen und 70 Punkten vergleicht man sonst Rauschen.
    good = [r for r in rows
            if r.get("guete") == "gut" and r.get("n_verfahren") == len(CORE)]
    stats = {}
    for m in METHODS:
        dev = [r[m] - r["konsens"] for r in good if r.get(m) is not None]
        if not dev:
            stats[m] = {"n": 0}
            continue
        a = np.array(dev)
        stats[m] = {"n": len(a), "bias_cm": round(float(a.mean()), 2),
                    "mad_cm": round(float(np.abs(a).mean()), 2),
                    "p95_abw_cm": round(float(np.percentile(np.abs(a), 95)), 2),
                    "im_konsens": m in CORE}
        print(f"  {m:9} n={len(a):3}  Bias {a.mean():+5.2f} cm  "
              f"mittlere |Abw| {np.abs(a).mean():4.2f} cm"
              f"{'' if m in CORE else '   (unabhaengig, nicht im Konsens)'}")
    spans = [r["spanne_cm"] for r in good]
    summary = {
        "plot": Path(args.stems).stem,
        "n_staemme": len(rows),
        "n_guete_gut": sum(1 for r in rows if r.get("guete") == "gut"),
        "n_bewertet": len(good),
        "konsens_verfahren": CORE,
        "unabhaengige_verfahren": EXTRA,
        "median_spanne_cm": round(float(np.median(spans)), 2) if spans else None,
        "guete_schwelle": {"bogen_deg": GOOD_ARC, "punkte_scheibe": GOOD_PTS},
        "verfahren": stats,
        "dreidfin_laeufe": fin_meta,
        "hinweis": ("Ohne Feld-Ground-Truth ist das UEBEREINSTIMMUNG (Praezision), "
                    "keine Genauigkeit -- die Verfahren koennen gemeinsam falsch "
                    "liegen. Konsens = Median aus " + ", ".join(CORE) + " je Stamm; "
                    + " und ".join(EXTRA) + " werden dagegen gehalten. Genauigkeit "
                    "gegen Feldmessung: scripts/BENCH_DBH.md (SYSSIFOSS, n=5)."),
    }
    if spans:
        print(f"  Median-Spanne der Konsens-Verfahren: {np.median(spans):.1f} cm "
              f"(an {len(good)} von {len(rows)} Staemmen bewertet)")
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        print(f"-> {args.summary}")


if __name__ == "__main__":
    main()
