"""Verarbeitungs-Pipeline: Originale -> Equirectangular-Panorama -> veroeffentlichte Szene.

Drei Job-Typen:
  equirect  fertiges Equirectangular-Bild direkt uebernehmen
  fisheye   Hugin-CLI-Kette (pto_gen -> cpfind -> ... -> nona -> enblend)
  e57       eingebettete Pinhole-Bilder + Posen extrahieren und ohne
            Kontrollpunkte sphaerisch reprojizieren (scripts/reproject_pano.py)
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MAX_CANVAS = 40000  # Schutz gegen Gigapixel-Rendering bei falschem FOV/LensType


class Pipeline:
    def __init__(self, media, originals, scripts_dir, work_root):
        self.media = media
        self.originals = originals
        self.scripts = Path(scripts_dir)
        self.work_root = Path(work_root)

    # ---------- Haupteinstieg (laeuft im Worker-Thread) ----------

    def run(self, job, log):
        sid = job["scene_id"]
        params = job["params"]
        work = self.work_root / job["id"]
        indir = work / "input"
        indir.mkdir(parents=True, exist_ok=True)
        try:
            for name in params.get("files", []):
                data = self.originals.get_bytes(f"{sid}/{name}")
                if data is None:
                    raise RuntimeError(f"Original nicht gefunden: {sid}/{name}")
                (indir / name).write_bytes(data)
            log(f"{len(params.get('files', []))} Original(e) aus dem Storage geladen")

            pano = work / "pano_equirect.jpg"
            origin = None
            pointcloud = None
            if job["type"] == "equirect":
                self._equirect(indir, pano, log)
            elif job["type"] == "fisheye":
                self._fisheye(indir, work, pano, params, log)
            elif job["type"] == "e57":
                origin = self._e57(indir, work, pano, log)
                pointcloud = self._pointcloud(indir, work, sid, origin, log)
            else:
                raise RuntimeError(f"Unbekannter Job-Typ: {job['type']}")

            self._publish(sid, job["type"], pano, origin, pointcloud, params, log)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    # ---------- Job-Typen ----------

    def _equirect(self, indir, pano, log):
        imgs = sorted(p for p in indir.iterdir() if p.suffix.lower() in IMG_EXT)
        if not imgs:
            raise RuntimeError("Kein Bild im Upload gefunden")
        with Image.open(imgs[0]) as im:
            im.convert("RGB").save(pano, quality=92)
        log(f"Equirectangular uebernommen: {imgs[0].name}")

    def _fisheye(self, indir, work, pano, params, log):
        imgs = sorted(p for p in indir.iterdir() if p.suffix.lower() in IMG_EXT)
        if len(imgs) < 2:
            raise RuntimeError(f"Zu wenige Bilder fuer Stitching ({len(imgs)}, mind. 2)")
        lens = int(params.get("lens", 3))
        fov = float(params.get("fov", 180))
        log(f"Hugin-Stitching: {len(imgs)} Bilder, LensType={lens}, FOV={fov}")

        self._run([self._tool("pto_gen"), "-p", lens, "-f", fov,
                   "-o", "project.pto"] + [str(p) for p in imgs], work, log)
        self._run([self._tool("cpfind"), "--multirow", "-o", "project_cp.pto",
                   "project.pto"], work, log)
        self._run([self._tool("cpclean"), "-o", "project_clean.pto",
                   "project_cp.pto"], work, log)
        self._run([self._tool("linefind"), "-o", "project_lines.pto",
                   "project_clean.pto"], work, log)
        self._run([self._tool("autooptimiser"), "-a", "-m", "-l", "-s",
                   "-o", "project_opt.pto", "project_lines.pto"], work, log)
        self._run([self._tool("pano_modify"), "--projection=2", "--fov=360x180",
                   "--canvas=AUTO", "--crop=AUTO", "-o", "project_final.pto",
                   "project_opt.pto"], work, log)

        pto = (work / "project_final.pto").read_text(errors="replace")
        m = re.search(r"^p .*?w(\d+)\s+h(\d+)", pto, re.M)
        if m and int(m.group(1)) > MAX_CANVAS:
            raise RuntimeError(
                f"Canvas {m.group(1)}x{m.group(2)} unplausibel gross — "
                f"LensType/FOV pruefen (aktuell {lens}/{fov})")

        self._run([self._tool("nona"), "-m", "TIFF_m", "-o", "stitched",
                   "project_final.pto"], work, log)
        tifs = sorted(work.glob("stitched*.tif"))
        if not tifs:
            raise RuntimeError("nona hat keine remappten Bilder erzeugt")
        self._run([self._tool("enblend"), "-o", str(pano)] +
                  [str(t) for t in tifs], work, log)

    def _e57(self, indir, work, pano, log):
        e57s = sorted(indir.glob("*.e57"))
        if not e57s:
            raise RuntimeError("Keine .e57-Datei im Upload gefunden")
        extract = work / "extracted"
        self._run([sys.executable, str(self.scripts / "e57_extract_images.py"),
                   str(e57s[0]), str(extract)], work, log)
        poses = sorted(extract.glob("*_poses.json"))
        if not poses:
            raise RuntimeError("Extraktion lieferte keine poses.json")
        self._run([sys.executable, str(self.scripts / "reproject_pano.py"),
                   str(poses[0]), str(extract), str(pano),
                   "--w", "8192", "--sx", "1", "--sy", "-1"], work, log)

        entries = json.loads(poses[0].read_text())
        for e in entries:
            t = (e.get("pose") or {}).get("translation_xyz")
            if e.get("representation") == "pinholeRepresentation" and t:
                log(f"Scan-Ursprung (Kamera-Translation): {t}")
                return t
        return None

    def _pointcloud(self, indir, work, sid, origin, log):
        """Kompakte Web-Punktwolke erzeugen (best effort; ohne pye57 uebersprungen)."""
        e57s = sorted(indir.glob("*.e57"))
        if not e57s:
            return None
        script = self.scripts / "pointcloud_web.py"
        if not script.exists():
            return None
        out = work / "cloud.bin"
        cmd = [sys.executable, str(script), str(e57s[0]), str(out),
               "--radius", "25", "--max-points", "700000", "--voxel", "0.04"]
        if origin:
            cmd += ["--origin", *[str(c) for c in origin]]
        try:
            self._run(cmd, work, log)
        except RuntimeError as e:
            log(f"Punktwolke uebersprungen ({e})")
            return None
        meta = json.loads(out.with_suffix(".json").read_text())
        self.media.put_file(out, f"scenes/{sid}/cloud.bin")
        return {"bin": f"scenes/{sid}/cloud.bin", "count": meta["count"],
                "stride": meta["stride"], "bbox_min": meta["bbox_min"],
                "bbox_max": meta["bbox_max"]}

    # ---------- Veroeffentlichen ----------

    def _publish(self, sid, jtype, pano, origin, pointcloud, params, log):
        prev = self.media.get_bytes(f"scenes/{sid}/scene.json")
        markers = json.loads(prev).get("markers", []) if prev else []

        thumb = pano.with_name("thumb.jpg")
        with Image.open(pano) as im:
            width, height = im.size
            im.convert("RGB").resize((640, 320), Image.LANCZOS).save(thumb, quality=85)

        self.media.put_file(pano, f"scenes/{sid}/pano.jpg")
        self.media.put_file(thumb, f"scenes/{sid}/thumb.jpg")

        scene = {
            "id": sid,
            "title": params.get("title") or sid,
            "description": params.get("description", ""),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pano": f"scenes/{sid}/pano.jpg",
            "thumb": f"scenes/{sid}/thumb.jpg",
            "width": width,
            "height": height,
            "source": {"type": jtype, "origin_xyz": origin},
            "pointcloud": pointcloud,
            "markers": markers,
        }
        self.media.put_bytes(f"scenes/{sid}/scene.json",
                             json.dumps(scene, ensure_ascii=False, indent=2).encode())
        log(f"Szene veroeffentlicht: scenes/{sid}/scene.json ({width}x{height}, "
            f"{len(markers)} Marker uebernommen)")

    # ---------- Hilfen ----------

    @staticmethod
    def _tool(name):
        exe = name + (".exe" if os.name == "nt" else "")
        for base in (os.environ.get("HUGIN_BIN"), r"C:\Program Files\Hugin\bin"):
            if base and (Path(base) / exe).exists():
                return str(Path(base) / exe)
        return name

    @staticmethod
    def _run(args, cwd, log):
        args = [str(a) for a in args]
        log("$ " + " ".join(args))
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                           errors="replace")
        tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-8:]
        for line in tail:
            log("  " + line)
        if r.returncode != 0:
            raise RuntimeError(f"{Path(args[0]).name} endete mit Code {r.returncode}")
