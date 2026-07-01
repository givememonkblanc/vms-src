"""
=====================================================================
 슬라이드 22 · 영상 관리 — 카메라 · 녹화 · 재생(검색)
=====================================================================
VMS의 '관리' 영역. 세 가지를 만든다.

 1) 카메라 관리 : 카메라를 DB(SQLite)에 등록·조회 (CRUD)
 2) 녹화        : ffmpeg 'segment muxer'로 영상을 타임스탬프 mp4 파일로 분할 저장
                  예) 20260630_140000.mp4, 20260630_140100.mp4 ...
                  - "-c copy" : 재인코딩 없이 복사 → 빠르고 CPU 안 씀
                  - "-strftime 1" + "%Y%m%d_%H%M%S.mp4" : 파일명에 시각 기록
 3) 재생/검색   : 파일명의 시각으로 '기간 검색' → 해당 mp4를 재생/다운로드

핵심 아이디어: 녹화 파일명에 시각을 박아두면, DB 없이도 시간으로 찾을 수 있다.
              (실제 앱은 파일을 DB에 등록해 빠르게 조회 — 아래 register 참고)

실행:  python 14_video_management.py
=====================================================================
"""
import os
import re
import sqlite3
import subprocess
import glob
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "..", "vms", "samples", "sample.mp4")
DB = os.path.join(HERE, "vms_demo.db")
_NAME = re.compile(r"(\d{8})_(\d{6})\.mp4$")   # 파일명 → 시각 파싱


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS cameras(
            camera_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, rtsp_url TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS recordings(
            rec_id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id INT,
            file_path TEXT UNIQUE, start_time TEXT, end_time TEXT)""")


# ── 1) 카메라 관리 (CRUD) ─────────────────────────────────────────
def add_camera(name, rtsp_url):
    with conn() as c:
        return c.execute("INSERT INTO cameras(name,rtsp_url) VALUES(?,?)",
                         (name, rtsp_url)).lastrowid

def list_cameras():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM cameras")]


# ── 2) 녹화 (ffmpeg segment) ─────────────────────────────────────
def record(camera_id, source, rec_root, segment_time=3):
    """source를 segment_time초 단위 mp4로 분할 저장 (파일명 = 시각)."""
    out = os.path.join(rec_root, str(camera_id))
    os.makedirs(out, exist_ok=True)
    pattern = os.path.join(out, "%Y%m%d_%H%M%S.mp4")
    inp = ["-rtsp_transport", "tcp", "-i", source] if str(source).startswith("rtsp") else ["-i", source]
    subprocess.run(["ffmpeg", "-y", *inp, "-c", "copy", "-f", "segment",
                    "-segment_time", str(segment_time), "-reset_timestamps", "1",
                    "-strftime", "1", pattern], capture_output=True)
    return out


def register_recordings(camera_id, rec_dir, segment_time=3):
    """디스크의 녹화 파일을 DB에 등록 (파일명 시각 → start/end)."""
    for f in sorted(glob.glob(os.path.join(rec_dir, "*.mp4"))):
        m = _NAME.search(os.path.basename(f))
        if not m:
            continue
        start = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        end = start + timedelta(seconds=segment_time)
        with conn() as c:
            c.execute("INSERT OR IGNORE INTO recordings(camera_id,file_path,start_time,end_time)"
                      " VALUES(?,?,?,?)", (camera_id, f,
                       start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")))


# ── 3) 재생/검색 — 기간으로 녹화 찾기 ────────────────────────────
def search_recordings(camera_id, start=None, end=None):
    q, p, where = "SELECT * FROM recordings", [], ["camera_id=?"]
    p.append(camera_id)
    if start: where.append("start_time>=?"); p.append(start)
    if end:   where.append("start_time<=?"); p.append(end)
    q += " WHERE " + " AND ".join(where) + " ORDER BY start_time"
    with conn() as c:
        return [dict(r) for r in c.execute(q, p).fetchall()]


# ── 실행 & 검증 ───────────────────────────────────────────────────
if __name__ == "__main__":
    if os.path.exists(DB):
        os.remove(DB)
    init_db()

    # 1) 카메라 등록
    cid = add_camera("창고 Camera 01", SAMPLE)
    print("[카메라] 등록 id:", cid, "| 목록:", list_cameras())

    # 2) 녹화 (샘플 6초 → 3초 세그먼트)
    rec_dir = record(cid, SAMPLE, os.path.join(HERE, "recordings"))
    register_recordings(cid, rec_dir)
    print("\n[녹화] 파일:", [os.path.basename(f) for f in glob.glob(rec_dir + "/*.mp4")])

    # 3) 검색 — 전체 / 기간
    recs = search_recordings(cid)
    print("\n[검색] 전체 녹화:", len(recs), "건")
    for r in recs:
        print("   ", r["start_time"], "→", r["end_time"], os.path.basename(r["file_path"]))
    print("\n재생: 위 file_path 를 <video>로 열거나 /api/recordings/file/... 로 제공")

    os.remove(DB)   # 데모 정리

# 👉 실제 완성본: vms/app/db.py · app/routes/cameras.py
#                · app/services/recording_service.py · app/routes/recordings.py
