# 라마 프리셋 (rama-preset)

이 폴더에서 작업할 때는 **반드시 아래를 먼저 읽어라.** 추측하지 마라.
사용자가 **"라마 프리셋으로 만들어줘"** · **"rama-preset"** · **"라마프리셋 불러와"** 하면 이 문서대로 한다.

드라마 장면을 **짧은 상황 설명 나레**로 잇는 세로 숏폼이다. 대사가 본문이고 나레는 5~9마디뿐이다.
2026-09-18 포레이로(drama-preset) 엔진에서 갈라져 나왔다.

★**drama-preset(`~/volcano_work`, `presets/포레이로`, 완성본 `volcano_work/포레이로/`)과 절대 섞지 않는다.**
  이 프리셋의 작업 폴더는 `~/rama_work`, 엔진은 `presets/라마`, 완성본은 `rama_work/라마/`, 저장소는 `~/rama-preset`.
  포레이로 문서·examples·episode.py 를 여기로 끌어오지 말고, 여기 것을 저기로 보내지도 마라.

## 읽는 순서 — 전부 읽고 시작한다

0. **★`docs/라마-지침서.md`** — 템플릿(§1) · **나레 말투(§2, 사용자 확정)** · 세로 쇼츠 소재(§3) · 로고(§4) · 절차(§5) · 수치(§6)
1. `docs/PLAYBOOK-라마.md` — 실측값과 겪은 함정
2. `docs/벤치-라마의드라마-나레분석-20260918.md` — 말투의 근거. ★벤치의 「~데?」「주어+?」는 **사용자가 뺐다** — 지침서 §2 가 이긴다
3. `examples/sb01_신병4_해병보고/episode.py` — 첫 편 설계도(사용자 확정 대본). 새 편은 이걸 본으로
4. 규격 수치 `presets/라마/spec.py` · 이력 `docs/SESSION-LOG-라마.md`

## 한 줄

★**대사가 본문, 나레는 지금 화면의 상황을 한 문장으로 설명한다.** 물음표로 던지지 않는다(~죠 / ~는데 / ~은). 마지막 한 마디만 반말 촌평.
★**0초는 그 편에서 가장 센 그림.** 줌·팬 없음. 딴 장소 컷을 앞 마디에 끌어오지 않는다.

## 순위 — 무엇을 포기하더라도 위에서부터

| 순위 | 무엇 |
|---|---|
| 1 | **싱크** — `synccheck.py` 로 재서 0.10초 안 |
| 2 | **대사를 자르지 않을 것** |
| 3 | **화면이 이야기와 맞을 것** — `cutsheet.jpg` 눈검사 |
| 4 | 말이 될 것 |
| 5 | 규격 수치 — `build.py` 의 `[라마 규격 위반]` |

## 절차 (지침서 §5)

```powershell
$env:PATH = "$HOME\.volcano\venv\Scripts;$env:PATH"
$P = "presets\라마"; $E = "<편폴더>"
python "$P\prep.py" $E <URL|파일> [시작] [끝]      # 세로 쇼츠면 그림 칸만 오림
python scripts\_asr_sm.py "$E\src.mp4" "$E\asr_ko.json" ko
python scripts\mute_vocals.py $E a-b …             # 남의 나레가 있을 때만
# episode.py 채우기 (말투 §2) · logo.png
python "$P\dlgcheck.py" $E "$E\asr_ko.json" 0      # 0개
python "$P\get_fonts.py" $E; python "$P\tts.py" $E; python "$P\align.py" $E; python "$P\reframe.py" $E
python "$P\build.py" $E                            # 로고까지 얹는다
python "$P\synccheck.py" $E; python "$P\cutsheet.py" $E
```

완성본 `라마/<편>.mp4` + `<편>_업로드.txt` 를 한 벌로 건넨다(제목·설명·`* 작품:`·"더 자세한 내용은 <플랫폼>에서 감상하는 걸 추천합니다!"·해시태그 작품명 하나).

## 최상위 규칙 (사용자가 박은 것)

- **다음 단계가 분명하면 묻지 말고 계속한다.** 소재 선택·업로드·삭제만 묻는다.
- **완성본 하나 + 업로드 세트.** 중간 파일 목록을 늘어놓지 마라.
- **한 번에 한 프리셋만.** 라마 작업 중에 포레이로·3D·크랩의 소재·엔진·자산을 꺼내지 마라.
- **작업이 한 덩이 끝나면 `docs/PLAYBOOK-라마.md` 에 규칙을, `docs/SESSION-LOG-라마.md` 에 이력을 더하고 `~/rama-preset` 에 커밋한다.** (사용자가 "테스트용, 저장하지 마"라고 한 세션은 예외 — 그때는 아무것도 쓰지 않는다.)
- 적어 두는 것만으로는 안 지켜진다 — 새 규칙은 `build.py` 검사로 박아라.
- 남의 채널 편집본이 소재면 **사용 권한을 사용자에게 확인**한다. 불법 스트리밍 파일은 쓰지 않는다.
- API 키·미디어는 커밋하지 않는다.

## 환경

- 전용 파이썬 `~/.volcano/venv/Scripts/python.exe` (포레이로와 공유 — venv 는 채널별이 아니다) · ffmpeg 7+ · demucs 는 **시스템 python** 에.
- API 키 `~/.volcano/keys/{typecast,speechmatics}`. 나레 목소리 "드라마" `uc_6aa8eb42d1b77888a4240797` 1.3배.
- 글꼴 `fonts/`(잘난체 2 · Gmarket Sans Bold · 코코초이툰) · 얼굴 모델 `models/yunet.onnx` · 효과음 `LLJtlSPtAMU/sfx/`.
- 점검: `python bootstrap_라마.py`
