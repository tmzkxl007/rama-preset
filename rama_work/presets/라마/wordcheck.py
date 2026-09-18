# -*- coding: utf-8 -*-
"""★자막 시각이 **실제 말**과 맞는지 잰다.

   지금까지는 "전사기가 준 낱말 시각"을 그대로 믿고 자막을 놓았다.
   그 시각 자체가 밀려 있으면 완성본 타임라인이 아무리 정확해도
   자막이 말보다 먼저(또는 늦게) 뜬다.

   소재 소리에서 **말이 실제로 시작하는 자리**를 찾아 자막 시작과 견준다.
   사용: python presets/라마/wordcheck.py <편폴더>
"""
import os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

wd = os.path.abspath(sys.argv[1])
sys.path.insert(0, wd)
import episode
os.chdir(wd)
SR, HOP = 16000, 160          # 10ms


def pcm(path, ss, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", path,
                          "-t", f"{t:.3f}", "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


print(f"  소재 {episode.SRC}")
bad = []
allg = []
for b in episode.BLOCKS:
    if b[0] != "D":
        continue
    for txt, t0, t1 in b[3]:
        PRE, POST = 0.60, 0.35
        x = pcm(episode.SRC, t0 - PRE, PRE + POST)
        n = len(x) // HOP
        if n < 10:
            continue
        e = np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(axis=1) + 1e-9)
        # 앞쪽 0.25초를 바닥으로 보고, 그보다 확 올라가는 첫 칸을 말 시작으로 본다
        floor = np.median(e[:max(3, int(0.25 * SR / HOP))])
        peak = e.max()
        if peak < floor * 2.2:                 # 또렷한 시작이 없다 (이어 말하는 중)
            continue
        thr = floor + (peak - floor) * 0.25
        idx = int(np.argmax(e >= thr))
        onset = (t0 - PRE) + idx * HOP / SR
        gap = t0 - onset                        # +면 자막이 말보다 늦다
        allg.append(gap)
        if abs(gap) > 0.20:
            bad.append((gap, txt, t0, onset))

if allg:
    a = np.array(allg)
    print(f"  잰 자막 {len(a)}개 · 치우침(중앙값) {np.median(a):+.2f}초 · "
          f"가장 큰 어긋남 {np.abs(a).max():.2f}초")
for gap, txt, t0, onset in sorted(bad, key=lambda x: -abs(x[0]))[:8]:
    how = "자막이 늦다" if gap > 0 else "자막이 이르다"
    print(f"  ★ {gap:+.2f}초 {how}  '{txt}'  (자막 {t0:.2f} · 말 시작 {onset:.2f})")
print(f"\n  [낱말] 0.20초 넘게 어긋난 자막: {len(bad)}개")
sys.exit(1 if bad else 0)
