# -*- coding: utf-8 -*-
"""이미 접수된 Speechmatics 작업의 결과만 받아 asr.json 꼴로 저장한다.
사용: python scripts/_asr_sm_fetch.py <job_id> <출력.json>
왜 필요한가 — 긴 소재(1시간)는 폴링 중에 502 가 난다. 작업은 서버에서 멀쩡히 돌고 있으므로
다시 올리지 말고 **결과만** 받아 와라(§17-39)."""
import io, json, os, sys, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
API = "https://asr.api.speechmatics.com/v2"
JID = sys.argv[1]; OUT = sys.argv[2] if len(sys.argv) > 2 else "asr.json"
KEY = open(os.path.expanduser("~/.volcano/keys/speechmatics"), encoding="utf-8").read().strip()
H = {"Authorization": "Bearer " + KEY}

def get(url, timeout=180):
    for k in range(8):                      # 502·503 은 잠깐 쉬었다 다시 묻는다
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout).read().decode()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and k < 7:
                time.sleep(10 + 10 * k); continue
            raise
        except Exception:
            if k < 7: time.sleep(10 + 10 * k); continue
            raise

for _ in range(900):
    st = json.loads(get(f"{API}/jobs/{JID}"))["job"]["status"]
    if st != "running":
        break
    print(".", end="", flush=True); time.sleep(20)
print("", st)
if st != "done":
    sys.exit("전사 실패: " + st)

t = json.loads(get(f"{API}/jobs/{JID}/transcript?format=json-v2"))
words, segs, cur = [], [], None
for it in t.get("results", []):
    alt = (it.get("alternatives") or [{}])[0]
    w = alt.get("content", "")
    if not w:
        continue
    if it["type"] == "punctuation":
        if cur:
            cur["text"] += w
            if w in ".?!":
                segs.append(cur); cur = None
        continue
    words.append({"word": w, "start": round(it["start_time"], 2), "end": round(it["end_time"], 2)})
    if cur is None:
        cur = {"start": round(it["start_time"], 2), "end": round(it["end_time"], 2), "text": w}
    else:
        cur["text"] += " " + w; cur["end"] = round(it["end_time"], 2)
if cur: segs.append(cur)
json.dump({"segments": segs, "words": words}, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("→ %s  마디 %d · 낱말 %d · 끝 %.1f초" % (OUT, len(segs), len(words), segs[-1]["end"] if segs else 0))
