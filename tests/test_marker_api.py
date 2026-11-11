"""Studio-API fuer Marker (Aufgabe B) und Freigabefilter (Aufgabe E).

Prueft marker_schema.clean_marker / is_public direkt und die FastAPI-Routen
gegen einen temporaeren lokalen Speicher (kein Docker, keine Rohdaten).
"""
import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "app"))
from marker_schema import clean_marker, consent_of, is_public, media_srcs, public_markers  # noqa: E402


# ---- clean_marker -----------------------------------------------------------
def test_clean_keeps_media_text_links_rights():
    m = {"id": "k1", "label": "Küche", "yaw": 10, "pitch": -5,
         "title": "Die Küche", "text": "Hier wurde gekocht.",
         "media": [{"type": "video", "src": "media/scenes/s/story/a.mp4", "caption": "Interview"}],
         "links": [{"label": "MUHBA", "url": "https://barcelona.cat/museuhistoria"}],
         "time": {"from": "1952", "to": 1968, "phase": "Anbau"},
         "provenance": "erinnert",
         "rights": {"consent": "onsite", "license": "CC BY-NC-ND 4.0"}}
    c = clean_marker(m)
    assert c["anchor"] == {"type": "pano", "yaw": 10.0, "pitch": -5.0}
    assert c["media"][0]["src"].endswith("a.mp4")
    assert c["links"][0]["url"].startswith("https://")
    assert c["time"] == {"from": 1952, "to": 1968, "phase": "Anbau"}
    assert c["rights"] == {"consent": "onsite", "license": "CC BY-NC-ND 4.0"}
    assert c["provenance"] == "erinnert"


def test_clean_keeps_rich_legacy_fields():
    # Wald-Panel-Marker: kind/facts/sources duerfen beim Speichern nicht verloren gehen
    m = {"id": "boden", "kind": "boden", "label": "Boden", "yaw": 1, "pitch": 2,
         "facts": [["pH", "4,5"]], "body": "<b>Braunerde</b>"}
    c = clean_marker(m)
    assert c["kind"] == "boden" and c["facts"] == [["pH", "4,5"]] and c["body"] == "<b>Braunerde</b>"


def test_clean_3d_marker():
    c = clean_marker({"id": "j", "pos": [1.23456, 0, -2], "title": "Porträt"})
    assert c["anchor"] == {"type": "3d", "pos": [1.2346, 0.0, -2.0]}


@pytest.mark.parametrize("bad", [
    {"id": "x"},                                     # keine Position
    {"id": "x", "yaw": "a", "pitch": 1},             # yaw keine Zahl
    {"id": "x", "pos": [1, 2]},                      # pos unvollstaendig
    {"id": "x", "yaw": 1, "pitch": 1, "rights": {"consent": "locked"}},  # Sperre ohne Jahr
    "kein Objekt",
])
def test_clean_rejects(bad):
    with pytest.raises(ValueError):
        clean_marker(bad)


def test_clean_drops_unsafe_urls():
    c = clean_marker({"id": "x", "yaw": 0, "pitch": 0,
                      "media": [{"type": "image", "src": "javascript:alert(1)"}],
                      "links": [{"label": "böse", "url": "data:text/html,x"}]})
    assert "media" not in c and "links" not in c


def test_clean_drops_unknown_provenance():
    c = clean_marker({"id": "x", "yaw": 0, "pitch": 0, "provenance": "ausgedacht"})
    assert "provenance" not in c


# ---- Freigabe -----------------------------------------------------------------
def test_consent_defaults_and_unknown():
    assert consent_of({"yaw": 0}) == "public"            # Altmarker
    assert consent_of({"rights": {"consent": "egal"}}) == "research"   # unbekannt = nicht oeffentlich


def test_is_public_levels():
    assert is_public({"rights": {"consent": "public"}})
    assert not is_public({"rights": {"consent": "onsite"}})
    assert not is_public({"rights": {"consent": "research"}})
    locked = {"rights": {"consent": "locked", "until": 2030}}
    assert not is_public(locked, 2029)
    assert is_public(locked, 2030)


def test_public_markers_and_media_srcs():
    ms = [{"id": "a", "yaw": 0, "pitch": 0, "media": [{"type": "video", "src": "story/a.mp4"}]},
          {"id": "b", "yaw": 0, "pitch": 0, "rights": {"consent": "onsite"},
           "media": [{"type": "video", "src": "story/b.mp4"}]}]
    assert [m["id"] for m in public_markers(ms, 2026)] == ["a"]
    assert media_srcs(ms[1]) == {"story/b.mp4"}


def test_all_existing_markers_stay_public():
    # Kein bestehender Marker in docs/data/ darf durch den Filter verschwinden
    for f in sorted((REPO / "docs" / "data").glob("scene-*.json")):
        ms = json.loads(f.read_text(encoding="utf-8")).get("markers") or []
        assert len(public_markers(ms, 2026)) == len(ms), f.name


def test_existing_markers_survive_clean():
    # Jeder bestehende Marker mit Position laesst sich ueber die API speichern
    for f in sorted((REPO / "docs" / "data").glob("scene-*.json")):
        for i, m in enumerate(json.loads(f.read_text(encoding="utf-8")).get("markers") or []):
            c = clean_marker(m, i)
            assert c["id"] == (m.get("id") or f"m{i + 1}"), f.name


# ---- API ------------------------------------------------------------------------
@pytest.fixture()
def client(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    monkeypatch.setenv("STORAGE", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    import main
    main = importlib.reload(main)
    scene = {"id": "testhaus", "title": "Testhaus", "markers": []}
    main.media.put_bytes("scenes/testhaus/scene.json", json.dumps(scene).encode())
    return TestClient(main.app), main


def test_api_roundtrip_and_public_filter(client):
    c, _ = client
    markers = [
        {"id": "a", "yaw": 0, "pitch": 0, "title": "Öffentlich",
         "media": [{"type": "video", "src": "media/scenes/testhaus/story/a.mp4"}]},
        {"id": "b", "yaw": 10, "pitch": 0, "title": "Nur vor Ort",
         "rights": {"consent": "onsite"}},
    ]
    r = c.put("/api/studio/scenes/testhaus/markers", json={"markers": markers})
    assert r.status_code == 200 and r.json()["count"] == 2
    studio = c.get("/api/studio/scenes/testhaus").json()
    assert [m["id"] for m in studio["markers"]] == ["a", "b"]
    assert studio["markers"][0]["media"][0]["type"] == "video"
    public = c.get("/api/scenes/testhaus").json()
    assert [m["id"] for m in public["markers"]] == ["a"]
    listing = c.get("/api/scenes").json()
    assert listing[0]["markers"] == 1 and listing[0]["markers_total"] == 2


def test_api_rejects_bad_marker_and_duplicate_ids(client):
    c, _ = client
    r = c.put("/api/studio/scenes/testhaus/markers", json={"markers": [{"id": "x"}]})
    assert r.status_code == 400
    dup = [{"id": "x", "yaw": 0, "pitch": 0}, {"id": "x", "yaw": 1, "pitch": 1}]
    assert c.put("/api/studio/scenes/testhaus/markers", json={"markers": dup}).status_code == 400


def test_api_media_upload(client):
    c, main = client
    r = c.post("/api/studio/scenes/testhaus/media",
               files={"file": ("Interview Oma.MP4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["type"] == "video"
    assert j["src"].startswith("media/scenes/testhaus/story/interview-oma-") and j["src"].endswith(".mp4")
    assert main.media.exists(j["src"][len("media/"):])
    bad = c.post("/api/studio/scenes/testhaus/media", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 400
    missing = c.post("/api/studio/scenes/gibtsnicht/media", files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert missing.status_code == 404


# ---- Export (Aufgabe E) ------------------------------------------------------------
def test_export_withholds_non_public_markers_and_their_media(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    sys.path.insert(0, str(REPO / "platform" / "dev"))
    import export_static as ex
    media = tmp_path / "media"
    scene_dir = media / "scenes" / "testhaus"
    (scene_dir / "story").mkdir(parents=True)
    (scene_dir / "story" / "a.mp4").write_bytes(b"a")
    (scene_dir / "story" / "b.mp4").write_bytes(b"b")
    scene = {"id": "testhaus", "title": "T", "markers": [
        {"id": "a", "yaw": 0, "pitch": 0, "media": [{"type": "video", "src": "media/scenes/testhaus/story/a.mp4"}]},
        {"id": "b", "yaw": 1, "pitch": 0, "rights": {"consent": "onsite"},
         "media": [{"type": "video", "src": "media/scenes/testhaus/story/b.mp4"}]},
    ]}
    (scene_dir / "scene.json").write_text(json.dumps(scene), encoding="utf-8")
    out = tmp_path / "docs"
    monkeypatch.setattr(ex, "MEDIA", media)
    monkeypatch.setattr(ex, "OUT", out)
    monkeypatch.setattr(ex, "load_publish_list", lambda: (None, []))
    monkeypatch.setattr(sys, "argv", ["export_static.py"])
    ex.main()
    exported = json.loads((out / "data" / "scene-testhaus.json").read_text(encoding="utf-8"))
    assert [m["id"] for m in exported["markers"]] == ["a"]
    story = out / "media" / "scenes" / "testhaus" / "story"
    assert (story / "a.mp4").is_file()
    assert not (story / "b.mp4").exists()
