"""Herkunft (Provenienz) je Layer: woher, wann, wie verarbeitet. Grundsatz: pruefbar, Herkunft ausgewiesen."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class LayerRecord:
    name: str
    source: str              # z. B. "Sentinel-2 L2A (Earth Search)", "Nutzerdatei"
    group: str               # structure, spectral, topography, landcover, intensity, climate, access, other
    origin: str = ""         # Pfad oder URL
    license: str = ""
    processing: list[str] = field(default_factory=list)
    date_range: str = ""
    created: str = field(default_factory=lambda: _dt.datetime.now().isoformat(timespec="seconds"))
    checksum: str = ""
    kind: str = "continuous"  # continuous | categorical | binary


class Provenance:
    def __init__(self):
        self.records: dict[str, LayerRecord] = {}

    def add(self, rec: LayerRecord):
        self.records[rec.name] = rec
        return rec

    def to_list(self):
        return [asdict(r) for r in self.records.values()]

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_list(), indent=2, ensure_ascii=False), encoding="utf-8")


def file_checksum(path, nbytes: int = 1 << 20) -> str:
    """SHA-256 der ersten MiB plus Dateigroesse (schnell, reicht zum Wiedererkennen)."""
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read(nbytes))
    h.update(str(p.stat().st_size).encode())
    return h.hexdigest()[:16]
