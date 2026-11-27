"""
Batch tanpa henti: riset -> naskah -> (dalil) -> render untuk beberapa topik, lalu (opsional) matikan laptop.

  python _batch/batch_tanpa_henti.py --date 2026-11-19 --shutdown

Dalil:
  - dalil yang LOLOS verifikasi (status ok) -> otomatis disetujui & tampil.
  - dalil yang TIDAK lolos (cek/gagal: ayat tak disebut di bahan, hadits tak ditemukan di sumber) -> adegannya DIBUANG otomatis
    (bukan disetujui), supaya tidak ada kutipan agama yang tak terverifikasi tayang ke publik. Tidak ada jeda menunggu persetujuan.
Gagal riset/naskah -> diulang dengan ambang longgar; tetap gagal -> topik dilewati, lanjut berikutnya.
"""
import argparse
import copy
import datetime as dt
import os
import subprocess
import sys
import time
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import aw_common as C  # noqa: E402
import aw_main as M  # noqa: E402

TOPIK = [
    ("Tubuh Siapa yang Diatur? Batas Antara Hak Otonomi Tubuh dan Kedaulatan Doktrin Agama",
     "tubuh amanah dari Allah dalam Islam, batas hak atas tubuh sendiri, larangan merusak diri, hukum menjaga tubuh"),
    ("Dekonstruksi Konsep 'Aurat' dan Moralitas Seksual di Era Modern: Antara Tekstualitas Kitab Suci dan Realitas Sosial",
     "pengertian aurat dalam Islam, batas aurat laki-laki dan perempuan, dalil menutup aurat, aurat di zaman modern"),
    ("Seksualitas di Ruang Publik: Mengapa Isu Tubuh dan Hasrat Selalu Menjadi Medan Perang Paling Sensitif dalam Dogma Agama?",
     "menjaga pandangan dan kemaluan dalam Islam, syahwat dan pernikahan, adab di ruang publik, larangan mendekati zina"),
]


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)


def drop_unverified(p):
    sc = p["script"]
    before = len(sc["adegan"])
    dropped = [a.get("ref_label") or a.get("ref") or a["tipe"] for a in sc["adegan"]
               if a.get("tipe") in ("quran", "hadits") and a.get("status") != "ok"]
    sc["adegan"] = [a for a in sc["adegan"] if a.get("tipe") not in ("quran", "hadits") or a.get("status") == "ok"]
    sc["masalah"] = 0
    if dropped:
        log(f"   🧹 {len(dropped)} dalil tidak terverifikasi dibuang (tidak ditayangkan): {', '.join(map(str, dropped))}")
    log(f"   ✓ dalil terverifikasi dipakai: {sum(1 for a in sc['adegan'] if a.get('tipe') in ('quran', 'hadits'))}"
        f" · adegan {before} -> {len(sc['adegan'])}")


def one(topik, sudut, cfg, date):
    p = C.new_project(topik, sudut)
    log(f"\n==================== {topik}\n📁 {p['id']}")
    for attempt, relax in enumerate((None, {"min_sources": 2, "min_facts": 3, "min_word_ratio": 0.5}), 1):
        c = copy.deepcopy(cfg)
        if relax:
            c.update(relax)
            log(f"   🔁 percobaan {attempt} dengan ambang longgar {relax}")
        try:
            if attempt == 1 or not p.get("sources"):
                M.cmd_research(p, c)
            M.cmd_script(p, c)
            break
        except Exception as e:                                           # noqa: BLE001 -- jangan berhenti
            log(f"   ⚠️ gagal: {str(e)[:300]}")
            if attempt == 2:
                raise
    drop_unverified(p)
    p["approved"] = True
    C.save_project(p)
    M.cmd_render(p, cfg, date)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--shutdown", action="store_true")
    ap.add_argument("--rerender", nargs="*", default=[], help="project id yang sudah disetujui -> render ulang dulu")
    ap.add_argument("--skip", type=int, default=0, help="lewati N topik pertama")
    a = ap.parse_args()
    cfg = C.load_config()
    cfg["style"] = C.style_of(cfg)
    t0 = time.time()
    ok, bad = [], []
    for pid in a.rerender:
        try:
            p = C.load_project(pid)
            log(f"\n==================== render ulang {p['topik']}")
            M.cmd_render(p, cfg, a.date)
            ok.append((p["topik"], p["videos"][-1]["path"]))
        except Exception as e:                                           # noqa: BLE001
            traceback.print_exc()
            bad.append((pid, str(e)[:300]))
    for topik, sudut in TOPIK[a.skip:]:
        try:
            p = one(topik, sudut, cfg, a.date)
            ok.append((topik, (p.get("videos") or [{}])[-1].get("path")))
        except Exception as e:                                           # noqa: BLE001
            traceback.print_exc()
            bad.append((topik, str(e)[:300]))
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
