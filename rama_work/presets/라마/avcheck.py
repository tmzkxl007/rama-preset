# -*- coding: utf-8 -*-
"""★그림과 소리가 서로 맞는지 잰다 (입모양 씽크).

   synccheck.py 는 **소리가 제자리에 있는지**만 쟀다.
   그림이 따로 밀리면 입은 움직이는데 소리가 어긋난다 — 그건 못 잡는다.
   여기서는 소재의 **장면전환 시각**이 완성본에서 어디로 갔는지 재서,
   소리 밀림과 견준다.

   사용: python presets/라마/avcheck.py <편폴더>
"""
import os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

wd = os.path.abspath(sys.argv[1])
sys.path.insert(0, wd)
import episode
import spec
os.chdir(wd)

SR, HOP = 16000, 320
NARR_PAD = getattr(spec, "NARR_PAD", 0.10)
DLG_TAIL = getattr(spec, "DLG_TAIL", 0.34)
NEED = abs(getattr(spec, "MUTE_LEAD", -0.09)) + getattr(spec, "MUTE_RAMP", 0.07) + 0.14


def sh(c):
    return subprocess.run(c, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def dur(p):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", p]).stdout.strip())


SRC, OUT = episode.SRC, episode.OUT
_fr = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
          "stream=r_frame_rate", "-of", "csv=p=0", SRC]).stdout.strip()
_a, _b = (_fr.split("/") + ["1"])[:2]
FPS = float(_a) / float(_b or 1)


def qd(x):
    return max(1, int(round(float(x) * FPS))) / FPS


# ── build.py 와 같은 셈 ────────────────────────────────────
rows, off, ni = [], 0.0, 0
for b in episode.BLOCKS:
    if b[0] == "N":
        ni += 1
        d = qd(dur(os.path.join("narr", f"n{ni}.wav")) + NARR_PAD)
        rows.append(("N", off, d, None))
    else:
        s1 = float(b[2])
        if isinstance(b[3], (list, tuple)) and b[3]:
            s1 = max(s1, max(x[2] for x in b[3]) + max(DLG_TAIL, NEED))
        d = qd(s1 - float(b[1]))
        rows.append(("D", off, d, b))
    off += d


def cuts(path, t0=None, t1=None, thr=0.30):
    cmd = ["ffmpeg", "-v", "error"]
    if t0 is not None:
        cmd += ["-ss", f"{t0:.3f}"]
    cmd += ["-i", path]
    if t1 is not None:
        cmd += ["-t", f"{t1 - t0:.3f}"]
    # ★완성본은 위아래가 검은 띠라 전체로 재면 점수가 묽어진다 — 그림 칸만 잘라서 잰다.
    pre = (f"crop={spec.PIC[0]}:{spec.PIC[1]}:0:{spec.VID_Y}," if path == OUT else "")
    cmd += ["-filter_complex",
            f"{pre}select='gt(scene,{thr})',metadata=print:file=-",
            "-f", "null", "-"]
    r = sh(cmd)
    base = t0 or 0.0
    return [base + float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stdout + r.stderr)]


out_cuts = cuts(OUT, thr=0.18)
print(f"  완성본 {dur(OUT):.2f}초 · 장면전환 {len(out_cuts)}곳")

worst, n = 0.0, 0
for kind, o, d, b in rows:
    if kind != "D":
        continue
    s0 = float(b[1])
    inner = [c for c in cuts(SRC, s0 + 0.25, s0 + d - 0.25, 0.18)]
    for c in inner:
        exp = o + (c - s0)                      # 완성본에서 그림이 바뀌어야 할 자리
        if not out_cuts:
            continue
        got = min(out_cuts, key=lambda x: abs(x - exp))
        if abs(got - exp) > 1.0:                # 못 찾은 것
            continue
        gap = got - exp
        worst = max(worst, abs(gap))
        n += 1
        tag = "OK " if abs(gap) <= 0.10 else "★밀림"
        print(f"  {tag} 소재 장면전환 {c:7.2f} → 있어야 할 자리 {exp:6.2f}초 · "
              f"실제 {got:6.2f}초 · {gap:+.2f}초")
if n == 0:
    print("  -- 대사 블록 안에 잴 만한 장면전환이 없다")
print(f"\n  [그림] 가장 크게 어긋난 값: {worst:.2f}초  "
      + ("— 맞음" if worst <= 0.10 else "★★그림이 소리와 어긋난다"))
sys.exit(1 if worst > 0.10 else 0)
