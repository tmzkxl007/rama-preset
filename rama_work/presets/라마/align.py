# -*- coding: utf-8 -*-
"""나레 자막을 **실제 발화 시각**에 맞춘다.  사용: python align.py <편폴더>

왜 필요한가
  글자수로 나누거나 파형의 골짜기를 찾는 방식은 TTS 가 실제로 쉬는 자리와 어긋난다.
  ("주말 아침에" 5음절이 0.39초로 잡히는 식으로 자막이 말보다 앞선다.)
  그래서 나레 wav 를 통째로 한 번 전사해 **단어 시각**을 받아 덩이 경계를 못 박는다.

하는 일
  1. narr/n*.wav 를 사이에 묵음을 넣어 하나로 잇는다
  2. Speechmatics 로 한 번 전사한다 (편당 1건)
  3. 덩이(어절 묶음)마다 그 안에 든 단어의 시각을 찾아 narr_align.json 으로 남긴다
  build.py 는 이 파일이 있으면 그 시각을 그대로 쓴다.
"""
import io, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
import spec

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

wd = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
sys.path.insert(0, wd)
import episode
os.chdir(wd)

GAP = 0.7          # 마디 사이에 넣는 묵음 (전사기가 마디를 갈라 보게)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True,
                                encoding="utf-8", errors="replace").stdout)


def chunks(t, lo, hi):
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
        if out and len(cur.replace(" ", "")) < lo:
            out[-1] = (out[-1] + " " + cur).strip()
        else:
            out.append(cur)
    return out or [t]


texts = [b[1] for b in episode.BLOCKS if b[0] == "N"]
wavs = [os.path.join("narr", f"n{i}.wav") for i in range(1, len(texts) + 1)]
for w in wavs:
    if not os.path.exists(w):
        sys.exit(f"나레가 없다: {w} (tts.py 를 먼저 돌려라)")

# 1) 이어 붙이기 — 각 마디가 이어붙인 파일에서 몇 초에 시작하는지 기록
starts, at = [], 0.0
lst = []
for w in wavs:
    starts.append(at)
    at += dur(w) + GAP
    lst.append(f"file '{os.path.abspath(w)}'")
    lst.append(f"duration {dur(w):.3f}")
sil = os.path.join("narr", "_gap.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                "-i", f"anullsrc=r=48000:cl=stereo:d={GAP}", sil], check=True)
lines = []
for i, w in enumerate(wavs):
    lines.append(f"file '{os.path.abspath(w)}'")
    if i < len(wavs) - 1:
        lines.append(f"file '{os.path.abspath(sil)}'")
io.open("narr/_list.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
joined = "narr/_all.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                "-i", "narr/_list.txt", "-c", "copy", joined], check=True)
print(f"  나레 {len(wavs)}마디를 이어 {dur(joined):.1f}초로 만들었다")

# 2) 전사 — ★나레가 바뀌면 **반드시 다시** 전사한다.
#   예전에는 파일만 있으면 건너뛰었다. 나레 문구를 갈아엎고 TTS 를 새로 만들어도
#   **옛 문구의 낱말 시각**을 그대로 써서, 덩이 절반이 시각을 못 찾고
#   나머지도 엉뚱한 자리에 붙었다 — "나레이션 씽크 안 맞아"의 진짜 원인이었다.
import hashlib
_join = chr(10).join(texts)
_sig = "|".join("%d:%d" % (os.path.getsize(w), int(os.path.getmtime(w))) for w in wavs)
_stamp = hashlib.sha1((_join + "|" + _sig).encode("utf-8")).hexdigest()
_sf = "narr/_all.asr.stamp"
asr = "narr/_all.asr.json"
_old = io.open(_sf, encoding="utf-8").read().strip() if os.path.exists(_sf) else ""
if _old != _stamp and os.path.exists(asr):
    os.remove(asr)
    print("  ★나레가 바뀌었다 — 전사를 다시 한다")
if not os.path.exists(asr):
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                                     "scripts", "_asr_sm.py"),
                        joined, asr, "ko"], text=True)
    if r.returncode != 0 or not os.path.exists(asr):
        sys.exit("전사 실패")
io.open(_sf, "w", encoding="utf-8").write(_stamp)
d = json.load(io.open(asr, encoding="utf-8"))
words = d.get("words") or [w for s in d.get("segments", []) for w in s.get("words", [])]
if not words:
    sys.exit("단어 시각이 없다 — 전사 결과를 확인해라")
print(f"  단어 {len(words)}개 시각 확보")


def norm(s):
    return re.sub(r"[^가-힣0-9A-Za-z]", "", s)


# 3) 마디마다 — ★**문자 정렬**로 덩이마다 시각을 찾는다.
#   예전에는 글자 수만큼 낱말을 앞에서부터 퍼 담았다(greedy).
#   전사가 한 낱말이라도 다르면 뒤로 갈수록 어긋나 **꼬리 덩이가 통째로 빈다.**
#   (19덩이 중 9개가 비었다 — 나레 자막이 말과 어긋난 원인)
#   이제 쓴 글자와 전사 글자를 difflib 로 맞춰 놓고, 덩이의 글자 범위에
#   해당하는 낱말을 집는다. 그래도 빈 덩이는 **앞뒤 사이를 글자 수로 나눠** 채운다.
from difflib import SequenceMatcher

out = {}
for i, (t, w, s0) in enumerate(zip(texts, wavs, starts), 1):
    wdur = dur(w)
    s1 = s0 + wdur
    ws = [x for x in words if x["start"] >= s0 - 0.15 and x["end"] <= s1 + 0.25]
    bits = chunks(t, *spec.NARR_CHUNK)

    # 덩이가 쓴 글자의 몇 번째부터 몇 번째인지
    spans_txt, at = [], 0
    for b in bits:
        n = len(norm(b))
        spans_txt.append((at, at + n))
        at += n
    T = "".join(norm(b) for b in bits)

    # 전사 글자열 + 글자 → 낱말 번호
    A, owner = "", []
    for k, x in enumerate(ws):
        nw = norm(x.get("word", x.get("text", "")))
        A += nw
        owner += [k] * len(nw)

    # 쓴 글자 → 전사 글자 대응표
    t2a = [None] * len(T)
    if A:
        for a0, b0, sz in SequenceMatcher(None, T, A, autojunk=False).get_matching_blocks():
            for q in range(sz):
                t2a[a0 + q] = b0 + q

    res = []
    for (ca, cb), b in zip(spans_txt, bits):
        idx = [t2a[q] for q in range(ca, min(cb, len(t2a))) if t2a[q] is not None]
        if idx and ws:
            k0, k1 = owner[idx[0]], owner[idx[-1]]
            res.append([b, round(ws[k0]["start"] - s0, 3), round(ws[k1]["end"] - s0, 3)])
        else:
            res.append([b, None, None])

    # ★빈 덩이를 **앞뒤 사이에 글자 수 비례로** 채운다 (버리지도, 밀지도 않는다)
    known = [k for k, r in enumerate(res) if r[1] is not None]
    if known:
        if res[0][1] is None:
            res[0][1] = 0.0
        if res[-1][2] is None:
            res[-1][2] = round(wdur, 3)
        k = 0
        while k < len(res):
            if res[k][1] is not None and res[k][2] is not None:
                k += 1
                continue
            j = k
            while j < len(res) and (res[j][1] is None or res[j][2] is None):
                j += 1
            lo = res[k - 1][2] if k > 0 and res[k - 1][2] is not None else 0.0
            hi = res[j][1] if j < len(res) and res[j][1] is not None else round(wdur, 3)
            wts = [max(1, len(norm(res[q][0]))) for q in range(k, j)]
            tot = float(sum(wts))
            cur = lo
            for q, wt in zip(range(k, j), wts):
                nx = lo + (hi - lo) * (sum(wts[:q - k + 1]) / tot)
                res[q][1] = round(cur, 3)
                res[q][2] = round(nx, 3)
                cur = nx
            k = j
    else:
        # 한 덩이도 못 찾았다 — 글자 수 비례로 통째로 나눈다
        wts = [max(1, len(norm(b))) for b in bits]
        tot = float(sum(wts))
        cur = 0.0
        for q, (b, wt) in enumerate(zip(bits, wts)):
            nx = wdur * (sum(wts[:q + 1]) / tot)
            res[q] = [b, round(cur, 3), round(nx, 3)]
            cur = nx

    # ★겹치거나 거꾸로 가는 자리를 바로잡고, 마지막 덩이는 말 끝까지 늘린다
    for q in range(len(res)):
        if q and res[q][1] < res[q - 1][2]:
            res[q][1] = res[q - 1][2]
        if res[q][2] < res[q][1] + 0.12:
            res[q][2] = res[q][1] + 0.12
    _end = max(x["end"] for x in ws) - s0 if ws else wdur
    res[-1][2] = round(max(res[-1][2], min(_end, wdur)), 3)

    # ★말이 되는 길이인지 본다 — 8글자를 0.2초에 읽을 수는 없다.
    #   글자당 최소 1/11초를 주고 뒤로 밀되, 마디 밖으로 나가면 통째로 눌러 넣는다.
    MINRATE = 11.0
    _sh = False
    for q in range(len(res)):
        need = max(0.12, len(norm(res[q][0])) / MINRATE)
        if res[q][2] - res[q][1] < need:
            res[q][2] = res[q][1] + need
            _sh = True
        if q + 1 < len(res) and res[q + 1][1] < res[q][2]:
            res[q + 1][1] = res[q][2]
    if res[-1][2] > wdur:
        a, bb = res[0][1], res[-1][2]
        sc = (wdur - a) / (bb - a) if bb > a else 1.0
        for q in range(len(res)):
            res[q][1] = a + (res[q][1] - a) * sc
            res[q][2] = a + (res[q][2] - a) * sc
        _sh = True
    if _sh:
        print(f"    n{i} 덩이 길이를 읽을 수 있게 폈다")
    for q in range(len(res)):
        res[q][1] = round(max(0.0, res[q][1]), 3)
        res[q][2] = round(res[q][2], 3)

    out[f"n{i}"] = res
    got = sum(1 for r in res if r[1] is not None)
    print(f"  n{i} {got}/{len(bits)}덩이  " +
          " / ".join(f"{r[0]}({r[1]}~{r[2]})" for r in res))

json.dump(out, io.open("narr_align.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  → narr_align.json")
