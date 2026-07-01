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
