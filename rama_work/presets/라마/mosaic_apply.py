# -*- coding: utf-8 -*-
"""body.mkv 의 정해진 칸만 모자이크한다 (build.py 가 mosaic_boxes.json 이 있을 때 부른다).
사용: python mosaic_apply.py <편폴더>
박스는 scripts/mosaic_track.py 가 만든다. 소리는 그대로 복사한다."""
import json, os, subprocess, sys
import cv2

wd = os.path.abspath(sys.argv[1])
cfg = json.load(open(os.path.join(wd, "mosaic_boxes.json"), encoding="utf-8"))
boxes = cfg["boxes"]
BLOCK = int(cfg.get("block", 14))       # 모자이크 한 칸 크기(px)
src = os.path.join(wd, "body.mkv")
tmp = os.path.join(wd, "_body_mosaic.mkv")
cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS)
W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                      "-s", f"{W}x{H}", "-r", f"{fps:.6f}", "-i", "-", "-i", src,
                      "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "15", "-preset", "medium",
                      "-pix_fmt", "yuv420p", "-c:a", "copy", "-f", "matroska", tmp], stdin=subprocess.PIPE)
f = n = 0
while True:
    ok, img = cap.read()
    if not ok:
        break
    for x, y, w, h in boxes.get(str(f), []):
        roi = img[y:y + h, x:x + w]
        if roi.size:
            s = cv2.resize(roi, (max(1, w // BLOCK), max(1, h // BLOCK)), interpolation=cv2.INTER_AREA)
            img[y:y + h, x:x + w] = cv2.resize(s, (w, h), interpolation=cv2.INTER_NEAREST)
            n += 1
    p.stdin.write(img.tobytes())
    f += 1
p.stdin.close()
cap.release()          # ★윈도는 열린 파일을 바꿔치기 못 한다 — 먼저 닫는다
if p.wait() != 0:
    sys.exit("모자이크 굽기 실패")
import shutil
shutil.copy2(src, os.path.join(wd, "_body_clean.mkv"))   # 추적은 모자이크 전 그림으로 해야 한다
os.replace(tmp, src)
print(f"  모자이크: {n}칸 · {f}프레임")
