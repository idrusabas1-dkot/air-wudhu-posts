"""Alat format KISAH air-wudhu untuk batch harian (dipakai skill /dakwah-berita-harian).

  from kisah_tools import *            # tok, shot, K, ilus, PUTIH/HIJAU/BIRU
  verify_and_save(N, save)             # cek kutipan kartu (match_score >= 0.85 ke teks sumber), simpan + approve
  render(jobs, date, folder)           # render ke output/<date>/<folder>/<slug>.mp4 (+ _caption.txt, _meta.json)
"""
import json, sys
sys.path.insert(0, r"I:\AG\air-wudhu")
import aw_common as C, aw_research as R

PUTIH = [236, 236, 228]
HIJAU = [120, 170, 140]
BIRU = [150, 190, 230]


def tok(jenis, aksi, x=250, y=1640, baju=PUTIH, hadap=1):
    return {"jenis": jenis, "x": x, "aksi": aksi, "hadap": hadap, "baju": baju, "y": y}


def shot(latar, kamera="dorong", tokoh=None, fokus=(420, 1300), **kw):
    s = {"latar": latar, "kamera": kamera, "fokus": list(fokus)}
    if tokoh:
        s["tokoh"] = tokoh
    s.update(kw)
    return s


def K(jenis, a, b="", c="", sumber="", pada="", pos=(540, 400), **kw):
    d = {"jenis": jenis, "a": a, "b": b, "pada": pada, "pos": list(pos)}
    if c:
        d["c"] = c
    if sumber:
        d["sumber"] = sumber
    d.update(kw)
    return d


def ilus(pada):
    return K("label", "cerita ilustrasi", "coklat", pada=pada, pos=(190, 560))



def verify_and_save(N, save):
    p = C.load_project(N["pid"])
    have = {s["url"] for s in p["sources"]}
    for u in N.get("extra_urls", []):
        if u not in have:
            R.add_url(p, u)
    bad = 0
    used = {}
    for i, sc in enumerate(N["adegan"], 1):
        for k in sc.get("kartu", []):
            if k["jenis"] not in ("pendapat", "hadits", "kutipan"):
                continue
            dom = k.get("sumber", "")
            cands = [s for s in p["sources"] if s.get("domain", "").endswith(dom) or dom in s.get("url", "")]
            best, bs = 0.0, None
            for s in cands:
                sc_ = R.match_score(k["a"], s["text"])
                if sc_ > best:
                    best, bs = sc_, s
            ok = best >= 0.85
            bad += not ok
            if bs:
                used[bs["url"]] = {"domain": bs["domain"], "url": bs["url"], "title": bs.get("title", "")}
            print(f"  [{i}] {k['jenis']:8} {dom:22} score={best:.2f} {'OK' if ok else 'GAGAL'}")
    words = sum(len(sc["narasi"].split()) for sc in N["adegan"])
    print(f"  kata narasi: {words}, gagal: {bad}")
    if save and not bad:
        script = {k: N[k] for k in ("judul_pendek", "judul", "deskripsi", "hashtag", "adegan")}
        script.update(sumber=list(used.values()), format="kisah", masalah=0,
                      model="manual (format kisah, kutipan diverifikasi match_score)")
        p["script"] = script
        p["approved"] = True
        p["status"] = "naskah"
        C.save_project(p)
        print("  disimpan + approved")
    return bad



def render(jobs, date, folder):
    import os, time
    import aw_render as RD, aw_script as S
    os.chdir(r"I:\AG\air-wudhu")
    cfg = C.load_config()
    out_dir = os.path.join(cfg["output_dir"], date, folder)
    os.makedirs(out_dir, exist_ok=True)
    for pid, slug in jobs:
        p = C.load_project(pid)
        assert p.get("approved"), pid
        final = os.path.join(out_dir, slug + ".mp4")
        print("RENDER", slug, flush=True)
        t = time.time()
        p["status"] = "render"; C.save_project(p)
        dur = RD.render_video(p["script"], cfg, final, lambda *a: print(*a, flush=True))
        sc = p["script"]
        open(os.path.join(out_dir, slug + "_caption.txt"), "w", encoding="utf-8").write(S.caption(sc, cfg))
        meta = {"project": pid, "topik": p["topik"], "duration": round(dur, 2), "judul": sc.get("judul", ""),
                "hook": sc.get("judul_pendek", "").replace("*", ""), "sumber": sc.get("sumber", []),
                "narasi": [x["narasi"] for x in sc["adegan"]]}
        json.dump(meta, open(os.path.join(out_dir, slug + "_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        p["status"] = "selesai"
        p.setdefault("videos", []).append({"path": final, "date": date, "duration": round(dur, 1),
                                           "created": time.strftime("%Y-%m-%d %H:%M:%S")})
        C.save_project(p)
        print(f"SELESAI {slug}: {dur:.1f} dtk video, render {time.time()-t:.0f} dtk", flush=True)
