"""
Batch topik sensitif/akademis -> video dakwah berbahan SITUS KAJIAN saja.

  python _batch/batch_kajian.py --date 2026-11-19 [--shutdown]

- Riset memakai kata kunci Islami (judul akademis panjang tidak ditemukan mesin pencari); judul asli tetap jadi judul video.
- Hanya sumber dari config trusted_domains yang dipakai (media umum/aktivis dibuang). < 3 sumber kajian -> kata kunci cadangan.
- Dalil terverifikasi dipakai; dalil tak terverifikasi DIBUANG (tidak ditayangkan). Tanpa jeda menunggu persetujuan.
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
import time
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "_batch"))
os.chdir(BASE)

import aw_common as C  # noqa: E402
import aw_main as M  # noqa: E402
from batch_tanpa_henti import drop_unverified, log  # noqa: E402

TOPIK = [
    ("Dekonstruksi Konsep 'Aurat' dan Moralitas Seksual di Era Modern: Antara Tekstualitas Kitab Suci dan Realitas Sosial",
     ["batasan aurat laki-laki dan perempuan dalam Islam", "hukum menutup aurat dan dalilnya", "aurat wanita di zaman modern menurut ulama"]),
    ("Seksualitas di Ruang Publik: Mengapa Isu Tubuh dan Hasrat Selalu Menjadi Medan Perang Paling Sensitif dalam Dogma Agama?",
     ["menjaga pandangan dan kemaluan dalam Islam", "larangan mendekati zina dan adab pergaulan", "syahwat dan pernikahan dalam Islam"]),
]


def kajian_only(p, cfg):
    trusted = [s for s in p.get("sources", []) if s.get("trusted") and s.get("text")]
    for s in p.get("sources", []):
        s["use"] = bool(s.get("trusted") and s.get("text"))
    return len(trusted)


def one(judul, queries, cfg, date):
    p = C.new_project(judul, "")
    log(f"\n==================== {judul}\n📁 {p['id']}")
    pool = []
    for q in queries:
        p["topik"], p["sudut"] = q, ""
        p["sources"] = []
        try:
            M.cmd_research(p, cfg)
        except Exception as e:                                           # noqa: BLE001
            log(f"   ⚠️ riset '{q}' gagal: {str(e)[:200]}")
        seen = {s.get("url") for s in pool}
        pool += [s for s in p.get("sources", []) if s.get("trusted") and s.get("text") and s.get("url") not in seen]
        log(f"   📚 sumber kajian terkumpul: {len(pool)} ({', '.join(sorted({s.get('domain', '') for s in pool}))})")
        if len(pool) >= 4:
            break
    if len(pool) < 2:
        raise RuntimeError(f"hanya {len(pool)} sumber kajian ditemukan — video tidak dibuat")
    for s in pool:
        s["use"] = True
    p["sources"] = pool[: int(cfg.get("sources_max", 7))]
    p["topik"] = judul                                                   # judul asli untuk pembuka & caption
    p["sudut"] = "jelaskan menurut Islam dari sumber kajian; " + queries[0]
    C.save_project(p)
    c = dict(cfg)
    c.update({"min_sources": min(int(cfg.get("min_sources", 4)), len(p["sources"]))})
    try:
        M.cmd_script(p, c)
    except Exception as e:                                               # noqa: BLE001
        log(f"   🔁 naskah gagal ({str(e)[:200]}) → ambang longgar")
        c.update({"min_sources": 2, "min_facts": 3, "min_word_ratio": 0.5})
        M.cmd_script(p, c)
    drop_unverified(p)
    p["approved"] = True
    C.save_project(p)
    M.cmd_render(p, cfg, date)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--shutdown", action="store_true")
    a = ap.parse_args()
    cfg = C.load_config()
    cfg["style"] = C.style_of(cfg)
    t0 = time.time()
    ok, bad = [], []
    for judul, qs in TOPIK:
        try:
            p = one(judul, qs, cfg, a.date)
            ok.append((judul, p["videos"][-1]["path"]))
        except Exception as e:                                           # noqa: BLE001
            traceback.print_exc()
            bad.append((judul, str(e)[:300]))
    log(f"\n==================== SELESAI dalam {(time.time() - t0) / 60:.0f} menit")
    for t, path in ok:
        log(f"✅ {path}  <- {t}")
    for t, e in bad:
        log(f"❌ {t}: {e}")
    if a.shutdown:
        log("⏻ Laptop dimatikan dalam 2 menit (batalkan dengan: shutdown /a)")
        subprocess.run(["shutdown", "/s", "/t", "120", "/c", "Air Wudhu: batch video selesai"], check=False)


if __name__ == "__main__":
    main()
