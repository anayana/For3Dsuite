#!/usr/bin/env python3
"""paperC_isprs.py -- Einreichfassung von Paper C fuer das ISPRS Journal of Photogrammetry and
Remote Sensing (Elsevier, hybrid). Titelseite, Highlights (eigene Datei), Abstract, Keywords,
nummerierte Abschnitte, Abbildungen und Tabellen im Text nach der ersten Erwaehnung, Erklaerungen
(CRediT, Interessenkonflikte, generative KI, Datenverfuegbarkeit, Finanzierung), Literatur.

  python scripts/paperC_isprs.py   -> Paper_ODT/Forst_Benchmark_Paper/ISPRS/
"""
import re
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "Paper_ODT" / "Forst_Benchmark_Paper"
OUT = P / "ISPRS"
HIGHLIGHTS = [
    "Visible stem arc, not point density, controls DBH error from laser scans",
    "Least-squares fits need about 200-225° of visible arc on clean stem points",
    "Branch points ruin least-squares fits at any coverage; RANSAC stays robust",
    "3DFin sector rule keeps accuracy but leaves about half the stems without DBH",
    "Spread scan positions add more coverage than additional clustered positions",
]
KEYWORDS = ["Terrestrial laser scanning", "Diameter at breast height", "Occlusion", "Circle fitting",
            "Virtual laser scanning", "Scan design"]
AI = ("During the preparation of this work the author used Claude (Anthropic) to assist with programming, "
      "data analysis and drafting of the text. After using this tool, the author reviewed and edited the "
      "content as needed and takes full responsibility for the content of the publication.")


def section(s, name):
    i = s.index(f"## {name}")
    j = s.find("\n## ", i + 3)
    return s[i:j if j > 0 else len(s)].split("\n", 1)[1].strip()


def main():
    s = (P / "Manuscript_EN.md").read_text()
    title = s.splitlines()[0].lstrip("% ").strip()
    abstract = section(s, "Abstract").split("**Keywords")[0].strip()
    body = s[s.index("## 1. Introduction"):s.index("## Code availability")]
    figs = {int(n): f"![{c}]({f}){{width=16cm}}" for c, n, f in
            re.findall(r"!\[(\*\*Figure (\d)\.\*\*.*?)\]\((figures/[^)]+)\)", section(s, "Figures"), re.S)}
    tabs = {int(n): b.strip() for n, b in
            re.findall(r"\*\*Table (\d)\.\*\*(.*?)(?=\n\*\*Table \d\.\*\*|\Z)", section(s, "Tables"), re.S)}
    tabs = {n: f"**Table {n}.** " + b for n, b in tabs.items()}
    paras, out, done = body.split("\n\n"), [], set()
    for para in paras:
        out.append(para)
        for key, items, pat in (("F", figs, r"Figs?\. {n}(?![0-9])"), ("T", tabs, r"Table {n}(?![0-9])")):
            for n in sorted(items):
                if (key, n) not in done and re.search(pat.format(n=n), para):
                    out.append(items[n]); done.add((key, n))
    assert len(done) == len(figs) + len(tabs), done
    body = "\n\n".join(out)
    data = (section(s, "Data availability") + " " + section(s, "Code availability")).replace("\n", " ")
    md = f"""---
title: "{title}"
---

Angel Naya^a^

^a^ Independent Researcher, Berlin, Germany

Corresponding author: Angel Naya, angel.naya@posteo.de

## Abstract

{abstract}

**Keywords:** {"; ".join(KEYWORDS)}

{body.strip()}

## CRediT authorship contribution statement

**Angel Naya:** Conceptualization, Methodology, Software, Formal analysis, Investigation, Data curation, Visualization, Writing – original draft, Writing – review & editing.

## Declaration of competing interest

The author declares no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Declaration of generative AI and AI-assisted technologies in the writing process

{AI}

## Data availability

{data}

## Funding

{section(s, "Funding")}

## Acknowledgements

{section(s, "Acknowledgements")}

## References

{section(s, "References")}
"""
    OUT.mkdir(exist_ok=True)
    (OUT / "Manuscript_ISPRS.md").write_text(md)
    (OUT / "Highlights_ISPRS.md").write_text("# Highlights\n\n" + "\n".join(f"- {h}" for h in HIGHLIGHTS) + "\n")
    for f in ("Manuscript_ISPRS", "Highlights_ISPRS"):
        subprocess.run(["pandoc", f"ISPRS/{f}.md", "--resource-path=.", "-o", f"ISPRS/{f}.docx"], cwd=P, check=True)
    print("->", OUT)


if __name__ == "__main__":
    main()
