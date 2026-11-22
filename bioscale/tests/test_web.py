import time

from fastapi.testclient import TestClient

from bioscale.web.app import create_app


def test_web_demo(tmp_path):
    app = create_app(tmp_path)
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200 and "BioScale" in r.text and "voegel_wald" in r.text
    assert len(c.get("/api/profiles").json()) >= 8
    job = c.post("/api/demo").json()["job"]
    app.state.last_thread.join(timeout=300)
    s = c.get(f"/api/jobs/{job}").json()
    assert s["status"] == "fertig", s
    rep = c.get(s["report_url"])
    assert rep.status_code == 200 and "Gueltigkeitsbereich" in rep.text


def test_web_bad_upload(tmp_path):
    c = TestClient(create_app(tmp_path))
    r = c.post("/api/run", data={"species": "", "profile": "voegel_wald"},
               files={"area": ("a.geojson", b"{}"), "points": ("p.csv", b"x\n1")})
    assert r.status_code == 400 and "species" in r.json()["detail"]
