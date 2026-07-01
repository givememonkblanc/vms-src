# VMS src

영상 관제 시스템(VMS) 강의 소스.

- **`code/`** — 슬라이드별 코드 (10 데이터 · 20 Flask · 21 RTSP→HLS · 22 영상관리 · 23 객체검출 · 24 이벤트 · 25 대시보드 · 26 검증)
- **`video/`** — CCTV 크롭 영상 10개 + 원본 90초 (서울역 광장, 위치·줌·시간대 다양)
- **`vms/`** — VMS 앱 (Flask App Factory, RTSP→HLS · YOLO 객체검출 · 이벤트, Docker)

## 실행
```bash
cd vms
pip install -r requirements.txt      # + 시스템 ffmpeg
python app.py                        # http://localhost:8000
```
> YOLO 추론은 CPU 기준. 가중치 `vms/yolo11n.pt`(COCO 사전학습) 포함.
