# 🎥 VMS — 영상 관제 시스템 만들기 (강의 소스)

CCTV 여러 대를 한 화면에서 관리하는 **VMS(Video Management System)** 를 직접 만들어 보는 강의의 소스 코드입니다.
**RTSP 수집 → HLS 변환(브라우저 재생) → AI 객체 검출 → 이벤트**까지, 실무 관제 시스템의 핵심을 한 조각씩 구현합니다.

> 카메라가 없어도 됩니다. 포함된 **샘플 영상**(횡단보도·서울역 CCTV)을 카메라처럼 사용합니다.
> AI 추론은 **CPU만으로** 동작합니다(GPU 불필요).

---

## 📂 무엇이 들어 있나요?

```
code/    📖 슬라이드별 학습용 코드 — 개념 하나당 실행 가능한 스크립트 1개
video/   🎞  실습용 CCTV 영상 — 크롭 10종 + 원본
vms/     🚀 완성된 VMS 앱 — 위 조각들을 하나로 합친 실제 서비스
```

### `code/` — 개념별 학습용 코드
슬라이드를 보며 **바로 열어 돌려보는** 코드입니다. 각 파일은 단독 실행되고, 결과를 눈으로 확인할 수 있습니다.

| 파일 | 배우는 것 | 실행하면 |
|------|-----------|----------|
| `10_database.py` | 데이터 설계(ERD→SQLite) | 5개 테이블 생성 + 관계 조회 |
| `20_flask_app.py` | Flask 앱 구조(App Factory·Blueprint) | 라우트 등록 + 자가 테스트 |
| `21_rtsp_hls.py` | RTSP → HLS 변환 | **ffprobe로 실제 영상(H.264) 확인** |
| `22_video_management.py` | 영상 관리(녹화·검색) | 녹화 mp4 생성 + 기간 검색 |
| `23_object_detection.py` | YOLO 객체 검출 | **박스 그린 detected.jpg 생성** |
| `24_event_trigger.py` | 이벤트 트리거(규칙·쿨다운) | 이벤트 발생/억제 시연 |
| `25_dashboard.html` | 관제 대시보드(hls.js) | 브라우저에서 라이브+이벤트 |
| `26_verify.py` | 단계별 검증 | 영상·AI·이벤트를 한 번에 점검 |

### `video/` — 실습용 영상
- `cctv_crop_01 ~ 10.mp4` — 서울역 광장 CCTV를 **위치·줌·시간대별로 잘라낸** 10종 (사람·차·버스 검출)
- `seoul_source_90s.mp4` — 크롭의 원본(90초 광각) — "원본 → 관심영역 크롭" 비교용

### `vms/` — 완성된 VMS 앱
`code/`의 조각들을 합친 **실제 동작하는 서비스**입니다. (레이어드 구조: 라우터 → 서비스 → 데이터)
```
vms/app/
 ├─ routes/     요청 처리 (cameras·stream·detection·events·recordings·web)
 ├─ services/   핵심 로직 (HLS 변환·녹화·YOLO 검출·이벤트)
 ├─ db.py       SQLite 데이터
 └─ config.py   설정
```

---

## 🚀 빠르게 시작하기

### 0) 준비물
```bash
# 시스템에 ffmpeg 설치 (필수)
#   Ubuntu:  sudo apt install ffmpeg
#   macOS:   brew install ffmpeg

pip install flask opencv-python ultralytics torch python-dotenv
```

### 1) 개념 하나씩 실습 (`code/`)
```bash
cd code
python 21_rtsp_hls.py          # 영상 → HLS 변환, 진짜 되는지 ffprobe로 확인
python 23_object_detection.py  # YOLO로 사람·차 검출 → detected.jpg 열어보기
python 26_verify.py            # 영상·AI·이벤트 한 번에 검증
```

### 2) 완성 앱 실행 (`vms/`)
```bash
cd vms
pip install -r requirements.txt
python app.py                  # → http://localhost:8000
```
브라우저에서 대시보드를 열고, **카메라 추가**의 URL 자리에 영상 파일 경로를 넣으면
(예: `video/cctv_crop_01.mp4` 절대경로) 실제 스트림처럼 재생·검출됩니다.

### 3) Docker로 실행
```bash
cd vms
docker compose up --build      # ffmpeg 포함 이미지로 한 번에 기동
```

---

## 💡 알아두면 좋은 점
- **GPU 없이 CPU로 동작**합니다. (가중치 `vms/yolo11n.pt` = YOLO11-nano COCO 사전학습, 포함)
- 브라우저는 RTSP를 직접 못 봅니다 → **ffmpeg로 HLS 변환**하는 것이 스트리밍의 핵심입니다.
- 실제 CCTV 영상이라 **원거리·오검출**(예: 에스컬레이터를 다른 물체로) 같은 현실적 특성이 그대로 담겨 있습니다.

## 🧰 사용 기술
Flask · ffmpeg · HLS.js · Ultralytics YOLO · SQLite · Docker

교육용 자료입니다. 🙂
