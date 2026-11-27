"""Ambil daftar video Fanspage Air-Wudhu + frame dari video (ffmpeg seek langsung di URL source)."""
import json, os, subprocess, sys
sys.path.insert(0, r"I:\AG\air-wudhu")
import aw_common as C
fb = C.fb_module()
D = r"I:\AG\air-wudhu\ui\data\fb_accounts\air-wudhu"
PID = "1534857413035794"
OUT = r"I:\AG\air-wudhu\output\thumbnail"
tok, _ = fb.resolve_token(PID, open(D + r"\token.txt").read().strip())
r = fb.graph_get(f"{PID}/videos", tok, {"fields": "id,title,description,length,source,created_time", "limit": 100})
vids = r["data"]
json.dump([{k: v.get(k) for k in ("id", "title", "description", "length", "created_time")} for v in vids],
          open(OUT + r"\videos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for v in vids:
    for f in (0.12, 0.3, 0.5, 0.7):
        dst = os.path.join(OUT, "frames", f"{v['id']}_{int(f*100)}.jpg")
        if os.path.exists(dst):
            continue
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{v['length']*f:.1f}", "-i", v["source"], "-frames:v", "1",
                        "-q:v", "2", dst])
    print(v["id"], "ok", flush=True)
