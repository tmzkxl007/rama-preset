# -*- coding: utf-8 -*-
"""라마 프리셋 — 드라마 장면을 짧은 상황 설명 나레로 잇는 세로 숏폼 (2026-09-18 갈라냄).

포레이로(drama-preset) 엔진에서 갈라져 나왔다. 다른 것 세 가지:
  ① 화면 템플릿 = 유튜브 쇼츠 GMDwCzB1mBI(엘플릭스) 실측 — 제목 흰/빨강 잘난체, 그림 1080x1086 정사각, 자막 한 자리(y1393), 아래 띠는 작품 로고 이미지
  ② 나레 말투 = 라마의드라마 7편(docs/벤치-라마의드라마-나레분석-20260918.md) + 사용자 확정(docs/라마-지침서.md §2): 상황 설명 한 문장, 물음표 없음
  ③ 세로 쇼츠 편집본 소재 처리 — 그림 칸만 오리고(prep.py) 남의 나레 음성은 demucs 로 지운다(scripts/mute_vocals.py)
★drama-preset(~/volcano_work · presets/포레이로)과 폴더·채널명·완성본 폴더를 전부 따로 둔다. 섞지 마라.
"""
from base import *   # noqa: F401,F403

CHANNEL = "라마"
LANGUAGE = "ko"

# ── 화면 (10편 전부 동일. 흔들림 없음) ──────────────────
CANVAS = (1080, 1920)
PIC = (1080, 1086)          # ★라마 템플릿(GMDwCzB1mBI 실측 y416~1501): 거의 정사각 0.995:1. 포레이로는 1080x1014
VID_Y = 416                 # 소재 위쪽 y  (윗 검은 띠 = 0~415)
BOTTOM_BAND = 418           # 아래 검은 띠 1502~1919 — 작품 로고(episode.LOGO)가 놓인다

# ── 아래 띠의 작품명 (토메이로 실측) ───────────────────
#   xSHSX1XDZB0("캐셔로") 실측: 흰색 · 글자높이 64 · 중심 y1563 · 가운데 정렬
#   episode.py 의 WORK 를 그대로 찍는다. 출처를 밝히는 자리다.
#   ★2026-09-15 사용자 템플릿 변경(20260915_160801.png · 헌트 클립형): 아래 띠에 두 줄 —
#     1행 「-작품명-」 · 2행 「풀영상은 <플랫폼>에서」(episode.PLATFORM, 없으면 1행만). 연회색 고딕.
CREDIT_Y = 1490             # 1행 잉크 세로 중앙  (예전 한 줄 템플릿: 1563)
CREDIT2_Y = 1575            # 2행 잉크 세로 중앙
CREDIT_INK = 52             # 글자높이 (예전 64)
CREDIT2_INK = 52
COL_CREDIT = "&H00E6E6E6"   # 연회색 #E6E6E6 (예전 흰색)
CREDIT_OUTLINE = 0          # 검은 띠 위라 테두리가 필요 없다
CREDIT_FMT = ""             # ★라마: 아래 띠에 글자 대신 작품 로고 이미지(episode.LOGO). 글자를 쓰려면 "-{work}-"
CREDIT2_FMT = ""            # (포레이로: "풀영상은 {platform}에서")
# ★아래 띠 로고 — episode.py 의 LOGO = ("logo.png", 높이px, 세로중앙y). 없으면 안 얹는다.
#   실측(GMDwCzB1mBI): 로고 잉크 y1540~1761 · 세로중앙 1650. 기본 높이 240.
LOGO_DEFAULT_H = 240
LOGO_DEFAULT_CY = 1650
FONT_CREDIT = "NanumGothic"   # ttf 안의 family 이름이 띄어쓰기 없다
ZOOM = 0.60                 # 1920x1080 원본에서 가운데 1150x1080 만 쓴다 (1150/1920)

# ── 제목 두 행 ──────────────────────────────────────────
#   1행 = 수식·조건절(살구색) / 2행 = 주어·인물(흰색). 항상 명사구로 끝난다.
#   ★2026-09-15 사용자 템플릿 변경(20260915_160801.png · 헌트 클립형):
#     1행 노랑 글자(검은 바탕) · 2행 흰 글자 + **가로 꽉 찬 빨간 띠** · 굵은 고딕(Black Han Sans).
#     예전 포레이로 값: HEAD_Y (204,315) · INK (95,92) · MAXW 940 · 1행 살구 &H008DB0F7 · 글꼴 코코초이툰
HEAD_Y = (156, 260)         # ★라마 템플릿 실측: 1행 잉크 156~241 · 2행 260~385
HEAD_INK = (85, 125)        # ★2행이 1행보다 크다 (85 / 125)
HEAD_SIZE = (107, 112)      # (안 씀 — fit 이 잰다)
HEAD_MAXW = 1040            # 잉크 폭 상한(좌우 20px 여백). 넘으면 비례로 줄인다
HEAD_OUTLINE = 3            # 잘난체는 획이 굵어 테두리 얇게
HEAD2_BAND = None           # 빨간 띠 안 그린다 (사용자 2026-09-15: "빨간 박스 없애고 글자색 빨간색으로")
COL_HEAD1 = "&H00FFFFFF"    # ★라마: 1행 흰색
COL_HEAD2 = "&H000201F7"    # ★라마: 2행 빨강 #F70102 (실측 BGR 2,1,247)

# ── 자막 — ★나레와 대사는 색·행수·덩이 길이로 갈린다 (2026-09-05 재실측, §17-4 정정)
#   처음에 "둘 다 흰색"이라고 적었던 것은 틀렸다. 색이 바로 가르는 방법이었다.
CAP_Y = 1228                # 원본은 나레·대사가 같은 높이(1228/1230)에 온다
NARR_CAP_Y = 1393           # ★라마: 나레·대사 한 자리(실측 자막 잉크 1364~1422, 세로중앙 1393). 동시에 뜨지 않으니 겹치지 않는다
DLG_CAP_Y = 1393

# 나레이션 자막 — 살구색, 1행, 짧은 덩이가 계속 바뀐다
COL_NARR = "&H00B2D2FF"     # 살구 #FFD2B2 (실측 #FFCCAF~#FFD6B4)
# ★사용자는 캡컷 글자크기로 말한다. 캡컷 14 ≈ 잉크 78px (원본 포레이로 대사 실측 79 와 같다).
#   환산: 잉크px ≈ 캡컷크기 × 5.6
NARR_INK = 60               # ★라마: 실측 잉크 59 (캡컷 약 10.5). 포레이로 73
NARR_CHUNK = (4, 8)         # ★한 덩이 글자수. 원본 잉크폭 중앙값 699 에 맞추려면 8자까지다
NARR_LINES = 1              # 나레는 절대 2행으로 만들지 않는다

# 원본 대사 자막 — 순백, 1~2행, 발화 전체
COL_DLG = "&H00FFFFFF"      # 흰색 #FFFFFF
DLG_INK = 60                # ★라마: 실측 59. 포레이로 78
WRAP_DLG = 11               # (안 씀 — 대사도 덩이로 자른다)
DLG_CHUNK = (5, 10)         # ★대사 한 덩이 글자수. | 로 직접 자르는 게 우선이다
DLG_LINES = 2

COL_OUTLINE = "&H00000000"  # 순검정
OUTLINE_PX = 5              # ★라마: 얇은 테두리 (포레이로 12)
CAP_MAXW = 1010             # 실측 최대 폭 1044
CAP_MAXLINES = 2

# ── 글자 애니메이션 ─────────────────────────────────────
# ★원본 실측(QHQQUUvabTI, 프레임 단위): 글자가 **작게 나타나 커진다.**
#   '두번째 여자가' 등장: 폭 208 -> 352 -> 398 -> 423 -> 434 (48% -> 100%, 4프레임 133ms)
#   밝기는 152 -> 229 -> 255 (2프레임 67ms). 가로세로 비율이 유지되니 가운데서 확대다.
FADE_MS = "70,60"           # 나타나고 사라지는 시간
POP_START = 52              # ★이 배율(%)로 시작해 100% 로 커진다 (0 이면 안 씀)
POP_MS = 125

# ── 효과자막 (분홍) ─────────────────────────────────────
#   감탄·비명·의성어·결정적 대사에만. 편당 2~5개(분당 4~7).
EFF_INK = 56                # 캡컷 10 — 자막보다 작게
EFF_SIZE = 82
COL_EFF = "&H00D891FD"      # 분홍 #FD91D8
EFF_POS = {                 # ★자막을 가리지 않게 인물 옆·위로 비켜 놓는다
    "left":   (300, 700),
    "right":  (790, 700),
    "upper":  (540, 560),
    "lowleft":  (300, 1050),
    "lowright": (790, 1050),
}
EFF_COUNT = (2, 5)          # 편당 개수

# ── 장면 전환 효과음 ────────────────────────────────────
#   그림이 확 바뀌는 자리에 '휙' 을 깐다. 컷마다 다 깔면 시끄럽다.
#   ★'마디가 바뀔 때' 같은 어림으로 깔면 화면이 안 바뀌는 데도 들어가 남발이 된다.
#     이음매마다 **앞뒤 프레임을 실제로 비교**해서 정말 확 바뀌는 곳에만 깐다.
SFX_WHOOSH = "whoosh"       # LLJtlSPtAMU/sfx 에서 가져다 쓴다
OPEN_SFX = ("dudung.wav", -4)   # ★앞머리 0초에 「두둥 북소리」(사용자 2026-09-15, 두둥픽에서 가져옴). None 이면 안 깐다
SFX_DB = -16                # 나레 밑으로 깔리게
SFX_MIN_GAP = 2.5           # 이 간격보다 촘촘하면 건너뛴다
SFX_MAX = 6                 # 한 편에 이만큼까지만
#   기준은 그 편 안에서 상대로 잡는다 — 밤 장면은 화면 차이가 작아 절대값으로는 안 걸린다.
SFX_PCT = 78                # 이음매 차이 상위 (100-이 값)% 만
SFX_DIFF_MIN = 12           # 그래도 이보다 작으면 안 깐다 (거의 안 바뀐 이음매)

# ── 글꼴 ────────────────────────────────────────────────
# ★사용자 지시: 대사 = 그리운 코코초이툰 · 나레 = 도현체
#   (산돌 네모니2 는 유료 산돌구름 글꼴이라 못 넣는다 — 사용자가 코코초이툰으로 바꿨다)
# ★템플릿 크기 고정 (2026-09-19 사용자 "템플릿 크기 좀 고정해봐, 유튜브에 올리면 다 제각각이야")
#   글자 크기는 문구마다 잉크높이로 다시 재지 않고 **아래 값으로 못 박는다.** 폭이 넘치면 줄이지 않고 [규격 위반] — 문구를 줄여라.
#   그림은 reframe 이 얼굴을 키우려고 크롭을 좁히지 않는다(REFRAME_ZOOM=False) — 옆으로 옮기기만. 컷마다 배율이 달라 보이던 것을 없앤다.
FIXED_SIZES = dict(H1=105, H2=156, NARR=78, DLG=78, EFF=74, CREDIT=59, CREDIT2=59)
REFRAME_ZOOM = False
FONT_HEAD = "Jalnan 2 TTF"              # ★라마: 여기어때 잘난체 2 (fonts/Jalnan2TTF.ttf 동봉). 참고 영상 제목 글꼴과 같은 계열
FONT_NARR = "Gmarket Sans Bold"         # ★라마: 나레·대사 둘 다 Gmarket Sans Bold (fonts/GmarketSansBold.ttf 동봉, family 이름을 넣어 둔 판)
FONT_DLG = "Gmarket Sans Bold"
FONT_SCALEX = 100                       # 글꼴이 바뀌었으니 좁히지 않는다
def _griun():
    """그리운 코코초이툰 위치 — 사용자 글꼴 폴더 → 윈도 글꼴 폴더 → 저장소 fonts/ 순서로 찾는다.
    ★PC 마다 사용자 이름이 달라 경로를 박아 두면 다른 컴에서 글꼴을 못 찾는다(이식팩 2026-09-15)."""
    name = "Griun_Cocochoitoon-Rg.ttf"
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cands = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", name),
             os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", name),
             os.path.join(root, "fonts", name)]
    return next((p for p in cands if os.path.exists(p)), cands[0]).replace("\\", "/")


def _bundled(name):
    """저장소 fonts/ 에 동봉한 글꼴 (rama_work/fonts/<name>)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "fonts", name).replace("\\", "/")


FONTS = {
    "Jalnan2.ttf": "local:" + _bundled("Jalnan2TTF.ttf"),
    "GmarketSansBold.ttf": "local:" + _bundled("GmarketSansBold.ttf"),
    "Jua.ttf": ("googlefonts", "Jua", "400"),
    "BlackHanSans.ttf": ("googlefonts", "Black Han Sans", "400"),
    "NanumGothic.ttf": ("googlefonts", "Nanum Gothic", "700"),
    "BMDoHyeon.ttf":
        "https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/BMDOHYEON.woff",
    "GriunCocochoitoon.ttf":
        "local:" + _griun(),
}

# ── 편 규격 ─────────────────────────────────────────────
LEN_RANGE = (31, 44)        # 완성 길이(초). 실측 31.3~44.4, 중앙 40
NARR_CHARS = (130, 380)     # ★나레이션 총 글자수. 상위 6편 실측 130·171·172·173·216·372
# ★문체 갈래 — episode.py 에 STYLE = "tome" 이라 적으면 토메이로 쪽 규격으로 잰다.
#   forey : 나레가 주인(65%+), 마지막을 연결어미로 **끊는다**. 긴 나레.
#   tome  : 대사가 본문, 나레는 짧은 이음새(3~12자). 마지막을 존댓말로 **맺는다**.
#           토메이로 8편(230만~692만) 실측. 뭉클하게 닫을 편은 이쪽이 낫다.
STYLE = "tome"              # ★2026-09-15 사용자 확정: 대사를 살리고 말틈에 짧은 나레. 예전 기본은 "forey"
NARR_SHARE = 0.65           # forey 기준. tome 이면 아래 값으로 바뀐다
#   토메이로 8편 실측: 길이 43~59초 · 대사가 잦다 · 나레는 짧은 이음새
#   ★라마 실측(라마의드라마 7편 · docs/벤치-라마의드라마-나레분석-20260918.md): 나레 6~9문장 73~163자,
#     글자 비중 30~45%, 길이 49~56초. 가장 터진 편(1,182만)이 나레가 제일 적다(73자). 대사가 본문이다.
#   ★2026-09-19 사용자 확정(sb02b 샘플 "좋아 아주 좋아"): **나레 목표 20%**, 대사를 더 들리게. 나레 3~5마디 40~110자.
TOME = dict(NARR_SHARE=0.15, NARR_CHARS=(40, 110), NARR_BEATS=(3, 6),
            LEN_RANGE=(40, 60), DLG_MARKS=(4, 14), CUTS_PER_MIN=(12, 55),
            END_OPEN=False)  # END_OPEN=False = 마지막을 맺어도 된다
DLG_MARKS = (2, 6)          # 원본 대사가 끼어드는 횟수
NARR_CPS = (6.0, 9.0)       # ★라마: 벤치 6~8자/초 · "드라마" 보이스 1.3배가 6.6~7.2
NARR_BEATS = (8, 15)        # 나레 마디 개수. ★사용자 지시로 하한을 8 로 낮췄다(나레를 줄인다)
NARR_BEAT_SECS = (1.5, 4.0)  # 한 마디 길이. ★라마: 촌평(6~10자·1.6초)이 있어 하한 1.5
NARR_SECS = NARR_BEAT_SECS   # 바탕값 이름도 맞춰 둔다

# ── 컷 ──────────────────────────────────────────────────
CUTS_PER_MIN = (38, 47)     # 실측 38.3~47.3
CUT_AVG = (1.23, 1.49)
CUT_OPEN = 4                # ★라마: 첫 5초 3컷 이상이면 된다(0초 얼굴 → 무리 → 대사). 딴 장소 컷을 끌어와 채우지 마라(PLAYBOOK R-3)
CUT_OPEN_LEN = (0.3, 1.0)   # 오프닝 컷 길이
CUT_BODY_LEN = (1.0, 3.0)   # 본문 컷 길이
MAX_STRETCH = 1.8           # ★컷이 모자라면 이 배까지 느리게 늘려 채운다 (되풀이 금지)
PAN = False                 # ★줌·팬을 넣지 않는다. 초당 배율변화 중앙값 0.000~0.005 (§17-5)

# ── 소리 ────────────────────────────────────────────────
MASTER_LUFS = -11.5         # 실측 -11.0~-12.8 (상위편). base 의 -14 보다 크다
MASTER_TP = -0.5
SILENCE_MAX = 0.0           # ★무음(-45dB 이하) 0%. 소리가 끊기는 구간을 만들지 마라
DUCK_DB = -13               # (지금은 안 쓴다 — MUTE_UNDER_NARR 참고)
MUTE_UNDER_NARR = True      # ★나레가 말하는 동안만 원음을 끈다 (사용자 지시)
NARR_BED_DB = -12           #   (블록 전체를 끄므로 거의 안 들린다)
MUTE_RAMP = 0.07            #   ★끄고 켤 때 이만큼 걸쳐 밀어야 '틱' 소리가 안 난다
NARR_PAD = 0.10             # ★나레를 타이트하게 붙인다 (바탕값 0.35)
END_TAIL = 0.45             # ★마지막 말이 끝나고 이만큼만 두고 끝낸다 (안 그러면 질질 끈다)
#   ★음수다: 나레 블록이 **시작되기 전에** 이미 다 꺼져 있어야 한다.
#     0 이상이면 나레 첫 몇 프레임에 다음 컷 소리가 터져 나온다(사용자 지적: '대사 찔끔').
#   ★대사 블록은 마지막 단어 뒤에 DLG_TAIL 만큼 여유를 둔다. 그래야 아래 램프가
#     말이 아니라 침묵만 깎는다(안 그러면 '뒤지는 거야' 끝이 잘린다).
# ★★절대 규칙: 대사는 절대 잘리지 않는다.
#   대사가 끝까지 나오고 → 그다음에 나레가 붙는다. 오디오가 잠깐 비는 건 참아도
#   대사가 잘리는 건 안 된다(사용자가 못 박음).
#   그래서 이 값은 build.py 가 **자동으로 끌어올린다** —
#   최소 |MUTE_LEAD| + MUTE_RAMP + 여유 만큼은 반드시 확보한다.
DLG_TAIL = 0.34
MUTE_LEAD = -0.09
#   완전히 0 으로 떨어뜨리면 마디 사이가 디지털 무음이 되어 '뚝 끊겼다'는 느낌이 난다.
#   이 정도로만 낮춘다 — 나레(-16 LUFS) 밑에서 30dB 아래라 대사가 들리지 않는다.
MUTE_FLOOR = 0.055          # -25dB (완전 무음이 안 생기게)
                            #   (실측 포레이로의 소리 바닥은 -20~-25dB — 원음이 끝까지 깔려 있다)
LRA_MAX = 10                # 다이내믹을 좁게. 대사 위주로 가면 16까지 벌어지고 조회수가 죽는다
# ★원음 바닥 들어올리기. 밤 장면처럼 조용한 소재는 덕킹 전에 이미 -45dB 아래로 떨어진다
#   (실측: 신병4 야간 시퀀스는 손도 대기 전에 35~42%가 무음이었다).
#   포레이로는 BGM 을 깔아 0% 를 만드는데, BGM 이 없으면 이걸로 바닥을 올린다.
#   컷마다 걸면 컷 사이 레벨이 튄다 — 반드시 이어 붙인 뒤 통째로 건다.
BED_LIFT = "dynaudnorm=f=250:g=15:p=0.55:m=8:s=10"

# ── 나레이션 목소리 ─────────────────────────────────────
TTS_LANG = "KOR"
# ★목소리는 타입캐스트 **세희(SeHee)** · 1.2배속 — 사용자가 지목했고 원본과 대조해 확인했다.
#   원본(토메이로) 실측: F0 225Hz · 14자 1.76초(초당 7.9자)
#   SeHee 1.2배:        F0 246Hz · 14자 1.88초(초당 7.5자)  ← 거의 같다
TTS_VOICE = "uc_6aa8eb42d1b77888a4240797"   # ★사용자 커스텀 보이스 "드라마"(2026-09-15 확정). 세희는 tc_611c3f692fac944dff493a04
TTS_TEMPO = 1.3             # ★"드라마" 보이스 기준(2026-09-15 확정). 세희는 1.2


# ── 크롭 ────────────────────────────────────────────────
# ★base.crop_filter 를 그대로 쓰면 안 된다. 그 함수는 base 의 PIC·ZOOM 을 물고 있어서
#   여기서 값을 덮어써도 반영되지 않는다(딸기우유 878 이 나온다). 그래서 다시 정의한다.
def crop_filter(src_w, src_h, hardsub_top=None):
    """16:9 원본의 좌우를 잘라 1080x1014(1.065:1) 를 만든다. -> (필터문자열, (w,h,x,y))"""
    cw = int(round(src_w * ZOOM / 2) * 2)
    ch = int(round(cw * PIC[1] / PIC[0] / 2) * 2)
    limit = hardsub_top if hardsub_top else src_h
    if ch > limit:                       # 하드섭 띠 위쪽만으로는 모자라면 폭을 줄여 맞춘다
        ch = int(limit / 2) * 2
        cw = int(round(ch * PIC[0] / PIC[1] / 2) * 2)
    cw = min(cw, int(src_w / 2) * 2)
    x = (src_w - cw) // 2
    y = max(0, (limit - ch) // 2)
    return (f"crop={cw}:{ch}:{x}:{y},scale={PIC[0]}:{PIC[1]},setsar=1", (cw, ch, x, y))

# ★야간 장면 걷어올리기 — episode.py 의 LIFT(0~100) 로 켠다.
#   드라마 야간 씬은 그대로 쓰면 0초 프레임이 죽어서 안 눌린다.
#   그렇다고 brightness 만 올리면 화면이 뿌옇게 뜬다. **감마로 어두운 쪽만** 올린다.
def nightlift(v):
    if not v:
        return ""
    a = float(v) / 100.0
    return (f",eq=gamma={1 + 0.95 * a:.3f}:gamma_weight={1 - 0.35 * a:.3f}"
            f":brightness={0.030 * a:.4f}:contrast={1 + 0.12 * a:.3f}"
            f":saturation={1 + 0.15 * a:.3f}")
