# 라마 프리셋 (rama-preset)

드라마 장면을 **짧은 상황 설명 나레**로 잇는 세로 숏폼 제작 프리셋. 대사가 본문이고 나레는 5~9마디.
2026-09-18 포레이로(drama-preset) 엔진에서 갈라져 나왔다 — 화면 템플릿·나레 말투·세로 쇼츠 소재 처리·아래 띠 로고가 다르다.

> 비공개 저장소. **API 키 · 소재 영상 · 완성본은 들어 있지 않다.**
> ★drama-preset(`~/volcano_work`)과 **폴더·채널명·완성본 폴더를 전부 따로** 둔다. 섞지 않는다.

## 다른 PC 에서 쓰기

```powershell
git clone <이 저장소> rama-preset
cd rama-preset
.\설치.bat
```

`설치.bat` 이 Python 3.12 · ffmpeg · 전용 venv(`~/.volcano/venv`, 포레이로와 공유) · 글꼴(잘난체 2 · Gmarket Sans Bold · 코코초이툰)을 깔고,
`rama_work` 를 `%USERPROFILE%\rama_work` 에 놓은 뒤 API 키(typecast · speechmatics)를 묻고 점검표를 찍는다.
남의 채널 나레를 지우는 `scripts/mute_vocals.py` 는 **시스템 python 의 demucs** 를 쓴다(`pip install demucs`).
그다음 Claude Code 를 `%USERPROFILE%\rama_work` 에서 열고 **「라마프리셋 불러와」**.

## 구성

| 위치 | 무엇 |
|---|---|
| `rama_work/CLAUDE.md` | Claude 가 제일 먼저 읽는 안내 (읽는 순서 · 절차 · 최상위 규칙) |
| `rama_work/docs/라마-지침서.md` | 템플릿 실측 · **나레 말투(사용자 확정)** · 세로 쇼츠 소재 · 로고 · 절차 · 수치 |
| `rama_work/docs/PLAYBOOK-라마.md` | 실측값·함정 |
| `rama_work/docs/벤치-라마의드라마-나레분석-20260918.md` | 말투 근거 — 유튜브 라마의드라마 7편 나레 전문·어미 전수 |
| `rama_work/docs/SESSION-LOG-라마.md` | 작업 이력 |
| `rama_work/presets/라마/` | 엔진 (prep · tts · align · reframe · build(+로고) · 검사기) |
| `rama_work/presets/_engine/base.py` | spec.py 가 물려받는 바탕값 |
| `rama_work/scripts/` | 전사(`_asr_sm.py`) · 남의 나레 지우기(`mute_vocals.py`) |
| `rama_work/fonts/` · `models/` · `LLJtlSPtAMU/sfx/` · `assets/logos/` | 동봉 자산 |
| `rama_work/examples/sb01_신병4_해병보고/` | 첫 편 설계도(사용자 확정 대본) · 업로드 세트 · 로고 |
| `install.ps1` · `설치.bat` · `requirements.txt` | 설치 |

## 고치고 올리기

규칙이나 코드를 고쳤으면 `~/rama_work` 에서 고친 파일을 이 저장소의 `rama_work/` 로 복사해 커밋한다(미디어·키 제외).
