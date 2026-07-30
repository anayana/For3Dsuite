#!/usr/bin/env python3
"""zenodo_zip_pick.py -- einzelne Dateien aus einem grossen ZIP im Netz holen.

SegmentedForests liegt als EIN 4,7-GB-Zip auf Zenodo. Fuer zwei Plots das ganze
Archiv zu laden waere Verschwendung; ZIP erlaubt aber wahlfreien Zugriff: das
Inhaltsverzeichnis steht am ENDE der Datei, jeder Eintrag nennt seinen Offset.
Mit HTTP-Range-Requests (Zenodo antwortet mit 206) laesst sich damit gezielt
lesen -- erst das Verzeichnis, dann nur die gewuenschten Eintraege.

  python scripts/zenodo_zip_pick.py <url> --list
  python scripts/zenodo_zip_pick.py <url> --extract "PLOT_A.laz" "PLOT_A.ini" --out data/segforests

Die Implementierung ist ein dateiaehnliches Objekt ueber HTTP-Ranges, das
Pythons zipfile direkt benutzen kann -- kein eigener ZIP-Parser.
"""
import argparse
import io
import time
import urllib.request
import zipfile
from pathlib import Path

# Blockgroesse des Lesecaches. Gross halten: bei 1 MiB kostet der Overhead je
# Range-Request mehr als die Uebertragung selbst (gemessen 200 kB/s gegenueber
# 970 kB/s bei einem einzigen grossen Request auf denselben Server).
CHUNK = 8 << 20   # 8 MiB


class HttpFile(io.RawIOBase):
    """Nur-Lese-Datei ueber HTTP-Range-Requests, blockweise gepuffert."""

    def __init__(self, url, timeout=300, chunk=CHUNK):
        self.url = url
        self.timeout = timeout
        self.chunk = chunk
        self._pos = 0
        self._cache = {}
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            self.size = int(r.headers["Content-Length"])
            self.url = r.url                      # Weiterleitung uebernehmen
        # Ein Range-Request muss beantwortet werden, sonst laedt zipfile still
        # die ganze Datei -- lieber sofort scheitern als 4,7 GB unbemerkt ziehen.
        if self._fetch(0, 16) is None:
            raise SystemExit("Server unterstuetzt keine Range-Requests")

    def _fetch(self, start, length, tries=6):
        """Einen Block holen -- mit Wiederholung.

        Ueber Hunderte Requests reisst frueher oder spaeter einer ab
        (IncompleteRead, Timeout). Ohne Wiederholung ist dann der halbe Download
        verloren; ein Range-Request laesst sich aber verlustfrei neu stellen.
        Geprueft wird auch die LAENGE: ein zu kurz gelieferter Block wuerde sonst
        still als gueltige Daten ins Archiv wandern.
        """
        end = min(start + length, self.size) - 1
        if end < start:
            return b""
        want = end - start + 1
        for attempt in range(tries):
            try:
                req = urllib.request.Request(
                    self.url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    if r.status != 206:
                        return None
                    data = r.read()
                if len(data) == want:
                    return data
                raise OSError(f"{len(data)} statt {want} Bytes")
            except Exception as e:
                if attempt == tries - 1:
                    raise
                wait = 2 ** attempt
                print(f"    Block {start}: {type(e).__name__} ({e}) -- "
                      f"Versuch {attempt+2}/{tries} in {wait}s", flush=True)
                time.sleep(wait)
        return None

    def _block(self, idx):
        if idx not in self._cache:
            if len(self._cache) > 64:             # Cache begrenzen
                self._cache.clear()
            self._cache[idx] = self._fetch(idx * self.chunk, self.chunk)
        return self._cache[idx]

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self.size}[whence]
        self._pos = max(0, min(base + offset, self.size))
        return self._pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self._pos
        n = min(n, self.size - self._pos)
        out = bytearray()
        while n > 0:
            idx = self._pos // self.chunk
            off = self._pos % self.chunk
            blk = self._block(idx)
            take = blk[off:off + n]
            if not take:
                break
            out += take
            self._pos += len(take)
            n -= len(take)
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--list", action="store_true", help="Inhaltsverzeichnis zeigen")
    ap.add_argument("--filter", default="", help="nur Namen mit diesem Text listen")
    ap.add_argument("--extract", nargs="+", help="Eintraege (exakter Name im Zip)")
    ap.add_argument("--out", default=".", help="Zielverzeichnis fuer --extract")
    args = ap.parse_args()

    hf = HttpFile(args.url)
    print(f"Archiv {hf.size/1e9:.2f} GB, Range-Requests OK")
    zf = zipfile.ZipFile(hf)
    infos = zf.infolist()
    print(f"{len(infos)} Eintraege im Verzeichnis")

    if args.list:
        for i in infos:
            if args.filter and args.filter.lower() not in i.filename.lower():
                continue
            print(f"  {i.file_size/1e6:9.1f} MB  {i.filename}")

    if args.extract:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        names = {i.filename for i in infos}
        for name in args.extract:
            if name not in names:
                print(f"  !! nicht im Archiv: {name}")
                continue
            info = zf.getinfo(name)
            dst = out / Path(name).name
            print(f"  lade {name} ({info.file_size/1e6:.1f} MB) -> {dst}", flush=True)
            done, t0 = 0, time.time()
            with zf.open(info) as src, open(dst, "wb") as fh:
                while True:
                    buf = src.read(4 << 20)
                    if not buf:
                        break
                    fh.write(buf)
                    done += len(buf)
                    dt = max(time.time() - t0, 1e-6)
                    print(f"    {done/1e6:7.1f}/{info.file_size/1e6:.1f} MB "
                          f"({100*done/info.file_size:4.1f}%, {done/dt/1e3:.0f} kB/s)",
                          flush=True)
        print(f"-> {out}")


if __name__ == "__main__":
    main()
