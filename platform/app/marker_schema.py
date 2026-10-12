"""Einheitliches Marker-Schema fuer Panorama- und Splat-Szenen.

Gegenstueck zu normalizeMarker() in platform/web/gallery/marker-card.js
(CLAUDE_CODE_UEBERGABE.md, Aufgabe A). Nur Standardbibliothek -- laeuft im
Backend, in Dev-Skripten und in den Tests.

Schema:
    {"id", "anchor": {"type": "pano", "yaw", "pitch", "xyz"?} | {"type": "3d", "pos"},
     "title", "text", "media": [{"type": "video"|"image"|"audio", "src", "poster"?,
     "caption"?, "credit"?, "alt"?}], "links": [{"label", "url"}],
     "time": {"from", "to", "phase"}, "provenance", "rights": {"consent", "license"},
     "attributes": {}, "demo"}

Alte Felder: yaw/pitch (+ xyz) -> anchor pano, pos -> anchor 3d,
image/video (+ poster/caption/credit) -> media[0], label -> title, sources -> links.
Alle anderen Felder (kind, type, target, attributes, prognosis, facts ...)
bleiben unangetastet.
"""
import copy
import re

MEDIA_TYPES = ("video", "image", "audio")
# Felder, die im neuen Schema aufgehen und mit strip_legacy entfallen
LEGACY_FIELDS = ("yaw", "pitch", "xyz", "pos", "image", "video", "poster",
                 "caption", "credit", "sources")

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def safe_url(u):
    """http(s), mailto und relative Pfade; alles andere (javascript:, data:) -> ''."""
    if not isinstance(u, str):
        return ""
    s = u.strip()
    if not s or any(ord(c) < 32 for c in s):
        return ""
    if re.match(r"^(https?:|mailto:)", s, re.I):
        return s
    return "" if _SCHEME.match(s) else s


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v \
        and v not in (float("inf"), float("-inf"))


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v)


def legacy_anchor(m):
    if _num(m.get("yaw")) and _num(m.get("pitch")):
        a = {"type": "pano", "yaw": m["yaw"], "pitch": m["pitch"]}
        if _vec3(m.get("xyz")):
            a["xyz"] = m["xyz"]
        return a
    if _vec3(m.get("pos")):
        return {"type": "3d", "pos": m["pos"]}
    return None


def legacy_media(m):
    """Altformat: hoechstens ein Medium, Video vor Bild (wie der alte Splat-Viewer)."""
    if m.get("video"):
        it = {"type": "video", "src": m["video"]}
    elif m.get("image"):
        it = {"type": "image", "src": m["image"]}
    else:
        return []
    for k in ("poster", "caption", "credit"):
        if m.get(k):
            it[k] = m[k]
    return [it]


def normalize_marker(m, strip_legacy=False):
    """Marker (alt oder neu) -> Marker mit Schema-Feldern. Idempotent.

    Standard: nicht-destruktiv, die alten Felder bleiben zusaetzlich stehen
    (Studio-Editor und API lesen noch yaw/pitch/xyz/label). strip_legacy=True
    entfernt sie -- erst sinnvoll, wenn Studio + API das neue Schema sprechen
    (Aufgaben B/C).
    """
    n = copy.deepcopy(m)
    anchor = n.get("anchor") if isinstance(n.get("anchor"), dict) else legacy_anchor(n)
    if anchor is not None:
        n["anchor"] = anchor
    if n.get("title") is None and n.get("label") is not None:
        n["title"] = n["label"]
    media = n["media"] if isinstance(n.get("media"), list) else legacy_media(n)
    n["media"] = [it for it in media if isinstance(it, dict)
                  and it.get("type") in MEDIA_TYPES and safe_url(it.get("src"))]
    links = n["links"] if isinstance(n.get("links"), list) else (n.get("sources") or [])
    n["links"] = [l for l in links if isinstance(l, dict) and safe_url(l.get("url"))]
    if not n["media"]:
        del n["media"]
    if not n["links"]:
        del n["links"]
    if strip_legacy and anchor is not None:
        for k in LEGACY_FIELDS:
            if k == "sources" and "links" not in n:
                continue
            if k in ("caption", "credit") and "media" not in n:
                continue           # Karte ohne Medium: Credit gehoert zur Karte
            n.pop(k, None)
        if n.get("label") == n.get("title"):
            n.pop("label", None)   # abweichendes Kurzlabel (Hotspot) bleibt
    return n


def anchor_view(n):
    """Positionsfelder, wie die Viewer sie aus einem Marker lesen (fuer Vergleiche)."""
    a = n.get("anchor") if isinstance(n.get("anchor"), dict) else legacy_anchor(n)
    if not a:
        return None
    if a.get("type") == "pano":
        return ("pano", a.get("yaw"), a.get("pitch"), tuple(a["xyz"]) if a.get("xyz") else None)
    return ("3d", tuple(a.get("pos") or ()))
