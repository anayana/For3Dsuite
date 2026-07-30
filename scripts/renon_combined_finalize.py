#!/usr/bin/env python3
"""renon_combined_finalize.py -- Abschluss-Schritt fuer die renon-combined-Szene.

Drei Aufraeumungen auf der fertig angereicherten Szene:
  1. entfernt den BHD-Methodenvergleich (dbh_benchmark) aus den Markern
  2. wirft Fehldetektionen raus (BHD_Guete == 'unsicher' -- Detektionen ohne
     verlaesslichen Stamm; 'gut' und 'schwach' bleiben als echte Baeume)
  3. haengt die VOLLE TreeGrOSS-Perioden-Serie je Baum an (prognosis_series),
     damit der Viewer einen Zeithorizont-Regler statt eines festen Jahres zeigt

  python scripts/renon_combined_finalize.py <scene.json> <tg_future.json>
"""
import json
import sys
from pathlib import Path

scene_p, future_p = Path(sys.argv[1]), Path(sys.argv[2])
scene = json.loads(scene_p.read_text(encoding="utf-8"))
fut = json.loads(future_p.read_text(encoding="utf-8"))

# id -> [{year, dbh_cm, height_m, alive}]
series = {}
for per in fut.get("periods", []):
    y = per["year"]
    for t in per.get("trees", []):
        series.setdefault(t["id"], []).append({
            "year": y,
            "dbh_cm": round(float(t["dbh_cm"]), 1) if t.get("dbh_cm") is not None else None,
            "height_m": round(float(t["height_m"]), 1) if t.get("height_m") is not None else None,
            "alive": bool(t.get("alive", True))})

kept, dropped = [], 0
for m in scene.get("markers", []):
    if m.get("attributes", {}).get("BHD_Guete") == "unsicher":
        dropped += 1
        continue
    m.pop("dbh_benchmark", None)                 # BHD-Methodenvergleich raus
    m.pop("prognosis", None)                      # festes Einzeljahr ersetzen ...
    s = series.get(m["id"])
    if s:
        m["prognosis_series"] = s                # ... durch die volle Serie
    kept.append(m)

scene["markers"] = kept
scene_p.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(kept)} Baeume behalten, {dropped} Fehldetektionen (unsicher) entfernt; "
      f"{sum('prognosis_series' in m for m in kept)} mit Prognose-Serie")
