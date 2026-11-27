"""Pasang storyboard (JSON) ke project lalu jalankan verifikasi dalil yang sama dengan pipeline."""
import sys, json, os
sys.path.insert(0, r"I:\AG\air-wudhu"); os.chdir(r"I:\AG\air-wudhu")
import aw_script as S
pid, f = sys.argv[1], sys.argv[2]
pp = os.path.join("projects", pid, "project.json")
P = json.load(open(pp, encoding="utf-8"))
new = json.load(open(f, encoding="utf-8"))
sc = P.get("script") or {}
P["script"] = sc
for k in ("judul_pendek", "judul", "deskripsi"):
    if new.get(k):
        sc[k] = new[k]
sc["hashtag"] = new.get("hashtag") or sc.get("hashtag", [])
sc["sumber"] = [{"title": s.get("title", ""), "url": s.get("url", ""), "domain": s.get("domain", "")} for s in P.get("sources", []) if s.get("use")]
d = S.normalize({"adegan": new["adegan"], "hashtag": sc["hashtag"], "judul_pendek": sc.get("judul_pendek")})
sc["adegan"] = d["adegan"]
S.verify(sc, P)
sc["masalah"] = sum(1 for a in sc["adegan"] if a.get("status") in ("cek", "gagal"))
sc["model"] = "naskah manual dari fakta terverifikasi"
json.dump(P, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
for a in sc["adegan"]:
    print(a["tipe"], a.get("status", "-"), a.get("ref_label", ""), a.get("catatan", ""))
print("masalah:", sc["masalah"], "| kata:", sum(len((a.get('narasi','')+' '+a.get('penjelasan','')).split()) for a in sc['adegan']))
