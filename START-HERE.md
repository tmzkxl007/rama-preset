# 라마 프리셋 이식팩 — 다른 PC 에서 쓰는 법

1. 이 저장소를 받는다 → **`설치.bat`** 더블클릭 (Python 3.12 · ffmpeg · venv · 글꼴 · `%USERPROFILE%\rama_work` 복사 · API 키 입력 · 점검).
   다른 위치: `powershell -ExecutionPolicy Bypass -File install.ps1 -Target D:\rama_work`
2. API 키는 팩에 없다 — `~/.volcano/keys/typecast`, `~/.volcano/keys/speechmatics` 에 값만 적는다. (포레이로와 같은 키·같은 venv 를 쓴다)
3. 남의 채널 나레를 지울 일이 있으면 시스템 python 에 `pip install demucs`.
4. Claude Code 를 `rama_work` 폴더에서 열고 **「라마프리셋 불러와」**. Claude 가 `CLAUDE.md` → 지침서 → PLAYBOOK → 벤치 → examples 순으로 읽는다.
5. 소재(쇼츠 URL 또는 파일 + 구간)를 준다. 남의 채널 편집본이면 권한은 사용자가 확인한다.

★drama-preset(`~/volcano_work`)이 같은 PC 에 있어도 된다 — 폴더·프리셋 이름·완성본 폴더가 전부 다르다. 다만 한 작업에 한 프리셋만.
