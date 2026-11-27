import sys, os, json, tempfile, time
sys.path.insert(0, r"I:\AG\air-wudhu"); os.chdir(r"I:\AG\air-wudhu")
import aw_render as R, aw_common as C
cfg = C.load_config() if hasattr(C, "load_config") else json.load(open("config.json", encoding="utf-8"))
P = json.load(open("projects/" + sys.argv[1] + "/project.json", encoding="utf-8"))
w = tempfile.mkdtemp(prefix="awt_")
t0 = time.time()
tl, total = R.plan(P["script"], w, cfg)
print("total", round(total, 1), "tts detik", round(time.time() - t0))
for s, sc in zip(tl, P["script"]["adegan"]):
    print(sc["tipe"], round(s["dur"], 1), len(s["words"]))
import soundfile as sf
