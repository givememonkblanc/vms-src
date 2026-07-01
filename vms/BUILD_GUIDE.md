# 🛠️ VMS 단계별 빌드 가이드 (소스코드)

슬라이드(CH2)의 각 개념을 **바이브 코딩으로 만들 때 나오는 실제 소스코드**입니다. 위에서부터 순서대로 만들면 VMS가 완성됩니다.

```
vms/
 ├─ app.py                  # 엔트리
 ├─ app/__init__.py         # App Factory + 블루프린트
 ├─ app/config.py · db.py   # 설정 / SQLite
 ├─ app/routes/             # cameras·stream·detection·events·recordings·health·web
 ├─ app/services/           # hls·recording·detection·event
 └─ templates/dashboard.html
```

실행: `pip install -r requirements.txt` (+ ffmpeg) → `python app.py` → http://localhost:8000

---

## STEP 1 · Flask 앱 구조  
<sub>📊 슬라이드 20</sub>

**무엇을 만드나** — create_app()으로 앱 뼈대를 만들고, 설정·DB·블루프린트(라우터)를 등록한다.

> 🤖 **바이브 코딩 지시 예**  
> “설계(아키텍처·기능정의서)대로 Flask App Factory와 cameras·stream·detection·events·health 블루프린트 뼈대를 만들어줘”

#### `app/config.py`

```python
"""VMS 설정 — .env에서 로드."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent.parent


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    PORT = int(os.getenv("PORT", "8000"))

    # HLS / 녹화 저장 경로
    HLS_DIR = str(BASE / "static" / "hls")
    REC_DIR = str(BASE / "recordings")
    HLS_TIME = int(os.getenv("HLS_TIME", "2"))          # 세그먼트 길이(초)
    HLS_LIST_SIZE = int(os.getenv("HLS_LIST_SIZE", "6"))

    # 객체 검출 (YOLO)
    DETECTOR_WEIGHTS = os.getenv("DETECTOR_WEIGHTS", "yolo11n.pt")
    DETECT_CLASSES = [int(x) for x in os.getenv("DETECT_CLASSES", "0,2").split(",")]  # person,car
    DETECT_CONF = float(os.getenv("DETECT_CONF", "0.4"))
    FRAME_SKIP = int(os.getenv("FRAME_SKIP", "15"))
    DEVICE = os.getenv("DEVICE") or None

    REC_SEGMENT_TIME = int(os.getenv("REC_SEGMENT_TIME", "60"))   # 녹화 파일 1개 길이(초)

    DB_PATH = os.getenv("DB_PATH", str(BASE / "vms.db"))
```

#### `app/db.py`

```python
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
```

#### `app/__init__.py`

```python
"""VMS App Factory — 카메라·스트림·검출·이벤트 + 웹 대시보드."""
import os

from flask import Flask

from . import db
from .config import BASE, Config
from .routes.cameras import cameras_bp
from .routes.detection import detection_bp
from .routes.events import events_bp
from .routes.health import health_bp
from .routes.recordings import recordings_bp
from .routes.stream import stream_bp
from .routes.web import web_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(BASE / "static"), static_url_path="/static",
        template_folder=str(BASE / "templates"),
    )
    app.config.from_object(Config)
    os.makedirs(app.config["HLS_DIR"], exist_ok=True)
    os.makedirs(app.config["REC_DIR"], exist_ok=True)
    db.init_db()

    app.register_blueprint(web_bp)                                   # /
    app.register_blueprint(cameras_bp, url_prefix="/api/cameras")
    app.register_blueprint(stream_bp, url_prefix="/api/stream")
    app.register_blueprint(recordings_bp, url_prefix="/api/recordings")
    app.register_blueprint(detection_bp, url_prefix="/api/detection")
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(health_bp, url_prefix="/api/health")
    return app
```

#### `app/routes/health.py`

```python
"""헬스체크."""
from flask import Blueprint, jsonify

from .. import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def health():
    return jsonify({"status": "healthy", "cameras": len(db.list_cameras())})
```

#### `app.py`

```python
"""엔트리포인트 — create_app()으로 앱 생성 후 실행.

  python app.py            # http://0.0.0.0:8000
포트는 .env(PORT)로 관리 → docker-compose 매핑과 반드시 일치시킨다.
"""
from app import create_app

flask_app = create_app()

if __name__ == "__main__":
    port = flask_app.config["PORT"]
    flask_app.run(host="0.0.0.0", port=port, debug=flask_app.config["DEBUG"],
                  use_reloader=False)
```

---

## STEP 2 · RTSP → HLS 스트리밍  
<sub>📊 슬라이드 21</sub>

**무엇을 만드나** — 카메라 RTSP를 ffmpeg로 HLS(.m3u8/.ts)로 변환해 브라우저가 재생하게 한다.

> 🤖 **바이브 코딩 지시 예**  
> “RTSP를 ffmpeg로 HLS로 변환하는 hls_service와, 시작/중지하는 /api/stream 라우터를 만들어줘 (force_key_frames로 첫 세그먼트 보장)”

#### `app/services/hls_service.py`

```python
"""RTSP → HLS 변환 — 카메라별 ffmpeg 프로세스 관리."""
import os
import subprocess

_procs = {}   # camera_id -> Popen


def _build_cmd(source, m3u8, seg_time, list_size):
    inp = ["-rtsp_transport", "tcp", "-i", source] if source.startswith("rtsp") \
        else ["-stream_loop", "-1", "-re", "-i", source]   # 파일은 반복 재생(데모)
    return ["ffmpeg", "-y", *inp,
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            # 세그먼트 경계마다 키프레임 강제 → 첫 세그먼트가 제때 닫힘
            "-force_key_frames", f"expr:gte(t,n_forced*{seg_time})",
            "-an", "-f", "hls",
            "-hls_time", str(seg_time), "-hls_list_size", str(list_size),
            "-hls_flags", "delete_segments", m3u8]


def start(camera_id, source, hls_dir, seg_time=2, list_size=6):
    cid = str(camera_id)
    p = _procs.get(cid)
    if p and p.poll() is None:
        return f"/static/hls/{cid}/index.m3u8"
    out_dir = os.path.join(hls_dir, cid)
    os.makedirs(out_dir, exist_ok=True)
    m3u8 = os.path.join(out_dir, "index.m3u8")
    _procs[cid] = subprocess.Popen(_build_cmd(source, m3u8, seg_time, list_size),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"/static/hls/{cid}/index.m3u8"


def stop(camera_id):
    cid = str(camera_id)
    p = _procs.pop(cid, None)
    if p and p.poll() is None:
        p.terminate()


def is_running(camera_id):
    p = _procs.get(str(camera_id))
    return bool(p and p.poll() is None)
```

#### `app/routes/stream.py`

```python
"""스트리밍 라우터 — 카메라 RTSP를 HLS로 변환 시작/중지. (.m3u8/.ts는 /static/hls/ 로 제공)"""
from flask import Blueprint, current_app, jsonify

from .. import db
from ..services import hls_service

stream_bp = Blueprint("stream", __name__)


@stream_bp.post("/<int:cid>/start")
def start(cid):
    cam = db.get_camera(cid)
    if not cam:
        return jsonify({"error": "카메라 없음"}), 404
    cfg = current_app.config
    url = hls_service.start(cid, cam["rtsp_url"], cfg["HLS_DIR"],
                            cfg["HLS_TIME"], cfg["HLS_LIST_SIZE"])
    db.set_status(cid, "online")
    return jsonify({"camera_id": cid, "hls_url": url})


@stream_bp.post("/<int:cid>/stop")
def stop(cid):
    hls_service.stop(cid)
    db.set_status(cid, "offline")
    return jsonify({"camera_id": cid, "stopped": True})
```

---

## STEP 3 · 영상 관리 — 카메라·녹화·재생  
<sub>📊 슬라이드 22</sub>

**무엇을 만드나** — 카메라 CRUD + ffmpeg 세그먼트 녹화 + 기간 검색·재생을 만든다.

> 🤖 **바이브 코딩 지시 예**  
> “카메라 CRUD API와, ffmpeg 세그먼트로 녹화해 기간으로 검색·재생하는 recordings API를 만들어줘”

#### `app/routes/cameras.py`

```python
"""카메라 관리 라우터."""
from flask import Blueprint, jsonify, request

from .. import db

cameras_bp = Blueprint("cameras", __name__)


@cameras_bp.get("")
@cameras_bp.get("/")
def list_cameras():
    return jsonify({"cameras": db.list_cameras()})


@cameras_bp.post("")
@cameras_bp.post("/")
def add_camera():
    b = request.get_json(silent=True) or {}
    if not b.get("name") or not b.get("rtsp_url"):
        return jsonify({"error": "name, rtsp_url 필요"}), 400
    cid = db.add_camera(b["name"], b["rtsp_url"])
    return jsonify(db.get_camera(cid)), 201


@cameras_bp.get("/<int:cid>")
def get_camera(cid):
    cam = db.get_camera(cid)
    return (jsonify(cam), 200) if cam else (jsonify({"error": "not found"}), 404)
```

#### `app/services/recording_service.py`

```python
"""녹화 — ffmpeg 세그먼트 muxer로 영상을 타임스탬프 mp4 파일로 저장."""
import glob
import os
import re
import subprocess
from datetime import datetime, timedelta

from .. import db

_procs = {}   # camera_id -> Popen
_NAME = re.compile(r"(\d{8})_(\d{6})\.mp4$")


def start_recording(camera_id, source, rec_dir, segment_time=60):
    cid = str(camera_id)
    p = _procs.get(cid)
    if p and p.poll() is None:
        return
    out = os.path.join(rec_dir, cid)
    os.makedirs(out, exist_ok=True)
    inp = ["-rtsp_transport", "tcp", "-i", source] if str(source).startswith("rtsp") else ["-i", source]
    pattern = os.path.join(out, "%Y%m%d_%H%M%S.mp4")
    cmd = ["ffmpeg", "-y", *inp, "-c", "copy", "-f", "segment",
           "-segment_time", str(segment_time), "-reset_timestamps", "1",
           "-strftime", "1", pattern]
    _procs[cid] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_recording(camera_id):
    p = _procs.pop(str(camera_id), None)
    if p and p.poll() is None:
        p.terminate()


def is_recording(camera_id):
    p = _procs.get(str(camera_id))
    return bool(p and p.poll() is None)


def scan_and_register(camera_id, rec_dir, segment_time=60):
    """디스크의 녹화 파일을 DB에 등록(파일명 타임스탬프 → start/end)."""
    out = os.path.join(rec_dir, str(camera_id))
    for f in sorted(glob.glob(os.path.join(out, "*.mp4"))):
        m = _NAME.search(os.path.basename(f))
        if not m:
            continue
        start = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        end = start + timedelta(seconds=segment_time)
        name = os.path.basename(f)
        db.register_recording(camera_id, f"/api/recordings/file/{camera_id}/{name}",
                              start.isoformat(timespec="seconds"),
                              end.isoformat(timespec="seconds"))
```

#### `app/routes/recordings.py`

```python
"""녹화 라우터 — 녹화 시작/중지 + 기간 검색 + 재생 파일 제공."""
import os

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from .. import db
from ..services import recording_service

recordings_bp = Blueprint("recordings", __name__)


@recordings_bp.post("/<int:cid>/start")
def start(cid):
    cam = db.get_camera(cid)
    if not cam:
        return jsonify({"error": "카메라 없음"}), 404
    cfg = current_app.config
    recording_service.start_recording(cid, cam["rtsp_url"], cfg["REC_DIR"], cfg["REC_SEGMENT_TIME"])
    return jsonify({"camera_id": cid, "recording": True})


@recordings_bp.post("/<int:cid>/stop")
def stop(cid):
    recording_service.stop_recording(cid)
    return jsonify({"camera_id": cid, "recording": False})


@recordings_bp.get("")
@recordings_bp.get("/")
def list_recordings():
    cfg = current_app.config
    cid = request.args.get("camera_id", type=int)
    if cid:                      # 디스크 새 파일을 DB에 반영 후 조회
        recording_service.scan_and_register(cid, cfg["REC_DIR"], cfg["REC_SEGMENT_TIME"])
    return jsonify({"recordings": db.list_recordings(cid, request.args.get("from"),
                                                     request.args.get("to"))})


@recordings_bp.get("/file/<int:cid>/<path:fname>")
def serve(cid, fname):
    return send_from_directory(os.path.join(current_app.config["REC_DIR"], str(cid)), fname)
```

---

## STEP 4 · AI 객체 검출  
<sub>📊 슬라이드 23</sub>

**무엇을 만드나** — 프레임을 샘플링해 YOLO로 객체를 검출하고 저장한다(백그라운드 스레드).

> 🤖 **바이브 코딩 지시 예**  
> “프레임을 샘플링해 YOLO로 사람·차량을 검출하고 결과를 저장하는 백그라운드 detection_service와 /api/detection 라우터를 만들어줘”

#### `app/services/detection_service.py`

```python
"""객체 검출 — 카메라별 백그라운드 스레드에서 YOLO 실행 → 검출 저장 + 이벤트 체크."""
import os
import threading

import cv2

from .. import db
from . import event_service

_model = None
_threads = {}   # camera_id -> Thread
_stop = {}      # camera_id -> bool


def _get_model(cfg):
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(cfg["DETECTOR_WEIGHTS"])
    return _model


def start(camera_id, source, cfg):
    cid = str(camera_id)
    if _threads.get(cid) and _threads[cid].is_alive():
        return
    _stop[cid] = False
    t = threading.Thread(target=_loop, args=(camera_id, source, dict(cfg)), daemon=True)
    _threads[cid] = t
    t.start()


def stop(camera_id):
    _stop[str(camera_id)] = True


def is_running(camera_id):
    t = _threads.get(str(camera_id))
    return bool(t and t.is_alive())


def _loop(camera_id, source, cfg):
    cid = str(camera_id)
    model = _get_model(cfg)
    snap_dir = os.path.join(cfg["HLS_DIR"], "_snapshots")
    cap = cv2.VideoCapture(source)
    skip, idx = cfg["FRAME_SKIP"], 0
    while not _stop.get(cid):
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % skip:
            continue
        r = model.predict(frame, classes=cfg["DETECT_CLASSES"],
                          conf=cfg["DETECT_CONF"], device=cfg["DEVICE"], verbose=False)[0]
        for b in r.boxes:
            label = model.names[int(b.cls[0])]
            conf = round(float(b.conf[0]), 3)
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            db.insert_detection(camera_id, label, conf, [x1, y1, x2, y2])
            event_service.check(camera_id, label, conf, frame, snap_dir)
    cap.release()


def run_once(camera_id, source, cfg, max_frames=40):
    """동기 1회 분석(데모/테스트용) — 검출·이벤트 수 반환."""
    model = _get_model(cfg)
    snap_dir = os.path.join(cfg["HLS_DIR"], "_snapshots")
    cap = cv2.VideoCapture(source)
    skip, idx, n_det, n_evt = cfg["FRAME_SKIP"], 0, 0, 0
    while idx < max_frames * skip:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % skip:
            continue
        r = model.predict(frame, classes=cfg["DETECT_CLASSES"],
                          conf=cfg["DETECT_CONF"], device=cfg["DEVICE"], verbose=False)[0]
        for b in r.boxes:
            label = model.names[int(b.cls[0])]
            conf = round(float(b.conf[0]), 3)
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            db.insert_detection(camera_id, label, conf, [x1, y1, x2, y2])
            n_det += 1
            n_evt += event_service.check(camera_id, label, conf, frame, snap_dir)
    cap.release()
    return {"detections": n_det, "events": n_evt}
```

#### `app/routes/detection.py`

```python
"""객체 검출 라우터 — 카메라별 검출 시작/중지/조회."""
from flask import Blueprint, current_app, jsonify

from .. import db
from ..services import detection_service

detection_bp = Blueprint("detection", __name__)


@detection_bp.post("/<int:cid>/start")
def start(cid):
    cam = db.get_camera(cid)
    if not cam:
        return jsonify({"error": "카메라 없음"}), 404
    detection_service.start(cid, cam["rtsp_url"], current_app.config)
    return jsonify({"camera_id": cid, "detecting": True})


@detection_bp.post("/<int:cid>/stop")
def stop(cid):
    detection_service.stop(cid)
    return jsonify({"camera_id": cid, "detecting": False})


@detection_bp.get("/<int:cid>/recent")
def recent(cid):
    return jsonify({"data": db.recent_detections(cid)})
```

---

## STEP 5 · 이벤트 트리거  
<sub>📊 슬라이드 24</sub>

**무엇을 만드나** — 검출이 규칙(객체·신뢰도)에 맞으면 쿨다운을 적용해 이벤트를 만들고 스냅샷을 저장한다.

> 🤖 **바이브 코딩 지시 예**  
> “검출이 규칙에 맞으면 쿨다운을 적용해 이벤트를 만들고 스냅샷을 저장하는 event_service와 /api/events 라우터를 만들어줘”

#### `app/services/event_service.py`

```python
"""이벤트 트리거 — 검출이 규칙에 맞으면 이벤트 생성(+쿨다운, 스냅샷)."""
import os
import time

import cv2

from .. import db

_last = {}   # (camera_id, rule_id) -> 마지막 발생 시각


def check(camera_id, label, confidence, frame, snap_dir):
    """검출 1건을 규칙들과 대조해 트리거. 발생한 이벤트 수 반환."""
    fired = 0
    for rule in db.get_rules(camera_id):
        if rule["object"] != label:
            continue
        if confidence < rule["min_confidence"]:
            continue
        key = (camera_id, rule["rule_id"])
        if time.time() - _last.get(key, 0) < rule["cooldown_sec"]:
            continue          # 쿨다운 — 중복 이벤트 억제
        _last[key] = time.time()
        snap = _save_snapshot(frame, camera_id, snap_dir)
        db.insert_event(camera_id, rule["rule_id"], label, confidence, snap)
        fired += 1
        # 실무: 여기서 웹훅/메신저 알림 호출
    return fired


def _save_snapshot(frame, camera_id, snap_dir):
    if frame is None:
        return None
    os.makedirs(snap_dir, exist_ok=True)
    name = f"evt_{camera_id}_{int(time.time()*1000)}.jpg"
    cv2.imwrite(os.path.join(snap_dir, name), frame)
    return f"/static/hls/_snapshots/{name}"
```

#### `app/routes/events.py`

```python
"""이벤트 라우터 — 규칙 관리 + 이벤트 조회/확인."""
from flask import Blueprint, jsonify, request

from .. import db

events_bp = Blueprint("events", __name__)


@events_bp.get("/rules")
def list_rules():
    return jsonify({"rules": db.all_rules()})


@events_bp.post("/rules")
def add_rule():
    b = request.get_json(silent=True) or {}
    if not b.get("camera_id") or not b.get("object"):
        return jsonify({"error": "camera_id, object 필요"}), 400
    rid = db.add_rule(b["camera_id"], b["object"],
                      float(b.get("min_confidence", 0.5)),
                      int(b.get("cooldown_sec", 30)))
    return jsonify({"rule_id": rid}), 201


@events_bp.get("")
@events_bp.get("/")
def list_events():
    cam = request.args.get("camera_id", type=int)
    return jsonify({"events": db.list_events(camera_id=cam)})


@events_bp.post("/<int:eid>/ack")
def ack(eid):
    db.ack_event(eid)
    return jsonify({"event_id": eid, "acked": True})
```

---

## STEP 6 · 웹 대시보드  
<sub>📊 슬라이드 25</sub>

**무엇을 만드나** — 화면정의서(SCR-01)대로 hls.js 라이브 그리드 + 이벤트 패널을 만든다.

> 🤖 **바이브 코딩 지시 예**  
> “화면정의서 SCR-01대로 hls.js로 카메라 라이브를 띄우고 이벤트를 3초마다 폴링하는 dashboard.html을 만들어줘”

#### `app/routes/web.py`

```python
"""웹 프론트(관제 대시보드) 라우터."""
from flask import Blueprint, render_template

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def dashboard():
    return render_template("dashboard.html")
```

#### `templates/dashboard.html`

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎥 VMS 관제 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
<style>
  :root{--green:#2e7d32;--green-d:#1b5e20;--bg:#10140f;--panel:#1b2118;--line:#2e3a28;--muted:#8aa090;--warn:#ff5d5d;--ok:#5fd07a;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:#e8f0e6;font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;}
  header{background:linear-gradient(135deg,var(--green-d),var(--green));padding:14px 22px;display:flex;justify-content:space-between;align-items:center;}
  header h1{font-size:19px;} header .add{display:flex;gap:8px;}
  header input{background:#0d120c;border:1px solid var(--line);color:#e8f0e6;border-radius:8px;padding:7px 10px;font-size:13px;}
  header button{background:#fff;color:var(--green-d);border:0;border-radius:8px;padding:7px 13px;font-weight:700;cursor:pointer;font-size:13px;}
  .wrap{display:grid;grid-template-columns:1fr 320px;gap:14px;padding:14px;}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;align-content:start;}
  .cam{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;}
  .cam .vid{position:relative;aspect-ratio:16/9;background:#000;}
  .cam video{width:100%;height:100%;object-fit:cover;display:block;}
  .cam .ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#56684f;font-size:13px;}
  .cam .bar{display:flex;align-items:center;gap:8px;padding:9px 12px;}
  .cam .nm{font-weight:700;font-size:14px;flex:1;}
  .dot{width:9px;height:9px;border-radius:50%;background:#566;}
  .dot.on{background:var(--ok);}
  .cam .btns{display:flex;gap:6px;padding:0 12px 11px;}
  .cam .btns button{flex:1;background:#0d120c;border:1px solid var(--line);color:#cfe0c8;border-radius:7px;padding:7px;font-size:12px;font-weight:600;cursor:pointer;}
  .cam .btns button.act{background:var(--green);color:#fff;border-color:var(--green);}
  aside{background:var(--panel);border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;max-height:calc(100vh - 92px);}
  aside h2{font-size:15px;padding:13px 15px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;}
  aside .badge{background:var(--warn);color:#fff;border-radius:999px;font-size:12px;padding:1px 9px;}
  .events{overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:8px;}
  .evt{background:#0d120c;border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:8px;padding:9px 11px;}
  .evt .t{font-size:13px;font-weight:700;} .evt .m{font-size:11px;color:var(--muted);margin-top:2px;}
  .evt.acked{opacity:.5;border-left-color:#566;}
  .evt button{margin-top:6px;background:none;border:1px solid var(--line);color:var(--muted);border-radius:6px;font-size:11px;padding:3px 9px;cursor:pointer;}
  .empty{color:var(--muted);text-align:center;padding:30px;font-size:13px;}
</style>
</head>
<body>
<header>
  <h1>🎥 VMS 관제 대시보드</h1>
  <div class="add">
    <input id="cname" placeholder="카메라 이름">
    <input id="curl" placeholder="rtsp://... (또는 영상 파일 경로)" style="width:260px">
    <button onclick="addCam()">+ 카메라 추가</button>
  </div>
</header>
<div class="wrap">
  <div class="grid" id="grid"></div>
  <aside>
    <h2>⚡ 이벤트 <span class="badge" id="evtcount">0</span></h2>
    <div class="events" id="events"><div class="empty">이벤트 없음</div></div>
  </aside>
</div>

<script>
const hlsMap = {};
async function api(url, opt){ const r=await fetch(url,opt); return r.json(); }

async function loadCams(){
  const {cameras} = await api('/api/cameras');
  const g = document.getElementById('grid');
  if(!cameras.length){ g.innerHTML='<div class="empty">카메라를 추가하세요</div>'; return; }
  g.innerHTML = cameras.map(c=>`
    <div class="cam" id="cam${c.camera_id}">
      <div class="vid"><video id="v${c.camera_id}" muted></video><div class="ph" id="ph${c.camera_id}">⏹ 스트림 중지됨</div></div>
      <div class="bar"><span class="dot ${c.status==='online'?'on':''}" id="dot${c.camera_id}"></span><span class="nm">${c.name}</span></div>
      <div class="btns">
        <button onclick="startStream(${c.camera_id})">▶ 스트림</button>
        <button onclick="startDetect(${c.camera_id})">🔍 검출</button>
        <button onclick="addRule(${c.camera_id})">⚡ 규칙</button>
      </div>
    </div>`).join('');
}
async function addCam(){
  const name=cname.value.trim(), url=curl.value.trim();
  if(!name||!url){ alert('이름·URL 입력'); return; }
  await api('/api/cameras',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,rtsp_url:url})});
  cname.value=curl.value=''; loadCams();
}
async function startStream(id){
  const {hls_url}=await api(`/api/stream/${id}/start`,{method:'POST'});
  document.getElementById('ph'+id).style.display='none';
  document.getElementById('dot'+id).classList.add('on');
  const v=document.getElementById('v'+id);
  // HLS 세그먼트 생성까지 잠깐 대기 후 로드
  setTimeout(()=>{
    if(Hls.isSupported()){ const h=new Hls(); hlsMap[id]=h; h.loadSource(hls_url); h.attachMedia(v); h.on(Hls.Events.MANIFEST_PARSED,()=>v.play()); }
    else { v.src=hls_url; v.play(); }
  }, 3500);
}
async function startDetect(id){
  await api(`/api/detection/${id}/start`,{method:'POST'});
  alert('객체 검출 시작 — 검출이 규칙에 맞으면 이벤트가 발생합니다.');
}
async function addRule(id){
  const obj=prompt('이벤트 트리거 대상 객체 (예: person, car)','person');
  if(!obj) return;
  await api('/api/events/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({camera_id:id,object:obj,min_confidence:0.5,cooldown_sec:15})});
  alert(`규칙 추가: ${obj} 감지 시 이벤트`);
}
async function loadEvents(){
  const {events}=await api('/api/events');
  document.getElementById('evtcount').textContent=events.filter(e=>!e.acked).length;
  const el=document.getElementById('events');
  if(!events.length){ el.innerHTML='<div class="empty">이벤트 없음</div>'; return; }
  el.innerHTML=events.map(e=>`
    <div class="evt ${e.acked?'acked':''}">
      <div class="t">⚠️ ${e.label} <span style="color:#8aa090;font-weight:400">(cam ${e.camera_id})</span></div>
      <div class="m">${e.ts.replace('T',' ')} · conf ${e.confidence??'-'}</div>
      ${e.acked?'':`<button onclick="ackEvt(${e.event_id})">확인</button>`}
    </div>`).join('');
}
async function ackEvt(id){ await api(`/api/events/${id}/ack`,{method:'POST'}); loadEvents(); }

loadCams(); loadEvents();
setInterval(loadEvents, 3000);
</script>
</body>
</html>
```

---

## STEP 7 · 단계별 검증  
<sub>📊 슬라이드 26</sub>

API 통과는 당연 — **영상이 진짜 만들어지나 / AI가 진짜 도나**를 `VMS_실습.ipynb`로 직접 확인합니다 (ffprobe로 HLS 영상 확인 · YOLO 박스 이미지 확인 · 검출→이벤트 확인).
