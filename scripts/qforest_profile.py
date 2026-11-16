#!/usr/bin/env python3
"""qforest_profile.py -- Kronendach-Struktur, Schichten und Lichtkarte aus einer TLS-Wolke.

Eingabe: Analyse-.npz aus qforest_bench.py prep (xyz + shift, hag = Hoehe ueber
Boden aus den Bodenpunkten). Ausgabe:

  <out>_profil.csv     Belegungsanteil je 1-m-Hoehenschicht (Voxel binaer)
  <out>_kennwerte.json Kronendachhoehe, Deckungsgrad, ENL, FHD, Schichtwerte,
                       Lichttransmission (senkrecht + Sonnengang) und Annahmen
  <out>_licht.npz      Transmission je Bodenzelle (fuer Karte und Szene)

Methode (festgelegt in scripts/QFOREST_PROJEKT.md):
  * Voxel fest (Standard 0,2 m), belegt = mind. ein Vegetationspunkt (hag > 0,3 m)
  * Schichten relativ zur Kronendachhoehe H (P95 der Vegetationshoehen)
  * Licht: Lueckenwahrscheinlichkeit Pgap -- Strahl vom Boden (1 m) zur Sonne trifft
    kein belegtes Voxel. Plot periodisch fortgesetzt, damit flache Sonnenstaende
    nicht seitlich aus der kleinen Flaeche fallen. Tagesmittel gewichtet mit sin(Hoehe)
  * Grenzen: keine Scannerstandorte -> keine Verdeckungskorrektur; das obere
    Kronendach ist v. a. in den Tropen unterschaetzt. Werte relativ deuten.

  python scripts/qforest_profile.py data/qforest/rc_test.npz --lat -17.12 \\
      --out extdata/qforest/robsoncreek_test
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

VEG_H = 0.3
STRATA = [("Boden", None), ("Unterwuchs 0,5–2 m", None), ("untere Schicht", None),
          ("mittlere Schicht", None), ("Kronendach", None)]
STRATA_COLORS = [(118, 100, 82), (120, 200, 120), (80, 160, 230), (230, 180, 70),
                 (225, 90, 110)]


def strata_bounds(H):
    """Obergrenzen der Schichten [m ueber Boden]; letzte = offen."""
    return [0.5, 2.0, max(2.0, H / 3), max(2.0, 2 * H / 3)]


def stratum_of(hag, H):
    b = strata_bounds(H)
    return np.searchsorted(np.array(b), hag, side="right")


def voxelize(xy, hag, v, H_max, sample=0.02):
    """Deckung je Voxel: Anzahl 2-cm-Punkte / (v/sample)^2, hoechstens 1.

    Die Wolke ist auf 2-cm-Voxel ausgeduennt (qforest_bench.py prep). Eine Blattflaeche,
    die ein Voxel ganz quert, liefert ~ (v/0,02)^2 Punkte -> Deckung 1; ein kleines
    Blattstueck entsprechend weniger. So wird nicht jedes Voxel mit einem einzigen
    Punkt undurchsichtig (das binaere Verfahren laesst im Regenwald kein Licht durch).
    """
    lo = xy.min(0)
    ij = np.floor((xy - lo) / v).astype(int)
    nx, ny = ij.max(0) + 1
    nz = int(math.ceil(H_max / v)) + 1
    k = np.clip(np.floor(hag / v).astype(int), 0, nz - 1)
    cnt = np.zeros((nx, ny, nz), np.float32)
    np.add.at(cnt, (ij[:, 0], ij[:, 1], k), 1.0)
    return np.minimum(cnt / (v / sample) ** 2, 1.0), lo


def sun_positions(lat, doy, step_h=0.5):
    """(Hoehe, Azimut) in rad fuer Sonne ueber Horizont, einfacher Ansatz (Cooper)."""
    dec = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365)
    phi = math.radians(lat)
    out = []
    for t in np.arange(0, 24, step_h):
        h = math.radians(15 * (t - 12))
        sin_el = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(h)
        el = math.asin(max(-1, min(1, sin_el)))
        if el <= math.radians(5):
            continue
        az = math.atan2(math.sin(h), math.cos(h) * math.sin(phi) - math.tan(dec) * math.cos(phi))
        out.append((el, az + math.pi))          # Azimut ab Nord, im Uhrzeigersinn
    return out


def gap_to_sun(opac, v, el, az, step_m=0.5, z0=1.0):
    """Transmission je Strahl von 1 m ueber Boden zur Sonne: Produkt (1 - Deckung)
    der durchquerten Voxel (jedes einmal). Ursprung auf einem 0,5-m-Raster."""
    nx, ny, nz = opac.shape
    g = max(1, int(round(step_m / v)))
    gx, gy = np.meshgrid(np.arange(0, nx, g) + 0.5, np.arange(0, ny, g) + 0.5, indexing="ij")
    dx, dy = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el)
    dz = math.sin(el)
    T = np.ones(gx.shape, np.float32)
    last = np.full(gx.shape + (3,), -1, int)
    t = 0.0
    while True:
        t += 0.5                                       # halbe Voxelweite je Schritt
        zi = int(z0 / v + dz * t)
        if zi >= nz:
            break
        xi = np.floor(gx + dx * t).astype(int) % nx   # periodisch fortgesetzt
        yi = np.floor(gy + dy * t).astype(int) % ny
        new = ~((last[..., 0] == xi) & (last[..., 1] == yi) & (last[..., 2] == zi))
        T *= np.where(new, 1.0 - opac[xi, yi, zi], 1.0)
        last[..., 0], last[..., 1], last[..., 2] = xi, yi, zi
        if T.max() < 1e-6:
            break
    return T


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("npz")
    ap.add_argument("--out", required=True, help="Praefix der Ausgabedateien")
    ap.add_argument("--lat", type=float, required=True, help="Breitengrad (Sonnenstand)")
    ap.add_argument("--voxel", type=float, default=0.2,
                    help="Voxelkante [m]; 0,5 m ist im Regenwald gesaettigt")
    a = ap.parse_args()

    d = np.load(a.npz)
    xyz = d["xyz"].astype(np.float64)
    hag = d["hag"].astype(np.float64)
    veg = hag > VEG_H
    xy, hv = xyz[veg, :2], hag[veg]
    H95, H99 = (float(np.percentile(hv, q)) for q in (95, 99))
    occ, lo = voxelize(xy, hv, a.voxel, float(hv.max()))   # Deckung 0..1 je Voxel
    nx, ny, nz = occ.shape
    area = nx * ny * a.voxel ** 2

    # ---- Profil in 1-m-Schichten (Anteil belegter Voxel je Schicht) ----
    per_m = max(1, int(round(1.0 / a.voxel)))
    # PAI-Proxy je 1-m-Schicht: projizierte Flaeche (Deckung x v^2) je Bodenflaeche
    pad = np.array([float(occ[:, :, i:i + per_m].sum()) * a.voxel ** 2 / area
                    for i in range(0, nz, per_m)])
    frac = pad
    vox_layer = np.array([int((occ[:, :, i:i + per_m] > 0).sum()) for i in range(0, nz, per_m)])
    p = pad[pad > 0] / pad.sum()
    enl = float(1.0 / (p ** 2).sum())                  # Ehbrecht: inverse Simpson
    fhd = float(-(p * np.log(p)).sum())                # MacArthur: Shannon
    t_above2 = np.prod(1.0 - occ[:, :, int(2.0 / a.voxel):], axis=2)
    cover = float(1.0 - t_above2.mean())               # Deckung ueber 2 m (senkrecht)

    # ---- Schichten ----
    b = strata_bounds(H95)
    edges = [0.0] + b + [float(hv.max()) + a.voxel]
    st = []
    for i, (name, _) in enumerate(STRATA):
        z0, z1 = edges[i], edges[i + 1]
        k0, k1 = int(z0 / a.voxel), max(int(z0 / a.voxel) + 1, int(math.ceil(z1 / a.voxel)))
        sub = occ[:, :, k0:k1]
        st.append({"schicht": name, "von_m": round(z0, 1), "bis_m": round(z1, 1),
                   "PAI_proxy": round(float(sub.sum()) * a.voxel ** 2 / area, 2),
                   "deckung_draufsicht": round(float(1 - np.prod(1 - sub, axis=2).mean()), 3)
                   if sub.size else 0.0,
                   "punkte_anteil": round(float(((hag > z0) & (hag <= z1)).mean()), 3)})

    # ---- Licht ----
    g = max(1, int(round(0.5 / a.voxel)))
    t_vert = np.prod(1.0 - occ[:, :, int(1.0 / a.voxel):], axis=2).astype(np.float32)
    t_vert = t_vert[:t_vert.shape[0] // g * g, :t_vert.shape[1] // g * g] \
        .reshape(t_vert.shape[0] // g, g, t_vert.shape[1] // g, g).mean(axis=(1, 3))
    days = {"Tag-und-Nacht-Gleiche": 80, "Juni-Sonnenwende": 172, "Dezember-Sonnenwende": 355}
    sun = {}
    tday = None
    for name, doy in days.items():
        pos = sun_positions(a.lat, doy)
        w = np.array([math.sin(el) for el, _ in pos])
        ts = np.array([gap_to_sun(occ, a.voxel, el, az) for el, az in pos])
        mean_map = (ts * w[:, None, None]).sum(0) / w.sum()
        sun[name] = {"mittel": round(float(mean_map.mean()), 4),
                     "p10": round(float(np.percentile(mean_map, 10)), 4),
                     "p90": round(float(np.percentile(mean_map, 90)), 4),
                     "anteil_zellen_ueber_10pct": round(float((mean_map > 0.1).mean()), 3),
                     "sonnenstaende": len(pos)}
        if name == "Tag-und-Nacht-Gleiche":
            tday = mean_map

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(f"{out}_profil.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hoehe_von_m", "hoehe_bis_m", "PAI_proxy_m2m2", "voxel_belegt"])
        for i, (fr, nv) in enumerate(zip(frac, vox_layer)):
            w.writerow([i, i + 1, round(float(fr), 4), int(nv)])
    kw = {
        "flaeche_m2": round(area, 1), "voxel_m": a.voxel, "breitengrad": a.lat,
        "kronendach_H95_m": round(H95, 1), "kronendach_H99_m": round(H99, 1),
        "deckungsgrad_ueber_2m": round(cover, 3),
        "PAI_proxy_gesamt": round(float(pad.sum()), 2),
        "ENL_inverse_Simpson": round(enl, 2), "FHD_Shannon": round(fhd, 3),
        "schichten": st,
        "licht": {"senkrecht_mittel": round(float(t_vert.mean()), 4),
                  "senkrecht_p10": round(float(np.percentile(t_vert, 10)), 4),
                  "senkrecht_p90": round(float(np.percentile(t_vert, 90)), 4),
                  "sonnengang": sun},
        "annahmen": {"licht": ("Transmission = Produkt (1 - Deckung) der durchquerten "
                               "Voxel; Deckung = 2-cm-Punkte / (v/0,02)^2"),
                     "vegetation_ab_m": VEG_H,
                     "rand": "Plot periodisch fortgesetzt",
                     "grenze": ("keine Scannerstandorte, keine Verdeckungskorrektur; "
                                "oberes Kronendach unterschaetzt -> Luecken eher "
                                "ueberschaetzt; Ergebnis haengt von der Voxelkante ab; "
                                "Werte relativ deuten")},
    }
    Path(f"{out}_kennwerte.json").write_text(json.dumps(kw, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    np.savez_compressed(f"{out}_licht.npz", licht=tday.astype(np.float32),
                        senkrecht=t_vert.astype(np.float32), lo=lo, voxel=a.voxel,
                        strata_bounds=np.array(b))
    print(f"H95 {H95:.1f} m, PAI-Proxy {pad.sum():.1f}, Deckung {cover:.0%}, ENL {enl:.2f}, FHD {fhd:.2f}, "
          f"Licht senkrecht {t_vert.mean():.1%}, Sonnengang (TNG) "
          f"{sun['Tag-und-Nacht-Gleiche']['mittel']:.1%}  -> {out}_*")


if __name__ == "__main__":
    main()
