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
# ★라마(2026-09-19): 문턱 0.28 은 텐트 안 같은 비슷한 shot 전환을 놓쳐 한 조각에 여러 구도가 섞였다 → 0.20
out = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-filter_complex",
                      "select='gt(scene,0.20)',metadata=print:file=-", "-f", "null", "-"],
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
    # ★라마(2026-09-19): 헬멧·위장 크림 얼굴은 검출이 절반 아래로 떨어진다. 30% 만 잡혀도 쓴다 —
    #   대신 아래에서 큰 얼굴만 남기고, 옮길 값이 작으면 그대로 둔다.
    if len(frames) < nsamp * 0.3:
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
    # ★라마(2026-09-19 사용자 "인물이 오버레이 밖으로 벗어난다"): 8/92 백분위는 shot 안에서 잠깐 가장자리로
    #   나가는 얼굴을 놓쳤다. 3/97 백분위 + 여백 5% 로 더 엄하게 본다. 0.995:1 이라 포레이로보다 좌우가 좁다.
    xl3, xr3 = np.percentile(keep[:, 0], 3), np.percentile(keep[:, 0] + keep[:, 2], 97)
    ok_in = (xl3 >= CX0 + CW0 * 0.05) and (xr3 <= CX0 + CW0 * 0.95)
    ok_big = fw_max >= CW0 * 0.115
    if ok_in and ok_big:
        REPORT.append((t0, t1, None, f"그대로 좋다 (얼굴폭 {fw_max/CW0*100:.0f}%)"))
        continue

    # 얼굴폭이 크롭폭의 20% 가 되게 — 얼빡은 아니고, 표정은 읽히는 크기
    w_target = fw_max / 0.20
    w_contain = (xr - xl) + fw_max * 1.1          # 양옆에 얼굴 반쪽씩 여백
    w = max(w_target, w_contain)
    w = min(w, SW, SH * AR, CW0)                  # 기본 크롭보다 넓게는 못 간다
    anchor = None
    if w < w_contain - 1:
        # ★다 못 담을 때(2026-09-19 라마 sb03): "큰 얼굴"이 아니라 **원본 화면 가운데 60% 안의 얼굴**을 닻으로 잡는다.
        #   가장자리에 걸린 큰 얼굴(원본에서도 잘린 사람)에 끌려가 정작 가운데 화자가 잘렸다.
        #   닻 얼굴은 반드시 담고, 남는 폭만큼 나머지 무리 쪽으로 붙인다.
        cen = keep[:, 0] + keep[:, 2] * 0.5
        mid = keep[(cen >= SW * 0.20) & (cen <= SW * 0.80)]
        if len(mid) == 0:
            mid = keep[np.argsort(-keep[:, 2])][:max(1, len(keep) // 2)]
        anchor = (float(np.percentile(mid[:, 0], 8)), float(np.percentile(mid[:, 0] + mid[:, 2], 92)))
        ycen = float(np.median(mid[:, 1] + mid[:, 3] * 0.5))
    # ★너무 좁게 자르면 1080 으로 늘릴 때 뭉갠다. 크롭폭은 기본의 60% 아래로 안 내린다.
    w = max(w, CW0 * 0.60)
    w = min(w, SW, SH * AR, CW0)
    if not getattr(spec, "REFRAME_ZOOM", True):
        w = float(CW0)          # ★라마: 배율 고정 — 옆으로 옮기기만 한다(2026-09-19 사용자 "템플릿 크기 고정")
    h = w / AR
    px = (xl + xr) / 2.0
    if anchor is not None:
        m = w * 0.04
        lo, hi = anchor[1] + m - w / 2.0, anchor[0] - m + w / 2.0     # 닻 얼굴이 다 들어오는 px 범위
        if lo <= hi:
            px = min(max(px, lo), hi)
        else:
            px = (anchor[0] + anchor[1]) / 2.0
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

# ── ★가장자리 검사 (2026-09-19 라마, 사용자 "인물이 오버레이 밖으로 벗어난다") ──────────
#   위에서 정한 크롭(그대로 둔 조각은 기본 크롭)으로 잘랐을 때 **큰 얼굴이 잘리는지** 조각마다 다시 본다.
#   잘리면 그 얼굴이 다 들어오도록 px 를 밀어 준다(폭은 그대로). 두 얼굴이 양끝이라 다 못 담으면
#   원본 가운데에 가까운 얼굴을 살린다. 헬멧·위장 얼굴은 검출이 드물어 한 프레임만 잡혀도 본다.
_ent = {(e[0], e[1]): e for e in ENTRIES}
_fixed = 0
cap = cv2.VideoCapture(SRC)
for (t0, t1) in pieces:
    e = _ent.get((t0, t1))
    if e:
        px, py, w = e[2], e[3], e[4] * CW0
    else:
        px, py, w = CX0 + CW0 / 2.0, CY0 + CH0 / 2.0, float(CW0)
    h = w / AR
    frames, nsamp = scan(t0, t1)
    # 원본 화면 끝에 이미 걸린 얼굴(뒤통수·어깨너머 앞사람)과 화면 22% 넘는 거대 얼굴은 잘린 게 아니라 구도다 — 뺀다
    boxes = [f for fr in frames for f in fr
             if CW0 * 0.12 <= f[2] <= SW * 0.22 and f[0] > 2 and f[0] + f[2] < SW - 2]
    if not boxes:
        continue
    B = np.array([[f[0], f[1], f[2], f[3]] for f in boxes], dtype=float)
    L, R = px - w / 2.0, px + w / 2.0
    m = w * 0.03
    cut = B[(B[:, 0] < L + m) | (B[:, 0] + B[:, 2] > R - m)]
    if len(cut) == 0:
        continue
    # 잘린 얼굴 중 원본 가운데에 가장 가까운 것을 살린다
    cen = cut[:, 0] + cut[:, 2] * 0.5
    f = cut[np.argmin(np.abs(cen - SW / 2.0))]
    fl, fr_ = float(np.percentile(cut[np.abs(cen - cen[np.argmin(np.abs(cen - SW / 2.0))]) < f[2]][:, 0], 10)),               float(np.percentile((cut[:, 0] + cut[:, 2])[np.abs(cen - cen[np.argmin(np.abs(cen - SW / 2.0))]) < f[2]], 90))
    lo, hi = fr_ + m - w / 2.0, fl - m + w / 2.0
    if lo > hi:                      # 얼굴이 크롭폭보다 넓다 — 얼굴 가운데로
        npx = (fl + fr_) / 2.0
    else:
        npx = min(max(px, lo), hi)
    npx = min(max(npx, w / 2.0), SW - w / 2.0)
    if abs(npx - px) < 4:
        continue
    if e:
        e[2] = round(npx, 1)
    else:
        ENTRIES.append([t0, t1, round(npx, 1), round(py, 1), round(w / CW0, 4)])
    _fixed += 1
    REPORT.append((t0, t1, ENTRIES[-1] if not e else e, f"가장자리에 잘린 얼굴 → 크롭을 {npx-px:+.0f}px 옮김"))
cap.release()
if _fixed:
    print(f"  ★가장자리 검사: {_fixed}조각의 크롭을 옮겼다")
ENTRIES.sort()
# ★같은 shot 안에서 맞붙은 조각끼리 크롭이 다르면 화면이 툭 뛴다 — 앞 조각 값으로 맞춘다(차이가 폭의 25% 안일 때).
_bset = set(round(b, 2) for b in bounds)
for i in range(1, len(ENTRIES)):
    p0, p1 = ENTRIES[i - 1], ENTRIES[i]
    if abs(p1[0] - p0[1]) <= 0.06 and not any(p0[1] - 0.05 <= b <= p1[0] + 0.05 for b in _bset):
        if abs(p1[2] - p0[2]) < p1[4] * CW0 * 0.25 and abs(p1[4] - p0[4]) < 0.05:
            p1[2], p1[3], p1[4] = p0[2], p0[3], p0[4]

json.dump({"src": SRC, "crop0": [CW0, CH0, CX0, CY0], "shots": ENTRIES},
          open("reframe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"  쓰는 구간 {len(used)}개 → shot 조각 {len(pieces)}개 · 다시 잡은 곳 {len(ENTRIES)}곳")
for t0, t1, e, why in REPORT:
    mark = "★" if e else " "
    print(f"  {mark} {t0:6.2f}~{t1:6.2f}  {why}")
print(f"  → {os.path.join(wd, 'reframe.json')}  (build.py 가 읽는다)")
