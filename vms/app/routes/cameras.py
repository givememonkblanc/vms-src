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
