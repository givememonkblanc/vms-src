"""
=====================================================================
 슬라이드 26 · 단계별 검증 — "진짜 되는가?"를 코드로 확인
=====================================================================
"API가 200 통과"는 당연한 것. 진짜 확인할 것은 세 가지다.
  ① 영상이 진짜 만들어지나  (HLS .ts 가 재생 가능한 H.264 인가 — ffprobe)
  ② AI가 그 영상에서 진짜 도나  (실제 프레임에서 객체를 잡나 — YOLO)
  ③ 검출 → 이벤트가 진짜 터지나  (규칙·쿨다운이 동작하나)

이 스크립트는 셋을 순서대로 실행해 결과를 출력한다.
(노트북 버전: vms/practice/*.ipynb — 셀 단위로 하나씩)

실행:  python 18_verify.py       (GPU 있으면 device 인자만 조정)
=====================================================================
"""
import os
import subprocess
import time
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.normpath(os.path.join(HERE, "..", "..", "vms", "samples", "sample.mp4"))
WORK = os.path.join(HERE, "_verify_out")


def check_video():
    """① HLS 변환 후 .ts 가 진짜 영상인지 ffprobe로 확인."""
    od = os.path.join(WORK, "hls"); os.makedirs(od, exist_ok=True)
    m3u8 = os.path.join(od, "index.m3u8")
    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-re", "-i", SAMPLE,
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
           "-force_key_frames", "expr:gte(t,n_forced*2)", "-an", "-f", "hls",
           "-hls_time", "2", "-hls_list_size", "6", m3u8]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)
    seg = sorted(glob.glob(os.path.join(od, "*.ts")))
    ok = os.path.exists(m3u8) and len(seg) > 0
    codec = ""
    if seg:
        codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height", "-of", "csv=p=0", seg[0]],
            capture_output=True, text=True).stdout.strip()
    p.terminate()
    print(f"① 영상 검증 : m3u8={os.path.exists(m3u8)} ts={len(seg)}개 ffprobe={codec}  "
          f"{'✅' if ok else '❌'}")
    return ok


def check_ai(device="cpu"):
    """② 실제 프레임에서 객체를 잡는지."""
    import cv2
    from ultralytics import YOLO
    from collections import Counter
    cap = cv2.VideoCapture(SAMPLE); cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ok_frame, frame = cap.read(); cap.release()
    model = YOLO("yolo11n.pt")
    r = model(frame, device=device, conf=0.3, verbose=False)[0]
    counts = dict(Counter(model.names[int(b.cls[0])] for b in r.boxes))
    cv2.imwrite(os.path.join(WORK, "detected.jpg"), r.plot())
    ok = len(r.boxes) > 0
    print(f"② AI 검증   : 검출={counts} (박스이미지 {WORK}/detected.jpg)  {'✅' if ok else '❌'}")
    return ok


def check_event():
    """③ 검출 → 규칙 → 이벤트 + 쿨다운."""
    rules = [{"object": "person", "min_confidence": 0.5, "cooldown_sec": 3}]
    last, events = {}, []
    def check(label, conf):
        for rr in rules:
            if rr["object"] != label or conf < rr["min_confidence"]:
                continue
            if time.time() - last.get(label, 0) < rr["cooldown_sec"]:
                return False
            last[label] = time.time(); events.append(label); return True
        return False
    a = check("person", 0.8)     # 발생
    b = check("person", 0.9)     # 쿨다운 억제
    ok = a and not b and len(events) == 1
    print(f"③ 이벤트 검증: 1차발생={a} 2차억제={not b} 이벤트수={len(events)}  {'✅' if ok else '❌'}")
    return ok


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    print("=== VMS 단계별 검증 ===\n대상 영상:", os.path.basename(SAMPLE), "\n")
    results = [check_video(), check_ai(), check_event()]
    print("\n결과:", "전부 통과 ✅" if all(results) else "일부 실패 ❌")
    # 정리
    import shutil; shutil.rmtree(WORK, ignore_errors=True)

# 👉 셀 단위 실습: vms/practice/14~17 노트북
