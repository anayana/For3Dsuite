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
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from jobs import JobStore, start_worker
from pipeline import Pipeline
from storage import LocalStorage, make_stores

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = Path(os.environ.get("WEB_DIR", APP_DIR.parent / "web"))
DATA_DIR = Path(os.environ.get("DATA_DIR", APP_DIR.parent / "dev-data"))
SCRIPTS_DIR = Path(os.environ.get("SCRIPTS_DIR", APP_DIR.parents[1] / "scripts"))

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
JOB_TYPES = {"equirect", "fisheye", "e57"}

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
            "markers": len(s.get("markers", [])),
            "source_type": (s.get("source") or {}).get("type"),
            "has_3d": bool(s.get("pointcloud")),
        })
    out.sort(key=lambda s: s.get("created") or "", reverse=True)
    return out


@app.get("/api/scenes/{sid}")
def get_scene(sid: str):
    scene = load_scene(sid)
    scene["pano_url"] = media.url(scene["pano"])
    scene["thumb_url"] = media.url(scene["thumb"]) if scene.get("thumb") else None
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
                 job_type: str = Form(..., alias="type"),
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


@app.put("/api/studio/scenes/{sid}/markers")
async def put_markers(sid: str, request: Request):
    body = await request.json()
    markers = body.get("markers")
    if not isinstance(markers, list):
        raise HTTPException(400, "Body muss {\"markers\": [...]} sein")
    clean = []
    for m in markers:
        try:
            clean.append({
                "id": str(m.get("id") or f"m{len(clean) + 1}"),
                "label": str(m.get("label") or ""),
                "yaw": round(float(m["yaw"]), 3),
                "pitch": round(float(m["pitch"]), 3),
                "xyz": m.get("xyz"),
                "attributes": m.get("attributes") if isinstance(m.get("attributes"), dict) else {},
                "demo": bool(m.get("demo", False)),
            })
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, f"Ungueltiger Marker (yaw/pitch noetig): {m}")
    scene = load_scene(sid)
    scene["markers"] = clean
    save_scene(scene)
    return {"ok": True, "count": len(clean)}


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
