# -*- coding: utf-8 -*-
"""episode.py 의 N 마디 문구로 나레를 합성한다.  사용: python tts.py <편폴더>

★포레이로는 나레 마디가 딸기우유보다 짧고 잦다 — 한 마디 2.5~4.0초, 편당 10~15개.
"""
import io, json, os, subprocess, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_engine"))
sys.path.insert(0, HERE)
import spec

wd = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
sys.path.insert(0, wd)
import episode

# 윈도우 콘솔은 cp949 라 em-dash 하나에도 죽는다. 출력만 UTF-8 로 돌린다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


KEY = (os.environ.get("TYPECAST_API_KEY") or "").strip() or \
      open(os.path.expanduser("~/.volcano/keys/typecast"), encoding="utf-8").read().strip()
nd = os.path.join(wd, "narr")
os.makedirs(nd, exist_ok=True)

texts = [b[1] for b in episode.BLOCKS if b[0] == "N"]
if not texts:
    sys.exit("BLOCKS 에 N 마디가 없다.")
tot = 0.0
for i, t in enumerate(texts, 1):
    spoken = t.replace("|", " ").strip()
    raw = os.path.join(nd, f"n{i}.raw.wav")
    fin = os.path.join(nd, f"n{i}.wav")
    # ★★문구가 바뀌면 반드시 다시 굽는다. "파일이 있으면 건너뛴다"로만 두었다가
    #   나레를 고쳐도 옛 목소리가 그대로 남았다(§17-24). 옆에 문구를 적어 두고 비교한다.
    sig = os.path.join(nd, f"n{i}.txt")
    old = io.open(sig, encoding="utf-8").read() if os.path.exists(sig) else None
    # ★목소리·배속이 바뀌어도 다시 굽는다 — 문구만 보면 보이스를 바꿔도 옛 목소리가 남는다(2026-09-15 승문).
    stamp = f"{spec.TTS_VOICE}|{spec.TTS_TEMPO}|{spoken}"
    stale = old is not None and old != stamp
    if stale:
        print(f"  ★n{i} 문구가 바뀌었다 — 다시 굽는다")
    if stale or not (os.path.exists(raw) and os.path.getsize(raw) > 20000):
        body = {"voice_id": spec.TTS_VOICE, "text": spoken, "model": spec.TTS_MODEL,
                "language": spec.TTS_LANG,
                "prompt": {"emotion_type": "preset", "emotion_preset": spec.TTS_EMOTION[0],
                           "emotion_intensity": spec.TTS_EMOTION[1]},
                "output": {"volume": 100, "audio_pitch": 0,
                           "audio_tempo": spec.TTS_TEMPO, "audio_format": "wav"}}
        req = urllib.request.Request(spec.TTS_URL, data=json.dumps(body).encode("utf-8"),
                                     headers={"X-API-KEY": KEY,
                                              "Content-Type": "application/json",
                                              "User-Agent": "curl/8.0"})
        try:
            open(raw, "wb").write(urllib.request.urlopen(req, timeout=180).read())
        except urllib.error.HTTPError as e:
            sys.exit(f"n{i}: HTTP {e.code} {e.read().decode('utf-8','replace')[:300]}")
    io.open(sig, "w", encoding="utf-8").write(stamp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw,
                    "-af", f"loudnorm=I={spec.NARR_LUFS}:TP=-1.5:LRA=9,aresample=48000",
                    "-ac", "2", "-ar", "48000", fin], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", fin], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
    tot += d + spec.NARR_PAD
    ok = spec.NARR_BEAT_SECS[0] <= d <= spec.NARR_BEAT_SECS[1]
    print(f"  n{i} {d:.2f}초 {'' if ok else '★한 마디 2.5~4.0초 밖 — 문구 길이를 손봐라'}  {spoken}")

chars = sum(len(t.replace('|', '').replace(' ', '')) for t in texts)
print(f"\n  나레 {len(texts)}마디 · {chars}자 · 합계 {tot:.1f}초 (여유 포함)")
print(f"  초당 {chars/max(0.1,tot):.2f}자 — 규격 {spec.NARR_CPS[0]}~{spec.NARR_CPS[1]}")
if not (spec.NARR_CHARS[0] <= chars <= spec.NARR_CHARS[1]):
    print(f"  ★나레 {chars}자 — 규격 {spec.NARR_CHARS[0]}~{spec.NARR_CHARS[1]}자 밖")
