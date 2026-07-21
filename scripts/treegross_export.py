#!/usr/bin/env python3
"""treegross_export.py -- Baustein 5: Bestandesbeschreibung <-> Wachstumsdienst.

Bindeglied zwischen der Suite (scene.json / Inventur-CSV) und dem
TreeGrOSS/BWINPro-Wachstumsdienst (growth-service/). Zwei Richtungen:

  export  Inventur (scene.json oder CSV)  ->  Baumlisten-JSON fuer den Dienst
          Geometrie (Position/BHD/Hoehe) aus den Bausteinen 1-3, Baumart aus
          Baustein 4 bzw. --default-species, Bestandesmetadaten (Alter/Bonitaet/
          Flaeche) aus --stand-config oder CLI (Hauptluecke, extern beizubringen).

  import  Simulationsergebnis-JSON  ->  scene.json (Prognosejahr in die Marker)
          schreibt projizierte BHD/Hoehe eines Zieljahres zurueck -> der Nutzer
          begeht im 3D-Viewer den prognostizierten Zukunftsbestand.

JSON-Kontrakt (stabil, vom Java-Adapter auf die TreeGrOSS-Objekte gemappt):

  Anfrage (export):
    { "stand": { "id","area_ha","age_years","site_index","latitude","longitude" },
      "simulate": { "years": 20, "step_years": 5 },
      "trees": [ { "id","species","dbh_cm","height_m","x","y",
                   "crown_base_m"?, "age_years"?, "out_of_stand": false } ] }

  Antwort (import):
    { "stand": {...},
      "periods": [ { "year": <int>,
                     "trees": [ { "id","dbh_cm","height_m","alive","removed" } ] } ] }

Artcode-Mapping unten (SPECIES) entspricht den ueblichen BWINPro/TreeGrOSS-
Nummern und ist an die SpeciesDef der eingesetzten TreeGrOSS-Version anzupassen.

Ohne laufenden Wachstumsdienst laesst sich der ganze Weg offline demonstrieren:
'simulate' spiegelt exakt die StubGrowthEngine des Java-Dienstes (deterministisches
Demonstrator-Wachstum, KEIN wissenschaftliches Modell) -- fuer belastbare Prognosen
den echten growth-service (TreeGrOSS) ansprechen statt 'simulate'.

Nutzung:
  python treegross_export.py export --scene scene.json --out trees.json \
      --default-species "Picea abies" --stand-config renon_stand.json --years 20 --step 5
  python treegross_export.py simulate trees.json future.json --base-year 2024   # Offline-Demo
  python treegross_export.py import  --result future.json --scene scene.json \
      --year 2044 --out-scene scene_2044.json
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

# Demonstrator-Wachstum (identisch zur Java-StubGrowthEngine)
STUB_DBH_PER_YEAR = 0.35    # cm/Jahr (Default)
STUB_HEIGHT_PER_YEAR = 0.18  # m/Jahr (Default)
# Artdifferenzierte Demonstrator-Zuwaechse je TreeGrOSS-Artcode (BHD cm/Jahr,
# Hoehe m/Jahr). KEIN gefittetes Modell -- nur plausibel abgestufte Platzhalter,
# damit die Prognose artabhaengig variiert, bis die echte TreeGrOSS-Engine laeuft.
STUB_SPECIES_GROWTH = {
    110: (0.28, 0.18),  # Eiche
    211: (0.30, 0.20),  # Buche
    421: (0.35, 0.22),  # Birke
    511: (0.40, 0.25),  # Fichte
    517: (0.38, 0.24),  # Tanne
    611: (0.55, 0.35),  # Douglasie
    711: (0.30, 0.18),  # Kiefer
    811: (0.45, 0.28),  # Laerche
}

# Klarname/Synonym -> BWINPro/TreeGrOSS-Artnummer (an SpeciesDef anpassen!)
SPECIES = {
    "eiche": 110, "quercus": 110,
    "buche": 211, "fagus": 211, "fagus sylvatica": 211,
    "fichte": 511, "picea": 511, "picea abies": 511,
    "douglasie": 611, "pseudotsuga": 611,
    "kiefer": 711, "pinus": 711, "pinus sylvestris": 711,
    "laerche": 811, "larix": 811,
    "tanne": 517, "abies": 517, "abies alba": 517,
    "birke": 421, "betula": 421,
}


def species_code(name, default_code):
    if name is None:
        return default_code
    key = str(name).strip().lower()
    if key.isdigit():
        return int(key)
    return SPECIES.get(key, default_code)


def as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_stand(args):
    stand = {"id": args.stand_id, "area_ha": args.area_ha, "age_years": args.age,
             "site_index": args.site_index, "latitude": args.lat, "longitude": args.lon}
    if args.stand_config:
        stand.update(json.loads(Path(args.stand_config).read_text(encoding="utf-8")))
    stand = {k: v for k, v in stand.items() if v is not None}
    if "age_years" not in stand or "site_index" not in stand:
        print("WARNUNG: Alter und/oder Bonitaet (site_index) fehlen -- extern "
              "beibringen (Hauptluecke laut Baustein 5).", file=sys.stderr)
    return stand


def trees_from_scene(scene, default_code, origin):
    trees, skipped = [], 0
    for mk in scene.get("markers", []):
        a = mk.get("attributes", {})
        dbh, h = as_float(a.get("BHD_cm")), as_float(a.get("Hoehe_m"))
        if dbh is None or h is None:
            skipped += 1
            continue
        xyz = mk.get("xyz") or [None, None, None]
        x = round(xyz[0] - origin[0], 3) if xyz[0] is not None else None
        y = round(xyz[1] - origin[1], 3) if xyz[1] is not None else None
        t = {"id": mk["id"],
             "species": species_code(a.get("Art") or a.get("Baumart") or a.get("species"), default_code),
             "dbh_cm": round(dbh, 1), "height_m": round(h, 1)}
        if x is not None:
            t["x"], t["y"] = x, y
        if as_float(a.get("Kronenansatz_m")) is not None:
            t["crown_base_m"] = as_float(a["Kronenansatz_m"])
        if as_float(a.get("Alter")) is not None:
            t["age_years"] = as_float(a["Alter"])
        t["out_of_stand"] = False
        trees.append(t)
    return trees, skipped


def trees_from_csv(rows, default_code):
    trees, skipped = [], 0
    for i, r in enumerate(rows, 1):
        dbh = as_float(r.get("BHD_cm") or r.get("dbh_cm"))
        h = as_float(r.get("Hoehe_m") or r.get("height_m"))
        if dbh is None or h is None:
            skipped += 1
            continue
        t = {"id": r.get("label") or r.get("id") or f"t{i:03d}",
             "species": species_code(r.get("Art") or r.get("Baumart") or r.get("species"),
                                     default_code),
             "dbh_cm": round(dbh, 1), "height_m": round(h, 1), "out_of_stand": False}
        for src, dst in (("x", "x"), ("y", "y")):
            v = as_float(r.get(src))
            if v is not None:
                t[dst] = round(v, 3)
        trees.append(t)
    return trees, skipped


def trees_from_stand(data, default_code):
    """Stand-Inventur (stand_inventory.py / species_renon.py-Ausgabe): trees[] mit
    BHD_cm, Hoehe_m, world-Koordinate und erkannter Baumart je Baum.

    Dies ist der Weg fuer ARTSPEZIFISCHE Prognosen, weil hier BHD, Hoehe und
    Baumart aus derselben Quelle stammen.

    ACHTUNG -- nicht stattdessen die Arten in die Szenen-Marker mergen:
    Stand-Inventur und Szenen-Marker sind zwei unabhaengige Detektionslaeufe,
    die beide nach BHD absteigend durchnummerieren. Gleiche IDs meinen also
    NICHT denselben Baum (am Renon-Setup: Median-Lagedifferenz 14 m). Ein Merge
    ueber die ID verteilt die Arten still auf die falschen Staemme; nur ein
    Positions-Matching mit enger Toleranz waere zulaessig.
    """
    trees, skipped = [], 0
    for i, r in enumerate(data.get("trees", []), 1):
        dbh, h = as_float(r.get("BHD_cm")), as_float(r.get("Hoehe_m"))
        if dbh is None or h is None:
            skipped += 1
            continue
        t = {"id": r.get("id") or f"t{i:03d}",
             "species": species_code(r.get("Baumart") or r.get("Art") or r.get("species"),
                                     default_code),
             "dbh_cm": round(dbh, 1), "height_m": round(h, 1), "out_of_stand": False}
        w = r.get("world") or []
        if len(w) >= 2 and w[0] is not None:
            t["x"], t["y"] = round(w[0], 3), round(w[1], 3)
        conf = as_float(r.get("Baumart_konfidenz"))
        if conf is not None:
            t["species_confidence"] = conf
        trees.append(t)
    return trees, skipped


def do_export(args):
    default_code = species_code(args.default_species, 511)
    if args.scene:
        scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
        origin = (scene.get("source") or {}).get("origin_xyz") or [0, 0, 0]
        trees, skipped = trees_from_scene(scene, default_code, origin)
    elif args.from_stand:
        data = json.loads(Path(args.from_stand).read_text(encoding="utf-8"))
        trees, skipped = trees_from_stand(data, default_code)
    else:
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            trees, skipped = trees_from_csv(list(csv.DictReader(f)), default_code)
    if not trees:
        sys.exit("Keine Baeume mit BHD und Hoehe gefunden")

    payload = {"stand": load_stand(args), "trees": trees}
    if args.years:
        payload["simulate"] = {"years": args.years, "step_years": args.step}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    codes = sorted({t["species"] for t in trees})
    print(f"-> {args.out}: {len(trees)} Baeume (Artcodes {codes}), "
          f"{skipped} ohne BHD/Hoehe uebersprungen")
    if args.years:
        print(f"   Simulationsauftrag: {args.years} Jahre in {args.step}-Jahres-Schritten")


def do_simulate(args):
    """Offline-Demonstrator: spiegelt die Java-StubGrowthEngine (kein Fachmodell)."""
    req = json.loads(Path(args.request).read_text(encoding="utf-8"))
    spec = req.get("simulate") or {}
    years = args.years or spec.get("years") or 20
    step = args.step or spec.get("step_years") or 5
    base = args.base_year or date.today().year

    periods = []
    for s in range(0, years + 1, step):
        trees = []
        for t in req.get("trees", []):
            dbh0 = t.get("dbh_cm") or 0.0
            h0 = t.get("height_m") or 0.0
            rd, rh = STUB_SPECIES_GROWTH.get(
                t.get("species"), (STUB_DBH_PER_YEAR, STUB_HEIGHT_PER_YEAR))
            alive = not (dbh0 < 10 and s >= 15)   # kleine Baeume scheiden spaet aus
            trees.append({"id": t["id"],
                          "dbh_cm": round(dbh0 + rd * s, 1),
                          "height_m": round(h0 + rh * s, 1),
                          "alive": alive, "removed": not alive})
        periods.append({"year": base + s, "trees": trees})
    Path(args.out).write_text(
        json.dumps({"stand": req.get("stand"), "periods": periods},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    n_out = sum(1 for t in periods[-1]["trees"] if t["removed"])
    print(f"-> {args.out}: {len(periods)} Perioden {periods[0]['year']}..{periods[-1]['year']}, "
          f"{len(periods[-1]['trees'])} Baeume, {n_out} ausgeschieden (Demonstrator-Wachstum)")


def pick_period(result, year):
    periods = result.get("periods") or []
    if not periods:
        sys.exit("Ergebnis-JSON enthaelt keine 'periods'")
    if year is None:
        return periods[-1]
    exact = [p for p in periods if p.get("year") == year]
    if exact:
        return exact[0]
    return min(periods, key=lambda p: abs(p.get("year", 0) - year))


def do_import(args):
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    period = pick_period(result, args.year)
    proj = {t["id"]: t for t in period.get("trees", [])}
    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))

    updated, removed = 0, 0
    kept_markers = []
    for mk in scene.get("markers", []):
        t = proj.get(mk["id"])
        if t is None:
            kept_markers.append(mk)
            continue
        gone = bool(t.get("removed") or t.get("alive") is False)
        if gone:
            removed += 1
            if args.drop_removed and not args.attach_key:
                continue
        if args.attach_key:
            # Prognose separat ablegen -- Heute-Werte in attributes bleiben erhalten
            block = {"Prognosejahr": period.get("year")}
            if as_float(t.get("dbh_cm")) is not None:
                block["BHD_cm"] = round(float(t["dbh_cm"]), 1)
            if as_float(t.get("height_m")) is not None:
                block["Hoehe_m"] = round(float(t["height_m"]), 1)
            block["Status"] = "ausgeschieden" if gone else "stehend"
            mk[args.attach_key] = block
        else:
            a = mk.setdefault("attributes", {})
            if gone:
                a["Status"] = "ausgeschieden"
            if as_float(t.get("dbh_cm")) is not None:
                a["BHD_cm"] = round(float(t["dbh_cm"]), 1)
            if as_float(t.get("height_m")) is not None:
                a["Hoehe_m"] = round(float(t["height_m"]), 1)
            a["Prognosejahr"] = period.get("year")
        updated += 1
        kept_markers.append(mk)
    scene["markers"] = kept_markers

    if args.title_suffix:
        scene["title"] = f"{scene.get('title', scene.get('id',''))} {args.title_suffix}"
    out = args.out_scene or args.scene
    Path(out).write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prognosejahr {period.get('year')}: {updated} Baeume aktualisiert, "
          f"{removed} ausgeschieden{' (entfernt)' if args.drop_removed else ''}")
    print(f"-> {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("export", help="Inventur -> Baumlisten-JSON")
    src = ex.add_mutually_exclusive_group(required=True)
    src.add_argument("--scene", help="scene.json als Quelle")
    src.add_argument("--csv", help="Inventur-CSV (BHD_cm,Hoehe_m[,Art,x,y,label])")
    src.add_argument("--from-stand", help="Stand-Inventur-JSON (stand_inventory/"
                     "species_renon) mit trees[].Baumart je Baum")
    ex.add_argument("--out", required=True)
    ex.add_argument("--default-species", default="Picea abies",
                    help="Art, wenn nicht je Baum bekannt (Name oder Code)")
    ex.add_argument("--stand-config", help="JSON mit Bestandesmetadaten (ueberschreibt CLI)")
    ex.add_argument("--stand-id", default="stand01")
    ex.add_argument("--area-ha", type=float)
    ex.add_argument("--age", type=int, help="Bestandesalter in Jahren")
    ex.add_argument("--site-index", type=float, help="Bonitaet (site index)")
    ex.add_argument("--lat", type=float)
    ex.add_argument("--lon", type=float)
    ex.add_argument("--years", type=int, help="Simulationszeitraum -> 'simulate'-Block")
    ex.add_argument("--step", type=int, default=5, help="Schrittweite Jahre")
    ex.set_defaults(func=do_export)

    si = sub.add_parser("simulate", help="Offline-Demonstrator (spiegelt Java-Stub)")
    si.add_argument("request", help="Baumlisten-JSON aus 'export'")
    si.add_argument("out", help="Ergebnis-JSON (wie growth-service /simulate)")
    si.add_argument("--base-year", type=int, help="Startjahr (Default: aktuelles Jahr)")
    si.add_argument("--years", type=int, help="ueberschreibt simulate.years")
    si.add_argument("--step", type=int, help="ueberschreibt simulate.step_years")
    si.set_defaults(func=do_simulate)

    im = sub.add_parser("import", help="Simulationsergebnis -> scene.json")
    im.add_argument("--result", required=True, help="Antwort-JSON des Dienstes")
    im.add_argument("--scene", required=True, help="scene.json (Positionen/Marker)")
    im.add_argument("--year", type=int, help="Zieljahr (Default: letzte Periode)")
    im.add_argument("--out-scene", help="Ziel-scene.json (Default: --scene ueberschreiben)")
    im.add_argument("--title-suffix", help="an den Szenentitel anhaengen, z. B. '(2044)'")
    im.add_argument("--attach-key", help="Prognose unter marker[KEY] ablegen statt "
                    "die Heute-Attribute zu ueberschreiben (z. B. 'prognosis')")
    im.add_argument("--drop-removed", action="store_true",
                    help="ausgeschiedene Baeume aus den Markern entfernen")
    im.set_defaults(func=do_import)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
