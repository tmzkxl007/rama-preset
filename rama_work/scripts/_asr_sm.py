# -*- coding: utf-8 -*-
"""Speechmatics 배치 전사 → groq(whisper) 와 같은 꼴의 asr.json 으로 저장한다.
사용: python _asr_sm.py <소재> [출력=asr.json] [언어=ko]
groq 키가 없는 PC 의 대체 사다리(전사 2순위)."""
import json, os, subprocess, sys, time, urllib.request, uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "seg.mp4"
OUT = sys.argv[2] if len(sys.argv) > 2 else "asr.json"
LANG = sys.argv[3] if len(sys.argv) > 3 else "ko"
API = "https://asr.api.speechmatics.com/v2"

KEY = (os.environ.get("SPEECHMATICS_API_KEY") or "").strip()
if not KEY:
    KEY = open(os.path.expanduser("~/.volcano/keys/speechmatics"), encoding="utf-8").read().strip()
H = {"Authorization": "Bearer " + KEY}

mp3 = os.path.splitext(OUT)[0] + "_in.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", SRC, "-vn", "-ac", "1", "-ar", "16000",
                "-b:a", "64k", mp3], check=True)

cfg = json.dumps({"type": "transcription",
                  "transcription_config": {"language": LANG, "operating_point": "enhanced",
                                           "diarization": "speaker"}})
b = "----sm" + uuid.uuid4().hex
parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"config\"\r\n\r\n{cfg}\r\n".encode(),
         (f"--{b}\r\nContent-Disposition: form-data; name=\"data_file\"; filename=\"a.mp3\"\r\n"
          f"Content-Type: audio/mpeg\r\n\r\n").encode(),
         open(mp3, "rb").read(), f"\r\n--{b}--\r\n".encode()]
req = urllib.request.Request(API + "/jobs", data=b"".join(parts),
        headers={**H, "Content-Type": "multipart/form-data; boundary=" + b})
try:
    jid = json.loads(urllib.request.urlopen(req, timeout=600).read().decode())["id"]
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code} {e.read().decode('utf-8','replace')[:600]}")
print("job", jid, "…")

for _ in range(600):
    time.sleep(5)
    r = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"{API}/jobs/{jid}", headers=H), timeout=60).read().decode())
    st = r["job"]["status"]
    if st != "running":
        break
    print(".", end="", flush=True)
print("", st)
if st != "done":
    sys.exit("전사 실패: " + json.dumps(r, ensure_ascii=False)[:600])

t = json.loads(urllib.request.urlopen(urllib.request.Request(
    f"{API}/jobs/{jid}/transcript?format=json-v2", headers=H), timeout=120).read().decode())

# json-v2 의 results 를 whisper verbose_json 꼴(segments/words)로 옮긴다
words, segs, cur = [], [], None
for it in t.get("results", []):
    alt = (it.get("alternatives") or [{}])[0]
    w = alt.get("content", "")
    if not w:
        continue
    if it["type"] == "punctuation":
        if cur:
            cur["text"] += w
            cur["end"] = it["end_time"]
        continue
    words.append({"word": w, "start": it["start_time"], "end": it["end_time"]})
    if cur is None or it["start_time"] - cur["end"] > 0.8 or len(cur["text"]) > 45:
        cur = {"start": it["start_time"], "end": it["end_time"], "text": w}
        segs.append(cur)
    else:
        cur["text"] += " " + w
        cur["end"] = it["end_time"]

json.dump({"segments": segs, "words": words}, open(OUT, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"{OUT}  구간 {len(segs)} · 낱말 {len(words)}")
