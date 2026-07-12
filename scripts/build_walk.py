#!/usr/bin/env python3
"""build_walk.py -- fluessiger "Waldspaziergang" aus sequenziellen Trail-Frames.

Die FinnWoodlands-Frames sind entlang eines Waldwegs aufgenommen, aber duenn
gesampelt (grosse Bewegung zwischen benachbarten Bildern) -- stures Durchschalten
wuerde ruckeln/springen. Hier wird zwischen je zwei Frames per dichtem optischem
Fluss (Farneback) morphend interpoliert: Frame A wird vorwaerts, Frame B rueckwaerts
entlang des Flusses verzogen und zeitabhaengig ueberblendet. Das Ergebnis ist eine
kontinuierliche Vorwaertsfahrt, als H.264-MP4 gestreamt (Street-View-artig, glatt).

  python build_walk.py <frames_dir> <out.mp4> [--steps 8] [--fps 30]
      [--width 960] [--max-frames 0] [--flow-scale 0.5]

--flow-scale rechnet den Fluss auf kleinerer Aufloesung (schneller, glatter),
das Warpen selbst geschieht in voller Ausgabegroesse.
"""
import argparse
import glob
import os

import cv2
import imageio
import numpy as np


def list_frames(frames_dir):
    fs = {}
    for f in glob.glob(os.path.join(frames_dir, "**", "*.jpg"), recursive=True) + \
             glob.glob(os.path.join(frames_dir, "**", "*.png"), recursive=True):
        stem = os.path.splitext(os.path.basename(f))[0]
        try:
            fs[int(stem)] = f
        except ValueError:
            fs[stem] = f
    return [fs[k] for k in sorted(fs)]


def load(path, width):
    im = cv2.imread(path, cv2.IMREAD_COLOR)          # BGR
    h, w = im.shape[:2]
    height = int(round(h * width / w / 2) * 2)       # gerade Hoehe (H.264)
    im = cv2.resize(im, (width, height), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def dense_flow(a_gray, b_gray, scale):
    """Farneback-Fluss a->b, optional auf kleinerer Aufloesung gerechnet."""
    if scale != 1.0:
        sa = cv2.resize(a_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        sb = cv2.resize(b_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        sa, sb = a_gray, b_gray
    flow = cv2.calcOpticalFlowFarneback(sa, sb, None,
                                        pyr_scale=0.5, levels=4, winsize=25,
                                        iterations=3, poly_n=7, poly_sigma=1.5, flags=0)
    if scale != 1.0:
        h, w = a_gray.shape
        flow = cv2.resize(flow, (w, h), interpolation=cv2.INTER_LINEAR) / scale
    return flow


def warp(img, flow, grid_x, grid_y):
    """Rueckwaerts-Warp: sample img an (grid + flow)."""
    mapx = (grid_x + flow[..., 0]).astype(np.float32)
    mapy = (grid_y + flow[..., 1]).astype(np.float32)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("out")
    ap.add_argument("--steps", type=int, default=8, help="Zwischenbilder je Frame-Paar")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--max-frames", type=int, default=0, help="0 = alle")
    ap.add_argument("--flow-scale", type=float, default=0.5)
    args = ap.parse_args()

    frames = list_frames(args.frames_dir)
    if args.max_frames:
        frames = frames[:args.max_frames]
    if len(frames) < 2:
        raise SystemExit(f"Zu wenige Frames in {args.frames_dir}")
    print(f"{len(frames)} Frames -> {args.out}  ({args.steps} Zwischenbilder/Paar)")

    a = load(frames[0], args.width)
    h, w = a.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32),
                                 np.arange(h, dtype=np.float32))
    a_gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)

    writer = imageio.get_writer(args.out, fps=args.fps, codec="libx264",
                                quality=7, macro_block_size=8,
                                ffmpeg_params=["-pix_fmt", "yuv420p"])
    total = 0
    writer.append_data(a)          # allererster Frame
    total += 1
    for i in range(1, len(frames)):
        b = load(frames[i], args.width)
        b_gray = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
        flow_fwd = dense_flow(a_gray, b_gray, args.flow_scale)   # A->B
        flow_bwd = dense_flow(b_gray, a_gray, args.flow_scale)   # B->A
        for s in range(1, args.steps + 1):
            t = s / (args.steps + 1)
            wa = warp(a, flow_bwd * t, grid_x, grid_y)           # A Richtung B ziehen
            wb = warp(b, flow_fwd * (1 - t), grid_x, grid_y)     # B Richtung A ziehen
            # Verdeckungs-bewusste Ueberblendung: wo beide Warps stark abweichen
            # (Fluss unzuverlaessig -> Geisterbild), auf den naeheren Frame umschalten
            diff = np.abs(wa.astype(np.float32) - wb.astype(np.float32)).mean(2)
            occ = np.clip((diff - 24) / 40, 0, 1)[..., None]     # 0=einig, 1=verdeckt
            wB = (1 - occ) * t + occ * (1.0 if t > 0.5 else 0.0)
            mid = ((1 - wB) * wa + wB * wb).astype(np.uint8)
            writer.append_data(mid)
            total += 1
        writer.append_data(b)
        total += 1
        a, a_gray = b, b_gray
        if i % 25 == 0:
            print(f"  {i}/{len(frames)-1} Paare, {total} Frames geschrieben")
    writer.close()
    dur = total / args.fps
    mb = os.path.getsize(args.out) / 1e6
    print(f"-> {args.out}: {total} Frames, {dur:.1f}s @ {args.fps}fps, {mb:.1f} MB, {w}x{h}")


if __name__ == "__main__":
    main()
