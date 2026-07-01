"""VMS 설정 — .env에서 로드."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent.parent


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    PORT = int(os.getenv("PORT", "8000"))

    # HLS / 녹화 저장 경로
    HLS_DIR = str(BASE / "static" / "hls")
    REC_DIR = str(BASE / "recordings")
    HLS_TIME = int(os.getenv("HLS_TIME", "2"))          # 세그먼트 길이(초)
    HLS_LIST_SIZE = int(os.getenv("HLS_LIST_SIZE", "6"))

    # 객체 검출 (YOLO)
    DETECTOR_WEIGHTS = os.getenv("DETECTOR_WEIGHTS", "yolo11n.pt")
    DETECT_CLASSES = [int(x) for x in os.getenv("DETECT_CLASSES", "0,2").split(",")]  # person,car
    DETECT_CONF = float(os.getenv("DETECT_CONF", "0.4"))
    FRAME_SKIP = int(os.getenv("FRAME_SKIP", "15"))
    DEVICE = os.getenv("DEVICE") or None

    REC_SEGMENT_TIME = int(os.getenv("REC_SEGMENT_TIME", "60"))   # 녹화 파일 1개 길이(초)

    DB_PATH = os.getenv("DB_PATH", str(BASE / "vms.db"))
