# -*- coding: utf-8 -*-
"""말하는 사람이 화면 밖으로 잘리거나 콩알만 하게 나오는 걸 막는다 (§17-17).

왜 필요한가
  16:9 원본에서 **가운데만** 세로로 잘라내기 때문에, 인물이 좌우로 치우친 shot 은
  얼굴이 통째로 날아간다. 넓은 shot 은 사람이 콩알만 해져서 "말하는 사람이 안 보인다"는
  지적을 받았다(사용자: "말할 때 그 화자가 얼굴 보이게 만들어, 너무 얼빡 안 해도 되고
  화면에 두 사람이 나올 수도 있잖아, 화면 안에 잘 배치해봐").

무엇을 하나
  그 편이 **실제로 쓰는 소재 구간**만 훑어 얼굴을 찾고, shot 마다
  얼굴이 다 들어오면서 너무 작지도 않은 크롭을 계산해 <편폴더>/reframe.json 에 적는다.
  build.py 가 이 파일을 읽어 구간마다 다른 크롭을 쓴다.

  사용: python presets\라마\reframe.py <편폴더> [--force]
  손으로 덮어쓰려면 episode.py 에
      CROP_SHOT = [(소재시작, 소재끝, 중심x, 중심y, 폭배율), ...]
  를 적는다. **episode.py 가 이 파일보다 세다.**
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
import cv2

wd = os.path.abspath(sys.argv[1])
sys.path.insert(0, wd)
import episode
import spec
os.chdir(wd)

SRC = getattr(episode, "SRC", "src.mp4")
if not os.path.exists(SRC):
    sys.exit(f"소재가 없다: {SRC}")

pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height", "-of", "json", SRC],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout)
SW, SH = pr["streams"][0]["width"], pr["streams"][0]["height"]
_HSTOP = getattr(episode, "HARDSUB_TOP", None)
_, (CW0, CH0, CX0, CY0) = spec.crop_filter(SW, SH, _HSTOP)
AR = CW0 / float(CH0)
# ★크롭 아래끝이 넘어가면 안 되는 선. 하드섭이 있으면 그 띠 위, 없으면 소재 아래끝.
_YMAX = float(_HSTOP) if _HSTOP else float(SH)

# ── 이 편이 실제로 쓰는 소재 구간 ──────────────────────────
used = []
for b in episode.BLOCKS:
    if b[0] == "N":
        for a, z in (b[2] if len(b) > 2 else []):
            used.append((float(a), float(z)))
    elif b[0] == "D":
        s1 = float(b[2])
        if isinstance(b[3], (list, tuple)) and b[3]:
            s1 = max(s1, max(x[2] for x in b[3]) + getattr(spec, "DLG_TAIL", 0.34))
        used.append((float(b[1]), s1))
for a, z in getattr(episode, "CUTS", []):
    used.append((float(a), float(z)))
used = sorted(set(used))
if not used:
    sys.exit("쓰는 구간이 없다")

# ── shot 경계 ─────────────────────────────────────────────
out = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-filter_complex",
                      "select='gt(scene,0.28)',metadata=print:file=-", "-f", "null", "-"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
bounds = sorted(float(m) for m in re.findall(r"pts_time:([0-9.]+)", out.stdout + out.stderr))
DUR = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout.strip())
edges = [0.0] + bounds + [DUR + 1.0]

# ── 구간 × shot 으로 쪼갠다 ───────────────────────────────
pieces = []
for a, z in used:
    for i in range(len(edges) - 1):
        s, e = max(a, edges[i]), min(z, edges[i + 1])
        if e - s > 0.18:
            pieces.append((round(s, 2), round(e, 2)))
pieces = sorted(set(pieces))

# ── 얼굴 찾기 ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(HERE))
MODEL = os.path.join(ROOT, "models", "yunet.onnx")
if not os.path.exists(MODEL):
    sys.exit(f"얼굴 모델이 없다: {MODEL}  (bootstrap.py 를 돌려라)")
if not MODEL.isascii():          # ★한글 경로면 윈도우 OpenCV 가 못 읽는다(§18-4)
    import shutil, tempfile
    _d = os.path.join(tempfile.gettempdir(), "volcano_models")
    if not _d.isascii():
        _d = "C:/vol_models"
    os.makedirs(_d, exist_ok=True)
    _a = os.path.join(_d, "yunet.onnx")
    if not os.path.exists(_a) or os.path.getsize(_a) != os.path.getsize(MODEL):
        shutil.copyfile(MODEL, _a)
    MODEL = _a
det = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), 0.55, 0.3, 5000)
det.setInputSize((SW, SH))

cap = cv2.VideoCapture(SRC)
FPS = cap.get(cv2.CAP_PROP_FPS) or 30.0
MINF = SW * 0.018            # 이보다 작은 얼굴은 배경 사람으로 보고 버린다


def scan(t0, t1):
    """샘플한 프레임 수와, 그 중 얼굴이 잡힌 프레임들의 상자."""
    got, n = [], 0
    t = t0 + 0.05
    while t < t1:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * FPS)))
        ok, fr = cap.read()
        if ok:
            n += 1
            _, fs = det.detect(fr)
            if fs is not None and len(fs):
                keep = [f for f in fs if f[2] >= MINF]
                if keep:
                    got.append(keep)
        t += 0.20
    return got, max(1, n)


ENTRIES = []
REPORT = []
for (t0, t1) in pieces:
    frames, nsamp = scan(t0, t1)
    boxes = [f for fr in frames for f in fr]
    if not boxes:
        REPORT.append((t0, t1, None, "얼굴 못 찾음 — 그대로 둔다"))
        continue
    # ★샘플의 절반도 못 잡았으면 믿지 않는다.
    #   벽에 붙은 사진·배경 사람 하나를 얼굴로 잡고 화면을 통째로 옮긴 사고가 있었다(§17-17).
    if len(frames) < nsamp * 0.5:
        REPORT.append((t0, t1, None, f"얼굴이 {len(frames)}/{nsamp} 프레임에서만 잡힘 — 못 믿어서 그대로 둔다"))
        continue
    B = np.array([[f[0], f[1], f[2], f[3]] for f in boxes], dtype=float)
    fw_max = float(np.median([max(f[2] for f in fr) for fr in frames if fr] or [0]))
    if fw_max <= CW0 * 0.05:
        # ★이만큼 작으면 사람인지 벽 사진인지 가릴 수 없고, 키워 봐야 뭉갠다.
        REPORT.append((t0, t1, None, f"얼굴이 너무 작다({fw_max/CW0*100:.0f}%) — 그대로 둔다"))
        continue

    # 큰 얼굴만 남긴다 — 배경에 스쳐 지나가는 사람에 끌려가지 않게
    keep = B[B[:, 2] >= fw_max * 0.55]
    if len(keep) == 0:
        keep = B
    xl, xr = np.percentile(keep[:, 0], 8), np.percentile(keep[:, 0] + keep[:, 2], 92)
    ycen = float(np.median(keep[:, 1] + keep[:, 3] * 0.5))

    # 지금 크롭(가운데 고정)으로 충분한가?
    ok_in = (xl >= CX0 + CW0 * 0.02) and (xr <= CX0 + CW0 * 0.98)
    ok_big = fw_max >= CW0 * 0.115
    if ok_in and ok_big:
        REPORT.append((t0, t1, None, f"그대로 좋다 (얼굴폭 {fw_max/CW0*100:.0f}%)"))
        continue

    # 얼굴폭이 크롭폭의 20% 가 되게 — 얼빡은 아니고, 표정은 읽히는 크기
    w_target = fw_max / 0.20
    w_contain = (xr - xl) + fw_max * 1.1          # 양옆에 얼굴 반쪽씩 여백
    w = max(w_target, w_contain)
    w = min(w, SW, SH * AR, CW0)                  # 기본 크롭보다 넓게는 못 간다
    if w < w_contain - 1:                         # 다 못 담으면 큰 얼굴 쪽만 담는다
        big = keep[np.argsort(-keep[:, 2])][:max(1, len(keep) // 2)]
        xl, xr = np.percentile(big[:, 0], 8), np.percentile(big[:, 0] + big[:, 2], 92)
        ycen = float(np.median(big[:, 1] + big[:, 3] * 0.5))
    # ★너무 좁게 자르면 1080 으로 늘릴 때 뭉갠다. 크롭폭은 기본의 60% 아래로 안 내린다.
    w = max(w, CW0 * 0.60)
    w = min(w, SW, SH * AR, CW0)
    h = w / AR
    px = (xl + xr) / 2.0
    py = ycen + h * 0.10                          # 눈높이를 화면 위쪽 40% 근처로
    px = min(max(px, w / 2.0), SW - w / 2.0)
    # ★★아래끝을 **하드섭 띠 위**로 막는다(2026-09-13에 당했다 — PLAYBOOK §17-30).
    #   SH(소재 전체 높이)로 막으면 화자를 따라 크롭이 내려가면서
    #   `crop_filter` 가 애써 잘라낸 원본 자막이 **그 구간만 도로 살아난다.**
    #   g26 에서 세 구간(18.4·22.4·178.8초)의 아래끝이 941~987 로 내려가 905 를 침범했다.
    py = min(max(py, h / 2.0), _YMAX - h / 2.0)
    if abs(px - (CX0 + CW0 / 2.0)) < CW0 * 0.03 and abs(w - CW0) < CW0 * 0.03             and abs(py - (CY0 + CH0 / 2.0)) < CH0 * 0.03:
        REPORT.append((t0, t1, None, f"그대로 좋다 (얼굴폭 {fw_max/CW0*100:.0f}%, 옮길 값이 없다)"))
        continue
    ENTRIES.append([t0, t1, round(px, 1), round(py, 1), round(w / CW0, 4)])
    REPORT.append((t0, t1, ENTRIES[-1], f"얼굴폭 {fw_max/CW0*100:.0f}% → {w/CW0:.2f}배로 다시 잡음"))

cap.release()

json.dump({"src": SRC, "crop0": [CW0, CH0, CX0, CY0], "shots": ENTRIES},
          open("reframe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"  쓰는 구간 {len(used)}개 → shot 조각 {len(pieces)}개 · 다시 잡은 곳 {len(ENTRIES)}곳")
for t0, t1, e, why in REPORT:
    mark = "★" if e else " "
    print(f"  {mark} {t0:6.2f}~{t1:6.2f}  {why}")
print(f"  → {os.path.join(wd, 'reframe.json')}  (build.py 가 읽는다)")
