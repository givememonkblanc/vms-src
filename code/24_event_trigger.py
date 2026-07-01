"""
=====================================================================
 슬라이드 24 · 이벤트 트리거 관리
=====================================================================
검출(슬라이드 23)이 그냥 쌓이기만 하면 의미가 없다.
"사람이 들어왔다!" 같은 상황을 골라 '이벤트'로 만들어 알린다.

구성:
 1) 규칙(rule)   : 어떤 카메라에서 / 어떤 객체가 / 신뢰도 몇 이상이면 이벤트
 2) 쿨다운       : 같은 상황이 매 프레임 터지면 알림 폭탄 → N초간 억제
 3) 액션         : 이벤트 저장 + 스냅샷(증거) 저장 (+실무: 웹훅/메신저 알림)

흐름:  검출 → 규칙 매칭 → (쿨다운 통과) → 이벤트 생성 + 스냅샷

실행:  python 16_event_trigger.py
=====================================================================
"""
import os
import time
from datetime import datetime


class EventEngine:
    def __init__(self, rules, snap_dir=None):
        # rules 예: [{"camera_id":1,"object":"person","min_confidence":0.5,"cooldown_sec":10}]
        self.rules = rules
        self.snap_dir = snap_dir
        self._last = {}            # (camera_id, rule_idx) -> 마지막 발생 시각
        self.events = []

    def check(self, camera_id, label, confidence, frame=None):
        """검출 1건을 규칙들과 대조 → 트리거된 이벤트 수 반환."""
        fired = 0
        for i, r in enumerate(self.rules):
            if r["camera_id"] != camera_id:        continue
            if r["object"] != label:               continue
            if confidence < r["min_confidence"]:   continue
            key = (camera_id, i)
            if time.time() - self._last.get(key, 0) < r["cooldown_sec"]:
                continue                            # 쿨다운 — 억제
            self._last[key] = time.time()
            snap = self._save_snapshot(camera_id, frame)
            ev = {"camera_id": camera_id, "label": label, "confidence": confidence,
                  "snapshot": snap, "ts": datetime.now().isoformat(timespec="seconds")}
            self.events.append(ev)
            fired += 1
            # 실무: 여기서 webhook/슬랙/문자 알림 호출
        return fired

    def _save_snapshot(self, camera_id, frame):
        if frame is None or not self.snap_dir:
            return None
        os.makedirs(self.snap_dir, exist_ok=True)
        path = os.path.join(self.snap_dir, f"evt_{camera_id}_{int(time.time()*1000)}.jpg")
        try:
            import cv2
            cv2.imwrite(path, frame)
            return path
        except Exception:
            return None


# ── 실행 & 검증 ───────────────────────────────────────────────────
if __name__ == "__main__":
    rules = [{"camera_id": 1, "object": "person", "min_confidence": 0.5, "cooldown_sec": 3}]
    engine = EventEngine(rules)

    # 검출 스트림을 흉내내 연속 입력 (실제론 15의 detect 결과)
    stream = [
        ("person", 0.82),   # ① 발생
        ("person", 0.90),   # ② 쿨다운 — 억제
        ("car",    0.95),   # ③ 규칙 없음 — 무시
        ("person", 0.30),   # ④ 신뢰도 미달 — 무시
    ]
    print("[검출 → 이벤트 판정]")
    for label, conf in stream:
        n = engine.check(camera_id=1, label=label, confidence=conf)
        mark = "⚡ 이벤트!" if n else "— (억제/무시)"
        print(f"   {label:7} conf={conf}  {mark}")

    print("\n[발생한 이벤트]", len(engine.events), "건")
    for e in engine.events:
        print("   ⚠️", e["label"], "conf", e["confidence"], "@", e["ts"])

    # 쿨다운(3초) 지난 뒤엔 다시 발생
    print("\n3초 대기 후 같은 검출...")
    time.sleep(3.1)
    print("   재발생:", "⚡ 이벤트!" if engine.check(1, "person", 0.8) else "억제")

# 👉 실제 완성본: vms/app/services/event_service.py · app/routes/events.py
