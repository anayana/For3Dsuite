import pytest
import yaml

from bioscale import profiles as P
from bioscale import project as PR


def test_all_profiles_load():
    names = P.list_profiles()
    assert {"laufkaefer", "totholzkaefer", "gefaesspflanzen", "tagfalter", "voegel_wald", "wildbienen",
            "fledermaeuse", "huftiere_kamerafalle"} <= set(names)
    for n in names:
        p = P.load_profile(n)
        assert p["radius_m"][0] < p["radius_m"][1]
        assert p["status"]
    assert P.load_profile("fledermaeuse")["radius_m"] == [200, 5000]
    assert P.load_profile("tagfalter")["domain"] == "offenland"


def test_profile_override():
    p = P.merge_overrides(P.load_profile("laufkaefer"), {"radius_m": [5, 50]})
    assert p["radius_m"] == [5, 50] and "angepasst" in p["status"]


def test_bad_profile(tmp_path):
    (tmp_path / "x.yml").write_text(yaml.safe_dump({"name": "x"}))
    with pytest.raises(ValueError):
        P.load_profile(tmp_path / "x.yml")


def test_project_validation(tmp_path):
    (tmp_path / "p.yml").write_text(yaml.safe_dump({"area": "fehlt.gpkg", "occurrence": {"path": "fehlt.csv"},
                                                    "question": {"species": ""}}))
    with pytest.raises(ValueError) as e:
        PR.load_project(tmp_path / "p.yml")
    msg = str(e.value)
    assert "Gebietsdatei" in msg and "Punktdaten" in msg and "species" in msg


def test_wizard(tmp_path):
    answers = iter(["Test", "gebiet.gpkg", "", "punkte.csv", "dwc", "Sitta europaea", "voegel_wald", "20",
                    "2025-04-01", "2025-07-31", "n", "j", "n", "chm.tif", "structure", "", ""])
    out = PR.wizard(tmp_path / "w.yml", ask=lambda q: next(answers), say=lambda *a: None)
    cfg = yaml.safe_load(out.read_text())
    assert cfg["question"]["species"] == "Sitta europaea"
    assert cfg["covariates"]["open"] == {"sentinel2": False, "dem": True, "worldcover": False}
    assert cfg["covariates"]["local"][0]["name"] == "chm"
