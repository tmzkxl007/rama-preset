# -*- coding: utf-8 -*-
"""효과자막이 **영상 밖으로 나갔는지 · 두 줄로 접히는지**를 굽지 않고 본다 (§17-19).

   사용: python presets\라마\fxscan.py        (volcano_work 에서. 모든 편을 훑는다)

   완성본 길이를 build.py 와 같은 셈으로 다시 구한다 —
   나레는 narr/nK.wav 길이 + NARR_PAD, 대사는 마지막 말 뒤 DLG_TAIL 만큼,
   마지막 마디는 END_TAIL 만 남기고 자른다.
"""
import glob, importlib.util, os, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NARR_PAD, DLG_TAIL, END_TAIL = 0.10, 0.34, 0.45
NEED = abs(-0.09) + 0.07 + 0.14          # |MUTE_LEAD| + MUTE_RAMP + 여유
EFF_MAXCH = 10


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                 "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout or 0)


for f in sorted(glob.glob("*ep*/episode.py")):
    wd = os.path.dirname(f)
    sp = importlib.util.spec_from_file_location("fx_" + wd, f)
    m = importlib.util.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except Exception:
        continue
    if not (hasattr(m, "BLOCKS") and getattr(m, "EFFECTS", None)):
        continue
    if not all(isinstance(e[0], (int, float, list, tuple)) for e in m.EFFECTS):
        continue                      # 다른 프리셋의 EFFECTS 꼴이다

    rows, off, ni = [], 0.0, 0
    ok = True
    for b in m.BLOCKS:
        if b[0] == "N":
            ni += 1
            w = os.path.join(wd, "narr", f"n{ni}.wav")
            if not os.path.exists(w):
                ok = False
                break
            d = dur(w) + NARR_PAD
            rows.append(("N", off, d))
        else:
            s1 = float(b[2])
            if isinstance(b[3], (list, tuple)) and b[3]:
                s1 = max(s1, max(x[2] for x in b[3]) + max(DLG_TAIL, NEED))
            d = s1 - float(b[1])
            rows.append(("D", off, d))
        off += d
    if not ok or not rows:
        print(f"{wd}: 나레 wav 가 없어 건너뜀")
        continue
    TOTAL = rows[-1][1] + rows[-1][2]      # 끝 꼬리 자르기는 여기선 안 쓴다(넉넉하게 본다)

    dR = [r for r in rows if r[0] == "D"]
    nR = [r for r in rows if r[0] == "N"]
    bad, hand = [], []
    for e in m.EFFECTS:
        t = e[0]
        anchored = isinstance(t, (list, tuple))
        if anchored:
            k, i = str(t[0]).upper(), int(t[1])
            dt = float(t[2]) if len(t) > 2 else 0.15
            lst = dR if k == "D" else nR
            t = (lst[i - 1][1] + lst[i - 1][2] + dt) if k == "D" else (lst[i - 1][1] + dt)
        t = float(t)
        hold = e[3] if len(e) > 3 else 1.2
        if t + hold > TOTAL:
            bad.append(f"★'{e[1]}' {t:.1f}초 — 영상({TOTAL:.1f}초) **밖이다. 안 보인다**")
        if len(e[1]) > EFF_MAXCH:
            bad.append(f"★'{e[1]}' {len(e[1])}자 — **두 줄로 접힌다**")
        if not anchored:
            hand.append(f"'{e[1]}' {t:.1f}초")
    if bad:
        print(f"\n■ {wd}  (길이 약 {TOTAL:.1f}초)")
        for x in bad:
            print("   " + x)
