"""360Pano3D Platform — API + statische UIs.

Betriebsarten (STORAGE-Umgebungsvariable):
  local  Dev auf dem Arbeitsrechner: Medien liegen unter platform/dev-data/,
         /media/* wird von der App selbst bedient. Start:
           python -m uvicorn main:app --port 8360 --app-dir platform/app
  s3     Produktion im Docker-Stack: Medien liegen in Garage, Caddy bedient
         /media/* direkt und schuetzt /admin + /api/studio per Basic-Auth.
"""
import base64
import json
import os
import re
import secrets
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from jobs import JobStore, start_worker
from marker_schema import clean_marker, public_markers
from pipeline import Pipeline
from storage import LocalStorage, make_stores

APP_DIR = Path(__file__).resolve().parent


def _dir(env, *fallbacks):
    """Verzeichnis aus der Umgebung, sonst der erste brauchbare Rueckfall.

    Wichtig: os.environ.get(name, default) wertet 'default' IMMER aus, auch wenn
    die Variable gesetzt ist. Der frühere Ausdruck APP_DIR.parents[1] / "scripts"
    warf deshalb im Container IndexError, obwohl der Dockerfile SCRIPTS_DIR
    korrekt setzt -- im Repo liegt die App zwei Ebenen unter der Wurzel, im Image
    direkt in /app. Die App kam so nie hoch.
    """
    v = os.environ.get(env)
    if v:
        return Path(v)
    for f in fallbacks:
        try:
            p = f()
        except (IndexError, OSError):
            continue
        if p.exists():
            return p
    return Path(fallbacks[0]()) if fallbacks else APP_DIR


WEB_DIR = _dir("WEB_DIR", lambda: APP_DIR.parent / "web", lambda: APP_DIR / "web")
DATA_DIR = _dir("DATA_DIR", lambda: APP_DIR.parent / "dev-data", lambda: Path("/data"))
SCRIPTS_DIR = _dir("SCRIPTS_DIR", lambda: APP_DIR.parents[1] / "scripts",
                   lambda: APP_DIR / "scripts")

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
JOB_TYPES = {"auto", "equirect", "fisheye", "e57"}

media, originals = make_stores(DATA_DIR)
jobstore = JobStore(DATA_DIR / "jobs.db")
pipeline = Pipeline(media, originals, SCRIPTS_DIR, DATA_DIR / "work")

app = FastAPI(title="360Pano3D Platform")


@app.on_event("startup")
def _startup():
    start_worker(jobstore, pipeline.run)


# ---------- Optionaler App-seitiger Studio-Schutz (Dev / Betrieb ohne Caddy) ----------

STUDIO_USER = os.environ.get("STUDIO_USER", "admin")
STUDIO_PASSWORD = os.environ.get("STUDIO_PASSWORD")


@app.middleware("http")
async def studio_auth(request: Request, call_next):
    path = request.url.path
    if STUDIO_PASSWORD and (path.startswith("/admin") or path.startswith("/api/studio")):
        ok = False
        auth = request.headers.get("authorization", "")
        if auth.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
                ok = (secrets.compare_digest(user, STUDIO_USER)
                      and secrets.compare_digest(pw, STUDIO_PASSWORD))
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="studio"'})
    return await call_next(request)


# ---------- Oeffentliche API ----------

def load_scene(sid):
    raw = media.get_bytes(f"scenes/{sid}/scene.json")
    if raw is None:
        raise HTTPException(404, f"Szene '{sid}' nicht gefunden")
    return json.loads(raw)


def save_scene(scene):
    media.put_bytes(f"scenes/{scene['id']}/scene.json",
                    json.dumps(scene, ensure_ascii=False, indent=2).encode())


@app.get("/api/health")
def health():
    return {"ok": True, "storage": os.environ.get("STORAGE", "local")}


@app.get("/api/scenes")
def list_scenes():
    out = []
    for key in media.list("scenes/"):
        if not key.endswith("/scene.json"):
            continue
        try:
            s = json.loads(media.get_bytes(key))
        except (TypeError, ValueError):
            continue
        out.append({
            "id": s.get("id"),
            "title": s.get("title"),
            "description": s.get("description", ""),
            "created": s.get("created"),
            "thumb_url": media.url(s["thumb"]) if s.get("thumb") else None,
            "markers": len(public_markers(s.get("markers"), date.today().year)),
            "markers_total": len(s.get("markers") or []),
            "source_type": (s.get("source") or {}).get("type"),
            "has_3d": bool(s.get("pointcloud")) or s.get("kind") == "tour",
            "kind": s.get("kind") or ("walk" if s.get("video") else "scene"),
        })
    out.sort(key=lambda s: s.get("created") or "", reverse=True)
    return out


@app.get("/api/scenes/{sid}")
def get_scene(sid: str):
    """Oeffentliche Szene: nur Marker mit Freigabe 'public' (bzw. abgelaufener Sperre)."""
    scene = with_urls(load_scene(sid))
    if "markers" in scene:
        scene["markers"] = public_markers(scene["markers"], date.today().year)
    return scene


def with_urls(scene):
    scene["pano_url"] = media.url(scene["pano"]) if scene.get("pano") else None
    scene["thumb_url"] = media.url(scene["thumb"]) if scene.get("thumb") else None
    if scene.get("video"):
        scene["video_url"] = media.url(scene["video"])
    for v in scene.get("variants") or []:
        if v.get("pano"):
            v["pano_url"] = media.url(v["pano"])
    pc = scene.get("pointcloud")
    if pc and pc.get("bin"):
        pc["bin_url"] = media.url(pc["bin"])
        for lv in pc.get("levels") or []:
            if lv.get("bin"):
                lv["bin_url"] = media.url(lv["bin"])
    return scene


# ---------- Studio-API (in Produktion hinter Caddy-Basic-Auth) ----------

@app.post("/api/studio/upload")
async def upload(scene_id: str = Form(...),
                 title: str = Form(""),
                 description: str = Form(""),
                 job_type: str = Form("auto", alias="type"),
                 fov: float = Form(180.0),
                 lens: int = Form(3),
                 files: list[UploadFile] = File(...)):
    if not SLUG.match(scene_id):
        raise HTTPException(400, "scene_id: nur a-z, 0-9, - und _ (max. 64 Zeichen)")
    if job_type not in JOB_TYPES:
        raise HTTPException(400, f"type muss eines von {sorted(JOB_TYPES)} sein")
    saved = []
    for f in files:
        name = Path(f.filename or "upload.bin").name
        originals.put_bytes(f"{scene_id}/{name}", await f.read())
        saved.append(name)
    job = jobstore.create(scene_id, job_type, {
        "title": title, "description": description,
        "fov": fov, "lens": lens, "files": saved,
    })
    return {"job": job}


@app.get("/api/studio/jobs")
def jobs_list():
    return jobstore.list()


@app.get("/api/studio/jobs/{jid}")
def jobs_get(jid: str):
    job = jobstore.get(jid)
    if job is None:
        raise HTTPException(404, "Job nicht gefunden")
    return job


@app.get("/api/studio/scenes/{sid}")
def studio_get_scene(sid: str):
    """Szene fuer den Editor: ALLE Marker, auch nicht freigegebene."""
    return with_urls(load_scene(sid))


@app.put("/api/studio/scenes/{sid}/markers")
async def put_markers(sid: str, request: Request):
    """Marker speichern (einheitliches Schema, marker_schema.clean_marker).

    Nimmt Titel, Text, Medien, Links, Zeit, Herkunft und Freigabe an; Felder
    ausserhalb des Schemas (kind, facts, prognosis ...) bleiben erhalten.
    """
    body = await request.json()
    markers = body.get("markers")
    if not isinstance(markers, list):
        raise HTTPException(400, "Body muss {\"markers\": [...]} sein")
    clean = []
    for i, m in enumerate(markers):
        try:
            clean.append(clean_marker(m, i))
        except (TypeError, ValueError) as e:
            raise HTTPException(400, f"Ungueltiger Marker #{i + 1}: {e}")
    ids = [m["id"] for m in clean]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Marker-IDs muessen eindeutig sein")
    scene = load_scene(sid)
    scene["markers"] = clean
    save_scene(scene)
    return {"ok": True, "count": len(clean)}


MEDIA_EXT = {".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
             ".mp4": "video", ".webm": "video",
             ".mp3": "audio", ".m4a": "audio", ".ogg": "audio", ".wav": "audio"}
MAX_MEDIA_MB = int(os.environ.get("MAX_MEDIA_MB", "300"))


@app.post("/api/studio/scenes/{sid}/media")
async def upload_media(sid: str, file: UploadFile = File(...)):
    """Medium (Bild, Video, Ton) fuer Marker hochladen -> scenes/<sid>/story/.

    Antwort: {"type", "src"}; src ist relativ wie bei den bestehenden
    Story-Medien und funktioniert in der App wie im statischen Export.
    """
    if not SLUG.match(sid):
        raise HTTPException(400, "Ungueltige scene_id")
    load_scene(sid)  # 404 falls unbekannt
    ext = Path(file.filename or "").suffix.lower()
    if ext not in MEDIA_EXT:
        raise HTTPException(400, f"Dateityp nicht erlaubt; erlaubt: {', '.join(sorted(MEDIA_EXT))}")
    data = await file.read()
    if len(data) > MAX_MEDIA_MB * 1024 * 1024:
        raise HTTPException(413, f"Datei groesser als {MAX_MEDIA_MB} MB")
    stem = re.sub(r"[^a-z0-9_-]+", "-", Path(file.filename).stem.lower()).strip("-")[:40] or "medium"
    name = f"{stem}-{secrets.token_hex(3)}{ext}"
    key = f"scenes/{sid}/story/{name}"
    media.put_bytes(key, data)
    return {"type": MEDIA_EXT[ext], "src": "media/" + key, "url": media.url(key)}


@app.patch("/api/studio/scenes/{sid}")
async def patch_scene(sid: str, request: Request):
    body = await request.json()
    scene = load_scene(sid)
    for field in ("title", "description"):
        if field in body:
            scene[field] = str(body[field])
    save_scene(scene)
    return {"ok": True}


@app.delete("/api/studio/scenes/{sid}")
def delete_scene(sid: str):
    if not SLUG.match(sid):
        raise HTTPException(400, "Ungueltige scene_id")
    load_scene(sid)  # 404 falls unbekannt
    media.delete_prefix(f"scenes/{sid}/")
    return {"ok": True}


# ---------- Statische Auslieferung (nach den API-Routen registriert) ----------

if isinstance(media, LocalStorage):
    app.mount("/media", StaticFiles(directory=media.root), name="media")
app.mount("/admin", StaticFiles(directory=WEB_DIR / "studio", html=True), name="studio")
app.mount("/", StaticFiles(directory=WEB_DIR / "gallery", html=True), name="gallery")
