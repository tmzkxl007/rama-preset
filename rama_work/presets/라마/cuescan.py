# -*- coding: utf-8 -*-
"""화면에 박힌 자막(하드섭)이 **뜨고 사라지는 시각**을 재서 대사 덩이를 뽑는다.

    python cuescan.py <편폴더> [간격초=0.1] [--json]

왜 필요한가 — 전사(ASR)가 막혔을 때(키 만료·음질 불량·외국어)의 대안이다.
하드섭은 **원본 자막의 공식 시각**이라, 사실 낱말 전사보다 대사 덩이를 잡기에 정확하다.
글자는 어차피 사람이 화면에서 읽어 넣어야 하므로(§8), 여기서는 **시각만** 뽑는다.

원리 — 자막 띠(HARDSUB_TOP 아래) 안에서
  흰 글자(≥240) 옆 ±7px 에 검은 테두리(≤50)가 있는 행을 센다(§17-10 과 같은 잣대).
  그런 행이 6줄 이상이면 '자막이 떠 있다'로 본다. 이어지는 프레임을 한 덩이로 묶는다.

결과 — `cues.json` (시작·끝·길이) + 화면 출력.
  `--json` 을 주면 `dlgcheck` 가 읽는 asr.json 꼴로도 저장한다(`cues_asr.json`).
  덩이 하나를 낱말 하나처럼 넣어, 자막이 그 구간을 덮는지 검사할 수 있다.
"""
import io, json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
import cv2

if len(sys.argv) < 2:
    sys.exit(__doc__)
wd = os.path.abspath(sys.argv[1])
step_s = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else 0.1
want_asr = "--json" in sys.argv

sys.path.insert(0, wd)
import importlib.util
spec_ = importlib.util.spec_from_file_location("episode", os.path.join(wd, "episode.py"))
HARDSUB_TOP = None
if spec_:
    try:
        ep = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(ep)
        HARDSUB_TOP = getattr(ep, "HARDSUB_TOP", None)
    except Exception:
        pass

SRC = os.path.join(wd, "src.mp4")
cap = cv2.VideoCapture(SRC)
if not cap.isOpened():
    sys.exit("소재를 못 연다: " + SRC)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
y0 = int(HARDSUB_TOP) if HARDSUB_TOP else int(H * 0.82)
y1 = H
print("%s  %d프레임 %.2ffps · 자막 띠 y%d~%d · %.2f초 간격" % (
    os.path.basename(wd), n, fps, y0, y1, step_s))

step = max(1, int(round(fps * step_s)))
on = []
for i in range(0, n, step):
    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
    ok, f = cap.read()
    if not ok:
        break
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[y0:y1]
    wh = g >= 240
    dk = g <= 50
    near = np.zeros_like(dk)
    for k in range(1, 8):
        near[:, k:] |= dk[:, :-k]
        near[:, :-k] |= dk[:, k:]
    rows = ((wh & near).sum(axis=1) > 12).sum()
    on.append((i / fps, rows >= 6))
cap.release()

# 이어지는 '떠 있음'을 한 덩이로. 0.2초 이하의 끊김은 같은 덩이로 본다.
cues, cur = [], None
GAP = 0.25
for t, hit in on:
    if hit:
        if cur is None:
            cur = [t, t]
        else:
            cur[1] = t
    else:
        if cur is not None and t - cur[1] > GAP:
            cues.append(cur); cur = None
if cur is not None:
    cues.append(cur)
cues = [c for c in cues if c[1] - c[0] >= 0.3]

print("자막 덩이 %d개" % len(cues))
for a, b in cues:
    print("  %7.2f ~ %7.2f  (%.2f초)" % (a, b + step_s, b + step_s - a))

json.dump([{"start": round(a, 2), "end": round(b + step_s, 2)} for a, b in cues],
          io.open(os.path.join(wd, "cues.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("→ cues.json")

if want_asr:
    # dlgcheck 가 읽는 꼴. 덩이 하나를 낱말 하나로 넣는다.
    words = [{"word": "자막%d" % (k + 1), "start": round(a, 2), "end": round(b + step_s, 2)}
             for k, (a, b) in enumerate(cues)]
    out = {"segments": [{"start": w["start"], "end": w["end"], "text": w["word"]} for w in words],
           "words": words}
    json.dump(out, io.open(os.path.join(wd, "cues_asr.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("→ cues_asr.json  (dlgcheck 용)")
