"""Einheitliches Marker-Schema: Lesen alter Marker, Migration, sichere URLs.

Prueft Python (platform/app/marker_schema.py) und -- falls node da ist -- die
Lesefunktion der Viewer (platform/web/gallery/marker-card.js) gegen alle
Marker in docs/data/.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "app"))
from marker_schema import anchor_view, normalize_marker, safe_url  # noqa: E402

DATA = sorted((REPO / "docs" / "data").glob("scene-*.json"))


def all_markers():
    for f in DATA:
        for m in json.loads(f.read_text(encoding="utf-8")).get("markers") or []:
            yield f.name, m


def test_pano_tree_marker():
    m = {"id": "t1", "label": "B1", "yaw": 12.5, "pitch": -3.0,
         "xyz": [1.0, 2.0, 0.5], "attributes": {"BHD_cm": 31}, "demo": True}
    n = normalize_marker(m)
    assert n["anchor"] == {"type": "pano", "yaw": 12.5, "pitch": -3.0, "xyz": [1.0, 2.0, 0.5]}
    assert n["title"] == "B1"
    assert n["attributes"] == {"BHD_cm": 31}
    assert {k: n[k] for k in m} == m          # nicht-destruktiv


def test_splat_story_marker():
    m = {"id": "johnson", "pos": [1.0, -0.1, 0.5], "title": "Willkommen",
         "image": "media/a.jpg", "caption": "Bild", "credit": "gemeinfrei", "text": "<b>x</b>"}
    n = normalize_marker(m)
    assert n["anchor"] == {"type": "3d", "pos": [1.0, -0.1, 0.5]}
    assert n["media"] == [{"type": "image", "src": "media/a.jpg",
                           "caption": "Bild", "credit": "gemeinfrei"}]
    s = normalize_marker(m, strip_legacy=True)
    assert set(s) == {"id", "anchor", "title", "text", "media"}


def test_video_beats_image_and_sources_become_links():
    n = normalize_marker({"id": "v", "yaw": 0, "pitch": 0, "video": "c.mp4", "image": "p.jpg",
                          "sources": [{"label": "Quelle", "url": "https://example.org"}]})
    assert [it["type"] for it in n["media"]] == ["video"]
    assert n["links"] == [{"label": "Quelle", "url": "https://example.org"}]


def test_idempotent_and_new_schema_kept():
    m = {"id": "k", "anchor": {"type": "pano", "yaw": 1, "pitch": 2},
         "title": "Küche", "text": "**Text**",
         "media": [{"type": "audio", "src": "media/x.mp3"},
                   {"type": "video", "src": "javascript:alert(1)"}],
         "links": [{"label": "Archiv", "url": "https://muhba.example"}],
         "time": {"from": 1952, "to": 1968}, "provenance": "erinnert",
         "rights": {"consent": "public", "license": "CC BY 4.0"}}
    n = normalize_marker(m)
    assert n["media"] == [{"type": "audio", "src": "media/x.mp3"}]   # js:-Quelle verworfen
    assert normalize_marker(n) == n
    assert n["time"] == m["time"] and n["rights"] == m["rights"]


@pytest.mark.parametrize("url,ok", [
    ("https://a.org/x", True), ("media/scenes/a/b.mp4", True), ("mailto:a@b.de", True),
    ("javascript:alert(1)", False), (" JavaScript:alert(1)", False),
    ("data:text/html,x", False), ("", False), (None, False),
])
def test_safe_url(url, ok):
    assert bool(safe_url(url)) is ok


def test_docs_markers_keep_count_and_position():
    assert DATA, "docs/data/scene-*.json fehlt"
    total = 0
    for name, m in all_markers():
        total += 1
        for strip in (False, True):
            n = normalize_marker(m, strip_legacy=strip)
            assert anchor_view(n) == anchor_view(m), (name, m.get("id"))
            assert n.get("kind") == m.get("kind") and n.get("type") == m.get("type")
            assert n.get("attributes") == m.get("attributes")
    assert total >= 554       # Stand 7886ba3; weniger hiesse: Marker verloren


JS_CHECK = r"""
import fs from 'node:fs';
const mc = await import(process.argv[1]);
const out = [];
for (const f of JSON.parse(process.argv[2])) {
  for (const m of JSON.parse(fs.readFileSync(f)).markers || []) {
    const n = mc.normalizeMarker(m);
    for (const k of Object.keys(m))
      if (JSON.stringify(m[k]) !== JSON.stringify(n[k])) out.push('feld ' + f + ' ' + k);
    if (m.yaw != null && mc.hasCardContent(n) && !m.kind) out.push('weg ' + f + ' ' + m.id);
  }
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht installiert")
def test_js_reader_keeps_legacy_fields():
    js = (REPO / "platform" / "web" / "gallery" / "marker-card.js").as_uri()
    r = subprocess.run(["node", "--input-type=module", "-e", JS_CHECK, js,
                        json.dumps([str(f) for f in DATA])],
                       capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == []
