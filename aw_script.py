"""
Storyboard (naskah adegan) dari bahan riset via LLM lokal, lalu VERIFIKASI dalil:
- Ayat: nomor surat:ayat dicek ke equran.id (teks Arab + terjemah Kemenag diambil dari API, bukan dari AI)
         dan dicek apakah rujukan itu memang disebut di bahan.
- Hadits: kutipan harus ditemukan (hampir persis) di teks bahan; kalau tidak -> ditandai "cek".
Naskah wajib disetujui (UI) sebelum dirender.
"""
import re

import aw_ai as ai
import aw_common as C
import aw_doodle as D
import aw_research as R

TYPES = ("tanya", "bicara", "quran", "hadits", "poin", "langkah", "fakta", "penutup")
BASE_TAGS = ["#NgajiSantai", "#IlmuIslam", "#Fiqih", "#DakwahIslam", "#Islam"]

SYSTEM = (
    "Kamu penulis naskah video animasi doodle edukasi Islam untuk Facebook Reels, bahasa Indonesia santai tapi sopan, "
    "untuk orang awam. ATURAN MUTLAK:\n"
    "1. Semua fakta, hukum, dalil, dan hikmah HANYA dari BAHAN yang diberikan. Jangan menambah dari ingatanmu.\n"
    "2. Jangan pernah mengarang ayat, hadits, nomor ayat, atau perawi. Ayat cukup ditulis nomor surat & ayat yang "
    "DISEBUT di bahan. Kutipan hadits harus DISALIN dari bahan.\n"
    "3. Jangan membuat klaim medis/ilmiah yang tidak ada di bahan.\n"
    "4. Topik sensitif (hubungan suami istri, haid, aurat) dijelaskan sopan dan tidak vulgar.\n"
    "5. Jika bahan menyebut perbedaan pendapat ulama/mazhab, sebutkan singkat dan adil.\n"
    "6. Jangan menggambarkan atau menyebut rupa Nabi dan sahabat.\n"
    "7. Video akan MENGGAMBAR tokoh saat perannya disebut. Bila bahan memuat contoh/perumpamaan, tulis dengan kata peran yang jelas "
    "(suami, istri, anak, ibu, ayah, bayi, kakek, nenek) dan kata perasaan (marah, sedih, bahagia, cinta) apa adanya. "
    "Jangan mengarang cerita yang tidak ada di bahan.\n"
    "Balas HANYA JSON valid.")

SCHEMA = """Format JSON:
{
 "judul_pendek": "judul di layar, maks 40 karakter, boleh tandai 1-2 kata penting dengan *bintang*",
 "judul": "judul postingan FB, maks 90 karakter",
 "adegan": [
  {"tipe":"tanya","narasi":"hook pembuka 1 kalimat","teks":"pertanyaan singkat di layar, maks 9 kata"},
  {"tipe":"bicara","narasi":"2-4 kalimat penjelasan ustadz, mengalir seperti bicara","teks":"inti kalimat di balon, maks 10 kata","ikon":["nama ikon","nama ikon"]},
  {"tipe":"quran","narasi":"1-2 kalimat pengantar sebelum ayat dibaca","penjelasan":"2-3 kalimat: makna ayat & kaitannya dengan topik, SESUAI bahan","surat":5,"ayat":6,"kutipan":"potongan terjemahan yang relevan"},
  {"tipe":"hadits","narasi":"1-2 kalimat pengantar sebelum hadits dibaca","penjelasan":"2-3 kalimat: pelajaran dari hadits, SESUAI bahan","kutipan":"teks hadits terjemahan, DISALIN dari bahan","perawi":"HR. ... (sesuai bahan)"},
  {"tipe":"poin","narasi":"3-4 kalimat menjelaskan tiap poin","judul":"maks 5 kata","poin":[{"ikon":"nama ikon","teks":"maks 6 kata"}]},
  {"tipe":"langkah","narasi":"3-4 kalimat menjelaskan tiap langkah","judul":"maks 5 kata","langkah":["maks 6 kata", "..."]},
  {"tipe":"fakta","narasi":"2-3 kalimat","besar":"1-2 kata besar","kecil":"keterangan maks 10 kata"},
  {"tipe":"penutup","narasi":"ajakan komentar 1-2 kalimat","tanya":"pertanyaan ke penonton","a":"opsi A singkat","b":"opsi B singkat"}
 ],
 "deskripsi": "2-3 kalimat ringkasan untuk caption",
 "hashtag": ["#...", "#...", "#...", "#...", "#..."]
}"""


def _source_digest(sources, topik, budget=6500):
    """Ambil paragraf paling relevan dari tiap sumber (muat di konteks LLM)."""
    words = R._words(topik)
    use = [s for s in sources if s.get("use") and s.get("text")]
    if not use:
        return "", []
    per = budget // len(use)
    out = []
    for i, s in enumerate(use, 1):
        paras = [p for p in s["text"].split("\n") if len(p) > 30]
        scored = sorted(range(len(paras)), key=lambda k: -(len(words & R._words(paras[k])) * 3
                                                        + (4 if re.search(r"\b(QS|HR|hadits|hadis|surat|firman|sabda|rasulullah)\b", paras[k], re.I) else 0)))
        pick, n = set(), 0
        for k in scored:
            if n + len(paras[k]) > per:
                continue
            pick.add(k)
            n += len(paras[k])
        body = "\n".join(paras[k] for k in sorted(pick))
        out.append(f"[BAHAN {i}] {s.get('title', '')} ({s.get('domain', '')})\n{body}")
    return "\n\n".join(out), use


EXTRACT = """Dari BAHAN di atas, SALIN kalimat-kalimat yang menjawab topik. Jangan menulis kalimat sendiri.
Format JSON:
{
 "alasan":  [{"kutipan": "kalimat PERSIS dari bahan tentang hukum/alasan", "bahan": 1}],
 "dalil":   [{"jenis": "quran", "surat": 5, "ayat": 6, "kutipan": "terjemah ayat PERSIS dari bahan", "bahan": 1},
             {"jenis": "hadits", "perawi": "HR. ... (sesuai bahan)", "kutipan": "teks hadits PERSIS dari bahan", "bahan": 2}],
 "hikmah":  [{"kutipan": "...", "bahan": 1}],
 "langkah": [{"kutipan": "satu langkah tata cara PERSIS dari bahan", "bahan": 3}],
 "catatan": [{"kutipan": "perbedaan pendapat ulama / pengecualian / kesalahan umum", "bahan": 2}]
}
Maksimal 6 item per daftar. Kosongkan daftar ([]) bila tidak ada di bahan. Kutipan disalin kata per kata."""


def _models(cfg, stage="naskah"):
    """Tahap 'kutip' (menyalin kalimat, hasilnya dicek ke teks asli) memakai model yang muat di RAM (llm_extract_model)
    agar 7 bahan tidak makan waktu berjam-jam; tahap 'naskah' memakai llm_model."""
    main = cfg.get("llm_model", "gemma2:9b")
    if stage == "kutip":
        main = cfg.get("llm_extract_model") or main
    return [main] + [m for m in [cfg.get("llm_model", "gemma2:9b")] + cfg.get("llm_fallback", ["qwen2.5:7b", "qwen2.5:3b", "gemma2:2b"])
                     if m != main]


def _ask(prompt, cfg, log, max_tokens, check, num_ctx=6144, stage="naskah"):
    models, err = _models(cfg, stage), ""
    timeout = int(cfg.get("llm_timeout", 1800)) if stage == "naskah" else 900
    for attempt in range(2):
        try:
            raw, model = ai.chat_auto(prompt, models, log, system=SYSTEM, json_mode=True, num_ctx=num_ctx, timeout=timeout,
                                      temperature=0.2 + 0.2 * attempt, max_tokens=max_tokens)
            return check(ai.parse_json(raw)), model
        except ai.AIUnavailable as e:
            raise RuntimeError(f"LLM tidak tersedia: {str(e)[:300]}")
        except Exception as e:
            err = str(e)[:150]
            log(f"   ⚠️ percobaan {attempt + 1}: {err}")
    raise RuntimeError(f"LLM gagal: {err}")


def extract_facts(project, cfg, log=print):
    """Tahap 1: kutipan ekstraktif dari bahan, lalu dicek satu per satu ke teks asli (yang tidak cocok dibuang)."""
    topik, sudut = project["topik"], project.get("sudut", "")
    digest, use = _source_digest(project.get("sources", []), topik + " " + sudut)
    if not digest:
        raise RuntimeError("Belum ada bahan terpilih. Jalankan riset atau tambahkan sumber/catatan dulu.")
    min_src = int(cfg.get("min_sources", 4))
    if len(use) < min_src:
        raise RuntimeError(f"Bahan baru {len(use)} sumber (minimal {min_src} agar video berbobot). "
                           "Klik 'Cari ulang bahan', centang bahan lain, atau tambah URL/catatan sendiri.")
    refs = []
    for s in use:
        for r in s.get("refs", []):
            if r not in refs:
                refs.append(r)
    log(f"📑 Tahap 1: mengutip fakta & dalil per bahan ({len(use)} bahan)…")

    def check(d):
        if not isinstance(d, dict):
            raise ValueError("bukan objek JSON")
        return d

    raws, model = [], None
    for i, src in enumerate(use, 1):
        one, _ = _source_digest([src], topik + " " + sudut, budget=4200)
        rr = [r for r in src.get("refs", [])]
        prompt = (f"TOPIK: {topik}\n" + (f"SUDUT: {sudut}\n" if sudut else "") + f"\nBAHAN:\n{one}\n\n"
                  f"RUJUKAN AYAT DI BAHAN: {', '.join(_ref_label_num(r) for r in rr[:8]) or '-'}\n\n{EXTRACT}\n"
                  "Ambil sebanyak mungkin (2-6 per daftar) kalimat yang relevan dengan topik.")
        try:
            r1, model = _ask(prompt, cfg, log, 1100, check, stage="kutip")
            raws.append(r1)
            log(f"   [{i}/{len(use)}] {src.get('domain', '')}: {sum(len(v) for v in r1.values() if isinstance(v, list))} kutipan")
        except RuntimeError as e:
            log(f"   [{i}/{len(use)}] {src.get('domain', '')}: gagal ({str(e)[:80]})")
    if model:
        ai.unload(model)                 # kosongkan RAM sebelum model naskah dimuat
    if not raws:
        raise RuntimeError("Tidak ada kutipan yang bisa diambil dari bahan (AI gagal membaca semua bahan)")
    raw = {}
    for r1 in raws:
        for k, v in r1.items():
            if isinstance(v, list):
                raw.setdefault(k, []).extend(v)
    texts = [s["text"] for s in use]
    facts = {"alasan": [], "dalil": [], "hikmah": [], "langkah": [], "catatan": []}
    # dalil yang DISALIN langsung dari teks bahan (tanpa AI) -> pasti persis; AI kecil sering melewatkan hadits
    kw = R.key_words(R.core_query(topik) + " " + sudut)
    harvested, hseen = [], []
    for s in use:
        for h in R.harvest_hadits(s["text"], kw) + R.harvest_quran(s["text"], s.get("refs", []), kw):
            key_h = f"q:{h['surat']}:{h['ayat']}" if h["jenis"] == "quran" else h["kutipan"]
            dup = next((n for n, k in enumerate(hseen)
                        if ((k == key_h) if h["jenis"] == "quran" else (not k.startswith("q:") and R.match_score(key_h, k) >= 0.6))), None)
            item = dict(h, skor=1.0, url=s.get("url", ""), otomatis=True)
            if dup is not None:      # dalil sama dari situs lain: simpan versi yang konteksnya paling lengkap
                if len(item.get("konteks2", "")) > len(harvested[dup].get("konteks2", "")):
                    harvested[dup] = item
                continue
            hseen.append(key_h)
            harvested.append(item)
    # kata kunci yang jarang muncul (mis. 'handuk') lebih membedakan daripada yang ada di semua dalil (mis. 'wudhu')
    import math
    low = [(h["kutipan"] + " " + h.get("konteks", "")).lower() for h in harvested]
    df = {w: sum(1 for t in low if w in t) for w in kw}
    for h, t in zip(harvested, low):
        h["relevan"] = round(sum(1 + math.log(len(low) / df[w]) for w in kw if df[w] and w in t), 2)
    harvested = [h for h in harvested if h["relevan"] > 0]
    harvested.sort(key=lambda h: -h["relevan"])
    facts["dalil"] = harvested[:10]
    log(f"   📜 {sum(h['jenis'] == 'hadits' for h in facts['dalil'])} hadits & "
        f"{sum(h['jenis'] == 'quran' for h in facts['dalil'])} ayat disalin langsung dari bahan")
    dropped = 0
    for key in facts:
        seen = set()
        for it in (raw.get(key) or [])[:24]:
            if isinstance(it, str):
                it = {"kutipan": it}
            if not isinstance(it, dict):
                continue
            q = _clean(it.get("kutipan"), 400).strip("'\"“”‘’ ")
            sig = re.sub(r"\W+", "", q.lower())[:60]
            if len(q) < 8 or sig in seen:
                continue
            seen.add(sig)
            if key == "dalil" and str(it.get("jenis", "")).lower().startswith("q"):
                if any(f.get("jenis") == "quran" and str(f.get("surat")) == str(it.get("surat")) and str(f.get("ayat")) == str(it.get("ayat"))
                       for f in facts["dalil"]):
                    continue
            elif key == "dalil" and any(f.get("jenis") != "quran" and R.match_score(q, f["kutipan"]) >= 0.7 for f in facts["dalil"]):
                continue
            best = max(((R.match_score(q, t), i) for i, t in enumerate(texts)), default=(0, 0))
            item = dict(it, kutipan=q, skor=best[0], url=use[best[1]].get("url", "") if texts else "")
            if key == "dalil" and str(it.get("jenis", "")).lower().startswith("q"):
                try:
                    sa = f"{int(it.get('surat'))}:{int(it.get('ayat'))}"
                except (TypeError, ValueError):
                    dropped += 1
                    continue
                item["jenis"] = "quran"
                try:
                    ay = R.get_ayat(*map(int, sa.split(":")))
                    item["resmi"] = R.match_score(q, ay["terjemah"])
                except Exception:
                    item["resmi"] = 0
                if sa not in refs and item["resmi"] < 0.6:
                    dropped += 1
                    continue
            elif best[0] < 0.75:
                dropped += 1
                continue
            facts[key].append(item)
    n = sum(len(v) for v in facts.values())
    log(f"   {n} kutipan cocok dengan bahan, {dropped} dibuang (tidak ditemukan di bahan)")
    return facts, use, model


_FACT_CAP = {"alasan": 8, "dalil": 8, "hikmah": 6, "langkah": 6, "catatan": 8}


def _facts_text(facts, budget=6500):
    """Teks fakta untuk prompt; dibatasi agar prompt + jawaban muat di konteks model lokal."""
    out = []
    names = {"alasan": "ALASAN/HUKUM", "dalil": "DALIL", "hikmah": "HIKMAH", "langkah": "TATA CARA", "catatan": "CATATAN ULAMA"}
    per = max(140, budget // max(1, sum(min(len(facts[k]), _FACT_CAP[k]) for k in names)))
    for k, label in names.items():
        if not facts[k]:
            continue
        out.append(label + ":")
        for it in facts[k][:_FACT_CAP[k]]:
            kut = _clean(it["kutipan"], max(per, 260) if k == "dalil" else per)
            if k == "dalil" and it.get("jenis") == "quran":
                out.append(f"- [AYAT surat={it['surat']} ayat={it['ayat']}] {kut}")
            elif k == "dalil":
                extra = f" (KETERANGAN DERAJAT DI BAHAN: {_clean(it['derajat'], 160)})" if it.get("derajat") else ""
                ctx = f" (konteks: {_clean(it['konteks'], 120)})" if it.get("konteks") else ""
                out.append(f"- [HADITS {it.get('perawi', '')}] {kut}{ctx}{extra}")
            else:
                out.append(f"- {kut}")
    return "\n".join(out)


def spoken_words(script):
    """Jumlah kata yang diucapkan ustadz (narasi + penjelasan dalil). Dalil sendiri dibacakan terpisah."""
    n = 0
    for a in script.get("adegan", []):
        n += len((a.get("narasi") or "").split())
        if a.get("tipe") in ("quran", "hadits"):
            n += len((a.get("penjelasan") or "").split())
    return n


_EXPANDABLE = ("bicara", "poin", "fakta", "langkah", "quran", "hadits")


def _expand(data, ft, topik, cfg, log, target):
    """Model kecil cenderung menulis naskah pendek. Perpanjang adegan pendek SATU PER SATU (prompt kecil & fokus),
    hanya dari fakta terverifikasi. Ayat/hadits: yang diperpanjang 'penjelasan', kutipan dalil tidak disentuh."""
    sc = data["adegan"]
    idx = [i for i, a in enumerate(sc) if a["tipe"] in _EXPANDABLE]
    if not idx:
        return data
    fixed = spoken_words(data) - sum(len((sc[i].get("penjelasan" if sc[i]["tipe"] in ("quran", "hadits") else "narasi") or "").split())
                                     for i in idx)
    per = max(25, min(60, -(-(target - fixed) // len(idx))))
    log(f"   ✍️ memperpanjang adegan pendek satu per satu (±{per} kata per adegan)…")

    def check(d):
        t = d.get("teks") if isinstance(d, dict) else None
        if not isinstance(t, str) or len(t.split()) < 8:
            raise ValueError("teks kosong")
        return t

    for i in sorted(idx, key=lambda k: len((sc[k].get("penjelasan") or sc[k].get("narasi") or "").split())):
        if spoken_words(data) >= target:
            break
        a = sc[i]
        field = "penjelasan" if a["tipe"] in ("quran", "hadits") else "narasi"
        old = a.get(field) or ""
        if len(old.split()) >= per * 0.85:
            continue
        outline = "\n".join(f"{k + 1}. [{x['tipe']}] {_clean(x.get('narasi'), 140)}" for k, x in enumerate(sc))
        if field == "penjelasan":
            dal = (f"QS {a.get('surat')}:{a.get('ayat')}" if a["tipe"] == "quran" else a.get("perawi", "hadits")) + \
                  f" — “{_clean(a.get('kutipan'), 220)}”"
            task = (f"Adegan {i + 1} membacakan dalil {dal}. Pengantarnya: “{a.get('narasi', '')}”.\n"
                    f"Tulis PENJELASAN ustadz setelah dalil dibaca: {per}-{per + 15} kata (3-4 kalimat lisan yang hangat): "
                    "apa makna dalil ini dan bagaimana kaitannya dengan topik, SESUAI fakta. Bila fakta menyebut derajat hadits ini "
                    "dhaif/lemah/diperselisihkan, katakan dengan jujur. Jangan mengutip dalil lain.")
        else:
            task = (f"Adegan {i + 1} (tipe {a['tipe']}) sekarang berbunyi: “{old}”.\n"
                    f"Tulis ulang NARASI adegan ini jadi {per}-{per + 15} kata (3-4 kalimat lisan yang hangat, untuk orang awam), "
                    "dengan topik yang sama seperti narasi sekarang, diperdalam dengan alasan/pendapat ulama/hikmah dari fakta.")
        prompt = (f"FAKTA TERVERIFIKASI (satu-satunya sumber yang boleh dipakai):\n{ft}\n\nTOPIK VIDEO: {topik}\n\n"
                  f"NASKAH SAAT INI:\n{outline}\n\nTUGAS: {task}\n"
                  "Jangan mengulang isi adegan lain, jangan menambah hukum/dalil/klaim yang tidak ada di fakta, "
                  "jangan memakai emoji. Balas JSON: {\"teks\": \"...\"}")
        try:
            new, _ = _ask(prompt, cfg, log, 420, check, stage="naskah")
        except RuntimeError as e:
            log(f"      adegan {i + 1}: gagal ({str(e)[:60]})")
            continue
        new = _clean(new, 520)
        if len(new.split()) > len(old.split()):
            a[field] = new
            log(f"      adegan {i + 1} [{a['tipe']}]: {len(old.split())} → {len(new.split())} kata")
    log(f"   naskah setelah diperpanjang: {spoken_words(data)} kata")
    return data


def _write_kerangka(project, cfg, log, facts, use):
    """Kerangka adegan disusun program dari fakta; AI hanya menulis ulang kutipan per adegan (lihat aw_kerangka)."""
    import aw_kerangka as K
    topik, sudut = project["topik"], project.get("sudut", "")
    kw = R.key_words(R.core_query(topik) + " " + sudut)
    outline, khilaf = K.build_outline(facts, topik, kw, {s.get("url", ""): s.get("title", "") for s in use})
    log(f"🧱 Kerangka ({'ada beda pendapat ulama' if khilaf else 'satu pendapat'}): "
        + " → ".join(s["peran"] + (f"[{s['label']}]" if s.get("label") and s["peran"] != "kesimpulan" else "") for s in outline))
    used = {"model": None}

    def ask(prompt, max_tokens, check):
        r, m = _ask(prompt, cfg, log, max_tokens, check, stage="naskah")
        used["model"] = m
        return r

    raw = K.write_from_outline(outline, khilaf, facts, topik, cfg, log, ask, _clean)
    if used["model"]:
        ai.unload(used["model"])
    data = normalize(raw)
    n, words = spoken_words(data), int(cfg.get("target_words", 140))
    log(f"   naskah: {n} kata, {len(data['adegan'])} adegan (target {words})")
    hard_min = int(words * 0.55)
    if n < hard_min:
        raise RuntimeError(f"Naskah terlalu pendek ({n} kata, minimal {hard_min}) — bahan kurang kaya untuk topik ini. "
                           "Tambah URL kajian/catatan sendiri lalu tulis ulang naskah.")
    data["model"] = (used["model"] or "-") + " (kerangka)"
    data["khilaf"] = khilaf
    data["fakta"] = facts
    data["sumber"] = [{"title": s.get("title", ""), "url": s.get("url", ""), "domain": s.get("domain", "")} for s in use]
    verify(data, project, log)
    _drop_bad_dalil(data, log)
    return data


def _drop_bad_dalil(data, log):
    """Adegan ayat yang gagal dicek / tidak disebut di bahan dibuang otomatis (bukan diserahkan ke pengguna)."""
    keep, gone = [], 0
    for a in data["adegan"]:
        if a["tipe"] == "quran" and (a.get("status") == "gagal" or "TIDAK disebut di bahan" in (a.get("catatan") or "")):
            gone += 1
            continue
        if a["tipe"] == "hadits" and (a.get("skor") or 0) < 0.8:
            gone += 1
            continue
        keep.append(a)
    if gone:
        data["adegan"] = keep
        data["masalah"] = sum(1 for a in keep if a["tipe"] in ("quran", "hadits") and a.get("status") != "ok")
        log(f"   🗑️ {gone} adegan dalil dibuang otomatis (tidak cocok dengan bahan)")


def write_script(project, cfg, log=print):
    topik, sudut = project["topik"], project.get("sudut", "")
    facts, use, model1 = extract_facts(project, cfg, log)
    ft = _facts_text(facts)
    nfacts = sum(len(v) for v in facts.values())
    min_facts = int(cfg.get("min_facts", 6))
    if len(ft) < 80 or nfacts < min_facts:
        raise RuntimeError(f"Bahan hanya menghasilkan {nfacts} fakta (minimal {min_facts}) — terlalu tipis untuk video berbobot. "
                           "Cari ulang bahan, tambah URL artikel kajian, atau tulis catatan sendiri.")
    has_dalil = bool(facts["dalil"])
    if not has_dalil:
        log("   ⚠️ Tidak ada ayat/hadits di bahan — naskah akan memperdalam alasan & pendapat ulama. "
            "Sebaiknya tambah URL kajian yang memuat dalil.")
    if cfg.get("naskah_mode", "kerangka") == "kerangka":
        return _write_kerangka(project, cfg, log, facts, use)
    words = int(cfg.get("target_words", 140))
    secs = int(round(words / 2.4 / 5.0) * 5)
    prompt = (f"TOPIK: {topik}\n" + (f"SUDUT/CERITA: {sudut}\n" if sudut else "") +
              f"\nFAKTA TERVERIFIKASI (satu-satunya sumber yang boleh dipakai):\n{ft}\n\n"
              f"Buat storyboard 8-10 adegan (ganti adegan tiap ±6 detik agar visual terus berubah), total narasi+penjelasan ±{words} kata (±{secs} detik, JANGAN kurang dari {words} kata; dalil dibacakan terpisah). Ustadz harus BANYAK MENJELASKAN: jelaskan alasan/hikmah dan hubungan tiap dalil dengan topik dengan bahasa lisan yang hangat, bukan sekadar menempel dalil. Isi 'penjelasan' di setiap adegan quran/hadits. Adegan 'bicara' dan 'poin' masing-masing 3-4 kalimat. Adegan pertama 'tanya' (hook), terakhir 'penutup'. "
              "Narasi harus sesuai isi fakta di atas — jangan menambah hukum, langkah, atau klaim baru. "
              "Adegan 'quran' HANYA untuk [AYAT ...] di atas dengan nomor surat & ayat yang sama. "
              "Adegan 'hadits' HANYA untuk [HADITS ...] di atas, kutipan disalin persis, perawi sama. "
              "Bila ada KETERANGAN DERAJAT yang menyebut hadits itu dhaif/lemah/diperselisihkan, WAJIB disebut jujur di 'penjelasan'. "
              "Bila ulama berbeda pendapat, tampilkan dalil masing-masing pendapat secara adil (2-3 dalil). "
              "Adegan 'langkah' hanya dari TATA CARA di atas: ringkas jadi 3-5 langkah berurutan, masing-masing maks 6 kata. "
              "Pilih dalil yang PALING LANGSUNG menjawab topik (bukan dalil sampingan). "
              "Bila ada CATATAN ULAMA/pengecualian penting, masukkan ke adegan 'bicara' atau 'fakta'. "
              "Bila tidak ada dalil/tata cara di fakta, jangan buat adegannya — GANTI dengan adegan 'bicara'/'poin'/'fakta' "
              "yang menjelaskan ALASAN, HIKMAH, dan CATATAN ULAMA lebih dalam sehingga tetap 8-10 adegan. "
              f"Nama ikon: {', '.join(D.ICON_NAMES)}.\n\n{SCHEMA}")
    log("✍️ Tahap 2: menyusun storyboard dari fakta terverifikasi…")

    def check(d):
        d = normalize(d)
        if len(d["adegan"]) < 6:
            raise ValueError(f"adegan terlalu sedikit ({len(d['adegan'])})")
        return d

    # naskah terlalu pendek -> tulis ulang dengan umpan balik (maks 3x), ambil yang terpanjang
    min_words = int(words * float(cfg.get("min_word_ratio", 0.75)))
    best, best_n, model = None, -1, None
    for attempt in range(max(1, int(cfg.get("naskah_percobaan", 2)))):
        p = prompt
        if best is not None:
            p += (f"\n\nPERCOBAAN SEBELUMNYA TERLALU PENDEK: hanya {best_n} kata dalam {len(best['adegan'])} adegan. "
                  f"Tulis ulang LEBIH PANJANG: minimal {words} kata narasi+penjelasan, 8-10 adegan. Pakai SEMUA fakta di atas "
                  "(alasan, dalil beserta penjelasannya, pendapat ulama, hikmah). Tiap 'bicara'/'poin' 3-4 kalimat.")
        try:
            data, model = _ask(p, cfg, log, 2800, check, num_ctx=8192)
        except RuntimeError as e:
            if best is None:
                raise
            log(f"   ⚠️ tulis ulang gagal: {str(e)[:100]}")
            break
        n = spoken_words(data)
        log(f"   naskah percobaan {attempt + 1}: {n} kata, {len(data['adegan'])} adegan (target ≥{min_words})")
        if n > best_n:
            best, best_n = data, n
        if n >= min_words:
            break
    data = best
    if best_n < min_words:
        data = _expand(data, ft, topik, cfg, log, words)
        best_n = spoken_words(data)
    ai.unload(model)
    hard_min = int(words * 0.55)
    if best_n < hard_min:
        raise RuntimeError(f"Naskah tetap terlalu pendek ({best_n} kata, minimal {hard_min}). "
                           "Coba 'Tulis ulang naskah', atau tambah URL kajian/catatan sendiri.")
    if best_n < min_words:
        log(f"   ⚠️ Naskah {best_n} kata (di bawah target {min_words}) — bisa ditambah manual di editor sebelum disetujui.")
    log(f"   model: {model}")
    data["model"] = model
    data["fakta"] = facts
    data["sumber"] = [{"title": s.get("title", ""), "url": s.get("url", ""), "domain": s.get("domain", "")} for s in use]
    verify(data, project, log)
    return data


def _ref_label_num(r):
    s, a = r.split(":")
    try:
        nama = next(x["namaLatin"] for x in R.surah_list() if int(x["nomor"]) == int(s))
    except Exception:
        nama = f"Surat {s}"
    return f"QS {nama} ({s}):{a}"


# ================================================================ normalisasi
def _clean(s, n=0):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    s = re.sub("[\U0001F000-\U0001FAFF☀-➿️‍]+", "", s)
    return s[:n].rstrip() if n and len(s) > n else s


def normalize(d):
    if not isinstance(d, dict):
        raise ValueError("bukan objek JSON")
    sc = d.get("adegan") or d.get("scenes") or []
    out = []
    for a in sc:
        if not isinstance(a, dict):
            continue
        tp = str(a.get("tipe", "bicara")).lower().strip()
        tp = {"ayat": "quran", "alquran": "quran", "hadis": "hadits", "hook": "tanya", "cta": "penutup", "tips": "langkah",
              "cara": "langkah", "hikmah": "poin", "list": "poin"}.get(tp, tp)
        if tp not in TYPES:
            tp = "bicara"
        x = {"tipe": tp, "narasi": _clean(a.get("narasi"), 520)}
        if _clean(a.get("penjelasan"), 520):
            x["penjelasan"] = _clean(a.get("penjelasan"), 520)
        if not x["narasi"]:
            continue
        if tp == "tanya":
            x["teks"] = _clean(a.get("teks") or x["narasi"], 80)
        elif tp == "bicara":
            x["teks"] = _clean(a.get("teks") or "", 90)
            ik = a.get("ikon") or []
            x["ikon"] = [D.icon_key(i) for i in (ik if isinstance(ik, list) else [ik]) if isinstance(i, str)][:2]
            if not x["ikon"]:      # isi otomatis dari kata di narasi agar layar tidak kosong
                auto = []
                for w in re.findall(r"[a-z']+", (x["narasi"] + " " + x["teks"]).lower()):
                    k = D.ICON_ALIASES.get(w)
                    if k and k not in auto:
                        auto.append(k)
                x["ikon"] = (auto + ["lampu", "buku"])[:2]
        elif tp == "quran":
            try:
                x["surat"], x["ayat"] = int(a.get("surat")), int(a.get("ayat"))
            except (TypeError, ValueError):
                m = re.search(r"(\d{1,3})\s*:\s*(\d{1,3})", str(a.get("surat", "")) + ":" + str(a.get("ayat", "")))
                if not m:
                    continue
                x["surat"], x["ayat"] = int(m.group(1)), int(m.group(2))
            x["kutipan"] = _clean(a.get("kutipan"), 300)
        elif tp == "hadits":
            x["kutipan"] = _clean(a.get("kutipan"), 360)
            x["perawi"] = _clean(a.get("perawi"), 60)
            if not x["kutipan"]:
                continue
        elif tp == "poin":
            x["judul"] = _clean(a.get("judul"), 50)
            pts = []
            for p in (a.get("poin") or [])[:3]:
                if isinstance(p, dict) and p.get("teks"):
                    pts.append({"ikon": D.icon_key(p.get("ikon", "")), "teks": _clean(p["teks"], 60)})
                elif isinstance(p, str):
                    pts.append({"ikon": D.icon_key(p), "teks": _clean(p, 60)})
            if not pts:
                continue
            x["poin"] = pts
        elif tp == "langkah":
            x["judul"] = _clean(a.get("judul"), 50)
            x["langkah"] = [_clean(s, 60) for s in (a.get("langkah") or []) if isinstance(s, str) and len(re.sub(r"[\W_]+", "", s)) > 2][:5]
            if not x["langkah"]:
                continue
        elif tp == "fakta":
            x["besar"] = _clean(a.get("besar"), 24)
            x["kecil"] = _clean(a.get("kecil"), 90)
        elif tp == "penutup":
            x["tanya"] = _clean(a.get("tanya") or x["narasi"], 90)
            x["a"], x["b"] = _clean(a.get("a"), 40), _clean(a.get("b"), 40)
        out.append(x)
    if out and out[0]["tipe"] != "tanya":
        out.insert(0, {"tipe": "tanya", "narasi": out[0]["narasi"] if out[0]["tipe"] == "bicara" else "Pernah kepikiran nggak?",
                       "teks": _clean(d.get("judul_pendek") or "Kenapa begitu?", 80)})
        if out[1]["tipe"] == "bicara" and out[1]["narasi"] == out[0]["narasi"]:
            out.pop(1)
    if out and out[-1]["tipe"] != "penutup":
        out.append({"tipe": "penutup", "narasi": "Semoga bermanfaat. Tulis pendapatmu di komentar, ya.",
                    "tanya": "Sudah tahu sebelumnya?", "a": "Sudah tahu", "b": "Baru tahu"})
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in (d.get("hashtag") or []) if str(t).strip()]
    tags = [re.sub(r"[^\w#]", "", t) for t in tags]
    seen, merged = set(), []
    for t in tags + BASE_TAGS:
        if len(t) > 2 and t.lower() not in seen:
            seen.add(t.lower())
            merged.append(t)
    return {"judul_pendek": _clean(d.get("judul_pendek"), 48) or _clean(out[0].get("teks") if out else "", 48),
            "judul": _clean(d.get("judul"), 100), "deskripsi": _clean(d.get("deskripsi"), 500),
            "hashtag": merged[:10], "adegan": out}


# ================================================================ verifikasi
def _arab_excerpt(arab, lim=150):
    """Ayat panjang: tampilkan & bacakan potongan awalnya (di batas kata) agar muat di kartu."""
    if len(arab) <= lim:
        return arab
    out = ""
    for w in arab.split():
        if len(out) + len(w) + 1 > lim - 20 and len(out) > 90:
            break
        out = (out + " " + w).strip()
    return out + " …"


def verify(script, project, log=print):
    """Isi ayat_data/tampil/ref_label/status per adegan dalil. status: ok | cek | gagal."""
    use = [s for s in project.get("sources", []) if s.get("use") and s.get("text")]
    corpus = "\n".join(s["text"] for s in use)
    refs = set()
    for s in use:
        refs.update(s.get("refs", []))
    issues = 0
    for sc in script["adegan"]:
        tp = sc["tipe"]
        if tp == "quran":
            sc["ref_label"] = f"QS {sc['surat']}:{sc['ayat']}"
            try:
                ay = R.get_ayat(sc["surat"], sc["ayat"])
            except Exception as e:
                sc.update(status="gagal", catatan=f"Ayat tidak ditemukan/tidak bisa dicek: {str(e)[:100]}", ayat_data=None,
                          tampil=sc.get("kutipan", ""))
                issues += 1
                continue
            sc["ayat_data"] = ay
            sc["arab_tampil"] = _arab_excerpt(ay["arab"])
            sc["ref_label"] = f"QS. {ay['nama']}: {ay['ayat']}"
            k = sc.get("kutipan", "")
            if k and R.match_score(k, ay["terjemah"]) >= 0.75:
                sc["tampil"] = _excerpt(ay["terjemah"], k)
            else:
                sc["tampil"] = R.best_sentence(ay["terjemah"], (k or "") + " " + sc.get("narasi", "")) if len(ay["terjemah"]) > 220 else ay["terjemah"]
            in_src = f"{sc['surat']}:{sc['ayat']}" in refs
            fakta = {f"{f.get('surat')}:{f.get('ayat')}" for f in (script.get("fakta") or {}).get("dalil", []) if f.get("jenis") == "quran"}
            k_ok = (not k) or R.match_score(k, ay["terjemah"]) >= 0.6
            if not in_src:
                sc.update(status="cek", catatan="Ayat valid, tapi TIDAK disebut di bahan — pastikan ayat ini memang dalil topik ini.")
                issues += 1
            elif not k_ok:
                sc.update(status="cek", catatan="Ayat disebut di bahan, tapi kutipan versi AI tidak ada di terjemah Kemenag — "
                                                "baca terjemah resmi di bawah & pastikan ayat ini relevan dengan narasinya.")
                issues += 1
            elif script.get("fakta") is not None and f"{sc['surat']}:{sc['ayat']}" not in fakta:
                sc.update(status="cek", catatan="Ayat disebut di bahan, tapi tidak ada di daftar dalil hasil kutipan — cek relevansinya.")
                issues += 1
            else:
                sc.update(status="ok", catatan="Ayat ada di API Kemenag, disebut di bahan, dan kutipannya cocok.")
        elif tp == "hadits":
            sc["kutipan"] = (sc.get("kutipan") or "").strip("'\"“”‘’ ")
            if not sc.get("perawi"):
                for f in (script.get("fakta") or {}).get("dalil", []):
                    if f.get("jenis") != "quran" and f.get("perawi") and R.match_score(sc["kutipan"], f["kutipan"]) >= 0.7:
                        sc["perawi"] = f["perawi"]
                        break
            score = R.match_score(sc.get("kutipan", ""), corpus)
            sc["tampil"] = sc.get("kutipan", "")
            sc["ref_label"] = sc.get("perawi") or "Hadits"
            src = ""
            fk = next((f for f in (script.get("fakta") or {}).get("dalil", []) if f.get("jenis") != "quran"
                       and R.match_score(sc["kutipan"], f.get("kutipan", "")) >= 0.7), None)
            der = (fk or {}).get("derajat", "")
            if der:
                sc["derajat"] = der
            weak = bool(re.search(r"dha['’]?[iī]f|da['’]?if|lemah|tidak s[h]?ahih|maudhu|palsu|munkar|mursal", der, re.I))
            if score >= 0.8:
                for s in use:
                    if R.match_score(sc["kutipan"], s["text"]) >= 0.8:
                        src = s.get("url") or s.get("title", "")
                        break
                if weak:
                    sc.update(status="cek", skor=score, sumber=src,
                              catatan=f"Kutipan ada di bahan, tapi bahan menyebut derajatnya: “{der[:140]}”. "
                                      "Pastikan penjelasan menyebut hal ini, atau hapus adegan.")
                    issues += 1
                else:
                    sc.update(status="ok", skor=score, sumber=src, catatan=f"Kutipan ditemukan di bahan ({int(score * 100)}% cocok).")
            else:
                sc.update(status="cek", skor=score, catatan=f"Kutipan hadits TIDAK ditemukan di bahan ({int(score * 100)}% cocok) — "
                                                            "bisa jadi dikarang AI. Cek ke kitab/situs hadits atau hapus adegan ini.")
                issues += 1
    # dukungan bahan per adegan: porsi kata kunci narasi/teks yang muncul di bahan
    cw = R._words(corpus)
    for sc in script["adegan"]:
        if sc["tipe"] in ("tanya", "penutup"):
            continue
        txt = " ".join([sc.get("narasi", ""), sc.get("teks", ""), sc.get("kecil", ""), " ".join(sc.get("langkah", []) or []),
                        " ".join(p.get("teks", "") for p in sc.get("poin", []) or [])])
        ws = {w for w in R._words(txt) if len(w) >= 4}
        sc["dukungan"] = round(len(ws & cw) / len(ws), 2) if ws else 1.0
        if sc["tipe"] == "langkah":
            weak = [x for x in sc.get("langkah", []) if R._words(x) and len(R._words(x) & cw) / len(R._words(x)) < 0.5]
            if weak:
                sc["catatan"] = "Langkah tidak ditemukan di bahan: " + "; ".join(weak)
    script["masalah"] = issues
    log(f"🔍 Verifikasi dalil: {issues} perlu dicek" if issues else "🔍 Verifikasi dalil: semua dalil cocok dengan sumber")
    return script


def _excerpt(full, hint):
    """Potongan terjemahan resmi yang paling mirip `hint` (agar teks di layar = teks Kemenag, bukan versi AI)."""
    fw = full.split()
    n = len(hint.split())
    best, bs = full, 0.0
    for i in range(0, max(1, len(fw) - n + 1)):
        for L in (n - 2, n, n + 2):
            if L < 3:
                continue
            seg = " ".join(fw[i:i + L])
            sc = R.match_score(hint, seg)
            if sc > bs:
                best, bs = seg, sc
    best = best.strip(" ,;")
    if not best.endswith((".", "!", "?")):
        best += "…"
    if fw and not full.startswith(best.rstrip("…")):
        best = "…" + best[0].lower() + best[1:]
    return best


def caption(script, cfg):
    src = "\n".join(f"• {s['domain']}: {s['url']}" for s in script.get("sumber", []) if s.get("url"))
    dalil = [sc["ref_label"] for sc in script["adegan"] if sc["tipe"] in ("quran", "hadits") and sc.get("ref_label")]
    parts = [script.get("judul") or script.get("judul_pendek", "").replace("*", ""), "", script.get("deskripsi", "")]
    if dalil:
        parts += ["", "Dalil: " + "; ".join(dalil)]
    if src:
        parts += ["", "Rujukan:", src]
    parts += ["", "Konten edukasi ringkas. Untuk kasus pribadi, tanyakan ke ustadz/ulama setempat.", "",
              " ".join(script.get("hashtag", []))]
    return "\n".join(parts).strip()
