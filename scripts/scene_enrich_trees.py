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
    "schwach": "Datenlage schwach (wenig Punkte oder kurzer Bogen) -- die Werte "
               "stehen trotzdem da, die Spanne der Verfahren zeigt, was sie taugen",
    "unsicher": "Die Brusthoehen-Scheibe passt nicht zum detektierten Stammradius -- "
                "moeglicherweise ein Nachbarstamm in der Scheibe. Werte mit Vorbehalt.",
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

    # Fehldetektionen aussortieren: was in 1,3 m rund aussieht, aber darueber
    # keinen Schaft hat, ist kein Baum (liegendes Holz, Wurzelteller, Gestruepp).
    # Ohne diesen Schritt stehen Marker im Bestand, wo gar kein Stamm ist.
    dropped = []
    if dbh:
        keep = []
        for mk in markers:
            d = dbh.get(mk.get("label"))
            if d and d.get("schaft_durchgehend") == "nein":
                dropped.append((mk.get("label"), d.get("schaft_bandanteil")))
            else:
                keep.append(mk)
        markers = keep
        scene["markers"] = markers
        if dropped:
            print(f"{len(dropped)} Fehldetektionen entfernt (kein durchgehender "
                  f"Schaft ueber 1,3 m): "
                  + ", ".join(f"{n} ({s})" for n, s in dropped[:8])
                  + (" ..." if len(dropped) > 8 else ""))

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
            # Baumhoehe aus der EIGENEN Krone statt aus "hoechster Punkt im
            # 1,5-m-Umkreis". Der Umkreis greift im dichten Bestand in die
            # Nachbarkrone: 8,3-cm-Staemmchen kamen so auf 20,7 m Hoehe. Mit der
            # ITCD-Zuordnung sind es 9,1 m, und die Korrelation zwischen BHD und
            # Hoehe steigt ueber alle Baeume von 0,27 auf 0,40.
            # 'Hoehe_m' aus dem Kronen-CSV = eigene Kronenpunkte PLUS die nicht
            # zugeordneten darueber; 'Kronenhoehe_m' waeren nur die eigenen.
            hi = num(c.get("Hoehe_m")) or num(c.get("Kronenhoehe_m"))
            if hi is not None:
                if num(a.get("Hoehe_m")) is not None:
                    a["Hoehe_Umkreis_m"] = num(a["Hoehe_m"])
                a["Hoehe_m"] = hi
                a["Hoehe_Quelle"] = "ITCD-Segmentierung (eigene Kronenpunkte)"
                g = num(a.get("Grundflaeche_m2"))
                if g is not None:      # Schaftvolumen mit der neuen Hoehe
                    a["Volumen_m3"] = round(g * hi * 0.5, 3)
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
            # Kopfzahl: normalerweise der Konsens der Verfahren. Bei 'unsicher'
            # passt die Brusthoehen-Scheibe nicht zum detektierten Stammradius --
            # dort liegen alle Scheiben-Verfahren einvernehmlich daneben (bis
            # 137 cm in einem Bestand mit 62,5 cm Maximum). Dann gilt der Wert der
            # Stammdetektion: auch der ist ein ERMITTELTER Wert mit eigener
            # Guetepruefung (Residuum <= 3 cm, Bogen >= 100 Grad), nur eben aus
            # der zusammenhaengenden Stammkomponente statt aus der Scheibe.
            # Sichtbar bleibt trotzdem alles: die Verfahrenstabelle zeigt jeden
            # einzelnen Wert samt Abweichung.
            det = num(d.get("kreisfit"))
            if guete == "unsicher" and num(a.get("BHD_cm")) is not None:
                mk["dbh_benchmark"]["detection_cm"] = num(a["BHD_cm"])
            else:
                a["BHD_cm"] = cons
            a["BHD_Verfahren"] = len([m for m in methods if m["consensus"]])
            a["BHD_Guete"] = guete
            if d.get("hinweis"):
                a["BHD_Hinweis"] = d["hinweis"]
            n_dbh += 1
        else:
            # Kein Verfahren hat gerechnet (zu wenig Punkte in der Scheibe). Der
            # BHD der Detektion bleibt stehen -- er hat seine eigene Guetepruefung
            # bestanden (Residuum, Winkelabdeckung) und ist ein ermittelter Wert.
            a["BHD_Guete"] = guete or "nur Detektion"
            if d.get("hinweis"):
                a["BHD_Hinweis"] = d["hinweis"]

    spath.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(markers)} Marker: {n_dbh} mit BHD-Methodenvergleich, "
          f"{n_crown} mit Kronenmetriken, {n_qsm} mit QSM-Kennzahlen")
    print(f"-> {spath}")


if __name__ == "__main__":
    main()
