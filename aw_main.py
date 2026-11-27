"""
Engine Air Wudhu — video animasi doodle penjelasan Islam (FB Reels).

  python aw_main.py new --topik "kenapa harus mandi wajib setelah berhubungan" [--sudut "..."]
  python aw_main.py research --project <id>        # cari & baca artikel
  python aw_main.py script   --project <id>        # storyboard via LLM + verifikasi dalil
  python aw_main.py render   --project <id> [--date YYYY-MM-DD] [--force]
  python aw_main.py auto     --topik "..." [--render]   # riset + naskah (+ render bila tidak ada dalil yang perlu dicek)

Render hanya jalan kalau naskah sudah disetujui (UI) kecuali --force.
Hasil: output/<tanggal>/auto_video_N_final.mp4 + _caption.txt + _meta.json (format sama dengan engine lain).
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import traceback

import aw_common as C


def cmd_research(p, cfg):
    import aw_research as R
    R.research(p, cfg)
    C.save_project(p)


def cmd_script(p, cfg):
    import aw_script as S
    p["script"] = S.write_script(p, cfg)
    p["approved"] = False
    p["status"] = "naskah"
    C.save_project(p)
    for i, sc in enumerate(p["script"]["adegan"], 1):
        flag = {"ok": " ✓", "cek": " ⚠️ CEK", "gagal": " ❌"}.get(sc.get("status"), "")
        print(f"   {i}. [{sc['tipe']}]{flag} {sc['narasi'][:90]}")


def cmd_render(p, cfg, date=None, force=False):
    import aw_render as RD
    import aw_script as S
    if not p.get("script"):
        raise SystemExit("❌ Naskah belum ada. Jalankan script dulu.")
    if not p.get("approved") and not force:
        raise SystemExit("❌ Naskah belum disetujui. Setujui di UI (tab Studio → Naskah) atau pakai --force.")
    date = date or dt.date.today().isoformat()
    out_dir = os.path.join(cfg["output_dir"], date)
    os.makedirs(out_dir, exist_ok=True)
    n = C.next_index(out_dir)
    final = os.path.join(out_dir, f"auto_video_{n}_final.mp4")
    print(f"🎬 Render: {p['topik']} -> {final}")
    p["status"] = "render"
    C.save_project(p)
    t = time.time()
    try:
        dur = RD.render_video(p["script"], cfg, final, print)
    except Exception:
        p["status"] = "naskah"
        C.save_project(p)
        raise
    sc = p["script"]
    with open(final.replace("_final.mp4", "_caption.txt"), "w", encoding="utf-8") as f:
        f.write(S.caption(sc, cfg))
    meta = {"project": p["id"], "topik": p["topik"], "duration": round(dur, 2), "judul": sc.get("judul", ""),
            "hook": sc.get("judul_pendek", "").replace("*", ""), "tema": p["topik"],
            "dalil": [x.get("ref_label") for x in sc["adegan"] if x["tipe"] in ("quran", "hadits")],
            "sumber": sc.get("sumber", []), "narasi": [x["narasi"] for x in sc["adegan"]]}
    with open(final.replace("_final.mp4", "_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    p["status"] = "selesai"
    p.setdefault("videos", []).append({"path": final, "date": date, "duration": round(dur, 1),
                                       "created": time.strftime("%Y-%m-%d %H:%M:%S")})
    C.save_project(p)
    print(f"✅ Selesai: {final} ({dur:.1f} detik video, render {time.time() - t:.0f} detik)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "research", "script", "render", "auto"])
    ap.add_argument("--project")
    ap.add_argument("--topik")
    ap.add_argument("--sudut", default="")
    ap.add_argument("--date")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    cfg = C.load_config()
    try:
        if a.cmd in ("new", "auto"):
            if not a.topik:
                raise SystemExit("❌ --topik wajib")
            p = C.new_project(a.topik, a.sudut)
            print(f"📁 Proyek: {p['id']}")
            if a.cmd == "new":
                return
            cmd_research(p, cfg)
            cmd_script(p, cfg)
            if a.render:
                if p["script"].get("masalah"):
                    print(f"⏸️ {p['script']['masalah']} dalil perlu dicek — render ditunda, setujui dulu di UI.")
                    return
                p["approved"] = True
                C.save_project(p)
                cmd_render(p, cfg, a.date)
            return
        if not a.project:
            raise SystemExit("❌ --project wajib")
        p = C.load_project(a.project)
        if a.cmd == "research":
            cmd_research(p, cfg)
        elif a.cmd == "script":
            cmd_script(p, cfg)
        elif a.cmd == "render":
            cmd_render(p, cfg, a.date, a.force)
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
