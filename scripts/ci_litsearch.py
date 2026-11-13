#!/usr/bin/env python3
"""ci_litsearch.py -- Literatur pruefen (fuer CI): je Suchanfrage die besten Treffer aus
OpenAlex mit Autoren, Jahr, Zeitschrift, Band, Seiten, DOI und Abstract (aus dem
invertierten Index rekonstruiert). Anfragen: .github/litsearch-request.txt (eine je Zeile).
Ausgabe: Paper_ODT/Forst_Benchmark_Paper/lit/litsearch.md"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "For3Dsuite-litsearch/1.0"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def abstract(inv):
    if not inv:
        return ""
    pos = {p: w for w, ps in inv.items() for p in ps}
    return " ".join(pos[i] for i in sorted(pos))


out = ["# Literaturpruefung (OpenAlex, automatisch)\n"]
for q in [l.strip() for l in open(".github/litsearch-request.txt") if l.strip() and not l.startswith("#")]:
    out.append(f"## Anfrage: {q}")
    if q.startswith("crossref:"):
        q2 = q[9:].strip()
        try:
            items = get("https://api.crossref.org/works?rows=3&query.bibliographic=" + urllib.parse.quote(q2))["message"]["items"]
        except Exception as e:
            out.append(f"Fehler: {e}\n"); continue
        for it in items:
            au = ", ".join(f"{a.get('given','')} {a.get('family','')}" for a in it.get("author", [])[:15])
            yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
            out.append(f"- **{(it.get('title') or [''])[0]}** — {au} ({yr}). *{(it.get('container-title') or [''])[0]}* "
                       f"{it.get('volume','')}({it.get('issue','')}) {it.get('page','') or it.get('article-number','')} — https://doi.org/{it.get('DOI','')}")
            ab = it.get("abstract", "")
            out.append(f"  - Abstract: {ab[:2500]}")
        out.append(""); continue
    try:
        res = get("https://api.openalex.org/works?per-page=2&search=" + urllib.parse.quote(q))["results"]
    except Exception as e:
        out.append(f"Fehler: {e}\n"); continue
    for w in res:
        au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:12])
        b = w.get("biblio") or {}
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        out.append(f"- **{w.get('title')}** — {au} ({w.get('publication_year')}). *{src}* "
                   f"{b.get('volume') or ''}({b.get('issue') or ''}) {b.get('first_page') or ''}–{b.get('last_page') or ''} — {w.get('doi')}")
        out.append(f"  - Abstract: {abstract(w.get('abstract_inverted_index'))[:2500]}")
    out.append("")
p = Path("Paper_ODT/Forst_Benchmark_Paper/lit/litsearch.md"); p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("\n".join(out) + "\n")
print(p, len(out))
