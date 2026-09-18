# -*- coding: utf-8 -*-
"""남의 채널 편집본에 깔린 **그 채널 나레 음성**을 지운다 (라마 지침서 §3).
사용:
    python scripts/mute_vocals.py <편폴더> 13.05-14.56 26.75-29.20 ...

하는 일
  1. src.mp4 의 소리를 demucs(htdemucs, two-stems)로 vocals / no_vocals 로 가른다
  2. 준 구간만 **vocals 스템에서** 0 으로 내리고(램프 0.03초) no_vocals 와 다시 섞는다 → 배경음은 끊기지 않는다
  3. src.mp4 를 새 소리로 다시 묶는다 (원본은 _src/src_before_mute.mp4)
  4. asr_ko.json 이 있으면 그 구간 낱말을 뺀다 (원본은 asr_ko_orig.json)

★demucs 는 전용 venv 가 아니라 **시스템 파이썬**(python 3.11 + torch CPU)에 있다. 없으면 `pip install demucs`.
★구간은 전사(asr_ko.json)에서 나레 낱말의 start/end 로 잡는다. 앞뒤 대사와 0.03초밖에 안 비는 곳이 흔하니
  대사 낱말을 물지 않게 경계를 정확히 적어라. 지운 뒤 dlgcheck 로 "자막 없는 말 0개"를 다시 확인한다.
"""
import json, os, shutil, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if len(sys.argv) < 3:
    sys.exit(__doc__)
wd = os.path.abspath(sys.argv[1])
spans = []
for a in sys.argv[2:]:
    s, e = a.split("-")
    spans.append((float(s), float(e)))

SRC = os.path.join(wd, "src.mp4")
sd = os.path.join(wd, "_src")
os.makedirs(sd, exist_ok=True)
before = os.path.join(sd, "src_before_mute.mp4")
if not os.path.exists(before):
    shutil.copy2(SRC, before)
wav = os.path.join(sd, "audio.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", before, "-vn", "-ac", "2", "-ar", "44100", wav], check=True)

sep = os.path.join(sd, "sep")
voc = os.path.join(sep, "htdemucs", "audio", "vocals.wav")
if not os.path.exists(voc):
    print("demucs 로 목소리를 가르는 중… (60초 소재에 30초쯤)")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    # ★venv 파이썬엔 demucs 가 없다. venv 가 PATH 앞에 있어도 시스템 파이썬을 찾아 쓴다.
    py = None
    for c in [os.environ.get("DEMUCS_PYTHON", ""),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python311", "python.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "python.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python313", "python.exe")]:
        if c and os.path.exists(c) and subprocess.run([c, "-c", "import demucs"], capture_output=True).returncode == 0:
            py = c
            break
    if not py:
        sys.exit("demucs 가 있는 파이썬을 못 찾았다 — 시스템 python 에 `pip install demucs` 하거나 DEMUCS_PYTHON 환경변수로 경로를 준다")
    r = subprocess.run([py, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", sep, wav],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(voc):
        sys.exit("demucs 실패 — 시스템 파이썬에 demucs 가 있는지 확인:\n" + (r.stderr or "")[-800:])
novoc = os.path.join(sep, "htdemucs", "audio", "no_vocals.wav")

R = 0.03
g = "*".join(f"(1-min(1,max(0,(t-{a})/{R}))*min(1,max(0,({b}-t)/{R})))" for a, b in spans)
fc = f"[0:a]volume='{g}':eval=frame[v];[v][1:a]amix=inputs=2:normalize=0:duration=longest[a]"
fcf = os.path.join(sd, "_fc_mute.txt")
open(fcf, "w", encoding="utf-8").write(fc)
mixed = os.path.join(sd, "mixed.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", voc, "-i", novoc, "-/filter_complex", fcf,
                "-map", "[a]", "-ar", "48000", mixed], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", before, "-i", mixed, "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", SRC], check=True)
print("지운 구간:", " ".join(f"{a:.2f}~{b:.2f}" for a, b in spans), "→ src.mp4 (원본 _src/src_before_mute.mp4)")

asr = os.path.join(wd, "asr_ko.json")
if os.path.exists(asr):
    orig = os.path.join(wd, "asr_ko_orig.json")
    if not os.path.exists(orig):
        shutil.copy2(asr, orig)
    d = json.load(open(orig, encoding="utf-8"))
    def inside(w):
        return any(a - 0.01 <= w["start"] and w["end"] <= b + 0.01 for a, b in spans)
    n0 = len(d["words"])
    d["words"] = [w for w in d["words"] if not inside(w)]
    json.dump(d, open(asr, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"asr_ko.json 낱말 {n0} → {len(d['words'])} (뺀 것은 asr_ko_orig.json 에 남아 있다)")
print("다음: dlgcheck 로 자막 없는 말 0개 확인 → 이어서 진행")
