# -*- coding: utf-8 -*-
"""포레이로 프리셋으로 한 편을 굽는다.  사용: python build.py <편폴더>

편 폴더에 있어야 할 것: episode.py · src.mp4 · narr/ (tts.py 가 만든다) · fonts/

★딸기우유 엔진과 뼈대가 다르다. 거기선 블록 하나가 컷 하나였지만,
  여기서는 **나레 마디가 시간축을 정하고 그 위를 컷 여러 개가 지나간다**(PLAYBOOK §17).
"""
import io, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))   # base.py
sys.path.insert(0, HERE)                                             # spec.py
import spec

wd = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
sys.path.insert(0, wd)
import episode

# 윈도우 콘솔은 cp949 라 em-dash 하나에도 죽는다. 출력만 UTF-8 로 돌린다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.chdir(wd)

BS = chr(92)
NL = BS + "N"
WARN = []


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)


def tc(s):
    return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"


def speech_window(wav):
    """나레 wav 안에서 실제로 말이 나는 구간 (앞뒤 묵음을 뺀다)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    if len(x) < 400:
        return 0.0, len(x) / 16000.0
    w = 160                                  # 10ms
    n = len(x) // w
    e = np.array([np.sqrt((x[i*w:(i+1)*w] ** 2).mean() + 1e-12) for i in range(n)])
    db = 20 * np.log10(e + 1e-9)
    thr = max(db.max() - 32, np.percentile(db, 15) + 8)
    on = np.where(db > thr)[0]
    if len(on) < 2:
        return 0.0, n * 0.01
    return max(0.0, on[0] * 0.01 - 0.03), min(n * 0.01, on[-1] * 0.01 + 0.06)


def pause_edges(wav, ws, we, k):
    """말하는 창 안에서 '숨 쉬는 자리'(에너지가 푹 꺼지는 곳) k 개를 고른다.
    ★글자수로만 나누면 TTS 가 쉬는 자리와 어긋나 자막이 말보다 빠르거나 늦는다."""
    import numpy as np
    if k <= 0:
        return []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    w = 160
    n = len(x) // w
    e = np.array([np.sqrt((x[i*w:(i+1)*w] ** 2).mean() + 1e-12) for i in range(n)])
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    i0, i1 = int(ws / 0.01), min(n - 1, int(we / 0.01))
    if i1 - i0 < 20:
        return []
    seg = e[i0:i1]
    # 가장자리 12% 는 제외 (시작·끝은 경계가 될 수 없다)
    m = max(2, int(len(seg) * 0.12))
    cand = []
    for i in range(m, len(seg) - m):
        if seg[i] <= seg[i-1] and seg[i] <= seg[i+1]:
            cand.append((seg[i], i))
    if not cand:
        return []
    cand.sort()
    picked = []
    for _v, i in cand:
        if all(abs(i - j) > len(seg) * 0.12 for j in picked):
            picked.append(i)
        if len(picked) == k:
            break
    picked.sort()
    return [ws + i * 0.01 for i in picked]



SRC = getattr(episode, "SRC", "src.mp4")
if not os.path.exists(SRC):
    sys.exit(f"소재가 없다: {os.path.join(wd, SRC)}  (prep.py 를 먼저 돌려라)")
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height", "-of", "json", SRC],
                               capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
SW, SH = pr["streams"][0]["width"], pr["streams"][0]["height"]
# ★★씽크 0순위: 컷 길이를 **프레임 격자에 맞춘다.**
#   ffmpeg 의 trim 은 프레임 경계로 올림/내림되므로, 컷마다 최대 1프레임씩 어긋난다.
#   35컷이면 0.3초가 쌓여 자막·나레가 그만큼 밀린다(사용자: "씽크 안 맞아").
#   → 모든 마디·컷 길이를 1/FPS 의 배수로 잡고, 굽을 때도 프레임 수로 못 박는다.
_fr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=r_frame_rate", "-of", "json", SRC],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace").stdout)["streams"][0]["r_frame_rate"]
_a, _b = (_fr.split("/") + ["1"])[:2]
FPS = float(_a) / float(_b or 1)


def qd(x):
    """길이를 프레임 격자에 맞춘다 (최소 1프레임)."""
    return max(1, int(round(float(x) * FPS))) / FPS


print(f"  소재 {FPS:g}fps — 모든 길이를 1/{FPS:g}초 격자에 맞춘다(씽크 0순위)")
CROP, (cw, ch, cx, cy) = spec.crop_filter(SW, SH, getattr(episode, "HARDSUB_TOP", None))
print(f"  소재 {SW}x{SH} → 크롭 {cw}x{ch} @({cx},{cy}) → 그림 {spec.PIC[0]}x{spec.PIC[1]}")
# ★말하는 사람이 화면 밖으로 잘리거나 콩알만 하게 나오는 걸 막는다(§17-17).
#   16:9 원본에서 가운데만 잘라내니, 인물이 좌우로 치우친 shot 은 얼굴이 날아가고
#   넓은 shot 은 사람이 콩알만 해진다. reframe.py 가 얼굴을 찾아 reframe.json 에 적어 두고,
#   여기서 구간마다 다른 크롭을 쓴다.
#     episode.py 의 CROP_SHOT = [(소재시작, 소재끝, 중심x, 중심y, 폭배율), ...] 가 **더 세다.**
#     (중심x·중심y 는 원본 픽셀. 폭배율 1.0 = 기본 크롭폭)
_SHOTS = [tuple(s) for s in getattr(episode, "CROP_SHOT", [])]
for _a, _b, _dx in getattr(episode, "CROP_SHIFT", []):        # 옛 표기도 받아 준다
    _SHOTS.append((_a, _b, cx + cw / 2.0 + _dx, cy + ch / 2.0, 1.0))
if os.path.exists("reframe.json"):
    _auto = json.load(open("reframe.json", encoding="utf-8")).get("shots", [])
    _hand = [(a, b) for a, b, *_ in _SHOTS]
    for _s in _auto:                                          # 손으로 적은 구간은 건드리지 않는다
        if not any(h0 - 0.05 <= _s[0] < h1 for h0, h1 in _hand):
            _SHOTS.append(tuple(_s))
    print(f"  reframe.json 에서 {len(_auto)}곳을 읽었다 (episode.py 지정 {len(_hand)}곳 우선)")


def crop_at(t0, t1):
    mid = (t0 + t1) / 2.0
    for _a, _b, _px, _py, _z in _SHOTS:
        if _a <= mid < _b:
            w2 = int(min(SW, SH * cw / ch, max(cw * 0.30, cw * float(_z)))) // 2 * 2
            h2 = int(min(SH, round(w2 * ch / cw))) // 2 * 2
            x2 = int(round(min(max(_px - w2 / 2.0, 0), SW - w2)))
            y2 = int(round(min(max(_py - h2 / 2.0, 0), SH - h2)))
            return (f"crop={w2}:{h2}:{x2}:{y2},"
                    f"scale={spec.PIC[0]}:{spec.PIC[1]},setsar=1")
    return CROP


LIFT = spec.nightlift(getattr(episode, "LIFT", 0))
if LIFT:
    print(f"  야간 보정 LIFT={getattr(episode, 'LIFT')}  (어두운 쪽만 감마로 올린다)")
# ★어두운 shot 만 골라 걷어올린다 — LIFT_AT = [(소재시작, 소재끝, 세기), ...]
_LIFTS = [tuple(x) for x in getattr(episode, "LIFT_AT", [])]


def lift_at(t0, t1):
    mid = (t0 + t1) / 2.0
    for _a, _b, _v in _LIFTS:
        if _a <= mid < _b:
            return spec.nightlift(_v)
    return LIFT

# ── 1. 시간축: 나레 마디와 대사 블록이 정한다 ───────────
rows = []
off = 0.0
ni = 0
for i, b in enumerate(episode.BLOCKS):
    if b[0] == "N":
        ni += 1
        wav = os.path.join("narr", f"n{ni}.wav")
        if not os.path.exists(wav):
            sys.exit(f"나레가 없다: {wav}  (tts.py 를 먼저 돌려라)")
        d = qd(dur(wav) + spec.NARR_PAD)
        rows.append(dict(kind="N", off=off, d=d, wav=wav, text=b[1],
                         cuts=(list(b[2]) if len(b) > 2 else None)))
    elif b[0] == "D":
        # ★마지막 단어가 끝난 뒤 DLG_TAIL 만큼 더 둔다 — 램프가 말을 깎지 않게
        # ★★대사는 절대 잘리지 않는다. 뒤에서 원음을 내리는 램프가 말을 먹지 않도록
        #   |MUTE_LEAD| + MUTE_RAMP + 0.14 만큼은 무조건 확보한다.
        _need = abs(getattr(spec, "MUTE_LEAD", 0.0)) + getattr(spec, "MUTE_RAMP", 0.0) + 0.14
        _tail = max(getattr(spec, "DLG_TAIL", 0.34), _need)
        s1 = b[2]
        if isinstance(b[3], (list, tuple)) and b[3]:
            last_word_end = max(x[2] for x in b[3])
            s1 = max(s1, last_word_end + _tail)
        d = qd(s1 - b[1])
        s1 = b[1] + d
        rows.append(dict(kind="D", off=off, d=d, s0=b[1], s1=s1, text=b[3]))
    else:
        sys.exit(f"BLOCKS[{i}] 의 종류가 이상하다: {b[0]!r} (N 또는 D)")
    off += d
TOTAL = off
if not rows:
    sys.exit("BLOCKS 가 비었다.")
# ★마지막 블록의 남는 꼬리를 잘라낸다 — 말이 끝난 뒤 END_TAIL 만 남긴다
_last = rows[-1]
_et = getattr(spec, "END_TAIL", 0.45)
if _last["kind"] == "N":
    _ws, _we = speech_window(_last["wav"])
    _want = spec.NARR_PAD / 2 + _we + _et
    if _want < _last["d"]:
        print(f"  끝 꼬리 {_last['d'] - _want:.2f}초 잘라냄")
        _last["d"] = qd(_want)
else:
    _lw = max(x[2] for x in _last["text"]) if isinstance(_last["text"], (list, tuple)) else None
    if _lw:
        _want = (_lw - _last["s0"]) + _et
        if _want < _last["d"]:
            print(f"  끝 꼬리 {_last['d'] - _want:.2f}초 잘라냄")
            _last["d"] = qd(_want)
            _last["s1"] = _last["s0"] + _last["d"]
TOTAL = _last["off"] + _last["d"]

# ── 2. 그림 깔기: N 구간을 CUTS 로 채운다 ───────────────
CUTS = list(getattr(episode, "CUTS", []))
if not CUTS:
    sys.exit("CUTS 가 비었다. ★0번에 그 편에서 가장 센 그림을 넣어라(§17-9).")
segs = []          # (src_t0, src_t1, 완성본_off, 길이)
ci = 0
# ★잇닿은 나레 마디는 하나로 묶는다. 마디 경계에서 컷을 자르면 컷 수가 헛되이 늘어난다.
# ★마디마다 자기 그림을 들고 있으면 그것만 쓴다.
#   ("N", "문구", [(시작,끝), ...]) 로 적는다. 안 적으면 아래 CUTS 목록에서 순서대로 꺼내 쓴다.
#   ※말과 그림이 따로 노는 사고를 막으려면 마디마다 직접 적어라(사용자 지적).
spans = []
for r in rows:
    if r["kind"] == "D":
        spans.append(("D", r["off"], r["d"], r))
    elif r.get("cuts"):
        spans.append(("NC", r["off"], r["d"], r))
    elif spans and spans[-1][0] == "N":
        spans[-1] = ("N", spans[-1][1], spans[-1][2] + r["d"], None)
    else:
        spans.append(("N", r["off"], r["d"], None))
nself = sum(1 for k, _a, _b, _c in spans if k == "NC")
for kind, soff, sdur, r in spans:
    if kind == "D":
        segs.append((r["s0"], r["s1"], r["off"], r["d"], "D", r, 1.0))
        continue
    if kind == "NC":
        # 이 마디가 들고 있는 컷만 쓴다 — 말과 그림이 반드시 붙는다.
        # ★모자라면 되풀이하지 않고 **느리게 늘려** 채운다(같은 장면이 두 번 나오면 안 된다).
        own = list(r["cuts"])
        tot = sum(b - a for a, b in own)
        at = soff
        # ★적어 놓은 컷은 **하나도 버리지 않는다.** 마디 길이에 맞게 배속만 바꾼다.
        #   예전에는 합이 마디보다 길면 뒤쪽 컷을 그냥 잘라냈다 —
        #   컷을 더 넣어도 분당 컷수가 안 오르고, 붙이려던 그림이 소리 없이 사라졌다.
        f = sdur / tot
        if f > spec.MAX_STRETCH:
            WARN.append(f"'{r['text'][:12]}' 마디: 컷 {tot:.1f}초로 {sdur:.1f}초를 채우려면 "
                        f"{f:.2f}배 늘려야 한다 — 컷을 더 넣어라")
            f = spec.MAX_STRETCH
        _rest = sdur
        for _k, (a, b) in enumerate(own):
            d2 = qd((b - a) * f)
            if _k == len(own) - 1:          # ★마지막 컷이 남는 만큼을 정확히 채운다
                d2 = qd(_rest)
            d2 = min(d2, _rest) if _k == len(own) - 1 else d2
            if d2 < 0.28:
                WARN.append(f"'{r['text'][:12]}' 마디: 컷 하나가 {d2:.2f}초밖에 안 된다 "
                            "— 깜빡이는 것처럼 보인다. 컷 개수를 줄여라")
            segs.append((a, b, at, d2, "C", None, f))
            at += d2
            _rest -= d2
        continue
    need = sdur
    at = soff
    while need > 0.04:
        if ci >= len(CUTS):
            WARN.append(f"컷이 모자라 마지막 컷을 {need:.2f}초 늘렸다 — CUTS 를 더 넣어라")
            s0, s1 = CUTS[-1]
            take = need
            segs.append((s0, min(s1 + need, s0 + (s1 - s0) + need), at, take, "C", None, 1.0))
            break
        s0, s1 = CUTS[ci]
        have = s1 - s0
        take = qd(min(have, need))
        if take > need:
            take = qd(need)
        segs.append((s0, s0 + take, at, take, "C", None, 1.0))
        at += take
        need -= take
        if take >= have - 1e-3:
            ci += 1
        else:
            CUTS[ci] = (s0 + take, s1)
# ★마디마다 그림을 직접 적었으면 CUTS 는 예비 목록일 뿐이라 안 쓰이는 게 정상이다.
#   그 경우까지 경고하면 고칠 수 없는 경고가 매 편 뜬다.
if ci and ci < len(CUTS) - 1:
    WARN.append(f"컷 {len(CUTS)-ci-1}개가 남아 안 쓰였다 — 나레가 짧거나 컷이 많다")

cutlens = [s[3] for s in segs]
ncut = len(segs)
# ★대사 블록 한 덩이 안에서도 shot 마다 다르게 잡을 수 있게 그림을 쪼갠다.
#   소리는 잇달아 이어 붙이므로 바뀌지 않는다. 분당컷수·효과음 자리는 아래 segs 로 센다.
_edges = sorted({e for sh in _SHOTS for e in (sh[0], sh[1])}
                | {e for lf in _LIFTS for e in (lf[0], lf[1])})
rsegs = []
for _sg in segs:
    _s0, _s1, _at, _d, _kind, _rr, _st = _sg
    if _kind != "D" or _st != 1.0:
        rsegs.append(_sg)
        continue
    _cut = [e for e in _edges if _s0 + 0.12 < e < _s1 - 0.12]
    _prev, _pat, _left = _s0, _at, _d
    for _i2, _e in enumerate(_cut + [_s1]):
        _dd = qd(_e - _prev)
        if _i2 == len(_cut):                # ★마지막 조각이 남는 만큼을 정확히 채운다
            _dd = _left
        rsegs.append((_prev, _prev + _dd, _pat, _dd, _kind, _rr, 1.0))
        _pat += _dd
        _left -= _dd
        _prev = _prev + _dd
if len(rsegs) != len(segs):
    print(f"  대사 블록을 shot 경계에서 {len(rsegs)-len(segs)}조각 더 쪼갬 (그림만)")
open3 = sum(1 for s in segs if s[2] < 5.0)

# ── 3. 규격 검사 (README 9장) ───────────────────────────
def chk(ok, msg):
    if not ok:
        WARN.append(msg)


pass  # 길이 검사는 문체 갈래를 정한 뒤에 한다
nchars = sum(len(r["text"].replace("|", "").replace(" ", "")) for r in rows if r["kind"] == "N")
def dtext(t):
    return "".join(x[0] for x in t) if isinstance(t, (list, tuple)) else t
dchars = sum(len(dtext(r["text"]).replace("|", "").replace(" ", "")) for r in rows if r["kind"] == "D")
share = nchars / max(1, nchars + dchars)
STYLE = getattr(episode, "STYLE", getattr(spec, "STYLE", "forey"))
CFG = dict(NARR_SHARE=spec.NARR_SHARE, NARR_CHARS=spec.NARR_CHARS,
           NARR_BEATS=spec.NARR_BEATS, LEN_RANGE=spec.LEN_RANGE,
           DLG_MARKS=spec.DLG_MARKS, CUTS_PER_MIN=spec.CUTS_PER_MIN, END_OPEN=True)
if STYLE == "tome":
    CFG.update(spec.TOME)
print(f"  문체: {STYLE}"
      + ("  (대사가 본문 · 나레는 짧은 이음새 · 끝을 맺는다)" if STYLE == "tome"
         else "  (나레가 주인 · 끝을 연결어미로 끊는다)"))
chk(share >= CFG["NARR_SHARE"],
    f"나레 비중 {share*100:.0f}% — {STYLE} 규격 {CFG[chr(78)+chr(65)+chr(82)+chr(82)+chr(95)+chr(83)+chr(72)+chr(65)+chr(82)+chr(69)]*100:.0f}% 이상. "
    "대사를 줄이고 나레로 이야기해라(§17-6)")
chk(CFG["NARR_CHARS"][0] <= nchars <= CFG["NARR_CHARS"][1],
    f"나레 {nchars}자 — {STYLE} 규격 {CFG['NARR_CHARS'][0]}~{CFG['NARR_CHARS'][1]}자 밖")
nN = sum(1 for r in rows if r["kind"] == "N")
nD = sum(1 for r in rows if r["kind"] == "D")
chk(CFG["NARR_BEATS"][0] <= nN <= CFG["NARR_BEATS"][1],
    f"나레 마디 {nN}개 — {STYLE} 규격 {CFG['NARR_BEATS'][0]}~{CFG['NARR_BEATS'][1]}개 밖")
chk(CFG["DLG_MARKS"][0] <= nD <= CFG["DLG_MARKS"][1],
    f"원본 대사 {nD}개 — {STYLE} 규격 {CFG['DLG_MARKS'][0]}~{CFG['DLG_MARKS'][1]}개 밖")
chk(CFG["LEN_RANGE"][0] <= TOTAL <= CFG["LEN_RANGE"][1],
    f"길이 {TOTAL:.1f}초 — {STYLE} 규격 {CFG['LEN_RANGE'][0]}~{CFG['LEN_RANGE'][1]}초 밖")
lastN = [r for r in rows if r["kind"] == "N"]
if lastN:
    tail = lastN[-1]["text"].rstrip("… .!?")
    ENDS = ("고", "는데", "이었고", "지만", "하며", "자", "죠", "인데", "더니", "면서")
    if CFG["END_OPEN"]:
        chk(tail.endswith(ENDS),
            f"마지막 나레가 '{tail[-6:]}' 로 끝난다 — ★연결어미로 끊어라. 결말을 주지 마라(§17-6)")
chk(open3 >= spec.CUT_OPEN - 1, f"첫 5초 컷이 {open3}개 — 규격 4~6개. 앞을 몰아쳐라(§17-5)")
cpm = ncut / TOTAL * 60
chk(CFG["CUTS_PER_MIN"][0] <= cpm <= CFG["CUTS_PER_MIN"][1],
    f"분당 {cpm:.1f}컷 — {STYLE} 규격 {CFG['CUTS_PER_MIN'][0]}~{CFG['CUTS_PER_MIN'][1]} 밖")
# ★★질문하는 말에는 물음표를 넣는다 (지침서 §9 · 사용자가 두 번 지적).
#   글자를 몰래 고치지는 않는다 — 어디를 고쳐야 하는지 짚어 주고 사람이 고친다.
# ★`까요` 는 의문(갈까요?)이기도 하지만 `~니까요`(까닭)이기도 하다.
#   "저도 그들과 같은 처지니까요" 를 질문으로 잡아 규격 위반을 냈다(2026-09-13).
#   앞 글자가 `니` 면 까닭이다 — 뺀다.
_Q_HARD = re.compile(r"(습니까|ㅂ니까|십니까|겁니까|나요|가요|(?<!니)까요|을까|ㄹ까|냐)$")
_Q_WORD = re.compile(r"(뭐|뭔|무슨|왜|어디|언제|누구|누가|어떻게|어떤|어때|몇)")
_Q_SOFT = re.compile(r"(나|니|래|데|지)$")


def _qcheck(t):
    if not isinstance(t, str):
        return None
    t = t.strip()
    if not t or t[-1] in "?!.…~":
        return None
    if _Q_HARD.search(t):
        return "hard"
    if _Q_WORD.search(t) or _Q_SOFT.search(t):
        return "soft"
    return None


# ★`가요` 는 질문(어디 가요?)이기도 하지만 명령(그만 내려가요)이기도 하다.
#   글자만으로는 못 가른다 — 사람이 화면을 보고 질문이 아니라고 판정한 대사만
#   episode.py 의 NOT_QUESTION 에 적는다(2026-09-15 · n02 "그쪽도 그만 내려가요").
_NOT_Q = set(getattr(episode, "NOT_QUESTION", []))
_qh, _qs = [], []
for _r in rows:
    if _r["kind"] != "D" or not isinstance(_r["text"], (list, tuple)):
        continue
    for _c in _r["text"]:
        if _c[0] in _NOT_Q:
            continue
        _k = _qcheck(_c[0])
        (_qh if _k == "hard" else _qs if _k == "soft" else []).append(_c[0])
for _e in getattr(episode, "EFFECTS", []):
    _k = _qcheck(_e[1])
    (_qh if _k == "hard" else _qs if _k == "soft" else []).append(_e[1])
if _qh:
    WARN.append("물음표가 빠졌다(지침서 §9): "
                + " / ".join(f"'{t}'" for t in _qh[:6])
                + "  — 질문하는 대사에는 반드시 ? 를 붙여라")
if _qs:
    print("  물음표를 봐야 할 곳(질문이면 ? 를 붙여라): "
          + " / ".join(f"'{t}'" for t in _qs[:8]))

# ★★나레 컷은 그 마디의 **앞뒤 대사 사이**에서만 고른다 (지침서 §12-3).
#   사용자 지적: "왜 자꾸 장면 중에 다른 장면이 들어가니"
#   0초 프레임만 예외다(§17-9 — 가장 센 그림을 시간 무시하고 놓는다).
_bl = list(episode.BLOCKS)
_dspan = []
for _i, _b in enumerate(_bl):
    if _b[0] == "D":
        _e1 = float(_b[2])
        if isinstance(_b[3], (list, tuple)) and _b[3]:
            _e1 = max(_e1, max(x[2] for x in _b[3]) + getattr(spec, "DLG_TAIL", 0.34))
        _dspan.append((_i, float(_b[1]), _e1))
#   창은 **앞 대사가 시작한 곳 ~ 뒤 대사가 끝나는 곳**으로 넉넉히 잡는다.
#   좁게 잡으면 "나레로 먼저 알리고 대사로 터뜨리는" 멀쩡한 배치까지 걸린다.
_ORD_SLACK = 3.0
for _i, _b in enumerate(_bl):
    if _b[0] != "N" or len(_b) < 3 or not _b[2]:
        continue
    _pv = [s0 for j, s0, _e in _dspan if j < _i]
    _lo = max(_pv) if _pv else 0.0
    _nx = [e for j, _s0, e in _dspan if j > _i]
    _hi = max(_nx) if _nx else 1e9
    for _k, (_a, _z) in enumerate(_b[2]):
        if _i == 0 and _k == 0:
            continue
        if _a < _lo - _ORD_SLACK or _z > _hi + _ORD_SLACK:
            WARN.append(f"'{_b[1][:14]}' 마디의 컷 {_a:g}~{_z:g}초는 이 마디 자리"
                        f"({_lo:.1f}~{_hi if _hi < 1e8 else 0:.1f}초) 밖이다 — "
                        "다른 장면이 끼어든다(지침서 §12-3). 앞뒤 대사 사이에서 골라라")

EFFECTS = list(getattr(episode, "EFFECTS", []))
# ★★효과자막 자리는 **손으로 세지 마라.** 완성본 초를 눈대중으로 적었다가
#   두 편에서 영상 밖으로 나가 아예 안 보였고, 나머지도 몇 초씩 밀려
#   엉뚱한 인물 얼굴 위에 붙었다(사용자: "효과자막이 영상이랑 안 맞아").
#   → 마디에 걸어라.  ("D", n, dt) = n번째 대사 블록이 **끝나고** dt초 뒤
#                     ("N", n, dt) = n번째 나레 마디가 **시작하고** dt초 뒤
_dRows = [r for r in rows if r["kind"] == "D"]
_nRows = [r for r in rows if r["kind"] == "N"]
_anch = []
for _e in EFFECTS:
    _t = _e[0]
    if isinstance(_t, (list, tuple)):
        _k = str(_t[0]).upper()
        _i = int(_t[1])
        _dt = float(_t[2]) if len(_t) > 2 else 0.15
        if _k == "C":
            # ★★("C", n, k, dt) = n번째 **대사 블록의 k번째 자막이 끝나고** dt초 뒤.
            #   블록 **안쪽**이라 말한 사람이 아직 화면에 있고 나레 구간이 아니다.
            #   ("D", n, dt)(블록이 끝난 뒤)는 거의 항상 다음 나레 자리라
            #   말한 사람이 화면에서 사라진 뒤에 떴다(사용자 지적).
            _kk = int(_t[2])
            _dt = float(_t[3]) if len(_t) > 3 else 0.05
            if not (1 <= _i <= len(_dRows)):
                sys.exit(f"EFFECTS: C{_i} 은 없다 — 이 편의 대사 블록은 {len(_dRows)}개다")
            _r = _dRows[_i - 1]
            _cs = _r["text"]
            if not (1 <= _kk <= len(_cs)):
                sys.exit(f"EFFECTS: C{_i} 의 {_kk}번째 자막은 없다 — 그 블록 자막은 {len(_cs)}개다")
            _t = _r["off"] + (float(_cs[_kk - 1][2]) - _r["s0"]) + _dt
        else:
            _lst = _dRows if _k == "D" else _nRows
            if not (1 <= _i <= len(_lst)):
                sys.exit(f"EFFECTS: {_k}{_i} 은 없다 — 이 편의 {_k} 마디는 {len(_lst)}개다")
            _r = _lst[_i - 1]
            _t = (_r["off"] + _r["d"] + _dt) if _k == "D" else (_r["off"] + _dt)
    _anch.append((round(float(_t), 2),) + tuple(_e[1:]))
EFFECTS = _anch

# ★0장은 봐준다 — "제대로 못 붙일 바엔 아예 빼라"가 사용자 지시다(2026-09-09).
#   다만 1장만 붙이는 건 어중간하니 막는다.
chk(len(EFFECTS) == 0 or len(EFFECTS) >= spec.EFF_COUNT[0],
    f"효과자막 {len(EFFECTS)}장 — 0장이거나 {spec.EFF_COUNT[0]}~{spec.EFF_COUNT[1]}장이어야 한다(§17-4)")
chk(len(EFFECTS) <= spec.EFF_COUNT[1],
    f"효과자막 {len(EFFECTS)}장 — 편당 최대 {spec.EFF_COUNT[1]}장(§17-4)")
chk(bool(getattr(episode, "HEAD1", "") and getattr(episode, "HEAD2", "")), "제목 두 행이 비었다")

# ★효과자막이 그 말보다 먼저 나오면 안 된다.
#   "부대 카페요?" 를 아직 아무도 부대 카페 얘기를 안 한 1초에 띄웠다가 지적받았다.
#   0초 효과자막 자체는 규격이다(§17-4) — 다만 그건 '아직 안 나온 낱말'을 앞질러 말하면 안 된다.
def _grams(t):
    t = re.sub(r"[^가-힣0-9A-Za-z]", "", t or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _said(rs):
    out = []
    for r in rs:
        if r["kind"] == "N":
            out.append(r["text"])
        elif isinstance(r["text"], (list, tuple)):
            out.extend(x[0] for x in r["text"])
    return " ".join(out)


# ★★나레가 앞뒤 대사를 그대로 따라 하면 안 된다 (지침서 §19·§22).
#   사용자: "나레이션이 대사를 따라하냐 나레이션이 이야기를 몰아가야지"
#   경성크리처 9편에서 "건물을 무너뜨리지는 못한다고 했습니다"처럼
#   바로 앞 대사를 그대로 되풀이한 마디가 여러 개 있었다.
_NEAR = 0.34
for _i, _b in enumerate(_bl):
    if _b[0] != "N":
        continue
    _ng = _grams(_b[1])
    if not _ng:
        continue
    _near = set()
    for _j in (_i - 1, _i + 1, _i + 2):
        if 0 <= _j < len(_bl) and _bl[_j][0] == "D":
            _near |= _grams(" ".join(c[0] for c in _bl[_j][3]))
    _ov = len(_ng & _near) / len(_ng)
    if _ov >= _NEAR:
        WARN.append(f"나레 '{_b[1][:16]}' 가 앞뒤 대사와 {_ov*100:.0f}% 겹친다 — "
                    "나레는 대사를 따라 하는 게 아니라 **이야기를 몰아가는 것**이다(§19). "
                    "대사가 말하지 않는 것(때·곳·관계·결과)을 말해라")

# ★흐린 말을 앞 자막으로 오래 덮으면 **지나간 자막이 화면에 남아 밀린 것처럼 보인다**(§8).
#   사용자 지적("씽크 안 맞아"). 3.2초 넘게 떠 있는 대사 자막은 대개 그 경우다.
for _r in rows:
    if _r["kind"] != "D" or not isinstance(_r["text"], (list, tuple)):
        continue
    for _c in _r["text"]:
        if _c[2] - _c[1] > 3.2:
            WARN.append(f"대사 자막 '{_c[0]}' 이 {_c[2]-_c[1]:.1f}초 동안 떠 있다 — "
                        "흐린 말을 1초 넘게 덮으면 지나간 자막이 남아 밀린 것처럼 보인다. "
                        "그 자리는 블록에서 빼라(§8)")

# ★효과자막 두 장이 한 화면에 같이 뜨면 안 된다 (g25 에서 두 장이 같은 순간에 떴다)
for _i in range(len(EFFECTS)):
    for _j in range(_i + 1, len(EFFECTS)):
        _ta, _tb = float(EFFECTS[_i][0]), float(EFFECTS[_j][0])
        _ha = EFFECTS[_i][3] if len(EFFECTS[_i]) > 3 else 1.2
        _hb = EFFECTS[_j][3] if len(EFFECTS[_j]) > 3 else 1.2
        if _ta < _tb + _hb and _tb < _ta + _ha:
            WARN.append(f"효과자막 '{EFFECTS[_i][1]}' 와 '{EFFECTS[_j][1]}' 가 "
                        f"{max(_ta,_tb):.1f}초에 함께 뜬다 — 한 번에 한 장만 띄워라")

EFF_MAXCH = 10          # ★wrap(txt, 10) 이라 이보다 길면 두 줄로 접혀 지저분해진다
for _e in EFFECTS:
    _t = float(_e[0])
    _hold = _e[3] if len(_e) > 3 else 1.2
    if _t < 0 or _t + _hold > TOTAL:
        WARN.append(f"효과자막 '{_e[1]}'({_t:.1f}초)이 영상(0~{TOTAL:.1f}초) 밖이다 — "
                    ' 아예 안 보인다. 마디에 걸어라: ("D", n, 0.15)')
    if len(_e[1]) > EFF_MAXCH:
        WARN.append(f"효과자막 '{_e[1]}' 이 {len(_e[1])}자 — {EFF_MAXCH}자를 넘으면 "
                    "두 줄로 접힌다. 줄여라")
for _e in EFFECTS:
    _t = float(_e[0])
    _g = _grams(_e[1])
    if not _g:
        continue
    _before = _grams(_said([r for r in rows if r["off"] + r["d"] <= _t + 0.05]))
    _after = _grams(_said([r for r in rows if r["off"] + r["d"] > _t + 0.05]))
    if not (_g & _before) and (_g & _after):
        WARN.append(f"효과자막 '{_e[1]}'({_t:.1f}초)이 그 말보다 먼저 나온다 — "
                    "효과자막은 이미 나온 말에 반응하는 것이다. 뒤로 미뤄라(§17-4)")

chk(bool(getattr(episode, "WORK", "")), "WORK(작품명)가 비었다 — 설명문 출처 표기에 쓴다")

# ── ★라마 나레 말투 검사 (docs/라마-지침서.md §2 · 사용자 2026-09-18) ──
#   ① 물음표로 던지는 나레 금지 — 「~은?/~는?」「~데?」「~지만?」 (사용자: "그냥 상황 설명을 해주는 게 좋을 거 같아")
#   ② 마지막 마디(촌평)만 반말. 본문 마디가 「~다/~습니다」로 끝나면 경고.
_nrows = [r for r in rows if r["kind"] == "N"]
for _i, _r in enumerate(_nrows):
    _nt = _r["text"].replace("|", " ").strip()
    _last = _i == len(_nrows) - 1
    if "?" in _nt:
        WARN.append(f"나레 '{_nt}' 에 물음표 — 라마 지침서 §2, 상황 설명 문장(~죠/~는데/~은)으로 바꿔라")
    if not _last and re.search(r"(습니다|입니다|[가-힣]다)\s*$", _nt) and not _nt.endswith(("는데", "인데", "은데")):
        WARN.append(f"나레 '{_nt}' 가 문어체(~다)로 끝난다 — 라마 지침서 §2, ~죠/~는데 로")

# ── 부록 M 나레 낱말 검사 (2026-09-18 사용자 지적 세 가지) ──
#   ① `~기에` 어미  ② 직함·신분(부장·중령·검사·고문·생도…)   ※장소 검사는 사용자가 취소(09-18 "별로다")
#   나레에서만 본다 — 대사 자막은 들리는 대로 둔다. 걸리면 이름·관계어·상황으로 바꿔 쓴다.
_M_TITLE = ["부장", "차장", "중령", "대령", "대위", "소령", "장군", "검사", "고문", "생도", "비서",
            "실장", "국장", "사장", "회장", "의원", "장관", "형사", "경감", "교수"]
for _r in rows:
    if _r["kind"] != "N":
        continue
    _nt = _r["text"].replace("|", "")
    if re.search(r"(?<![여거저])기에(\s|$)", _nt):   # "여기에·거기에" 는 어미가 아니다(2026-09-19 sb05 오탐)
        WARN.append(f"나레 '{_nt}' 에 `~기에` 어미 — 부록 M-2, ~죠/~는데 로 바꿔라")
    for _w in _M_TITLE:
        if re.search(r"(^|\s)\S*" + _w + r"(\s|$|이|은|는|의|에게|을|를|과|와|도|님)", _nt):
            WARN.append(f"나레 '{_nt}' 에 직함 '{_w}' — 부록 M-3, 이름·관계어로 불러라")
            break

print(f"  길이 {TOTAL:.1f}초 · 컷 {ncut}개(분당 {cpm:.1f}) · 첫5초 {open3}컷"
      f" · 그림 직접지정 {nself}/{nN}마디")
_need = abs(getattr(spec, "MUTE_LEAD", 0.0)) + getattr(spec, "MUTE_RAMP", 0.0)
for _r in rows:
    if _r["kind"] == "D" and isinstance(_r["text"], (list, tuple)) and _r["text"]:
        _lw = max(x[2] for x in _r["text"])
        _margin = _r["s1"] - _lw
        if _margin < _need + 0.06:
            WARN.append(f"대사 '{_r['text'][-1][0]}' 뒤 여유 {_margin:.2f}초 — "
                        f"원음 내리는 램프({_need:.2f}초)에 말이 먹힌다. 절대 안 된다")
print(f"  나레 {nN}마디 {nchars}자 (비중 {share*100:.0f}%) · 원본 대사 {nD}개 {dchars}자")
if nself < nN:
    WARN.append(f"그림을 직접 지정하지 않은 나레 마디가 {nN-nself}개 — 말과 그림이 따로 논다. "
                'BLOCKS 에 ("N", "문구", [(시작,끝), ...]) 로 적어라')
if WARN:
    print("\n  ┌ [라마 규격 위반]")
    for w in WARN:
        print("  │ ★ " + w)
    print("  └ 고치고 다시 돌려라. 그래도 굽는다.\n")

# ── 4. 1차: 그림 + 원음 ─────────────────────────────────
fc = []
fc.append(f"[0:v]split={len(rsegs)}" + "".join(f"[v{i}s]" for i in range(len(rsegs))))
fc.append(f"[0:a]asplit={len(rsegs)}" + "".join(f"[a{i}s]" for i in range(len(rsegs))))
vs, as_ = [], []
NSEC = len(spec.SECTIONS)
for i, (s0, s1, at, d, kind, _r, st) in enumerate(rsegs):
    k = min(NSEC - 1, int((at + d / 2) / (TOTAL / NSEC)))
    a_, sh_ = spec.SECTIONS[k]
    _src_len = d if st == 1.0 else (s1 - s0)
    _pts = "setpts=PTS-STARTPTS" if st == 1.0 else f"setpts={st:.4f}*(PTS-STARTPTS)"
    # ★★씽크 0순위: 이 컷을 **정확히 nfr 프레임**으로 못 박는다.
    #   trim 만 쓰면 프레임 경계로 올림돼 컷마다 최대 1프레임씩 길어지고,
    #   그게 쌓여 뒤로 갈수록 자막·나레가 밀린다(측정값 35컷에 0.3초).
    nfr = max(1, int(round(d * FPS)))
    fc.append(f"[v{i}s]trim=start={s0:.3f}:end={s0+_src_len+0.5:.3f},{_pts},"
              f"{crop_at(s0, s0 + _src_len)},{spec.grade(a_, sh_)}"
              f"{lift_at(s0, s0 + _src_len)},fps={FPS:.6f},"
              f"tpad=stop_mode=clone:stop_duration=1,"
              f"trim=end_frame={nfr},setpts=PTS-STARTPTS[v{i}]")
    # 대사 블록은 원음 그대로. 나레 구간은 살짝 낮춰 두고, 실제로 말하는 동안만 2차에서 끈다.
    duck = "" if kind == "D" else f",volume={spec.NARR_BED_DB}dB"
    _atempo = "" if st == 1.0 else f",atempo={max(0.5, min(2.0, 1.0/st)):.4f}"
    fc.append(f"[a{i}s]atrim=start={s0:.3f}:end={s0+_src_len:.3f},asetpts=PTS-STARTPTS{_atempo},"
              f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
              f"{spec.voicefx(spec.VOICE[1])}{duck},"
              f"apad=pad_dur=1,atrim=end={nfr/FPS:.6f},asetpts=PTS-STARTPTS[a{i}]")
    vs.append(f"[v{i}]")
    as_.append(f"[a{i}]")
fc.append("".join(a + b for a, b in zip(vs, as_)) + f"concat=n={len(rsegs)}:v=1:a=1[vo][ao]")
print("1차 굽기…")
# ★필터가 길어 윈도 명령줄 한도(32KB)를 넘는다 → 파일로 넘긴다.
#   ffmpeg 9 에는 -filter_complex_script 가 없다. **-/filter_complex <파일>** 꼴을 쓴다.
open("_fc1.txt", "w", encoding="utf-8").write(";".join(fc))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-/filter_complex", "_fc1.txt",
                "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-crf", "15",
                "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
                "-f", "matroska", "body.mkv"], check=True)

# ── 5. 자막 (ASS) ───────────────────────────────────────
PROBE_Y = 600


def probe(name, size, text, align, w=None):
    """libass 로 실제 그려 잉크 상자를 잰다 -> (위, 아래, 높이, 폭).
    ★PIL 로 재면 20% 넘게 틀린다(§12-12). 크기도 자리도 여기서 나온 값으로 정한다.
    y 는 PROBE_Y 에 \\pos 로 찍었을 때의 실제 잉크 위치다 — 그 차이만큼 자리를 보정한다."""
    import cv2
    # ★w 를 주면 그 폭의 판에 그린다. 1080 판에 재면 넘치는 글이 잘려서
    #   "폭이 넘친다"는 걸 영영 못 잡는다(ep14 에서 실제로 놓쳤다).
    W, H = (w or spec.CANVAS[0]), 1200
    L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
         "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour,"
         " BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle,"
         " BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
         f"Style: T,{name},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
         f"0,0,0,0,{spec.FONT_SCALEX},100,0,0,1,0,0,{align},35,35,0", "", "[Events]",
         "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
         f"Dialogue: 0,0:00:00.00,0:00:10.00,T,,0,0,0,,"
         f"{chr(123)}{BS}pos({W // 2},{PROBE_Y}){chr(125)}{text}"]
    open("_hw.ass", "w", encoding="utf-8").write(chr(10).join(L) + chr(10))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"color=black:s={W}x{H}:d=1",
                    "-vf", "ass=_hw.ass:fontsdir=fonts", "-frames:v", "1", "_hw.png"], check=True)
    m = (cv2.cvtColor(cv2.imread("_hw.png"), cv2.COLOR_BGR2GRAY) > 110)
    ys = [y for y, v in enumerate(m.sum(axis=1)) if v > 0]
    xs = [x for x, v in enumerate(m.sum(axis=0)) if v > 0]
    if not ys:
        return (0, 0, 0, 0)
    return (ys[0], ys[-1], ys[-1] - ys[0] + 1, xs[-1] - xs[0] + 1)


_FIX = getattr(spec, "FIXED_SIZES", None) or {}
_FIXKEY = {"제목 1행": "H1", "제목 2행": "H2", "나레 자막": "NARR", "대사 자막": "DLG", "대사 1행": "DLG",
           "대사 2행": "DLG", "효과자막": "EFF", "작품명": "CREDIT", "풀영상 안내": "CREDIT2"}


def fit(name, text, target_h, maxw, align, what):
    """잉크 높이를 target_h 에 맞추고, 그래도 폭이 넘치면 줄인다.
    -> (글자크기, \\pos 에 넣을 y 보정값)"""
    probe_txt = text.replace(NL, " ")
    # ★spec.FIXED_SIZES 가 있으면 크기를 거기 값으로 못 박고, 폭이 넘치면 [규격 위반] 만 찍는다(줄이지 않는다).
    #   (2026-09-19 사용자 "템플릿 크기 좀 고정해봐, 유튜브에 올리면 다 제각각이야")
    if _FIXKEY.get(what) in _FIX:
        size = int(_FIX[_FIXKEY[what]])
        t, b, ih, iw = probe(name, size, probe_txt, align, w=4000)
        if iw > maxw:
            print(f"  ★[규격 위반] {what} '{probe_txt}' 이 {iw}px 라 {maxw}px 을 넘는다 — 크기는 고정이니 문구를 줄여라")
        t2, b2, ih2, _w2 = probe(name, size, text, align)
        off = (t2 - PROBE_Y) if align == 8 else ((t2 + b2) / 2.0 - PROBE_Y)
        print(f"  {what} 크기 {size}(고정) · 잉크높이 {ih} · 자리보정 {-off:+.0f}px")
        return size, -off
    lo, hi = 30, 400
    for _ in range(12):
        mid = (lo + hi) // 2
        if probe(name, mid, probe_txt, align)[2] < target_h:
            lo = mid + 1
        else:
            hi = mid
    size = max(30, hi)
    # ★폭은 넓은 판(w=4000)에 재야 한다 — 1080 판에서는 넘치는 글이 잘려 1080 으로 보이고,
    #   줄인 크기가 모자라 제목이 화면 밖으로 나갔다(2026-09-19 라마 sb03·sb05, 사용자 "제목이 다 넘어오잖아").
    t, b, ih, iw = probe(name, size, probe_txt, align, w=4000)
    if iw > maxw and iw > 0:
        for _ in range(4):
            size = max(30, int(size * maxw / iw) - 1)
            t, b, ih, iw = probe(name, size, probe_txt, align, w=4000)
            if iw <= maxw:
                break
        print(f"  {what} 폭이 넘쳐 크기를 {size} 로 줄임 (잉크 {iw}px ≤ {maxw})")
    # 여러 줄이면 실제 자막 문구로 다시 재야 자리가 맞는다
    t2, b2, ih2, _w2 = probe(name, size, text, align)
    if align == 8:            # 위쪽 기준: 잉크 위쪽이 원하는 y 에 오게
        off = t2 - PROBE_Y
    else:                     # 가운데 기준: 잉크 한가운데가 원하는 y 에 오게
        off = (t2 + b2) / 2.0 - PROBE_Y
    print(f"  {what} 크기 {size} · 잉크높이 {ih}(목표 {target_h}) · 자리보정 {-off:+.0f}px")
    return size, -off


def wrap(t, n):
    """| 가 있으면 그 자리에서, 없으면 어절 단위로 n 자에 맞춰 끊는다."""
    if "|" in t:
        return NL.join(p.strip() for p in t.split("|"))
    ws = t.split()
    ls, cur = [], ""
    for w in ws:
        if cur and len(cur) + 1 + len(w) > n:
            ls.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        ls.append(cur)
    return NL.join(ls)


def chunks(t, lo, hi):
    """나레 한 마디를 어절 단위로 잘게 쪼갠다.
    ★원본 포레이로는 4~10자짜리 한 줄이 0.7~0.9초마다 바뀐다(§17-4). 통으로 띄우면
      읽을 게 많아 보이고 말과 글자가 어긋난다."""
    if "|" in t:
        return [p.strip() for p in t.split("|") if p.strip()]
    # ★숫자·수량 뒤에서 끊으면 "냉동식품 만 / 원어치" 처럼 갈라진다. 붙여 둔다.
    import re as _re
    HOLD = _re.compile(r"(?:[0-9]+|만|천|백|십|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)$")
    out, cur = [], ""
    ws = t.split()
    for i, w in enumerate(ws):
        cand = (cur + " " + w).strip()
        too_long = cur and len(cand.replace(" ", "")) > hi
        if too_long and HOLD.search(cur):      # 수량으로 끝나면 한 어절 더 붙인다
            too_long = False
        if too_long:
            out.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        if out and len(cur.replace(" ", "")) < lo:   # 꼬리가 너무 짧으면 앞에 붙인다
            out[-1] = (out[-1] + " " + cur).strip()
        else:
            out.append(cur)
    return out or [t]


dlg_caps = [wrap(dtext(r["text"]), spec.WRAP_DLG) for r in rows if r["kind"] == "D"]
narr_bits = [c for r in rows if r["kind"] == "N"
             for c in chunks(r["text"], *spec.NARR_CHUNK)]
dlg_line = max((p for t in dlg_caps for p in t.split(NL)), key=len, default="가나다라마바사아자")
narr_line = max(narr_bits, key=len, default="가나다라마바사아자")

H1S, H1OFF = fit(spec.FONT_HEAD, episode.HEAD1, spec.HEAD_INK[0], spec.HEAD_MAXW, 8, "제목 1행")
H2S, H2OFF = fit(spec.FONT_HEAD, episode.HEAD2, spec.HEAD_INK[1], spec.HEAD_MAXW, 8, "제목 2행")
NARRS, NARR_OFF = fit(spec.FONT_NARR, narr_line, spec.NARR_INK, spec.CAP_MAXW, 5, "나레 자막")
CAPS, _ = fit(spec.FONT_DLG, dlg_line, spec.DLG_INK, spec.CAP_MAXW, 5, "대사 자막")
_, CAP_OFF1 = fit(spec.FONT_DLG, dlg_line, spec.DLG_INK, spec.CAP_MAXW, 5, "대사 1행")
_, CAP_OFF2 = fit(spec.FONT_DLG, dlg_line + NL + dlg_line, spec.DLG_INK, 9999, 5, "대사 2행")
# ★대사 덩이는 화면에 **적은 그대로** 그려진다(줄바꿈을 안 한다).
#   글자 크기는 짧은 줄 기준으로 잡히니, 긴 덩이는 화면 밖으로 삐져나간다.
#   실제로 ep14 에서 19자짜리 덩이가 좌우로 잘렸다 → 여기서 잡는다.
for _r in rows:
    if _r["kind"] != "D" or not isinstance(_r["text"], (list, tuple)):
        continue
    for _c in _r["text"]:
        _w = probe(spec.FONT_DLG, CAPS, _c[0], 5, w=4000)[3]
        if _w > spec.CAP_MAXW:
            # ★[규격 위반] 칸은 이미 위에서 찍혔다. WARN 에 넣으면 아무도 못 본다 — 바로 찍는다.
            print(f"  ★[규격 위반] 대사 자막 '{_c[0]}' 이 {_w}px 라 "
                  f"화면(최대 {spec.CAP_MAXW}px)을 넘는다 — 덩이를 둘로 쪼개라")

EFFS, EFF_OFF = fit(spec.FONT_DLG, "오! 여신의 탄생이다", spec.EFF_INK, spec.CAP_MAXW, 5, "효과자막")
WORKNAME = getattr(episode, "WORK", "")
PLATFORM = getattr(episode, "PLATFORM", "")
_FCR = getattr(spec, "FONT_CREDIT", spec.FONT_DLG)
CREDIT1 = getattr(spec, "CREDIT_FMT", "{work}").format(work=WORKNAME or "작품명")
CREDIT2 = getattr(spec, "CREDIT2_FMT", "").format(platform=PLATFORM) if PLATFORM else ""
CRS, CR_OFF = fit(_FCR, CREDIT1, spec.CREDIT_INK, 900, 5, "작품명")
if CREDIT2:
    CR2S, CR2_OFF = fit(_FCR, CREDIT2, getattr(spec, "CREDIT2_INK", spec.CREDIT_INK), 900, 5, "풀영상 안내")

SX = spec.FONT_SCALEX
ST = "0,0,0,0,{sx},100,0,0,1,{o},{sh},{al},{ml},{mr},{mv},1"
A = ["[Script Info]", "ScriptType: v4.00+",
     f"PlayResX: {spec.CANVAS[0]}", f"PlayResY: {spec.CANVAS[1]}",
     "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
     "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,"
     " Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline,"
     " Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
     # 제목 두 행 — 위쪽 가운데 기준(al 8)이라 \pos 의 y 가 곧 잉크 위쪽이다
     f"Style: H1,{spec.FONT_HEAD},{H1S},{spec.COL_HEAD1},&H00FFFFFF,{spec.COL_OUTLINE},&H00000000,"
     + ST.format(sx=SX, o=getattr(spec, "HEAD_OUTLINE", 8), sh=0, al=8, ml=40, mr=40, mv=0),
     f"Style: H2,{spec.FONT_HEAD},{H2S},{spec.COL_HEAD2},&H00FFFFFF,{spec.COL_OUTLINE},&H00000000,"
     + ST.format(sx=SX, o=getattr(spec, "HEAD_OUTLINE", 8), sh=0, al=8, ml=40, mr=40, mv=0),
     # ★나레(살구·1행·위)와 대사(흰색·1~2행·아래)를 스타일부터 가른다
     f"Style: NARR,{spec.FONT_NARR},{NARRS},{spec.COL_NARR},&H00FFFFFF,{spec.COL_OUTLINE},"
     f"&H00000000," + ST.format(sx=SX, o=spec.OUTLINE_PX, sh=0, al=5, ml=35, mr=35, mv=0),
     f"Style: CAP,{spec.FONT_DLG},{CAPS},{spec.COL_DLG},&H00FFFFFF,{spec.COL_OUTLINE},"
     f"&H00000000," + ST.format(sx=SX, o=spec.OUTLINE_PX, sh=0, al=5, ml=35, mr=35, mv=0),
     f"Style: CREDIT,{_FCR},{CRS},{spec.COL_CREDIT},&H00FFFFFF,{spec.COL_OUTLINE},"
     f"&H00000000," + ST.format(sx=SX, o=spec.CREDIT_OUTLINE, sh=0, al=5, ml=30, mr=30, mv=0),
     (f"Style: CREDIT2,{_FCR},{CR2S},{spec.COL_CREDIT},&H00FFFFFF,{spec.COL_OUTLINE},"
      f"&H00000000," + ST.format(sx=SX, o=spec.CREDIT_OUTLINE, sh=0, al=5, ml=30, mr=30, mv=0))
     if CREDIT2 else "",
     f"Style: EFF,{spec.FONT_DLG},{EFFS},{spec.COL_EFF},&H00FFFFFF,{spec.COL_OUTLINE},"
     f"&H00000000," + ST.format(sx=SX, o=spec.OUTLINE_PX, sh=0, al=5, ml=30, mr=30, mv=0),
     "", "[Events]",
     "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
POS = "{" + BS + "pos(540,%d)}"
A.append(f"Dialogue: 0,{tc(0)},{tc(TOTAL)},H1,,0,0,0,,"
         f"{POS % round(spec.HEAD_Y[0] + H1OFF)}{episode.HEAD1}")
if WORKNAME:
    A.append(f"Dialogue: 0,{tc(0)},{tc(TOTAL)},CREDIT,,0,0,0,,"
             f"{POS % round(spec.CREDIT_Y + CR_OFF)}{CREDIT1}")
if CREDIT2:
    A.append(f"Dialogue: 0,{tc(0)},{tc(TOTAL)},CREDIT2,,0,0,0,,"
             f"{POS % round(getattr(spec, 'CREDIT2_Y', spec.CREDIT_Y + 80) + CR2_OFF)}{CREDIT2}")
A.append(f"Dialogue: 0,{tc(0)},{tc(TOTAL)},H2,,0,0,0,,"
         f"{POS % round(spec.HEAD_Y[1] + H2OFF)}{episode.HEAD2}")
# ★효과자막이 자막 자리('cap')에 뜨는 동안에는 흰 자막을 감춘다.
#   실제 포레이로도 0초 효과자막 밑에 흰 자막을 겹쳐 두지 않는다(§17-4).
blocked = []
for e in EFFECTS:
    where = e[2] if len(e) > 2 else "right"
    if where not in ("lowleft", "lowright"):
        continue   # 자막 자리를 가리는 효과자막만 흰 자막을 감춘다
    t = e[0]
    hold = e[3] if len(e) > 3 else 1.2
    blocked.append((t - 0.05, min(t + hold + 0.05, TOTAL)))
blocked.sort()


def holes(t0, t1):
    """[t0,t1) 에서 효과자막에 가린 구간을 도려낸 조각들."""
    out = [(t0, t1)]
    for b0, b1 in blocked:
        nxt = []
        for a0, a1 in out:
            if b1 <= a0 or b0 >= a1:
                nxt.append((a0, a1))
                continue
            if a0 < b0:
                nxt.append((a0, b0))
            if b1 < a1:
                nxt.append((b1, a1))
        out = nxt
    return [(a, b) for a, b in out if b - a > 0.25]



def anim(x, y):
    """★원본처럼 **작게 나타나 커진다**(48%->100%, 4프레임). 반대로 하면 안 된다."""
    tag = "{" + BS + "fad(" + spec.FADE_MS + ")" + BS + "pos(%d,%d)" % (x, y)
    if getattr(spec, "POP_START", 0):
        g = spec.POP_START
        tag += (BS + "fscx%d" % g + BS + "fscy%d" % g
                + BS + "t(0,%d," % spec.POP_MS + BS + "fscx100" + BS + "fscy100)")
    return tag + "}"


ALIGN = {}
if os.path.exists("narr_align.json"):
    ALIGN = json.load(io.open("narr_align.json", encoding="utf-8"))
    print(f"  narr_align.json 을 쓴다 — 나레 자막을 실제 발화 시각에 맞춘다")
else:
    print("  ★narr_align.json 이 없다 — align.py 를 돌리면 자막이 말에 딱 맞는다")
hidden = 0
nbits = 0
ndlgbits = 0
nidx = 0
for r in rows:
    t0 = r["off"] + 0.04
    t1 = r["off"] + r["d"] - 0.04
    if r["kind"] == "D":
        # ★원본 대사도 한 줄씩 잘라 순서대로 넘긴다(사용자 지시).
        #   문구가 [(글, 소재시작, 소재끝), ...] 이면 **실제 말한 시각**에 딱 맞춘다.
        #   그냥 문자열이면 | 로 자르고 글자수 비례로 나눈다.
        if isinstance(r["text"], (list, tuple)):
            spans = []
            for b, s0, s1 in r["text"]:
                spans.append((b, r["off"] + (s0 - r["s0"]), r["off"] + (s1 - r["s0"])))
        else:
            bits = ([x.strip() for x in r["text"].split("|") if x.strip()]
                    if "|" in r["text"] else chunks(r["text"], *spec.DLG_CHUNK))
            wsum = sum(max(1, len(b.replace(" ", ""))) for b in bits)
            at = t0
            spans = []
            for b in bits:
                e = min(t1, at + (t1 - t0) * max(1, len(b.replace(" ", ""))) / wsum)
                spans.append((b, at, e))
                at = e
        for b, st, en in spans:
            for a2, b2 in holes(st, en):
                if b2 - a2 >= 0.12:
                    A.append(f"Dialogue: 0,{tc(a2)},{tc(b2)},CAP,,0,0,0,,"
                             f"{anim(540, round(spec.DLG_CAP_Y + CAP_OFF1))}{b}")
                    ndlgbits += 1
        continue
    # ★나레 — 살구색 1행. 마디를 어절 덩이로 쪼개되,
    #   **TTS 가 실제로 말하는 창**에만 배분한다. 앞뒤 여유까지 넣으면 자막이 말보다 먼저 뜬다.
    nidx += 1
    ws, we = speech_window(r["wav"])
    base = r["off"] + spec.NARR_PAD / 2
    a0, a1 = base + ws, base + we
    bits = chunks(r["text"], *spec.NARR_CHUNK)
    rec = ALIGN.get(f"n{nidx}")
    spans = []
    if rec and len(rec) == len(bits):
        # ★전사에서 받은 실제 단어 시각. 빠진 칸은 앞뒤로 이어 메운다.
        prev = ws
        for bi, (_b, s0, s1) in enumerate(rec):
            st = prev if s0 is None else max(ws, s0)
            en = s1 if s1 is not None else None
            spans.append([st, en])
            prev = en if en is not None else st
        for bi in range(len(spans)):
            if spans[bi][1] is None:
                nxt = next((spans[j][0] for j in range(bi + 1, len(spans))
                            if spans[j][0] is not None), we)
                spans[bi][1] = max(spans[bi][0] + 0.15, nxt)
        spans[-1][1] = max(spans[-1][1], we)          # 마지막은 말 끝까지
        for bi in range(len(spans) - 1):
            spans[bi][1] = spans[bi + 1][0]           # 사이를 비우지 않는다
        spans = [(base + a, base + b) for a, b in spans]
    else:
        wsum = sum(max(1, len(b.replace(" ", ""))) for b in bits)
        at = a0
        for b in bits:
            e = min(a1, at + (a1 - a0) * max(1, len(b.replace(" ", ""))) / wsum)
            spans.append((at, e))
            at = e
    # ★★덩이를 **절대 버리지 않는다.**
    #   예전에는 0.12초보다 짧으면 그냥 버렸다 — align 이 시각을 못 찾은 덩이가
    #   통째로 사라져서 "행운을 부른다는 (돌이 박힌) 은팔찌입니다" 처럼
    #   말은 나오는데 글자가 빠졌다(사용자 지적).
    MINBIT = 0.28
    _st = [float(a) for a, _ in spans]
    _en = [float(b) for _, b in spans]
    _fixed = False
    for _i in range(len(bits)):
        if _en[_i] - _st[_i] < MINBIT:
            _en[_i] = _st[_i] + MINBIT
            _fixed = True
        if _i + 1 < len(bits) and _st[_i + 1] < _en[_i]:
            _st[_i + 1] = _en[_i]
            if _en[_i + 1] < _st[_i + 1] + MINBIT:
                _en[_i + 1] = _st[_i + 1] + MINBIT
    _cap = r["off"] + r["d"] - 0.02
    if _en[-1] > _cap:                       # 마디 밖으로 넘치면 통째로 눌러 넣는다
        _a, _b = _st[0], _en[-1]
        _sc = (_cap - _a) / (_b - _a) if _b > _a else 1.0
        _st = [_a + (x - _a) * _sc for x in _st]
        _en = [_a + (x - _a) * _sc for x in _en]
        _fixed = True
    if _fixed:
        print(f"    나레 n{nidx} 자막 덩이 시각을 다시 폈다 — 버려지는 덩이가 없게")
    for b, st, en in zip(bits, _st, _en):
        A.append(f"Dialogue: 0,{tc(st)},{tc(en)},NARR,,0,0,0,,"
                 f"{anim(540, round(spec.NARR_CAP_Y + NARR_OFF))}{b}")
        nbits += 1
nfx = 0
for e in EFFECTS:
    t, txt = e[0], e[1]
    where = e[2] if len(e) > 2 else "right"
    hold = e[3] if len(e) > 3 else 1.2
    x, y = spec.EFF_POS.get(where, spec.EFF_POS["right"])
    tag = anim(x, round(y + EFF_OFF))
    A.append(f"Dialogue: 1,{tc(t)},{tc(min(t+hold, TOTAL))},EFF,,0,0,0,,{tag}{wrap(txt, 10)}")
    nfx += 1
# ★효과자막이 **어느 그림 위에** 떨어지는지 찍어 둔다(§17-19).
#   눈대중으로 적은 초가 몇 초씩 밀려 엉뚱한 얼굴에 붙는 사고가 있었다.
for _e in EFFECTS:
    _t = float(_e[0])
    _hit = False
    for (_s0, _s1, _at, _d, _kind, _rr, _st) in rsegs:
        if _at <= _t < _at + _d:
            _src = _s0 + (_t - _at) * (_st if _st != 1.0 else 1.0)
            _under = ""
            if _kind == "D" and _rr is not None and isinstance(_rr["text"], (list, tuple)):
                _under = " / ".join(c[0] for c in _rr["text"]
                                    if c[1] - 0.05 <= _src <= c[2] + 0.05)
            elif _rr is not None:
                _under = str(_rr.get("text", ""))
            print(f"  효과자막 '{_e[1]}' {_t:6.2f}초 → 소재 {_src:6.2f}초"
                  f" ({'대사' if _kind == 'D' else '나레'}"
                  + (f", 밑자막 '{_under}'" if _under else "") + ")")
            _hit = True
            break
    if not _hit:
        print(f"  효과자막 '{_e[1]}' {_t:6.2f}초 → ★어느 컷에도 안 걸린다(영상 밖)")

open("captions.ass", "w", encoding="utf-8").write("\n".join(A) + "\n")
ndlg = sum(1 for r in rows if r["kind"] == "D")
print(f"  나레 자막 {nbits}덩이 · 대사 자막 {ndlgbits}덩이({ndlg}발화) · 효과자막 {nfx}장"
      + (f" · 효과자막에 가려 통째로 감춘 자막 {hidden}장" if hidden else ""))
LATE = [w for w in WARN if w.startswith("자막이")]
if LATE:
    print("\n  ┌ [라마 규격 위반]")
    for w in LATE:
        print("  │ ★ " + w)
    print("  └\n")

# ── 6. 2차: 캔버스 + 자막 + 나레 ────────────────────────
ins = ["-i", "body.mkv"]
# ★원음 바닥을 이어 붙인 뒤 통째로 올린다(§17-7). 컷마다 걸면 컷 사이 레벨이 튄다.
# ★나레가 실제로 말하는 구간에서만 원음을 끈다(사용자 지시).
#   마디 사이 빈틈까지 끄면 그 자리가 통째로 죽는다 — 빈틈에는 원음이 돌아온다.
#   ★말하는 동안만 끄면 마디 사이 빈틈으로 드라마 소리가 찔끔 샌다(사용자 지적).
#   나레 블록은 통째로 끊는다. 대사 꼬리를 물지 않게 시작은 조금 늦춘다.
spk = []
for r in rows:
    if r["kind"] == "N":
        spk.append((r["off"] + spec.MUTE_LEAD, r["off"] + r["d"] - 0.02))
# 잇닿은 나레 블록은 하나로 합친다 (블록 사이에서 원음이 되살아나지 않게)
mrg = []
for a, b in spk:
    if mrg and a - mrg[-1][1] < 0.12:
        mrg[-1][1] = b
    else:
        mrg.append([a, b])
spk = [(a, b) for a, b in mrg]
if getattr(spec, "MUTE_UNDER_NARR", False) and spk:
    # ★딱 끊으면 '틱' 하고 튄다. 앞뒤로 R 초에 걸쳐 밀어 내리고 올린다.
    R = spec.MUTE_RAMP
    g = "1"
    for a, b in spk:
        F = getattr(spec, "MUTE_FLOOR", 0.0)
        gate = f"(1-(1-{F})*clip(min((t-{a:.2f})/{R},({b:.2f}-t)/{R}),0,1))"
        g = f"min({g},{gate})"
    fc2 = [f"[0:a]{spec.BED_LIFT},volume=volume='{g}':eval=frame[bed]"]
else:
    fc2 = [f"[0:a]{spec.BED_LIFT}[bed]"]
mix = ["[bed]"]
k = 1
for r in rows:
    if r["kind"] == "N":
        ins += ["-i", r["wav"]]
        t = int((r["off"] + spec.NARR_PAD / 2) * 1000)
        fc2.append(f"[{k}:a]adelay={t}|{t}[n{k}]")
        mix.append(f"[n{k}]")
        k += 1
# ★장면 전환 효과음 — 이음매 앞뒤 화면을 실제로 비교해 확 바뀌는 곳에만 깐다
sfx_at = []
if getattr(spec, "SFX_WHOOSH", None):
    wav = None
    for cand in (os.path.join("sfx", spec.SFX_WHOOSH + ".wav"),
                 os.path.join(os.path.dirname(os.path.dirname(HERE)),
                              "LLJtlSPtAMU", "sfx", spec.SFX_WHOOSH + ".wav")):
        if os.path.exists(cand):
            wav = cand
            break
    if wav:
        import numpy as _np, cv2 as _cv2
        capb = _cv2.VideoCapture("body.mkv")
        bfps = capb.get(_cv2.CAP_PROP_FPS) or 30.0
        def _fr(t):
            capb.set(_cv2.CAP_PROP_POS_FRAMES, max(0, int(round(t * bfps))))
            ok, f = capb.read()
            if not ok:
                return None
            return _cv2.cvtColor(_cv2.resize(f, (96, 96)), _cv2.COLOR_BGR2GRAY).astype(_np.float32)
        cand2 = []
        for (_s0, _s1, at, d, kind, _r, _st) in segs:
            if at < 0.15:
                continue
            a0, a1 = _fr(at - 0.07), _fr(at + 0.07)
            if a0 is None or a1 is None:
                continue
            cand2.append((float(_np.abs(a1 - a0).mean()), at))
        capb.release()
        cand2.sort(reverse=True)
        thr = spec.SFX_DIFF_MIN
        if cand2:
            thr = max(spec.SFX_DIFF_MIN,
                      float(_np.percentile([c[0] for c in cand2], spec.SFX_PCT)))
        for diff, at in cand2:
            if diff < thr:
                break
            if all(abs(at - x) >= spec.SFX_MIN_GAP for x in sfx_at):
                sfx_at.append(at)
            if len(sfx_at) >= spec.SFX_MAX:
                break
        sfx_at.sort()
        # ★사용자가 특정 자리의 효과음을 빼거나 바꿀 수 있다 (2026-09-15 mk01 "너 부산 다시 내려갈래?" 자리).
        #   episode.py:  SFX_RULES = [(("D", 5), None), (("N", 2), "sfx/boom.wav", -12)]
        #   앵커 ("D", n) = n번째 대사 블록 시작, ("N", n) = n번째 나레 마디 시작, 숫자 = 완성본 초.
        #   둘째가 None 이면 그 자리(±0.5초)의 whoosh 를 뺀다. 파일이면 whoosh 대신 그 파일을 깐다(셋째 = dB, 기본 SFX_DB).
        _rows_d = [r for r in rows if r["kind"] == "D"]
        _rows_n = [r for r in rows if r["kind"] == "N"]
        def _anchor_t(a):
            if isinstance(a, (int, float)):
                return float(a)
            kind, n = a[0], int(a[1])
            src_rows = _rows_d if kind == "D" else _rows_n
            if not (1 <= n <= len(src_rows)):
                sys.exit(f"SFX_RULES 앵커 {a!r} — {kind} 블록이 {len(src_rows)}개뿐이다")
            return src_rows[n - 1]["off"]
        sfx_list = [(t, wav, spec.SFX_DB) for t in sfx_at]
        # ★앞머리 효과음(spec.OPEN_SFX = (파일이름, dB)) — 두둥픽의 「두둥 북소리」를 0초에 깐다(사용자 2026-09-15).
        #   LLJtlSPtAMU/sfx/<파일> 을 쓴다. episode.py 의 SFX_RULES 가 0초를 따로 정하면 그쪽이 이긴다.
        _rules = list(getattr(episode, "SFX_RULES", []))
        _open = getattr(spec, "OPEN_SFX", None)
        if _open and not any(isinstance(r[0], (int, float)) and abs(float(r[0])) < 0.01 for r in _rules):
            _of = os.path.join(os.path.dirname(os.path.dirname(HERE)), "LLJtlSPtAMU", "sfx", _open[0])
            if os.path.exists(_of):
                _rules.insert(0, (0.0, _of, _open[1]))
                _rules.insert(1, (0.55, None))      # 북소리 바로 뒤의 휙은 뺀다 (소리가 겹쳐 지저분하다)
        for _rule in _rules:
            _t = _anchor_t(_rule[0])
            _before = len(sfx_list)
            sfx_list = [x for x in sfx_list if abs(x[0] - _t) > 0.5]
            if _rule[1] is None:
                print(f"  효과음 {_t:.1f}s 자리 뺌 (SFX_RULES, {_before - len(sfx_list)}개)")
            else:
                _f = _rule[1] if os.path.isabs(_rule[1]) else os.path.join(wd, _rule[1])
                if not os.path.exists(_f):
                    sys.exit(f"SFX_RULES 파일이 없다: {_f}")
                _db = _rule[2] if len(_rule) > 2 else spec.SFX_DB
                sfx_list.append((_t, _f, _db))
                print(f"  효과음 {_t:.1f}s 자리 → {os.path.basename(_f)} ({_db}dB)")
        sfx_list.sort()
        for t, _f, _db in sfx_list:
            ins += ["-i", _f]
            ms = int(max(0, t - 0.06) * 1000)
            fc2.append(f"[{k}:a]adelay={ms}|{ms},volume={_db}dB[w{k}]")
            mix.append(f"[w{k}]")
            k += 1
        print(f"  장면전환 효과음 {len(sfx_list)}개 (문턱 {thr:.0f}) "
              + " ".join(f"{t:.1f}s" for t, _, _ in sfx_list))
fc2.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:dropout_transition=0,"
           f"alimiter=limit=0.97,"
           f"loudnorm=I={spec.MASTER_LUFS}:TP={spec.MASTER_TP}:LRA={spec.LRA_MAX},"
           f"aresample=48000[aout]")
# 그림을 y=VID_Y 에 앉히고 위아래는 검정. 아래 띠는 비워 둔다(§17-2).
# ★2026-09-15 템플릿: 제목 2행 뒤에 가로 꽉 찬 빨간 띠(spec.HEAD2_BAND)를 자막보다 먼저 그린다.
_band = getattr(spec, "HEAD2_BAND", None)
_bandf = (f"drawbox=x=0:y={_band[0]}:w={spec.CANVAS[0]}:h={_band[1]-_band[0]}:color={_band[2]}:t=fill,"
          if _band else "")
fc2.append(f"[0:v]pad={spec.CANVAS[0]}:{spec.CANVAS[1]}:0:{spec.VID_Y}:black,{_bandf}"
           f"ass=captions.ass:fontsdir=fonts[vout]")
OUT = getattr(episode, "OUT", "out.mp4")
print("2차 굽기…")
open("_fc2.txt", "w", encoding="utf-8").write(";".join(fc2))
subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins + ["-/filter_complex", "_fc2.txt",
                "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-crf", "17",
                "-preset", "slow", "-pix_fmt", "yuv420p", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT], check=True)

# ── 6-2. ★아래 띠 로고 (라마 템플릿) ─────────────────────
#   episode.LOGO = ("logo.png", 높이px, 세로중앙y) — 편 폴더의 투명 PNG 를 검은 아래 띠 가운데에 얹는다.
#   자막·소리는 손대지 않는다(-c:a copy). 없으면 건너뛴다. 로고 만드는 법은 docs/라마-지침서.md §4.
_logo = getattr(episode, "LOGO", None)
if _logo:
    _lf = _logo[0] if isinstance(_logo, (tuple, list)) else _logo
    _lh = _logo[1] if isinstance(_logo, (tuple, list)) and len(_logo) > 1 else getattr(spec, "LOGO_DEFAULT_H", 240)
    _lcy = _logo[2] if isinstance(_logo, (tuple, list)) and len(_logo) > 2 else getattr(spec, "LOGO_DEFAULT_CY", 1650)
    if not os.path.exists(_lf):
        print(f"  ★로고 파일이 없다: {_lf} — 아래 띠를 비워 둔다")
    else:
        _tmp = "_logo_tmp.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", OUT, "-i", _lf, "-filter_complex",
                        f"[1]scale=-1:{_lh}[l];[0][l]overlay=(W-w)/2:{_lcy}-{_lh//2}:format=auto",
                        "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p",
                        "-profile:v", "high", "-c:a", "copy", "-movflags", "+faststart", _tmp], check=True)
        os.replace(_tmp, OUT)
        print(f"  로고 {_lf} 높이 {_lh} 세로중앙 {_lcy} 에 얹음")

# ── 7. 소리 검사: 무음이 있으면 안 된다 (§17-7) ─────────
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", OUT, "-ac", "1", "-ar", "16000",
                      "-f", "s16le", "-"], capture_output=True).stdout
try:
    import numpy as np
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    win = 800
    n = max(1, len(x) // win)
    db = 20 * np.log10(np.array([np.sqrt((x[i*win:(i+1)*win]**2).mean() + 1e-12)
                                 for i in range(n)]) + 1e-9)
    q = db < -45
    spans = []
    i = 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]:
                j += 1
            spans.append((i * 0.05, j * 0.05))
            i = j
        else:
            i += 1
    sil = float(q.mean() * 100)
    longest = max((b - a for a, b in spans), default=0.0)
    # ★컷 이음매의 0.2초짜리 순간 딥은 문제가 아니다. 0.4초 넘게 이어지는 죽은 구간만 잡는다.
    bad = [(a, b) for a, b in spans if b - a >= 0.4]
    print(f"  무음(-45dB) {sil:.2f}% · 가장 긴 구간 {longest:.2f}초")
    if bad:
        print("  ★죽은 구간이 있다(§17-7): "
              + " ".join(f"{a:.1f}~{b:.1f}" for a, b in bad[:6]))
except Exception:
    pass

print(f"  완성: {os.path.join(wd, OUT)}  {dur(OUT):.2f}초")

# ── 9. ★★씽크 검사 — 굽고 나면 **무조건** 잰다 (0순위 규칙, 사용자 지시) ──
#   자막·나레가 계산상 시각에 놓이므로, 실제 소리가 그 자리에 있는지
#   재 보지 않으면 밀린 걸 알 수 없다. 눈대중 금지.
_sc = subprocess.run([sys.executable, os.path.join(HERE, "synccheck.py"), wd],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
_line = [l for l in (_sc.stdout or "").splitlines() if "[씽크]" in l]
print(_line[0] if _line else "  [씽크] ★못 쟀다 — synccheck.py 를 직접 돌려 봐라")
if _sc.returncode != 0:
    print("  ┌ [라마 규격 위반]")
    print("  │ ★ 씽크가 0.10초를 넘게 어긋났다. 이대로 내보내지 마라.")
    print("  │   python presets/라마/synccheck.py " + os.path.basename(wd))
    print("  └ 어느 마디가 밀렸는지 위 명령으로 확인해라.")

# ── 8. 완성본만 채널 폴더로 ─────────────────────────────
dst_dir = os.path.join(getattr(spec, "DELIVER_ROOT", "."), spec.CHANNEL)
os.makedirs(dst_dir, exist_ok=True)
shutil.copy2(OUT, os.path.join(dst_dir, OUT))
print(f"  모음: {os.path.join(dst_dir, OUT)}")

# ── 9. 설명문 초안 (§17-8) ──────────────────────────────
if not os.path.exists("description.txt"):
    work = getattr(episode, "WORK", "")
    # 해시태그에는 공백·콜론이 못 들어간다 — 「신병4 : 사보타주」 -> #신병4
    tag = re.split(r"[\s:·]", work.strip())[0] or "작품명"
    desc = f"""{episode.HEAD1} {episode.HEAD2}.

<배경·맥락 한 줄>

<질문 한 줄로 끝낸다>

* 작품: {work}

#{tag} #드라마리뷰 #명장면 #한국드라마 #쇼츠"""
    open("description.txt", "w", encoding="utf-8").write(desc)
    print("  설명문 초안: description.txt  (★손봐야 한다 — §17-8)")
else:
    print("  설명문: description.txt (이미 있어 건드리지 않음)")
