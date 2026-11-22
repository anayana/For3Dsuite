"""Ende-zu-Ende auf synthetischen Daten."""
import json

import numpy as np
import pandas as pd
import pytest
import rasterio
import yaml

from bioscale.pipeline import run
from bioscale.synthetic import write_demo_project


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo")
    proj = write_demo_project(d, seed=42)
    return proj, run(proj, echo=False)


def test_demo_end_to_end(demo):
    proj, r = demo
    out = proj.parent / "ergebnis"
    for f in ["bericht.html", "ergebnis.json", "herkunft.json", "neue_standorte.gpx", "neue_standorte.gpkg",
              "karten/vorhersage_im_aoa.tif", "karten/aoa.tif", "karten/di.tif", "karten/unsicherheit_sd.tif",
              "abbildungen/karte.png"]:
        assert (out / f).exists(), f
    html = (out / "bericht.html").read_text()
    assert "Gueltigkeitsbereich" in html and "Korrelation ist keine Ursache" in html
    with rasterio.open(out / "karten/vorhersage_im_aoa.tif") as s:
        assert s.crs.to_epsg() == 25832
    js = json.loads((out / "ergebnis.json").read_text())
    assert js["truth"]["true_radius_m"] == 200


def test_demo_finds_truth(demo):
    _, r = demo
    rad = {c["variable"]: c["radius_m"] for c in r["chosen"]}
    habitat = [v for v in rad if v in ("forest", "canopy_height", "ndvi")]
    assert habitat and 100 <= rad[habitat[0]] <= 300
    assert "elevation" in rad  # Hoehenbezug erkannt
    assert 0.3 < r["aoa"]["fraction"] < 0.9  # Osten ausserhalb
    t = r["truth"]
    assert t["corr_aoa"] > 0.8 and t["corr_aoa"] > t["corr_out"]
    assert t["mae_aoa"] < t["mae_out"]
    assert r["cv"][r["best_model"]]["raeumlich"]["AUC"] > 0.75
    assert any("Wegen" in w for w in r["warnings"])  # Bias erkannt
    assert len(r["suggestions"]) >= 5
    # Vorschlaege liegen ueberwiegend im Osten (dort fehlt Abdeckung)
    xs = np.array([s["x"] for s in r["suggestions"]])
    assert np.mean(xs > 600000 + 1500) > 0.6
    assert r["occupancy"]["p"] == pytest.approx(0.75, abs=0.08)


def _modify(proj, fn, name):
    cfg = yaml.safe_load(proj.read_text())
    fn(cfg)
    cfg["output"] = name
    cfg.pop("demo_truth", None)
    p = proj.parent / f"{name}.yml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_sensitive_species_coarsened(demo):
    proj, _ = demo
    p = _modify(proj, lambda c: c["sensitive"].update(taxa=["Virtualis exemplaris"], publish_resolution_m=250) if "sensitive" in c
                else c.update(sensitive={"taxa": ["Virtualis exemplaris"], "publish_resolution_m": 250, "coarsen_m": 1000}),
                "sensibel")
    cfg = yaml.safe_load(p.read_text()); cfg["model"]["candidates"] = ["glm"]; cfg["model"]["bootstrap"] = 5
    p.write_text(yaml.safe_dump(cfg))
    r = run(p, echo=False)
    assert r["sensitive"]
    pub = proj.parent / "sensibel" / "veroeffentlichung"
    f = list(pub.glob("vorhersage_im_aoa_*m.tif"))
    assert f
    with rasterio.open(f[0]) as s:
        a = s.read(1)
    blk = a[:25, :25]
    assert np.nanstd(blk[np.isfinite(blk)]) < 1e-6  # 250-m-Bloecke konstant
    assert (proj.parent / "sensibel" / "karten" / "NICHT_VEROEFFENTLICHEN.txt").exists()
    assert "vergroebert" in (proj.parent / "sensibel" / "bericht.html").read_text()


def test_presence_only(demo):
    proj, _ = demo
    d = proj.parent / "daten"
    df = pd.read_csv(d / "erhebungen_dwc.csv")
    df[df.occurrenceStatus == "present"].to_csv(d / "nur_vorkommen.csv", index=False)

    def f(c):
        c["occurrence"]["path"] = "daten/nur_vorkommen.csv"
        c["model"]["candidates"] = ["glm"]
        c["model"]["bootstrap"] = 5
    r = run(_modify(proj, f, "po"), echo=False)
    assert r["dtype"] == "presence_only" and r["best_model"] in ("maxent", "glm")
    assert "maxent" in r["cv"]
    assert any("relative Eignung" in w for w in r["warnings"])


def test_counts_with_effort(demo, tmp_path):
    proj, _ = demo
    d = proj.parent / "daten"
    df = pd.read_csv(d / "erhebungen_dwc.csv")
    rng = np.random.default_rng(0)
    df["individualCount"] = np.where(df.occurrenceStatus == "present", rng.poisson(3, len(df)) + 1, 0)
    df.to_csv(d / "zaehlungen.csv", index=False)

    def f(c):
        c["occurrence"]["path"] = "daten/zaehlungen.csv"
        c["model"]["candidates"] = ["glm", "gbm"]
        c["model"]["bootstrap"] = 5
    r = run(_modify(proj, f, "counts"), echo=False)
    assert r["dtype"] == "counts" and "R2" in r["cv"]["glm"]["raeumlich"]
    assert (proj.parent / "counts" / "bericht.html").exists()
