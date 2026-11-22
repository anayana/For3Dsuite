"""Kommandozeile:  bioscale demo | run projekt.yml | wizard | profiles | download | web"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bioscale", description="Punktdaten zur Biodiversitaet auf die Flaeche bringen - mit Leitplanken.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Synthetisches Beispiel (virtuelle Art) erzeugen und komplett rechnen")
    d.add_argument("ordner", nargs="?", default="bioscale_demo")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--artenzahl", action="store_true", help="zusaetzlich Artenzahl einer virtuellen Gemeinschaft rechnen")

    r = sub.add_parser("run", help="Projekt rechnen")
    r.add_argument("projekt")
    r.add_argument("--out", default=None)

    w = sub.add_parser("wizard", help="Projektdatei per Fragen erstellen")
    w.add_argument("datei", nargs="?", default="projekt.yml")

    sub.add_parser("profiles", help="Profile auflisten")

    dl = sub.add_parser("download", help="Offene Daten fuer ein Projekt vorab laden und als COG speichern")
    dl.add_argument("projekt")
    dl.add_argument("--out", default="einflussgroessen_offen")

    wb = sub.add_parser("web", help="Web-Assistent starten (Browser: http://127.0.0.1:8765)")
    wb.add_argument("--host", default="127.0.0.1")
    wb.add_argument("--port", type=int, default=8765)
    wb.add_argument("--arbeitsordner", default="bioscale_web")

    a = ap.parse_args(argv)
    if a.cmd == "demo":
        from .pipeline import run
        from .synthetic import write_demo_project
        proj = write_demo_project(a.ordner, seed=a.seed)
        print(f"Beispielprojekt geschrieben: {proj}")
        res = run(proj)
        print(f"\nFertig. Bericht oeffnen: {res['report']}")
        if a.artenzahl:
            res2 = run(proj.parent / "projekt_artenzahl.yml")
            print(f"Artenzahl-Bericht: {res2['report']}")
    elif a.cmd == "run":
        from .pipeline import run
        res = run(a.projekt, a.out)
        print(f"\nFertig. Bericht oeffnen: {res['report']}")
    elif a.cmd == "wizard":
        from .project import wizard
        wizard(a.datei)
    elif a.cmd == "profiles":
        from .profiles import list_profiles, load_profile
        for p in list_profiles():
            pr = load_profile(p)
            print(f"{p:24s} {pr['radius_m'][0]:>5}-{pr['radius_m'][1]:<5} m  {pr['label']}  [{pr['status']}]")
    elif a.cmd == "download":
        from .grid import Grid, write_raster
        from .occurrence import read_area
        from .pipeline import Log, build_covariates
        from .project import load_project
        cfg = load_project(a.projekt)
        base = Path(cfg["_base"])
        geom = read_area(base / cfg["area"], cfg["crs"])
        grid = Grid.from_bounds(geom.bounds, float(cfg["resolution_m"]), cfg["crs"])
        cfg["covariates"]["local"] = []
        st, _, warns = build_covariates(cfg, grid, base, Log())
        out = Path(a.out)
        for n, L in st.layers.items():
            write_raster(out / f"{n}.tif", L.array, grid)
        st.provenance.save(out / "herkunft.json")
        for w_ in warns:
            print("WARNUNG:", w_)
        print(f"{len(st.layers)} Layer in {out}")
    elif a.cmd == "web":
        import uvicorn
        from .web.app import create_app
        uvicorn.run(create_app(a.arbeitsordner), host=a.host, port=a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
