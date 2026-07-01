"""RTSP → HLS 변환 — 카메라별 ffmpeg 프로세스 관리."""
import os
import subprocess

_procs = {}   # camera_id -> Popen


def _build_cmd(source, m3u8, seg_time, list_size):
    inp = ["-rtsp_transport", "tcp", "-i", source] if source.startswith("rtsp") \
        else ["-stream_loop", "-1", "-re", "-i", source]   # 파일은 반복 재생(데모)
    return ["ffmpeg", "-y", *inp,
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            # 세그먼트 경계마다 키프레임 강제 → 첫 세그먼트가 제때 닫힘
            "-force_key_frames", f"expr:gte(t,n_forced*{seg_time})",
            "-an", "-f", "hls",
            "-hls_time", str(seg_time), "-hls_list_size", str(list_size),
            "-hls_flags", "delete_segments", m3u8]


def start(camera_id, source, hls_dir, seg_time=2, list_size=6):
    cid = str(camera_id)
    p = _procs.get(cid)
    if p and p.poll() is None:
        return f"/static/hls/{cid}/index.m3u8"
    out_dir = os.path.join(hls_dir, cid)
    os.makedirs(out_dir, exist_ok=True)
    m3u8 = os.path.join(out_dir, "index.m3u8")
    _procs[cid] = subprocess.Popen(_build_cmd(source, m3u8, seg_time, list_size),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"/static/hls/{cid}/index.m3u8"


def stop(camera_id):
    cid = str(camera_id)
    p = _procs.pop(cid, None)
    if p and p.poll() is None:
        p.terminate()


def is_running(camera_id):
    p = _procs.get(str(camera_id))
    return bool(p and p.poll() is None)
