"""VMS SQLite — cameras / recordings / detections / event_rules / events."""
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "vms.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def now():
    return datetime.now().isoformat(timespec="seconds")


def init_db():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                rtsp_url   TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'offline',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recordings (
                rec_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id  INTEGER NOT NULL,
                file_path  TEXT NOT NULL UNIQUE,
                start_time TEXT NOT NULL,
                end_time   TEXT
            );
            CREATE TABLE IF NOT EXISTS detections (
                det_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id  INTEGER NOT NULL,
                label      TEXT NOT NULL,
                confidence REAL NOT NULL,
                bbox       TEXT NOT NULL,
                ts         TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_rules (
                rule_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id      INTEGER NOT NULL,
                object         TEXT NOT NULL,
                min_confidence REAL NOT NULL DEFAULT 0.5,
                cooldown_sec   INTEGER NOT NULL DEFAULT 30,
                enabled        INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id  INTEGER NOT NULL,
                rule_id    INTEGER,
                label      TEXT NOT NULL,
                confidence REAL,
                snapshot   TEXT,
                ts         TEXT NOT NULL,
                acked      INTEGER NOT NULL DEFAULT 0
            );
            """
        )


# ---------- cameras ----------
def add_camera(name, rtsp_url):
    with _conn() as c:
        return c.execute("INSERT INTO cameras (name, rtsp_url, status, created_at) VALUES (?,?,?,?)",
                         (name, rtsp_url, "offline", now())).lastrowid


def list_cameras():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM cameras ORDER BY camera_id").fetchall()]


def get_camera(cid):
    with _conn() as c:
        r = c.execute("SELECT * FROM cameras WHERE camera_id=?", (cid,)).fetchone()
        return dict(r) if r else None


def set_status(cid, status):
    with _conn() as c:
        c.execute("UPDATE cameras SET status=? WHERE camera_id=?", (status, cid))


# ---------- recordings ----------
def register_recording(camera_id, file_path, start_time, end_time=None):
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO recordings (camera_id,file_path,start_time,end_time)"
                  " VALUES (?,?,?,?)", (camera_id, file_path, start_time, end_time))


def list_recordings(camera_id=None, start=None, end=None):
    q, p = "SELECT * FROM recordings", []
    where = []
    if camera_id:
        where.append("camera_id=?"); p.append(camera_id)
    if start:
        where.append("start_time>=?"); p.append(start)
    if end:
        where.append("start_time<=?"); p.append(end)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY start_time DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, p).fetchall()]


# ---------- detections ----------
def insert_detection(cid, label, conf, bbox):
    with _conn() as c:
        c.execute("INSERT INTO detections (camera_id,label,confidence,bbox,ts) VALUES (?,?,?,?,?)",
                  (cid, label, conf, json.dumps(bbox), now()))


def recent_detections(cid, limit=20):
    with _conn() as c:
        rows = c.execute("SELECT * FROM detections WHERE camera_id=? ORDER BY det_id DESC LIMIT ?",
                         (cid, limit)).fetchall()
    return [{**dict(r), "bbox": json.loads(r["bbox"])} for r in rows]


# ---------- rules ----------
def add_rule(cid, obj, min_conf=0.5, cooldown=30):
    with _conn() as c:
        return c.execute("INSERT INTO event_rules (camera_id,object,min_confidence,cooldown_sec) VALUES (?,?,?,?)",
                         (cid, obj, min_conf, cooldown)).lastrowid


def get_rules(cid):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM event_rules WHERE camera_id=? AND enabled=1", (cid,)).fetchall()]


def all_rules():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM event_rules ORDER BY rule_id").fetchall()]


# ---------- events ----------
def insert_event(cid, rule_id, label, conf, snapshot):
    with _conn() as c:
        return c.execute("INSERT INTO events (camera_id,rule_id,label,confidence,snapshot,ts) VALUES (?,?,?,?,?,?)",
                         (cid, rule_id, label, conf, snapshot, now())).lastrowid


def list_events(limit=50, camera_id=None):
    q = "SELECT * FROM events"
    p = []
    if camera_id:
        q += " WHERE camera_id=?"; p.append(camera_id)
    q += " ORDER BY event_id DESC LIMIT ?"; p.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, p).fetchall()]


def ack_event(eid):
    with _conn() as c:
        c.execute("UPDATE events SET acked=1 WHERE event_id=?", (eid,))
