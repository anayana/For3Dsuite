"""SQLite-basierte Job-Queue mit einem Worker-Thread.

Bewusst ohne Redis/Celery: ein Selfhosting-Stack soll mit drei Containern
auskommen, und die Pipeline-Jobs sind langlaufend und seriell (CPU-bound).
"""
import json
import sqlite3
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._lock = threading.Lock()
        with self._conn() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, scene_id TEXT, type TEXT, status TEXT,
                params TEXT, log TEXT DEFAULT '', created TEXT, updated TEXT)""")
            # Nach einem Neustart haengen gebliebene Jobs zuruecksetzen
            con.execute("UPDATE jobs SET status='queued' WHERE status='running'")

    def _conn(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _to_dict(row):
        d = dict(row)
        d["params"] = json.loads(d["params"] or "{}")
        return d

    def create(self, scene_id, jtype, params):
        jid = uuid.uuid4().hex[:12]
        now = utcnow()
        with self._conn() as con:
            con.execute(
                "INSERT INTO jobs(id, scene_id, type, status, params, log, created, updated) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (jid, scene_id, jtype, "queued", json.dumps(params), "", now, now))
        return self.get(jid)

    def get(self, jid):
        with self._conn() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        return self._to_dict(row) if row else None

    def list(self, limit=50):
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [self._to_dict(r) for r in rows]

    def claim_next(self):
        with self._lock, self._conn() as con:
            row = con.execute(
                "SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            con.execute("UPDATE jobs SET status='running', updated=? WHERE id=?",
                        (utcnow(), row["id"]))
        return self.get(row["id"])

    def append_log(self, jid, line):
        with self._conn() as con:
            con.execute("UPDATE jobs SET log = log || ?, updated=? WHERE id=?",
                        (line.rstrip("\n") + "\n", utcnow(), jid))

    def finish(self, jid, status):
        with self._conn() as con:
            con.execute("UPDATE jobs SET status=?, updated=? WHERE id=?",
                        (status, utcnow(), jid))


def start_worker(store, runner):
    """Startet den Verarbeitungs-Thread. `runner(job, log)` macht die Arbeit."""
    def loop():
        while True:
            job = store.claim_next()
            if job is None:
                time.sleep(1.0)
                continue
            def log(line, _jid=job["id"]):
                store.append_log(_jid, str(line))
            try:
                log(f"Job {job['id']} ({job['type']}, Szene {job['scene_id']}) gestartet")
                runner(job, log)
                store.finish(job["id"], "done")
                log("Fertig.")
            except Exception:
                store.append_log(job["id"], traceback.format_exc())
                store.finish(job["id"], "error")

    t = threading.Thread(target=loop, daemon=True, name="pipeline-worker")
    t.start()
    return t
