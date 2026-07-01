"""녹화 — ffmpeg 세그먼트 muxer로 영상을 타임스탬프 mp4 파일로 저장."""
import glob
import os
import re
import subprocess
from datetime import datetime, timedelta

from .. import db

_procs = {}   # camera_id -> Popen
_NAME = re.compile(r"(\d{8})_(\d{6})\.mp4$")


def start_recording(camera_id, source, rec_dir, segment_time=60):
    cid = str(camera_id)
    p = _procs.get(cid)
    if p and p.poll() is None:
        return
    out = os.path.join(rec_dir, cid)
    os.makedirs(out, exist_ok=True)
    inp = ["-rtsp_transport", "tcp", "-i", source] if str(source).startswith("rtsp") else ["-i", source]
    pattern = os.path.join(out, "%Y%m%d_%H%M%S.mp4")
    cmd = ["ffmpeg", "-y", *inp, "-c", "copy", "-f", "segment",
           "-segment_time", str(segment_time), "-reset_timestamps", "1",
           "-strftime", "1", pattern]
    _procs[cid] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_recording(camera_id):
    p = _procs.pop(str(camera_id), None)
    if p and p.poll() is None:
        p.terminate()


def is_recording(camera_id):
    p = _procs.get(str(camera_id))
    return bool(p and p.poll() is None)


def scan_and_register(camera_id, rec_dir, segment_time=60):
    """디스크의 녹화 파일을 DB에 등록(파일명 타임스탬프 → start/end)."""
    out = os.path.join(rec_dir, str(camera_id))
    for f in sorted(glob.glob(os.path.join(out, "*.mp4"))):
        m = _NAME.search(os.path.basename(f))
        if not m:
            continue
        start = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        end = start + timedelta(seconds=segment_time)
        name = os.path.basename(f)
        db.register_recording(camera_id, f"/api/recordings/file/{camera_id}/{name}",
                              start.isoformat(timespec="seconds"),
                              end.isoformat(timespec="seconds"))
