# -*- coding: utf-8 -*-
"""넷플릭스 자막 규격 맞추기 — 포레이로 (2026-09-25 사용자 지시: 만든 편·앞으로 만들 편 전부).

docs/NETFLIX-자막규격.md 의 규칙을 자막에 실제로 적용한다.
  · 자막은 한 줄 · 한 장 0.83초 이상 · 줄 끝 . , 금지 · 말줄임표는 … 한 글자
  · 꾸미는 말·부정어와 뒤 낱말을 다른 장으로 떼지 않는다("기현을 제 / 집으로" ✗)

쓰는 곳
  align.py    나레 덩이를 **낱말 시각**으로 다시 나눈다(resplit) → narr_align.json 에 덩이 글까지 남긴다
  build.py    captions.ass 를 쓰기 직전에 fix_ass() — 늘리기 · 앞당기기 · 합치기 · 문장부호
  ★이미 만든 편은 다시 굽지 않는다(사용자 지시 2026-09-25) — 새로 만드는 편부터 적용된다.

★씽크 0순위: 자막을 말보다 **0.10초 넘게 앞당기지 않는다**(synccheck 한도와 같다).
"""
import os
import re
from difflib import SequenceMatcher

MIN_DUR = 5 / 6          # G1 넷플릭스 최소 표시 시간
EPS = 0.01               # ASS 는 1/100초라 0.83 을 통과로 본다
LEAD_MAX = 0.10          # 자막을 말보다 먼저 띄워도 되는 한도 (씽크 한도)
MAX_CHARS = 16           # K1 한 줄 16자 (라틴·숫자·공백·문장부호 0.5)
CAP_STYLES = ("NARR", "CAP")

# 뒤 명사·동사와 떼면 안 되는 말(관형사·부정어) — build.py/align.py chunks() 의 MODS 와 같다
MODS = {"제", "그", "이", "저", "내", "네", "우리", "저희", "너희", "이런", "그런", "저런",
        "어떤", "무슨", "몇", "모든", "온갖", "새", "헌", "옛", "첫", "각", "딴", "다른",
        "여러", "어느", "웬", "그깟", "이깟", "안", "못"}
# 수량 뒤에서 끊지 않는다 — chunks() 의 HOLD 와 같다
HOLD = re.compile(r"(?:[0-9]+|만|천|백|십|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)$")


def kchars(t):
    return sum(1 if "가" <= c <= "힣" or "ㄱ" <= c <= "ㆎ" else 0.5
               for c in t if c not in "\r\n")


def norm(s):
    return re.sub(r"[^가-힣0-9A-Za-z]", "", s)


def no_break_after(word):
    return word in MODS or bool(HOLD.search(word))


# ── 글꼴 폭 ──────────────────────────────────────────────
_font_cache = {}


def font_file(family, fontsdir):
    """편/fonts 안에서 family 이름이 맞는 ttf/otf 를 찾는다."""
    key = (family, fontsdir)
    if key in _font_cache:
        return _font_cache[key]
    from PIL import ImageFont
    hit = None
    if os.path.isdir(fontsdir):
        for f in sorted(os.listdir(fontsdir)):
            if not f.lower().endswith((".ttf", ".otf")):
                continue
            p = os.path.join(fontsdir, f)
            try:
                if ImageFont.truetype(p, 20).getname()[0].replace(" ", "").lower() == family.replace(" ", "").lower():
                    hit = p
                    break
            except Exception:
                pass
    _font_cache[key] = hit
    return hit


def width_fn(family, size, fontsdir, maxw):
    """글이 한 줄 폭(maxw) 안에 드는지 보는 함수. 글꼴을 못 찾으면 16자 기준으로만 본다."""
    path = font_file(family, fontsdir)
    if not path:
        return lambda t: kchars(t) <= MAX_CHARS
    from PIL import ImageFont
    f = ImageFont.truetype(path, int(round(size)))

    def fits(t):
        b = f.getbbox(t)
        return kchars(t) <= MAX_CHARS and (b[2] - b[0]) <= maxw
    return fits


# ── 낱말 시각 ────────────────────────────────────────────
def word_times(text, asr_words, s0, wdur):
    """나레 한 마디(text)의 **낱말마다** [낱말, 시작, 끝] (마디 wav 기준 초).
    align.py 의 덩이 정렬과 같은 문자 정렬(difflib)을 낱말 단위로 한다. 못 찾은 낱말은 앞뒤 사이를 글자 수로 채운다."""
    words = text.replace("|", " ").split()
    ws = [x for x in asr_words if x["start"] >= s0 - 0.15 and x["end"] <= s0 + wdur + 0.25]
    spans, at = [], 0
    for w in words:
        n = len(norm(w))
        spans.append((at, at + n))
        at += n
    T = "".join(norm(w) for w in words)
    A, owner = "", []
    for k, x in enumerate(ws):
        nw = norm(x.get("word", x.get("text", "")))
        A += nw
        owner += [k] * len(nw)
    t2a = [None] * len(T)
    if A:
        for a0, b0, sz in SequenceMatcher(None, T, A, autojunk=False).get_matching_blocks():
            for q in range(sz):
                t2a[a0 + q] = b0 + q
    res = []
    for (ca, cb), w in zip(spans, words):
        idx = [t2a[q] for q in range(ca, min(cb, len(t2a))) if t2a[q] is not None]
        if idx and ws:
            res.append([w, ws[owner[idx[0]]]["start"] - s0, ws[owner[idx[-1]]]["end"] - s0])
        else:
            res.append([w, None, None])
    if res and res[0][1] is None:
        res[0][1] = 0.0
    if res and res[-1][2] is None:
        res[-1][2] = wdur
    k = 0
    while k < len(res):
        if res[k][1] is not None and res[k][2] is not None:
            k += 1
            continue
        j = k
        while j < len(res) and (res[j][1] is None or res[j][2] is None):
            j += 1
        lo = res[k - 1][2] if k > 0 else 0.0
        hi = res[j][1] if j < len(res) and res[j][1] is not None else wdur
        wts = [max(1, len(norm(res[q][0]))) for q in range(k, j)]
        tot, cur = float(sum(wts)), lo
        for q in range(k, j):
            nx = lo + (hi - lo) * sum(wts[:q - k + 1]) / tot
            res[q][1], res[q][2] = cur, nx
            cur = nx
        k = j
    for q in range(1, len(res)):                       # 거꾸로 가는 자리 바로잡기
        if res[q][1] < res[q - 1][1]:
            res[q][1] = res[q - 1][1]
    return res


# ── 덩이 다시 나누기 ─────────────────────────────────────
def resplit(wt, base_bits, t_first, t_end, hi, fits):
    """낱말 시각(wt)으로 덩이를 다시 나눈다. -> [[글, 시작, 끝], ...] (wt 와 같은 시간축)

    덩이 i 는 첫 낱말이 들릴 때 뜨고 다음 덩이가 뜰 때 내려간다(build.py 와 같다).
    첫 덩이는 t_first 에, 마지막 덩이는 t_end 에 맞춘다.
    원래 덩이(base_bits)가 이미 규격(0.83초·꾸미는 말)을 지키면 그대로 둔다.
    아니면 모든 나누기를 훑어서: ① 0.83초 못 되는 장 수 ② 그 모자람 ③ hi 자를 넘는 글자 수
    ④ 원래 덩이와 다른 경계 수 가 가장 작은 것을 고른다. 폭(fits)을 넘거나 꾸미는 말 뒤에서 끊는 나누기는 뺀다."""
    words = [w for w, _, _ in wt]
    n = len(words)
    if n == 0:
        return None
    # 원래 덩이의 경계(낱말 번호)
    base_cut, acc = [], 0
    for b in base_bits:
        acc += len(b.split())
        base_cut.append(acc)
    if acc != n:
        return None
    starts = [s for _, s, _ in wt]

    def spans(cuts):
        out, i = [], 0
        for c in cuts:
            out.append((i, c))
            i = c
        return out

    def score(cuts):
        segs = spans(cuts)
        short = deficit = over = 0
        for k, (i, j) in enumerate(segs):
            t0 = t_first if k == 0 else starts[i]
            t1 = t_end if j == n else starts[j]
            d = t1 - t0
            if d < MIN_DUR - EPS:
                short += 1
                deficit += MIN_DUR - d
            over += max(0, len("".join(words[i:j])) - hi)
        moved = len(set(cuts) ^ set(base_cut))
        return (short, round(deficit, 3), over, moved)

    def valid(cuts):
        for i, j in spans(cuts):
            if not fits(" ".join(words[i:j])):
                return False
            if j < n and no_break_after(words[j - 1]):
                return False
        return True

    base_ok = valid(base_cut) and score(base_cut)[0] == 0
    if base_ok or n > 16:
        best = base_cut
    else:
        best, best_s = base_cut, None
        for mask in range(1 << (n - 1)):
            cuts = [i + 1 for i in range(n - 1) if mask >> i & 1] + [n]
            if not valid(cuts):
                continue
            s = score(cuts)
            if best_s is None or s < best_s:
                best, best_s = cuts, s
    out = []
    for k, (i, j) in enumerate(spans(best)):
        t0 = t_first if k == 0 else starts[i]
        t1 = t_end if j == n else starts[j]
        out.append([" ".join(words[i:j]), t0, t1])
    return out


# ── ASS 한 줄 다루기 ─────────────────────────────────────
def tc_parse(v):
    h, m, s = v.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def tc(v):
    cs = int(round(max(0.0, v) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def parse_event(line):
    p = line.split(",", 9)
    m = re.match(r"^((?:\{[^}]*\})*)(.*)$", p[9])
    return {"p": p, "start": tc_parse(p[1]), "end": tc_parse(p[2]), "style": p[3],
            "tag": m.group(1), "text": m.group(2)}


def render_event(e):
    p = list(e["p"])
    p[1], p[2] = tc(e["start"]), tc(e["end"])
    p[9] = e["tag"] + e["text"]
    return ",".join(p)


def punct(t):
    """K3 줄 끝 . , 지우기 · K4 .. ... → …"""
    t = re.sub(r"\.{2,}", "…", t)
    t = re.sub(r"(?<![.…])[.,]\s*$", "", t)
    return t


def fix_ass(lines, total, fits_by_style=None, log=None, styles=CAP_STYLES):
    """ASS 줄 목록(헤더 포함)에서 NARR/CAP 자막을 넷플릭스 규격에 맞춘다. -> 새 줄 목록

    짧은 자막(0.83초 미만)은 이 순서로 고친다 — 뒤로 갈수록 화면이 많이 바뀐다.
      ① 뒤가 비어 있으면 끝을 늘린다(말과 상관없는 빈 시간이라 씽크 영향 없음)
      ② 앞이 비어 있거나 앞 자막이 넉넉하면 시작을 최대 0.10초 당긴다
      ③ 같은 발화로 이어진 옆 장과 합쳐 한 줄(16자·폭 안)이 되면 합친다
    그래도 모자라면 그대로 두고 log 에 남긴다."""
    log = log if log is not None else []
    fits_by_style = fits_by_style or {}
    idx = [i for i, l in enumerate(lines) if l.startswith("Dialogue:") and l.split(",", 9)[3] in styles]
    ev = [parse_event(lines[i]) for i in idx]
    for e in ev:
        t = punct(e["text"])
        if t != e["text"]:
            log.append(f"문장부호 '{e['text']}' → '{t}'")
            e["text"] = t
    ev.sort(key=lambda e: e["start"])
    ev = [e for e in ev if e["text"].strip()]

    def dur(e):
        return e["end"] - e["start"]

    for e in ev:
        e["d0"], e["s0"] = dur(e), e["start"]

    changed = True
    rounds = 0
    while changed and rounds < 5:
        changed, rounds = False, rounds + 1
        k = 0
        while k < len(ev):
            e = ev[k]
            if dur(e) >= MIN_DUR - EPS:
                k += 1
                continue
            nxt = ev[k + 1]["start"] if k + 1 < len(ev) else total
            prv = ev[k - 1] if k > 0 else None
            # ① 끝 늘리기
            want = e["start"] + MIN_DUR
            new_end = min(want, nxt, total)
            if new_end > e["end"] + 0.004:
                e["end"] = new_end
                changed = True
            # ② 시작 당기기 (말보다 0.10초 안쪽)
            if dur(e) < MIN_DUR - EPS:
                need = MIN_DUR - dur(e)
                room = LEAD_MAX - (e["s0"] - e["start"])          # 여러 번 돌아도 합쳐서 0.10초까지만
                if prv is None:
                    room = min(room, e["start"])
                elif prv["end"] <= e["start"] - 0.004:
                    room = min(room, e["start"] - prv["end"])
                elif prv["style"] == e["style"]:
                    room = min(room, max(0.0, dur(prv) - MIN_DUR))   # 앞 장이 넉넉한 만큼만
                else:
                    room = 0.0
                sh = min(need, room)
                if sh > 0.004:
                    if prv is not None and prv["end"] > e["start"] - sh:
                        prv["end"] = e["start"] - sh
                    e["start"] -= sh
                    changed = True
            # ③ 이어진 옆 장과 합치기
            if dur(e) < MIN_DUR - EPS:
                fits = fits_by_style.get(e["style"], lambda t: kchars(t) <= MAX_CHARS)
                cands = []
                if prv is not None and prv["style"] == e["style"] and abs(prv["end"] - e["start"]) < 0.05:
                    cands.append((k - 1, k))
                if k + 1 < len(ev) and ev[k + 1]["style"] == e["style"] and abs(e["end"] - ev[k + 1]["start"]) < 0.05:
                    cands.append((k, k + 1))
                cands = [(a, b) for a, b in cands if fits(ev[a]["text"] + " " + ev[b]["text"])]
                if cands:
                    a, b = min(cands, key=lambda ab: kchars(ev[ab[0]]["text"] + ev[ab[1]]["text"]))
                    log.append(f"합침 '{ev[a]['text']}' + '{ev[b]['text']}'")
                    ev[a]["text"] = ev[a]["text"] + " " + ev[b]["text"]
                    ev[a]["end"] = ev[b]["end"]
                    ev[a]["d0"] = dur(ev[a])              # 합친 건 위에서 이미 적었다
                    ev[a]["s0"] = min(ev[a]["s0"], ev[b]["s0"])
                    del ev[b]
                    changed = True
                    k = max(0, a - 1)
                    continue
            k += 1
    for e in ev:
        if abs(dur(e) - e["d0"]) > 0.005 and e["d0"] < MIN_DUR - EPS:
            log.append(f"시간 조정 '{e['text']}' {e['d0']:.2f}초 → {dur(e):.2f}초 ({e['start']:.2f}초)")
    for e in ev:
        if dur(e) < MIN_DUR - EPS:
            log.append(f"★그래도 짧음 {dur(e):.2f}초 '{e['text']}' ({e['start']:.2f}초)")
    # 원래 자리에 다시 넣는다(시간 순)
    drop = set(idx)
    at = idx[0] if idx else len(lines)
    before = [l for i, l in enumerate(lines) if i < at and i not in drop]
    after = [l for i, l in enumerate(lines) if i >= at and i not in drop]
    return before + [render_event(e) for e in ev] + after


def styles_fits(lines, fontsdir, maxw, styles=CAP_STYLES):
    """ASS 헤더의 NARR/CAP 스타일(글꼴·크기)로 폭 검사 함수를 만든다."""
    fmt, out = None, {}
    for l in lines:
        if l.startswith("Format:") and "Fontname" in l:
            fmt = [x.strip() for x in l[7:].split(",")]
        elif l.startswith("Style:") and fmt:
            st = dict(zip(fmt, [x.strip() for x in l[6:].split(",")]))
            if st.get("Name") in styles:
                sx = float(st.get("ScaleX", 100) or 100) / 100
                out[st["Name"]] = width_fn(st["Fontname"], float(st["Fontsize"]) * sx, fontsdir, maxw)
    return out
