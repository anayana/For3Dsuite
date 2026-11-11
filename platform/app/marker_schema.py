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


# ---- Freigabe (rights.consent) und Studio-API (Aufgaben B + E) -------------
#
# Freigabestufen pro Marker, festgelegt von der erzaehlenden Person:
#   public    darf im oeffentlichen Online-Rundgang erscheinen
#   onsite    nur in einer Installation vor Ort, nie online
#   research  nur fuer die Auswertung, nie gezeigt
#   locked    gesperrt bis rights.until (Jahr), danach oeffentlich
# Marker ohne rights (alle bisherigen Wald-/Museumsmarker) gelten als public.

CONSENT_LEVELS = ("public", "onsite", "research", "locked")
PROVENANCE = ("erinnert", "dokumentiert", "rekonstruiert", "kuratiert")
MAX_TEXT = 20000
MAX_SHORT = 500


def consent_of(m):
    """Freigabestufe eines Markers; unbekannte Werte gelten als nicht oeffentlich."""
    r = m.get("rights") if isinstance(m, dict) else None
    if not isinstance(r, dict) or r.get("consent") in (None, ""):
        return "public"
    c = r.get("consent")
    return c if c in CONSENT_LEVELS else "research"


def is_public(m, year=None):
    """Darf der Marker oeffentlich (Online-Galerie, statischer Export) erscheinen?"""
    c = consent_of(m)
    if c == "public":
        return True
    if c == "locked" and year is not None:
        until = (m.get("rights") or {}).get("until")
        return _num(until) and year >= until
    return False


def public_markers(markers, year=None):
    return [m for m in (markers or []) if isinstance(m, dict) and is_public(m, year)]


def media_srcs(m):
    """Alle Medienpfade eines Markers (neu und alt), z. B. fuer den Export."""
    n = normalize_marker(m) if isinstance(m, dict) else {}
    out = set()
    for it in n.get("media") or []:
        for k in ("src", "poster"):
            if isinstance(it.get(k), str) and it[k]:
                out.add(it[k])
    return out


def _short(v, limit=MAX_SHORT):
    return v.strip()[:limit] if isinstance(v, str) else ""


def _year(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"-?\d{1,4}", v.strip()):
        return int(v.strip())
    return None


def clean_marker(m, index=0):
    """Ein Marker aus dem Studio -> gepruefte, speicherbare Fassung.

    Nicht-destruktiv: Felder ausserhalb des Schemas (kind, facts, prognosis,
    body, target ...) bleiben erhalten, damit bestehende Wald- und
    Rundgangsmarker beim Speichern nichts verlieren. Die Schema-Felder werden
    geprueft und bereinigt. Wirft ValueError ohne gueltige Position.
    """
    if not isinstance(m, dict):
        raise ValueError("Marker muss ein Objekt sein")
    n = normalize_marker(m)
    out = copy.deepcopy(m)

    a = n.get("anchor")
    if not isinstance(a, dict):
        raise ValueError("Position fehlt (yaw/pitch oder pos)")
    if a.get("type") == "pano" and _num(a.get("yaw")) and _num(a.get("pitch")):
        anchor = {"type": "pano", "yaw": round(float(a["yaw"]), 3),
                  "pitch": round(float(a["pitch"]), 3)}
        if _vec3(a.get("xyz")):
            anchor["xyz"] = a["xyz"]
        out["yaw"], out["pitch"] = anchor["yaw"], anchor["pitch"]   # Altfelder fuer Editor/Viewer
        if "xyz" in anchor:
            out["xyz"] = anchor["xyz"]
        else:
            out.pop("xyz", None)
    elif a.get("type") == "3d" and _vec3(a.get("pos")):
        anchor = {"type": "3d", "pos": [round(float(x), 4) for x in a["pos"]]}
        out["pos"] = anchor["pos"]
    else:
        raise ValueError("Position ungueltig (yaw/pitch als Zahlen oder pos als [x, y, z])")
    out["anchor"] = anchor

    out["id"] = _short(str(m.get("id") or ""), 64) or f"m{index + 1}"
    for k in ("label", "title"):
        if k in out:
            out[k] = _short(out.get(k))
    if "title" not in out and n.get("title"):
        out["title"] = _short(n["title"])
    if "text" in out:
        out["text"] = out["text"][:MAX_TEXT] if isinstance(out["text"], str) else ""

    media = []
    for it in n.get("media") or []:
        c = {"type": it["type"], "src": safe_url(it["src"])}
        if safe_url(it.get("poster")):
            c["poster"] = safe_url(it["poster"])
        for k in ("caption", "credit", "alt"):
            if _short(it.get(k)):
                c[k] = _short(it[k])
        media.append(c)
    if media:
        out["media"] = media
    else:
        out.pop("media", None)

    links = [{"label": _short(l.get("label")) or safe_url(l["url"]), "url": safe_url(l["url"])}
             for l in n.get("links") or []]
    if links:
        out["links"] = links
    else:
        out.pop("links", None)

    t = m.get("time")
    if isinstance(t, dict):
        tc = {k: _year(t.get(k)) for k in ("from", "to") if _year(t.get(k)) is not None}
        if _short(t.get("phase")):
            tc["phase"] = _short(t["phase"])
        if tc:
            out["time"] = tc
        else:
            out.pop("time", None)
    elif "time" in out:
        out.pop("time")

    if "provenance" in out and out["provenance"] not in PROVENANCE:
        out.pop("provenance")

    r = m.get("rights")
    if isinstance(r, dict):
        rc = {"consent": consent_of(m)}
        if _short(r.get("license")):
            rc["license"] = _short(r["license"])
        if rc["consent"] == "locked":
            y = _year(r.get("until"))
            if y is None:
                raise ValueError("Freigabe 'locked' braucht rights.until (Jahr)")
            rc["until"] = y
        out["rights"] = rc
    elif "rights" in out:
        out.pop("rights")

    out["attributes"] = m["attributes"] if isinstance(m.get("attributes"), dict) else {}
    out["demo"] = bool(m.get("demo", False))
    return out
