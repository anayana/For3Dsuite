#!/usr/bin/env python3
"""scene_enrich_trees.py -- Auswertungen je Baum in die Szenen-Marker schreiben.

Fuehrt zusammen, was die Einzelschritte je Baum ergeben haben, und legt es an den
Markern ab, die markers_from_xyz.py aus der Stammdetektion erzeugt hat:

  --dbh     dbh_methods.py   BHD je Verfahren + Konsens + Guete -> marker.dbh_benchmark
  --crowns  itcd_cloud.py    Kronenansatz/-laenge/-durchmesser/-volumen
  --qsm     qsm_cloud.py     Holzvolumen, Stammvolumen, Oberflaeche, QSM-BHD,
                             Verzweigungsordnung, Zylinderzahl

Zuordnung ueber das Label ("Baum 07") -- alle drei Quellen stammen aus DERSELBEN
Stammdetektion, die IDs meinen also denselben Baum. Das ist bei dieser Suite
ausdruecklich nicht selbstverstaendlich: Stand-Inventur und Szenen-Marker sind
getrennte Laeufe, deren gleiche IDs verschiedene Baeume meinen (Median-Versatz
14 m, s. treegross_export.trees_from_stand). Hier ist die Quelle dieselbe.

  python scripts/scene_enrich_trees.py <scene.json> \\
      --dbh data/Renon/dbh_methods_combined.csv \\
      --crowns data/Renon/crowns_combined.csv \\
      --qsm data/Renon/qsm_combined.json
"""
import argparse
import csv
import json
from pathlib import Path

# Anzeigenamen der BHD-Verfahren im Viewer
METHOD_LABELS = {
    "kreisfit": "Kreisfit (Kasa)",
    "geofit": "Kreisfit (geometrisch)",
    "ransac": "RANSAC-Kreisfit",
    "zylinder": "Zylinderfit (3D)",
    "3dfin": "3DFin",
    "qsm": "QSM (Schafttaper)",
}
CONSENSUS_METHODS = ("kreisfit", "geofit", "ransac", "zylinder")
GUETE_TEXT = {
    "gut": "Datenlage gut (Bogen >= 180 Grad, >= 200 Punkte in der Scheibe)",
    "schwach": "Datenlage schwach -- wenig Punkte oder kurzer Bogen",
    "unsicher": "kein eindeutiger Stamm in der Scheibe -- Werte zurueckgehalten",
}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scene")
    ap.add_argument("--dbh", help="CSV aus dbh_methods.py")
    ap.add_argument("--crowns", help="CSV aus itcd_cloud.py")
    ap.add_argument("--qsm", help="JSON aus qsm_cloud.py")
    args = ap.parse_args()

    spath = Path(args.scene)
    scene = json.loads(spath.read_text(encoding="utf-8"))
    markers = scene.get("markers") or []
    if not markers:
        raise SystemExit("Szene hat keine Marker -- erst markers_from_xyz.py laufen lassen")

    dbh = {}
    if args.dbh:
        dbh = {r["id"]: r for r in csv.DictReader(open(args.dbh, encoding="utf-8-sig"))}
    crowns = {}
    if args.crowns:
        crowns = {r["label"]: r
                  for r in csv.DictReader(open(args.crowns, encoding="utf-8-sig"))}
    qsm = {}
    if args.qsm:
        qsm = json.loads(Path(args.qsm).read_text(encoding="utf-8")).get("baeume", {})

    n_dbh = n_crown = n_qsm = 0
    for mk in markers:
        label = mk.get("label")
        a = mk.setdefault("attributes", {})

        # ---- Kronenmetriken (aus der ITCD-Segmentierung) ----
        c = crowns.get(label)
        if c:
            for k in ("Kronenansatz_m", "Kronenlaenge_m", "Kronendurchmesser_m",
                      "Kronenvolumen_m3"):
                v = num(c.get(k))
                if v is not None:
                    a[k] = v
            if num(c.get("Punkte_ITCD")) is not None:
                a["Punkte_ITCD"] = int(float(c["Punkte_ITCD"]))
            n_crown += 1

        # ---- QSM-Kennzahlen ----
        q = qsm.get(label) or {}
        qbhd = num(q.get("bhd_qsm_cm"))
        if q.get("zylinder"):
            a["QSM_Zylinder"] = int(q["zylinder"])
            a["QSM_Verzweigungsordnung"] = int(q.get("max_ordnung") or 0)
            for src, dst in (("holzvolumen_l", "QSM_Holzvolumen_l"),
                             ("stammvolumen_l", "QSM_Stammvolumen_l"),
                             ("kronenholz_l", "QSM_Kronenholz_l"),
                             ("oberflaeche_m2", "QSM_Oberflaeche_m2")):
                if num(q.get(src)) is not None:
                    a[dst] = num(q[src])
            if num(q.get("stammlaenge_m")) is not None:
                a["QSM_Schaftlaenge_m"] = num(q["stammlaenge_m"])
            if qbhd is not None:
                a["QSM_BHD_cm"] = qbhd
            n_qsm += 1

        # ---- BHD-Methodenvergleich ----
        d = dbh.get(label)
        if not d:
            continue
        guete = d.get("guete") or ""
        methods = []
        for key in CONSENSUS_METHODS + ("3dfin",):
            v = num(d.get(key))
            if v is not None:
                methods.append({"name": METHOD_LABELS[key], "dbh_cm": v,
                                "consensus": key in CONSENSUS_METHODS})
        if qbhd is not None:
            methods.append({"name": METHOD_LABELS["qsm"], "dbh_cm": qbhd,
                            "consensus": False})
        cons = num(d.get("konsens"))
        if methods and cons is not None:
            mk["dbh_benchmark"] = {
                "consensus_cm": cons,
                "spread_cm": num(d.get("spanne_cm")),
                "quality": guete,
                "quality_note": GUETE_TEXT.get(guete, ""),
                "methods": methods,
            }
            # Konsens als gemessener BHD fuehren -- er ist der Median mehrerer
            # Verfahren, der Einzelfit der Detektion war nur eines davon.
            a["BHD_cm"] = cons
            a["BHD_Verfahren"] = len([m for m in methods if m["consensus"]])
            a["BHD_Guete"] = guete
            n_dbh += 1
        elif guete == "unsicher":
            # Kein belastbarer BHD: die Zahl der Detektion NICHT als Messwert
            # stehen lassen, sondern den Vorbehalt sichtbar machen.
            a["BHD_Guete"] = guete
            a["BHD_Hinweis"] = d.get("hinweis") or GUETE_TEXT[guete]

    spath.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(markers)} Marker: {n_dbh} mit BHD-Methodenvergleich, "
          f"{n_crown} mit Kronenmetriken, {n_qsm} mit QSM-Kennzahlen")
    print(f"-> {spath}")


if __name__ == "__main__":
    main()
