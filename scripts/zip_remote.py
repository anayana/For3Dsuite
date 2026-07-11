#!/usr/bin/env python3
"""zip_remote.py -- ein entferntes ZIP ueber HTTP-Range-Requests lesen.

Zenodo liefert die BLK360-Rohscans als eine 9,5-GB-ZIP. Um die offene
Prueffrage (enthalten die E57-Dateien Image2D-Bloecke?) zu beantworten,
genuegt EINE E57-Datei. Statt das ganze Archiv zu laden, liest dieses
Skript nur das zentrale Verzeichnis am Dateiende und extrahiert danach
gezielt einzelne Mitglieder per Range-Request.

Nutzung:
  python zip_remote.py list  <url>
  python zip_remote.py get   <url> <member-substring> <outdir> [max_n]
"""
import sys, struct, zlib, urllib.request, os

def ranged(url, start, end=None):
    """Bytes [start, end] (inklusiv) per HTTP-Range holen."""
    rng = f"bytes={start}-" + ("" if end is None else str(end))
    req = urllib.request.Request(url, headers={"Range": rng})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def head_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])

def find_eocd(url, size):
    """End-of-Central-Directory (ggf. ZIP64) finden -> (cd_offset, cd_size)."""
    tail_len = min(size, 1 << 20)  # 1 MB reicht fuer EOCD + Kommentar
    tail = ranged(url, size - tail_len)
    base = size - tail_len
    p = tail.rfind(b"PK\x05\x06")
    if p < 0:
        raise RuntimeError("Kein EOCD gefunden")
    eocd = tail[p:p + 22]
    cd_size   = struct.unpack("<I", eocd[12:16])[0]
    cd_offset = struct.unpack("<I", eocd[16:20])[0]
    # ZIP64? Werte auf 0xFFFFFFFF gesetzt -> ZIP64-Locator direkt vor EOCD
    if cd_offset == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
        l = tail.rfind(b"PK\x06\x07", 0, p)
        if l < 0:
            raise RuntimeError("ZIP64-Locator fehlt")
        z64_eocd_off = struct.unpack("<Q", tail[l + 8:l + 16])[0]
        z = ranged(url, z64_eocd_off, z64_eocd_off + 55)
        assert z[:4] == b"PK\x06\x06", "ZIP64-EOCD-Signatur falsch"
        cd_size   = struct.unpack("<Q", z[40:48])[0]
        cd_offset = struct.unpack("<Q", z[48:56])[0]
    return cd_offset, cd_size

def parse_cd(url, cd_offset, cd_size):
    """Zentrales Verzeichnis parsen -> Liste von Eintraegen."""
    cd = ranged(url, cd_offset, cd_offset + cd_size - 1)
    entries, i = [], 0
    while i + 4 <= len(cd) and cd[i:i + 4] == b"PK\x01\x02":
        method = struct.unpack("<H", cd[i + 10:i + 12])[0]
        comp   = struct.unpack("<I", cd[i + 20:i + 24])[0]
        uncomp = struct.unpack("<I", cd[i + 24:i + 28])[0]
        nlen   = struct.unpack("<H", cd[i + 28:i + 30])[0]
        elen   = struct.unpack("<H", cd[i + 30:i + 32])[0]
        clen   = struct.unpack("<H", cd[i + 32:i + 34])[0]
        lho    = struct.unpack("<I", cd[i + 42:i + 46])[0]
        name   = cd[i + 46:i + 46 + nlen].decode("utf-8", "replace")
        extra  = cd[i + 46 + nlen:i + 46 + nlen + elen]
        # ZIP64-Extra-Feld (0x0001) fuer grosse Werte
        j = 0
        while j + 4 <= len(extra):
            hid, hsz = struct.unpack("<HH", extra[j:j + 4])
            if hid == 0x0001:
                blk, k = extra[j + 4:j + 4 + hsz], 0
                if uncomp == 0xFFFFFFFF: uncomp = struct.unpack("<Q", blk[k:k + 8])[0]; k += 8
                if comp   == 0xFFFFFFFF: comp   = struct.unpack("<Q", blk[k:k + 8])[0]; k += 8
                if lho    == 0xFFFFFFFF: lho    = struct.unpack("<Q", blk[k:k + 8])[0]; k += 8
            j += 4 + hsz
        entries.append(dict(name=name, method=method, comp=comp,
                            uncomp=uncomp, lho=lho))
        i += 46 + nlen + elen + clen
    return entries

def extract(url, e, outdir):
    """Ein Mitglied per Range holen, ggf. inflaten, auf Platte schreiben."""
    # Lokalen Header lesen (30 Byte fix + name + extra), um Datenoffset zu finden
    lh = ranged(url, e["lho"], e["lho"] + 29)
    assert lh[:4] == b"PK\x03\x04", "Local-Header-Signatur falsch"
    nlen = struct.unpack("<H", lh[26:28])[0]
    elen = struct.unpack("<H", lh[28:30])[0]
    data_off = e["lho"] + 30 + nlen + elen
    raw = ranged(url, data_off, data_off + e["comp"] - 1)
    if e["method"] == 0:
        data = raw
    elif e["method"] == 8:
        data = zlib.decompress(raw, -15)
    else:
        raise RuntimeError(f"Unbekannte Methode {e['method']}")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, os.path.basename(e["name"]))
    with open(out, "wb") as f:
        f.write(data)
    return out, len(data)

def stream_member(url, e, chunk=1 << 20):
    """Komprimierte Bytes eines Mitglieds streamen und (raw-)inflaten.
    Liefert nacheinander dekomprimierte Byte-Bloecke (Generator)."""
    lh = ranged(url, e["lho"], e["lho"] + 29)
    assert lh[:4] == b"PK\x03\x04", "Local-Header-Signatur falsch"
    nlen = struct.unpack("<H", lh[26:28])[0]
    elen = struct.unpack("<H", lh[28:30])[0]
    data_off = e["lho"] + 30 + nlen + elen
    end = data_off + e["comp"] - 1
    req = urllib.request.Request(url, headers={"Range": f"bytes={data_off}-{end}"})
    dec = zlib.decompressobj(-15) if e["method"] == 8 else None
    with urllib.request.urlopen(req, timeout=300) as r:
        while True:
            buf = r.read(chunk)
            if not buf:
                break
            yield dec.decompress(buf) if dec else buf
    if dec:
        tail = dec.flush()
        if tail:
            yield tail

def get_nested(url, outer_sub, inner_sub, outdir, maxn):
    """Aeusseres Mitglied streamen, inneres ZIP sequenziell parsen und die
    ersten `maxn` passenden Dateien extrahieren -- dann fruehzeitig abbrechen.

    Das innere ZIP nutzt Data-Descriptors (Flag Bit 3), die lokalen Header
    tragen also keine Groessen. Deflate-Streams (Methode 8) haben aber ein
    eigenes Ende-Signal (zlib eof); danach wird der Descriptor per Suche nach
    der naechsten Header-Signatur uebersprungen. Verzeichniseintraege
    (Methode 0, Groesse 0) folgen ohne Daten direkt dem naechsten Header.
    """
    size = head_size(url)
    cd_off, cd_size = find_eocd(url, size)
    outer = next(e for e in parse_cd(url, cd_off, cd_size)
                 if outer_sub.lower() in e["name"].lower())
    print(f"Aeusseres Mitglied: {outer['name']}  "
          f"({outer['comp']/1e6:.0f} MB komprimiert, Methode {outer['method']})")
    os.makedirs(outdir, exist_ok=True)

    buf = bytearray()
    got = 0
    state = "HDR"       # HDR | INFLATE | SKIP (Data-Descriptor ueberspringen)
    dec = fh = out = None
    blocks = stream_member(url, outer)
    done = False
    while not done:
        try:
            buf += next(blocks)
        except StopIteration:
            done = True   # letzte Runde mit dem verbleibenden Puffer

        again = True
        while again:
            again = False
            if state == "HDR":
                if len(buf) < 4:
                    break
                sig = bytes(buf[:4])
                if sig in (b"PK\x01\x02", b"PK\x05\x06", b"PK\x06\x06"):
                    return   # zentrales Verzeichnis -> fertig
                if sig != b"PK\x03\x04":
                    raise RuntimeError(f"Unerwartete Signatur {sig.hex()}")
                if len(buf) < 30:
                    break
                method = struct.unpack("<H", buf[8:10])[0]
                nlen   = struct.unpack("<H", buf[26:28])[0]
                elen   = struct.unpack("<H", buf[28:30])[0]
                if len(buf) < 30 + nlen + elen:
                    break
                name = bytes(buf[30:30 + nlen]).decode("utf-8", "replace")
                del buf[:30 + nlen + elen]
                take = (inner_sub.lower() in name.lower()) and not name.endswith("/")
                if method == 0:
                    # Verzeichnis / leerer Eintrag ohne Daten -> naechster Header
                    if take:
                        print(f"  (uebersprungen, unkomprimiert) {name}")
                    state = "HDR"; again = True
                elif method == 8:
                    dec = zlib.decompressobj(-15)
                    if take:
                        out = os.path.join(outdir, os.path.basename(name))
                        fh = open(out, "wb")
                        print(f"  extrahiere {name} ...")
                    else:
                        out = fh = None
                    state = "INFLATE"; again = True
                else:
                    raise RuntimeError(f"Methode {method} nicht unterstuetzt")

            elif state == "INFLATE":
                out_bytes = dec.decompress(bytes(buf))
                if fh and out_bytes:
                    fh.write(out_bytes)
                if dec.eof:
                    buf = bytearray(dec.unused_data)
                    if fh:
                        fh.close()
                        got += 1
                        print(f"  -> fertig: {out} ({os.path.getsize(out)/1e6:.1f} MB)")
                        if got >= maxn:
                            return
                    dec = fh = out = None
                    state = "SKIP"; again = True
                else:
                    buf = bytearray()   # vollstaendig konsumiert, mehr Daten holen

            elif state == "SKIP":
                # Data-Descriptor variabler Laenge -> zur naechsten Signatur springen
                idx = -1
                for s in (b"PK\x03\x04", b"PK\x01\x02"):
                    j = buf.find(s)
                    if j >= 0 and (idx < 0 or j < idx):
                        idx = j
                if idx >= 0:
                    del buf[:idx]
                    state = "HDR"; again = True
                # sonst: mehr Daten noetig
        if done and state == "HDR" and len(buf) < 4:
            break
    print("Stream zu Ende ohne genug Treffer.")

def main():
    cmd, url = sys.argv[1], sys.argv[2]
    if cmd == "getnested":
        outer_sub, inner_sub, outdir = sys.argv[3], sys.argv[4], sys.argv[5]
        maxn = int(sys.argv[6]) if len(sys.argv) > 6 else 1
        get_nested(url, outer_sub, inner_sub, outdir, maxn)
        return
    size = head_size(url)
    cd_offset, cd_size = find_eocd(url, size)
    entries = parse_cd(url, cd_offset, cd_size)
    if cmd == "list":
        for e in entries:
            m = {0: "stored", 8: "deflate"}.get(e["method"], e["method"])
            print(f"{e['uncomp']/1e6:10.2f} MB  {m:8}  {e['name']}")
        print(f"\n{len(entries)} Eintraege, Archiv {size/1e9:.2f} GB")
    elif cmd == "get":
        sub, outdir = sys.argv[3], sys.argv[4]
        maxn = int(sys.argv[5]) if len(sys.argv) > 5 else 1
        hits = [e for e in entries if sub.lower() in e["name"].lower()
                and not e["name"].endswith("/")][:maxn]
        if not hits:
            print("Kein Treffer fuer:", sub); sys.exit(1)
        for e in hits:
            out, n = extract(url, e, outdir)
            print(f"-> {out}  ({n/1e6:.1f} MB)")

if __name__ == "__main__":
    main()
