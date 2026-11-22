"""Schlichter Web-Assistent (FastAPI): Dateien hochladen, Profil waehlen, rechnen, Bericht ansehen.

Laeuft lokal beim Nutzer - Daten verlassen den Rechner nicht.
"""
from __future__ import annotations

import shutil
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from ..profiles import list_profiles, load_profile
from ..project import make_project, save_project

HERE = Path(__file__).parent


def create_app(workdir="bioscale_web") -> FastAPI:
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="BioScale")
    jobs: dict[str, dict] = {}

    def _run(job_id, proj):
        from ..pipeline import run
        try:
            res = run(proj, echo=False)
            jobs[job_id].update(status="fertig", report=res["report"], ampel=res["ampel"])
        except Exception as e:  # Fehler verstaendlich zurueckgeben
            jobs[job_id].update(status="fehler", error=str(e), trace=traceback.format_exc()[-2000:])

    def _start(job_id, proj):
        jobs[job_id] = {"status": "laeuft"}
        t = threading.Thread(target=_run, args=(job_id, proj), daemon=True)
        t.start()
        return t

    @app.get("/", response_class=HTMLResponse)
    def index():
        html = (HERE / "index.html").read_text(encoding="utf-8")
        opts = "\n".join(f'<option value="{p}">{load_profile(p)["label"]}</option>' for p in list_profiles()
                         if p != "demo_virtuelle_art")
        return html.replace("{{PROFILE_OPTIONS}}", opts)

    @app.get("/api/profiles")
    def profiles():
        return [{**{k: v for k, v in load_profile(p).items() if k in ("name", "label", "radius_m", "status", "hints")}}
                for p in list_profiles()]

    @app.post("/api/demo")
    def demo():
        from ..synthetic import write_demo_project
        job_id = uuid.uuid4().hex[:10]
        proj = write_demo_project(work / job_id)
        app.state.last_thread = _start(job_id, proj)
        return {"job": job_id}

    @app.post("/api/run")
    async def run_job(area: UploadFile = File(...), points: UploadFile = File(...), species: str = Form(""),
                      profile: str = Form(...), fmt: str = Form("dwc"), resolution_m: float = Form(20),
                      crs: str = Form("EPSG:25832"), start: str = Form(""), end: str = Form(""),
                      sentinel2: bool = Form(False), dem: bool = Form(False), worldcover: bool = Form(False),
                      rasters: list[UploadFile] | None = File(None), raster_group: str = Form("structure")):
        job_id = uuid.uuid4().hex[:10]
        d = work / job_id
        d.mkdir(parents=True)

        def save(u: UploadFile):
            name = Path(u.filename or "datei").name
            with open(d / name, "wb") as f:
                shutil.copyfileobj(u.file, f)
            return name

        a, p = save(area), save(points)
        rl = [{"path": save(r), "name": Path(r.filename).stem, "group": raster_group} for r in (rasters or []) if r.filename]
        cfg = make_project(a, p, species, profile, fmt=fmt, resolution_m=resolution_m, crs=crs, start=start or None,
                           end=end or None, rasters=rl, open_data={"sentinel2": sentinel2, "dem": dem, "worldcover": worldcover})
        proj = save_project(cfg, d / "projekt.yml")
        try:
            from ..project import load_project
            load_project(proj)
        except ValueError as e:
            raise HTTPException(400, str(e))
        app.state.last_thread = _start(job_id, proj)
        return {"job": job_id}

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str):
        if job_id not in jobs:
            raise HTTPException(404, "Auftrag unbekannt")
        j = {k: v for k, v in jobs[job_id].items() if k != "report"}
        if jobs[job_id].get("report"):
            j["report_url"] = f"/jobs/{job_id}/bericht"
        return JSONResponse(j)

    @app.get("/jobs/{job_id}/bericht", response_class=HTMLResponse)
    def report(job_id: str):
        j = jobs.get(job_id)
        if not j or not j.get("report"):
            raise HTTPException(404, "Noch kein Bericht")
        return FileResponse(j["report"], media_type="text/html")

    return app
