#!/usr/bin/env python3
"""seed_forestvr.py -- Forest-VR-Datensatz (Zenodo 7632474) als Suite-Szenen.

Datensatz: "Advancing Forest Monitoring and Assessment Through Immersive Virtual
Reality" (Zuercher, Zhao, Lau, Brede, Klippel; Wageningen University & Research,
2023). CC-BY-4.0, doi:10.5281/zenodo.7632474. Buchenbestand in der Eifel.

Er enthaelt BEIDE Datenarten derselben Flaeche -- 16 bodennahe 360-Grad-Panoramen
und terrestrische Punktwolken -- und ist damit thematisch genau der Fall, um den
es in dieser Arbeit geht. Zwei Einschraenkungen sind wichtig und werden in den
Szenenbeschreibungen benannt:

  * Die Panoramen tragen KEINE Pose. Sie laufen daher ueber den
    equirect-Eingang (uebernehmen), nicht ueber die Reprojektion.
  * Die LAS-Dateien sind EINZELBAEUME (rund 12 x 12 m Grundflaeche, 28 m hoch),
    keine Plot-Wolken -- erkennbar an der Ausdehnung und an den
    Autoren-Skripten ("#Tree1", "#Tree2").

Panorama und Punktwolke sind folglich NICHT ko-registriert; sie stammen von
derselben Flaeche, lassen sich aber ohne Pose nicht in eine gemeinsame begehbare
Szene legen. Genau diese Luecke schliesst der Scanner-RGB-Weg der Suite, wenn die
Pose im E57 mitgeliefert wird.

  python platform/dev/seed_forestvr.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media" / "scenes"
SRC = REPO / "data" / "forestvr"

DOI = "https://doi.org/10.5281/zenodo.7632474"
CITE = ("Zürcher, R., Zhao, J., Lau, A., Brede, B., Klippel, A. (2023): "
        "Advancing Forest Monitoring and Assessment Through Immersive Virtual "
        "Reality. Wageningen University & Research.")
LIC = "CC BY 4.0"
MAX_W = 4096


def write_bin(path, xyz, rgb):
    path.write_bytes(np.ascontiguousarray(xyz, "<f4").tobytes()
                     + np.ascontiguousarray(rgb, np.uint8).tobytes())


def seed_panorama():
    src = next(SRC.glob("B*_GS__*.JPG"), None)
    if not src:
        print("  kein Panorama gefunden -- uebersprungen")
        return None
    sid = "forestvr-eifel-pano"
    dest = MEDIA / sid
    dest.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        w, h = im.size
        if abs(w / h - 2.0) > 0.02:
            print(f"  {src.name}: kein 2:1-Panorama ({w}x{h}) -- uebersprungen")
            return None
        out = im.convert("RGB")
        if w > MAX_W:
            out = out.resize((MAX_W, MAX_W // 2), Image.LANCZOS)
        out.save(dest / "pano.jpg", quality=88)
        out.resize((640, 320), Image.LANCZOS).save(dest / "thumb.jpg", quality=85)
    scene = {
        "id": sid,
        "title": "Eifel-Buchenbestand — 360°-Aufnahme aus einer VR-Studie",
        "description": (
            "Bodennahes 360°-Panorama eines Buchenbestandes in der Eifel, "
            f"aufgenommen für die Studie „{CITE.split(':')[1].strip()}\". "
            "Belegt den equirektangularen Eingang der Kette mit einem realen "
            "Waldpanorama aus einer begutachteten Untersuchung. Die Aufnahme "
            "trägt KEINE Kamerapose und läuft daher über den Übernahme-Zweig, "
            "nicht über die Reprojektion — anders als die Scanner-RGB-Bilder, "
            "bei denen die Pose im E57 mitgeliefert wird."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": f"scenes/{sid}/pano.jpg", "thumb": f"scenes/{sid}/thumb.jpg",
        "width": min(w, MAX_W), "height": min(h, MAX_W // 2), "variants": [],
        "source": {"type": "forest-vr-360", "dataset": CITE, "url": DOI,
                   "license": LIC, "attribution": CITE},
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"  Szene '{sid}' ({min(w, MAX_W)}x{min(h, MAX_W//2)}) aus {src.name}")
    return sid


def seed_tree():
    las = sorted(SRC.glob("*.las"))
    if not las:
        print("  keine LAS-Datei gefunden -- uebersprungen")
        return None
    import laspy
    sid = "forestvr-eifel-tree"
    dest = MEDIA / sid
    dest.mkdir(parents=True, exist_ok=True)

    f = laspy.read(str(las[0]))
    xyz = np.c_[f.x, f.y, f.z].astype(np.float64)
    try:
        rgb = np.c_[f.red, f.green, f.blue].astype(np.float64)
        rgb = (rgb / max(rgb.max(), 1) * 255).astype(np.uint8)
    except Exception:
        rgb = None
    if rgb is None or rgb.max() == 0:
        # Ohne Farbe nach Hoehe einfaerben -- sonst ist die Wolke schwarz
        z = xyz[:, 2]
        t = (z - z.min()) / max(np.ptp(z), 1e-6)
        rgb = np.c_[80 + 120 * t, 90 + 130 * t, 70 + 60 * (1 - t)].astype(np.uint8)

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(),
                       np.percentile(xyz[:, 2], 1)])
    local = (xyz - origin).astype(np.float32)
    rng = np.random.default_rng(0)
    levels = []
    for lid, label, name, n in (("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
                                ("full", "Voll", "cloud.bin", 700_000)):
        sel = rng.choice(len(local), n, replace=False) if len(local) > n else np.arange(len(local))
        p, c = local[sel], rgb[sel]
        write_bin(dest / name, p, c)
        levels.append({"id": lid, "label": label, "bin": f"scenes/{sid}/{name}",
                       "count": int(len(p)),
                       "bbox_min": [float(v) for v in p.min(0)],
                       "bbox_max": [float(v) for v in p.max(0)]})
        if lid == "lite":
            W, H = 640, 480
            img = np.full((H, W, 3), 13, np.uint8)
            nx = ((p[:, 0] - p[:, 0].min()) / max(np.ptp(p[:, 0]), 1e-6) * (W - 1)).astype(int)
            ny = ((p[:, 2] - p[:, 2].min()) / max(np.ptp(p[:, 2]), 1e-6) * (H - 1)).astype(int)
            img[H - 1 - ny, nx] = c
            Image.fromarray(img).save(dest / "thumb.jpg", quality=85)

    hoehe = float(xyz[:, 2].max() - np.percentile(xyz[:, 2], 1))
    scene = {
        "id": sid,
        "title": f"Eifel-Buche — terrestrischer Scan eines Einzelbaums ({hoehe:.0f} m)",
        "description": (
            f"Terrestrische Punktwolke eines einzelnen Buchenstamms ({len(xyz):,} "
            f"Punkte, {hoehe:.1f} m hoch) aus demselben Bestand wie die "
            "360°-Aufnahme. Die Dateien des Datensatzes sind EINZELBÄUME, keine "
            "Plot-Wolken. Panorama und Punktwolke sind NICHT ko-registriert — "
            "sie stammen von derselben Fläche, lassen sich ohne Kamerapose aber "
            "nicht in eine gemeinsame begehbare Szene legen. Genau das leistet "
            "der Scanner-RGB-Weg dieser Suite, wenn die Pose im E57 mitkommt."
        ).replace(",", ",", 1),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{sid}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "forest-vr-tls", "dataset": CITE, "url": DOI,
                   "license": LIC, "attribution": CITE,
                   "origin_xyz": [float(c) for c in origin],
                   "hinweis": ("Einzelbaum-Wolke, kein Plot; Koordinaten lokal "
                               "(kein CRS in der LAS-Datei hinterlegt).")},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"  Szene '{sid}': {len(xyz):,} Punkte, Höhe {hoehe:.1f} m")
    return sid


def main():
    print(f"Forest-VR-Datensatz ({DOI})")
    ids = [s for s in (seed_panorama(), seed_tree()) if s]
    print(f"-> {len(ids)} Szenen gebaut: {', '.join(ids)}")


if __name__ == "__main__":
    main()
