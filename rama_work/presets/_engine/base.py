# -*- coding: utf-8 -*-
"""프리셋 공통 바탕값. 프리셋별 spec.py 가 `from base import *` 로 받아 필요한 것만 덮어쓴다.

사용자가 "이건 고정이야" 라고 못 박은 값들이다(2026-09-05). 함부로 바꾸지 마라.
편마다 다른 것(소재·구간·제목 문구·블록표)은 편 폴더의 `episode.py` 에 있다.
"""
import os

# ── 화면 ────────────────────────────────────────────────
CANVAS      = (1080, 1920)
PIC         = (1080, 878)      # 소재가 놓이는 크기
VID_Y       = 481              # 소재 위쪽 y
ZOOM        = 0.50             # 원본 가로의 몇 할을 보여줄지 (인물 크기를 정한다)
HEAD_Y      = (280, 382)       # 제목 두 행의 위쪽 y
HEAD_SIZE   = (109, 100)       # 제목 두 행 글자크기
CAP_Y       = 1450             # 자막 중앙 y

# ── 글꼴 ────────────────────────────────────────────────
FONT_HEAD   = "BM DoHyeon"                    # 제목·나레
FONT_DLG    = "Ownglyph Dailyokja Regular"    # 대사
DLG_SIZE    = 102
NARR_SIZE   = 88
COL_HEAD1   = "&H00FFFFFF"     # 흰색
COL_HEAD2   = "&H0040CC2E"     # 초록 #2ECC40
COL_DLG     = "&H00FFFFFF"     # 흰색
COL_NARR    = "&H004DE0FF"     # 노랑 #FFE04D
COL_OUTLINE = "&H00101010"
WRAP_DLG    = 11               # 대사 한 줄 최대 글자수
WRAP_NARR   = 12               # 나레 한 줄 최대 글자수

# ── 효과자막 (웃음 표시·속마음 등 짧은 것) ─────────────
EFF_SIZE    = 92
COL_EFF     = "&H008A5CFF"     # 핫핑크 #FF5C8A
EFF_POS     = {                # 소재 화면(y481~1359) 안쪽 자리
    "top":    (540,  580),
    "bottom": (540, 1265),
    "left":   (300,  930),
    "right":  (780,  930),
}
EFF_FADE    = "80,120"         # 나타나고 사라지는 시간(ms)
# 효과자막 색 — EFFECTS 6번째 칸에 이름을 적으면 그 색으로 나온다(안 적으면 COL_EFF)
EFF_COLORS  = {
    "pink":   "&H008A5CFF",   # #FF5C8A
    "blue":   "&H00FFC34F",   # #4FC3FF
    "yellow": "&H004DE0FF",   # #FFE04D
    "green":  "&H0040CC2E",   # #2ECC40 — ★제목 2행이 쓰는 색이다. 효과자막엔 되도록 쓰지 마라
    "orange": "&H001B8CFF",   # #FF8C1B
    "purple": "&H00FF6BC4",   # #C46BFF
    "white":  "&H00FFFFFF",
}

FONTS = {   # 눈누(projectnoonnu) 공식 배포처. 둘 다 상업적 사용·임베딩 허용
    "BMDoHyeon.ttf":
        "https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/BMDOHYEON.woff",
    "OwnglyphDailyokja.ttf":
        "https://cdn.jsdelivr.net/gh/projectnoonnu/2403@1.1/Ownglyph_Dailyokja-Rg.woff2",
}

# ── 나레이션 (Typecast) ─────────────────────────────────
TTS_URL     = "https://api.typecast.ai/v1/text-to-speech"
TTS_VOICE   = "tc_61e748d0fd9fb2d2cacbb04d"   # Yena — 참고 채널 나레와 음높이가 맞는다
TTS_MODEL   = "ssfm-v30"
TTS_EMOTION = ("normal", 1.0)
TTS_LANG    = "KOR"
TTS_TEMPO   = 1.0              # ★보이스를 바꾸면 다시 잡아라. Yena 는 1.0 에서 12자≈2.0초
NARR_LUFS   = -16
NARR_PAD    = 0.35             # 나레 앞뒤 여유
DUCK_DB     = -30              # 나레 구간 원음 (완전 무음 금지 — AAC 가 죽는다)

# ── 보정 (사용자 고정값) ────────────────────────────────
SECTIONS    = [(30, 30), (40, 40), (50, 50)]   # (자동조정, 선명도) — 컷 경계로 3등분
VOICE       = ("달콤한", 50)                    # 음성 보정 — 원음에만, 나레엔 안 건다

# ── 소리 ────────────────────────────────────────────────
MASTER_LUFS = -14
MASTER_TP   = -1.0

# ── 완성본 모으는 곳 ────────────
# 굽고 나면 완성본만 여기로 복사한다. 편 폴더엔 중간물이 남지만 사용자는 여기만 보면 된다.
DELIVER_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")

# ── 편 규격 ─────────────────────────────────────────────
LEN_RANGE   = (30, 45)         # 완성 길이(초)
FIRST_BLOCK = "D"              # ★첫 컷은 반드시 후킹 대사. 나레로 시작하지 않는다
NARR_COUNT  = (2, 3)           # 나레 개수
NARR_SECS   = (1.8, 3.2)       # 나레 한 줄 길이 (목표 2~3초)


# ── 보정 필터 (캡컷 값을 ffmpeg 로 흉내낸 것) ───────────
def grade(auto, sharp):
    a, sh = auto/100.0, sharp/100.0
    return (f"eq=contrast={1+0.30*a:.3f}:saturation={1+0.35*a:.3f}:brightness={0.015*a:.4f},"
            f"unsharp=5:5:{1.2*sh:.3f}:5:5:0")

def voicefx(strength):
    v = strength/100.0
    return (f"highpass=f=80,"
            f"equalizer=f=220:width_type=q:width=1.0:g={2.4*v:.2f},"
            f"equalizer=f=450:width_type=q:width=1.2:g={-1.6*v:.2f},"
            f"equalizer=f=5000:width_type=q:width=1.0:g={4.4*v:.2f},"
            f"acompressor=threshold=-18dB:ratio=2:attack=20:release=250")

def crop_filter(src_w, src_h, hardsub_top=None):
    """인물 크기(ZOOM)와 하드섭 위치로 크롭을 정한다. -> (필터문자열, (w,h,x,y))"""
    cw = int(round(src_w * ZOOM / 2) * 2)
    ch = int(round(cw * PIC[1] / PIC[0] / 2) * 2)
    x  = (src_w - cw) // 2
    limit = hardsub_top if hardsub_top else src_h
    y = max(0, (limit - ch) // 2)
    if y + ch > limit:
        y = max(0, limit - ch)
    return (f"crop={cw}:{ch}:{x}:{y},scale={PIC[0]}:{PIC[1]},setsar=1", (cw, ch, x, y))
