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
