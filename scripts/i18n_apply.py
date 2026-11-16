#!/usr/bin/env python3
"""i18n_apply.py -- deutsche UI-Texte in HTML/JS durch englische ersetzen.

Ersetzt nur innerhalb von Textknoten und String-Literalen ('..', "..", `..`),
nie in Bezeichnern (so bleiben Attribut-Schluessel wie Alter, Hoehe_m intakt).
Wortgrenzen, laengste Eintraege zuerst.

  python scripts/i18n_apply.py platform/web/gallery/i18n_en_ui.json \\
      platform/web/gallery/index.html platform/web/gallery/scene.html ...
"""
import json
import re
import sys

W = r"[\wäöüÄÖÜß]"


def main():
    table = {k: v for k, v in json.load(open(sys.argv[1], encoding="utf-8")).items()
             if not k.startswith("_")}
    keys = sorted(table, key=len, reverse=True)
    pat = re.compile("|".join(
        (rf"(?<!{W})" if k[0].isalnum() else "") + re.escape(k) + (rf"(?!{W})" if k[-1].isalnum() else "")
        for k in keys))
    span = re.compile(r">([^<>]+)<|'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`([^`]*)`")
    for f in sys.argv[2:]:
        s = open(f, encoding="utf-8").read()
        n = 0

        def fix(m):
            nonlocal n
            g = next(i for i in range(1, 5) if m.group(i) is not None)
            inner = m.group(g)
            new = pat.sub(lambda x: table[x.group(0)], inner)
            if new != inner:
                n += 1
            a, b = m.start(g) - m.start(0), m.end(g) - m.start(0)
            whole = m.group(0)
            return whole[:a] + new + whole[b:]

        out = span.sub(fix, s)
        out = out.replace('<html lang="de">', '<html lang="en">')
        open(f, "w", encoding="utf-8").write(out)
        print(f"{f}: {n} Textstellen uebersetzt")


if __name__ == "__main__":
    main()
