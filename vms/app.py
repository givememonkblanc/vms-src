"""엔트리포인트 — create_app()으로 앱 생성 후 실행.

  python app.py            # http://0.0.0.0:8000
포트는 .env(PORT)로 관리 → docker-compose 매핑과 반드시 일치시킨다.
"""
from app import create_app

flask_app = create_app()

if __name__ == "__main__":
    port = flask_app.config["PORT"]
    flask_app.run(host="0.0.0.0", port=port, debug=flask_app.config["DEBUG"],
                  use_reloader=False)
