#!/usr/bin/env bash
# Einreichdateien fuer Computers & Geosciences aus den Markdown-Quellen erzeugen.
# Braucht pandoc und LibreOffice (soffice). Aufruf: bash build.sh
set -euo pipefail
cd "$(dirname "$0")"
tmp="$(mktemp -d)"
# Abbildungen als PNG einbinden (Word kann kein SVG zuverlaessig)
sed 's#figures/\(fig[0-9]_[a-z]*\)\.svg#figures/\1.png#g' Manuscript_EN.md > "$tmp/ms.md"
pandoc "$tmp/ms.md" --resource-path=. --reference-doc=reference_cageo.docx -o Manuscript_EN.docx
pandoc Highlights.md -o Highlights.docx
pandoc Cover_Letter.md -o Cover_Letter.docx
soffice --headless --convert-to pdf --outdir . Manuscript_EN.docx >/dev/null 2>&1
rm -rf "$tmp"
echo "-> Manuscript_EN.docx/.pdf, Highlights.docx, Cover_Letter.docx"
