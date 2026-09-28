# -*- coding: utf-8 -*-
"""담배 같은 작은 물건만 모자이크하는 박스를 만든다 (라마, 2026-09-28 sb34).
사용:
    python scripts/mosaic_track.py <편폴더> [미리보기fps=3]

<편폴더>/mosaic.json (손으로 쓰는 설정) — 그림 칸(body.mkv, 1080x1086) 좌표·완성본 초:
    {"items": [
       {"t0": 0.0, "t1": 1.54, "roi": [0,120,900,560]},              # ROI 안에서 흰 막대(담배)를 찾아 따라간다
       {"t0": 56.47, "t1": 58.1, "roi": [80,150,220,280], "fallback": [120,200,90,160]},
       {"t0": 3.17, "t1": 9.30, "box": [520,640,120,110]}             # 고정 박스
    ]}
결과: <편폴더>/mosaic_boxes.json {프레임번호: [[x,y,w,h], ...]} + _mosaic/preview_*.jpg (빨간 상자)
build.py 가 mosaic_boxes.json 을 보면 body.mkv 를 구운 직후 그 칸만 모자이크한다(presets/라마/mosaic_apply.py).
"""
import json, os, sys
import cv2
import numpy as np

wd = os.path.abspath(sys.argv[1])
pfps = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
cfg = json.load(open(os.path.join(wd, "mosaic.json"), encoding="utf-8"))
PAD = cfg.get("pad", 22)
MIN = cfg.get("min_box", 56)
HOLD = cfg.get("hold_frames", 8)

_clean = os.path.join(wd, "_body_clean.mkv")   # build 가 모자이크 전 그림을 남겨 둔다
cap = cv2.VideoCapture(_clean if os.path.exists(_clean) else os.path.join(wd, "body.mkv"))
fps = cap.get(cv2.CAP_PROP_FPS)
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


def sticks(img, roi):
    x0, y0, w0, h0 = roi
    sub = img[y0:y0 + h0, x0:x0 + w0]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] > cfg.get("v_min", 140)) & (hsv[..., 1] < cfg.get("s_max", 80))).astype(np.uint8) * 255
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    out = []
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if a < 15 or a > 6000:
            continue
        pts = np.column_stack(np.where(lab[y:y + h, x:x + w] == k))[:, ::-1].astype(np.float32)
        (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
        lo, hi = min(rw, rh), max(rw, rh)
        if lo < 1 or hi / lo < 2.5 or hi < 10 or lo > 32 or a / max(1.0, rw * rh) < 0.35:
            continue
        out.append([x0 + x, y0 + y, w, h])
    return out


def pad(b):
    x, y, w, h = b
    cx, cy = x + w / 2, y + h / 2
    w, h = max(MIN, w + 2 * PAD), max(MIN, h + 2 * PAD)
    x, y = int(max(0, cx - w / 2)), int(max(0, cy - h / 2))
    return [x, y, int(min(W - x, w)), int(min(H - y, h))]


def merge(bs):
    bs = [list(b) for b in bs]
    changed = True
    while changed:
        changed = False
        for i in range(len(bs)):
            for j in range(i + 1, len(bs)):
                a, b = bs[i], bs[j]
                if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
                    x, y = min(a[0], b[0]), min(a[1], b[1])
                    bs[i] = [x, y, max(a[0] + a[2], b[0] + b[2]) - x, max(a[1] + a[3], b[1] + b[3]) - y]
                    del bs[j]
                    changed = True
                    break
            if changed:
                break
    return bs


def frame(f):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ok, img = cap.read()
    return img if ok else None


def track(it, f0, f1):
    """seeds=[[초,[x,y,w,h]],...] 사이를 선형 보간하고, 가까운 seed 의 모양으로 ±SR px 안을 템플릿 매칭해 다듬는다."""
    SR = it.get("search", 30)
    seeds = [(int(round(t * fps)), b) for t, b in it["seeds"]]
    tmpl = {}
    for sf, (x, y, w, h) in seeds:
        img = frame(sf)
        m = 8
        tmpl[sf] = img[max(0, y - m):y + h + m, max(0, x - m):x + w + m].copy()
    res = {}
    for f in range(f0, f1):
        prev = [s for s in seeds if s[0] <= f]
        nxt = [s for s in seeds if s[0] >= f]
        a = prev[-1] if prev else nxt[0]
        b = nxt[0] if nxt else prev[-1]
        k = 0 if a[0] == b[0] else (f - a[0]) / (b[0] - a[0])
        box = [a[1][i] + (b[1][i] - a[1][i]) * k for i in range(4)]
        near = a if abs(f - a[0]) <= abs(f - b[0]) else b
        T = tmpl[near[0]]
        img = frame(f)
        x, y, w, h = [int(v) for v in box]
        X0, Y0 = max(0, x - 8 - SR), max(0, y - 8 - SR)
        win = img[Y0:y + h + 8 + SR, X0:x + w + 8 + SR]
        if win.shape[0] > T.shape[0] and win.shape[1] > T.shape[1]:
            r = cv2.matchTemplate(win, T, cv2.TM_CCOEFF_NORMED)
            _, sc, _, loc = cv2.minMaxLoc(r)
            if sc > it.get("min_score", 0.45):
                x, y = X0 + loc[0] + 8, Y0 + loc[1] + 8
        res[f] = [x, y, w, h]
    return res


boxes = {}
for it in cfg["items"]:
    f0, f1 = int(round(it["t0"] * fps)), min(N, int(round(it["t1"] * fps)))
    if "seeds" in it:
        for f, b in track(it, f0, f1).items():
            boxes.setdefault(f, []).append(pad(b))
        continue
    last, miss, first = [], 0, None
    for f in range(f0, f1):
        if "box" in it:
            got = [it["box"]]
        else:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, img = cap.read()
            got = [pad(b) for b in sticks(img, it["roi"])] if ok else []
            if got:
                if first is None:
                    first = f
                    # ★shot 첫머리에서 못 찾은 프레임은 처음 찾은 박스로 채운다(되감기 hold)
                    for g in range(max(f0, f - HOLD), f):
                        boxes.setdefault(g, []).extend(got)
                last, miss = got, 0
            elif last and miss < HOLD:
                got, miss = last, miss + 1
            elif "fallback" in it:
                got = [it["fallback"]]
        if got:
            boxes.setdefault(f, []).extend(got)
boxes = {f: merge(b) for f, b in boxes.items()}
json.dump({"fps": fps, "block": cfg.get("block", 24), "boxes": {str(k): v for k, v in sorted(boxes.items())}},
          open(os.path.join(wd, "mosaic_boxes.json"), "w"))
print(f"모자이크 프레임 {len(boxes)} / {N}")

# 미리보기: 설정 구간마다 pfps 로, 빨간 상자
od = os.path.join(wd, "_mosaic")
os.makedirs(od, exist_ok=True)
tiles = []
for it in cfg["items"]:
    t = it["t0"]
    while t < it["t1"]:
        f = int(round(t * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if ok:
            for x, y, w, h in boxes.get(f, []):
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 4)
            if "roi" in it:
                x, y, w, h = it["roi"]
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 255), 1)
            cv2.putText(img, f"{t:.2f}", (820, 1060), 0, 1.6, (255, 255, 255), 4)
            tiles.append(cv2.resize(img, (360, 362)))
        t += 1.0 / pfps
for i in range(0, len(tiles), 30):
    part = tiles[i:i + 30]
    while len(part) % 5:
        part.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(part[j:j + 5]) for j in range(0, len(part), 5)])
    # ★cv2.imwrite 는 윈도에서 한글 경로에 못 쓴다 → imencode 후 직접 쓴다
    open(os.path.join(od, f"preview_{i // 30 + 1}.jpg"), "wb").write(
        cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes())
print("미리보기:", od)
