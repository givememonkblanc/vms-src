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
