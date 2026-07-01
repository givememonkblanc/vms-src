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
