#!/usr/bin/env python3
"""ci_refcheck_paperB.py -- Literatur von Paper B gegen Crossref pruefen und die Zenodo-Beschreibung des
Pellis-Datensatzes (Klassen-Nummern) holen (fuer CI; aus der Cloud-Sitzung gesperrt).
Schreibt Paper_ODT/Heritage_Toolkit_Paper/lit/refs_check.md."""
import html
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "For3Dsuite-refcheck/1.0 (mailto:angel.naya@posteo.de)"}
QUERIES = {
    "Barron 2022": "Mip-NeRF 360 unbounded anti-aliased neural radiance fields Barron",
    "Guedon 2024": "SuGaR surface-aligned Gaussian splatting efficient 3D mesh reconstruction Guedon Lepetit",
    "Huang 2024": "2D Gaussian splatting for geometrically accurate radiance fields Huang",
    "Kerbl 2023": "3D Gaussian splatting for real-time radiance field rendering Kerbl",
    "Martin-Brualla 2021": "NeRF in the wild neural radiance fields for unconstrained photo collections",
    "Matrone 2020": "A benchmark for large-scale heritage point cloud semantic segmentation Matrone",
    "Mildenhall 2020": "NeRF representing scenes as neural radiance fields for view synthesis Mildenhall",
    "Pellis 2021": "Assembling an image and point cloud dataset for heritage building semantic segmentation Pellis",
    "Pellis 2025": "A photogrammetric image-point dataset for the semantic segmentation of heritage buildings",
    "Remondino 2011": "Heritage recording and 3D modeling with photogrammetry and 3D scanning Remondino",
    "Remondino 2023": "A critical analysis of NeRF-based 3D reconstruction Remondino",
    "Schoenberger 2016": "Structure-from-motion revisited Schonberger Frahm",
    "Umeyama 1991": "Least-squares estimation of transformation parameters between two point patterns Umeyama",
    "Virtanen 2020": "SciPy 1.0 fundamental algorithms for scientific computing in Python",
    "Wang 2004": "Image quality assessment from error visibility to structural similarity",
    "Ye 2025": "gsplat an open-source library for Gaussian splatting",
    "Zhang 2018": "The unreasonable effectiveness of deep features as a perceptual metric",
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


out = ["# Literaturpruefung Paper B (Crossref, automatisch)\n"]
for key, q in QUERIES.items():
    try:
        items = get("https://api.crossref.org/works?rows=3&query.bibliographic=" + urllib.parse.quote(q))["message"]["items"]
    except Exception as e:
        out.append(f"## {key}\nFehler: {e}\n")
        continue
    out.append(f"## {key}")
    for it in items:
        au = "; ".join(f"{a.get('family','')}, {a.get('given','')}" for a in it.get("author", [])[:12])
        yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        out.append(f"- **{(it.get('title') or [''])[0]}** — {au} ({yr}). *{(it.get('container-title') or [''])[0]}* "
                   f"{it.get('volume','')}({it.get('issue','')}) {it.get('page','')} — doi:{it.get('DOI','')}")
    out.append("")
try:
    m = get("https://zenodo.org/api/records/14626611")["metadata"]
    au = "; ".join(c.get("name", "") for c in m.get("creators", []))
    desc = html.unescape(re.sub(r"<[^>]+>", "\n", m.get("description", "")))
    desc = "\n".join(l.strip() for l in desc.splitlines() if l.strip())
    out.append(f"## Zenodo 14626611 (Pellis-Datensatz)\n- {au} ({m.get('publication_date','')}). {m.get('title','')}. "
               f"doi:{m.get('doi','')} — Lizenz: {m.get('license',{}).get('id','')}\n\n### Beschreibung\n\n{desc}\n")
except Exception as e:
    out.append(f"## Zenodo 14626611\nFehler: {e}\n")
import os
os.makedirs("Paper_ODT/Heritage_Toolkit_Paper/lit", exist_ok=True)
open("Paper_ODT/Heritage_Toolkit_Paper/lit/refs_check.md", "w").write("\n".join(out))
print("\n".join(out))
