"""웹 프론트(관제 대시보드) 라우터."""
from flask import Blueprint, render_template

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def dashboard():
    return render_template("dashboard.html")
