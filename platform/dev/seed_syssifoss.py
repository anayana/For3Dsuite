#!/usr/bin/env python3
"""seed_syssifoss.py -- SYSSIFOSS-Einzelbaeume (TLS) als begehbare Punktwolken-Szenen.

Quelle: heiDATA doi:10.11588/DATA/UUMEDI (SYSSIFOSS, Uni Heidelberg / KIT),
RIEGL VZ-400, elf manuell blatt-/holz-separierte Einzelbaeume aus den zwoelf
Waldplots bei Bretten und Karlsruhe. Die Wolken tragen ihre echten
EPSG:25832-Koordinaten, Baeume desselben Plots lassen sich daher in ihrer
realen Nachbarschaft wieder zusammensetzen.

Besonderheit des Datensatzes: die LAS-classification ist die MANUELLE
Blatt-Holz-Trennung -- 0 = Holz, 1 = Blatt (geprueft am Stammfuss: dort ist
class 0 mit ~99 % dominant). Genau danach wird eingefaerbt, die Einfaerbung
zeigt also gemessene Ground Truth, keine Schaetzung. Der BHD wird nur aus den
Holzpunkten gefittet -- Blattpunkte im Brusthoehenring wuerden ihn aufblaehen.

Drei Szenen:
  syssifoss-br01       Plot BR01, Buche + Traubeneiche, ECHTE Relativlage
  syssifoss-ka09       Plot KA09, Waldkiefer + Roteiche, ECHTE Relativlage
  syssifoss-arboretum  alle elf Baeume, sechs Arten -- Anordnung SYNTHETISCH
                       (die Originalstandorte liegen bis zu 20 km auseinander),
                       Geometrie und Groesse je Baum bleiben unveraendert

  python platform/dev/seed_syssifoss.py                  # alle drei
  python platform/dev/seed_syssifoss.py syssifoss-br01   # einzeln
"""
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
SRC = REPO / "data" / "dataverse_files"
sys.path.insert(0, str(REPO / "scripts"))
from inventory_from_cloud import fit_circle                       # noqa: E402

WOOD, LEAF = 0, 1                    # LAS-classification im Quelldatensatz
C_WOOD = np.array([150, 108, 68], np.uint8)     # Rinde
C_LEAF = np.array([104, 168, 78], np.uint8)     # Laub/Nadel

SPECIES = {"AcePse": "Bergahorn", "FagSyl": "Rotbuche", "PicAbi": "Fichte",
           "PinSyl": "Waldkiefer", "PseMen": "Douglasie", "QuePet": "Traubeneiche",
           "QueRub": "Roteiche"}

LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]

SCENES = {
    "syssifoss-br01": {
        "title": "SYSSIFOSS Plot BR01 — Buche & Traubeneiche",
        "trees": ["FagSyl_BR01_01", "QuePet_BR01_01"],
        "layout": "real",
    },
    "syssifoss-ka09": {
        "title": "SYSSIFOSS Plot KA09 — Waldkiefer & Roteiche",
        "trees": ["PinSyl_KA09_T048", "QueRub_KA09_T053"],
        "layout": "real",
    },
    "syssifoss-arboretum": {
        "title": "SYSSIFOSS Arboretum — 11 Bäume, 6 Arten",
        "trees": None,                                   # alle
        "layout": "grid",
    },
}

DATASET = "SYSSIFOSS single trees, leaf-wood separated (RIEGL VZ-400)"
DOI = "https://doi.org/10.11588/DATA/UUMEDI"


def tree_key(path):
    """'FagSyl_BR01_01_2019-07-08_q1_TLS-on_c.laz' -> 'FagSyl_BR01_01'."""
    return re.sub(r"_\d{4}-\d{2}-\d{2}_.*$", "", path.stem)


def load_tree(path):
    """(xyz float64, classification uint8) einer Baumwolke.

    Bewusst float64: die Rechtswerte liegen bei 5,4e6, in float32 bleiben davon
    keine 0,5 m Aufloesung uebrig -- der Stammquerschnitt waere danach ein
    Quantisierungsraster statt eines Kreises und der BHD-Fit reiner Zufall.
    Auf float32 wird erst heruntergerechnet, wenn die Punkte auf den
    Szenen-Ursprung bezogen sind (dann sind die Betraege klein).
    """
    import laspy
    las = laspy.read(str(path))
    xyz = np.c_[las.x, las.y, las.z].astype(np.float64)
    return xyz, np.asarray(las.classification, np.uint8)


def positions():
    """{ID: (Art, Easting, Northing)} aus der beiliegenden CSV."""
    out = {}
    for line in (SRC / "positions_epsg25832.csv").read_text().splitlines()[1:]:
        if not line.strip():
            continue
        tid, art, e, n, _h = line.split(",")
        out[tid] = (art, float(e), float(n))
    return out


def trunk_center(sl):
    """Dichteste 25-cm-Zelle des Brusthoehen-Schnitts = Stammachse.

    Die Wolken sind aus dem Plotscan ausgeschnitten, im Brusthoehenring liegen
    daher auch Unterwuchs- und Nachbarstamm-Punkte ueber die ganzen ~10 m
    Grundflaeche verteilt. Ein Kreis-Fit ueber alles liefert Radien im
    Kilometerbereich -- erst auf den Stamm eingrenzen, dann fitten.
    """
    step = 0.25
    kx = np.floor(sl[:, 0] / step).astype(np.int64)
    ky = np.floor(sl[:, 1] / step).astype(np.int64)
    _keys, inv, cnt = np.unique(np.c_[kx, ky], axis=0, return_inverse=True,
                                return_counts=True)
    core = sl[inv == int(np.argmax(cnt))]
    return core[:, :2].mean(0)


def metrics(xyz, cls):
    """Hoehe ueber Stammfuss und BHD -- Kreis-Fit NUR auf Holzpunkten.

    Der Fit wird eingeschnuert: Start am dichtesten Stammpixel mit weitem
    Fangradius, dann je Runde Zentrum nachfuehren und Fangradius auf das
    1,35-fache des aktuellen Stammradius ziehen. Ohne dieses Nachziehen
    bleiben Nachbarstaemme im Ring und blaehen den BHD auf das Mehrfache auf
    (110 cm an einer 10,8-m-Roteiche statt der tatsaechlichen 9 cm).
    """
    base = float(np.percentile(xyz[:, 2], 1))
    height = float(xyz[:, 2].max() - base)
    rel = xyz[:, 2] - base
    sl = xyz[(rel >= 1.2) & (rel <= 1.4) & (cls == WOOD)].astype(float)
    bhd = None
    xy = xyz[:, :2].mean(0)
    if len(sl) >= 40:
        c = trunk_center(sl)
        gate, last = 0.9, None
        for _ in range(6):
            near = sl[np.hypot(sl[:, 0] - c[0], sl[:, 1] - c[1]) <= gate]
            if len(near) < 40:
                break
            # lokal zentriert fitten: UTM-Absolutwerte (5.4e6) kosten sonst
            # die Genauigkeit, die der Zentimeter-Radius braucht
            fit = fit_circle(near[:, 0] - c[0], near[:, 1] - c[1])
            if not fit:
                break
            cx, cy, r, rms, arc = fit
            c = np.array([c[0] + cx, c[1] + cy])
            gate = max(r * 1.35, 0.12)
            last = (r, rms, arc)
        if last:
            r, rms, arc = last
            xy = c
            if 0.02 <= r <= 1.2 and rms <= 0.03 and arc >= 180.0:
                bhd = round(2 * r * 100, 1)
    return float(xy[0]), float(xy[1]), base, height, bhd


def write_bin(path, xyz, rgb, origin):
    """xyz liegt bereits relativ zum Ursprung; origin nur fuer die Metadaten."""
    xyz = np.ascontiguousarray(xyz, "<f4")
    path.write_bytes(xyz.tobytes() + rgb.astype(np.uint8).tobytes())
    path.with_suffix(".json").write_text(json.dumps({
        "count": int(len(xyz)),
        "origin_xyz": [float(c) for c in origin],
        "bbox_min": [float(c) for c in xyz.min(0)],
        "bbox_max": [float(c) for c in xyz.max(0)]}, indent=2))


def thumbnail(dest, xyz, rgb):
    """Seitenansicht (x/z) -- zeigt Wuchsform und Blatt-Holz-Trennung."""
    W, H = 640, 320
    img = np.full((H, W, 3), 13, np.uint8)
    x, z = xyz[:, 0], xyz[:, 2]
    nx = ((x - x.min()) / max(np.ptp(x), 1e-6) * (W - 1)).astype(int)
    nz = ((z - z.min()) / max(np.ptp(z), 1e-6) * (H - 1)).astype(int)
    img[H - 1 - nz, nx] = rgb
    Image.fromarray(img).save(dest, quality=85)


def grid_offsets(n, spacing=16.0):
    """Baeume in ein moeglichst quadratisches Raster legen (Arboretum)."""
    cols = math.ceil(math.sqrt(n))
    return [((i % cols) * spacing, (i // cols) * spacing) for i in range(n)]


def build(sid, spec, files, pos):
    dest = MEDIA / "scenes" / sid
    dest.mkdir(parents=True, exist_ok=True)

    keys = spec["trees"] or sorted(files)
    missing = [k for k in keys if k not in files]
    if missing:
        print(f"  {sid}: fehlende Baeume {missing} -- uebersprungen")
        return

    # Je Baum: Punkte lokal zum eigenen Stammfuss (klein -> float32-tauglich),
    # dazu der Platz, an den dieser Fuss in der Szene kommt.
    offs = grid_offsets(len(keys)) if spec["layout"] == "grid" else None
    locals_, cls_all, places, trees = [], [], [], []
    for i, k in enumerate(keys):
        src, cls = load_tree(files[k])
        foot = np.array([src[:, 0].mean(), src[:, 1].mean(),
                         np.percentile(src[:, 2], 1)], np.float64)
        # Synthetische Anordnung setzt den Fuss auf den Rasterpunkt; die
        # Baumgeometrie selbst bleibt in beiden Faellen unangetastet.
        place = np.array([offs[i][0], offs[i][1], 0.0]) if offs else foot
        locals_.append((src - foot).astype(np.float32))
        cls_all.append(cls)
        places.append(place)
        trees.append((k, src, cls, place - foot))

    origin = np.array([np.mean([p[0] for p in places]),
                       np.mean([p[1] for p in places]),
                       min(p[2] for p in places)], np.float64)
    xyz = np.concatenate([lc + (pl - origin).astype(np.float32)
                          for lc, pl in zip(locals_, places)])
    del locals_
    cls = np.concatenate(cls_all)
    rgb = np.where((cls == LEAF)[:, None], C_LEAF, C_WOOD).astype(np.uint8)

    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        idx = (rng.choice(len(xyz), maxpts, replace=False)
               if len(xyz) > maxpts else np.arange(len(xyz)))
        write_bin(dest / fname, xyz[idx], rgb[idx], origin)
        mj = json.loads((dest / fname).with_suffix(".json").read_text())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{sid}/{fname}",
                       "count": mj["count"], "bbox_min": mj["bbox_min"],
                       "bbox_max": mj["bbox_max"]})
        if lid == "lite":
            thumbnail(dest / "thumb.jpg", xyz[idx], rgb[idx])

    markers, arten = [], {}
    for i, (k, txyz, tcls, shift) in enumerate(trees, 1):
        art = SPECIES.get(k.split("_")[0], k.split("_")[0])
        # metrics rechnet in den Original-Koordinaten (float64, praezise),
        # das Ergebnis wird danach an den Platz in der Szene geschoben
        x, y, base, height, bhd = metrics(txyz, tcls)
        x, y, base = x + shift[0], y + shift[1], base + shift[2]
        arten[art] = arten.get(art, 0) + 1
        leaf_share = round(100.0 * float((tcls == LEAF).mean()), 1)
        attrs = {"Art": art, "Plot": k.split("_")[1], "Hoehe_m": round(height, 1),
                 "Blattanteil_pct": leaf_share, "Punkte": int(len(txyz))}
        if bhd:
            attrs["BHD_cm"] = bhd
        # QSM-Kennwerte anhaengen, falls fuer den Baum gerechnet (data/qsm/<key>.json,
        # aus scripts/qsm_tree.R). Das Zylindermodell liefert Groessen, die aus der
        # Punktwolke allein nicht ablesbar sind: Holzvolumen, Oberflaeche,
        # Verzweigungsordnung -- plus den BHD als unabhaengige Gegenprobe zum Kreis-Fit.
        qsm_f = REPO / "data" / "qsm" / f"{k}.json"
        if qsm_f.is_file():
            q = json.loads(qsm_f.read_text(encoding="utf-8"))
            qm, qmod = q.get("metriken", {}), q.get("modell", {})
            if qm.get("holzvolumen_l"):
                attrs["QSM_Holzvolumen_l"] = qm["holzvolumen_l"]
            if qm.get("holzoberflaeche_m2"):
                attrs["QSM_Oberflaeche_m2"] = qm["holzoberflaeche_m2"]
            if qmod.get("max_verzweigungsordnung"):
                attrs["QSM_Verzweigungsordnung"] = qmod["max_verzweigungsordnung"]
            if qmod.get("zylinder"):
                attrs["QSM_Zylinder"] = qmod["zylinder"]
            # QSM-BHD nur als Gegenprobe zeigen, wenn er zum Kreis-Fit passt
            # (<=25 %). Bei dicken, einseitig verdeckten Staemmen zerlegt die
            # Skelettierung den Stamm in duenne Parallelzylinder -> QSM-BHD
            # unbrauchbar (Buche: 11 statt 38 cm). Dann lieber weglassen.
            qb = qm.get("bhd_aus_qsm_cm")
            if qb and bhd and abs(qb - bhd) / bhd <= 0.25:
                attrs["QSM_BHD_cm"] = qb
        dx, dy, dz = x - origin[0], y - origin[1], (base + 1.3) - origin[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        markers.append({
            "id": f"t{i:03d}", "label": f"{art} {k}",
            "yaw": round(math.degrees(math.atan2(dy, dx)), 3),
            "pitch": round(math.degrees(math.asin(dz / dist)), 3),
            "xyz": [round(x, 3), round(y, 3), round(base + 1.3, 3)],
            "attributes": attrs, "demo": False})

    artliste = ", ".join(f"{n}x {a}" for a, n in sorted(arten.items()))
    if spec["layout"] == "real":
        plot = keys[0].split("_")[1]
        span = max(math.dist(markers[a]["xyz"][:2], markers[b]["xyz"][:2])
                   for a in range(len(markers)) for b in range(len(markers)))
        lage = (f"Plot {plot}: die {len(keys)} Baeume stehen in ihrer ECHTEN "
                f"Relativlage (EPSG:25832), Abstand {span:.0f} m -- der Raum "
                f"zwischen ihnen ist frei begehbar.")
    else:
        lage = (f"Anordnung SYNTHETISCH im 16-m-Raster: die Originalstandorte "
                f"liegen ueber ~20 km verteilt. Geometrie, Hoehe und Dicke jedes "
                f"Baums bleiben unveraendert -- ein Arboretum zum Artvergleich.")

    scene = {
        "id": sid, "title": spec["title"],
        "description": (f"Terrestrischer Laserscan (RIEGL VZ-400) einzelner Baeume "
                        f"aus mitteleuropaeischen Mischwaldplots bei Bretten und "
                        f"Karlsruhe. {len(keys)} Baeume ({artliste}). {lage} "
                        f"Einfaerbung = manuelle Blatt-Holz-Trennung des Datensatzes "
                        f"(gruen = Blatt/Nadel, braun = Holz, Ground Truth); der BHD "
                        f"ist allein aus den Holzpunkten gefittet. Kein Panorama im "
                        f"Datensatz enthalten. Quelle: SYSSIFOSS, heiDATA "
                        f"doi:10.11588/DATA/UUMEDI, CC-BY-4.0."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{sid}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "syssifoss-tls", "origin_xyz": [float(c) for c in origin],
                   "dataset": DATASET, "url": DOI, "license": "CC-BY-4.0"},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": markers,
    }
    if spec["layout"] == "real":
        art, e, n = pos[keys[0]]
        scene["source"]["gps"] = utm32_to_wgs84(e, n)

    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    n_bhd = sum(1 for m in markers if "BHD_cm" in m["attributes"])
    print(f"  Szene '{sid}': {len(keys)} Baeume, {len(xyz):,} Punkte "
          f"(Stufen {levels[0]['count']:,}/{levels[1]['count']:,}), BHD fuer {n_bhd}")


def utm32_to_wgs84(e, n):
    """UTM 32N (EPSG:25832) -> WGS84, Karten-Pin fuer die Galerie-Uebersicht."""
    k0, a, f = 0.9996, 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    m = (n - 0.0) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    p = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
         + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
         + (151 * e1**3 / 96) * math.sin(6 * mu))
    ep2 = e2 / (1 - e2)
    c1, t1 = ep2 * math.cos(p)**2, math.tan(p)**2
    r1 = a * (1 - e2) / (1 - e2 * math.sin(p)**2)**1.5
    n1 = a / math.sqrt(1 - e2 * math.sin(p)**2)
    d = (e - 500000.0) / (n1 * k0)
    lat = p - (n1 * math.tan(p) / r1) * (
        d**2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d**3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120) / math.cos(p)
    return {"lat": round(math.degrees(lat), 6), "lon": round(math.degrees(lon) + 9.0, 6)}


def main():
    if not SRC.is_dir():
        raise SystemExit(f"Quelldaten fehlen: {SRC}")
    files = {tree_key(p): p for p in SRC.glob("*.laz")}
    if not files:
        raise SystemExit(f"Keine .laz in {SRC}")
    pos = positions()
    want = sys.argv[1:] or list(SCENES)
    for sid in want:
        if sid not in SCENES:
            print(f"  Unbekannte Szene: {sid}"); continue
        build(sid, SCENES[sid], files, pos)


if __name__ == "__main__":
    main()
