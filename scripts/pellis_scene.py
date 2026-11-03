#!/usr/bin/env python3
"""pellis_scene.py -- schlanke Pellis-Splat-.ply (clean_splat.py --sh0) als Szene fuer die For3Dsuite-Galerie.

Schreibt in <out>/: scene.json (docs/data/scene-pellis-<b>.json), entry.json (Eintrag fuer
docs/data/scenes.json) und thumb.jpg (Draufsicht der Splat-Zentren). Die .ply liegt schon in <out>/.

  python scripts/pellis_scene.py <out>/<b>.ply 5_CB <out>
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_splat import read_ply, write_ply  # noqa: E402

NAMES = {"1_SC": "SC", "2_OSA": "OSA", "3_SS": "SS", "4_CG": "CG", "5_CB": "CB"}


def main():
    ply, b, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    arr, names = read_ply(ply)
    arr = arr.copy()
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1).astype(float)
    # Viewer (GaussianSplats3D) zeigt bei Koordinaten > ~100 m nichts an -> um den Kern verschieben
    op0 = 1 / (1 + np.exp(-arr["opacity"].astype(float)))
    off = np.round(np.median(xyz[op0 > 0.5] if (op0 > 0.5).sum() > 1000 else xyz, 0), 1)
    for i, k in enumerate("xyz"):
        arr[k] = arr[k] - off[i]
    write_ply(ply, arr, names)
    xyz = xyz - off
    op = 1 / (1 + np.exp(-arr["opacity"].astype(float)))
    core = xyz[op > 0.5] if (op > 0.5).sum() > 1000 else xyz
    lo, hi = np.percentile(core, 2, 0), np.percentile(core, 98, 0)
    focus = np.median(core, 0)
    sid = f"pellis-{b.lower().replace('_', '-')}"
    title = f"Pellis {b} — 3D Gaussian Splatting (Kulturerbe)"
    desc = (f"3D-Gaussian-Splatting-Modell des historischen Gebaeudes {b} aus dem Pellis-Datensatz, trainiert "
            f"mit gsplat 1.5.3 auf den veroeffentlichten Kameraparametern ({len(arr):,} Gaussians, SH-Grad 0). "
            f"Koordinaten im System der photogrammetrischen Referenzpunktwolke (m, Z oben). Daten: Pellis, "
            f"Masiero, Betti, Tucci, Grussenmeyer (2025), Images&PointClouds Cultural Heritage Dataset, "
            f"Zenodo 14626611, CC BY 4.0.")
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base = f"media/scenes/{sid}/"
    scene = {"id": sid, "title": title, "description": desc, "created": created, "pano": None,
             "thumb": f"scenes/{sid}/thumb.jpg", "width": None, "height": None, "variants": [],
             "source": {"type": "gaussian-splatting", "dataset": "Pellis et al. 2025, Zenodo 14626611",
                        "license": "CC-BY-4.0"},
             "splat": {"file": ply.name, "camera_up": [0, 0, 1], "focus": focus.tolist(), "offset": off.tolist(),
                       "start": (focus + np.array([0, -0.6, 0.2]) * np.linalg.norm(hi - lo) / 2).round(2).tolist(),
                       "look": focus.round(2).tolist(),
                       "bbox": {"bbox_min": lo.tolist(), "bbox_max": hi.tolist()},
                       "note": f"{b}: 3DGS gegen photogrammetrische Referenz (Paper B). Daten CC BY 4.0, "
                               f"Pellis et al. 2025.",
                       "url": base + ply.name},
             "markers": [], "pano_url": None, "thumb_url": base + "thumb.jpg"}
    entry = {"id": sid, "title": title, "description": desc, "created": created,
             "thumb_url": base + "thumb.jpg", "markers": 0, "source_type": "gaussian-splatting",
             "has_3d": False, "kind": "splat", "datasets": ["Gaussian Splatting", "Pellis 2025"]}
    (out / "scene.json").write_text(json.dumps(scene, ensure_ascii=False))
    (out / "entry.json").write_text(json.dumps(entry, ensure_ascii=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sel = (op > 0.3) & np.all((xyz >= lo) & (xyz <= hi), 1)
    rgb = np.clip(0.5 + 0.2821 * np.stack([arr["f_dc_0"], arr["f_dc_1"], arr["f_dc_2"]], 1)[sel], 0, 1)
    p = xyz[sel]
    order = np.argsort(p[:, 2])                      # oben zuletzt zeichnen
    fig = plt.figure(figsize=(6.4, 4.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.scatter(p[order, 0], p[order, 1], c=rgb[order], s=0.3, linewidths=0)
    ax.set_aspect("equal")
    ax.set_facecolor("black")
    ax.axis("off")
    fig.patch.set_facecolor("black")
    fig.savefig(out / "thumb.jpg", facecolor="black")
    print(f"-> {out}: scene.json, entry.json, thumb.jpg ({sid})")


if __name__ == "__main__":
    main()
