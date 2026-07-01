"""
=====================================================================
 슬라이드 10 · 데이터베이스 설계 (ERD → SQLite 스키마)
=====================================================================
VMS가 다루는 데이터를 5개 테이블로 설계한다. 관계(ERD):

  cameras ──1:N──> recordings      (한 카메라에 여러 녹화)
  cameras ──1:N──> detections      (한 카메라에 여러 검출)
  cameras ──1:N──> event_rules     (한 카메라에 여러 이벤트 규칙)
  event_rules ──1:N──> events      (한 규칙이 여러 이벤트 발생)

설계 원칙:
 - PK(기본키)는 AUTOINCREMENT 정수, FK(외래키)로 카메라와 연결.
 - JSON이 필요한 가변 데이터(bbox 좌표)는 TEXT에 JSON 문자열로.
 - 단일 DB(SQLite 파일 하나) — 이중화 안 함(슬라이드 31 안티패턴).

실행:  python 10_database.py    (스키마 생성 + 샘플 데이터 + 관계 조회 시연)
=====================================================================
"""
import os
import json
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "vms_schema_demo.db")


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")     # FK 제약 활성화
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS cameras (
    camera_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    rtsp_url   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'offline',   -- online / offline
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recordings (
    rec_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id  INTEGER NOT NULL REFERENCES cameras(camera_id),
    file_path  TEXT NOT NULL UNIQUE,
    start_time TEXT NOT NULL,
    end_time   TEXT
);

CREATE TABLE IF NOT EXISTS detections (
    det_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id  INTEGER NOT NULL REFERENCES cameras(camera_id),
    label      TEXT NOT NULL,           -- person / car ...
    confidence REAL NOT NULL,
    bbox       TEXT NOT NULL,           -- JSON [x1,y1,x2,y2]
    ts         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_rules (
    rule_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id      INTEGER NOT NULL REFERENCES cameras(camera_id),
    object         TEXT NOT NULL,
    min_confidence REAL NOT NULL DEFAULT 0.5,
    cooldown_sec   INTEGER NOT NULL DEFAULT 30,
    enabled        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS events (
    event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id  INTEGER NOT NULL REFERENCES cameras(camera_id),
    rule_id    INTEGER REFERENCES event_rules(rule_id),
    label      TEXT NOT NULL,
    confidence REAL,
    snapshot   TEXT,
    ts         TEXT NOT NULL,
    acked      INTEGER NOT NULL DEFAULT 0    -- 0:미확인 1:확인
);
"""


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)


def now():
    return datetime.now().isoformat(timespec="seconds")


# ── 실행: 스키마 생성 + 샘플 데이터 + 관계(JOIN) 조회 ────────────
if __name__ == "__main__":
    if os.path.exists(DB):
        os.remove(DB)
    init_db()

    with conn() as c:
        # 1) 카메라
        cid = c.execute("INSERT INTO cameras(name,rtsp_url,status,created_at) VALUES(?,?,?,?)",
                        ("창고 Camera 01", "rtsp://192.168.0.10/stream", "online", now())).lastrowid
        # 2) 규칙
        rid = c.execute("INSERT INTO event_rules(camera_id,object,min_confidence,cooldown_sec)"
                        " VALUES(?,?,?,?)", (cid, "person", 0.5, 30)).lastrowid
        # 3) 검출 (bbox는 JSON)
        c.execute("INSERT INTO detections(camera_id,label,confidence,bbox,ts) VALUES(?,?,?,?,?)",
                  (cid, "person", 0.81, json.dumps([1325, 127, 1424, 372]), now()))
        # 4) 이벤트 (규칙에서 발생)
        c.execute("INSERT INTO events(camera_id,rule_id,label,confidence,ts) VALUES(?,?,?,?,?)",
                  (cid, rid, "person", 0.81, now()))
        # 5) 녹화
        c.execute("INSERT INTO recordings(camera_id,file_path,start_time,end_time) VALUES(?,?,?,?)",
                  (cid, "/rec/1/20260701_090000.mp4", "2026-07-01T09:00:00", "2026-07-01T09:01:00"))

    # 테이블 목록
    with conn() as c:
        tbls = [r["name"] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        print("[생성된 테이블]", tbls)

        # 관계 조회: 카메라 + 그 카메라의 이벤트 (FK JOIN)
        print("\n[JOIN — 카메라별 이벤트]")
        rows = c.execute("""
            SELECT cam.name, e.label, e.confidence, e.ts
            FROM events e JOIN cameras cam ON cam.camera_id = e.camera_id
        """).fetchall()
        for r in rows:
            print("  ", dict(r))

    os.remove(DB)   # 데모 정리
    print("\n✅ 스키마·관계 확인 완료")

# 👉 실제 완성본: vms/app/db.py (같은 스키마 + insert/query 함수들)
