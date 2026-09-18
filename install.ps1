param([string]$Target = "$HOME\rama_work")
# 라마 프리셋 이식팩 설치 — ★drama-preset(volcano_work)과 다른 폴더에 놓는다 — Windows PowerShell 5.1
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = Join-Path $Here "rama_work"

function Say($m) { Write-Host "== $m" -ForegroundColor Cyan }
function Has($n) { [bool](Get-Command $n -ErrorAction SilentlyContinue) }
function RefreshPath {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

Say "설치 위치: $Target"

# ── 1. 도구 ────────────────────────────────────────────
Say "ffmpeg"
if (-not (Has ffmpeg)) {
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    RefreshPath
    if (-not (Has ffmpeg)) { Write-Host "  ffmpeg 을 깔았지만 이 창에서는 아직 안 보인다. 창을 새로 열고 설치.bat 을 한 번 더 돌려라." -ForegroundColor Yellow }
} else { Write-Host "  있다" }

Say "전용 파이썬 (~/.volcano/venv)"
$Venv = Join-Path $HOME ".volcano\venv"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    $base = $null
    foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "C:\Program Files\Python312\python.exe")) {
        if (Test-Path $c) { $base = $c; break }
    }
    if (-not $base) {
        winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
        $base = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    }
    if (-not (Test-Path $base)) { throw "Python 3.12 를 찾지 못했다: $base" }
    & $base -m venv $Venv
}
& $Py -m pip install --upgrade pip --quiet
& $Py -m pip install -r (Join-Path $Here "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip 설치 실패" }

# ── 2. 파일 놓기 ───────────────────────────────────────
Say "파일 복사"
New-Item -ItemType Directory -Force $Target | Out-Null
$Preset = Join-Path $Target "presets\라마"
if (Test-Path $Preset) {
    $bak = $Preset + ".bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Move-Item $Preset $bak
    Write-Host "  기존 presets\라마 → $bak"
}
$keep = @("CLAUDE.md", "presets\_engine\base.py")
Get-ChildItem $Src -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($Src.Length + 1)
    $dst = Join-Path $Target $rel
    if ((Test-Path $dst) -and ($keep -contains $rel)) {
        if ($rel -eq "CLAUDE.md") {
            $dst = Join-Path $Target "CLAUDE-라마.md"
            Write-Host "  CLAUDE.md 가 이미 있어 CLAUDE-라마.md 로 둔다 (기존 CLAUDE.md 에서 이 파일을 가리키게 해라)"
        } else { return }
    }
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item $_.FullName $dst -Force
}

# ── 3. 글꼴 ────────────────────────────────────────────
Say "글꼴 (잘난체 2 · Gmarket Sans Bold · 그리운 코코초이툰) — 엔진은 rama_work\fonts 를 직접 읽으니 설치는 보너스"
$userFonts = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"
New-Item -ItemType Directory -Force $userFonts | Out-Null
foreach ($f in @(@("Jalnan2TTF.ttf", "Jalnan 2 TTF (TrueType)"),
                 @("GmarketSansBold.ttf", "Gmarket Sans Bold (TrueType)"),
                 @("Griun_Cocochoitoon-Rg.ttf", "Griun Cocochoitoon Regular (TrueType)"))) {
    $fontDst = Join-Path $userFonts $f[0]
    if (-not (Test-Path $fontDst)) {
        Copy-Item (Join-Path $Src "fonts\$($f[0])") $fontDst
        New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" `
            -Name $f[1] -Value $fontDst -PropertyType String -Force | Out-Null
        Write-Host "  $($f[0]) 설치했다"
    } else { Write-Host "  $($f[0]) 이미 있다" }
}

# ── 4. API 키 ──────────────────────────────────────────
Say "API 키 (~/.volcano/keys) — 비우고 엔터면 건너뛴다"
$Keys = Join-Path $HOME ".volcano\keys"
New-Item -ItemType Directory -Force $Keys | Out-Null
foreach ($k in @(@("typecast", "나레 목소리 · 필수"), @("speechmatics", "대사 전사 · 필수"))) {
    $p = Join-Path $Keys $k[0]
    if (Test-Path $p) { Write-Host "  $($k[0]) 이미 있다"; continue }
    $v = Read-Host "  $($k[0]) 키 ($($k[1]))"
    if ($v -and $v.Trim()) {
        [IO.File]::WriteAllText($p, $v.Trim())     # 값만, BOM·줄바꿈 없이
        Write-Host "  저장했다"
    }
}

# ── 5. 점검 ────────────────────────────────────────────
Say "점검"
& $Py (Join-Path $Target "bootstrap_라마.py")
Write-Host ""
Write-Host "끝. Claude Code 를 $Target 에서 열고 「라마프리셋 불러와」 라고 하면 된다. (남의 나레 지우기용 demucs 는 시스템 python 에 pip install demucs)" -ForegroundColor Green
