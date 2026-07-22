#!/usr/bin/env python3
"""seed_hvi_ahn.py -- Hecken aus offenem ALS (AHN) als HVI-Szene.

Quelle: AHN (Actueel Hoogtebestand Nederland), offene ALS-Punktwolke, ~21 Pkt/m2,
CC-BY-4.0. Der Hedge Vertical Index (HVI, Repo shrub_div) beschreibt die
vertikale Struktur einer Hecke aus dem LiDAR-Profil: FHD, VCI, Schichtzahl und
-Evenness, Deckung, Kronenrauigkeit.

Ablauf: hvi_ahn_scene.R rechnet den Index und legt die hoehennormalisierten
Punkte mit UserData = hedge_id ab; dieses Skript faerbt und paketiert daraus die
Web-Szene. Heckenpunkte tragen die HVI-Farbe ihres Segments, alles uebrige
(Boden, Einzelbaeume, Gebaeude) bleibt gedaempft -- der Index wird damit im Raum
selbst sichtbar, nicht nur in der Tabelle.

  python platform/dev/seed_hvi_ahn.py                     # rechnet und baut
  python platform/dev/seed_hvi_ahn.py --skip-r            # nur neu paketieren
"""
import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
SHRUB = Path(r"C:/Users/A/Desktop/R/shrub_div")
WORK = REPO / "data" / "hvi_ahn"
SID = "hvi-ahn-hedges"

# Ausschnitt aus der Kachel: 1000 x 1000 m, aus dem Grobscan als heckenreich und
# waldfrei ausgewaehlt (RD New / EPSG:28992).
AOI = (255000, 494500, 256000, 495500)
TILE = SHRUB / "testdata" / "C_28FN2.LAZ"

LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]

# Sequenzieller Verlauf fuer den HVI (niedrig -> hoch): blass-sandig zu
# tiefgruen. Bewusst einfarbig-sequenziell, weil der Index eine Rangfolge ist.
HVI_RAMP = np.array([[222, 214, 176], [190, 205, 140], [140, 190, 110],
                     [ 84, 165, 100], [ 40, 130,  95], [ 20,  92,  80]], np.float32)


def rd_to_wgs84(x, y):
    """RD New (EPSG:28992) -> WGS84, Naeherung nach Schreutelkamp/Strang van Hees.

    Genauigkeit im Meterbereich -- fuer den Kartenpin der Galerie reicht das,
    fuer Geometrie wird es nicht verwendet (pyproj ist hier nicht installiert).
    """
    dx, dy = (x - 155000) * 1e-5, (y - 463000) * 1e-5
    lat = (52.15517440
           + (3235.65389 * dy - 32.58297 * dx**2 - 0.24750 * dy**2
              - 0.84978 * dx**2 * dy - 0.06550 * dy**3 - 0.01709 * dx**2 * dy**2
              - 0.00738 * dx + 0.00530 * dx**4 - 0.00039 * dx**2 * dy**3
              + 0.00033 * dx**4 * dy - 0.00012 * dx * dy) / 3600)
    lon = (5.38720621
           + (5260.52916 * dx + 105.94684 * dx * dy + 2.45656 * dx * dy**2
              - 0.81885 * dx**3 + 0.05594 * dx * dy**3 - 0.05607 * dx**3 * dy
              + 0.01199 * dy + 0.00256 * dx**3 * dy**2 + 0.00128 * dx * dy**4
              + 0.00022 * dy**2 - 0.00022 * dx**2 * dy + 0.00026 * dx**5) / 3600)
    return {"lat": round(lat, 6), "lon": round(lon, 6)}


def ramp(t):
    """t in [0,1] -> RGB nach HVI_RAMP (linear interpoliert)."""
    t = np.clip(np.asarray(t, np.float32), 0, 1)
    pos = np.linspace(0, 1, len(HVI_RAMP))
    return np.stack([np.interp(t, pos, HVI_RAMP[:, k]) for k in range(3)], -1)


def run_r():
    rscript = next((str(p) for p in Path(r"C:/Program Files/R").glob("R-*/bin/Rscript.exe")),
                   "Rscript")
    WORK.mkdir(parents=True, exist_ok=True)
    cmd = [rscript, str(Path(__file__).with_name("hvi_ahn_scene.R")), str(TILE),
           *[str(v) for v in AOI], str(WORK), str(SHRUB)]
    print("$", " ".join(Path(c).name if c.endswith(('.R', '.LAZ')) else c for c in cmd))
    subprocess.run(cmd, check=True, cwd=SHRUB)


def thumbnail(dest, xy, rgb):
    """Draufsicht -- zeigt das Heckennetz im Feldmuster."""
    W, H = 640, 640
    img = np.full((H, W, 3), 13, np.uint8)
    x, y = xy[:, 0], xy[:, 1]
    nx = ((x - x.min()) / max(np.ptp(x), 1e-6) * (W - 1)).astype(int)
    ny = ((y - y.min()) / max(np.ptp(y), 1e-6) * (H - 1)).astype(int)
    img[H - 1 - ny, nx] = rgb
    Image.fromarray(img).save(dest, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-r", action="store_true",
                    help="R-Auswertung ueberspringen, nur neu paketieren")
    args = ap.parse_args()

    if not args.skip_r:
        run_r()

    res = json.loads((WORK / "hvi_result.json").read_text(encoding="utf-8"))
    segs = res["segmentliste"]
    print(f"{len(segs)} Heckensegmente")

    import laspy
    las = laspy.read(str(WORK / "aoi_norm.las"))
    xyz = np.c_[las.x, las.y, las.z].astype(np.float64)
    hid = np.asarray(las.point_source_id, np.int32)

    # HVI je Segment nachschlagen; Punkte ohne Hecke bekommen -1
    nmax = max(int(s["hedge_id"]) for s in segs) + 1
    hvi_of = np.full(nmax, np.nan, np.float32)
    for s in segs:
        hvi_of[int(s["hedge_id"])] = float(s["HVI"])
    hvi_pt = hvi_of[np.clip(hid, 0, nmax - 1)]
    in_hedge = np.isfinite(hvi_pt) & (hid > 0)

    lo = min(float(s["HVI"]) for s in segs)
    hi = max(float(s["HVI"]) for s in segs)
    rgb = np.empty((len(xyz), 3), np.float32)
    # Hecke: Farbe = HVI-Rang. Rest: gedaempft ueber die Hoehe, damit Relief und
    # Einzelbaeume als Kontext lesbar bleiben, ohne vom Index abzulenken.
    rgb[in_hedge] = ramp((hvi_pt[in_hedge] - lo) / max(hi - lo, 1e-6))
    zt = np.clip(xyz[~in_hedge, 2] / 12.0, 0, 1)[:, None]
    rgb[~in_hedge] = np.array([56, 58, 62], np.float32) + zt * np.array([44, 46, 40], np.float32)

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(), 0.0])
    local = (xyz - origin).astype(np.float32)

    dest = MEDIA / "scenes" / SID
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        # Heckenpunkte bevorzugt behalten -- sie sind das Motiv, der Rest Kulisse
        idx_h = np.flatnonzero(in_hedge)
        idx_o = np.flatnonzero(~in_hedge)
        n_h = min(len(idx_h), int(maxpts * 0.7))
        n_o = min(len(idx_o), maxpts - n_h)
        sel = np.concatenate([rng.choice(idx_h, n_h, replace=False),
                              rng.choice(idx_o, n_o, replace=False)])
        p, c = local[sel], np.clip(rgb[sel], 0, 255).astype(np.uint8)
        (dest / fname).write_bytes(np.ascontiguousarray(p, "<f4").tobytes() + c.tobytes())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{SID}/{fname}",
                       "count": int(len(p)),
                       "bbox_min": [float(v) for v in p.min(0)],
                       "bbox_max": [float(v) for v in p.max(0)]})
        print(f"  {label}: {len(p):,} Punkte ({n_h:,} Hecke)")
        if lid == "lite":
            thumbnail(dest / "thumb.jpg", p[:, :2], c)

    # ---- Marker je Segment -------------------------------------------------
    zeig = ["HVI", "vertical_complexity", "volume_size", "heterogeneity",
            "fhd", "vci", "n_layers", "strata_evenness", "h_p95", "h_max",
            "cover_frac", "canopy_sd", "understory_openness", "vertical_gap"]
    markers = []
    for i, s in enumerate(sorted(segs, key=lambda d: -float(d["HVI"])), 1):
        x, y = float(s["x"]), float(s["y"])
        top = float(s.get("h_p95") or 3.0)
        dx, dy, dz = x - origin[0], y - origin[1], top
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        attrs = {"Flaeche_m2": round(float(s.get("flaeche_m2") or 0), 1)}
        for k in zeig:
            v = s.get(k)
            if v is not None and isinstance(v, (int, float)) and math.isfinite(v):
                attrs[k] = round(float(v), 3)
        if s.get("hedge_type") is not None:
            attrs["Habitattyp"] = f"Cluster {int(s['hedge_type'])}"
        for k, v in s.items():                       # Arteignungen (HSI_*)
            if k.startswith("HSI") and isinstance(v, (int, float)):
                attrs[k] = round(float(v), 3)
        markers.append({
            "id": f"h{i:03d}", "label": f"Segment {int(s['hedge_id'])} · HVI {float(s['HVI']):.2f}",
            "yaw": round(math.degrees(math.atan2(dy, dx)), 3),
            "pitch": round(math.degrees(math.asin(dz / dist)), 3),
            "xyz": [round(dx, 3), round(dy, 3), round(top, 3)],
            "attributes": attrs, "demo": False})

    cx = (AOI[0] + AOI[2]) / 2
    cy = (AOI[1] + AOI[3]) / 2
    hvis = [float(s["HVI"]) for s in segs]
    scene = {
        "id": SID,
        "title": "Heckennetz Niederlande — Hedge Vertical Index (ALS)",
        "description": (
            f"Offene ALS-Punktwolke (AHN, ~21 Pkt/m2) eines 1 x 1 km grossen "
            f"Feldausschnitts. {len(segs)} Heckensegmente, eingefaerbt nach dem "
            f"Hedge Vertical Index (HVI {min(hvis):.2f}-{max(hvis):.2f}): einem "
            f"zusammengesetzten Strukturindex aus vertikaler Komplexitaet (FHD, "
            f"VCI, Schichtzahl und -Evenness, Gewicht 0,50), Volumen/Groesse "
            f"(0,15) und Heterogenitaet (0,25). Boden und Umfeld bleiben "
            f"gedaempft als Kulisse. Marker tragen alle Kennwerte je Segment. "
            f"{res['limits']} Ein Kennwert traegt hier nichts bei: cover_frac "
            f"ist in allen {len(segs)} Segmenten exakt 1,00, weil die Segmente "
            f"AUS der Vegetationsmaske abgeleitet sind und die Deckung darin "
            f"zwangslaeufig vollstaendig ist -- der Subindex Volumen/Groesse "
            f"schrumpft damit faktisch auf die Hoehe. Mit kartierten "
            f"Heckenpolygonen (z. B. UKCEH fuer England) wuerde cover_frac "
            f"Luecken in der Heckenlinie messen und wieder Information tragen. "
            f"Quelle: AHN, CC-BY-4.0; Index: shrub_div/HVI."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{SID}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "hvi-als", "origin_xyz": [float(v) for v in origin],
                   "dataset": "AHN (Actueel Hoogtebestand Nederland)",
                   "url": "https://www.ahn.nl/", "license": "CC-BY-4.0",
                   "gps": rd_to_wgs84(cx, cy)},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": markers,
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"-> Szene '{SID}': {len(markers)} Segmente, "
          f"HVI {min(hvis):.2f}-{max(hvis):.2f}, GPS {scene['source']['gps']}")


if __name__ == "__main__":
    main()
