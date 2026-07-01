# VMS — 영상 관리 시스템 (Video Management System)

RTSP 카메라를 **HLS로 변환·재생**하고, **YOLO 객체 검출** + **이벤트 트리거**까지 갖춘 Flask VMS와
**웹 관제 대시보드**. 학생이 직접 구성·실행하는 실습 프로젝트.

## 기능
- 📥 **RTSP 수집 → HLS 변환** (ffmpeg) — 브라우저 `<video>`로 실시간 재생
- 🗂️ **카메라 관리** — 등록·상태·스트림 시작/중지
- 🔍 **AI 객체 검출** — 프레임에서 사람·차량 검출(YOLO)
- ⚡ **이벤트 트리거** — 검출이 규칙에 맞으면 이벤트 발생(쿨다운·스냅샷)
- 🖥️ **웹 대시보드** — 라이브 그리드 + 이벤트 패널

## 구조
```
vms/
├── app.py
├── app/
│   ├── __init__.py            # App Factory + 블루프린트
│   ├── config.py · db.py      # 설정 / SQLite(cameras·detections·rules·events)
│   ├── routes/                # cameras·stream·detection·events·health·web
│   └── services/
│       ├── hls_service.py     # RTSP→HLS (ffmpeg)
│       ├── detection_service.py # YOLO 검출(스레드)
│       └── event_service.py   # 규칙 매칭·이벤트
├── templates/dashboard.html   # 웹 관제 화면 (hls.js)
├── static/hls/ · recordings/  # 산출물(볼륨)
└── Dockerfile · docker-compose.yml
```

## 실행
```bash
pip install -r requirements.txt   # + 시스템 ffmpeg 필요
python app.py                     # http://localhost:8000
# 또는
docker compose up --build
```

## API
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET/POST | `/api/cameras` | 카메라 목록·등록 |
| POST | `/api/stream/<id>/start` ·`/stop` | RTSP→HLS 시작·중지 |
| POST | `/api/detection/<id>/start`·`/stop` | 객체 검출 시작·중지 |
| GET | `/api/detection/<id>/recent` | 최근 검출 |
| GET/POST | `/api/events/rules` | 이벤트 규칙 |
| GET | `/api/events` · POST `/api/events/<id>/ack` | 이벤트 조회·확인 |
| GET | `/api/health/` | 상태 |

> 카메라 URL에 **영상 파일 경로**를 넣으면 RTSP 없이도 데모 가능(반복 재생).
