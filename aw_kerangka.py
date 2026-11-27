"""
Naskah berbasis KERANGKA (bukan tulisan bebas AI).

1. Program (tanpa AI) menyusun urutan adegan dari fakta terverifikasi:
     ada beda pendapat : pembuka -> duduk persoalan -> pendapat A + dalilnya -> pendapat B + dalilnya
                         -> catatan derajat hadits -> kesimpulan dari bahan -> penutup
     tidak ada         : pembuka -> duduk persoalan -> dalil + penjelasan -> hikmah -> tata cara -> catatan -> kesimpulan -> penutup
2. AI (lokal) hanya menulis ulang 1-3 kutipan milik SATU adegan menjadi bahasa lisan.
3. Tiap kalimat AI dicek ke kutipan adegan itu: kata kunci harus ada di bahan, kata hukum (boleh/makruh/haram/
   batal/wajib/…) dan angka harus ada di bahan. Kalimat yang tidak didukung dibuang; kalau sisanya terlalu
   sedikit, narasi diganti kutipan bahan apa adanya.
4. Teks ayat & hadits selalu disalin dari bahan / API Kemenag, tidak pernah dari AI.
"""
import re

import aw_research as R

# ================================================================ pendapat (stance)
_B_NEG = re.compile(r"tidak(?:lah)?\s+(?:menunjukkan\s+|berarti\s+)?(?:hukum(?:nya)?\s+)?(?:makruh|haram|dilarang|terlarang)", re.I)
_K_NEG = re.compile(r"tidak\s+(?:di)?boleh\w*", re.I)
_BOLEH = re.compile(r"\b(boleh\w*|dibolehkan|diperbolehkan|mubah|tidak mengapa|tidak masalah|tidak apa|tak mengapa)\b|BOLEHX", re.I)
_KETAT = re.compile(r"\b(makruh|dimakruhkan|kemakruhan|haram|diharamkan|dilarang|terlarang|khil[aā]ful\s+aul[aā]|"
                    r"menyalahi yang lebih utama|lebih (?:baik|utama) (?:tidak|ditinggalkan|meninggalkan))\b|KETATX", re.I)


def stance(text):
    """'A' = membolehkan, 'B' = memakruhkan/melarang, None = tidak jelas."""
    t = _B_NEG.sub(" BOLEHX ", text or "")
    t = _K_NEG.sub(" KETATX ", t)
    b, k = len(_BOLEH.findall(t)), len(_KETAT.findall(t))
    return "A" if b > k else "B" if k > b else None


def _label_B(items):
    """Label pendapat kedua = kata hukum yang paling sering dipakai (negasi 'tidak/nggak sampai haram' tidak dihitung)."""
    txt = " ".join(i.get("kutipan", "") + " " + i.get("konteks2", "") for i in items).lower()
    txt = re.sub(r"\b(tidak|nggak|gak|bukan|tak)\s+(sampai\s+|lah\s+)?(haram|makruh|dilarang)\w*", " ", txt)
    cnt = {lab: len(re.findall(pat, txt)) for pat, lab in ((r"\bharam\b|\bdiharamkan", "Haram"), (r"makruh", "Makruh"),
                                                          (r"\bdilarang|\bterlarang", "Dilarang"), (r"aul[aā]", "Kurang utama"))}
    best = max(cnt, key=cnt.get)
    return best if cnt[best] else "Makruh"


_WEAK = re.compile(r"dha['’]?[iī]f|da['’]?if|lemah|tidak s[h]?ahih|maudhu|palsu|munkar|mursal", re.I)
_DERAJAT = re.compile(r"\b(dha['’]?[iī]f|lemah|shahih|sahih|hasan|maudhu|palsu|sanad|perawi)\b", re.I)
_KESIMPULAN = re.compile(r"(jumhur|mayoritas|kebanyakan ulama|pendapat yang (?:lebih )?(?:kuat|tepat|rajih|benar)|yang lebih tepat|"
                         r"yang rajih|kesimpulan|dengan demikian|intinya|walhasil|dapat disimpulkan)", re.I)

# ================================================================ cek kalimat (grounding)
_FILLER = set("""kita kamu teman sahabat yuk nah jadi karena bahwa namun tetapi tapi sebagian ulama para pendapat berpendapat
menurut dalam hal tersebut sangat penting untuk dengan adalah yang bisa dapat akan juga maka saat ketika setelah sebelum
agama islam rasulullah nabi hadits hadis dalil ini itu ada lebih memang tentang bagi oleh pada dari atau dan sebuah seperti
mereka beliau kalau jika apabila sehingga hingga masih sudah belum perlu harus begitu begini orang sering kali
menjadi tidak bukan hanya cukup lain lainnya sama secara artinya maksudnya yaitu yakni berarti menunjukkan menjelaskan
menyebutkan disebutkan dijelaskan diriwayatkan riwayat shallallahu alaihi sallam allah subhanahu taala muhammad saw swt
pertama kedua ketiga terakhir kemudian lalu selain juga pula sendiri setiap semua kedua dasar dasarnya landasan alasan
alasannya sebab sebabnya pandangan kalangan pihak lainnya inilah itulah tadi berikut sebagai mari simak perhatikan
ingat tahu ketahui mengetahui paham memahami pahami penjelasan menjelaskannya diketahui terkait kaitan kaitannya
hubungan berhubungan topik bahas membahas pembahasan soal masalah persoalan pertanyaan bertanya jawab jawabannya
umat muslim kaum saudara saudaraku ustadz ustad insya allah wallahu alam""".split())
_HUKUM = re.compile(r"\b(?:di|ter|mem|men|me|ber|ke)?(boleh|mubah|makruh|haram|wajib|sunn?ah|batal|larang|bid['’]?ah|dosa|najis)"
                    r"(?:kan|an|nya|i|lah)?\b", re.I)
_QUANT = re.compile(r"\b(banyak|mayoritas|jumhur|semua|seluruh|sepakat|ijma['’]?|kebanyakan|selalu|pernah|pasti|mutlak|"
                    r"hanya|satu-satunya|terbaik|paling)\b", re.I)
_NEG = {"tidak", "tidaklah", "bukan", "bukanlah", "nggak", "gak", "tak", "tanpa", "jangan"}
_PRE = re.compile(r"^(meng|meny|mem|men|me|ber|di|ter|peng|pem|pen|pe|ke|se)")


def _hukum_forms(text):
    """{(kata_hukum, dinegasikan?)} — 'tidak makruh' ≠ 'makruh'."""
    toks = re.findall(r"[a-z'’]+", (text or "").lower())
    out = set()
    for i, t in enumerate(toks):
        m = _HUKUM.fullmatch(t)
        if m:
            out.add((m.group(1).replace("’", "'"), any(x in _NEG for x in toks[max(0, i - 3):i])))
    return out
_SUF = re.compile(r"(nya|lah|kan|an|i)$")


def _stem(w):
    return _SUF.sub("", _PRE.sub("", w))


def _in(w, src):
    if w in src:
        return True
    if len(w) >= 7 and w[:6] in src:
        return True
    s = _stem(w)
    return len(s) >= 4 and s in src


def _sentences(t):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", (t or "").strip()) if s.strip()]


def grounded(text, src, min_support=0.6, topic=""):
    """Kalimat-kalimat `text` yang didukung `src` (teks bahan adegan). Kata hukum & angka harus ada di `src`
    (bukan cukup di judul topik); kata biasa boleh dari `src` atau `topic`. Return (teks_bersih, jumlah_dibuang)."""
    low = (src or "").lower()
    topic_words = set(re.findall(r"[a-z]{4,}", (topic or "").lower()))
    src_forms = _hukum_forms(low)
    keep, drop = [], 0
    for s in _sentences(text):
        sl = s.lower()
        forms = _hukum_forms(sl)
        why = ""
        if forms - src_forms:
            why = "hukum/negasi tidak sama dengan bahan"
        elif any(q.group(1).lower() not in low for q in _QUANT.finditer(sl)):
            why = "kata jumlah (banyak/sepakat/…) tidak ada di bahan"
        elif any(n not in low for n in re.findall(r"\d+", sl)):
            why = "angka tidak ada di bahan"
        elif (forms or _QUANT.search(sl)) and R.match_score(s, src) < 0.7:
            why = "kalimat hukum harus mengikuti redaksi bahan"
        else:
            # kata dari judul topik netral (tidak menambah dukungan): yang dinilai kata isi lainnya
            ws = [w for w in re.findall(r"[a-z]{4,}", sl) if w not in _FILLER and w not in topic_words]
            sup = (sum(1 for w in ws if _in(w, low)) / len(ws)) if ws else 1.0
            if sup < min_support:
                why = f"hanya {int(sup * 100)}% kata ada di bahan"
        if why:
            drop += 1
            DROPPED.append((s, why))
            continue
        keep.append(s if s[-1] in ".!?" else s + ".")
    return " ".join(keep), drop


DROPPED = []          # (kalimat, alasan) — untuk log


_LEAD = re.compile(r"^(artinya|atinya|terjemahnya)\s*:\s*|^(sedangkan|namun|adapun|dan|sehingga|jadi|maka|lalu|kemudian|"
                   r"pertama|kedua|ketiga|selain itu|sementara itu|di sisi lain)\s*[,]?\s+", re.I)


def _tidy(t):
    t = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", t or "")).strip(" “”\"'")
    for _ in range(2):
        t = _LEAD.sub("", t).strip()
    return t[:1].upper() + t[1:] if t else t


def quote_narasi(facts_, n, prefix=""):
    """Narasi dari kutipan bahan apa adanya, dipotong di batas KALIMAT (bukan di tengah kalimat)."""
    out, cnt = [], len(prefix.split())
    for f in facts_:
        for s in _sentences(_tidy(f.get("kutipan", ""))):
            w = len(s.split())
            if out and cnt + w > n + 6:
                break
            out.append(s if s[-1] in ".!?" else s + ".")
            cnt += w
        if cnt >= n:
            break
    return (prefix + " ".join(out)).strip()


def _cut_words(t, n):
    w = (t or "").split()
    if len(w) <= n:
        return " ".join(w)
    out = " ".join(w[:n]).rstrip(",;:")
    return out + "…"


# ================================================================ penyusun kerangka
def _rank(items, kw):
    return sorted(items, key=lambda x: -(R.relevance(kw, x.get("kutipan", "")) + (0.5 if x.get("skor", 0) >= 0.9 else 0)))


def build_outline(facts, topik, kw, titles=None):
    """Urutan adegan + fakta milik tiap adegan. Tanpa AI.
    Fakta & dalil wajib menyebut ≥2 kata kunci topik (judul artikel sumbernya yang relevan dihitung +1),
    agar dalil/kalimat yang hanya kebetulan menyebut 'wudhu' tidak ikut masuk."""
    titles = titles or {}
    need = min(2, len(kw))
    # kata kunci 'umum' (muncul di >60% bahan, mis. 'wudhu' pada topik wudhu) tidak cukup untuk menyebut sesuatu relevan
    allt = [x.get("kutipan", "").lower() for k in ("alasan", "catatan", "hikmah", "dalil") for x in facts.get(k, [])]
    umum = {w for w in kw if allt and sum(1 for t in allt if w in t) / len(allt) > 0.6}
    beda = (kw - umum) or kw

    def near(d):                                                 # kutipan + paragraf tepat sebelumnya
        return d.get("kutipan", "") + " " + ((d.get("konteks2") or d.get("konteks") or "").split("\n")[0])

    pool = []                                                     # fakta non-dalil (alasan/hikmah/catatan)
    for k in ("alasan", "catatan", "hikmah"):
        for it in facts.get(k, []):
            t = it.get("kutipan", "")
            rel = R.relevance(kw, t) + (1 if R.relevance(kw, titles.get(it.get("url", ""), "")) >= 2 else 0)
            if rel >= need and R.relevance(beda, t + " " + titles.get(it.get("url", ""), "")) >= 1:
                pool.append(dict(it, _jenis=k, _sikap=stance(t)))
    dalil = [dict(d, _sikap=stance(d.get("konteks2") or d.get("konteks") or "")) for d in facts.get("dalil", [])
             if R.relevance(kw, near(d)) >= need and R.relevance(beda, near(d)) >= 1]
    # urutan: ayat & riwayat terkuat (Bukhari dan Muslim > Bukhari/Muslim > lainnya) dulu, lalu relevansi;
    # hadits panjang (sulit dibaca di layar) dan yang disebut lemah di bahan diturunkan
    def _kuat(d):
        if d.get("jenis") == "quran":
            return 3
        pr = (d.get("perawi") or "").lower()
        b, m = "bukh" in pr, "muslim" in pr
        return 2 if (b and m) else 1 if (b or m) else 0

    dalil.sort(key=lambda d: -(_kuat(d) * 2 + min(d.get("relevan", 0), 4) - (1.5 if len(d.get("kutipan", "")) > 320 else 0)
                               - (3 if _WEAK.search(d.get("derajat", "")) else 0)))
    A = [x for x in pool if x["_sikap"] == "A"]
    B = [x for x in pool if x["_sikap"] == "B"]
    dA = [d for d in dalil if d["_sikap"] == "A"]
    dB = [d for d in dalil if d["_sikap"] == "B"]
    khilaf = (A or dA) and (B or dB) and len(A) + len(dA) >= 2 and len(B) + len(dB) >= 2
    used = set()

    def take(items, n):
        out = []
        for it in items:
            key = re.sub(r"\W+", "", it.get("kutipan", "").lower())[:60]
            if key in used:
                continue
            used.add(key)
            out.append(it)
            if len(out) >= n:
                break
        return out

    sc = [{"peran": "pembuka"}]
    netral = [x for x in pool if x["_sikap"] is None and x["_jenis"] == "alasan"] or [x for x in pool if x["_sikap"] is None]
    intro = take(_rank(netral, kw), 2)
    if intro:
        sc.append({"peran": "pengantar", "fakta": intro})
    if khilaf:
        labB = _label_B(B + dB)
        for grp, dd, lab in ((A, dA, "Boleh"), (B, dB, labB)):
            f = take(_rank(grp, kw), 2)
            dd = [d for d in dd if len(d.get("kutipan", "")) <= 320] or dd       # hadits panjang terpotong di layar
            dl = take([d for d in dd if not _WEAK.search(d.get("derajat", ""))] + [d for d in dd if _WEAK.search(d.get("derajat", ""))], 2)
            if not f and dl:
                f = [{"kutipan": dl[0].get("konteks2", "")[-300:]}]
            sc.append({"peran": "pendapat", "label": lab, "fakta": f})
            for d in dl:
                sc.append({"peran": "dalil", "label": lab, "dalil": d})
    else:
        labB = ""
        dl = take(dalil, 3)
        al = take(_rank([x for x in pool if x["_jenis"] == "alasan"], kw), 4)
        if dl:
            sc.append({"peran": "dalil", "dalil": dl[0]})
        if al:
            sc.append({"peran": "penjelasan", "fakta": al[:2]})
        for d in dl[1:]:
            sc.append({"peran": "dalil", "dalil": d})
        if al[2:]:
            sc.append({"peran": "penjelasan", "fakta": al[2:]})
    hik = take(_rank([x for x in pool if x["_jenis"] == "hikmah"], kw), 3)
    if len(hik) >= 1:
        sc.append({"peran": "hikmah", "fakta": hik})
    lk = facts.get("langkah", [])[:6]
    if len(lk) >= 2 and not khilaf:
        sc.append({"peran": "langkah", "fakta": lk})
    # catatan derajat hadits yang dipakai
    used_d = [s["dalil"] for s in sc if s.get("dalil") and s["dalil"].get("jenis") != "quran"]
    der = [d for d in used_d if d.get("derajat") and _DERAJAT.search(d["derajat"])]
    der_f = take(_rank([x for x in pool if _DERAJAT.search(x.get("kutipan", "")) and not _KESIMPULAN.search(x.get("kutipan", ""))
                        and re.search(r"hadi[st]|riwayat|sanad|perawi", x.get("kutipan", ""), re.I)], kw), 1)
    if any(_WEAK.search(d["derajat"]) for d in der) or der_f:
        sc.append({"peran": "derajat", "dalil_list": der, "fakta": der_f})
    # kesimpulan: kalimat bahan yang memang menyimpulkan (jumhur / pendapat yang kuat / …)
    kes = take(_rank([x for x in pool if _KESIMPULAN.search(x.get("kutipan", ""))], kw), 2)
    if not kes:                                                   # tidak ada kesimpulan eksplisit: pakai catatan ulama
        kes = take(_rank([x for x in pool if x["_jenis"] == "catatan"], kw), 1)
    sc.append({"peran": "kesimpulan", "fakta": kes, "khilaf": bool(khilaf), "label": labB})
    # sisa fakta relevan untuk menambah bobot bila adegan masih sedikit
    sisa = take(_rank([x for x in pool], kw), 4)
    while len(sc) < 8 and sisa:
        sc.insert(-1, {"peran": "penjelasan", "fakta": sisa[:2]})
        sisa = sisa[2:]
    sc.append({"peran": "penutup", "khilaf": bool(khilaf), "label": labB})
    return sc, bool(khilaf)


# ================================================================ anggaran durasi
def _est_words(sc):
    """Kata yang DIUCAPKAN: narasi + (penjelasan & terjemah dalil yang dibacakan)."""
    n = len((sc.get("narasi") or "").split())
    if sc["tipe"] in ("quran", "hadits"):
        n += len((sc.get("penjelasan") or "").split()) + len((sc.get("kutipan") or "").split())
    return n


def _fit_budget(out, tag, cfg, log):
    """Jaga perkiraan durasi ≈ target_sec (±2,4 kata/detik). Kurangi berurutan: dalil ke-2 dalam satu pendapat,
    adegan hikmah, lalu kalimat terakhir adegan terpanjang (bukan pembuka/penutup/kesimpulan, minimal 2 kalimat)."""
    budget = int(float(cfg.get("max_video_sec", cfg.get("target_sec", 90))) * 2.4 * 0.95)
    role = {i: (p, lab) for i, p, lab in tag}
    rows = [[x, *role.get(i, ("", None))] for i, x in enumerate(out)]          # [adegan, peran, label]
    total = lambda: sum(_est_words(r[0]) for r in rows)
    start = total()
    if start <= budget:
        return out
    # 1) dalil ke-2 (dan seterusnya) pada pendapat yang sama, yang terpanjang dulu
    seen, extra = set(), []
    for r in rows:
        if r[1] == "dalil":
            if r[2] in seen:
                extra.append(r)
            seen.add(r[2])
    for r in reversed(extra):                          # dalil urutan belakang (lebih lemah/kurang relevan) dibuang dulu
        if total() <= budget:
            break
        rows = [x for x in rows if x is not r]
    # 2) adegan hikmah
    for r in [r for r in rows if r[1] == "hikmah"]:
        if total() > budget:
            rows = [x for x in rows if x is not r]
    # 3) kalimat terakhir adegan terpanjang (sisakan minimal 1 kalimat)
    for _ in range(40):
        if total() <= budget:
            break
        cand = []
        for r in rows:
            if r[1] in ("pembuka", "penutup", "kesimpulan"):
                continue
            f = "penjelasan" if r[0]["tipe"] in ("quran", "hadits") else "narasi"
            if len(_sentences(r[0].get(f))) >= 2:
                cand.append((_est_words(r[0]), id(r), r, f))
        if not cand:
            break
        _, _, r, f = max(cand, key=lambda c: c[0])
        r[0][f] = " ".join(_sentences(r[0][f])[:-1])
    log(f"   ⏱️ naskah dirampingkan agar ±{cfg.get('max_video_sec', cfg.get('target_sec'))} detik: "
        f"{start} → {total()} kata terucap (termasuk bacaan dalil)")
    return [r[0] for r in rows]


# ================================================================ penulis per adegan
_ROLE = {
    "pengantar": "Jelaskan duduk persoalan topik ini secara singkat untuk orang awam",
    "pendapat": "Sampaikan bahwa sebagian ulama berpendapat hukumnya {label}, beserta alasan mereka",
    "penjelasan": "Jelaskan isi bahan ini dengan bahasa lisan yang mudah dipahami",
    "hikmah": "Jelaskan hikmah/pelajaran dari bahan ini",
    "langkah": "Jelaskan urutan tata cara dari bahan ini",
    "derajat": "Sampaikan dengan jujur penilaian ulama hadits tentang kekuatan (derajat) hadits yang disebut di bahan",
    "kesimpulan": "Simpulkan sesuai bahan",
}


def _src_text(facts):
    return "\n".join("- " + f.get("kutipan", "") for f in facts if f.get("kutipan"))


def _perawi_lisan(p):
    p = re.sub(r"^HR\.?\s*", "", p or "").strip()
    p = re.sub(r"\s*\d+", "", p)
    return re.sub(r"\s+", " ", p).strip(" ,")


def write_from_outline(outline, khilaf, facts, topik, cfg, log, ask, clean):
    """ask(prompt, max_tokens, check) -> hasil; clean(teks, n) -> teks bersih."""
    import aw_doodle as D
    target = int(cfg.get("target_words", 140))
    talk = [s for s in outline if s["peran"] not in ("pembuka", "penutup")]
    n_dalil = sum(1 for s in outline if s["peran"] == "dalil")
    # anggaran kata: pembuka+penutup ±30 kata, pengantar dalil ±8 kata/dalil; sisanya dibagi rata
    per = max(18, min(40, (target - 30 - 8 * n_dalil) // max(1, len(talk))))
    core = R.core_query(topik)
    topic_low = (topik + " " + core).lower()
    out, dropped_total = [], 0
    DROPPED.clear()

    def llm(src, instr, n, extra_json='"teks": "inti adegan, maks 8 kata"'):
        prompt = (f"TOPIK VIDEO: {topik}\n\nBAHAN ADEGAN INI (satu-satunya yang boleh dipakai):\n{src}\n\n"
                  f"TUGAS: {instr}. Tulis {n}-{n + 12} kata, 2-4 kalimat lisan yang hangat & sopan untuk orang awam. "
                  "HANYA dari bahan di atas: jangan menambah hukum, dalil, angka, nama, atau klaim lain. "
                  "Jangan menyebut nama situs/website. Jangan memakai emoji.\n"
                  f'Balas JSON: {{"narasi": "...", {extra_json}}}')

        def check(d):
            if not isinstance(d, dict) or not isinstance(d.get("narasi"), str) or len(d["narasi"].split()) < 6:
                raise ValueError("narasi kosong")
            return d
        try:
            return ask(prompt, 500, check)
        except RuntimeError as e:
            log(f"      ⚠️ AI gagal ({str(e)[:60]}) — pakai kutipan bahan")
            return {}

    def narasi_ok(d, src, n, fallback):
        nonlocal dropped_total
        txt, drop = grounded(clean(d.get("narasi", ""), 600), src, topic=topic_low)
        dropped_total += drop
        if len(txt.split()) < max(10, int(n * 0.5)):
            txt = fallback                                         # kutipan bahan apa adanya (pasti benar)
        return clean(txt, 520)

    def fb(facts_, prefix=""):
        return quote_narasi(facts_, per, prefix)

    tag = []                                                     # (indeks adegan out, peran, label) untuk perampingan

    for i, s in enumerate(outline):
        p = s["peran"]
        if out and (not tag or tag[-1][0] != len(out) - 1):
            tag.append((len(out) - 1, outline[i - 1]["peran"], outline[i - 1].get("label")))
        log(f"   🧩 adegan {i + 1}: {p}" + (f" ({s['label']})" if s.get("label") else ""))
        if p == "pembuka":
            q = re.split(r"(?<=\?)", topik.strip())[0].strip()
            q = q if q.endswith("?") else core + "?"
            out.append({"tipe": "tanya", "narasi": f"{q} Yuk, kita lihat apa kata ulama dan dalilnya.",
                        "teks": _cut_words(core + "?", 9)})
        elif p == "penutup":
            if s.get("khilaf"):
                out.append({"tipe": "penutup", "narasi": "Itulah dua pendapat ulama beserta dalilnya. Kamu biasanya bagaimana? Tulis di komentar, ya.",
                            "tanya": "Kamu ikut pendapat yang mana?", "a": "Boleh", "b": s.get("label") or "Makruh"})
            else:
                out.append({"tipe": "penutup", "narasi": "Semoga bermanfaat. Sudah tahu sebelumnya? Tulis di komentar, ya.",
                            "tanya": "Sudah tahu sebelumnya?", "a": "Sudah tahu", "b": "Baru tahu"})
        elif p == "dalil":
            d = s["dalil"]
            src = (d.get("konteks2") or d.get("konteks") or "") + "\n" + d.get("kutipan", "") + "\n" + d.get("derajat", "")
            lab = s.get("label")
            instr = ("Jelaskan makna dalil berikut" + (f" dan mengapa ulama yang berpendapat '{lab}' memakainya sebagai dasar" if lab
                                                       else " dan kaitannya dengan topik") +
                     (". Bahan menyebut derajatnya; sampaikan dengan jujur" if _WEAK.search(d.get("derajat", "")) else ""))
            dd = llm(f"DALIL: “{d.get('kutipan', '')}” ({d.get('perawi') or 'QS ' + str(d.get('surat')) + ':' + str(d.get('ayat'))})\n"
                     f"KONTEKS DI ARTIKEL: {src}", instr, per, '"teks": ""')
            fbk = (d.get("konteks2") or d.get("konteks") or "").split("\n")[0]
            pen = narasi_ok(dd, src, per, quote_narasi([{"kutipan": fbk}], per) if fbk else "")
            if d.get("jenis") == "quran":
                nama = d.get("nama") or f"surat ke-{d['surat']}"
                out.append({"tipe": "quran", "narasi": f"Allah berfirman dalam surat {nama} ayat {d['ayat']}.",
                            "surat": d["surat"], "ayat": d["ayat"], "kutipan": d.get("kutipan", ""), "penjelasan": pen})
            else:
                pr = _perawi_lisan(d.get("perawi"))
                pre = f"Dalil pendapat {lab.lower()}, hadits riwayat {pr}." if lab else f"Dalilnya, hadits riwayat {pr}."
                out.append({"tipe": "hadits", "narasi": pre, "kutipan": d.get("kutipan", ""), "perawi": d.get("perawi", ""),
                            "penjelasan": pen})
        elif p == "hikmah" and len(s["fakta"]) >= 2:
            src = _src_text(s["fakta"])
            dd = llm(src, _ROLE["hikmah"], per, '"judul": "maks 4 kata", "poin": ["maks 5 kata", "maks 5 kata", "maks 5 kata"]')
            nar = narasi_ok(dd, src, per, fb(s["fakta"]))
            pts = []
            for x in (dd.get("poin") or [])[:3]:
                if isinstance(x, str):
                    g, _ = grounded(x.strip(" .") + ".", src, 0.5, topic=topic_low)
                    if g:
                        pts.append({"ikon": "", "teks": _cut_words(g.rstrip("."), 6)})
            if len(pts) >= 2:
                out.append({"tipe": "poin", "narasi": nar, "judul": clean(dd.get("judul") or "Hikmahnya", 40), "poin": pts})
            else:
                out.append({"tipe": "bicara", "narasi": nar, "teks": "Hikmahnya"})
        elif p == "langkah":
            src = _src_text(s["fakta"])
            dd = llm(src, _ROLE["langkah"], per, '"judul": "maks 4 kata", "langkah": ["maks 6 kata", "..."]')
            nar = narasi_ok(dd, src, per, fb(s["fakta"]))
            lk = []
            for x in (dd.get("langkah") or [])[:5]:
                if isinstance(x, str):
                    g, _ = grounded(x.strip(" .") + ".", src, 0.5, topic=topic_low)
                    if g:
                        lk.append(_cut_words(g.rstrip("."), 6))
            if len(lk) < 2:
                lk = [_cut_words(f.get("kutipan", ""), 6) for f in s["fakta"][:5]]
            out.append({"tipe": "langkah", "narasi": nar, "judul": clean(dd.get("judul") or "Caranya", 40), "langkah": lk})
        elif p == "derajat":
            parts = [f"Hadits “{_cut_words(d.get('kutipan', ''), 12)}” ({d.get('perawi', '')}): {d.get('derajat', '')}"
                     for d in s.get("dalil_list", [])]
            src = "\n".join(parts) + "\n" + _src_text(s.get("fakta", []))
            dd = llm(src, _ROLE["derajat"], per)
            nar = narasi_ok(dd, src, per, fb(s.get("fakta", []) or [{"kutipan": d.get("derajat", "")} for d in s.get("dalil_list", [])],
                                             "Catatan ulama hadits: "))
            out.append({"tipe": "bicara", "narasi": nar, "teks": "Catatan derajat hadits", "ikon": ["buku", "lampu"]})
        elif p == "kesimpulan":
            # TANPA AI: kesimpulan hukum terlalu mudah bergeser maknanya bila diringkas model kecil -> kutip bahan apa adanya
            nar = quote_narasi(s.get("fakta", []), per + 10, "Salah satu rujukan menyimpulkan: ") if s.get("fakta") else ""
            if s.get("khilaf"):
                nar = (nar + " " if nar else "") + ("Jadi, ulama berbeda pendapat dalam masalah ini. Ikuti pendapat yang kamu yakini, "
                                                    "dan tanyakan ke ustadz setempat bila ragu.")
            if not nar:
                continue
            out.append({"tipe": "fakta", "narasi": clean(nar, 520), "besar": "Beda pendapat" if s.get("khilaf") else "Intinya",
                        "kecil": _cut_words(core, 10)})
        else:                                                     # pengantar / pendapat / penjelasan / hikmah(1 fakta)
            src = _src_text(s.get("fakta", []))
            if not src:
                continue
            instr = _ROLE.get(p, _ROLE["penjelasan"]).format(label=(s.get("label") or "").lower())
            dd = llm(src, instr, per)
            prefix = f"Sebagian ulama berpendapat hukumnya {s['label'].lower()}. " if p == "pendapat" else ""
            nar = narasi_ok(dd, src, per, fb(s["fakta"], prefix))
            if p == "pendapat" and s["label"].lower() not in nar.lower():
                nar = prefix + nar                                 # pastikan penonton tahu ini pendapat yang mana
            teks = clean(dd.get("teks"), 80)
            if teks and not grounded(teks + ".", src, 0.5, topic=topic_low)[0]:
                teks = ""
            if p == "pendapat":
                teks = f"Pendapat: {s['label']}" + (f" — {teks}" if teks and len(teks) < 40 else "")
            out.append({"tipe": "bicara", "narasi": nar, "teks": teks or _cut_words(nar, 8)})
    if out and (not tag or tag[-1][0] != len(out) - 1):
        tag.append((len(out) - 1, outline[-1]["peran"], outline[-1].get("label")))
    out = _fit_budget(out, tag, cfg, log)
    if DROPPED:
        log(f"   🧹 {len(DROPPED)} kalimat/label AI dibuang karena tidak didukung bahan:")
        for s_, why in DROPPED:
            log(f"      ✂️ “{_cut_words(s_, 16)}” — {why}")
    kws = [w for w in core.split() if w.lower() in R.key_words(core)][:4]
    return {"judul_pendek": _cut_words(core, 6) + "?", "judul": topik.strip()[:90],
            "deskripsi": f"{core}: penjelasan ulama beserta dalilnya, disusun dari sumber kajian terpercaya.",
            "hashtag": ["#" + re.sub(r"\W", "", w.capitalize()) for w in kws], "adegan": out}
