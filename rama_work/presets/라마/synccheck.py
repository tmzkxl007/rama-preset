# -*- coding: utf-8 -*-
"""★씽크를 **재서** 확인한다 (0순위 규칙). 추측 금지.

   사용: python presets/라마/synccheck.py <편폴더>

   완성본은 loudnorm·더킹·나레 믹스를 거쳐 파형이 달라진다. 그래서 원파형이 아니라
   **소리 크기 곡선(20ms RMS)** 을 맞춘다. 곡선은 필터를 거쳐도 모양이 남는다.

   1) build.py 와 같은 셈으로 대사 블록의 완성본 시각(off)을 다시 구한다
   2) 그 자리 ±3초 안에서 원본 구간과 곡선이 가장 잘 맞는 지점을 찾는다
   3) 어긋난 초(밀림)를 찍는다. 0.10초를 넘으면 씽크가 깨진 것이다
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
import spec
os.chdir(wd)

SR, HOP = 16000, 320          # 20ms
NARR_PAD = getattr(spec, "NARR_PAD", 0.10)
DLG_TAIL = getattr(spec, "DLG_TAIL", 0.34)
NEED = abs(getattr(spec, "MUTE_LEAD", -0.09)) + getattr(spec, "MUTE_RAMP", 0.07) + 0.14


def pcm(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", path]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def env(x):
    n = len(x) // HOP
    e = np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(axis=1) + 1e-9)
    return np.log(e)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True).stdout)


# ── build.py 와 **똑같은 셈**으로 완성본 시각을 다시 구한다 ──────
#   ★build 가 길이를 프레임 격자(qd)에 맞추므로 여기서도 맞춰야 한다.
#     안 맞추면 마디마다 최대 1/2프레임씩 어긋나 **재는 쪽이 밀린다.**
_fr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                      "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
                      episode.SRC], capture_output=True, text=True).stdout.strip()
_a, _b = (_fr.split("/") + ["1"])[:2]
FPS = float(_a) / float(_b or 1)


def qd(x):
    return max(1, int(round(float(x) * FPS))) / FPS


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

OUT = getattr(episode, "OUT")
big = env(pcm(OUT))
worst = 0.0
print(f"  완성본 {dur(OUT):.2f}초 · 소재 {episode.SRC}")
for kind, o, d, b in rows:
    if kind != "D":
        continue
    s0 = float(b[1])
    # ★블록 **가운데**를 잰다. 블록 첫머리는 앞 나레의 꼬리가 섞여 곡선이 흐려진다.
    w0 = float(b[3][0][1])
    mid = s0 + d * 0.35
    w0 = max(w0, mid)
    LEN = min(3.0, s0 + d - w0 - 0.15)
    if LEN < 1.0:
        w0 = float(b[3][0][1])
        LEN = min(3.0, d - (w0 - s0) - 0.1)
    if LEN < 0.8:
        continue
    ref = env(pcm(episode.SRC, w0 - 0.2, LEN))
    exp = o + (w0 - s0) - 0.2                   # 완성본에서 있어야 할 자리
    best, bl = -9, None
    for k in range(-150, 151):                  # ±3.0초 (20ms 칸)
        st = int(round(exp * SR / HOP)) + k
        if st < 0 or st + len(ref) > len(big):
            continue
        seg = big[st:st + len(ref)]
        r = ref - ref.mean(); s = seg - seg.mean()
        dn = np.sqrt((r * r).sum() * (s * s).sum())
        if dn < 1e-9:
            continue
        c = float((r * s).sum() / dn)
        if c > best:
            best, bl = c, k * HOP / SR
    # ★닮음이 낮으면 못 잰 것이다 — 짧은 블록은 잰 창이 다음 블록까지 넘어간다.
    #   그걸 "밀림"으로 찍으면 멀쩡한 편을 깨진 것으로 오해한다.
    if best < 0.85:
        print(f"  --  소재 {w0:7.2f} → 닮음 {best:.2f} 로 낮아 못 쟀다 (블록이 짧다)")
        continue
    tag = "OK " if abs(bl) <= 0.10 else "★밀림"
    worst = max(worst, abs(bl))
    print(f"  {tag} 소재 {w0:7.2f} → 있어야 할 자리 {exp+0.2:6.2f}초 · 실제로는 "
          f"{bl:+.2f}초 어긋남 (닮음 {best:.2f})")
# ── 나레도 잰다 ────────────────────────────────────────────
#   나레 음성은 완성본 r["off"] + NARR_PAD/2 자리에 얹힌다.
#   나레 자막도 같은 자리에서 나오므로, 소리가 맞으면 자막도 맞는다.
print("  -- 나레 --")
wn = 0.0
ni2 = 0
for kind, o, d, b in rows:
    if kind == "D":
        continue
    ni2 += 1
    wavp = os.path.join("narr", "n%d.wav" % ni2)
    if not os.path.exists(wavp):
        continue
    ref = env(pcm(wavp))
    if len(ref) < 25:
        continue
    exp = o + NARR_PAD / 2
    best, bl = -9, None
    for k in range(-150, 151):
        st = int(round(exp * SR / HOP)) + k
        if st < 0 or st + len(ref) > len(big):
            continue
        seg = big[st:st + len(ref)]
        r_ = ref - ref.mean()
        s_ = seg - seg.mean()
        dn = np.sqrt((r_ * r_).sum() * (s_ * s_).sum())
        if dn < 1e-9:
            continue
        c = float((r_ * s_).sum() / dn)
        if c > best:
            best, bl = c, k * HOP / SR
    if bl is None or best < 0.80:
        print("  --  n%d 닮음 %.2f 로 낮아 못 쟀다" % (ni2, best))
        continue
    tag = "OK " if abs(bl) <= 0.10 else "★밀림"
    wn = max(wn, abs(bl))
    print("  %s n%d → 있어야 할 자리 %6.2f초 · 실제로는 %+.2f초 어긋남 (닮음 %.2f)"
          % (tag, ni2, exp, bl, best))

print("")
_bad = max(worst, wn) > 0.10
print("  [씽크] 대사 %.2f초 · 나레 %.2f초  %s"
      % (worst, wn, "★★깨졌다 — 다시 구워라" if _bad else "— 맞음"))
sys.exit(1 if _bad else 0)

