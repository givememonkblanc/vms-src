"""
=====================================================================
 슬라이드 20 · Flask 앱 구조 (App Factory + Blueprint)
=====================================================================
VMS는 기능이 많다(영상·녹화·검출·이벤트). 한 파일에 다 넣으면 금방 엉킨다.
그래서 두 가지 패턴을 쓴다.

 1) App Factory  : create_app() 함수가 앱을 '조립'해서 반환.
                   - 설정을 바꿔 여러 앱(개발/테스트/운영)을 만들기 쉽다.
                   - 테스트 시 app.test_client()로 서버 없이 호출 가능.
 2) Blueprint    : 라우트(API)를 도메인별로 묶은 '미니 앱'.
                   - cameras / stream / detection / events 처럼 파일 분리.
                   - url_prefix로 경로 네임스페이스를 준다.

실행:  python 12_flask_app.py        →  http://localhost:8000
테스트: 아래 __main__ 이 test_client로 직접 호출해 결과를 출력한다.
=====================================================================
"""
from flask import Flask, Blueprint, jsonify, request


# ── 설정 (실제 앱에선 app/config.py) ──────────────────────────────
class Config:
    DEBUG = True
    PORT = 8000
    # 여기에 카메라 URL, DB 경로 등 환경값을 모은다(.env에서 로드).


# ── 블루프린트 1: 헬스체크 (app/routes/health.py) ─────────────────
health_bp = Blueprint("health", __name__)

@health_bp.get("/")
def health():
    # 모니터링/로드밸런서가 서버 생존을 확인하는 표준 엔드포인트
    return jsonify({"status": "healthy"})


# ── 블루프린트 2: 카메라 CRUD (app/routes/cameras.py) ─────────────
cameras_bp = Blueprint("cameras", __name__)
_cameras = []   # 데모용 메모리 저장 (실제는 SQLite — 슬라이드 22)

# 슬래시 있든("/api/cameras/") 없든("/api/cameras") 둘 다 받게 "" 와 "/" 모두 등록
# (안 하면 /api/cameras 가 308 리다이렉트로 튕긴다 — 흔한 함정!)
@cameras_bp.get("")
@cameras_bp.get("/")
def list_cameras():
    return jsonify({"cameras": _cameras})

@cameras_bp.post("")
@cameras_bp.post("/")
def add_camera():
    body = request.get_json(silent=True) or {}
    # 입력 검증: 라우터는 '입출구'이므로 형식 체크는 여기서
    if not body.get("name") or not body.get("rtsp_url"):
        return jsonify({"error": "name, rtsp_url 필요"}), 400
    cam = {"camera_id": len(_cameras) + 1, **body}
    _cameras.append(cam)
    return jsonify(cam), 201            # 201 Created


# ── App Factory: 앱을 조립한다 (app/__init__.py) ──────────────────
def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    # 도메인별 블루프린트 등록 — 경로 = url_prefix + 라우트
    app.register_blueprint(health_bp,  url_prefix="/api/health")    # GET /api/health/
    app.register_blueprint(cameras_bp, url_prefix="/api/cameras")   # /api/cameras
    # 기능이 늘면 여기에 stream_bp, detection_bp, events_bp ... 추가
    return app


# ── 실행 & 자가 테스트 ────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()

    # (1) 등록된 라우트 확인
    print("[등록된 라우트]")
    for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
        if "static" not in r.rule:
            print("  ", sorted(r.methods & {"GET", "POST"}), r.rule)

    # (2) 서버를 띄우지 않고 test_client로 호출 (TDD에 유용)
    print("\n[test_client 호출]")
    c = app.test_client()
    print("  GET  /api/health/  ->", c.get("/api/health/").get_json())
    print("  POST /api/cameras  ->", c.post("/api/cameras",
          json={"name": "정문", "rtsp_url": "rtsp://192.168.0.10/stream"}).get_json())
    print("  POST (검증실패)    ->", c.post("/api/cameras", json={}).status_code, "(400 = 정상)")
    print("  GET  /api/cameras  ->", c.get("/api/cameras").get_json())

    # (3) 실제 서버로 띄우려면 아래 주석 해제
    # app.run(host="0.0.0.0", port=app.config["PORT"], debug=app.config["DEBUG"])

# 👉 실제 완성본: vms/app/__init__.py · app/config.py · app/routes/*.py
