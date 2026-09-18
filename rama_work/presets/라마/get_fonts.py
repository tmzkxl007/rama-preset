# -*- coding: utf-8 -*-
"""포레이로가 쓰는 글꼴을 받아 편 폴더의 fonts/ 에 ttf 로 넣는다.
사용: python get_fonts.py <편폴더>

★구글폰트는 옛 User-Agent 로 요청해야 통짜 woff 가 온다(최신 UA 면 유니코드 구간별로 쪼개진다).
★원본 글꼴은 특정하지 못했다(§17-4). 주아체는 원본보다 25% 넓어 spec.FONT_SCALEX 로 좁힌다.
"""
import os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
import spec
from fontTools.ttLib import TTFont

# 윈도우 콘솔은 cp949 라 em-dash 하나에도 죽는다. 출력만 UTF-8 로 돌린다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


wd = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
out = os.path.join(wd, "fonts")
os.makedirs(out, exist_ok=True)
UA_OLD = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/29 Safari/537.36"}


def save(raw, dst):
    tmp = dst + ".web"
    open(tmp, "wb").write(raw)
    f = TTFont(tmp)
    f.flavor = None
    f.save(dst)
    os.remove(tmp)
    return TTFont(dst)["name"].getDebugName(1)


for name, src in spec.FONTS.items():
    dst = os.path.join(out, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 100000:
        print("이미 있음", name)
        continue
    if isinstance(src, str) and src.startswith("local:"):
        import shutil
        srcp = src[6:]
        if not os.path.exists(srcp):
            print("★없다:", srcp, "— 이 글꼴은 사람이 넣어야 한다")
            continue
        shutil.copy2(srcp, dst)
        print("넣음", name, "| family:", TTFont(dst)["name"].getDebugName(1))
        continue
    if isinstance(src, str):
        raw = urllib.request.urlopen(urllib.request.Request(src, headers=UA_OLD), timeout=300).read()
    else:
        _, fam, w = src
        css = urllib.request.urlopen(urllib.request.Request(
            f"https://fonts.googleapis.com/css2?family={fam.replace(' ', '+')}:wght@{w}",
            headers=UA_OLD), timeout=60).read().decode()
        u = re.findall(r"url\((https://[^)]+)\)", css)[0]
        raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA_OLD), timeout=300).read()
    print("넣음", name, "| family:", save(raw, dst))
