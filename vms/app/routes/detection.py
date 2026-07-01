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
