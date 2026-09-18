# -*- coding: utf-8 -*-
"""대사 구간 안에 **자막 없이 들리는 말**이 있는지 검사한다.
사용: python dlgcheck.py <편폴더> <소재구간전사.json> <소재시각보정>

왜 필요한가
  대사 시각을 묶음 단위로 대충 잡으면, 그 구간 앞뒤에 자막이 안 붙은 말이 남는다.
  (실제로 '10초에 병사가 말하는데 자막이 없다'는 지적을 받았다.)
  전사에서 받은 **단어 시각**과 episode.py 의 대사 자막 구간을 맞대어 빠진 말을 찾는다.
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

wd = os.path.abspath(sys.argv[1])
asr = sys.argv[2]
off = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0   # 전사 시각 - 소재 시각
sys.path.insert(0, wd)
import episode

d = json.load(io.open(asr, encoding="utf-8"))
words = d.get("words") or [w for s in d.get("segments", []) for w in s.get("words", [])]
words = [(w["start"] - off, w["end"] - off, w.get("word", w.get("text", ""))) for w in words]

bad = 0
for b in episode.BLOCKS:
    if b[0] != "D":
        continue
    s0, s1, cap = b[1], b[2], b[3]
    if not isinstance(cap, (list, tuple)):
        print(f"  [{s0:.2f}~{s1:.2f}] 자막에 단어 시각이 없다 — [(글,시작,끝)...] 로 적어라")
        bad += 1
        continue
    covered = [(c[1], c[2]) for c in cap]
    inside = [w for w in words if w[1] > s0 + 0.05 and w[0] < s1 - 0.05]
    miss = []
    for a, e, t in inside:
        mid = (a + e) / 2
        if not any(ca - 0.12 <= mid <= cb + 0.12 for ca, cb in covered):
            miss.append((a, e, t))
    head = f"[{s0:6.2f}~{s1:6.2f}] 말 {len(inside)}개"
    if miss:
        bad += 1
        print(f"  ★{head} — 자막 없는 말 {len(miss)}개: "
              + " ".join(f"{t}({a:.2f})" for a, e, t in miss))
    else:
        print(f"   {head} — 전부 자막 있음")
print(f"\n{'★' if bad else ''}자막 없는 말이 있는 대사 블록: {bad}개")
sys.exit(1 if bad else 0)
