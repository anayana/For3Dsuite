#!/usr/bin/env python3
"""tree_age_from_height.py -- Alter je Baum aus der Hoehe, mit TreeGrOSS' eigener Kurve.

Behebt einen Fehler, der die ganze Prognose entwertet hat: ohne Alter je Baum faellt
der Wachstumsdienst auf das BESTANDESALTER zurueck und rechnet jeden Stamm als
200 Jahre alt -- auch den 8-cm-Stamm im Unterstand. Ein 200-jaehriger Baum waechst
im Modell praktisch nicht mehr; deshalb stand die Prognose auf der Stelle.

Renon ist laut Standortbeschreibung ausdruecklich ein UNGLEICHALTRIGER,
mehrschichtiger Fichtenbestand -- "~200 Jahre" gilt fuer die OBERSCHICHT, nicht
fuer den Bestand.

Verfahren -- kein erfundenes Modell, sondern die Umkehrung der Bonitaetsfunktion,
die in der eingesetzten TreeGrOSS-Parameterdatei steht (Fichte: NAGEL 1999):

    SI = (h100 + A - B*ln(t) - C*ln(t)^2) / (D + E*ln(t))

  1. Oberhoehe h100 des Bestandes = mittlere Hoehe der 100 dicksten Baeume je ha
  2. SI aus h100 beim dokumentierten Alter der Oberschicht (--top-age)
  3. je Baum die Gleichung nach t aufloesen -> Alter aus der eigenen Hoehe

Damit ist genau EINE Annahme im Spiel (das Alter der Oberschicht, extern belegt),
und alles andere folgt aus gemessenen Hoehen und der Modellkurve selbst.

GRENZE, die bleibt: die Fichten-Bonitaetsfunktion ist fuer NORDWESTDEUTSCHLAND
kalibriert. Renon liegt auf ~1730 m in den Alpen; die Kurve wird hier ausserhalb
ihres Kalibrierbereichs benutzt. Die abgeleitete Bonitaet faellt entsprechend sehr
niedrig aus -- das ist fuer einen subalpinen Standort plausibel, aber es ist eine
Extrapolation und keine Ertragstafel fuer diesen Standort.

  python scripts/tree_age_from_height.py <scene.json> --top-age 200
"""
import argparse
import json
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL = (REPO / "growth-service" / "lib" / "src" / "treegross" / "model"
         / "ForestSimulatorNWGermany6.xml")

# Form, die dieses Skript aufloesen kann:
#   (sp.h100 + A - B*ln(t.age) - C*((ln(t.age))^2.0)) / (D + E*ln(t.age))
SHAPE = re.compile(
    r"\(\s*sp\.h100\s*([+-][\d.]+)\s*([+-][\d.]+)\*ln\(t\.age\)\s*"
    r"([+-][\d.]+)\*\(\(ln\(t\.age\)\)\^2\.0\)\s*\)\s*/\s*"
    r"\(\s*([+-]?[\d.]+)\s*([+-][\d.]+)\*ln\(t\.age\)\s*\)")


def site_index_coeffs(species_code, model=MODEL):
    """(A, B, C, D, E) der Bonitaetsfunktion einer Art aus der Modell-XML."""
    txt = model.read_text(encoding="utf-8", errors="replace")
    pos = txt.find(f"<Code>{species_code}</Code>")
    if pos < 0:
        raise SystemExit(f"Artcode {species_code} nicht in {model.name}")
    seg = txt[pos:pos + 8000]
    m = re.search(r"<SiteIndex>(.*?)</SiteIndex>", seg, re.S)
    if not m:
        raise SystemExit(f"Keine SiteIndex-Funktion fuer Artcode {species_code}")
    formula = m.group(1)
    s = SHAPE.search(formula.replace(" ", ""))
    if not s:
        raise SystemExit(
            f"Die Bonitaetsfunktion der Art {species_code} hat eine andere Form als "
            f"dieses Skript aufloesen kann:\n  {formula.strip()}\n"
            "Nicht raten -- Umkehrung fuer diese Form ergaenzen.")
    a, b, c, d, e = (float(x) for x in s.groups())
    return a, b, c, d, e, formula.strip()


def si_from_height(h100, age, k):
    a, b, c, d, e = k[:5]
    L = math.log(age)
    return (h100 + a + b * L + c * L * L) / (d + e * L)


def age_from_height(h, si, k, lo=5.0, hi=400.0):
    """Umkehrung: quadratisch in ln(t), also geschlossen loesbar."""
    a, b, c, d, e = k[:5]
    # SI = (h + a + b*L + c*L^2) / (d + e*L)   nach h aufgeloest:
    #   h = SI*(d + e*L) - a - b*L - c*L^2
    # und nach L sortiert (ALLE Terme negiert, nicht nur zwei -- genau das ging
    # hier zuerst schief und lieferte fuer jeden Baum "kein Alter"):
    #   c*L^2 + (b - SI*e)*L + (a + h - SI*d) = 0
    A, B, C = c, b - si * e, a + h - si * d
    if abs(A) < 1e-12:
        if abs(B) < 1e-12:
            return None
        roots = [-C / B]
    else:
        disc = B * B - 4 * A * C
        if disc < 0:
            return None
        s = math.sqrt(disc)
        roots = [(-B + s) / (2 * A), (-B - s) / (2 * A)]
    # Der Ast c<0 macht die Parabel nach unten offen: eine der beiden Wurzeln
    # liegt auf dem fallenden Ast und ist forstlich sinnlos. Es gilt die
    # kleinste Wurzel im plausiblen Altersbereich (monoton steigende Hoehe).
    ages = sorted(math.exp(L) for L in roots if -20 < L < 20)
    for t in ages:
        if lo <= t <= hi:
            return t
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scene")
    ap.add_argument("--species", type=int, default=511, help="TreeGrOSS-Artcode")
    ap.add_argument("--top-age", type=float, default=200.0,
                    help="dokumentiertes Alter der Oberschicht [Jahre]")
    ap.add_argument("--site-index", type=float,
                    help="Bonitaet (h100 im Alter 100) direkt vorgeben, statt sie "
                         "aus --top-age herzuleiten. Fuer Flaechen ohne dokumentiertes "
                         "Bestandesalter: die Standortguete ist regional belegbar, "
                         "das Alter waere geraten. Beides sind Annahmen -- welche "
                         "gilt, steht danach in scene.stand.age_source.")
    ap.add_argument("--area-ha", type=float, required=True,
                    help="Bezugsflaeche fuer die Oberhoehe (100 dickste je ha)")
    ap.add_argument("--out-stand", help="Bestandes-JSON fuer treegross_export --stand-config")
    args = ap.parse_args()

    k = site_index_coeffs(args.species)
    print(f"Bonitaetsfunktion Art {args.species}: {k[5]}")

    spath = Path(args.scene)
    scene = json.loads(spath.read_text(encoding="utf-8"))
    markers = scene.get("markers") or []
    trees = [m for m in markers
             if m["attributes"].get("Hoehe_m") and m["attributes"].get("BHD_cm")]
    if not trees:
        raise SystemExit("Keine Marker mit Hoehe und BHD")

    # Oberhoehe: die 100 dicksten je Hektar -- aber NUR aus sauber gemessenen
    # Staemmen. Die als 'unsicher' gekennzeichneten sind ueberwiegend zwei
    # verschmolzene Nachbarstaemme; sie erscheinen mit 100-137 cm ganz oben in
    # der Dickenliste und haben zugleich nur 2-3 m eigene Kronenhoehe. Nimmt man
    # sie mit, faellt die Oberhoehe von 23 auf 11 m und die ganze Bonitaet mit ihr.
    clean = [m for m in trees
             if m["attributes"].get("BHD_Guete") in (None, "gut")] or trees
    n_top = max(1, round(100 * args.area_ha))
    top = sorted(clean, key=lambda m: -m["attributes"]["BHD_cm"])[:n_top]
    h100 = sum(m["attributes"]["Hoehe_m"] for m in top) / len(top)
    print(f"Oberhoehe aus {len(clean)} von {len(trees)} Baeumen mit sauberer "
          f"BHD-Messung (Guete 'gut')")
    print(f"Oberhoehe h100 = {h100:.1f} m (aus den {n_top} dicksten Baeumen auf "
          f"{args.area_ha:.4f} ha)")
    if args.site_index is not None:
        si = args.site_index
        top_age = age_from_height(h100, si, k)
        print(f"Bonitaet SI = {si:.1f} m  (VORGEGEBEN) -> Oberschicht rechnerisch "
              f"{top_age:.0f} Jahre")
    else:
        si = si_from_height(h100, args.top_age, k)
        top_age = args.top_age
        print(f"Bonitaet SI = {si:.1f} m  (h100 im Alter 100, hergeleitet aus "
              f"Oberschicht-Alter {args.top_age:.0f})")

    ages = []
    for m in markers:
        h = m["attributes"].get("Hoehe_m")
        if not h:
            continue
        t = age_from_height(float(h), si, k)
        if t is None:
            continue
        m["attributes"]["Alter"] = int(round(t))
        ages.append(t)
    ages.sort()
    print(f"{len(ages)} Baeume mit Alter: min {ages[0]:.0f}, Median "
          f"{ages[len(ages)//2]:.0f}, max {ages[-1]:.0f} Jahre")

    scene.setdefault("stand", {})
    scene["stand"].update({
        "h100_m": round(h100, 1), "site_index": round(si, 1),
        "top_age_years": round(top_age, 0) if top_age else None,
        "area_ha": args.area_ha,
        "species_code": args.species,
        "site_index_source": ("vorgegeben" if args.site_index is not None
                              else "aus dokumentiertem Oberschicht-Alter hergeleitet"),
        "age_source": ("Alter je Baum aus der Hoehe ueber die Bonitaetsfunktion der "
                       "eingesetzten TreeGrOSS-Parameterdatei (Fichte, NAGEL 1999), "
                       f"verankert am dokumentierten Oberschicht-Alter von "
                       f"{args.top_age:.0f} Jahren. Die Funktion ist fuer "
                       "Nordwestdeutschland kalibriert und wird hier auf einen "
                       "subalpinen Standort (~1730 m) extrapoliert."),
    })
    spath.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {spath}")

    if args.out_stand:
        Path(args.out_stand).write_text(json.dumps({
            "id": scene.get("id", "stand"), "area_ha": args.area_ha,
            "age_years": int(round(args.top_age)), "site_index": round(si, 1),
            "latitude": (scene.get("source") or {}).get("gps", {}).get("lat"),
            "longitude": (scene.get("source") or {}).get("gps", {}).get("lon"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"-> {args.out_stand}")


if __name__ == "__main__":
    main()
