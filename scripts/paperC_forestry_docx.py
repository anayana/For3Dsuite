#!/usr/bin/env python3
"""paperC_forestry_docx.py -- Word-Fassung von Paper C nach der Forestry-Vorlage (OUP, Mai 2024).

Aus Manuscript_EN.md: Titelblock wie Vorlage, Abschnitte ohne Nummern, Abbildungen im
Text nach dem Absatz der ersten Erwaehnung, Schlussabschnitte in der Reihenfolge der
Vorlage (Funding, Acknowledgements, Conflict of interest statement, Data availability
statement, References, Table and Figure captions), Literatur im Oxford-SciMed-Stil.
Formatvorlagen kommen aus der Vorlage (pandoc --reference-doc).

  python scripts/paperC_forestry_docx.py <forestry-template.docx>
"""
import re
import subprocess
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "Paper_ODT" / "Forst_Benchmark_Paper"

REFS = """\
Abegg, M., Kükenbrink, D., Zell, J., Schaepman, M.E. and Morsdorf, F. 2017 Terrestrial laser scanning for forest inventories—tree diameter distribution and scanner location impact on occlusion. *Forests* 8, 184.

Al-Sharadqah, A. and Chernov, N. 2009 Error analysis for circle fitting algorithms. *Electron. J. Stat.* 3, 886–911.

Chang, M., Candotti, A., von Ellenrieder, K., Tomelleri, E. and Camurri, M. 2025 Data for: “A multi-platform LiDAR dataset for standardized forest inventory measurement at long term ecological monitoring sites”. Zenodo. https://doi.org/10.5281/zenodo.17186174.

Chernov, N. 2010 *Circular and Linear Regression: Fitting Circles and Lines by Least Squares*. CRC Press, Boca Raton.

Fischler, M.A. and Bolles, R.C. 1981 Random sample consensus: a paradigm for model fitting with applications to image analysis and automated cartography. *Commun. ACM* 24, 381–395.

Gollob, C., Ritter, T. and Nothdurft, A. 2020a Comparison of 3D point clouds obtained by terrestrial laser scanning and personal laser scanning on forest inventory sample plots. *Data* 5, 103.

Gollob, C., Ritter, T. and Nothdurft, A. 2020b LAUT – Terrestrial and personal laser scanner data from Austrian forest inventory plots. Zenodo. https://doi.org/10.5281/zenodo.3698956.

Gollob, C., Ritter, T., Wassermann, C. and Nothdurft, A. 2019 Influence of scanner position and plot size on the accuracy of tree detection and diameter estimation using terrestrial laser scanning on forest inventory plots. *Remote Sens.* 11, 1602.

Kåsa, I. 1976 A circle fitting procedure and its error analysis. *IEEE Trans. Instrum. Meas.* IM-25, 8–14.

Laino, D., Cabo, C., Prendes, C., Janvier, R., Ordóñez, C., Nikonovas, T. et al. 2024 3DFin: a software for automated 3D forest inventories from terrestrial point clouds. *Forestry* 97, 479–496.

Laino, D., Cabo, C., Ordóñez, C., Bolanos, R., Janvier, R., Giulioni, F. et al. 2026 SegmentedForests: a labelled dataset of terrestrial LiDAR point clouds for semantic segmentation of forests. *Forestry* 99, cpaf062.

Li, L., Mu, X., Soma, M., Wan, P., Qi, J., Hu, R. et al. 2021 An iterative-mode scan design of terrestrial laser scanning in forests for minimizing occlusion effects. *IEEE Trans. Geosci. Remote Sens.* 59, 3547–3566.

Liang, X., Hyyppä, J., Kaartinen, H. et al. 2018 International benchmarking of terrestrial laser scanning approaches for forest inventories. *ISPRS J. Photogramm. Remote Sens.* 144, 137–179.

Molina-Valero, J.A., Martínez-Calvo, A., Ginzo Villamayor, M.J., Novo Pérez, M.A., Álvarez-González, J.G., Montes, F. et al. 2022 Operationalizing the use of TLS in forest inventories: the R package FORTLS. *Environ. Model. Softw.* 150, 105337.

Ritter, T., Gollob, C. and Nothdurft, A. 2020 Towards an optimization of sample plot size and scanner position layout for terrestrial laser scanning in multi-scan mode. *Forests* 11, 1099.

van der Walt, S., Schönberger, J.L., Nunez-Iglesias, J., Boulogne, F., Warner, J.D., Yager, N. et al. 2014 scikit-image: image processing in Python. *PeerJ* 2, e453.

Winiwarter, L., Esmorís Pena, A.M., Weiser, H., Anders, K., Martínez Sánchez, J., Searle, M. et al. 2022 Virtual laser scanning with HELIOS++: a novel take on ray tracing-based simulation of topographic full-waveform 3D laser scanning. *Remote Sens. Environ.* 269, 112772.
"""


def section(s, name):
    i = s.index(f"## {name}")
    j = s.find("\n## ", i + 3)
    return s[i:j if j > 0 else len(s)].split("\n", 1)[1].strip()


def main():
    tpl = sys.argv[1]
    s = (P / "Manuscript_EN.md").read_text()
    title = s.splitlines()[0].lstrip("% ").strip()
    abstract = section(s, "Abstract").split("**Keywords")[0].strip()
    body = s[s.index("## 1. Introduction"):s.index("## Code availability")]
    # Abbildungen: Block je Nummer, Bildbreite fest
    figs = dict((int(n), b) for b, n in re.findall(
        r"(!\[\*\*Figure (\d)\.\*\*.*?\]\(figures/[^)]+\)(?:\{[^}]*\})?)", section(s, "Figures"), re.S))
    captions = {n: re.match(r"!\[(.*)\]\(", b, re.S).group(1) for n, b in figs.items()}
    for n in figs:
        figs[n] = re.sub(r"\{[^}]*\}$", "", figs[n]) + "{width=15cm}"
    # Ueberschriften ohne Nummern; Ebene um eins hoch (Abschnitt = Heading 1)
    body = re.sub(r"^## \d+\. (.*)$", r"# \1", body, flags=re.M)
    body = re.sub(r"^### \d+\.\d+ (.*)$", r"## \1", body, flags=re.M)
    body = body.replace("# Conclusions", "# Conclusion")
    # Abbildung nach dem Absatz ihrer ersten Erwaehnung
    paras = body.split("\n\n")
    placed = set()
    out = []
    for para in paras:
        out.append(para)
        for n in sorted(figs):
            if n not in placed and re.search(rf"Figs?\. {n}(?![0-9])", para):
                out.append(figs[n]); placed.add(n)
    assert placed == set(figs), placed
    body = "\n\n".join(out)
    data = (section(s, "Data availability") + " " + section(s, "Code availability")).replace("\n", " ")
    md = f"""---
title: "{title}"
---

Angel Naya^1,\\*^

^1^Independent Researcher, Berlin, Germany

^\\*^Corresponding author: Email: angel.naya@posteo.de

{abstract}

{body.strip()}

# Funding

{section(s, "Funding")}

# Acknowledgements

{section(s, "Acknowledgements")}

# Conflict of interest statement

None declared.

# Data availability statement

{data}

# References

{REFS}
# Table and Figure captions

""" + "\n\n".join(captions[n] for n in sorted(captions)) + "\n"
    (P / "Manuscript_Forestry.md").write_text(md)
    subprocess.run(["pandoc", "Manuscript_Forestry.md", "--resource-path=.", f"--reference-doc={tpl}",
                    "-o", "Manuscript_Forestry.docx"], cwd=P, check=True)
    print("->", P / "Manuscript_Forestry.docx")


if __name__ == "__main__":
    main()
