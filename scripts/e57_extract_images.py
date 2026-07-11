#!/usr/bin/env python3
"""e57_extract_images.py -- Bilder + Posen aus einer E57-Datei extrahieren.

Python-Ersatz fuer e57_inspect.R (die R-Variante segfaultet unter Windows).
Liest die XML-Sektion CRC-seitenkorrekt, listet die images2D-Eintraege,
extrahiert die eingebetteten JPEG/PNG-Blobs und schreibt ein poses.json.

Nutzung:
  python e57_extract_images.py <datei.e57> <outdir>
"""
import sys, os, re, json, struct

PAGE, DATA = 1024, 1020

def read_logical(f, off, length):
    """`length` logische Bytes ab physischem Offset `off`, CRC-Seiten (letzte
    4 Byte je 1024) ueberspringend."""
    out = bytearray()
    while len(out) < length:
        page, inp = off // PAGE, off % PAGE
        if inp >= DATA:
            off = (page + 1) * PAGE
            continue
        f.seek(page * PAGE)
        buf = f.read(PAGE)
        if not buf:
            break
        out += buf[inp:min(DATA, len(buf))]
        off = (page + 1) * PAGE
    return bytes(out[:length])

def extract_blob(f, off, length):
    """Blob lesen; fileOffset zeigt je nach Writer auf einen 16-Byte
    Section-Header oder direkt auf die Daten -- per Magic Bytes pruefen."""
    probe = read_logical(f, off, min(length, 16))
    is_jpg = probe[:3] == b"\xff\xd8\xff"
    is_png = probe[:4] == b"\x89PNG"
    return read_logical(f, off if (is_jpg or is_png) else off + 16, length)

def txt(block, tag):
    m = re.search(r"<" + tag + r"[^>]*>([^<]*)</" + tag + r">", block)
    return m.group(1).strip() if m else None

def main():
    path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    f = open(path, "rb")
    h = f.read(48)
    assert h[:8] == b"ASTM-E57", "keine E57-Datei"
    xoff = struct.unpack("<Q", h[24:32])[0]
    xlen = struct.unpack("<Q", h[32:40])[0]
    xml = read_logical(f, xoff, xlen).decode("utf-8", "replace")

    stem = os.path.splitext(os.path.basename(path))[0]
    imgs = re.findall(r"<vectorChild.*?</vectorChild>",
                      re.search(r"<images2D.*?</images2D>", xml, re.S).group(0), re.S) \
           if "<images2D" in xml else []
    print(f"{os.path.basename(path)}: {len(imgs)} Bilder in images2D")

    manifest = []
    for i, one in enumerate(imgs, 1):
        rep = next((r for r in ("pinholeRepresentation", "sphericalRepresentation",
                                "cylindricalRepresentation", "visualReferenceRepresentation")
                    if "<" + r in one), None)
        w = txt(one, "imageWidth"); ht = txt(one, "imageHeight")
        entry = {"index": i, "guid": txt(one, "guid"), "representation": rep,
                 "width": int(w) if w else None, "height": int(ht) if ht else None}
        if rep == "pinholeRepresentation":
            entry["pinhole"] = {k: float(txt(one, k)) for k in
                                ("focalLength", "pixelWidth", "pixelHeight",
                                 "principalPointX", "principalPointY") if txt(one, k)}
        pose = re.search(r"<pose.*?</pose>", one, re.S)
        if pose:
            ps = pose.group(0)
            rot = re.search(r"<rotation.*?</rotation>", ps, re.S)
            tr = re.search(r"<translation.*?</translation>", ps, re.S)
            entry["pose"] = {
                "quaternion_wxyz": [float(txt(rot.group(0), k)) for k in ("w", "x", "y", "z")] if rot else None,
                "translation_xyz": [float(txt(tr.group(0), k)) for k in ("x", "y", "z")] if tr else None,
            }
        blob = re.search(r'<jpegImage[^>]*fileOffset="(\d+)"[^>]*length="(\d+)"', one)
        ext = ".jpg"
        if not blob:
            blob = re.search(r'<pngImage[^>]*fileOffset="(\d+)"[^>]*length="(\d+)"', one)
            ext = ".png"
        if blob:
            off, length = int(blob.group(1)), int(blob.group(2))
            data = extract_blob(f, off, length)
            fn = os.path.join(outdir, f"{stem}_{i:02d}{ext}")
            open(fn, "wb").write(data)
            ok = data[:3] == b"\xff\xd8\xff" or data[:4] == b"\x89PNG"
            entry["file"] = os.path.basename(fn)
            entry["bytes"] = len(data)
            t = entry.get("pose", {}).get("translation_xyz")
            print(f"  [{i}] {rep} {w}x{ht} -> {os.path.basename(fn)} "
                  f"({len(data)/1e3:.0f} KB) {'OK' if ok else 'BAD MAGIC'}"
                  + (f"  t=({t[0]:.2f},{t[1]:.2f},{t[2]:.2f})" if t else ""))
        manifest.append(entry)

    mf = os.path.join(outdir, f"{stem}_poses.json")
    json.dump(manifest, open(mf, "w"), indent=2)
    print("-> Posen:", os.path.basename(mf))

if __name__ == "__main__":
    main()
