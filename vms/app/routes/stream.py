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
