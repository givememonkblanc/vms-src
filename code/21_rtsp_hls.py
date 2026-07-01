"""
=====================================================================
 슬라이드 21 · RTSP → HLS 실시간 스트리밍
=====================================================================
문제: 카메라는 RTSP로 영상을 보내는데, 웹 브라우저는 RTSP를 못 본다.
해결: ffmpeg로 RTSP를 HLS로 변환한다.
      - HLS = 영상을 2초짜리 .ts 조각으로 잘라 .m3u8 '재생목록'으로 제공
      - HTTP 기반이라 브라우저 <video> + hls.js 로 바로 재생된다.

핵심 ffmpeg 옵션 (왜 쓰는가):
  -stream_loop -1 -re   : (파일일 때) 실시간 속도로 무한 반복 — 카메라 흉내
  -rtsp_transport tcp    : (RTSP일 때) UDP 패킷 유실 줄이려 TCP 사용
  -c:v libx264           : H.264로 인코딩 (브라우저 호환)
  -force_key_frames ...  : 세그먼트 경계마다 키프레임 강제
                           → 없으면 첫 조각이 안 닫혀 한참 뒤에야 재생됨(중요!)
  -hls_time 2            : 세그먼트 길이 2초
  -hls_list_size 6       : 재생목록에 최근 6개만 유지
  -hls_flags delete_segments : 오래된 .ts 자동 삭제 (디스크 보호)

실행:  python 13_rtsp_hls.py
=====================================================================
"""
import os
import subprocess
import time
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "..", "vms", "samples", "sample.mp4")  # 카메라 대신

# 카메라별 ffmpeg 프로세스를 관리 (시작/중지)
_procs = {}


def start_hls(camera_id, source, out_root, seg_time=2, list_size=6):
    """source(RTSP 또는 파일)를 HLS로 변환 시작. (프로세스, m3u8경로) 반환."""
    cid = str(camera_id)
    # 이미 돌고 있으면 중복 실행 방지
    if _procs.get(cid) and _procs[cid].poll() is None:
        return _procs[cid], os.path.join(out_root, cid, "index.m3u8")

    out_dir = os.path.join(out_root, cid)
    os.makedirs(out_dir, exist_ok=True)
    m3u8 = os.path.join(out_dir, "index.m3u8")

    # 입력 옵션: RTSP면 TCP, 파일이면 실시간 반복재생
    if str(source).startswith("rtsp"):
        inp = ["-rtsp_transport", "tcp", "-i", source]
    else:
        inp = ["-stream_loop", "-1", "-re", "-i", source]

    cmd = ["ffmpeg", "-y", *inp,
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
           "-force_key_frames", f"expr:gte(t,n_forced*{seg_time})",
           "-an",                                  # 오디오 제거(관제용)
           "-f", "hls",
           "-hls_time", str(seg_time),
           "-hls_list_size", str(list_size),
           "-hls_flags", "delete_segments",
           m3u8]
    # stderr는 ffmpeg 진행로그 — 데모에선 버린다
    _procs[cid] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return _procs[cid], m3u8


def stop_hls(camera_id):
    p = _procs.pop(str(camera_id), None)
    if p and p.poll() is None:
        p.terminate()


# ── 실제 앱에선 이렇게 라우트로 노출한다 (app/routes/stream.py) ──
#   @stream_bp.post("/<int:cid>/start")
#   def start(cid):
#       cam = db.get_camera(cid)                       # DB에서 RTSP URL 조회
#       _, url = start_hls(cid, cam["rtsp_url"], HLS_DIR)
#       return jsonify({"hls_url": "/static/hls/%d/index.m3u8" % cid})
#   → 브라우저: hls.js 로 그 url 을 재생 (슬라이드 25)


# ── 실행 & 검증: "진짜 영상이 만들어지는가?" ─────────────────────
if __name__ == "__main__":
    out_root = os.path.join(HERE, "hls_out")
    print("HLS 변환 시작...", os.path.basename(SAMPLE))
    proc, m3u8 = start_hls(1, SAMPLE, out_root)

    print("첫 세그먼트 생성 대기 (6초)...")
    time.sleep(6)

    seg = sorted(glob.glob(os.path.join(os.path.dirname(m3u8), "*.ts")))
    print("\n[결과] m3u8 생성:", os.path.exists(m3u8), "| .ts 세그먼트:", len(seg), "개")

    # 재생목록 내용 확인
    if os.path.exists(m3u8):
        print("\n[index.m3u8 내용]")
        print(open(m3u8).read().strip())

    # ⭐ 핵심 검증: .ts 가 진짜 재생 가능한 H.264 영상인지 ffprobe로 확인
    if seg:
        info = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height",
             "-of", "default=noprint_wrappers=1", seg[0]],
            capture_output=True, text=True).stdout.strip()
        print("\n[ffprobe — 진짜 영상 확인]\n" + info)

    stop_hls(1)
    print("\n변환 중지. 브라우저에선:  <video> + hls.js 로 index.m3u8 재생")

# 👉 실제 완성본: vms/app/services/hls_service.py · app/routes/stream.py
