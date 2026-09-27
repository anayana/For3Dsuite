"""Loader für den Bolderwood-Datensatz (TLS-Panoramawolken + Stereo + LiDAR-Depth).

Alle Konstanten hier sind an den Daten nachgemessen, nicht aus dem Header übernommen.
Details und Messwerte: QC_REPORT.md

Wichtigste Eigenheit
--------------------
Der PCD-Header meldet ``WIDTH 10054 / HEIGHT 3771``. Nach PCD-Konvention wäre die
Speicherreihenfolge ``(HEIGHT, WIDTH)`` — das ist hier FALSCH. Tatsächlich liegen
10054 aufeinanderfolgende Vertikallinien à 3771 Punkte vor, korrekt ist also
``reshape(10054, 3771).T``. ``load_panorama()`` macht das richtig.

Fehlende Returns sind als exakt ``(0, 0, 0)`` kodiert, nicht als NaN.
Es sind keine NaN/Inf in den Wolken.

Benötigt: numpy, scipy (für die .mat-Depthmaps), tifffile oder Pillow (für die Stereo-TIFs).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np

# --- Verzeichnis ------------------------------------------------------------
# Standard: der Ordner, in dem diese Datei liegt. Bei Bedarf überschreiben:
#   import bolderwood_io as bw; bw.ROOT = Path("/pfad/zu/bolderwood")
ROOT = Path(__file__).resolve().parent

# --- nachgemessene Scan-Geometrie -------------------------------------------
N_LINES = 10054          # vertikale Scanlinien = Azimutschritte (Header: WIDTH)
N_PER_LINE = 3771        # Punkte je Linie = Elevationsschritte (Header: HEIGHT)
N_POINTS = N_LINES * N_PER_LINE          # 37_913_634
ANG_RES_DEG = 0.0358     # identisch in Azimut und Elevation
ELEV_MIN_DEG = -45.03
ELEV_MAX_DEG = +89.93
AZIMUTH_SPAN_DEG = 359.9  # volle 360°-Abdeckung

# --- Bildindizes (Szene 19 hat Lücken bei 3 und 13) -------------------------
VIEW_IDS = {
    19: (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18),
    45: tuple(range(1, 19)),
}
SCENES = (19, 45)

STEREO_SHAPE = (688, 1032, 3)   # uint8 RGB, 8 bit — KEINE HDRs im Datensatz
DEPTH_SHAPE = (688, 1032)       # float64, radiale Distanz in Metern, NaN = kein Return

_PCD_ZIP = "clean_cloud{scene}_UPDATE.pcd_.zip"
_STEREO_ZIP = "Scene{scene}_Res688_1032_StereoIm.zip"
_DEPTH_ZIP = "Scene{scene}_Res688_1032_Depth.zip"


# ---------------------------------------------------------------------------
# Punktwolken
# ---------------------------------------------------------------------------
def _parse_ascii(text: bytes) -> np.ndarray:
    """Schnellster verfügbare ASCII->float32-Pfad (C-Ebene, ~40 s je Wolke)."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")           # np.fromstring ist deprecated,
        return np.fromstring(text, np.float32, sep=" ")   # aber 20x schneller


def iter_points(scene: int, chunk_bytes: int = 1 << 24):
    """Streamt die Wolke als (n, 4)-float32-Blöcke [x, y, z, intensity].

    Liest direkt aus dem ZIP, ohne die 1,43 GB auf Platte zu entpacken.
    Eine Wolke braucht so ~40 s und ~200 MB RAM.
    """
    path = ROOT / _PCD_ZIP.format(scene=scene)
    with zipfile.ZipFile(path) as zf, zf.open(zf.namelist()[0]) as fh:
        buf = fh.read(1 << 16)
        start = buf.index(b"\n", buf.index(b"DATA")) + 1   # Header überspringen
        carry = buf[start:]
        while True:
            chunk = fh.read(chunk_bytes)
            if chunk:
                data = carry + chunk
                cut = data.rfind(b"\n") + 1                # nur ganze Zeilen
                carry, data = data[cut:], data[:cut]
            else:
                data, carry = carry, b""
            if data:
                a = _parse_ascii(data)
                yield a[: a.size // 4 * 4].reshape(-1, 4)
            if not chunk:
                return


def load_cloud(scene: int, fields: str = "xyzi") -> np.ndarray:
    """Lädt die komplette Wolke als (37913634, 4) float32 — ca. 610 MB RAM.

    ``fields='xyz'`` liefert nur die Koordinaten (457 MB).
    """
    ncol = 4 if fields == "xyzi" else 3
    out = np.empty((N_POINTS, ncol), np.float32)
    i = 0
    for block in iter_points(scene):
        k = len(block)
        out[i:i + k] = block[:, :ncol]
        i += k
    if i != N_POINTS:
        raise ValueError(f"Szene {scene}: {i} Punkte gelesen, {N_POINTS} erwartet")
    return out


def load_panorama(scene: int, flip_elevation: bool = True) -> np.ndarray:
    """Lädt die Wolke als equirektangulares Panorama (3771, 10054, 4).

    Achse 0 = Elevation, Achse 1 = Azimut, 0,0358°/px in beiden Richtungen.
    Mit ``flip_elevation=True`` (Default) liegt der Zenit in Zeile 0, das Bild
    ist also so orientiert, wie man es erwartet.
    """
    pano = load_cloud(scene).reshape(N_LINES, N_PER_LINE, 4).transpose(1, 0, 2)
    return pano[::-1] if flip_elevation else pano


def valid_mask(points: np.ndarray) -> np.ndarray:
    """True, wo ein echter Return vorliegt. Fehlende Returns sind exakt (0,0,0)."""
    return (points[..., :3] != 0).any(-1)


def to_spherical(xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Kartesisch -> (Reichweite [m], Azimut [°], Elevation [°]).

    Die Wolken sind sensorzentriert, der Ursprung ist die Scannerposition.
    Die Depth-Maps enthalten genau diese Reichweite, nicht die z-Tiefe.
    """
    x, y, z = xyz[..., 0], xyz[..., 1], xyz[..., 2]
    rho = np.hypot(x, y)
    return (np.sqrt(rho ** 2 + z ** 2),
            np.degrees(np.arctan2(y, x)),
            np.degrees(np.arctan2(z, rho)))


# ---------------------------------------------------------------------------
# Depth-Maps und Stereobilder
# ---------------------------------------------------------------------------
def load_depth(scene: int, view: int) -> np.ndarray:
    """Depth-Map als (688, 1032) float64. NaN = kein LiDAR-Return.

    Werte sind radiale Distanzen in Metern (2,3–125,5 m), niemals <= 0.
    """
    _check_view(scene, view)
    from scipy.io import loadmat
    with zipfile.ZipFile(ROOT / _DEPTH_ZIP.format(scene=scene)) as zf:
        with zf.open(f"DMapScene{scene}_{view}.mat") as fh:
            return loadmat(fh)["dMapLiDAR"]


def load_stereo(scene: int, view: int) -> tuple[np.ndarray, np.ndarray]:
    """Stereopaar als (links, rechts), je (688, 1032, 3) uint8.

    8-Bit-RGB — der Datensatz enthält keine HDR-Aufnahmen.
    """
    _check_view(scene, view)
    with zipfile.ZipFile(ROOT / _STEREO_ZIP.format(scene=scene)) as zf:
        return tuple(_read_tif(zf, f"Scene_{scene}_{view}{side}.tif")
                     for side in ("Left", "Right"))


def _read_tif(zf: zipfile.ZipFile, name: str) -> np.ndarray:
    import io
    raw = io.BytesIO(zf.read(name))
    try:
        import tifffile
        return tifffile.imread(raw)
    except ImportError:
        from PIL import Image
        return np.asarray(Image.open(raw))


def _check_view(scene: int, view: int) -> None:
    if scene not in VIEW_IDS:
        raise ValueError(f"Szene {scene} gibt es nicht, nur {SCENES}")
    if view not in VIEW_IDS[scene]:
        raise ValueError(
            f"Szene {scene} hat keine Aufnahme {view}; verfügbar: {VIEW_IDS[scene]}"
        )


# ---------------------------------------------------------------------------
# Vorgefertigte Teilmengen (klein, für schnelle Tests)
# ---------------------------------------------------------------------------
def load_small(scene: int, with_rgb: bool = True):
    """Die ausgedünnte Wolke aus den CSVs: (n, 3) float32, optional (n, 3) uint8 RGB.

    710 292 Punkte (Szene 19) bzw. 619 140 (Szene 45). Verifizierte Teilmenge der
    Vollwolke — >99 % Deckung bei 5 cm Voxelgröße —, aber um ~1–2 mm versetzt und
    daher nicht bitgleich.
    """
    xyz = np.loadtxt(ROOT / f"scene{scene}_small_xyz.csv", dtype=np.float32)
    if not with_rgb:
        return xyz
    rgb = np.loadtxt(ROOT / f"scene{scene}_small_rgb.csv", dtype=np.uint8)
    return xyz, rgb


# ---------------------------------------------------------------------------
# QC-Bilder
# ---------------------------------------------------------------------------
def write_qc_panoramas(scene: int, outdir: Path | str = ROOT,
                       reduce: int = 4) -> list[Path]:
    """Reichweiten- und Intensitaetspanorama als PNG schreiben.

    Die Sichtpruefung zu QC_REPORT.md Punkt 1: stimmt die Speicherreihenfolge,
    ergibt sich ein durchgehendes Panorama; stimmt sie nicht, ist es Streifenmuell.
    Die Bilder liegen NICHT im Repo (je 2-30 MB Rauschbild, praktisch nicht
    komprimierbar, und der Push dieses Repos scheitert ab etwa 1 MB) -- sie werden
    hier erzeugt.

    ``reduce=4`` mittelt auf 2514x943, die Groesse, in der die Panoramen fuer
    QC_REPORT.md angesehen wurden; der Streifentest braucht die volle Aufloesung
    nicht. ``reduce=1`` liefert die ganzen 3771x10054 (dann je 20-30 MB).
    """
    from PIL import Image

    outdir = Path(outdir)
    pano = load_panorama(scene)
    m = valid_mask(pano)
    rng, _, _ = to_spherical(pano[..., :3])

    # Reichweite: Perzentilschnitt, damit einzelne weite Returns nicht alles
    # flachdruecken; ohne Return schwarz.
    lo, hi = np.percentile(rng[m], [1, 99])
    r = np.clip((rng - lo) / max(hi - lo, 1e-9), 0, 1)
    r[~m] = 0
    cmap = np.stack([np.clip(1.5 - abs(4 * r - 3), 0, 1),      # R
                     np.clip(1.5 - abs(4 * r - 2), 0, 1),      # G
                     np.clip(1.5 - abs(4 * r - 1), 0, 1)], -1)  # B
    cmap[~m] = 0

    inten = pano[..., 3]
    ilo, ihi = np.percentile(inten[m], [1, 99])
    g = np.clip((inten - ilo) / max(ihi - ilo, 1e-9), 0, 1)
    g[~m] = 0

    out = []
    for name, arr in (("range", (cmap * 255).astype(np.uint8)),
                      ("intensity", (g * 255).astype(np.uint8))):
        p = outdir / f"QC_scene{scene}_{name}_pano.png"
        im = Image.fromarray(arr)
        if reduce > 1:
            im = im.reduce(reduce)      # Kastenmittel, kein Nachschaerfen
        im.save(p, optimize=True)
        out.append(p)
    return out


if __name__ == "__main__":
    import sys

    if "--qc-images" in sys.argv:
        for sc in SCENES:
            for p in write_qc_panoramas(sc):
                print(f"-> {p}")
        raise SystemExit(0)

    for sc in SCENES:
        pano = load_panorama(sc)
        m = valid_mask(pano)
        rng, az, el = to_spherical(pano[..., :3])
        print(f"Szene {sc}: {pano.shape}, {m.sum():,} Returns "
              f"({100 * (~m).mean():.2f} % ohne), "
              f"Reichweite {rng[m].min():.2f}–{rng[m].max():.2f} m, "
              f"Elevation {el[m].min():.2f}..{el[m].max():.2f}°, "
              f"Aufnahmen {VIEW_IDS[sc]}")
