"""HTML-Bericht in einfacher Sprache (eine Datei, Bilder eingebettet; PNGs zusaetzlich im Ordner)."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from jinja2 import Template  # noqa: E402

AMPEL_TEXT = {
    "gruen": "Belastbar im Gueltigkeitsbereich - trotzdem Unsicherheitskarte beachten.",
    "gelb": "Mit Vorsicht nutzen - Warnungen unten lesen.",
    "rot": "Nicht fuer Entscheidungen nutzen - erst Daten ergaenzen (siehe Stichprobenvorschlag).",
}


def _png(fig, path=None):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _extent(grid):
    minx, miny, maxx, maxy = grid["x0"], grid["y0"] - grid["height"] * grid["res"], grid["x0"] + grid["width"] * grid["res"], grid["y0"]
    return [(minx - minx) / 1000, (maxx - minx) / 1000, 0, (maxy - miny) / 1000], minx, miny


def map_figs(result, maps, out, points=None):
    g = result["grid"]
    ext, x0, y0 = _extent(g)
    figs = {}
    lab = "Vorkommenswahrscheinlichkeit" if result["dtype"] == "presence_absence" else (
        "relative Eignung" if result["dtype"] == "presence_only" else f"erwartete Anzahl je {result['ref_effort']:g} Aufwand")

    def base(ax):
        ax.set_xlabel("km"); ax.set_ylabel("km")

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    im = axs[0].imshow(maps["vorhersage"], extent=ext, cmap="viridis")
    axs[0].set_title("Vorhersage (ganze Flaeche)")
    plt.colorbar(im, ax=axs[0], label=lab, shrink=0.8)
    bg = np.where(np.isfinite(maps["aoa"]) & (maps["aoa"] == 0), 1.0, np.nan)
    axs[1].imshow(bg, extent=ext, cmap="Greys", vmin=0, vmax=2.5)
    im = axs[1].imshow(maps["vorhersage_im_aoa"], extent=ext, cmap="viridis",
                       vmin=np.nanmin(maps["vorhersage"]), vmax=np.nanmax(maps["vorhersage"]))
    axs[1].set_title("Nur im Gueltigkeitsbereich (grau = keine Aussage)")
    plt.colorbar(im, ax=axs[1], label=lab, shrink=0.8)
    for a in axs:
        base(a)
    figs["karte"] = _png(fig, out / "abbildungen" / "karte.png")

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    im = axs[0].imshow(maps["unsicherheit_sd"], extent=ext, cmap="magma")
    axs[0].set_title("Unsicherheit (Streuung der Bootstrap-Modelle)")
    plt.colorbar(im, ax=axs[0], shrink=0.8)
    im = axs[1].imshow(maps["di"], extent=ext, cmap="RdYlBu_r", vmin=0, vmax=max(2 * result["aoa"]["threshold"], 1e-6))
    axs[1].contour(np.nan_to_num(maps["aoa"], nan=1.0), levels=[0.5], colors="k", linewidths=0.8,
                   extent=[ext[0], ext[1], ext[3], ext[2]], origin="upper")
    axs[1].set_title("Unaehnlichkeit zu den Daten (DI), Linie = Grenze AOA")
    plt.colorbar(im, ax=axs[1], shrink=0.8)
    if points is not None:
        px, py, pr = points
        axs[1].scatter((px - x0) / 1000, (py - y0) / 1000, c=np.where(pr > 0, "white", "black"), s=10,
                       edgecolors="k", linewidths=0.4, label="Standorte" + (" (vergroebert)" if result["sensitive"] else ""))
    if result["suggestions"]:
        sx = [(s["x"] - x0) / 1000 for s in result["suggestions"]]
        sy = [(s["y"] - y0) / 1000 for s in result["suggestions"]]
        axs[1].scatter(sx, sy, marker="*", s=120, c="gold", edgecolors="k", label="Vorschlag neu")
        for i, (a, b) in enumerate(zip(sx, sy)):
            axs[1].annotate(str(i + 1), (a, b), fontsize=7, xytext=(3, 3), textcoords="offset points")
    axs[1].legend(loc="lower right", fontsize=7)
    for a in axs:
        base(a)
    figs["unsicherheit"] = _png(fig, out / "abbildungen" / "unsicherheit_aoa.png")
    return figs


def radius_fig(result, out):
    rr = [r for r in result["radius_results"] if len(r["radii"]) > 1]
    if not rr:
        return None
    n = len(rr)
    cols = min(3, n)
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows), squeeze=False)
    chosen = {c["variable"]: c["radius_m"] for c in result["chosen"]}
    for ax, r in zip(axs.ravel(), rr):
        x, y, e = np.array(r["radii"]), np.array(r["scores"]), np.array(r["ses"])
        ax.fill_between(x, y - e, y + e, alpha=0.2)
        ax.plot(x, y, "o-")
        ax.axhline(r["null_score"], color="grey", ls=":", label="ohne Variable")
        ax.axvspan(*r["plausible"], color="orange", alpha=0.15, label="plausibel (1-SE)")
        if r["base"] in chosen:
            ax.axvline(chosen[r["base"]], color="red", label="gewaehlt")
        ax.set_xscale("log")
        ax.set_xticks(x, [f"{v:g}" for v in x], fontsize=7, rotation=45)
        ax.minorticks_off()
        ax.set_title(r["base"] + ("" if r["base"] in chosen else " (nicht genutzt)"), fontsize=9)
        ax.set_xlabel("Wirkradius (m)")
        ax.set_ylabel("Guete (hoeher = besser)")
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    axs.ravel()[0].legend(fontsize=7)
    fig.tight_layout()
    return _png(fig, out / "abbildungen" / "wirkradien.png")


def cv_fig(result, out):
    cv = result["cv"]
    key = "AUC" if "AUC" in next(iter(cv.values()))["raeumlich"] else "Deviance_erklaert"
    names = list(cv)
    sp = [cv[n]["raeumlich"].get(key, np.nan) for n in names]
    rd = [cv[n]["zufaellig"].get(key, np.nan) for n in names]
    fig, ax = plt.subplots(figsize=(5, 3.2))
    x = np.arange(len(names))
    ax.bar(x - 0.2, rd, 0.4, label="zufaellige Pruefung", color="#bbb")
    ax.bar(x + 0.2, sp, 0.4, label="raeumliche Pruefung", color="#2a7")
    ax.set_xticks(x, [n.upper() for n in names])
    ax.set_ylabel(key)
    lo = min([v for v in sp + rd if np.isfinite(v)] + [0.5])
    ax.set_ylim(max(0, lo - 0.1), 1)
    ax.legend(fontsize=8)
    return _png(fig, out / "abbildungen" / "pruefung.png")


def calib_fig(result, out):
    c = result.get("calibration")
    if not c:
        return None
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.plot([0, 1], [0, 1], "k:")
    ax.plot([r["vorhergesagt"] for r in c], [r["beobachtet"] for r in c], "o-")
    ax.set_xlabel("vorhergesagt"); ax.set_ylabel("beobachtet")
    ax.set_title("Kalibrierung (raeumlich geprueft)", fontsize=9)
    return _png(fig, out / "abbildungen" / "kalibrierung.png")


TEMPLATE = Template(r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioScale-Bericht</title>
<style>
:root{--bg:#fff;--fg:#1d2329;--muted:#5b6670;--card:#f4f6f7;--line:#d9dee2;--g:#1f9d55;--y:#d69e2e;--r:#c53030}
@media (prefers-color-scheme:dark){:root{--bg:#14181b;--fg:#e7ecef;--muted:#9aa6af;--card:#1d2328;--line:#2e363d}}
body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}
h1{font-size:1.6em;margin-bottom:.2em} h2{margin-top:1.6em;border-bottom:1px solid var(--line);padding-bottom:.2em}
.muted{color:var(--muted)} .card{background:var(--card);border-radius:10px;padding:12px 16px;margin:12px 0}
.ampel{display:flex;gap:14px;align-items:center}.dot{width:34px;height:34px;border-radius:50%;flex:none}
.gruen{background:var(--g)}.gelb{background:var(--y)}.rot{background:var(--r)}
table{border-collapse:collapse;width:100%;font-size:.92em;display:block;overflow-x:auto}
td,th{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;white-space:nowrap}
img{max-width:100%;height:auto;background:#fff;border-radius:6px}
li{margin:.25em 0} code{background:var(--card);padding:0 4px;border-radius:4px}
</style></head><body>
<h1>{{ r.species }} - {{ r.project }}</h1>
<div class="muted">Profil: {{ r.profile.label }} ({{ r.profile.status }}) - Gebiet {{ "%.0f"|format(r.area_ha) }} ha,
Raster {{ r.grid.res|round(1) }} m - BioScale {{ version }}</div>

<div class="card ampel"><div class="dot {{ r.ampel }}"></div><div><b>Kurzfazit: {{ ampel_text }}</b><br>
{{ r.n_sites }} Standorte, {{ r.n_events }} Ereignisse ({{ dtype_text }}).
Raeumlich gepruefte Guete: <b>{{ main_metric }}</b>. Gueltigkeitsbereich: <b>{{ "%.0f"|format(100*r.aoa.fraction) }} %</b> der Flaeche.</div></div>

{% if r.sensitive %}<div class="card"><b>Sensible Art.</b> Punkte in diesem Bericht sind auf {{ coarsen }} m vergroebert.
Karten voller Aufloesung liegen in <code>karten/</code> und duerfen nicht veroeffentlicht werden; zum Teilen
<code>veroeffentlichung/</code> verwenden.</div>{% endif %}

<h2>1. Karte</h2>
<p>Links die Vorhersage fuer die ganze Flaeche, rechts nur dort, wo die Umweltbedingungen den Daten aehneln
(<b>Gueltigkeitsbereich, AOA</b>). Im grauen Bereich trifft die Karte keine Aussage: Dort gab es keine vergleichbaren Standorte.</p>
<img src="data:image/png;base64,{{ figs.karte }}" alt="Karte">

<h2>2. Wie sicher ist die Karte?</h2>
<p>Links: Wie stark sich die Vorhersage aendert, wenn man das Modell mit leicht anderen Stichproben rechnet (heller = unsicherer).
Rechts: Wie unaehnlich jede Stelle den beprobten Standorten ist. Sterne = Vorschlaege fuer neue Standorte.</p>
<img src="data:image/png;base64,{{ figs.unsicherheit }}" alt="Unsicherheit">

<h2>3. Wie gut ist das Modell?</h2>
<p>Gepruefte Modelle: {{ r.cv.keys()|join(", ")|upper }}. Gewaehlt: <b>{{ r.best_model|upper }}</b>.
Die Pruefung ist <b>raeumlich</b> (kNNDM): Getestet wird an Standorten, die so weit von den Trainingsdaten entfernt sind,
wie die Karte im Mittel extrapolieren muss. Die zufaellige Pruefung ist zum Vergleich gezeigt - sie ist meist zu optimistisch.
Wirkradius und Variablen wurden in jeder Pruef-Runde neu gewaehlt (keine Selbsttaeuschung durch Radiussuche).</p>
<img src="data:image/png;base64,{{ figs.pruefung }}" alt="Pruefung" style="max-width:480px">
{% if figs.kalibrierung %}<img src="data:image/png;base64,{{ figs.kalibrierung }}" alt="Kalibrierung" style="max-width:340px">{% endif %}
<table><tr><th>Modell</th><th>Pruefung</th>{% for k in metric_keys %}<th>{{ k }}</th>{% endfor %}</tr>
{% for m, v in r.cv.items() %}{% for t in ["raeumlich","zufaellig"] %}<tr><td>{{ m|upper }}</td><td>{{ t }}</td>
{% for k in metric_keys %}<td>{{ "%.3f"|format(v[t].get(k, nan)) }}</td>{% endfor %}</tr>{% endfor %}{% endfor %}</table>

<h2>4. Welche Variablen und Wirkradien zaehlen?</h2>
<table><tr><th>Variable</th><th>Wirkradius</th><th>plausible Spanne</th><th>Wichtigkeit</th><th>Herkunft</th></tr>
{% for c in r.chosen %}<tr><td>{{ c.variable }}</td><td>{{ "%.0f"|format(c.radius_m) }} m</td>
<td>{{ plaus[c.variable] }}</td><td>{{ "%.0f"|format(100*c.wichtigkeit) }} %</td><td>{{ src[c.variable] }}</td></tr>{% endfor %}</table>
<p class="muted">Wirkradius = 2 Sigma eines Gauss-Kernels (ca. 86 % des Gewichts liegen innerhalb). Plausible Spanne:
alle Radien, die innerhalb eines Standardfehlers gleich gut sind. Eine breite Spanne heisst: Der Radius ist aus diesen Daten kaum bestimmbar.</p>
{% if figs.radien %}<img src="data:image/png;base64,{{ figs.radien }}" alt="Wirkradien">{% endif %}
{% if r.selection_notes %}<ul>{% for n in r.selection_notes %}<li>{{ n }}</li>{% endfor %}</ul>{% endif %}
{% if truth %}<div class="card"><b>Kontrolle gegen die Wahrheit (nur Demo):</b> wahrer Wirkradius {{ truth.true_radius_m }} m.
{% if truth.corr is defined %} Korrelation Karte vs. wahre Wahrscheinlichkeit im AOA: {{ "%.2f"|format(truth.corr_aoa) }},
ausserhalb: {{ "%.2f"|format(truth.corr_out) }}.{% endif %}</div>{% endif %}

<h2>5. Decken die Standorte das Gebiet ab?</h2>
<table><tr><th>Variable</th><th>Flaeche in Spanne der Punkte</th><th>Verteilungsabstand (KS)</th><th>Punkte min-max</th><th>Gebiet 5-95 %</th></tr>
{% for c in r.coverage %}<tr><td>{{ c.variable }}</td><td>{{ "%.0f"|format(100*c.flaeche_in_spanne) }} %</td><td>{{ "%.2f"|format(c.ks_abstand) }}</td>
<td>{{ "%.3g"|format(c.punkte_min) }} - {{ "%.3g"|format(c.punkte_max) }}</td><td>{{ "%.3g"|format(c.gebiet_p05) }} - {{ "%.3g"|format(c.gebiet_p95) }}</td></tr>{% endfor %}</table>
{% if r.access_bias %}<p>Abstand zu Wegen: Median an Standorten {{ "%.0f"|format(r.access_bias.median_punkte) }} m,
im Gebiet {{ "%.0f"|format(r.access_bias.median_gebiet) }} m{% if r.access_bias.verzerrt %} - <b>Standorte sind wegnah verzerrt.</b>{% endif %}</p>{% endif %}
{% if r.occupancy %}<p>Erkennungswahrscheinlichkeit (einfaches Occupancy-Modell ohne Kovariaten): je Begehung
<b>{{ "%.2f"|format(r.occupancy.p) }}</b>, nach {{ "%.1f"|format(r.occupancy.mean_visits) }} Begehungen {{ "%.2f"|format(r.occupancy.p_cum) }}.
Geschaetzte Besetzung {{ "%.2f"|format(r.occupancy.psi) }} (beobachtet {{ "%.2f"|format(r.occupancy.naive) }}).</p>{% endif %}

<h2>6. Wo lohnen neue Standorte?</h2>
<p>Die Vorschlaege erweitern den Gueltigkeitsbereich am staerksten (Datei <code>neue_standorte.gpx</code> fuers GPS,
<code>neue_standorte.gpkg</code> fuer QGIS). Vor Ort Zugang, Sicherheit und Genehmigungen pruefen.</p>
{% if r.suggestions %}<table><tr><th>Nr.</th><th>Rechtswert</th><th>Hochwert</th><th>AOA-Gewinn</th></tr>
{% for s in r.suggestions %}<tr><td>{{ loop.index }}</td><td>{{ "%.0f"|format(s.x) }}</td><td>{{ "%.0f"|format(s.y) }}</td>
<td>+{{ "%.1f"|format(100*s.gewinn) }} %</td></tr>{% endfor %}</table>{% else %}<p>Keine Vorschlaege (Gebiet bereits abgedeckt).</p>{% endif %}

<h2>7. Warnungen</h2>
<ul>{% for w in r.warnings %}<li>{{ w }}</li>{% endfor %}</ul>
{% if r.profile.hints %}<p><b>Hinweise zum Profil:</b></p><ul>{% for h in r.profile.hints %}<li>{{ h }}</li>{% endfor %}</ul>{% endif %}

<h2>8. Herkunft aller Daten</h2>
<table><tr><th>Layer</th><th>Quelle</th><th>Gruppe</th><th>Lizenz</th><th>Verarbeitung</th></tr>
{% for p in r.provenance %}<tr><td>{{ p.name }}</td><td>{{ p.source }}</td><td>{{ p.group }}</td><td>{{ p.license }}</td>
<td>{{ p.processing|join("; ") }}</td></tr>{% endfor %}</table>
{% for n in r.notes %}<p class="muted">{{ n }}</p>{% endfor %}

<h2>9. Dateien</h2>
<ul><li><code>karten/vorhersage_im_aoa.tif</code> - Karte nur im Gueltigkeitsbereich (COG)</li>
<li><code>karten/vorhersage.tif</code>, <code>q05.tif</code>, <code>q95.tif</code>, <code>unsicherheit_sd.tif</code></li>
<li><code>karten/aoa.tif</code> (1 = gueltig), <code>karten/di.tif</code> (Unaehnlichkeit)</li>
<li><code>einflussgroessen/</code> - die gewaehlten Variablen im gewaehlten Radius</li>
<li><code>ergebnis.json</code>, <code>herkunft.json</code> - alle Zahlen und die Herkunft maschinenlesbar</li></ul>
<details><summary>Protokoll</summary><pre style="white-space:pre-wrap;font-size:.8em">{{ r.log|join("\n") }}</pre></details>
<p class="muted">Methoden: Wirkradius-Wahl per raeumlicher Kreuzvalidierung (vgl. Jackson &amp; Fahrig 2015),
kNNDM-Pruefung (Linnenbrink et al. 2024), Gueltigkeitsbereich nach Meyer &amp; Pebesma 2021. Korrelation ist keine Ursache.</p>
</body></html>
""")


def write_report(result, maps, grid, out, points=None, truth=None):
    from . import __version__
    out = Path(out)
    figs = map_figs(result, maps, out, points)
    figs["radien"] = radius_fig(result, out)
    figs["pruefung"] = cv_fig(result, out)
    figs["kalibrierung"] = calib_fig(result, out)
    cv_b = result["cv"][result["best_model"]]["raeumlich"]
    if "AUC" in cv_b:
        main_metric = f"AUC {cv_b['AUC']:.2f}, TSS {cv_b.get('TSS', float('nan')):.2f}, Boyce {cv_b.get('Boyce', float('nan')):.2f}"
        metric_keys = ["AUC", "TSS", "Boyce", "Deviance", "Brier", "Kalibrierung_Steigung"]
    else:
        main_metric = f"R2 {cv_b['R2']:.2f}, erklaerte Devianz {cv_b['Deviance_erklaert']:.2f}"
        metric_keys = ["R2", "Deviance_erklaert", "Spearman"]
    plaus = {}
    for r in result["radius_results"]:
        lo, hi = r["plausible"]
        plaus[r["base"]] = f"{lo:.0f}-{hi:.0f} m" if len(r["radii"]) > 1 else "-"
    src = {p["name"]: p["source"] for p in result["provenance"]}
    dtype_text = {"presence_absence": "Vorkommen/Fehlen", "counts": "Zaehlungen", "presence_only": "nur Vorkommen"}[result["dtype"]]
    html = TEMPLATE.render(r=result, figs=figs, version=__version__, ampel_text=AMPEL_TEXT[result["ampel"]],
                           main_metric=main_metric, metric_keys=metric_keys, plaus=plaus, src=src, nan=float("nan"),
                           dtype_text=dtype_text, truth=truth or result.get("truth"),
                           coarsen=result.get("coarsen_m", 1000))
    p = out / "bericht.html"
    p.write_text(html, encoding="utf-8")
    return p
