"""
Riset bahan: cari artikel tentang topik di web (Bing/Google lewat ddgs), baca isinya, dan deteksi rujukan ayat.
Ayat Al-Qur'an diverifikasi ke API equran.id (teks Arab + terjemahan Kemenag), di-cache di cache/quran/.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

import requests

import aw_common as C

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36", "Accept-Language": "id-ID,id;q=0.9,en;q=0.6"}
QURAN_API = "https://equran.id/api/v2/surat"


# ================================================================ pencarian
def _domain(url):
    d = urllib.parse.urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d


def _in(domain, lst):
    return any(domain == x or domain.endswith("." + x) for x in lst)


_CLICKBAIT = re.compile(r"\b(ini faktanya|ini dia|ini jawabannya|ini penjelasannya|begini penjelasannya|begini|ternyata|simak|"
                        r"yuk|wajib tahu|harus tahu|perlu tahu|jangan salah|banyak yang (?:belum|tidak|gak|nggak) tahu|"
                        r"faktanya|penjelasannya|jawabannya|lho|loh|sih|dong|kok|nih|lengkap|terbaru|viral)\b", re.I)
_ASK = re.compile(r"\b(itu|apakah|apa|benarkah|betulkah|kenapa|mengapa|bagaimana|gimana|kah)\b", re.I)
# kata umum yang tidak membedakan topik (tidak dipakai untuk menilai relevansi)
_GENERIC = {"air", "pakai", "memakai", "hukum", "boleh", "orang", "kita", "kamu", "faktanya", "islam", "muslim", "menurut",
            "sama", "bisa", "lebih", "sangat", "sudah", "belum", "agar", "supaya", "sebelum", "sesudah", "setelah", "laki"}


def core_query(topik):
    """Judul clickbait -> kata kunci pencarian. 'Mengelap air wudhu pakai handuk itu makruh? Ini faktanya!'
    -> 'Mengelap air wudhu pakai handuk makruh'."""
    t = re.sub(r"[\"“”‘’!?:;,.()\[\]|/]+", " ", topik or "")
    t = _CLICKBAIT.sub(" ", t)
    t = _ASK.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) >= 4 else (topik or "").strip()


def key_words(s):
    return {w for w in _words(s) if w not in _GENERIC}


def short_query(core):
    """Hanya kata kunci pembeda, urutan asli: 'Mengelap air wudhu pakai handuk makruh' -> 'Mengelap wudhu handuk makruh'."""
    kw = key_words(core)
    out = [w for w in core.split() if w.lower() in kw]
    return " ".join(out[:5]) if len(out) >= 2 else core


def relevance(words, text):
    """Berapa kata kunci topik muncul di teks (cocok juga untuk imbuhan: wudhu ~ berwudhu/wudhunya)."""
    low = (text or "").lower()
    return sum(1 for w in words if (w in low if len(w) >= 4 else re.search(r"\b" + w + r"\b", low)))


def _site_groups(cfg, start=0, stop=12, size=3):
    dom = cfg.get("trusted_domains", [])[start:stop]
    return [" OR ".join(f"site:{d}" for d in dom[i:i + size]) for i in range(0, len(dom), size)]


def search_queries(topik, cfg, sudut=""):
    core = core_query(topik)
    hukum = core if re.match(r"(?i)hukum\b", core) else "hukum " + core
    qs = [core, hukum, f"{core} dalil hadits", f"{core} menurut ulama"]
    if sudut:
        qs.insert(1, f"{core} {sudut}")
    qs += [f"{short_query(core)} ({g})" for g in _site_groups(cfg)]       # mesin cari gagal bila kueri site: terlalu panjang
    if core.lower() != (topik or "").strip().lower():
        qs.append(topik.strip())
    return qs


def search(topik, cfg, sudut="", log=print, queries=None, seen=None):
    from ddgs import DDGS
    queries = queries or search_queries(topik, cfg, sudut)
    seen, res = (seen if seen is not None else set()), []
    n = int(cfg.get("search_results", 10))
    for q in queries:
        try:
            hits = DDGS().text(q, region="id-id", max_results=n, backend="bing,google,yahoo")
        except Exception as e:
            log(f"   ⚠️ cari '{q}': {str(e)[:90]}")
            continue
        for h in hits:
            url = h.get("href") or ""
            dom = _domain(url)
            if (not url.startswith("http") or url in seen or _in(dom, cfg.get("blocked_domains", [])) or url.lower().endswith(".pdf")
                    or re.search(r"/(tag|tags|category|kategori|topik|search|page/\d+)(/|$|\?)", url.lower())):
                continue
            seen.add(url)
            res.append({"url": url, "title": (h.get("title") or "").strip(), "snippet": (h.get("body") or "").strip(),
                        "domain": dom, "trusted": _in(dom, cfg.get("trusted_domains", []))})
        time.sleep(0.6)
    words = key_words(core_query(topik) + " " + sudut)
    for r in res:
        r["score"] = (3 if r["trusted"] else 0) + relevance(words, r["title"] + " " + r["snippet"])
    res.sort(key=lambda r: -r["score"])
    return res


# ================================================================ baca artikel
_JUNK = re.compile(r"(baca juga|simak juga|artikel terkait|share|bagikan|follow|ikuti kami|copyright|hak cipta|"
                   r"download|unduh aplikasi|klik di sini|whatsapp|telegram|newsletter|komentar|berita terkait|"
                   r"advertisement|iklan|scroll to|lihat juga)", re.I)


_ALLPAGE = {"tribunnews.com": "page=all", "kompas.com": "page=all", "sindonews.com": "showpage=all", "okezone.com": "page=all"}


def fetch_text(url, timeout=25):
    """Judul + teks artikel. Situs berita berhalaman (Tribun/Kompas/…) dicoba versi satu halaman bila isinya pendek."""
    title, text = _fetch_text(url, timeout)
    dom = _domain(url)
    q = next((v for k, v in _ALLPAGE.items() if dom == k or dom.endswith("." + k)), None)
    if q and len(text) < 1500 and q not in url:
        try:
            t2, x2 = _fetch_text(url + ("&" if "?" in url else "?") + q, timeout)
            if len(x2) > len(text):
                title, text = t2 or title, x2
        except Exception:
            pass
    return title, text


def _fetch_text(url, timeout=25):
    from bs4 import BeautifulSoup
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
    soup = BeautifulSoup(r.text, "html.parser")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:200]
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg", "button"]):
        t.decompose()
    root = None
    for sel in ["article", "[itemprop=articleBody]", ".entry-content", ".post-content", ".detail__body-text",
                ".read__content", ".content-detail", "main", ".post", "#content"]:
        cand = soup.select_one(sel)
        if cand and len(cand.get_text(" ", strip=True)) > 600:
            root = cand
            break
    root = root or soup.body or soup
    parts, seen = [], set()
    for el in root.find_all(["p", "li", "blockquote", "h2", "h3", "h4"]):
        tx = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if len(tx) < 25 or tx in seen or (len(tx) < 140 and _JUNK.search(tx)):
            continue
        seen.add(tx)
        parts.append(("## " + tx) if el.name in ("h2", "h3", "h4") else tx)
    return title, "\n".join(parts)[:24000]


def _words(s):
    stop = {"dan", "yang", "di", "ke", "dari", "itu", "ini", "untuk", "dengan", "atau", "pada", "adalah", "dalam",
            "kenapa", "mengapa", "apa", "harus", "bagaimana", "tidak", "juga", "akan", "ada", "karena", "saat", "jika"}
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in stop}


def _src_score(s):
    return ((4 if s.get("trusted") else 0) + min(s.get("relevance", 0), 6) * 1.5 + min(len(s.get("refs", [])), 3)
            + min(s.get("hadits_n", 0), 4) * 1.5 + (2 if s.get("chars", 0) >= 3000 else 0))


def _read_hits(hits, words, need, seen_urls, log, limit):
    """Baca artikel paralel; buang yang gagal / pendek / tidak membahas topik."""
    from concurrent.futures import ThreadPoolExecutor
    per_dom, cand = {}, []
    for h in hits:
        if h["url"] in seen_urls:
            continue
        if per_dom.get(h["domain"], 0) >= 2:          # maks 2 artikel per situs agar rujukan beragam
            continue
        per_dom[h["domain"]] = per_dom.get(h["domain"], 0) + 1
        cand.append(h)
        if len(cand) >= limit:
            break
    for h in cand:
        seen_urls.add(h["url"])

    def one(h):
        try:
            return h, fetch_text(h["url"]), None
        except Exception as e:
            return h, None, e

    got = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for h, res, err in ex.map(one, cand):
            if err is not None:
                log(f"   ⏭️ {h['domain']}: gagal dibuka ({str(err)[:60]})")
                continue
            title, text = res
            if len(text) < 800:
                log(f"   ⏭️ {h['domain']}: isi terlalu pendek")
                continue
            rel = relevance(words, (title or "") + "\n" + text[:15000])
            if rel < need:
                log(f"   ⏭️ {h['domain']}: tidak membahas topik ({rel}/{len(words)} kata kunci)")
                continue
            refs = find_quran_refs(text)
            had = harvest_hadits(text, words)
            h.update({"title": h["title"] or title, "text": text, "chars": len(text), "relevance": rel,
                      "refs": [f"{s}:{a}" for s, a in refs], "hadits_n": len(had), "use": False})
            got.append(h)
            log(f"   📄 {h['domain']} ({len(text)} huruf, {len(refs)} ayat, {len(had)} hadits)"
                f"{' ✓ terpercaya' if h['trusted'] else ''}")
    return got


def assess(sources, cfg):
    """Ringkasan kecukupan bahan yang dicentang (dipakai UI & gerbang naskah)."""
    use = [s for s in sources if s.get("use") and s.get("text")]
    refs = set()
    for s in use:
        refs.update(s.get("refs", []))
    had = sum(s.get("hadits_n", 0) for s in use)
    min_src = int(cfg.get("min_sources", 4))
    info = {"sumber": len(use), "terpercaya": sum(1 for s in use if s.get("trusted")), "ayat": len(refs), "hadits": had,
            "huruf": sum(s.get("chars", 0) for s in use), "min_sumber": min_src}
    kurang = []
    if len(use) < min_src:
        kurang.append(f"baru {len(use)} sumber dipakai (minimal {min_src})")
    if info["terpercaya"] < 2:
        kurang.append(f"sumber terpercaya baru {info['terpercaya']} (sebaiknya ≥2)")
    if not refs and not had:
        kurang.append("belum ada ayat/hadits di bahan")
    info["cukup"] = len(use) >= min_src
    info["kurang"] = kurang
    return info


def research(project, cfg, log=print):
    topik, sudut = project["topik"], project.get("sudut", "")
    core = core_query(topik)
    log(f"🔎 Mencari bahan: {topik}" + (f"\n   kata kunci: {core}" if core != topik.strip() else ""))
    words = key_words(core + " " + sudut) or _words(core)
    need = max(1, round(len(words) * 0.4))
    keep = [s for s in project.get("sources", []) if s.get("manual")]      # sumber manual user tetap dipertahankan
    want = int(cfg.get("sources_max", 7))
    min_src = int(cfg.get("min_sources", 4))
    seen_q, seen_urls = set(), {s.get("url") for s in keep if s.get("url")}

    hits = search(topik, cfg, sudut, log, seen=seen_q)
    log(f"   {len(hits)} hasil pencarian")
    got = _read_hits(hits, words, need, seen_urls, log, want * 2 + 4)

    # putaran 2: bahan masih sedikit / belum ada dalil -> kueri tambahan & situs terpercaya lainnya
    dalil = sum(len(s["refs"]) + s["hadits_n"] for s in got)
    if len(got) + len(keep) < want or dalil == 0 or sum(s["trusted"] for s in got) < 2:
        log(f"🔁 Bahan belum cukup ({len(got)} artikel, {dalil} dalil) — mencari lebih luas…")
        extra = [f"{core} hadits shahih", f"{core} fiqih", f"{core} rumaysho", f"{core} nu online",
                 f"{core} konsultasi syariah", f"{core} almanhaj", f"dalil {core}"]
        extra += [f"{short_query(core)} ({g})" for g in _site_groups(cfg, 12, 30)]
        hits2 = search(topik, cfg, sudut, log, queries=extra, seen=seen_q)
        log(f"   {len(hits2)} hasil tambahan")
        got += _read_hits(hits2, words, need, seen_urls, log, want * 2)

    got.sort(key=lambda s: -_src_score(s))
    for s in got[:max(want - len([k for k in keep if k.get("use")]), min_src)]:
        s["use"] = True
    project["sources"] = keep + got
    project["status"] = "riset"
    info = assess(project["sources"], cfg)
    info["kata_kunci"] = core
    project["riset"] = info
    log(f"✅ {len(got)} artikel terbaca, {info['sumber']} dipakai ({info['terpercaya']} terpercaya) · "
        f"{info['ayat']} ayat · {info['hadits']} hadits terdeteksi")
    for k in info["kurang"]:
        log(f"   ⚠️ {k}")
    if not info["cukup"]:
        log("   ⚠️ Bahan belum cukup untuk video berbobot: tambah URL artikel/catatan sendiri, atau ubah topik jadi lebih umum.")
    return project


# ================================================================ dalil hadits (tanpa AI: disalin dari teks bahan)
_PERAWI = (r"(?:Imam\s+)?(?:Al-?\s?)?(?:Bukh[aā]r[iī]|Muslim|Tirmi[dz]+[iī]|Turmu[dz]+[iī]|Abu\s+Da[wu]+d|An-?\s?Nas[aā]'?[iī]|"
           r"Nas[aā]'?[iī]|Ibnu?\s+Maj[aā]h|Ibn\s+Maj[aā]h|Ahmad|Malik|Ad-?\s?D[aā]rim[iī]|D[aā]rim[iī]|Baihaq[iī]|"
           r"Ath-?\s?Thabr[aā]n[iī]|Thabr[aā]n[iī]|Tabrani|Hakim|Ibnu\s+Hibb[aā]n|Ibnu\s+Khuzaimah|D[aā]ruquthn[iī])")
_HR_RE = re.compile(r"\(?\s*\bH\.?\s?R\.?\s*(?=[A-Z])([^)\n]{2,140})\)?")
_RIWAYAT_RE = re.compile(r"diriwayatkan\s+oleh\s+(" + _PERAWI + r"(?:\s*(?:,|dan|&)\s*" + _PERAWI + r")*)", re.I)
_QUOTE_RE = re.compile(r"[“\"]([^”\"]{20,700})[”\"]")
_DERAJAT_RE = re.compile(r"[^.]*\b(dha['’]?[iī]f|da['’]?if|lemah|tidak shahih|tidak sahih|maudhu|palsu|munkar|mursal|"
                         r"shahih|sahih|hasan)\b[^.]*\.?", re.I)
_INTRO_RE = re.compile(r"(bersabda|sabda|mengatakan|berkata|menceritakan|meriwayatkan|menuturkan|disebutkan|hadi[st]+)\s*[:,]?\s*$", re.I)


def _clean_quote(q):
    q = re.sub(r"^\s*(artinya|atinya|terjemah(?:an)?)\s*:\s*", "", q, flags=re.I)
    q = re.sub(r"\(\s*H\.?\s?R\.?[^)]*\)?", "", q)
    q = re.sub(r"\s+", " ", q).strip(" \"“”'‘’,;:(")
    q = re.sub(r"^[.…]+\s*", "", q)
    return q


def _short_perawi(s):
    s = re.split(r"\.\s+(?=[A-Z])|;|\s+dengan sanad|\s+dalam\s+(?:kitab|sunan|shahih)|\s+no\.|\s+nomor", s.strip())[0]
    s = re.sub(r"\s+", " ", s).strip(" .,(")
    return "HR. " + s[:60]


def harvest_hadits(text, words, max_items=8):
    """Kutipan hadits beserta perawi, DISALIN dari teks bahan (bukan dari AI), diurutkan dari yang paling relevan.
    Pola: “…” (HR. X) · kalimat … (HR X) · paragraf hadits lalu 'Hadis ini diriwayatkan oleh X'."""
    paras = [p.strip() for p in (text or "").split("\n")]
    out, seen = [], set()
    for i, p in enumerate(paras):
        if not p or p.startswith("## "):
            continue
        perawi = quote = None
        qi = i
        m = _HR_RE.search(p)
        if m:
            perawi = _short_perawi(m.group(1))
            before = p[:m.start()]
            qs = _QUOTE_RE.findall(before)
            quote = qs[-1] if qs else before
            if len(_clean_quote(quote)) < 20 and i > 0:          # "(HR. Bukhari)" sendirian -> hadits di paragraf sebelumnya
                quote, qi = paras[i - 1], i - 1
        else:
            m = _RIWAYAT_RE.search(p)
            if m and re.match(r"^\s*(\(|hadi[st]+\s+(ini|tersebut)|riwayat|diriwayatkan)", p, re.I) and i > 0:
                perawi, quote, qi = "HR. " + re.sub(r"\s+", " ", m.group(1)).strip(), paras[i - 1], i - 1
        if not perawi or not quote or paras[qi].startswith("## "):
            continue
        quote = _clean_quote(quote)
        if not (20 <= len(quote) <= 700) or _HR_RE.search(quote):
            continue
        sig = re.sub(r"\W+", "", quote.lower())[:60]
        if sig in seen:
            continue
        seen.add(sig)
        intro = paras[qi - 1] if qi > 0 and not paras[qi - 1].startswith("## ") else ""
        arab = ""
        if re.search(r"[؀-ۿ]{3,}", intro):          # paragraf sebelumnya = teks Arab hadits -> simpan terpisah
            arab = intro
            intro = paras[qi - 2] if qi > 1 and not paras[qi - 2].startswith("## ") else ""
            if re.search(r"[؀-ۿ]{3,}", intro):
                intro = ""
        if intro and not _INTRO_RE.search(intro) and len(intro) > 260:
            intro = ""
        around = " ".join(x for x in paras[i:i + 3] if not x.startswith("## "))
        der = sorted((d.group(0).strip() for d in _DERAJAT_RE.finditer(around)),
                     key=lambda x: 0 if re.search(r"dha|da['’]?if|lemah|tidak s|maudhu|palsu|munkar|mursal", x, re.I) else 1)[:1]
        rel = relevance(words, quote + " " + intro)
        der = re.sub(r"^[\d\s).,;:]+", "", der[0]).strip() if der else ""
        # konteks luas (2 paragraf non-Arab sebelum hadits) -> untuk tahu hadits ini dalil pendapat yang mana
        k2, j = [], qi - 1
        while j >= 0 and len(k2) < 2 and qi - j <= 4:
            if _HR_RE.search(paras[j]) or _RIWAYAT_RE.search(paras[j]) or _QUOTE_RE.search(paras[j]):
                break                                    # jangan mencampur konteks hadits lain
            if paras[j] and not paras[j].startswith("## ") and not re.search(r"[؀-ۿ]{3,}", paras[j]):
                k2.append(paras[j][-450:])
            j -= 1
        out.append({"jenis": "hadits", "kutipan": quote, "perawi": perawi, "konteks": intro[:220], "arab": arab[:400],
                    "konteks2": "\n".join(k2), "derajat": der[:220], "relevan": rel})
    out = [x for x in out if x["relevan"] >= 1]
    out.sort(key=lambda x: -x["relevan"])
    return out[:max_items]


def harvest_quran(text, refs, words, max_items=6):
    """Ayat yang disebut di bahan + paragraf di sekitarnya (untuk menilai relevansi); terjemah dari Kemenag."""
    paras = [p.strip() for p in (text or "").split("\n")]
    out = []
    for r in refs:
        s, a = map(int, r.split(":"))
        ctx, best = "", -1
        for i, p in enumerate(paras):
            if (s, a) in find_quran_refs(p):
                c = " ".join(paras[max(0, i - 1):i + 1])
                rv = relevance(words, c)
                if rv > best:
                    ctx, best = c, rv
        if best < 1:
            continue
        try:
            ay = get_ayat(s, a)
        except Exception:
            continue
        terj = ay["terjemah"] if len(ay["terjemah"]) <= 300 else best_sentence(ay["terjemah"], ctx)
        out.append({"jenis": "quran", "surat": s, "ayat": a, "kutipan": terj[:300], "resmi": 1.0,
                    "konteks": ctx[:220], "konteks2": ctx[-600:], "nama": ay["nama"], "relevan": best})
    out.sort(key=lambda x: -x["relevan"])
    return out[:max_items]


def add_url(project, url):
    title, text = fetch_text(url)
    if len(text) < 300:
        raise ValueError("Isi halaman terlalu pendek / tidak terbaca")
    dom = _domain(url)
    cfg = C.load_config()
    refs = find_quran_refs(text)
    words = key_words(core_query(project.get("topik", "")))
    project.setdefault("sources", []).insert(0, {
        "url": url, "title": title, "snippet": text[:200], "domain": dom, "trusted": _in(dom, cfg.get("trusted_domains", [])),
        "text": text, "chars": len(text), "relevance": relevance(words, text), "refs": [f"{s}:{a}" for s, a in refs],
        "hadits_n": len(harvest_hadits(text, words)), "use": True, "manual": True})
    return project


def add_note(project, title, text):
    refs = find_quran_refs(text)
    words = key_words(core_query(project.get("topik", "")))
    project.setdefault("sources", []).insert(0, {
        "url": "", "title": title or "Catatan sendiri", "snippet": text[:200], "domain": "catatan", "trusted": True,
        "text": text, "chars": len(text), "relevance": relevance(words, text), "refs": [f"{s}:{a}" for s, a in refs],
        "hadits_n": len(harvest_hadits(text, words)), "use": True, "manual": True})
    return project


# ================================================================ Al-Qur'an (equran.id)
def _get_json(url, cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)["data"]
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def surah_list():
    return _get_json(QURAN_API, os.path.join(C.CACHE_DIR, "quran", "surat.json"))


def surah(n):
    return _get_json(f"{QURAN_API}/{int(n)}", os.path.join(C.CACHE_DIR, "quran", f"{int(n)}.json"))


def _norm_name(s):
    s = s.lower().replace("’", "'").replace("`", "'")
    s = re.sub(r"^(al|an|ar|at|as|asy|ash|ad|adz|az|aš)[\s\-']+", "", s.strip())
    s = re.sub(r"[^a-z]", "", s)
    s = re.sub(r"(a|i|u)\1+", r"\1", s).replace("dh", "d").replace("sy", "s").replace("kh", "k").replace("ts", "s")
    return s.rstrip("h")


_NAMES = None


def surah_number(name):
    """Nomor surat dari nama ('Al-Maidah', 'An Nisa', '5'). None kalau tidak dikenal."""
    global _NAMES
    name = (name or "").strip()
    if name.isdigit():
        n = int(name)
        return n if 1 <= n <= 114 else None
    if _NAMES is None:
        try:
            _NAMES = {_norm_name(s["namaLatin"]): s["nomor"] for s in surah_list()}
        except Exception:
            _NAMES = {}
    key = _norm_name(name)
    if key in _NAMES:
        return _NAMES[key]
    best = max(_NAMES.items(), key=lambda kv: SequenceMatcher(None, kv[0], key).ratio(), default=None)
    if best and SequenceMatcher(None, best[0], key).ratio() >= 0.84:
        return best[1]
    return None


_REF_RE = re.compile(r"(?:\bQ\.?\s?S\.?|\bsurah|\bsurat)\s*\.?\s*([A-Za-z][A-Za-z'’`\-]*(?:[\s\-][A-Za-z'’`]+){0,2}?)\s*"
                     r"(?:\[\s*\d{1,3}\s*\]|\(\s*\d{1,3}\s*\))?\s*(?::|ayat|ayah|,\s*ayat)\s*(\d{1,3})", re.I)
_REF_NUM = re.compile(r"\bQ\.?\s?S\.?\s*(\d{1,3})\s*:\s*(\d{1,3})", re.I)


def find_quran_refs(text):
    found = []
    for m in _REF_NUM.finditer(text or ""):
        found.append((int(m.group(1)), int(m.group(2))))
    for m in _REF_RE.finditer(text or ""):
        n = surah_number(m.group(1))
        if n:
            found.append((n, int(m.group(2))))
    out = []
    for r in found:
        if r not in out and 1 <= r[0] <= 114:
            out.append(r)
    return out


def get_ayat(s, a):
    d = surah(s)
    for x in d["ayat"]:
        if int(x["nomorAyat"]) == int(a):
            return {"surat": int(s), "ayat": int(a), "nama": d["namaLatin"], "arab": x["teksArab"],
                    "terjemah": re.sub(r"\s+", " ", x["teksIndonesia"]).strip(), "jumlah_ayat": d["jumlahAyat"]}
    raise ValueError(f"Ayat {a} tidak ada di surat {d['namaLatin']} ({d['jumlahAyat']} ayat)")


# ================================================================ pencocokan teks (verifikasi kutipan)
def _toks(s):
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def match_score(quote, text):
    """Seberapa persis `quote` ada di `text` (0..1): porsi kata kutipan yang muncul berurutan di jendela terbaik."""
    q, t = _toks(quote), _toks(text)
    if not q or not t:
        return 0.0
    qs = set(q)
    win = len(q)
    best = 0.0
    step = max(1, win // 4)
    for i in range(0, max(1, len(t) - win + 1), step):
        seg = t[i:i + win + 3]
        if len(qs & set(seg)) / len(qs) < best:
            continue
        sm = SequenceMatcher(None, q, seg, autojunk=False)
        best = max(best, sum(b.size for b in sm.get_matching_blocks()) / len(q))
        if best > 0.97:
            break
    return round(best, 3)


def best_sentence(full, hint):
    """Kalimat/potongan terjemahan yang paling cocok dengan `hint` (untuk ayat panjang)."""
    parts = [p.strip() for p in re.split(r"(?<=[.;:!?])\s+", full) if len(p.strip()) > 8]
    if not parts:
        return full
    hw = set(_toks(hint))
    return max(parts, key=lambda p: len(hw & set(_toks(p))) / (1 + len(_toks(p)) ** 0.3))
