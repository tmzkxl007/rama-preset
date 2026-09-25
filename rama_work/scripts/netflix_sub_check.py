#!/usr/bin/env python3
"""넷플릭스 자막 규격 검사기 (Timed Text Style Guide: General Requirements + Korean)

완성본 자막 파일(.ass / .srt / .vtt)을 읽어 넷플릭스 규격 위반을 센다. 파일은 고치지 않는다.

  python netflix_sub_check.py <자막파일 또는 폴더 ...> [--json] [--quiet]

규칙 출처
  General Requirements  https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617
    G1 최소 표시 시간 5/6초(0.833s)          G2 최대 표시 시간 7초
    G3 한 줄 (사용자 지정 2026-09-25 · 넷플릭스는 최대 2줄)   G4 가운데 정렬(화면 위/아래)
  Korean Timed Text Style Guide  https://partnerhelp.netflixstudios.com/hc/en-us/articles/216001127
    K1 한 줄 16자 (라틴 문자·숫자·공백·문장부호는 0.5자)
    K2 읽기 속도 초당 12자 (어린이 9자) — K1과 같은 가중치로 센다
    K3 줄 끝에 마침표·쉼표 금지             K4 말줄임표는 '…' 한 글자 (.. / ... 금지)
    K5 이탤릭 금지

화면에 계속 떠 있는 제목·크레딧·로고 문구(ASS 스타일 H1/H2/HL1/Title/CREDIT*)와 벡터 도형(p 태그)은 자막이 아니라
그래픽이므로 검사하지 않는다. 한 카드를 여러 Dialogue 로 쌓는 방식(끝 시각이 같은 줄들)은
한 자막으로 묶어서 본다.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

MIN_DUR = 5 / 6
MAX_DUR = 7.0
MAX_LINES = 1          # 사용자 지정: 자막은 한 줄. 넷플릭스 원 규격은 2줄
MAX_CPL = 16
MAX_CPS = 12
GRAPHIC_STYLES = re.compile(r"^(H\d|HL\d|Title|CREDIT\d*|LOGO|WM)$", re.I)
ALIGN_CENTER = {2, 5, 8}          # ASS \an: 가운데 열(아래·중간·위)
LEGACY_A = {1: 1, 2: 2, 3: 3, 5: 7, 6: 8, 7: 9, 9: 4, 10: 5, 11: 6}


def kchars(s: str) -> float:
    """넷플릭스 한국어 글자 수: 한글·한자 1, 그 밖(라틴·숫자·공백·문장부호) 0.5."""
    n = 0.0
    for ch in s:
        if ch in "\r\n":
            continue
        name = unicodedata.name(ch, "")
        n += 1 if ("HANGUL" in name or "CJK" in name) else 0.5
    return n


def ts(t: str) -> float:
    t = t.strip().replace(",", ".")
    parts = t.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def parse_ass(text):
    fmt, styles, events = None, {}, []
    sfmt = None
    for line in text.splitlines():
        if line.startswith("Format:") and sfmt is None and "Name" in line and "Fontname" in line:
            sfmt = [x.strip() for x in line[7:].split(",")]
        elif line.startswith("Style:") and sfmt:
            vals = [x.strip() for x in line[6:].split(",", len(sfmt) - 1)]
            st = dict(zip(sfmt, vals))
            styles[st["Name"]] = st
        elif line.startswith("Format:") and "Start" in line:
            fmt = [x.strip() for x in line[7:].split(",")]
        elif line.startswith("Dialogue:") and fmt:
            vals = line[9:].split(",", len(fmt) - 1)
            ev = dict(zip(fmt, [v.strip() if k != "Text" else v for k, v in zip(fmt, vals)]))
            style = ev.get("Style", "")
            if GRAPHIC_STYLES.match(style):
                continue
            raw = ev["Text"]
            tags = "".join(re.findall(r"\{[^}]*\}", raw))
            if re.search(r"\\p[1-9]", tags):      # 벡터 도형(카드 배경·아이콘)은 글자가 아니다
                continue
            body = re.sub(r"\{[^}]*\}", "", raw).replace("\\h", " ")
            body = re.sub(r"\\[Nn]", "\n", body)
            if not body.strip():
                continue
            st = styles.get(style, {})
            m = re.search(r"\\an(\d)", tags)
            if m:
                align = int(m.group(1))
            elif re.search(r"\\a(\d+)", tags):
                align = LEGACY_A.get(int(re.search(r"\\a(\d+)", tags).group(1)), 2)
            else:
                try:
                    align = int(st.get("Alignment", 2))
                except ValueError:
                    align = 2
            italic = bool(re.search(r"\\i1", tags)) or st.get("Italic", "0") not in ("0", "")
            events.append(dict(start=ts(ev["Start"]), end=ts(ev["End"]), style=style,
                               lines=[l for l in body.split("\n") if l.strip()],
                               align=align, italic=italic, stacked=False))
    # 끝 시각·스타일이 같고 시간이 겹치는 줄들 = 한 카드에 쌓은 줄 → 한 자막으로 묶는다
    events.sort(key=lambda e: (e["end"], e["style"], e["start"]))
    merged = []
    for e in events:
        p = merged[-1] if merged else None
        if p and p["style"] == e["style"] and abs(p["end"] - e["end"]) < 1e-3 and e["start"] < p["end"] \
                and len(e["lines"]) == 1 and e["start"] >= p["start"]:
            p["lines"] += e["lines"]
            p["italic"] |= e["italic"]
            p["stacked"] = True
            if e["align"] not in ALIGN_CENTER:
                p["align"] = e["align"]
        else:
            merged.append(dict(e))
    merged.sort(key=lambda e: e["start"])
    return merged


def parse_srt_vtt(text):
    events = []
    blocks = re.split(r"\n\s*\n", text.replace("\r", ""))
    for b in blocks:
        m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)", b)
        if not m:
            continue
        after = b[m.end():].split("\n", 1)
        body = after[1] if len(after) > 1 else ""
        italic = "<i>" in body
        body = re.sub(r"<[^>]+>", "", body)
        lines = [l for l in body.split("\n") if l.strip()]
        if not lines:
            continue
        events.append(dict(start=ts(m.group(1)), end=ts(m.group(2)), style="", lines=lines,
                           align=2, italic=italic, stacked=False))
    return events


def check(events, max_cps=MAX_CPS):
    rows = []
    for i, e in enumerate(events, 1):
        dur = e["end"] - e["start"]
        text = "\n".join(e["lines"])
        n = sum(kchars(l) for l in e["lines"])
        cps = n / dur if dur > 0 else 999
        v = []
        if dur < MIN_DUR - 0.01:   # ASS 는 1/100초 단위라 0.83 을 통과로 본다
            v.append(("G1", f"{dur:.2f}s<0.83s"))
        if dur > MAX_DUR + 1e-3:
            v.append(("G2", f"{dur:.2f}s>7s"))
        if len(e["lines"]) > MAX_LINES:
            v.append(("G3", f"{len(e['lines'])}줄>1줄"))
        if e["align"] not in ALIGN_CENTER:
            v.append(("G4", f"\\an{e['align']}"))
        for l in e["lines"]:
            if kchars(l) > MAX_CPL:
                v.append(("K1", f"{kchars(l):g}자"))
                break
        if cps > max_cps + 1e-6:
            v.append(("K2", f"{cps:.1f}cps"))
        if any(re.search(r"(?<!\.)[.,]$", l.rstrip()) for l in e["lines"]):
            v.append(("K3", "줄끝 .,"))
        if re.search(r"\.{2,}", text):
            v.append(("K4", "점 여러 개 → …"))
        if e["italic"]:
            v.append(("K5", "이탤릭"))
        rows.append(dict(i=i, start=e["start"], end=e["end"], dur=dur, chars=n, cps=cps,
                         text=text, violations=v))
    return rows


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() == ".ass":
        return parse_ass(text)
    return parse_srt_vtt(text)


def summarize(rows):
    codes = {}
    for r in rows:
        for c, _ in r["violations"]:
            codes[c] = codes.get(c, 0) + 1
    bad = sum(1 for r in rows if r["violations"])
    cps = sorted(r["cps"] for r in rows)
    med = cps[len(cps) // 2] if cps else 0
    return dict(events=len(rows), failing=bad, codes=codes, median_cps=round(med, 1),
                max_cpl=max((kchars(l) for r in rows for l in r["text"].split("\n")), default=0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="파일별 요약만")
    ap.add_argument("--kids", action="store_true", help="어린이 콘텐츠(초당 9자)")
    a = ap.parse_args()
    files = []
    for p in map(Path, a.paths):
        if p.is_dir():
            files += sorted(x for x in p.rglob("*") if x.suffix.lower() in (".ass", ".srt", ".vtt"))
        else:
            files.append(p)
    out, any_fail = [], False
    for f in files:
        rows = check(load(f), 9 if a.kids else MAX_CPS)
        s = summarize(rows)
        any_fail |= s["failing"] > 0
        out.append(dict(file=str(f), **s, rows=rows))
        if a.json:
            continue
        codes = " ".join(f"{k}:{v}" for k, v in sorted(s["codes"].items())) or "통과"
        print(f"{f}  자막 {s['events']}장 · 위반 {s['failing']}장 · 중앙 {s['median_cps']}cps · "
              f"최장줄 {s['max_cpl']:g}자  [{codes}]")
        if not a.quiet:
            for r in rows:
                if r["violations"]:
                    vs = ", ".join(f"{c} {d}" for c, d in r["violations"])
                    print(f"  #{r['i']:>3} {r['start']:6.2f}-{r['end']:6.2f}  {r['text']!r}  → {vs}")
    if a.json:
        json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
