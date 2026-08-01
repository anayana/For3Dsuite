#!/usr/bin/env python3
"""eval_runtime.py -- Laufzeit der Kette je Eingangsklasse, End-zu-Ende.

Misst, was Abschnitt 5.3 des Papers verlangt: die Zeit von der Uebergabe der
Aufnahmen bis zur veroeffentlichten, begehbaren Szene -- und zwar durch den
LAUFENDEN Dienst, nicht durch Einzelaufrufe der Skripte. Damit sind Upload,
Warteschlange, Verarbeitung und Veroeffentlichung enthalten, so wie ein Anwender
sie erlebt.

Gemessen wird je Eingangsklasse getrennt, weil sie voellig verschieden teuer sind:

  equirect  fertiges 360-Grad-Bild (Consumer-Kamera)   -- nur uebernehmen
  fisheye   mehrere Einzelaufnahmen ohne Pose          -- Hugin-Stitching
  e57       Laserscan mit Posen                        -- Reprojektion + Punktwolke

Die Autoerkennung bekommt KEINEN Typ mitgeteilt; welcher Zweig lief, steht
hinterher im Job-Log und wird mitberichtet.

  python scripts/eval_runtime.py --base http://localhost --user admin --password ...
"""
import argparse
import json
import statistics as st
import time
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def post_files(base, auth, scene_id, files, title):
    """Multipart-Upload ohne Fremdbibliothek."""
    boundary = "----for3d" + uuid.uuid4().hex
    body = bytearray()
    for k, v in (("scene_id", scene_id), ("title", title), ("description", "Laufzeitmessung")):
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                 f"{v}\r\n").encode()
    for p in files:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
                 f"filename=\"{p.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
                 ).encode()
        body += p.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{base}/api/studio/upload", data=bytes(body),
                                 method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", auth)
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())["job"]


def job(base, auth, jid):
    req = urllib.request.Request(f"{base}/api/studio/jobs/{jid}")
    req.add_header("Authorization", auth)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def run_case(base, auth, name, files, mb):
    sid = f"rt-{name}-{uuid.uuid4().hex[:6]}"
    t0 = time.time()
    j = post_files(base, auth, sid, files, f"Laufzeit {name}")
    t_upload = time.time() - t0
    while True:
        d = job(base, auth, j["id"])
        if d["status"] in ("done", "error"):
            break
        time.sleep(1.0)
    total = time.time() - t0
    log = d.get("log") or ""
    zweig = "?"
    for line in log.splitlines():
        if "Eingangsklasse erkannt" in line:
            zweig = line.split(":", 1)[1].split("(")[0].strip()
    return {"klasse": name, "szene": sid, "status": d["status"],
            "aufnahmen": len(files), "eingang_mb": round(mb, 1),
            "upload_s": round(t_upload, 1), "gesamt_s": round(total, 1),
            "verarbeitung_s": round(total - t_upload, 1),
            "erkannter_zweig": zweig}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--repeat", type=int, default=1, help="Wiederholungen je Klasse")
    ap.add_argument("--out", default=str(REPO / "data" / "_eval" / "laufzeit.json"))
    ap.add_argument("--skip-e57", action="store_true")
    args = ap.parse_args()

    import base64
    auth = "Basic " + base64.b64encode(
        f"{args.user}:{args.password}".encode()).decode()

    cases = []
    eq = REPO / "platform/dev-data/media/scenes/consumer360-chopfholz-wald/pano.jpg"
    if eq.is_file():
        cases.append(("equirect", [eq]))
    fish = sorted((REPO / "data/_eval/real_passta").glob("*.jpg"))
    if fish:
        cases.append(("fisheye", fish))
    e57 = sorted((REPO / "data/Renon/e57").glob("*.e57"))
    if e57 and not args.skip_e57:
        cases.append(("e57", e57[:1]))
    if not cases:
        raise SystemExit("Keine Eingaben gefunden")

    rows = []
    for name, files in cases:
        mb = sum(p.stat().st_size for p in files) / 1e6
        for i in range(args.repeat):
            print(f"[{name}] {len(files)} Datei(en), {mb:.1f} MB "
                  f"(Lauf {i+1}/{args.repeat}) ...", flush=True)
            r = run_case(args.base, auth, name, files, mb)
            rows.append(r)
            print(f"    {r['status']}  Upload {r['upload_s']:.1f}s  "
                  f"Verarbeitung {r['verarbeitung_s']:.1f}s  "
                  f"gesamt {r['gesamt_s']:.1f}s  Zweig: {r['erkannter_zweig']}",
                  flush=True)

    Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\n-> {args.out}")
    print(f"\n{'Klasse':10} {'Aufn.':>6} {'MB':>7} {'Upload':>8} {'Verarb.':>9} {'gesamt':>8}")
    for name in dict.fromkeys(r["klasse"] for r in rows):
        sel = [r for r in rows if r["klasse"] == name and r["status"] == "done"]
        if not sel:
            print(f"{name:10} -- kein erfolgreicher Lauf")
            continue
        med = lambda k: st.median([r[k] for r in sel])       # noqa: E731
        print(f"{name:10} {sel[0]['aufnahmen']:>6} {sel[0]['eingang_mb']:>7.1f} "
              f"{med('upload_s'):>7.1f}s {med('verarbeitung_s'):>8.1f}s "
              f"{med('gesamt_s'):>7.1f}s")


if __name__ == "__main__":
    main()
