# -*- coding: utf-8 -*-
"""src.mp4 의 **배경음악을 빼고 목소리만** 남긴다 (라마, 2026-09-25 사용자 "배경음악 다 지워줘").
사용:
    python scripts/devocal_src.py <편폴더>

하는 일
  1. 지금 src.mp4 를 _src/src_with_bgm.mp4 로 한 번만 떠 둔다 (mute_vocals 를 먼저 했으면 그 결과가 들어간다)
  2. demucs(htdemucs, two-stems)로 vocals 만 뽑는다 → _src/sep_devocal/
  3. src.mp4 를 vocals 소리로 다시 묶는다 (그림은 복사)
  4. _src/devocal.json 도장 — build.py 가 보고 BED_LIFT_DEVOCAL(m=3)을 쓴다
되돌리기: _src/src_with_bgm.mp4 를 src.mp4 로 되돌리고 _src/devocal.json 을 지운다.
★demucs 는 시스템 파이썬에 있다 (mute_vocals.py 와 같은 방식으로 찾는다).
"""
import json, os, shutil, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if len(sys.argv) < 2:
    sys.exit(__doc__)
wd = os.path.abspath(sys.argv[1])
SRC = os.path.join(wd, "src.mp4")
sd = os.path.join(wd, "_src")
os.makedirs(sd, exist_ok=True)
keep = os.path.join(sd, "src_with_bgm.mp4")
if not os.path.exists(keep):
    shutil.copy2(SRC, keep)
wav = os.path.join(sd, "bgm_audio.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", keep, "-vn", "-ac", "2", "-ar", "44100", wav], check=True)

sep = os.path.join(sd, "sep_devocal")
voc = os.path.join(sep, "htdemucs", "bgm_audio", "vocals.wav")
if not os.path.exists(voc):
    print("demucs 로 목소리만 뽑는 중…", flush=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    py = None
    for c in [os.environ.get("DEMUCS_PYTHON", ""),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python311", "python.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "python.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python313", "python.exe")]:
        if c and os.path.exists(c) and subprocess.run([c, "-c", "import demucs"], capture_output=True).returncode == 0:
            py = c
            break
    if not py:
        sys.exit("demucs 가 있는 파이썬을 못 찾았다 — DEMUCS_PYTHON 환경변수로 경로를 준다")
    r = subprocess.run([py, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", sep, wav],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(voc):
        sys.exit("demucs 실패:\n" + (r.stderr or "")[-800:])

subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", keep, "-i", voc, "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", SRC], check=True)
json.dump({"stem": "vocals", "model": "htdemucs", "from": "_src/src_with_bgm.mp4"},
          open(os.path.join(sd, "devocal.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("배경음악 제거 → src.mp4 (원본 _src/src_with_bgm.mp4) · 도장 _src/devocal.json")
