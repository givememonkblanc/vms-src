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
