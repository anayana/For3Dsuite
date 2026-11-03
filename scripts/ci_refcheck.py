#!/usr/bin/env python3
"""ci_refcheck.py -- Literaturangaben gegen Crossref (und Zenodo) pruefen (fuer CI).
Schreibt Paper_ODT/Forst_Benchmark_Paper/lit/refs_check.md."""
import json
import urllib.parse
import urllib.request

UA = {"User-Agent": "For3Dsuite-refcheck/1.0 (mailto:angel.naya@posteo.de)"}
QUERIES = {
    "3DFin": "3DFin software automated 3D forest inventories terrestrial point clouds Laino Cabo",
    "HELIOS++": "Virtual laser scanning with HELIOS++ novel take on ray tracing-based simulation Winiwarter",
    "Li scan design": "iterative-mode scan design of terrestrial laser scanning in forests for minimizing occlusion effects",
    "LAUT Gollob": "Comparison of 3D point clouds obtained by terrestrial laser scanning and personal laser scanning on forest inventory sample plots",
    "Weiser 2022": "Individual tree point clouds and tree measurements from multi-platform laser scanning in German forests Weiser",
    "SegmentedForests": "SegmentedForests semantic segmentation forest point clouds Laino",
    "Abegg 2017": "Terrestrial laser scanning for forest inventories tree diameter distribution and scanner location impact on occlusion",
    "Liang 2018": "International benchmarking of terrestrial laser scanning approaches for forest inventories",
    "FORTLS": "FORTLS R package processing TLS data estimating stand variables forest inventories",
    "Kasa 1976": "A circle fitting procedure and its error analysis Kasa",
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


out = ["# Literaturpruefung (Crossref, automatisch)\n"]
for key, q in QUERIES.items():
    try:
        items = get("https://api.crossref.org/works?rows=3&query.bibliographic=" + urllib.parse.quote(q))["message"]["items"]
    except Exception as e:
        out.append(f"## {key}\nFehler: {e}\n"); continue
    out.append(f"## {key}")
    for it in items:
        au = "; ".join(f"{a.get('family','')}, {a.get('given','')}" for a in it.get("author", [])[:12])
        yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        out.append(f"- **{(it.get('title') or [''])[0]}** — {au} ({yr}). *{(it.get('container-title') or [''])[0]}* "
                   f"{it.get('volume','')}({it.get('issue','')}) {it.get('page','')} — doi:{it.get('DOI','')}")
    out.append("")
for rec in ("17186174", "17396681", "3698956"):
    try:
        m = get(f"https://zenodo.org/api/records/{rec}")["metadata"]
        au = "; ".join(c.get("name", "") for c in m.get("creators", []))
        out.append(f"## Zenodo {rec}\n- {au} ({m.get('publication_date','')}). {m.get('title','')}. Zenodo. "
                   f"doi:{m.get('doi','')} — Lizenz: {m.get('license',{}).get('id','')}\n")
    except Exception as e:
        out.append(f"## Zenodo {rec}\nFehler: {e}\n")
open("Paper_ODT/Forst_Benchmark_Paper/lit/refs_check.md", "w").write("\n".join(out))
print("\n".join(out))
