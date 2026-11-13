#!/usr/bin/env python3
"""paperC_ejfr.py -- Einreichfassung von Paper C fuer das European Journal of Forest Research.

Vorgaben (Springer, 'For Authors and Editors', EJFR): Abstract 150-250 Woerter, hoechstens fuenf
Keywords, Abschnitte Introduction, Materials and methods, Results, Discussion, Conclusions;
Acknowledgements nach dem Text und vor den References; nach den References Bildunterschriften,
dann Abbildungen. Literatur alphabetisch, DOIs als Link; Zitate Name Jahr ohne Komma.

  python scripts/paperC_ejfr.py   -> Paper_ODT/Forst_Benchmark_Paper/EJFR/Manuscript_EJFR.{md,docx}
"""
import re
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "Paper_ODT" / "Forst_Benchmark_Paper"
OUT = P / "EJFR"


def section(s, name):
    i = s.index(f"## {name}")
    j = s.find("\n## ", i + 3)
    return s[i:j if j > 0 else len(s)].split("\n", 1)[1].strip()


def cite_style(t):
    # (Laino et al., 2024) -> (Laino et al. 2024); Kåsa, 1976 -> Kåsa 1976
    return re.sub(r"((?:et al\.)|(?:[A-ZÅÄÖÜ][\wÀ-ÿ'\-]+)),\s+(\d{4}[a-c]?\b)", r"\1 \2", t)


def ref_springer(e):
    """'- Abegg, M., Kükenbrink, D., ..., 2017. Title. Journal 8(6), 184. https://doi...'
    -> 'Abegg M, Kükenbrink D, ... (2017) Title. Journal 8(6):184. https://doi...'"""
    e = " ".join(e[2:].split())
    m = re.match(r"(.+?),\s+(\d{4}[a-c]?)\.\s+(.*)$", e)
    authors, year, rest = m.groups()
    parts = [a.strip() for a in re.split(r",\s*(?=[A-ZÅÄÖÜÉ][\wÀ-ÿ'\- ]+,\s*[A-Z])|,\s*(?=et al\.)|,\s*(?=the )", authors)]
    out = []
    for a in parts:
        if a.startswith("et al") or a.startswith("the "):
            out.append(a.rstrip(".") if a.startswith("the ") else "et al"); continue
        sur, ini = a.split(",", 1)
        out.append(f"{sur.strip()} {ini.replace('.', '').replace(' ', '').strip()}")
    au = ", ".join(x for x in out if x != "et al") + (" et al" if "et al" in out else "")
    rest = re.sub(r"(\d+(?:\([^)]*\))?),\s+(\S+?)\.(\s+https://doi|$)", r"\1:\2.\3", rest)
    out = f"{au} ({year}) {rest}"
    # Namen mit kleinem Praefix bzw. Akzent-Grossbuchstaben, die die Trennung oben verfehlt
    return (out.replace("Maas H-G,vonOheimb,G", "Maas H-G, von Oheimb G")
               .replace("Novo Pérez MA,Álvarez-González,JG", "Novo Pérez MA, Álvarez-González JG"))


def main():
    s = (P / "Manuscript_EN.md").read_text()
    title = s.splitlines()[0].lstrip("% ").strip()
    abstract = section(s, "Abstract").split("**Keywords")[0].strip()
    body = s[s.index("## 1. Introduction"):s.index("## Code availability")]
    body = body.replace("## 2. Methods", "## 2. Materials and methods")
    body = cite_style(body)
    figs = re.findall(r"!\[(\*\*Figure (\d)\.\*\*.*?)\]\((figures/[^)]+)\)", section(s, "Figures"), re.S)
    caps = "\n\n".join(" ".join(c.split()) for c, n, f in figs)
    figblocks = "\n\n".join(f"![]({f}){{width=16cm}}\n\n**Fig. {n}**\n\n\\newpage" for c, n, f in figs)
    refs_raw = re.split(r"\n(?=- )", section(s, "References"))
    refs = "\n\n".join(ref_springer(e) for e in refs_raw if e.startswith("- "))
    data = cite_style((section(s, "Data availability") + " " + section(s, "Code availability")).replace("\n", " "))
    md = f"""---
title: "{title}"
---

**Angel Naya**

Independent Researcher, Berlin, Germany

Corresponding author: Angel Naya, angel.naya@posteo.de

## Abstract

{abstract}

**Keywords** Terrestrial laser scanning · Diameter at breast height · Occlusion · Circle fitting · Scan design

{body.strip()}

## Acknowledgements

{section(s, "Acknowledgements")}

## Declarations

**Funding** {section(s, "Funding")}

**Competing interests** The author declares no competing interests.

**Author contributions** Angel Naya: conceptualization, methodology, software, formal analysis, investigation, data curation, visualization, writing – original draft, writing – review and editing.

**Data availability** {data}

## References

{refs}

## Figure captions

{caps}

\\newpage

{figblocks}
"""
    OUT.mkdir(exist_ok=True)
    (OUT / "Manuscript_EJFR.md").write_text(md)
    subprocess.run(["pandoc", "EJFR/Manuscript_EJFR.md", "--resource-path=.", "-o", "EJFR/Manuscript_EJFR.docx"], cwd=P, check=True)
    print("->", OUT / "Manuscript_EJFR.docx")


if __name__ == "__main__":
    main()
