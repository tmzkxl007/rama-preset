# -*- coding: utf-8 -*-
"""여러 구간을 이어 src.mp4 + asr_ko.json 을 만든다: multi_cut.py <폴더> a0 a1 b0 b1 [c0 c1 …]"""
import json, os, subprocess, sys
F = r'C:\Users\최진영\Downloads\Video\신병4 - 사보타주 제18화 다시보기 - 무료 영화 드라마 예능 다시보기 - 티비착.mp4'
wd = sys.argv[1]
nums = list(map(float, sys.argv[2:]))
segs = list(zip(nums[0::2], nums[1::2]))
os.makedirs(wd, exist_ok=True)
tmp = []
for i, (s, e) in enumerate(segs):
    p = os.path.join(wd, f"_p{i}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s), "-to", str(e), "-i", F,
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", p], check=True)
    tmp.append(p)
lst = os.path.join(wd, "_cat.txt")
open(lst, "w", encoding="utf-8").write("".join(f"file '{os.path.basename(p)}'\n" for p in tmp))
out = os.path.join(wd, "src.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip())
offs, acc = [], 0.0
for p in tmp:
    offs.append(acc); acc += dur(p)
print("조각 시작:", [round(o, 3) for o in offs], "합계", round(dur(out), 3))
src = json.load(open("ep18_scan/asr_ep18.json", encoding="utf-8"))
ws = src["words"] if isinstance(src, dict) and "words" in src else src
ks = "s" if "s" in ws[0] else "start"; ke = "e" if "e" in ws[0] else "end"
out_w = []
for (s, e), off in zip(segs, offs):
    for w in ws:
        a, b = float(w[ks]), float(w[ke])
        if a >= s and b <= e:
            nw = dict(w); nw[ks] = round(a - s + off, 3); nw[ke] = round(b - s + off, 3)
            out_w.append(nw)
res = dict(src)
if isinstance(src, dict) and "words" in src: res["words"] = out_w
else: res = out_w
json.dump(res, open(os.path.join(wd, "asr_ko.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("낱말", len(out_w))
for p in tmp: os.remove(p)
os.remove(lst)
