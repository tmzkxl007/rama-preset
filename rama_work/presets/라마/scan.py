# -*- coding: utf-8 -*-
"""굽지 않고 **물음표·나레 컷 자리**만 한꺼번에 검사한다 (§17-18).

   사용: python presets\라마\scan.py     (volcano_work 에서. 모든 편을 훑는다)
   build.py 가 하는 두 검사와 같은 규칙이다 — 다시 굽지 않고 어디가 틀렸는지만 본다.
"""
import importlib.util, os, re, sys, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DLG_TAIL = 0.34
_Q_HARD = re.compile(r"(습니까|ㅂ니까|십니까|겁니까|나요|가요|까요|을까|ㄹ까|냐)$")
_Q_WORD = re.compile(r"(뭐|뭔|무슨|왜|어디|언제|누구|누가|어떻게|어떤|어때|몇)")
_Q_SOFT = re.compile(r"(나|니|래|데|지)$")
def q(t):
    if not isinstance(t, str): return None
    t=t.strip()
    if not t or t[-1] in "?!.…~": return None
    if _Q_HARD.search(t): return "hard"
    if _Q_WORD.search(t) or _Q_SOFT.search(t): return "soft"
for d in sorted(glob.glob("*ep*/episode.py")):
    wd=os.path.dirname(d)
    sp=importlib.util.spec_from_file_location("ep_"+wd.replace("\\","_"), d)
    m=importlib.util.module_from_spec(sp)
    try: sp.loader.exec_module(m)
    except Exception as e: print(f"{wd}: 못 읽음 {e}"); continue
    if not hasattr(m,"BLOCKS"): continue
    hard=[]; soft=[]; ord_bad=[]
    bl=list(m.BLOCKS); dsp=[]
    for i,b in enumerate(bl):
        if b[0]=="D":
            e1=float(b[2])
            if isinstance(b[3],(list,tuple)) and b[3]: e1=max(e1,max(x[2] for x in b[3])+DLG_TAIL)
            dsp.append((i,float(b[1]),e1))
            for c in b[3]:
                k=q(c[0])
                (hard if k=="hard" else soft if k=="soft" else []).append(c[0])
    for e in getattr(m,"EFFECTS",[]):
        k=q(e[1]); (hard if k=="hard" else soft if k=="soft" else []).append(e[1])
    for i,b in enumerate(bl):
        if b[0]!="N" or len(b)<3 or not b[2]: continue
        pv=[s0 for j,s0,_e in dsp if j<i]; lo=max(pv) if pv else 0.0
        nx=[e for j,_s,e in dsp if j>i]; hi=max(nx) if nx else 1e9
        for k,(a,z) in enumerate(b[2]):
            if i==0 and k==0: continue
            if a<lo-3.0 or z>hi+3.0:
                ord_bad.append(f"{b[1][:10]}:{a:g}~{z:g}(자리 {lo:.1f}~{hi if hi<1e8 else 0:.1f})")
    if hard or ord_bad:
        print(f"\n■ {wd}")
        if hard: print("   물음표 빠짐: " + " / ".join(hard))
        if ord_bad: print(f"   컷 자리 벗어남 {len(ord_bad)}곳: " + " · ".join(ord_bad[:8]))
