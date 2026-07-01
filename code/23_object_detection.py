"""
=====================================================================
 슬라이드 23 · AI 객체 검출 (YOLO)
=====================================================================
영상 프레임에서 '무엇이 어디 있는지'(사람·차량 등)를 찾는다.

핵심 개념:
 - YOLO : 이미지를 한 번 보고 객체의 박스+클래스+신뢰도를 출력하는 검출 모델.
 - classes=[0,2] : COCO 기준 0=person, 2=car 만 보겠다는 필터.
 - conf=0.4      : 신뢰도 0.4 미만은 버린다(오탐 줄이기).
 - 프레임 샘플링 : 모든 프레임을 검출하면 너무 무겁다 → N프레임마다 1회.
 - lazy load     : 모델은 무거우므로 처음 1번만 메모리에 올리고 재사용.

이 검출 결과(클래스·신뢰도·박스)가 슬라이드 24의 '이벤트' 입력이 된다.

실행:  python 15_object_detection.py     (GPU 있으면 device="cpu" 삭제)
=====================================================================
"""
import os
from collections import Counter

import cv2
from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "vms", "samples", "sample.mp4")


class Detector:
    """YOLO 검출기 래퍼 — 모델 1회 로드 후 재사용."""
    def __init__(self, weights="yolo11n.pt", device="cpu",
                 classes=(0, 2), conf=0.4):       # 0=person, 2=car
        self.model = YOLO(weights)
        self.device, self.classes, self.conf = device, list(classes), conf

    def detect(self, frame):
        """프레임 1장 → 검출 리스트 [{label, conf, bbox}]."""
        r = self.model(frame, classes=self.classes, conf=self.conf,
                       device=self.device, verbose=False)[0]
        dets = []
        for b in r.boxes:
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            dets.append({"label": self.model.names[int(b.cls[0])],
                         "conf": round(float(b.conf[0]), 3),
                         "bbox": [x1, y1, x2, y2]})
        return dets, r            # r.plot() 으로 박스 이미지 생성 가능


def detect_video(detector, video, frame_skip=15, max_frames=30):
    """영상 전체를 샘플링하며 검출 (실제 detection_service 의 핵심 루프)."""
    cap = cv2.VideoCapture(video)
    idx, all_dets = 0, []
    while len(all_dets) < max_frames * 5:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % frame_skip:           # N프레임마다 1회만
            continue
        dets, _ = detector.detect(frame)
        for d in dets:
            all_dets.append({"frame": idx, **d})
    cap.release()
    return all_dets


# ── 실행 & 검증: "AI가 진짜 그 영상에서 도는가?" ─────────────────
if __name__ == "__main__":
    det = Detector(device="cpu", classes=(0, 2, 63, 67))  # +tv,laptop (데모 풍부하게)

    # (1) 한 프레임 검출 + 박스 그려 저장 → 눈으로 확인
    cap = cv2.VideoCapture(SAMPLE); cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ok, frame = cap.read(); cap.release()
    dets, r = det.detect(frame)
    print("[프레임 검출]", dict(Counter(d["label"] for d in dets)))
    for d in dets[:6]:
        print("   ", d["label"], "conf", d["conf"], "bbox", d["bbox"])
    out = os.path.join(HERE, "detected.jpg")
    cv2.imwrite(out, r.plot())
    print("   → 박스 이미지:", out, "(열어서 확인)")

    # (2) 영상 전체 샘플링 검출
    vid = detect_video(det, SAMPLE)
    print("\n[영상 전체 검출]", len(vid), "건 (샘플링)")
    print("   클래스 분포:", dict(Counter(d["label"] for d in vid)))

# 👉 실제 완성본: vms/app/services/detection_service.py · app/routes/detection.py
