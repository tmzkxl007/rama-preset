# 라마 엔진 — presets/라마

포레이로 엔진(drama-preset `presets/포레이로`)의 복사본에 아래를 더한 것이다. **절차·원고 규칙은 `docs/라마-지침서.md`** 를 본다.

| 파일 | 하는 일 | 포레이로와 다른 점 |
|---|---|---|
| `spec.py` | 규격 수치 | CHANNEL "라마" · 그림 1080×1086/y416 · 제목 잘난체 흰/빨강(156/260, 잉크 85/125) · 자막 Gmarket Sans Bold 잉크 60 y1393 테두리 5 · CREDIT 글자 없음 · TOME 수치(나레 30%·5~10마디·70~200자·분당 18~55) · NARR_CPS 6~9 |
| `build.py` | 굽기 + 검사 | **로고 오버레이**(episode.LOGO) · **나레 물음표·본문 `~다` 검사** |
| `prep.py` | 소재 놓기 | **세로(H>W) 소재는 그림 칸만 오려 src.mp4** (원본 `_src/raw.mp4`), episode.py 에 ZOOM 1.0 힌트 |
| `episode_template.py` | 편 설계도 뼈대 | LOGO · 말투 주석 |
| 나머지 (tts · align · reframe · dlgcheck · synccheck · cutsheet · scan · fxscan · get_fonts …) | 포레이로와 같다 | |

`../../scripts/mute_vocals.py` — 남의 채널 나레 음성 지우기(demucs).
