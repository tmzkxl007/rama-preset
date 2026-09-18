# -*- coding: utf-8 -*-
"""나레 밑에 깔 컷을 **한 장에 모아 본다.**  사용: python cutsheet.py <편폴더>

왜 필요한가
  나레 컷은 소재 아무 데서나 가져오기 때문에, 그 편 이야기와 상관없는 장면이
  섞여 들어가도 완성본을 처음부터 끝까지 보기 전에는 모른다.
  실제로 ep16 에서 **행정병이 파일을 치켜드는 장면**이 들어가 "때릴 듯이 손 올린다"는
  지적을 받았다. 굽기 전에 이 판을 눈으로 훑어라.

  → <편폴더>/cutsheet.jpg  (컷마다 가운데 프레임 한 장, 마디 번호를 박아 둔다)
"""
import io, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

wd = os.path.abspath(sys.argv[1])
sys.path.insert(0, wd)
import episode
os.chdir(wd)

SRC = episode.SRC
shots = []                      # (마디번호, 소재시각, 라벨)
ni = 0
for b in episode.BLOCKS:
    if b[0] != "N":
        continue
    ni += 1
    for a, z in (b[2] if len(b) > 2 else []):
        shots.append((ni, (a + z) / 2.0, f"n{ni} {a:g}"))
if not shots:
    sys.exit("나레 마디에 컷이 없다")

os.makedirs("_cuts", exist_ok=True)
for i, (n, t, lab) in enumerate(shots):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", SRC,
                    "-frames:v", "1", "-vf",
                    f"scale=320:-1,drawbox=x=0:y=0:w=iw:h=22:color=black@0.6:t=fill",
                    f"_cuts/c{i:03d}.jpg"], check=True)

cols = 6
rows = (len(shots) + cols - 1) // cols
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "_cuts/c%03d.jpg",
                "-filter_complex", f"tile={cols}x{rows}:margin=4:padding=4",
                "-frames:v", "1", "cutsheet.jpg"], check=True)
print(f"  컷 {len(shots)}장 → {os.path.join(wd, 'cutsheet.jpg')}")
print("  ★이 편 이야기와 상관없는 장면(몸싸움·손찌검처럼 보이는 동작 포함)이 없는지 눈으로 훑어라")
for n, t, lab in shots:
    print(f"    {lab}  ({t:.2f}초)")
