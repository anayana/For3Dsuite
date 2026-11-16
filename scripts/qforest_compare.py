#!/usr/bin/env python3
"""qforest_compare.py -- Kennwerte und Profile der vier Q-ForestLab-Plots fuer die
Vergleichsseite (platform/web/gallery/qforest.html) in eine JSON zusammenfuehren.

  python scripts/qforest_compare.py   -> platform/web/gallery/qforest_compare.json
"""
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
X = REPO / "extdata" / "qforest"
PLOTS = [  # Reihenfolge = feste Farbzuordnung auf der Seite
    ("litchfield", "Litchfield", "Tropical savanna, Northern Territory (AUS)"),
    ("wytham", "Wytham Woods", "Temperate deciduous forest, England (UK)"),
    ("ofental", "Ofental", "Alpine coniferous forest, Berchtesgaden (DE)"),
    ("robsoncreek", "Robson Creek", "Tropical rainforest, Queensland (AUS)"),
]


def main():
    plots = []
    for pid, name, kind in PLOTS:
        k = json.loads((X / f"{pid}_test_kennwerte.json").read_text(encoding="utf-8"))
        prof = [float(r["PAI_proxy_m2m2"]) for r in csv.DictReader(open(X / f"{pid}_test_profil.csv"))]
        sun = k["licht"]["sonnengang"]
        plots.append({
            "id": pid, "name": name, "kind": kind, "scene": f"qforest-{pid}",
            "area_m2": k["flaeche_m2"], "H95_m": k["kronendach_H95_m"], "H99_m": k["kronendach_H99_m"],
            "PAI_proxy": k["PAI_proxy_gesamt"], "cover_2m": k["deckungsgrad_ueber_2m"],
            "ENL": k["ENL_inverse_Simpson"], "FHD": k["FHD_Shannon"],
            "light_vertical": k["licht"]["senkrecht_mittel"],
            "light_sun": {"equinox": sun["Tag-und-Nacht-Gleiche"]["mittel"],
                          "june_solstice": sun["Juni-Sonnenwende"]["mittel"],
                          "december_solstice": sun["Dezember-Sonnenwende"]["mittel"]},
            "latitude": k["breitengrad"],
            "strata": [{"name": s["schicht"], "from_m": s["von_m"], "to_m": s["bis_m"],
                        "PAI_proxy": s["PAI_proxy"], "cover": s["deckung_draufsicht"]}
                       for s in k["schichten"]],
            "profile": prof,
        })
    qsm = json.loads((X / "bra_qsm_vergleich.json").read_text(encoding="utf-8"))
    det = json.loads((X / "robsoncreek_test_bericht.json").read_text(encoding="utf-8"))
    out = {"plots": plots,
           "qsm_bra": {"ground": qsm["nur_bodenscan"], "ground_canopy": qsm["boden_plus_kronenscan"],
                       "gain_pct": qsm["zuwachs_durch_kronenscan_prozent"],
                       "points_canopy_only": qsm.get("punkte_nur_kronenscan_anteil")},
           "detection_robsoncreek": {"reference_trees": det["referenz"]["baeume_ab_10cm"],
                                     "methods": det["detektion"], "itcd": det.get("itcd")}}
    dst = REPO / "platform" / "web" / "gallery" / "qforest_compare.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {dst.relative_to(REPO)}")


if __name__ == "__main__":
    main()
