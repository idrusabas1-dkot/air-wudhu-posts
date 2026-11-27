"""Daftar 20 video terbaru Fanspage Air-Wudhu: SPEC = sudah punya entri thumbnail di thumb_make.SPEC, BARU = belum."""
import os, sys, requests
sys.path.insert(0, r"I:\AG\air-wudhu"); os.chdir(r"I:\AG\air-wudhu")
sys.path.insert(0, r"I:\AG\air-wudhu\_batch")
import aw_common as C, thumb_make as T
fb = C.fb_module()
D = os.path.join("ui","data","fb_accounts","air-wudhu")
tok,_ = fb.resolve_token("1534857413035794", open(os.path.join(D,"token.txt")).read().strip())
r = requests.get("https://graph.facebook.com/v21.0/1534857413035794/videos", params={"access_token":tok,"fields":"id,title,description,created_time,published","limit":20}).json()
for v in r.get("data",[]):
    print(v["id"], v.get("created_time"), "SPEC" if v["id"] in T.SPEC else "BARU", (v.get("title") or v.get("description") or "")[:90].replace("\n"," "))
if "error" in r: print(r)
