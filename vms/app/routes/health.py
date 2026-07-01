"""헬스체크."""
from flask import Blueprint, jsonify

from .. import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def health():
    return jsonify({"status": "healthy", "cameras": len(db.list_cameras())})
