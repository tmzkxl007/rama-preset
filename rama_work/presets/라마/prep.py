# -*- coding: utf-8 -*-
"""라마 편 준비.  사용:
    python prep.py <편폴더> <URL 또는 로컬파일>   [시작초] [끝초]

하는 일
  1. 소재를 편 폴더에 `src.mp4` 로 놓는다 (URL 이면 yt-dlp, 로컬이면 복사)
  2. 원본에 박힌 자막 띠(하드섭)를 찾아 HARDSUB_TOP 을 잡는다
  3. 장면 전환을 훑어 **컷 후보**를 뽑는다  → cuts_candidates.txt
  4. `episode.py` 뼈대를 만든다 (없을 때만)
  ★라마: 소재가 **세로(H>W) 쇼츠 편집본**이면 위 제목띠·아래 로고를 뺀 **그림 칸만** 잘라 src.mp4 로 만든다
    (원본은 _src/raw.mp4). 그림 안에 남의 자막이 있으면 2번 하드섭 검출이 잡고, episode.py 에 spec.ZOOM=1.0 힌트를 적는다.
    남의 나레 음성은 따로 `scripts/mute_vocals.py` 로 지운다 (docs/라마-지침서.md §3).

★소재 권한은 사람이 확인한다. 불법 스트리밍 사이트 파일은 쓰지 않는다(PLAYBOOK §8).
"""
import os, shutil, subprocess, sys

# 윈도우 콘솔은 cp949 라 em-dash 하나에도 죽는다. 출력만 UTF-8 로 돌린다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
import spec

if len(sys.argv) < 3:
    sys.exit(__doc__)
wd = os.path.abspath(sys.argv[1])
srcarg = sys.argv[2]
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else None
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else None
os.makedirs(wd, exist_ok=True)
SRC = os.path.join(wd, "src.mp4")
PY = sys.executable

# ── 1. 소재 ─────────────────────────────────────────────
if not os.path.exists(SRC):
    if srcarg.startswith(("http://", "https://")):
        print("소재 받는 중…")
        cmd = [PY, "-m", "yt_dlp", "-f", "bv*[height<=1080]+ba/b",
               "--merge-output-format", "mp4", "-o", SRC, "--no-warnings",
               "--sleep-requests", "2", srcarg]
        if t0 is not None and t1 is not None:
            cmd[-1:-1] = ["--download-sections", f"*{t0}-{t1}", "--force-keyframes-at-cuts"]
        subprocess.run(cmd, check=True)
    else:
        if not os.path.exists(srcarg):
            sys.exit(f"소재가 없다: {srcarg}")
        if t0 is not None and t1 is not None:
            print(f"{t0}~{t1}초 잘라내는 중…")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-to", str(t1),
                            "-i", srcarg, "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                            "-c:a", "aac", "-b:a", "192k", SRC], check=True)
        else:
            shutil.copy2(srcarg, SRC)
print("소재:", SRC)

# ── 1-2. ★세로 쇼츠 편집본이면 그림 칸만 오린다 (라마 지침서 §3) ──
import json
import numpy as np, cv2
_pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=width,height", "-of", "json", SRC],
                                capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
_W, _H = _pr["streams"][0]["width"], _pr["streams"][0]["height"]
VERT_HINT = None
if _H > _W and not os.path.exists(os.path.join(wd, "_src", "raw.mp4")):
    cap = cv2.VideoCapture(SRC)
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    acc = np.zeros(_H)
    for i in np.linspace(0, max(0, N - 1), 120).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        acc = np.maximum(acc, (g > 12).mean(axis=1))      # ★프레임별 max — 평균은 어두운 장면에 속는다(§17-47)
    cap.release()
    rows = np.where(acc > 0.3)[0]
    runs, s0, p0 = [], rows[0], rows[0]
    for r in rows[1:]:
        if r != p0 + 1:
            runs.append((s0, p0)); s0 = r
        p0 = r
    runs.append((s0, p0))
    y0, y1 = max(runs, key=lambda ab: ab[1] - ab[0])
    y0, y1 = int(y0), int(y1) + 1
    if (y1 - y0) < _H * 0.9:
        os.makedirs(os.path.join(wd, "_src"), exist_ok=True)
        raw = os.path.join(wd, "_src", "raw.mp4")
        shutil.move(SRC, raw)
        h = (y1 - y0) // 2 * 2
        print(f"  세로 소재 {_W}x{_H} → 그림 칸 y{y0}~{y1} 만 오린다 ({_W}x{h}) · 원본은 _src/raw.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vf", f"crop={_W}:{h}:0:{y0}",
                        "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", SRC], check=True)
        VERT_HINT = (y0, y1)

pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height,r_frame_rate",
                                "-show_entries", "format=duration", "-of", "json", SRC],
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
W = pr["streams"][0]["width"]
H = pr["streams"][0]["height"]
DUR = float(pr["format"]["duration"])
print(f"  {W}x{H} · {DUR:.1f}초")

# ── 2. 하드섭 띠 찾기 ───────────────────────────────────

cap = cv2.VideoCapture(SRC)
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)
# ★★프레임 평균을 쓰면 안 된다(2026-09-13에 당했다 — PLAYBOOK §17-30).
#   자막이 **두 줄**일 때만 쓰이는 윗줄은 전체 프레임의 몇 %에만 나온다.
#   200장 평균을 내면 그 행이 문턱 아래로 깔려, 검출기가 **아랫줄 위쪽**을 띠로 잡는다.
#   → 경성크리처 1화에서 실제 띠는 y905 인데 y931 로 잡혀 **윗줄이 완성본에 그대로 남았다.**
#   프레임마다 "자막처럼 보이는 행"을 세고, **몇 장에서만 나와도** 띠로 인정한다.
# ★흰 픽셀만 세면 밝은 화면을 자막으로 오인한다 → 흰 글자 옆 ±7px 에 검은 테두리가 있는 것만.
hits = np.zeros(H, dtype=int)
sampled = 0
for i in np.linspace(0, max(0, N - 1), 200).astype(int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
    ok, f = cap.read()
    if not ok:
        continue
    sampled += 1
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    wh = g >= 240
    dk = g <= 50
    near = np.zeros_like(dk)
    for k in range(1, 8):
        near[:, k:] |= dk[:, :-k]
        near[:, :-k] |= dk[:, k:]
    hits += ((wh & near).sum(axis=1) > 12)
cap.release()
need = max(2, sampled // 25)          # 200장 중 8장에만 나와도 자막 띠로 본다
low = hits[int(H * 0.72):]
hot = np.where(low >= need)[0]
HARDSUB_TOP = int(H * 0.72) + int(hot.min()) - 8 if len(hot) else None
print("  하드섭 띠 위쪽:", HARDSUB_TOP if HARDSUB_TOP else "없음",
      f"(표본 {sampled}장 중 {need}장 이상에서 잡힌 맨 윗줄)")

# ── 3. 컷 후보 ──────────────────────────────────────────
print("장면 전환 훑는 중…")
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", SRC,
                    "-vf", "select='gt(scene,0.30)',metadata=print:file=-",
                    "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
ts = []
for ln in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if "pts_time:" in ln:
        try:
            ts.append(float(ln.split("pts_time:")[1].split()[0]))
        except Exception:
            pass
ts = sorted(set(round(t, 2) for t in ts))
lines = ["# 장면 전환 지점. 여기서 골라 episode.py 의 CUTS 에 (시작, 끝) 로 넣어라.",
         f"# 소재 {DUR:.1f}초 · 전환 {len(ts)}곳",
         "# ★0번 컷은 이 목록과 상관없이 '가장 센 그림'을 직접 골라 맨 앞에 넣어라(§17-9).",
         ""]
for a, b in zip(ts, ts[1:] + [DUR]):
    if b - a >= 0.4:
        lines.append(f"({a:.2f}, {min(b, a+3.0):.2f}),   # {b-a:.1f}초짜리 장면")
open(os.path.join(wd, "cuts_candidates.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"  컷 후보 {len(lines)-4}개 → cuts_candidates.txt")

# ── 4. episode.py 뼈대 ──────────────────────────────────
EP = os.path.join(wd, "episode.py")
if os.path.exists(EP):
    print("episode.py 는 이미 있다 — 건드리지 않는다")
else:
    tpl = open(os.path.join(HERE, "episode_template.py"), encoding="utf-8").read()
    tpl = tpl.replace("HARDSUB_TOP = None",
                      f"HARDSUB_TOP = {HARDSUB_TOP}" if HARDSUB_TOP else "HARDSUB_TOP = None")
    tpl = tpl.replace('OUT = "ep01.mp4"', f'OUT = "{os.path.basename(wd)}.mp4"')
    if VERT_HINT:
        tpl = tpl.replace("spec.ZOOM = 0.60", "spec.ZOOM = 1.0   # 세로 쇼츠 그림 칸 — 폭을 다 쓰고 HARDSUB_TOP 위만")
    open(EP, "w", encoding="utf-8").write(tpl)
    print("뼈대:", EP)

print("\n다음: episode.py 의 HEAD1/HEAD2 · BLOCKS · CUTS · EFFECTS 를 채운 뒤")
print(f"  python {os.path.join(HERE,'get_fonts.py')} {wd}")
print(f"  python {os.path.join(HERE,'tts.py')} {wd}")
print(f"  python {os.path.join(HERE,'build.py')} {wd}")
