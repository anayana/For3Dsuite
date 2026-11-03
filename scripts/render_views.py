#!/usr/bin/env python3
"""render_views.py -- 3DGS-Modell (gsplat-Checkpoint) an Fotostandpunkten rendern: Foto | Render.

Laeuft im Ordner gsplat/examples (nutzt datasets.colmap.Parser). Waehlt N gleichmaessig verteilte
Fotos, rendert sie auf der GPU, schreibt view_<i>.jpg (links Foto, rechts Render) und views.json mit
PSNR sowie Kamerazentrum/Blickrichtung im System der Punktwolke (fuer die Startansicht im Viewer).

  cd gsplat/examples && python render_views.py <data_dir> <factor> <result_dir> <out_dir> [--n 8]
"""
import argparse
import glob
import json
import os

import imageio.v2 as imageio
import numpy as np
import torch
from datasets.colmap import Parser
from gsplat import rasterization


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("data")
    ap.add_argument("factor", type=int)
    ap.add_argument("gs")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    p = Parser(data_dir=a.data, factor=a.factor, normalize=True, test_every=8)
    Tinv = np.linalg.inv(p.transform)                       # normiert -> Welt (Punktwolke)
    ck = sorted(glob.glob(f"{a.gs}/ckpts/*.pt"), key=lambda q: int(q.split("_")[-2]))
    st = torch.load(ck[-1], map_location="cuda", weights_only=False)["splats"]
    means, quats = st["means"], torch.nn.functional.normalize(st["quats"], dim=-1)
    scales, opac = torch.exp(st["scales"]), torch.sigmoid(st["opacities"])
    colors = torch.cat([st["sh0"], st["shN"]], 1)
    sh_deg = int(np.sqrt(colors.shape[1])) - 1

    n_img = len(p.image_names)
    idx = np.linspace(0, n_img - 1, min(a.n, n_img)).round().astype(int)
    views = []
    for k, i in enumerate(idx):
        c2w = p.camtoworlds[i]
        K = p.Ks_dict[p.camera_ids[i]]
        W, H = p.imsize_dict[p.camera_ids[i]]
        gt = imageio.imread(p.image_paths[i])[..., :3]
        H, W = gt.shape[:2]
        vm = torch.from_numpy(np.linalg.inv(c2w)).float().cuda()[None]
        Kt = torch.from_numpy(K).float().cuda()[None]
        with torch.no_grad():
            img, _, _ = rasterization(means, quats, scales, opac, colors, vm, Kt, W, H, sh_degree=sh_deg)
        rd = (img[0].clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
        mse = np.mean((rd.astype(float) - gt.astype(float)) ** 2) / 255 ** 2
        psnr = float(10 * np.log10(1 / max(mse, 1e-12)))
        imageio.imwrite(os.path.join(a.out, f"view_{k}.jpg"), np.concatenate([gt, rd], 1), quality=88)
        cw = Tinv @ c2w                                       # Kamera im System der Punktwolke
        R = cw[:3, :3] / np.cbrt(np.linalg.det(cw[:3, :3]))
        views.append({"file": f"view_{k}.jpg", "image": p.image_names[i], "psnr": round(psnr, 2),
                      "center": cw[:3, 3].round(3).tolist(), "forward": (R[:, 2]).round(4).tolist(),
                      "up": (-R[:, 1]).round(4).tolist()})
        print(f"view_{k}: {p.image_names[i]} PSNR {psnr:.2f}")
    json.dump(views, open(os.path.join(a.out, "views.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
