import json

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from bioscale import occurrence as O

CRS = "EPSG:25832"


def _lonlat(x, y):
    from pyproj import Transformer
    return Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform(x, y)


def _dwc(tmp_path, rows):
    p = tmp_path / "p.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_dwc_presence_absence_and_visits(tmp_path):
    rows = []
    for i in range(6):
        lon, lat = _lonlat(600000 + 100 * i, 5650000)
        for v in range(3):
            rows.append(dict(scientificName="Sitta europaea", occurrenceStatus="present" if (i < 3 and v != 1) else "absent",
                             decimalLongitude=lon, decimalLatitude=lat, locationID=f"L{i}", eventID=f"L{i}-{v}",
                             eventDate=f"2025-05-0{v + 1}", samplingEffort="10 min"))
    obs = O.load_observations({"path": str(_dwc(tmp_path, rows))}, "Sitta europaea", CRS, tmp_path)
    assert obs.dtype == "presence_absence" and obs.n == 6
    assert obs.sites.response.sum() == 3
    assert obs.sites.effort.iloc[0] == 30
    vm = O.visit_matrix(obs.sites)
    assert vm.shape == (6, 3) and vm[0, 1] == 0
    assert np.allclose(obs.sites.x.iloc[1] - obs.sites.x.iloc[0], 100, atol=0.01)


def test_complete_lists_other_species_are_absence(tmp_path):
    lon, lat = _lonlat(600000, 5650000)
    lon2, lat2 = _lonlat(601000, 5650000)
    rows = [dict(scientificName="A b", occurrenceStatus="present", decimalLongitude=lon, decimalLatitude=lat),
            dict(scientificName="C d", occurrenceStatus="present", decimalLongitude=lon2, decimalLatitude=lat2)]
    obs = O.load_observations({"path": str(_dwc(tmp_path, rows))}, "A b", CRS, tmp_path)
    assert obs.dtype == "presence_absence" and list(obs.sites.response) == [1, 0]
    obs2 = O.load_observations({"path": str(_dwc(tmp_path, rows)), "complete_lists": False}, "A b", CRS, tmp_path)
    assert obs2.dtype == "presence_only"


def test_counts_and_plausibility(tmp_path):
    rows = []
    for i in range(10):
        lon, lat = _lonlat(600000 + 50 * i, 5650000)
        rows.append(dict(scientificName="X y", occurrenceStatus="present" if i % 3 else "absent", individualCount=(i % 3) * 3,
                         decimalLongitude=lon, decimalLatitude=lat, eventDate="2030-01-01" if i == 0 else "2025-06-01",
                         coordinateUncertaintyInMeters=500 if i == 1 else 5))
    obs = O.load_observations({"path": str(_dwc(tmp_path, rows))}, "X y", CRS, tmp_path, period={"start": "2025-04-01", "end": "2025-08-01"})
    assert obs.dtype == "counts"
    txt = " ".join(obs.issues)
    assert "Zukunft" in txt and "250 m" in txt and "Projektzeitraums" in txt


def test_outside_area_removed(tmp_path):
    lon, lat = _lonlat(600000, 5650000)
    lon2, lat2 = _lonlat(700000, 5650000)
    rows = [dict(scientificName="A b", occurrenceStatus="present", decimalLongitude=lon, decimalLatitude=lat),
            dict(scientificName="A b", occurrenceStatus="absent", decimalLongitude=lon2, decimalLatitude=lat2)]
    obs = O.load_observations({"path": str(_dwc(tmp_path, rows))}, "A b", CRS, tmp_path, area_geom=box(599000, 5649000, 601000, 5651000))
    assert obs.n == 1 and any("ausserhalb" in i for i in obs.issues)


def test_camtrap_dp(tmp_path):
    lon, lat = _lonlat(600000, 5650000)
    pd.DataFrame(dict(deploymentID=["d1", "d2"], latitude=[lat, lat], longitude=[lon, lon + 0.01],
                      deploymentStart=["2025-05-01T00:00:00Z"] * 2, deploymentEnd=["2025-05-11T00:00:00Z", "2025-05-21T00:00:00Z"])
                 ).to_csv(tmp_path / "deployments.csv", index=False)
    pd.DataFrame(dict(observationID=range(4), deploymentID=["d1", "d1", "d1", "d2"], eventID=["e1", "e1", "e2", "e3"],
                      observationType="animal", scientificName=["Capreolus capreolus"] * 3 + ["Sus scrofa"])
                 ).to_csv(tmp_path / "observations.csv", index=False)
    O.camtrap_package_stub(tmp_path)
    obs = O.load_observations({"path": "datapackage.json", "format": "camtrapdp"}, "Capreolus capreolus", CRS, tmp_path)
    assert obs.dtype == "counts"
    s = obs.sites.set_index("locationID")
    assert s.loc["d1", "count"] == 2 and s.loc["d2", "count"] == 0
    assert s.loc["d1", "effort"] == pytest.approx(10) and s.loc["d2", "effort"] == pytest.approx(20)


def test_birdnet_and_batdetect(tmp_path):
    lon, lat = _lonlat(600000, 5650000)
    pd.DataFrame(dict(locationID=["A", "B"], latitude=[lat, lat], longitude=[lon, lon + 0.01])).to_csv(tmp_path / "st.csv", index=False)
    pd.DataFrame({"Start (s)": [0, 3, 6], "End (s)": [3, 6, 9], "Scientific name": ["Sitta europaea"] * 3,
                  "Common name": ["Kleiber"] * 3, "Confidence": [0.9, 0.5, 0.95],
                  "File": ["A/rec1.wav", "B/rec1.wav", "A/rec2.wav"]}).to_csv(tmp_path / "bn.csv", index=False)
    obs = O.load_observations({"path": "bn.csv", "format": "birdnet", "sites": "st.csv"}, "Sitta europaea", CRS, tmp_path)
    s = obs.sites.set_index("locationID")
    assert s.loc["A", "count"] == 2 and s.loc["B", "count"] == 0 and s.loc["A", "effort"] == 2
    pd.DataFrame({"file": ["A/n1.wav", "B/n1.wav"], "class": ["Pipistrellus pipistrellus"] * 2,
                  "class_prob": [0.9, 0.9], "det_prob": [0.9, 0.3]}).to_csv(tmp_path / "bd.csv", index=False)
    obs = O.load_observations({"path": "bd.csv", "format": "batdetect2", "sites": "st.csv"}, "Pipistrellus pipistrellus", CRS, tmp_path)
    assert obs.sensitive
    assert list(obs.sites.sort_values("locationID").detected) == [1, 0]


def test_sensitive_and_coarsen():
    assert O.is_sensitive("Myotis bechsteinii") and O.is_sensitive("Ciconia nigra")
    assert not O.is_sensitive("Ciconia ciconia") and not O.is_sensitive("Parus major")
    assert O.is_sensitive("Parus major", ["Parus major"])
    x, y = O.coarsen_xy([600123.0, 600987.0], [5650444.0, 5650001.0], 1000)
    assert list(x) == [600500.0, 600500.0] and list(y) == [5650500.0, 5650500.0]


def test_occupancy_null_recovers_p():
    rng = np.random.default_rng(0)
    z = rng.random(400) < 0.6
    V = (rng.random((400, 4)) < 0.4) & z[:, None]
    r = O.occupancy_null(V.astype(float))
    assert abs(r["p"] - 0.4) < 0.06 and abs(r["psi"] - 0.6) < 0.08 and r["naive"] < r["psi"]
