# -*- coding: utf-8 -*-
"""라마 프리셋 환경 점검.  사용: python bootstrap_라마.py
   빠진 도구·파이썬 모듈·API 키·동봉 파일을 찍는다. 아무것도 고치지 않는다."""
import importlib, os, shutil, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
ok, bad = [], []


def say(good, msg):
    (ok if good else bad).append(msg)
    print(("  [OK] " if good else "  [!!] ") + msg)


print("== 파이썬 ==")
say(sys.version_info[:2] >= (3, 11), f"{sys.version.split()[0]}  ({sys.executable})")
if ".volcano" not in sys.executable:
    print("  (참고) 전용 venv 가 아닌 파이썬이다 → ~/.volcano/venv/Scripts/python.exe 로 돌려라")

print("== 파이썬 모듈 ==")
for mod, pkg in (("numpy", "numpy"), ("cv2", "opencv-python"), ("fontTools", "fonttools"),
                 ("brotli", "brotli"), ("PIL", "pillow"), ("yt_dlp", "yt-dlp")):
    try:
        importlib.import_module(mod)
        say(True, mod)
    except ImportError:
        say(False, f"{mod} 없다 → pip install {pkg}")
try:
    import cv2
    say(hasattr(cv2, "FaceDetectorYN"), "cv2.FaceDetectorYN (reframe 얼굴 검출)")
except Exception:
    pass

print("== 도구 ==")
for tool in ("ffmpeg", "ffprobe"):
    p = shutil.which(tool)
    say(bool(p), f"{tool}: {p or '없다 → winget install Gyan.FFmpeg'}")
if shutil.which("ffmpeg"):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    say(" ass " in out, "ffmpeg ass 필터 (자막 굽기)")
    ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.split("\n")[0]
    print("  " + ver)

print("== API 키 (~/.volcano/keys/) ==")
for k, what, need in (("typecast", "나레 합성", True), ("speechmatics", "전사", True),
                      ("gemini", "시대극 두 번째 귀", False)):
    p = os.path.expanduser(f"~/.volcano/keys/{k}")
    have = os.path.exists(p) and os.path.getsize(p) > 0
    if have or need:
        say(have, f"{k} ({what}): {'있다' if have else '없다 → 지금 PC 의 같은 파일 내용을 옮겨 적어라'}")
    else:
        print(f"  [--] {k} ({what}): 없다 (선택)")

print("== 동봉 파일 ==")
for rel, what in (("presets/라마/build.py", "엔진"),
                  ("presets/_engine/base.py", "바탕값"),
                  ("scripts/_asr_sm.py", "전사"),
                  ("models/yunet.onnx", "얼굴 모델"),
                  ("LLJtlSPtAMU/sfx/whoosh.wav", "장면전환음"),
                  ("docs/라마-지침서.md", "지침서"),
                  ("scripts/mute_vocals.py", "남의 나레 지우기"),
                  ("fonts/Jalnan2TTF.ttf", "제목 글꼴 잘난체 2"),
                  ("fonts/GmarketSansBold.ttf", "자막 글꼴")):
    say(os.path.exists(os.path.join(ROOT, rel)), f"{rel} ({what})")

print("== 글꼴 ==")
sys.path.insert(0, os.path.join(ROOT, "presets", "_engine"))
sys.path.insert(0, os.path.join(ROOT, "presets", "라마"))
try:
    import spec
    src = spec.FONTS["GriunCocochoitoon.ttf"]
    path = src[6:] if src.startswith("local:") else src
    say(os.path.exists(path), f"그리운 코코초이툰: {path}")
except Exception as e:
    say(False, f"spec.py 를 못 읽었다: {e}")

print("\n== 정리 ==")
print(f"  된 것 {len(ok)}개 · 안 된 것 {len(bad)}개")
for b in bad:
    print("   - " + b)
sys.exit(1 if bad else 0)
