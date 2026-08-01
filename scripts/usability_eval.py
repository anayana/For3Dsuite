#!/usr/bin/env python3
"""usability_eval.py -- Nutzbarkeitstest auswerten (Abschnitt 5.4 des Papers).

Liest die JSON-Boegen aus Nutzbarkeitstest_Formular.html und rechnet daraus die
Zahlen, die ins Paper gehoeren: SUS-Score, Aufgaben-Erfolgsquote, Median-Zeit je
Aufgabe, Hilfestellungen. Ausgabe als Tabelle und optional als Markdown-Block
zum direkten Einfuegen.

SUS nach Brooke (1996): ungerade Items Wert-1, gerade Items 5-Wert, Summe x 2,5.
Die Referenzschwelle 68 stammt aus Sauro & Lewis (2016) -- Mittelwert ueber
mehrere Hundert Studien, NICHT eine Bestehensgrenze. Bei kleinem n wird der
MEDIAN berichtet, nicht der Mittelwert: einzelne Ausreisser verzerren bei n<10
den Mittelwert stark.

  python scripts/usability_eval.py boegen/*.json [--markdown]
"""
import argparse
import glob
import json
import statistics as st
from pathlib import Path

SUS_REF = 68.0        # Sauro & Lewis (2016), Mittel ueber ~500 Studien
TASK_LABELS = {
    "consumer360": "Consumer-360 hochladen",
    "sechs_bilder": "Sechs Einzelbilder",
    "e57": "Laserscan (E57)",
    "kuratieren": "Szene kuratieren",
    "teilen": "Öffnen und Marker anklicken",
}


def sus_from_items(items):
    """SUS aus den zehn Einzelwerten; None, wenn unvollstaendig."""
    vals = [items.get(f"item{i+1}") for i in range(10)]
    if any(v is None for v in vals):
        return None
    total = sum((v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(vals))
    return total * 2.5


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", help="JSON-Boegen (Glob erlaubt)")
    ap.add_argument("--markdown", action="store_true",
                    help="Markdown-Block fuers Paper ausgeben")
    args = ap.parse_args()

    paths = []
    for f in args.files:
        paths += [Path(p) for p in glob.glob(f)]
    boegen = []
    for p in sorted(set(paths)):
        try:
            boegen.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  !! {p.name}: {e}")
    if not boegen:
        raise SystemExit("Keine lesbaren Boegen gefunden")

    # ---- SUS ----
    scores = []
    for b in boegen:
        s = b.get("sus_score")
        if s is None:
            s = sus_from_items(b.get("sus") or {})
        if s is not None:
            scores.append(s)
    n = len(boegen)
    print(f"{n} Boegen, davon {len(scores)} mit vollstaendigem SUS\n")

    if scores:
        scores.sort()
        med = st.median(scores)
        q1 = st.median(scores[:len(scores) // 2]) if len(scores) > 1 else med
        q3 = st.median(scores[(len(scores) + 1) // 2:]) if len(scores) > 1 else med
        print(f"SUS  Median {med:.1f}   IQR {q1:.1f}–{q3:.1f}   "
              f"min {min(scores):.1f}  max {max(scores):.1f}")
        print(f"     Referenz {SUS_REF:.0f} (Sauro & Lewis 2016): "
              f"{sum(s >= SUS_REF for s in scores)}/{len(scores)} darueber\n")

    # ---- Aufgaben ----
    ids = []
    for b in boegen:
        for k in (b.get("aufgaben") or {}):
            if k not in ids:
                ids.append(k)
    print(f"{'Aufgabe':30} {'ohne Hilfe':>11} {'mit Hilfe':>10} {'Abbruch':>8} "
          f"{'Median s':>9} {'Hilfen':>7}")
    rows = []
    for k in ids:
        recs = [(b.get("aufgaben") or {}).get(k) for b in boegen]
        recs = [r for r in recs if r]
        ok = sum(1 for r in recs if r.get("erfolg") == "ja")
        hilfe = sum(1 for r in recs if r.get("erfolg") == "hilfe")
        nein = sum(1 for r in recs if r.get("erfolg") == "nein")
        zeiten = [r["sekunden"] for r in recs if r.get("sekunden")]
        hilfen = [r.get("hilfen", 0) for r in recs]
        med_t = st.median(zeiten) if zeiten else None
        rows.append((k, ok, hilfe, nein, med_t, sum(hilfen), len(recs)))
        print(f"{TASK_LABELS.get(k, k):30} {ok:>11} {hilfe:>10} {nein:>8} "
              f"{(f'{med_t:.0f}' if med_t else '—'):>9} {sum(hilfen):>7}")

    ges = sum(r[1] for r in rows)
    total = sum(r[6] for r in rows)
    quote = 100.0 * ges / total if total else 0
    print(f"\nAufgaben-Erfolg ohne Hilfe: {ges}/{total} = {quote:.0f} %")

    # ---- Reibungspunkte ----
    offen = [b.get("offen", {}) for b in boegen]
    txt = [o.get("verwirrend", "").strip() for o in offen if o.get("verwirrend", "").strip()]
    if txt:
        print("\nGenannte Verwirrungspunkte:")
        for t in txt:
            print(f"  - {t[:110]}")

    if args.markdown and scores:
        print("\n--- fuers Paper ---\n")
        print(f"n = {n}, SUS-Median = {med:.1f} (IQR {q1:.1f}–{q3:.1f}), "
              f"Aufgaben-Erfolg ohne Hilfe {quote:.0f} %.\n")
        print("| Aufgabe | ohne Hilfe | Median-Zeit |")
        print("|---|--:|--:|")
        for k, ok, _h, _n, med_t, _hh, cnt in rows:
            print(f"| {TASK_LABELS.get(k, k)} | {ok}/{cnt} | "
                  f"{(f'{med_t:.0f} s' if med_t else '—')} |")


if __name__ == "__main__":
    main()
