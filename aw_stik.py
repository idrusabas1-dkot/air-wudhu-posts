"""
Teater cerita STICKMAN: saat Gus Idrus menjelaskan, alur cerita diperagakan tokoh stickman di panggung besar.

  storyboard(sc, cast, cfg)   babak-babak cerita (LLM lokal, di-cache; cadangan aturan kata kunci) -- TANPA waktu
  make_cast(script, seed)     tokoh tetap satu video (penampilan diacak per video -> tiap video beda)
  plan_story(...)             babak -> waktu dari kata yang diucapkan -> StoryA
  StoryA                      menggambar panggung: latar, tokoh (pose prosedural), benda, efek, kamera, transisi, alur 1→2→3

Aturan isi: hanya orang biasa (tidak ada Nabi/Rasul/sahabat/malaikat/Allah dalam bentuk apa pun), tidak ada tanda benar/salah;
gambar hanya memperagakan situasi yang disebut narasi. Klaim hukum tetap hanya dari naskah terverifikasi.
"""
import hashlib
import json
import math
import os
import random
import re
import zlib

import cv2
import numpy as np

import aw_doodle as D
import aw_kata as K

W, H = D.W, D.H
INK = (40, 36, 32)

# ================================================================ kosakata
LATAR = ["rumah", "kamar", "dapur", "wudhu", "masjid", "halaman", "jalan", "kantor", "sekolah", "pasar"]
AKSI = ["diam", "jalan", "lari", "bicara", "lambai", "tunjuk", "mikir", "senang", "sedih", "marah", "kaget", "takut", "duduk",
        "tidur", "takbir", "berdiri_sholat", "rukuk", "sujud", "duduk_sholat", "doa", "wudhu", "cuci_tangan", "mandi", "makan",
        "minum", "baca", "kerja", "masak", "beri", "terima", "gendong", "sapu", "ngupil", "bersin", "batuk", "sakit", "telepon",
        "salaman", "peluk", "tepuk_tangan", "angguk", "geleng", "lihat_jam", "tolak", "pusing", "lapar"]
EMOSI = ["biasa", "senang", "sedih", "marah", "kaget", "bingung", "takut", "malu", "tenang"]
BENDA = ["buku", "quran", "hp", "uang", "piring", "gelas", "hadiah", "sapu", "bayi", "handuk", "tisu", "tas", "bola", "kurma"]
EFEK = ["hati", "bintang", "lampu", "tanya", "seru", "air", "cahaya", "hujan", "uang", "jam", "petir", "zzz"]
JENIS = ["pria", "wanita", "anak_l", "anak_p", "kakek", "nenek", "bayi"]

SYN = {   # sinonim jawaban LLM -> kosakata
    "berjalan": "jalan", "berlari": "lari", "berbicara": "bicara", "ngobrol": "bicara", "menjelaskan": "bicara", "melambai": "lambai",
    "menunjuk": "tunjuk", "berpikir": "mikir", "bingung": "mikir", "gembira": "senang", "bahagia": "senang", "menangis": "sedih",
    "terkejut": "kaget", "duduk_kursi": "duduk", "tidur_kasur": "tidur", "berbaring": "tidur", "sholat": "takbir", "shalat": "takbir",
    "salat": "takbir", "berdoa": "doa", "berwudhu": "wudhu", "membasuh": "wudhu", "mencuci": "cuci_tangan", "cuci": "cuci_tangan",
    "membaca": "baca", "bekerja": "kerja", "memasak": "masak", "memberi": "beri", "sedekah": "beri", "menerima": "terima",
    "menggendong": "gendong", "menyapu": "sapu", "mengupil": "ngupil", "berjabat_tangan": "salaman", "memeluk": "peluk",
    "bertepuk_tangan": "tepuk_tangan", "mengangguk": "angguk", "menggeleng": "geleng", "menolak": "tolak", "menelepon": "telepon",
    "rukuk": "rukuk", "ruku": "rukuk", "sujud": "sujud", "tasyahud": "duduk_sholat", "qiyam": "berdiri_sholat", "minum_air": "minum",
    "laki-laki": "pria", "lelaki": "pria", "suami": "pria", "ayah": "pria", "perempuan": "wanita", "istri": "wanita", "ibu": "wanita",
    "anak": "anak_l", "anak_laki": "anak_l", "anak_perempuan": "anak_p", "al-quran": "quran", "alquran": "quran", "mushaf": "quran",
    "kitab": "buku", "handphone": "hp", "ponsel": "hp", "makanan": "piring", "air": "gelas", "koin": "uang",
}
FORBID = re.compile(r"nabi|rasul|sahabat|malaikat|allah|tuhan|jibril|muhammad|ﷺ", re.I)

# ================================================================ tokoh tetap video
SHIRTS = [(79, 134, 198), (63, 167, 160), (224, 122, 72), (122, 104, 196), (70, 150, 96), (214, 92, 120), (232, 170, 60), (90, 120, 150)]
PANTS = [(70, 76, 90), (88, 72, 60), (60, 90, 120), (96, 96, 104)]
HIJAB = [(107, 79, 181), (47, 127, 111), (214, 100, 143), (232, 163, 61), (70, 120, 200), (150, 70, 90)]
SKIN = [(242, 201, 160), (233, 184, 139), (221, 167, 119), (237, 190, 146)]
ROLE = {"suami": "pria", "ayah": "pria", "bapak": "pria", "teman": "pria", "laki-laki": "pria", "lelaki": "pria", "pria": "pria",
        "istri": "wanita", "isteri": "wanita", "ibu": "wanita", "wanita": "wanita", "perempuan": "wanita", "muslimah": "wanita",
        "anak": "anak_l", "putra": "anak_l", "putri": "anak_p", "kakek": "kakek", "nenek": "nenek", "bayi": "bayi"}


def _look(jenis, rng):
    sk = rng.choice(SKIN)
    lk = {"jenis": jenis, "skin": sk, "shirt": rng.choice(SHIRTS), "pants": rng.choice(PANTS), "hijab": rng.choice(HIJAB),
          "peci": rng.random() < 0.7, "beard": jenis == "kakek" or (jenis == "pria" and rng.random() < 0.35)}
    if jenis in ("kakek",):
        lk["shirt"] = (238, 234, 222)
    return lk


def make_cast(script, seed=None):
    """Tokoh tetap video: dari kata peran di narasi (suami, istri, anak ...) + tokoh utama acak (pria/wanita)."""
    text = " ".join((a.get("narasi") or "") + " " + (a.get("penjelasan") or "") for a in script.get("adegan", []))
    seed = seed if seed is not None else zlib.crc32((script.get("judul") or text[:200]).encode("utf-8"))
    rng = random.Random(seed)
    roles = []
    for w in re.findall(r"[\w\-]+", text.lower()):
        for c in K._cands(K._norm(w)):
            if c in ROLE and ROLE[c] not in [r[1] for r in roles]:
                roles.append((c, ROLE[c]))
                break
    if not roles or roles[0][1] not in ("pria", "wanita"):
        roles.insert(0, ("tokoh utama", rng.choice(["pria", "pria", "wanita"])))
    if len(roles) < 2:
        roles.append(("teman", roles[0][1]))                               # teman sesama jenis
    cast = {}
    for i, (name, jenis) in enumerate(roles[:4]):
        cid = "ABCD"[i]
        lk = _look(jenis, rng)
        lk["nama"] = name
        cast[cid] = lk
    return cast


def cast_text(cast):
    out = []
    for cid, lk in cast.items():
        j = lk["jenis"].replace("_l", " laki-laki").replace("_p", " perempuan")
        out.append(f"{cid} = {lk['nama']} ({j})")
    return "; ".join(out)


# ================================================================ storyboard (LLM + cadangan)
PROMPT = """Kamu sutradara animasi STICKMAN untuk video dakwah singkat. Buat ALUR CERITA visual yang memperagakan
penjelasan ustad di bawah ini secara konkret, lucu-santun, dan menarik, berupa contoh kejadian sehari-hari.

Topik video: {topik}
Narasi adegan ini: "{narasi}"
Tokoh tetap video ini (pakai id-nya; boleh sebagian): {cast}
{prev}
ATURAN:
- {nb} babak, urut mengikuti narasi. Setiap babak dimulai pada satu KATA yang benar-benar ada di narasi (tulis persis kata itu).
- Hanya orang biasa. DILARANG menggambarkan Nabi, Rasul, sahabat, malaikat, atau Allah dalam bentuk apa pun. Bila narasi
  menyebut mereka, gambarkan tokoh biasa yang membaca buku/quran atau mendengarkan.
- Jangan menambah hukum atau penilaian benar/salah. Gambar hanya memperagakan situasi yang disebut narasi.
- Jaga adab: pria dan wanita yang bukan suami-istri TIDAK boleh peluk/salaman; jangan tampilkan makan/minum di babak puasa
  kecuali narasi menyebut berbuka/sahur. Setiap babak harus jelas memperagakan kalimat pada kata pemicunya.
- Variasikan aksi, posisi, ekspresi, benda dan latar antar babak supaya tidak monoton. 1 sampai 3 tokoh per babak.
- Pilih nilai HANYA dari daftar ini:
  latar: {latar}
  aksi: {aksi}
  emosi: {emosi}
  benda: {benda} (atau null)
  efek: {efek} (atau null)
  posisi: kiri, tengah, kanan

Jawab HANYA JSON:
{{"babak":[{{"kata":"...","latar":"...","malam":false,"tokoh":[{{"id":"A","aksi":"...","posisi":"tengah","emosi":"...","benda":null}}],"efek":null}}]}}"""


def _pick(v, allowed, default):
    v = (str(v or "")).strip().lower().replace(" ", "_").replace("-", "_") if v is not None else ""
    if v in allowed:
        return v
    v2 = SYN.get(v) or SYN.get(v.replace("_", "-")) or SYN.get(v.replace("_", ""))
    if v2 in allowed:
        return v2
    for a in allowed:
        if v and (v.startswith(a) or a.startswith(v)) and len(v) >= 3:
            return a
    return default


def _sanitize(data, cast, narasi):
    beats = []
    raw = data.get("babak") if isinstance(data, dict) else None
    for b in (raw or [])[:4]:
        if not isinstance(b, dict):
            continue
        if FORBID.search(json.dumps(b, ensure_ascii=False).replace("quran", "")):
            # jangan sampai ada tokoh/label sosok suci; kata pemicu boleh, tapi tokoh bukan
            b = {**b, "tokoh": [t for t in (b.get("tokoh") or []) if not FORBID.search(json.dumps(t, ensure_ascii=False))]}
        toks = []
        used = set()
        for t in (b.get("tokoh") or [])[:3]:
            if not isinstance(t, dict):
                continue
            cid = str(t.get("id") or "").strip().upper()[:1]
            if cid not in cast or cid in used:
                cid = next((c for c in cast if c not in used), None)
                if not cid:
                    break
            used.add(cid)
            toks.append({"id": cid, "aksi": _pick(t.get("aksi"), AKSI, "bicara"), "emosi": _pick(t.get("emosi"), EMOSI, "biasa"),
                         "posisi": _pick(t.get("posisi"), ["kiri", "tengah", "kanan"], ""), "benda": _pick(t.get("benda"), BENDA, None)})
        if not toks:
            continue
        beats.append({"kata": str(b.get("kata") or "").strip(), "latar": _pick(b.get("latar"), LATAR, "rumah"),
                      "malam": bool(b.get("malam")), "tokoh": toks, "efek": _pick(b.get("efek"), EFEK, None)})
    return beats


# kata -> (aksi, latar, benda, efek, aksi_tokoh_kedua)
KEYMAP = {
    "wudhu": ("wudhu", "wudhu", None, "air", None), "wudu": ("wudhu", "wudhu", None, "air", None), "basuh": ("wudhu", "wudhu", None, "air", None),
    "kumur": ("wudhu", "wudhu", None, "air", None), "usap": ("wudhu", "wudhu", None, None, None),
    "cuci": ("cuci_tangan", "wudhu", None, None, None), "bersih": ("cuci_tangan", "wudhu", None, "bintang", None),
    "mandi": ("mandi", "wudhu", None, "air", None), "junub": ("mikir", "kamar", None, "tanya", None),
    "sholat": ("takbir", "masjid", None, "cahaya", None), "shalat": ("takbir", "masjid", None, "cahaya", None),
    "salat": ("takbir", "masjid", None, "cahaya", None), "rukuk": ("rukuk", "masjid", None, None, None),
    "sujud": ("sujud", "masjid", None, "cahaya", None), "doa": ("doa", "masjid", None, "cahaya", None),
    "puasa": ("lihat_jam", "rumah", None, "jam", None), "shaum": ("lihat_jam", "rumah", None, "jam", None),
    "buka": ("makan", "rumah", "kurma", "bintang", "makan"), "sahur": ("makan", "dapur", "piring", None, None),
    "makan": ("makan", "rumah", "piring", None, None), "minum": ("minum", "rumah", "gelas", None, None),
    "upil": ("ngupil", "rumah", None, None, "kaget"), "ngupil": ("ngupil", "rumah", None, None, "kaget"),
    "hidung": ("ngupil", "rumah", None, None, None), "bersin": ("bersin", "rumah", "tisu", None, None),
    "batuk": ("batuk", "rumah", None, None, None), "sakit": ("sakit", "kamar", None, None, "duduk"),
    "tidur": ("tidur", "kamar", None, "zzz", None), "mimpi": ("tidur", "kamar", None, "zzz", None),
    "baca": ("baca", "masjid", "quran", "cahaya", None), "quran": ("baca", "masjid", "quran", "cahaya", None),
    "kitab": ("baca", "sekolah", "buku", "lampu", None), "ilmu": ("baca", "sekolah", "buku", "lampu", None),
    "belajar": ("baca", "sekolah", "buku", "lampu", None), "kajian": ("duduk", "masjid", "buku", "lampu", "bicara"),
    "kerja": ("kerja", "kantor", None, None, None), "nafkah": ("kerja", "kantor", "uang", "uang", None),
    "masak": ("masak", "dapur", None, None, None), "dapur": ("masak", "dapur", None, None, None),
    "sedekah": ("beri", "jalan", "uang", "hati", "terima"), "zakat": ("beri", "masjid", "uang", "hati", "terima"),
    "infak": ("beri", "masjid", "uang", "hati", "terima"), "beri": ("beri", "rumah", "hadiah", "hati", "terima"),
    "nikah": ("salaman", "masjid", None, "hati", "salaman"), "menikah": ("salaman", "masjid", None, "hati", "salaman"),
    "istri": ("bicara", "rumah", None, None, "angguk"), "suami": ("bicara", "rumah", None, None, "angguk"),
    "anak": ("gendong", "rumah", "bayi", "hati", None), "bayi": ("gendong", "rumah", "bayi", "hati", None),
    "marah": ("marah", "rumah", None, "petir", "takut"), "sedih": ("sedih", "rumah", None, None, None),
    "menangis": ("sedih", "rumah", None, None, None), "senang": ("senang", "halaman", None, "bintang", None),
    "bahagia": ("senang", "halaman", None, "hati", "tepuk_tangan"), "kaget": ("kaget", "rumah", None, "seru", None),
    "bingung": ("mikir", "rumah", None, "tanya", None), "kenapa": ("mikir", "rumah", None, "tanya", None),
    "mengapa": ("mikir", "rumah", None, "tanya", None), "bagaimana": ("mikir", "rumah", None, "tanya", None),
    "takut": ("takut", "jalan", None, None, None), "pasar": ("beri", "pasar", "uang", None, "terima"),
    "jual": ("beri", "pasar", "piring", None, "terima"), "beli": ("terima", "pasar", "uang", None, "beri"),
    "pergi": ("jalan", "jalan", "tas", None, None), "masjid": ("jalan", "masjid", None, None, None),
    "paham": ("senang", "sekolah", None, "lampu", None), "tahu": ("angguk", "rumah", None, "lampu", None),
    "ingat": ("tunjuk", "rumah", None, "lampu", None), "maaf": ("salaman", "rumah", None, "hati", "salaman"),
    "telepon": ("telepon", "rumah", "hp", None, None), "hp": ("telepon", "rumah", "hp", None, None),
    "hujan": ("lari", "jalan", None, "hujan", None), "malam": ("tidur", "kamar", None, "zzz", None),
    "sapu": ("sapu", "halaman", None, None, None), "tetangga": ("lambai", "halaman", None, None, "lambai"),
}


CONTRA = {"tapi", "tetapi", "namun", "sedangkan", "padahal", "berbeda", "kecuali"}
CONCL = {"jadi", "maka", "intinya", "kesimpulannya", "kesimpulan", "sehingga", "artinya", "makanya"}
POS_RULE = {"boleh", "sah", "halal", "sunnah", "sunah", "dianjurkan", "pahala", "aman", "tenang", "mudah"}
NEG_RULE = {"batal", "haram", "jangan", "dosa", "larang", "makruh", "bahaya", "rusak"}
SOLO_OK = {"wudhu", "cuci_tangan", "mandi", "tidur", "sakit", "takbir", "berdiri_sholat", "rukuk", "sujud", "duduk_sholat", "doa",
           "baca", "kerja", "masak", "lari", "jalan", "sapu", "telepon"}
REACT = {"ragu": ["mikir", "pusing", "tunjuk"], "aksi": ["angguk", "mikir", "bicara", "tunjuk"], "kontras": ["kaget", "mikir", "pusing"], "paham": ["tepuk_tangan", "angguk", "senang"],
         "positif": ["tepuk_tangan", "senang", "angguk"], "negatif": ["kaget", "takut", "mikir"]}
ODD = {"ngupil", "bersin", "batuk", "marah", "tidur"}         # aksi yang biasanya bikin lawan main kaget


def story_state(script, seed):
    """Latar 'rumah dasar' satu video: dari kata kunci topik (wudhu -> tempat wudhu, sholat -> masjid ...) atau acak."""
    rng = random.Random(seed)
    text = " ".join((a.get("narasi") or "") for a in script.get("adegan", [])) + " " + (script.get("judul") or "")
    cnt = {}
    for w in re.findall(r"[\w\-]+", text.lower()):
        for c in K._cands(K._norm(w)):
            if c in KEYMAP:
                lat = KEYMAP[c][1]
                cnt[lat] = cnt.get(lat, 0) + (0.4 if lat == "rumah" else 1)
                break
    home = max(cnt, key=cnt.get) if cnt else rng.choice(["rumah", "halaman", "kantor", "rumah"])
    return {"home": home, "last": home, "seed": seed, "n": 0, "used": {}, "mood": MOODS[seed % len(MOODS)],
            "topic": topic_action(script)}


def auto_story(sc, cast, state=None, seed=0):
    """Cerita dari kata yang diucapkan: aksi (wudhu, makan, ngupil ...), 'tapi' = babak kontras, 'jadi/intinya' = babak paham,
    boleh/sah = senang, batal/jangan (tidak disangkal) = menolak. Lawan main bereaksi bervariasi. Tanpa tanda benar/salah."""
    state = state or {"home": "rumah", "last": "rumah", "seed": seed, "n": 0, "used": {}}
    used = state.setdefault("used", {})
    text = ((sc.get("narasi") or "") + " " + (sc.get("penjelasan") or "")).strip()
    words = re.findall(r"[\w\-']+", text)
    rng = random.Random((seed or 0) * 7 + state["n"] * 131 + state["seed"])
    ids = list(cast)
    A, B = ids[0], (ids[1] if len(ids) > 1 else None)
    wl = [(0, 0, w) for w in words]
    ev = []
    asks = set()                                                          # kata di dalam kalimat tanya -> hukumnya belum dijawab
    pos_ = 0
    for m in re.finditer(r"[^.!?]+[.!?]?", text):
        nw = len(re.findall(r"[\w\-']+", m.group(0)))
        if m.group(0).strip().endswith("?"):
            asks.update(range(pos_, pos_ + nw))
        pos_ += nw
    for i, w in enumerate(words):
        n = K._norm(w)
        cands = K._cands(n)
        ask = i in asks
        neg = K.negated(wl, i)
        hit = next((KEYMAP[c] for c in cands if c in KEYMAP), None)
        if n in CONTRA:
            ev.append((i, "kontras", None))
        elif n in CONCL:
            ev.append((i, "paham", None))
        elif any(c in NEG_RULE for c in cands):
            ev.append((i, "ragu" if ask else ("positif" if neg else "negatif"), None))
        elif any(c in POS_RULE for c in cands) and not neg:
            ev.append((i, "ragu" if ask else "positif", None))
        elif hit:
            ev.append((i, "aksi", hit))
    tp = sc.get("tipe")
    chosen, last_i, last_key = [], -99, None
    for i, kind, hit in ev:
        key = hit[0] if hit else kind
        if i - last_i < 5 or key == last_key:
            continue
        chosen.append((i, kind, hit))
        last_i, last_key = i, key
        if len(chosen) >= 4:
            break
    beats = []
    side = rng.random() < 0.5
    setting = state["last"]
    night = False

    def pos(k):
        return ("kiri", "kanan")[(k + side) % 2]

    if not chosen or chosen[0][0] > 3:                                   # babak pembuka
        if tp == "tanya":
            tk = [{"id": A, "aksi": "mikir", "emosi": "bingung", "posisi": "tengah" if not B else pos(0), "benda": None}]
            if B and rng.random() < 0.6:
                tk.append({"id": B, "aksi": rng.choice(["pusing", "mikir", "tunjuk"]), "emosi": "bingung", "posisi": pos(1), "benda": None})
            beats.append({"kata": words[0] if words else "", "latar": setting, "malam": False, "tokoh": tk, "efek": "tanya"})
        else:
            a1 = rng.choice(["bicara", "lambai", "jalan", "tunjuk"]) if state["n"] else rng.choice(["lambai", "jalan"])
            tk = [{"id": A, "aksi": a1, "emosi": "senang", "posisi": pos(0), "benda": None}]
            if B:
                tk.append({"id": B, "aksi": rng.choice(["angguk", "bicara", "mikir", "lambai"]), "emosi": "biasa", "posisi": pos(1), "benda": None})
            beats.append({"kata": words[0] if words else "", "latar": setting, "malam": False, "tokoh": tk, "efek": None})
    for k, (i, kind, hit) in enumerate(chosen):
        n = K._norm(words[i])
        if n in ("malam", "tidur", "sahur", "tahajud", "isya"):
            night = True
        if kind == "aksi":
            a, lat, bd, ef, a2 = hit
            if lat != "rumah":
                setting = lat
            elif setting not in ("rumah", "kamar", "dapur", "halaman", "kantor"):
                setting = state["home"] if state["home"] in ("rumah", "halaman", "kantor") else "rumah"
            emo = "bingung" if a == "mikir" else "biasa"
            u = used.get(a, [])
            if u:                                                         # aksi diulang -> latar & reaksi lain
                alt = [x for x in ("rumah", "halaman", "kantor", "jalan", "kamar", "dapur") if x != u[-1][0] and x != setting]
                if lat == "rumah":
                    setting = rng.choice(alt)
            solo = a in SOLO_OK and rng.random() < 0.45
            tk = [{"id": A, "aksi": a, "emosi": emo, "posisi": "tengah" if (solo or not B) else pos(k), "benda": bd}]
            if B and not solo:
                pool = (["kaget", "mikir", "geleng", "takut"] if a in ODD else REACT["aksi"])
                pool = [x for x in pool if x not in [r_ for _s, r_ in u]] or pool
                r = a2 if (a2 and not u) else rng.choice(pool)
                tk.append({"id": B, "aksi": r, "emosi": "biasa", "posisi": pos(k + 1), "benda": None})
            else:
                r = None
            used.setdefault(a, []).append((setting, r))
        else:
            ef = {"kontras": "seru", "paham": rng.choice(["lampu", "bintang"]), "positif": rng.choice(["bintang", "hati"]),
                  "negatif": "seru", "ragu": "tanya"}[kind]
            a = {"kontras": rng.choice(["tunjuk", "geleng", "bicara"]), "paham": rng.choice(["senang", "tunjuk", "angguk"]),
                 "positif": rng.choice(["senang", "angguk", "tepuk_tangan"]), "negatif": rng.choice(["tolak", "geleng"]),
                 "ragu": rng.choice(["mikir", "pusing"])}[kind]
            tk = [{"id": A, "aksi": a, "emosi": "senang" if kind in ("paham", "positif") else "biasa", "posisi": pos(k) if B else "tengah",
                   "benda": None}]
            if B:
                tk.append({"id": B, "aksi": rng.choice(REACT[kind]), "emosi": "biasa", "posisi": pos(k + 1), "benda": None})
        beats.append({"kata": words[i], "latar": setting, "malam": night, "tokoh": tk, "efek": ef})
    state["last"] = setting
    state["n"] += 1
    return beats[:4]


fallback_story = auto_story

ADULT_M, ADULT_F = {"pria", "kakek"}, {"wanita", "nenek"}


def adab(beats, cast):
    """Peluk/salaman hanya sesama jenis atau suami-istri (anak boleh). Selain itu diganti lambai/senang."""
    names = {c: (lk.get("nama") or "") for c, lk in cast.items()}
    for b in beats:
        tks = b.get("tokoh") or []
        for t in tks:
            if t["aksi"] not in ("peluk", "salaman"):
                continue
            others = [o for o in tks if o is not t]
            if not others:
                t["aksi"] = "lambai" if t["aksi"] == "salaman" else "senang"
                continue
            ok = True
            for o in others:
                j1, j2 = cast.get(t["id"], {}).get("jenis", ""), cast.get(o["id"], {}).get("jenis", "")
                mixed = (j1 in ADULT_M and j2 in ADULT_F) or (j1 in ADULT_F and j2 in ADULT_M)
                pasangan = {names.get(t["id"]), names.get(o["id"])} == {"suami", "istri"}
                if mixed and not pasangan:
                    ok = False
            if not ok:
                for x in [t] + others:
                    if x["aksi"] in ("peluk", "salaman"):
                        x["aksi"] = "lambai" if x["aksi"] == "salaman" else "senang"
    return beats


CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "stik")


def storyboard(sc, cast, cfg, topik="", prev=None, log=print, use_llm=True, state=None):
    """Babak cerita satu adegan. Default: cerita otomatis dari kata yang diucapkan (cepat & selalu nyambung).
    cfg["stik_llm"]=True -> disusun LLM lokal (lebih bebas, ±45 dtk/adegan, di-cache di cache/stik)."""
    narasi = " ".join(x for x in ((sc.get("narasi") or ""), (sc.get("penjelasan") or "")) if x).strip()
    if not narasi:
        return []
    if sc.get("cerita"):                                                    # cerita yang ditulis/diubah manual
        return adab(_sanitize({"babak": sc["cerita"]}, cast, narasi), cast)
    if not (use_llm and cfg.get("stik_llm", False)):
        return adab(auto_story(sc, cast, state, zlib.crc32(narasi.encode("utf-8"))), cast)
    key = hashlib.sha1(json.dumps([narasi, cast_text(cast), topik, cfg.get("stik_model") or cfg.get("llm_model")],
                                  ensure_ascii=False).encode("utf-8")).hexdigest()[:20]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return adab(json.load(f), cast)
        except (OSError, ValueError):
            pass
    beats = []
    if use_llm and cfg.get("stik_llm", True):
        try:
            import aw_ai as ai
            nwords = len(narasi.split())
            nb = "2" if nwords < 18 else ("2 sampai 3" if nwords < 40 else "3 sampai 4")
            pv = f"Babak terakhir adegan sebelumnya: {prev}\n" if prev else ""
            prompt = PROMPT.format(topik=topik, narasi=narasi, cast=cast_text(cast), prev=pv, nb=nb, latar=", ".join(LATAR),
                                   aksi=", ".join(AKSI), emosi=", ".join(EMOSI), benda=", ".join(BENDA), efek=", ".join(EFEK))
            models = [cfg.get("stik_model") or cfg.get("llm_model", "qwen2.5:7b")] + list(cfg.get("llm_fallback") or [])
            txt, _m = ai.chat_auto(prompt, models, log=log, json_mode=True, temperature=0.8, max_tokens=700, num_ctx=4096,
                                   timeout=int(cfg.get("llm_timeout", 600)))
            beats = _sanitize(ai.parse_json(txt), cast, narasi)
        except Exception as e:                                              # noqa: BLE001 -- cadangan selalu tersedia
            log(f"   ⚠️ cerita stickman: LLM gagal ({str(e)[:80]}) → pakai cerita otomatis")
            beats = []
    if not beats:
        beats = auto_story(sc, cast, state, zlib.crc32(narasi.encode("utf-8")))
    else:
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(beats, f, ensure_ascii=False, indent=1)
    return adab(beats, cast)


# ================================================================ waktu
def _find_word(words, kata, start_i):
    k = K._norm(kata)
    if not k:
        return None
    cands = set(K._cands(k))
    for i in range(start_i, len(words)):
        w = K._norm(words[i][2])
        if w == k or cands & set(K._cands(w)):
            return i
    return None


def timed_beats(beats, words, speech, dur):
    """Pasang waktu: tiap babak mulai di kata pemicunya; bila tidak ketemu -> dibagi rata sepanjang narasi."""
    s0, s1 = speech
    n = len(beats)
    out, wi = [], 0
    for j, b in enumerate(beats):
        t = None
        if j == 0:
            t = 0.0
        elif words:
            i = _find_word(words, b.get("kata", ""), wi)
            if i is not None:
                t, wi = words[i][0] - 0.12, i + 1
        if t is None:
            t = s0 + (s1 - s0) * j / max(1, n)
        out.append(dict(b, t0=max(0.0, t)))
    out.sort(key=lambda b: b["t0"])
    kept = []
    for b in out:
        if kept and b["t0"] - kept[-1]["t0"] < 1.5:                  # babak terlalu rapat -> dilewati
            continue
        kept.append(b)
    for j, b in enumerate(kept):
        b["t1"] = kept[j + 1]["t0"] if j + 1 < len(kept) else dur + 0.5
    return kept


# ================================================================ latar (di-cache)
_BG = {}


def _grad(h, w, top, bot):
    a = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    return (np.array(top, np.float32) * (1 - a) + np.array(bot, np.float32) * a).repeat(w, 1).astype(np.uint8)


def _rr(img, x0, y0, x1, y1, fill, line=INK, w=3):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    if fill is not None:
        cv2.rectangle(img, (x0, y0), (x1, y1), fill, -1, cv2.LINE_AA)
    if line is not None and w:
        cv2.rectangle(img, (x0, y0), (x1, y1), line, w, cv2.LINE_AA)


def _poly(img, pts, fill, line=INK, w=3):
    p = np.int32(pts)
    if fill is not None:
        cv2.fillPoly(img, [p], fill, cv2.LINE_AA)
    if line is not None and w:
        cv2.polylines(img, [p], True, line, w, cv2.LINE_AA)


def _dk(c, t):
    return tuple(int(v * (1 - t)) for v in c)


def _lt(c, t):
    return tuple(int(v + (255 - v) * t) for v in c)


WALLS = [(246, 232, 206), (226, 238, 230), (236, 228, 246), (250, 226, 214), (222, 234, 246)]


def background(setting, night, w, h, gy, var=0):
    key = (setting, night, w, h, gy, var)
    if key in _BG:
        return _BG[key]
    rng = np.random.RandomState(var * 31 + LATAR.index(setting) if setting in LATAR else 0)
    outdoor = setting in ("halaman", "jalan", "pasar")
    if outdoor:
        sky = ((40, 52, 96), (92, 96, 150)) if night else ((132, 200, 238), (214, 238, 246))
        img = _grad(gy, w, *sky)
        img = np.vstack([img, np.zeros((h - gy, w, 3), np.uint8)])
        if night:
            for _ in range(40):
                cv2.circle(img, (rng.randint(0, w), rng.randint(0, gy - 120)), rng.randint(1, 3), (255, 248, 210), -1, cv2.LINE_AA)
            cv2.circle(img, (w - 120, 90), 40, (255, 240, 190), -1, cv2.LINE_AA)
            cv2.circle(img, (w - 104, 80), 36, sky[0], -1, cv2.LINE_AA)
        else:
            cv2.circle(img, (w - 120, 92), 46, (255, 222, 120), -1, cv2.LINE_AA)
            for cx in (rng.randint(60, w // 2), rng.randint(w // 2, max(w // 2 + 1, w - 200))):
                for dx, r in ((-40, 26), (0, 36), (40, 28)):
                    cv2.circle(img, (cx + dx, 110 + rng.randint(-20, 20)), r, (255, 255, 255), -1, cv2.LINE_AA)
    else:
        wall = WALLS[var % len(WALLS)]
        if setting == "masjid":
            wall = (238, 230, 210)
        if setting == "wudhu":
            wall = (214, 236, 240)
        if night:
            wall = _dk(wall, 0.42)
        img = np.zeros((h, w, 3), np.uint8)
        img[:gy] = wall
    ground = {"halaman": (150, 206, 120), "jalan": (120, 124, 132), "pasar": (200, 178, 140), "masjid": (52, 132, 104),
              "wudhu": (196, 216, 224), "kamar": (200, 160, 120), "dapur": (214, 200, 176), "kantor": (190, 186, 182),
              "sekolah": (200, 170, 130)}.get(setting, (206, 168, 124))
    if night:
        ground = _dk(ground, 0.35)
    img[gy:] = ground
    cv2.line(img, (0, gy), (w, gy), INK, 3, cv2.LINE_AA)
    if setting in ("rumah", "kamar", "dapur", "kantor", "sekolah"):              # papan lantai
        for x in range(0, w, 120):
            cv2.line(img, (x, gy), (x - 60, h), _dk(ground, 0.12), 2, cv2.LINE_AA)
    lamp = (255, 236, 160)
    if setting == "rumah":
        _rr(img, 70, 90, 250, 260, (190, 224, 246) if not night else (40, 56, 100))       # jendela
        cv2.line(img, (160, 90), (160, 260), INK, 3)
        cv2.line(img, (70, 175), (250, 175), INK, 3)
        _rr(img, w - 250, 110, w - 150, 200, (240, 200, 120))                              # pigura
        cv2.ellipse(img, (w - 200, 155), (30, 26), 0, 180, 360, (60, 140, 120), -1, cv2.LINE_AA)
        _rr(img, w - 330, gy - 110, w - 60, gy - 40, (170, 120, 100))                      # sofa
        _rr(img, w - 345, gy - 140, w - 315, gy - 2, (150, 100, 84))
        _rr(img, w - 75, gy - 140, w - 45, gy - 2, (150, 100, 84))
        cv2.circle(img, (w // 2, 40), 16, lamp, -1, cv2.LINE_AA)
    elif setting == "kamar":
        _rr(img, w - 230, 80, w - 80, 240, (190, 224, 246) if not night else (34, 46, 90))
        cv2.line(img, (w - 155, 80), (w - 155, 240), INK, 3)
        if night:
            cv2.circle(img, (w - 120, 120), 18, (255, 240, 190), -1, cv2.LINE_AA)
        _rr(img, 60, gy - 150, 110, gy - 2, (190, 150, 110))                                # lemari kecil
        cv2.circle(img, (85, gy - 175), 22, lamp if night else (250, 240, 210), -1, cv2.LINE_AA)
        cv2.circle(img, (85, gy - 175), 22, INK, 3, cv2.LINE_AA)
    elif setting == "dapur":
        _rr(img, 40, 70, w - 40, 170, (214, 190, 160))                                      # lemari atas
        for x in range(40, w - 40, 180):
            _rr(img, x, 70, x + 180, 170, None)
        _rr(img, 40, gy - 120, 330, gy, (220, 200, 170))                                    # meja dapur kiri
        cv2.circle(img, (110, gy - 160), 26, (230, 120, 80), -1, cv2.LINE_AA)               # buah
        cv2.circle(img, (150, gy - 150), 20, (240, 200, 70), -1, cv2.LINE_AA)
    elif setting == "wudhu":
        for y in range(0, gy, 60):
            cv2.line(img, (0, y), (w, y), _dk((214, 236, 240), 0.08), 2)
        for x in range(0, w, 60):
            cv2.line(img, (x, 0), (x, gy), _dk((214, 236, 240), 0.08), 2)
        _rr(img, 30, gy - 130, w - 30, gy - 100, (170, 190, 200))                             # bak/talang air
        for x in range(110, w - 60, 190):
            cv2.line(img, (x, gy - 200), (x, gy - 175), (150, 160, 170), 8, cv2.LINE_AA)        # kran
            cv2.line(img, (x, gy - 175), (x + 22, gy - 175), (150, 160, 170), 8, cv2.LINE_AA)
            cv2.circle(img, (x, gy - 205), 9, (200, 80, 70), -1, cv2.LINE_AA)
        _rr(img, w // 2 - 70, 60, w // 2 + 70, 170, (200, 230, 240))                          # cermin
    elif setting == "masjid":
        cx = w // 2
        _poly(img, [(cx - 130, gy), (cx - 130, 170), (cx, 70), (cx + 130, 170), (cx + 130, gy)], (220, 200, 160))   # mihrab
        _poly(img, [(cx - 90, gy), (cx - 90, 200), (cx, 125), (cx + 90, 200), (cx + 90, gy)], (60, 130, 110), INK, 2)
        for x in (110, w - 110):
            _poly(img, [(x - 60, gy - 30), (x - 60, 150), (x, 100), (x + 60, 150), (x + 60, gy - 30)], (230, 214, 180))
        cv2.line(img, (cx, 0), (cx, 40), INK, 2)
        cv2.circle(img, (cx, 52), 16, lamp, -1, cv2.LINE_AA)
        for y in range(gy + 18, h, 26):                                                       # garis saf
            cv2.line(img, (0, y), (w, y), _lt(ground, 0.18), 2)
    elif setting == "halaman":
        tx = 110 + var % 3 * 40
        _rr(img, tx - 16, gy - 210, tx + 16, gy, (140, 100, 70))
        for dx, dy, r in ((0, -260, 80), (-60, -220, 60), (60, -220, 60)):
            cv2.circle(img, (tx + dx, gy + dy), r, (90, 170, 100), -1, cv2.LINE_AA)
        for x in range(w - 330, w - 30, 40):                                                  # pagar
            _rr(img, x, gy - 80, x + 22, gy, (250, 250, 245), INK, 2)
        cv2.line(img, (w - 340, gy - 55), (w - 20, gy - 55), INK, 3)
        cv2.circle(img, (w - 240, gy - 150), 0, INK)
    elif setting == "jalan":
        for i, x in enumerate(range(20, w, 170)):
            hh = 150 + (i * 53 + var * 17) % 120
            col = [(230, 200, 180), (200, 214, 230), (240, 226, 190), (214, 200, 230)][i % 4]
            _rr(img, x, gy - 40 - hh, x + 140, gy - 40, col if not night else _dk(col, 0.4))
            for wy in range(gy - 20 - hh, gy - 60, 40):
                for wx in (x + 20, x + 80):
                    _rr(img, wx, wy, wx + 30, wy + 22, lamp if night else (180, 214, 240), INK, 2)
        _rr(img, 0, gy - 40, w, gy, (200, 196, 190))
        for x in range(30, w, 140):
            cv2.line(img, (x, gy + 30), (x + 70, gy + 30), (250, 250, 250), 5)
    elif setting == "kantor":
        _rr(img, 60, 80, 330, 260, (180, 214, 240) if not night else (40, 56, 100))
        for x in range(90, 330, 60):
            _rr(img, x, 190 - (x % 90), x + 40, 260, (140, 160, 190), INK, 2)
        _rr(img, w - 140, gy - 160, w - 90, gy - 70, (140, 100, 70))                         # pot tanaman
        cv2.circle(img, (w - 115, gy - 180), 40, (90, 170, 100), -1, cv2.LINE_AA)
    elif setting == "sekolah":
        _rr(img, w // 2 - 260, 60, w // 2 + 260, 250, (52, 104, 80), (120, 90, 60), 8)
        for i in range(3):
            y = 110 + i * 45
            cv2.line(img, (w // 2 - 200, y), (w // 2 - 20 + i * 60, y), (240, 240, 230), 3, cv2.LINE_AA)
    elif setting == "pasar":
        for i, x in enumerate(range(20, w, 330)):
            c1, c2 = [((224, 90, 71), (250, 250, 245)), ((63, 167, 160), (250, 250, 245)), ((232, 170, 60), (250, 250, 245))][i % 3]
            for k in range(6):
                _rr(img, x + k * 50, gy - 260, x + k * 50 + 50, gy - 210, c1 if k % 2 else c2, INK, 2)
            _rr(img, x + 10, gy - 110, x + 290, gy - 40, (190, 150, 100))
            for k in range(7):
                cv2.circle(img, (x + 40 + k * 36, gy - 125), 16, [(230, 90, 70), (240, 200, 70), (110, 180, 90)][k % 3], -1, cv2.LINE_AA)
    if night and not outdoor:
        glow = np.zeros((h, w), np.float32)
        cv2.circle(glow, (w // 2, 60), 260, 1.0, -1)
        glow = cv2.GaussianBlur(glow, (0, 0), 90)[..., None] * 0.18
        img = np.clip(img.astype(np.float32) + glow * np.array(lamp, np.float32), 0, 255).astype(np.uint8)
    _BG[key] = img
    if len(_BG) > 60:
        _BG.pop(next(iter(_BG)))
    return img


# ================================================================ pose stickman
HEAD_R, NECK, TORSO, UA, LA, TH, SH = 27, 6, 92, 50, 48, 60, 58
PRAY = {"takbir", "berdiri_sholat", "rukuk", "sujud", "duduk_sholat", "doa"}


def pose_of(act, t, ph):
    """Sudut sendi (derajat, 0 = lurus ke bawah, + = ke depan/arah hadap)."""
    S = math.sin
    p = dict(lean=0.0, head=0.0, hdx=0.0, ub=-10.0, lb=-6.0, uf=10.0, lf=6.0, tb=-6.0, sb=-6.0, tf=6.0, sf=6.0, dy=0.0, rot=0.0,
             seat=None, talk=False, hold="f", auto=None, eyes="buka", fx=None, shake=0.0)
    br = S(t * 2.2 + ph)
    p["ub"] += 2 * br
    p["uf"] -= 2 * br
    p["head"] += 1.5 * S(t * 1.3 + ph)
    if act in ("jalan", "lari"):
        A = 26 if act == "jalan" else 42
        sp = 7.0 if act == "jalan" else 11.0
        a = t * sp + ph
        for side, off in (("f", 0.0), ("b", math.pi)):
            th = A * S(a + off)
            bend = max(0.0, S(a + off + math.pi / 2)) * (38 if act == "jalan" else 70)
            p["t" + side], p["s" + side] = th, th - bend
            ua = -A * 0.8 * S(a + off)
            p["u" + side], p["l" + side] = ua, ua + (18 if act == "jalan" else 85)
        p["dy"] = -abs(S(a)) * (5 if act == "jalan" else 14)
        p["lean"] = 4 if act == "jalan" else 14
    elif act == "bicara":
        p.update(uf=40 + 14 * S(t * 2.6 + ph), lf=95 + 16 * S(t * 3.4 + ph), talk=True)
        p["head"] += 3 * S(t * 4.0)
    elif act == "lambai":
        p.update(uf=155, lf=168 + 26 * S(t * 11), talk=True)
    elif act == "tunjuk":
        p.update(uf=86, lf=88 + 3 * S(t * 3), talk=True)
    elif act == "mikir":
        p.update(uf=24, lf=165, ub=-4, lb=62, head=9 + 3 * S(t * 1.5), fx="tanya")
    elif act == "senang":
        u = 145 + 10 * S(t * 8)
        p.update(uf=u, lf=165, ub=-u, lb=-165, dy=-abs(S(t * 6.0)) * 30, fx="bintang")
    elif act == "sedih":
        p.update(lean=10, head=20, ub=-3, lb=0, uf=3, lf=2, fx="air_mata")
    elif act == "marah":
        p.update(uf=62 + 9 * S(t * 14), lf=150, ub=-30, lb=-100, head=-5, shake=2.5, talk=True, fx="marah")
    elif act == "kaget":
        p.update(uf=130, lf=150, ub=-130, lb=-150, lean=-7, dy=-16 * math.exp(-t * 5), fx="seru")
    elif act == "takut":
        p.update(lean=-9, uf=100, lf=145, ub=70, lb=130, shake=1.6, fx="keringat")
    elif act == "duduk":
        p.update(seat=74, tb=86, tf=90, sb=4, sf=6, uf=30, lf=82, ub=22, lb=76, auto="kursi", talk=True)
    elif act in ("tidur", "sakit"):
        p.update(rot=90, auto="kasur", eyes="tutup" if act == "tidur" else "buka", fx="zzz" if act == "tidur" else "keringat",
                 ub=-4, lb=-2, uf=4, lf=2)
    elif act == "takbir":
        p.update(uf=34, lf=170, ub=26, lb=166, auto="sajadah", eyes="tutup", fx="cahaya")
    elif act == "berdiri_sholat":
        p.update(uf=18, lf=100, ub=12, lb=96, head=8, auto="sajadah", eyes="tutup")
    elif act == "rukuk":
        p.update(lean=86, head=0, uf=10, lf=8, ub=6, lb=4, tb=0, sb=0, tf=0, sf=0, auto="sajadah", eyes="tutup")
    elif act == "sujud":
        p.update(lean=122, head=0, uf=8, lf=62, ub=4, lb=58, tb=18, sb=-90, tf=22, sf=-90, auto="sajadah", eyes="tutup", fx="cahaya")
    elif act == "duduk_sholat":
        p.update(tb=88, sb=-92, tf=92, sf=-90, uf=24, lf=86, ub=18, lb=82, auto="sajadah", eyes="tutup")
    elif act == "doa":
        p.update(tb=88, sb=-92, tf=92, sf=-90, uf=56 + 2 * S(t * 2), lf=126, ub=46, lb=120, head=10, auto="sajadah", eyes="tutup",
                 fx="cahaya")
    elif act == "wudhu":
        ph2 = (t % 2.6) / 2.6
        if ph2 < 0.5:
            p.update(uf=26, lf=168 + 6 * S(t * 12), ub=20, lb=164 - 6 * S(t * 12))
        else:
            p.update(uf=70, lf=78, ub=40, lb=104 + 14 * S(t * 12))
        p.update(auto="kran", fx="air")
    elif act == "cuci_tangan":
        p.update(uf=26, lf=80 + 10 * S(t * 12), ub=20, lb=74 - 10 * S(t * 12), head=12, auto="kran", fx="busa")
    elif act == "mandi":
        p.update(uf=60, lf=170 + 10 * S(t * 9), ub=50, lb=165 - 10 * S(t * 9), auto="shower", eyes="tutup", fx="air_atas")
    elif act == "makan":
        p.update(hold="b", ub=14, lb=86, uf=26, lf=100 + 66 * (0.5 + 0.5 * S(t * 4.2)), talk=True)
    elif act == "minum":
        p.update(uf=32, lf=158 + 4 * S(t * 3), head=-14)
    elif act == "baca":
        p.update(hold="2", uf=18, lf=96, ub=10, lb=90, head=16, talk=True)
    elif act == "kerja":
        p.update(seat=74, tb=86, tf=90, sb=4, sf=6, uf=42, lf=88 + 5 * S(t * 22), ub=36, lb=86 - 5 * S(t * 22), auto="meja", head=8)
    elif act == "masak":
        p.update(uf=36, lf=80 + 14 * S(t * 5), ub=16, lb=70, auto="kompor", fx="uap")
    elif act == "beri":
        p.update(uf=72 + 5 * S(t * 2), lf=80, talk=True)
    elif act == "terima":
        p.update(uf=64, lf=72, ub=52, lb=62)
    elif act == "gendong":
        p.update(hold="2", uf=22, lf=106, ub=16, lb=100, lean=3 * S(t * 2), fx="hati")
    elif act == "sapu":
        a = 12 * S(t * 5)
        p.update(hold="2", uf=42 + a, lf=50 + a, ub=32 + a, lb=40 + a, lean=8)
    elif act == "ngupil":
        p.update(uf=22, lf=172 + 3 * S(t * 9), head=-5)
    elif act == "bersin":
        q = (t % 1.8) / 1.8
        back = q < 0.55
        p.update(lean=-10 if back else 16, head=-16 if back else 10, uf=22, lf=166, fx=None if back else "puff")
    elif act == "batuk":
        p.update(lean=8 + 5 * abs(S(t * 8)), uf=26, lf=158, shake=1.0, fx="puff" if S(t * 8) > 0.8 else None)
    elif act == "telepon":
        p.update(uf=26, lf=176, talk=True)
    elif act == "salaman":
        p.update(uf=62, lf=66 + 7 * S(t * 10), talk=True)
    elif act == "peluk":
        p.update(uf=80, lf=108, ub=74, lb=104, eyes="tutup", fx="hati")
    elif act == "tepuk_tangan":
        c = abs(S(t * 9))
        p.update(uf=46, ub=40, lf=100 + 12 * c, lb=96 - 12 * c, fx="bintang")
    elif act == "angguk":
        p["head"] = 12 * S(t * 6)
    elif act == "geleng":
        p["hdx"] = 6 * S(t * 10)
    elif act == "lapar":
        p.update(uf=18, lf=72, ub=14, lb=66, head=10, lean=4, fx="jam")
    elif act == "lihat_jam":
        p.update(uf=58, lf=150, ub=52, lb=100, head=12, fx="jam")
    elif act == "tolak":
        p.update(uf=82, lf=142, hdx=6 * S(t * 8))
    elif act == "pusing":
        p.update(uf=40, lf=176, ub=30, lb=172, lean=6 * S(t * 3), fx="pusing")
    return p


DEFAULT_EMO = {"senang": "senang", "sedih": "sedih", "marah": "marah", "kaget": "kaget", "mikir": "bingung", "takut": "takut",
               "tidur": "tenang", "sakit": "sedih", "pusing": "bingung", "peluk": "senang", "tepuk_tangan": "senang",
               "gendong": "senang", "ngupil": "malu", "bersin": "kaget", "batuk": "sedih"}


def _v(a, d):
    r = math.radians(a)
    return np.array([math.sin(r) * d, math.cos(r)])


def skeleton(p, s, d):
    """Sendi relatif pinggul (0,0). d = arah hadap (+1 kanan, -1 kiri)."""
    lean = math.radians(p["lean"])
    up = np.array([math.sin(lean) * d, -math.cos(lean)])
    hip = np.zeros(2)
    sho = hip + up * TORSO * 0.88 * s
    neck = hip + up * TORSO * s
    hl = math.radians(p["lean"] + p["head"])
    head = neck + np.array([math.sin(hl) * d, -math.cos(hl)]) * (HEAD_R + NECK) * s + np.array([p["hdx"] * s, 0])
    J = {"hip": hip, "sho": sho, "neck": neck, "head": head}
    for sd in ("b", "f"):
        J["el" + sd] = sho + _v(p["u" + sd], d) * UA * s
        J["wr" + sd] = J["el" + sd] + _v(p["l" + sd], d) * LA * s
        J["kn" + sd] = hip + _v(p["t" + sd], d) * TH * s
        J["ft" + sd] = J["kn" + sd] + _v(p["s" + sd], d) * SH * s
    if p["rot"]:
        r = math.radians(p["rot"] * -d)
        R = np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]])
        J = {k: R @ v for k, v in J.items()}
    return J


def _ln(img, a, b, col, w):
    cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), col, max(1, int(w)), cv2.LINE_AA)


def _limb(img, pts, col, w, ink=INK):
    for a, b in zip(pts, pts[1:]):
        _ln(img, a, b, ink, w + 5)
    for a, b in zip(pts, pts[1:]):
        _ln(img, a, b, col, w)


def draw_person(img, x, gy, s, d, p, look, emo, t, talk_amt, alpha_k=1.0):
    """Gambar satu stickman. Kembalikan posisi penting (tangan, kepala) untuk benda & efek."""
    J = skeleton(p, s, d)
    hr = HEAD_R * s * (1.22 if look["jenis"].startswith("anak") else 1.0)
    pts = np.array(list(J.values()))
    low = max(pts[:, 1].max(), J["head"][1] + hr)
    base_y = (gy - p["seat"] * s - 0) if p["seat"] is not None else gy - low
    if p["rot"]:
        base_y = gy - low - (46 * s if p["auto"] == "kasur" else 0)
    sh = p["shake"] * math.sin(t * 40) * s
    off = np.array([x + sh, base_y + p["dy"] * s])
    J = {k: v + off for k, v in J.items()}
    col_s, col_p = look["shirt"], look["pants"]
    dark = lambda c: _dk(c, 0.22)                                               # noqa: E731
    lw = 9 * s
    female = look["jenis"] in ("wanita", "nenek", "anak_p")
    # kaki & lengan belakang
    _limb(img, [J["hip"], J["knb"], J["ftb"]], dark(col_p), lw)
    _limb(img, [J["sho"], J["elb"], J["wrb"]], dark(col_s), lw * 0.9)
    cv2.circle(img, tuple(int(v) for v in J["wrb"]), int(6 * s), look["skin"], -1, cv2.LINE_AA)
    if female:
        _limb(img, [J["hip"], J["knf"], J["ftf"]], col_p, lw)                     # kaki di balik rok
    # badan: pria = kapsul baju, wanita = gamis
    if female:                                                                   # gamis: badan + rok mengikuti arah paha
        knee = (J["knb"] + J["knf"]) / 2
        th = knee - J["hip"]
        L = np.linalg.norm(th) + 1e-6
        nrm = np.array([-th[1], th[0]]) / L
        straight = abs(th[1]) / L > 0.85                                           # berdiri -> rok sampai mata kaki
        hem = J["hip"] + th * (1.75 if straight else 1.2)
        poly = [J["hip"] + nrm * 15 * s, J["hip"] - nrm * 15 * s, hem - nrm * 27 * s, hem + nrm * 27 * s]
        _poly(img, poly, col_s, INK, max(2, int(3 * s)))
        _limb(img, [J["hip"], J["neck"]], col_s, 24 * s)
    else:
        _limb(img, [J["hip"], J["neck"]], col_s, 17 * s)
        _limb(img, [J["hip"], J["knf"], J["ftf"]], col_p, lw)
    for f in ("ftb", "ftf"):
        cv2.ellipse(img, (int(J[f][0] + 6 * s * d), int(J[f][1])), (int(10 * s), int(5 * s)), 0, 0, 360, INK, -1, cv2.LINE_AA)
    _limb(img, [J["sho"], J["elf"], J["wrf"]], col_s, lw * 0.9)
    cv2.circle(img, tuple(int(v) for v in J["wrf"]), int(6.5 * s), look["skin"], -1, cv2.LINE_AA)
    cv2.circle(img, tuple(int(v) for v in J["wrf"]), int(6.5 * s), INK, max(1, int(2 * s)), cv2.LINE_AA)
    # kepala
    hc = J["head"]
    hx, hy = int(hc[0]), int(hc[1])
    if female:
        cv2.circle(img, (hx, hy), int(hr * 1.28), look["hijab"], -1, cv2.LINE_AA)
        _poly(img, [(hx - hr * 1.2, hy), (hx + hr * 1.2, hy), (hx + hr * 1.5, hy + hr * 1.9), (hx - hr * 1.5, hy + hr * 1.9)],
              look["hijab"], None, 0)
        cv2.circle(img, (hx, hy), int(hr * 1.28), INK, max(2, int(3 * s)), cv2.LINE_AA)
        cv2.ellipse(img, (hx + int(3 * s * d), hy + int(2 * s)), (int(hr * 0.86), int(hr * 0.94)), 0, 0, 360, look["skin"], -1, cv2.LINE_AA)
    else:
        cv2.circle(img, (hx, hy), int(hr), look["skin"], -1, cv2.LINE_AA)
        cv2.circle(img, (hx, hy), int(hr), INK, max(2, int(3.5 * s)), cv2.LINE_AA)
        if look["jenis"] in ("kakek",):
            cv2.ellipse(img, (hx, hy), (int(hr), int(hr)), 0, 200, 340, (245, 245, 245), int(6 * s), cv2.LINE_AA)
        if look.get("peci") and look["jenis"] in ("pria", "kakek", "anak_l"):
            pc = (250, 250, 250) if look["jenis"] == "kakek" else (40, 40, 44)
            _poly(img, [(hx - hr * 0.86, hy - hr * 0.5), (hx + hr * 0.86, hy - hr * 0.5), (hx + hr * 0.78, hy - hr * 1.05),
                        (hx - hr * 0.78, hy - hr * 1.05)], pc, INK, 2)
        if look.get("beard"):
            cv2.ellipse(img, (hx + int(4 * s * d), hy + int(hr * 0.55)), (int(hr * 0.62), int(hr * 0.5)), 0, 0, 180,
                        (245, 245, 245) if look["jenis"] == "kakek" else (52, 44, 40), -1, cv2.LINE_AA)
    _face(img, hx + int(hr * 0.22 * d), hy, hr, emo, p["eyes"], t, talk_amt if p["talk"] else 0.0, d)
    return {"wrf": J["wrf"], "wrb": J["wrb"], "head": hc, "hr": hr, "hip": J["hip"], "feet": (J["ftb"] + J["ftf"]) / 2,
            "mouth": hc + np.array([hr * 0.3 * d, hr * 0.42])}


def _face(img, fx, fy, r, emo, eyes, t, talk, d):
    ex = r * 0.34
    ey = fy - r * 0.1
    blink = (t * 0.9) % 3.3 > 3.18
    lw = max(2, int(r * 0.11))
    for sx in (-1, 1):
        cx = int(fx + sx * ex)
        if eyes == "tutup" or blink or emo == "tenang":
            cv2.ellipse(img, (cx, int(ey)), (int(r * 0.13), int(r * 0.08)), 0, 0, 180, INK, lw, cv2.LINE_AA)
        elif emo == "senang":
            cv2.ellipse(img, (cx, int(ey + r * 0.05)), (int(r * 0.13), int(r * 0.12)), 0, 180, 360, INK, lw, cv2.LINE_AA)
        elif emo == "kaget":
            cv2.circle(img, (cx, int(ey)), int(r * 0.14), (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(img, (cx, int(ey)), int(r * 0.14), INK, max(1, lw - 1), cv2.LINE_AA)
            cv2.circle(img, (cx, int(ey)), int(r * 0.05), INK, -1, cv2.LINE_AA)
        else:
            cv2.circle(img, (cx, int(ey)), max(2, int(r * 0.09)), INK, -1, cv2.LINE_AA)
        if emo == "marah":
            cv2.line(img, (int(cx - r * 0.16), int(ey - r * 0.32 + sx * -r * 0.08)), (int(cx + r * 0.16), int(ey - r * 0.32 - sx * -r * 0.08)),
                     INK, lw, cv2.LINE_AA)
        elif emo in ("sedih", "takut", "bingung"):
            cv2.line(img, (int(cx - r * 0.15), int(ey - r * 0.28 - sx * r * 0.06)), (int(cx + r * 0.15), int(ey - r * 0.28 + sx * r * 0.06)),
                     INK, max(1, lw - 1), cv2.LINE_AA)
    mx, my = int(fx), int(fy + r * 0.42)
    if emo == "malu" or emo == "senang":
        for sx in (-1, 1):
            cv2.circle(img, (int(fx + sx * r * 0.55), int(fy + r * 0.25)), int(r * 0.13), (240, 150, 150), -1, cv2.LINE_AA)
    if talk > 0.05 and emo not in ("sedih",):
        h = int(r * (0.06 + 0.22 * talk))
        cv2.ellipse(img, (mx, my), (int(r * 0.2), h), 0, 0, 360, (120, 50, 50), -1, cv2.LINE_AA)
        cv2.ellipse(img, (mx, my), (int(r * 0.2), h), 0, 0, 360, INK, max(1, lw - 1), cv2.LINE_AA)
    elif emo == "kaget":
        cv2.ellipse(img, (mx, my + 2), (int(r * 0.12), int(r * 0.16)), 0, 0, 360, (120, 50, 50), -1, cv2.LINE_AA)
    elif emo in ("sedih", "marah", "takut"):
        cv2.ellipse(img, (mx, my + int(r * 0.12)), (int(r * 0.22), int(r * 0.12)), 0, 200, 340, INK, lw, cv2.LINE_AA)
    elif emo == "bingung":
        pts = np.int32([(mx - r * 0.22 + i * r * 0.11, my + (3 if i % 2 else -3)) for i in range(5)])
        cv2.polylines(img, [pts], False, INK, lw, cv2.LINE_AA)
    else:
        cv2.ellipse(img, (mx, my - int(r * 0.05)), (int(r * 0.24), int(r * 0.16)), 0, 15, 165, INK, lw, cv2.LINE_AA)


# ================================================================ benda & perabot
def draw_prop(img, name, at, s, d, t, other=None):
    x, y = float(at[0]), float(at[1])
    if name in ("buku", "quran"):
        if other is not None:
            x, y = (at[0] + other[0]) / 2, (at[1] + other[1]) / 2
        cov = (52, 132, 92) if name == "quran" else (70, 110, 190)
        _poly(img, [(x - 34 * s, y - 24 * s), (x, y - 16 * s), (x + 34 * s, y - 24 * s), (x + 34 * s, y + 18 * s), (x, y + 26 * s),
                    (x - 34 * s, y + 18 * s)], cov, INK, 3)
        _poly(img, [(x - 28 * s, y - 18 * s), (x - 3 * s, y - 11 * s), (x - 3 * s, y + 18 * s), (x - 28 * s, y + 12 * s)], (250, 246, 230), None, 0)
        _poly(img, [(x + 28 * s, y - 18 * s), (x + 3 * s, y - 11 * s), (x + 3 * s, y + 18 * s), (x + 28 * s, y + 12 * s)], (250, 246, 230), None, 0)
        if name == "quran":
            cv2.circle(img, (int(x), int(y + 2)), int(5 * s), (230, 190, 70), -1, cv2.LINE_AA)
    elif name == "hp":
        _rr(img, x - 8 * s, y - 16 * s, x + 8 * s, y + 14 * s, (40, 44, 52))
    elif name == "uang":
        for k in range(2):
            _rr(img, x - 22 * s + k * 5, y - 12 * s - k * 6, x + 22 * s + k * 5, y + 10 * s - k * 6, (130, 196, 120), INK, 2)
    elif name == "piring" or name == "kurma":
        cv2.ellipse(img, (int(x + 10 * s * d), int(y)), (int(34 * s), int(10 * s)), 0, 0, 360, (250, 250, 250), -1, cv2.LINE_AA)
        cv2.ellipse(img, (int(x + 10 * s * d), int(y)), (int(34 * s), int(10 * s)), 0, 0, 360, INK, 2, cv2.LINE_AA)
        for k in range(3):
            c = (120, 70, 40) if name == "kurma" else [(240, 200, 90), (230, 110, 80), (120, 180, 90)][k]
            cv2.ellipse(img, (int(x + (k * 16 - 6) * s * d), int(y - 7 * s)), (int(10 * s), int(7 * s)), 0, 0, 360, c, -1, cv2.LINE_AA)
    elif name == "gelas":
        _poly(img, [(x - 11 * s, y - 24 * s), (x + 11 * s, y - 24 * s), (x + 9 * s, y + 10 * s), (x - 9 * s, y + 10 * s)], (200, 230, 250), INK, 2)
        _rr(img, x - 9 * s, y - 8 * s, x + 9 * s, y + 8 * s, (120, 190, 240), None, 0)
    elif name == "hadiah":
        _rr(img, x - 22 * s, y - 22 * s, x + 22 * s, y + 18 * s, (224, 90, 120))
        cv2.line(img, (int(x), int(y - 22 * s)), (int(x), int(y + 18 * s)), (250, 220, 90), max(2, int(5 * s)))
        cv2.circle(img, (int(x), int(y - 26 * s)), int(7 * s), (250, 220, 90), -1, cv2.LINE_AA)
    elif name == "sapu" and other is not None:
        a, b = np.array(at), np.array(other)
        v = (a - b) / (np.linalg.norm(a - b) + 1e-6)
        tip = a + v * 70 * s
        top = b - v * 50 * s
        _ln(img, top, tip, (150, 110, 70), 6 * s)
        cv2.ellipse(img, (int(tip[0]), int(tip[1])), (int(26 * s), int(10 * s)), 0, 0, 360, (220, 190, 110), -1, cv2.LINE_AA)
    elif name == "bayi":
        if other is not None:
            x, y = (at[0] + other[0]) / 2, (at[1] + other[1]) / 2 - 6 * s
        cv2.ellipse(img, (int(x), int(y)), (int(34 * s), int(18 * s)), 0, 0, 360, (250, 236, 200), -1, cv2.LINE_AA)
        cv2.ellipse(img, (int(x), int(y)), (int(34 * s), int(18 * s)), 0, 0, 360, INK, 2, cv2.LINE_AA)
        cv2.circle(img, (int(x + 26 * s * d), int(y - 10 * s)), int(14 * s), (242, 201, 160), -1, cv2.LINE_AA)
        cv2.circle(img, (int(x + 26 * s * d), int(y - 10 * s)), int(14 * s), INK, 2, cv2.LINE_AA)
    elif name in ("handuk", "tisu"):
        _rr(img, x - 16 * s, y - 10 * s, x + 16 * s, y + 18 * s, (250, 250, 250) if name == "tisu" else (120, 190, 230))
    elif name == "tas":
        _rr(img, x - 18 * s, y, x + 18 * s, y + 30 * s, (150, 100, 70))
    elif name == "bola":
        cv2.circle(img, (int(x + 14 * s * d), int(y)), int(15 * s), (240, 120, 80), -1, cv2.LINE_AA)
        cv2.circle(img, (int(x + 14 * s * d), int(y)), int(15 * s), INK, 2, cv2.LINE_AA)


def draw_furniture(img, name, x, gy, s, d, t):
    if name == "kursi":
        _rr(img, x - 34 * s * d - 22 * s, gy - 74 * s, x - 34 * s * d + 30 * s, gy - 62 * s, (170, 120, 80))
        for k in (-18, 22):
            cv2.line(img, (int(x - 34 * s * d + k * s), int(gy - 62 * s)), (int(x - 34 * s * d + k * s), int(gy)), INK, int(5 * s))
    elif name == "kasur":
        _rr(img, x - 170 * s, gy - 52 * s, x + 170 * s, gy - 10 * s, (250, 250, 245))
        _rr(img, x - 180 * s, gy - 10 * s, x + 180 * s, gy, (160, 110, 80))
        cv2.ellipse(img, (int(x + 140 * s * d), int(gy - 58 * s)), (int(36 * s), int(14 * s)), 0, 0, 360, (190, 214, 240), -1, cv2.LINE_AA)
    elif name == "sajadah":
        _poly(img, [(x - 110 * s, gy + 4), (x + 110 * s, gy + 4), (x + 130 * s, gy + 26 * s), (x - 130 * s, gy + 26 * s)],
              (180, 60, 70), INK, 2)
        _poly(img, [(x - 92 * s, gy + 9), (x + 92 * s, gy + 9), (x + 106 * s, gy + 21 * s), (x - 106 * s, gy + 21 * s)],
              None, (240, 200, 90), 2)
    elif name == "kran":
        px = x + 70 * s * d
        cv2.line(img, (int(px), int(gy - 260 * s)), (int(px), int(gy - 205 * s)), (150, 160, 170), int(9 * s), cv2.LINE_AA)
        cv2.line(img, (int(px), int(gy - 205 * s)), (int(px - 26 * s * d), int(gy - 205 * s)), (150, 160, 170), int(9 * s), cv2.LINE_AA)
        for k in range(5):
            yy = gy - 195 * s + ((t * 300 + k * 30) % 150) * s
            cv2.line(img, (int(px - 26 * s * d), int(yy)), (int(px - 26 * s * d), int(yy + 12 * s)), (90, 170, 230), 3, cv2.LINE_AA)
    elif name == "shower":
        cv2.line(img, (int(x - 60 * s), int(gy - 360 * s)), (int(x + 20 * s), int(gy - 360 * s)), (150, 160, 170), int(8 * s))
        cv2.ellipse(img, (int(x), int(gy - 350 * s)), (int(34 * s), int(10 * s)), 0, 0, 360, (150, 160, 170), -1, cv2.LINE_AA)
        for k in range(10):
            xx = x - 30 * s + k * 7 * s
            yy = gy - 340 * s + ((t * 420 + k * 37) % 220) * s
            cv2.line(img, (int(xx), int(yy)), (int(xx), int(yy + 14 * s)), (90, 170, 230), 3, cv2.LINE_AA)
    elif name == "meja":
        tx = x + 80 * s * d
        _rr(img, tx - 70 * s, gy - 110 * s, tx + 70 * s, gy - 98 * s, (170, 120, 80))
        cv2.line(img, (int(tx - 60 * s), int(gy - 98 * s)), (int(tx - 60 * s), int(gy)), INK, int(5 * s))
        cv2.line(img, (int(tx + 60 * s), int(gy - 98 * s)), (int(tx + 60 * s), int(gy)), INK, int(5 * s))
        _poly(img, [(tx - 30 * s, gy - 110 * s), (tx + 30 * s, gy - 110 * s), (tx + 38 * s * d, gy - 160 * s), (tx - 22 * s * d, gy - 160 * s)],
              (60, 64, 74), INK, 2)
        cv2.circle(img, (int(tx + 8 * s * d), int(gy - 135 * s)), int(6 * s), (120, 200, 240), -1, cv2.LINE_AA)
    elif name == "kompor":
        tx = x + 85 * s * d
        _rr(img, tx - 70 * s, gy - 120 * s, tx + 70 * s, gy, (220, 200, 170))
        _rr(img, tx - 44 * s, gy - 160 * s, tx + 44 * s, gy - 120 * s, (90, 96, 110))
        cv2.ellipse(img, (int(tx), int(gy - 160 * s)), (int(44 * s), int(8 * s)), 0, 0, 360, (120, 126, 140), -1, cv2.LINE_AA)
        for k in range(3):
            fx = tx - 20 * s + k * 20 * s
            cv2.ellipse(img, (int(fx), int(gy - 116 * s)), (int(6 * s), int(10 * s + 3 * math.sin(t * 20 + k))), 0, 0, 360,
                        (250, 140, 60), -1, cv2.LINE_AA)


# ================================================================ efek
def draw_fx(img, kind, info, s, t, d, P):
    hc, hr = info["head"], info["hr"]
    hx, hy = float(hc[0]), float(hc[1])
    top = hy - hr * 1.6
    if kind in ("tanya", "seru", "jam", "hati", "bintang"):
        icon = {"tanya": "tanya", "seru": "seru", "jam": "jam", "hati": "hati", "bintang": "bintang"}[kind]
        sz = int(60 * s)
        bob = 5 * math.sin(t * 4)
        pop = D.ease_back(min(1.0, t / 0.35))
        D.icon(icon, sz, P).render(img, hx + hr * 0.8 * d - sz / 2, top - sz + bob, max(0.05, pop), 1.0, 0, 0)
    elif kind == "air_mata":
        for k in range(2):
            ph = (t * 1.4 + k * 0.5) % 1.0
            x = hx + (hr * 0.1 + k * hr * 0.42) * d - hr * 0.2
            y = hy + ph * hr * 2.2
            cv2.ellipse(img, (int(x), int(y)), (int(4 * s), int(7 * s)), 0, 0, 360, (90, 170, 230), -1, cv2.LINE_AA)
    elif kind == "marah":
        x, y = int(hx + hr * 0.9 * d), int(top)
        r = int(14 * s * (1 + 0.15 * math.sin(t * 12)))
        for a in range(4):
            ang = a * math.pi / 2 + math.pi / 4
            c = (int(x + math.cos(ang) * r), int(y + math.sin(ang) * r))
            cv2.ellipse(img, c, (int(r * 0.7), int(r * 0.7)), math.degrees(ang) + 180, -50, 50, (220, 50, 50), max(2, int(4 * s)), cv2.LINE_AA)
    elif kind == "keringat":
        ph = (t * 1.2) % 1.0
        x, y = hx - hr * 0.9 * d, hy - hr * 0.4 + ph * 20 * s
        cv2.ellipse(img, (int(x), int(y)), (int(5 * s), int(8 * s)), 0, 0, 360, (120, 190, 240), -1, cv2.LINE_AA)
    elif kind == "zzz":
        for k in range(3):
            ph = (t * 0.6 + k / 3) % 1.0
            sc = (0.5 + ph) * s
            cv2.putText(img, "Z", (int(hx + 20 * s + ph * 70 * s), int(hy - 30 * s - ph * 110 * s)), cv2.FONT_HERSHEY_SIMPLEX, sc,
                        (70, 90, 160), max(1, int(3 * s)), cv2.LINE_AA)
    elif kind == "cahaya":
        for k in range(8):
            ph = (t * 0.5 + k / 8) % 1.0
            x = hx + math.sin(k * 2.3) * 60 * s
            y = hy - ph * 140 * s
            r = max(1, int(5 * s * (1 - ph)))
            cv2.circle(img, (int(x), int(y)), r, (240, 200, 80), -1, cv2.LINE_AA)
    elif kind in ("air", "air_atas"):
        src = info["wrf"] if kind == "air" else hc - np.array([0, 60 * s])
        for k in range(6):
            ph = (t * 1.6 + k / 6) % 1.0
            x = src[0] + math.sin(k * 1.9) * 26 * s
            y = src[1] + ph * 120 * s
            cv2.ellipse(img, (int(x), int(y)), (int(4 * s), int(7 * s)), 0, 0, 360, (90, 170, 230), -1, cv2.LINE_AA)
    elif kind == "busa":
        w = info["wrf"]
        for k in range(6):
            ph = (t * 0.8 + k / 6) % 1.0
            cv2.circle(img, (int(w[0] + math.sin(k * 2.1 + t) * 22 * s), int(w[1] - ph * 70 * s)), int((4 + k % 3 * 3) * s),
                       (250, 250, 255), 2, cv2.LINE_AA)
    elif kind == "uap":
        x0 = hx + 85 * s * d
        for k in range(3):
            pts = [(x0 - 20 * s + k * 20 * s + 8 * s * math.sin(t * 3 + j * 0.8 + k), info["feet"][1] - 175 * s - j * 14 * s) for j in range(7)]
            cv2.polylines(img, [np.int32(pts)], False, (200, 200, 205), max(2, int(3 * s)), cv2.LINE_AA)
    elif kind == "puff":
        m = info["mouth"]
        for k in range(5):
            r = int((8 + k * 5) * s)
            cv2.circle(img, (int(m[0] + (20 + k * 16) * s * d), int(m[1] - k * 3 * s)), r, (225, 228, 232), -1, cv2.LINE_AA)
    elif kind == "pusing":
        for k in range(3):
            a = t * 5 + k * 2.1
            cv2.circle(img, (int(hx + math.cos(a) * hr * 1.3), int(top + 10 * s + math.sin(a) * hr * 0.35)), int(6 * s),
                       (240, 200, 70), -1, cv2.LINE_AA)


def beat_fx(img, kind, t, w, h, gy, P, s):
    """Efek babak (besar, di panggung)."""
    if not kind:
        return
    if kind in ("hati", "bintang", "lampu", "tanya", "seru", "jam", "uang", "petir"):
        icon = {"uang": "koin"}.get(kind, kind)
        if kind in ("hati", "bintang", "uang"):
            for k in range(7):
                ph = (t * 0.45 + k / 7) % 1.0
                x = w * (0.15 + 0.7 * ((k * 0.37) % 1.0))
                y = (h * 0.15 + ph * gy * 0.8) if kind == "uang" else (gy - ph * gy * 0.85)
                sz = int(46 * s * (0.7 + 0.3 * math.sin(k)))
                D.icon(icon, sz, P).render(img, x - sz / 2, y - sz / 2, 1.0, 1.0, 0, 0)
        else:
            pop = D.ease_back(min(1.0, t / 0.4))
            sz = int(110 * s)
            D.icon(icon, sz, P).render(img, w - 150 - sz / 2, 40 + 6 * math.sin(t * 3), max(0.05, pop), 1.0, 0, 0)
    elif kind == "cahaya":
        ov = img.copy()
        for k in range(9):
            a = math.radians(-160 + k * 18 + 4 * math.sin(t))
            p2 = (int(w / 2 + math.cos(a) * w), int(-20 + math.sin(a) * w))
            cv2.line(ov, (w // 2, -20), (p2[0], -p2[1] + 40), (255, 236, 160), 30)
        cv2.addWeighted(ov, 0.25, img, 0.75, 0, dst=img)
    elif kind in ("air", "hujan"):
        for k in range(36 if kind == "hujan" else 14):
            x = (k * 97 + 13) % w
            y = (t * (900 if kind == "hujan" else 300) + k * 131) % (gy + 40)
            if kind == "hujan":
                cv2.line(img, (int(x), int(y)), (int(x - 8), int(y + 26)), (120, 170, 220), 2, cv2.LINE_AA)
            else:
                cv2.ellipse(img, (int(x), int(y)), (5, 8), 0, 0, 360, (90, 170, 230), -1, cv2.LINE_AA)
    elif kind == "zzz":
        pass


# ================================================================ CERITA PER ANAK KALIMAT (semua yang diucapkan diperagakan)
NOUN_EXTRA = {
    "puasa": "bulan", "shaum": "bulan", "berpuasa": "bulan", "ulama": "buku", "dalil": "buku", "hukum": "timbangan", "fikih": "buku",
    "fiqih": "buku", "sengaja": "lampu", "lupa": "tanya", "rongga": "hidung", "batang": "hidung", "pangkal": "hidung",
    "tenggorokan": "mulut", "perut": "piring", "obat": "tetes", "jari": "tangan", "kuku": "tangan",
    "kotoran": "awan", "contoh": "lampu", "hari": "matahari", "detik": "jam", "menit": "jam", "jam": "jam", "makanan": "piring",
    "minuman": "tetes", "darah": "tetes", "keringat": "tetes", "ludah": "mulut", "gigi": "mulut", "lidah": "mulut", "badan": "senyum",
    "tubuh": "senyum", "jiwa": "hati", "akhirat": "pohon", "dunia": "matahari", "uang": "koin", "harta": "koin", "orang": "senyum",
}
NO_BUBBLE_ICON = {"centang", "silang", "angka", "tanya", "seru"}
SALAM = {"assalamualaikum", "assalamu'alaikum", "assalamu", "yuk", "mari", "halo", "sahabat", "teman-teman", "hai"}
TEKAN = {"penting", "ingat", "perlu", "harus", "wajib", "perhatikan", "catat", "awas"}
KONDISI = {"jika", "kalau", "apabila", "selama", "asal", "asalkan", "seandainya", "ketika", "saat", "bila"}
SEBAB = {"karena", "sebab", "soalnya", "lantaran"}
TANYA_W = {"kenapa", "mengapa", "bagaimana", "apakah", "apa", "bolehkah", "benarkah"}
CONJ = KONDISI | SEBAB | CONTRA | CONCL | {"dan", "lalu", "kemudian", "atau", "agar", "supaya", "bahwa", "yaitu", "seperti"}

# tipe -> (aksi A, pilihan reaksi B, jenis balon, ikon bawaan, efek)
TYPE_ACT = {
    "salam": (["lambai"], ["lambai", "senang"], "bicara", ["senyum"], None),
    "ragu": (["mikir", "pusing"], ["mikir", "pusing", "geleng"], "pikir", ["tanya"], None),
    "kondisi": (["mikir", "tunjuk"], ["angguk", "mikir"], "pikir", [], None),
    "sebab": (["tunjuk", "bicara"], ["mikir", "angguk"], "bicara", ["lampu"], None),
    "paham": (["senang", "tunjuk"], ["tepuk_tangan", "senang", "angguk"], "bicara", ["lampu"], "bintang"),
    "tekan": (["tunjuk"], ["kaget", "angguk", "mikir"], "bicara", ["seru"], None),
    "kontras": (["geleng", "bicara", "tolak"], ["kaget", "mikir"], "bicara", ["seru"], None),
    "positif": (["senang", "angguk", "tepuk_tangan"], ["tepuk_tangan", "senang", "angguk"], "bicara", ["senyum"], "hati"),
    "negatif": (["tolak", "geleng"], ["kaget", "takut", "mikir"], "bicara", ["seru"], None),
    "jelaskan": (["bicara", "tunjuk", "bicara"], ["angguk", "mikir", "angguk", "bicara"], "bicara", [], None),
}


def _punct(sc, words):
    """Tanda baca setelah tiap kata TTS (diselaraskan dengan teks naskah)."""
    toks = []
    for m in re.finditer(r"[\w\-'’]+([.,!?;:]*)", K.spoken_text(sc)):
        toks.append((K._norm(m.group(0)), (m.group(1) or "")[:1]))
    out, j = [], 0
    for _t, _d, w in words:
        n = K._norm(w)
        hit = next((k for k in range(j, min(len(toks), j + 5)) if toks[k][0] == n), None)
        if hit is not None:
            j = hit + 1
            out.append(toks[hit][1])
        else:
            out.append("")
    return out


def clauses(sc, words):
    """Pecah kata TTS jadi anak kalimat: tanda baca, jeda > 0.22 dtk, kata sambung, atau maks 8 kata; min ±1.1 dtk."""
    pun = _punct(sc, words)
    out, cur = [], []
    for i, (t, d, w) in enumerate(words):
        n = K._norm(w)
        gap = t - (words[i - 1][0] + words[i - 1][1]) if i else 0
        cdur = (t - words[cur[0]][0]) if cur else 0.0
        if cur and (((n in CONJ or n in KONDISI or n in ("tidak", "bukan")) and cdur >= 0.9 and len(cur) >= 2)
                    or (gap > 0.25 and cdur >= 0.9) or len(cur) >= 6):
            out.append(cur)
            cur = []
        cur.append(i)
        if pun[i] in ".!?;:" and len(cur) >= 2:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    merged = []
    for c in out:                                                    # gabung potongan terlalu pendek
        dur = words[c[-1]][0] + words[c[-1]][1] - words[c[0]][0]
        if merged and (dur < 0.7 or len(c) < 2) and len(merged[-1]) < 6:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    if len(merged) > 1:
        c = merged[-1]
        if words[c[-1]][0] + words[c[-1]][1] - words[c[0]][0] < 0.6:
            last = merged.pop()
            merged[-1] = merged[-1] + last
    return merged, pun


SUCI = {"allah", "tuhan", "ta'ala", "swt", "ilahi", "rabb", "nabi", "rasul", "rasulullah", "muhammad", "saw", "malaikat",
        "jibril", "sahabat"}


def _icons(words, idx):
    """Ikon benda yang disebut. Lafaz Allah/Nabi/Rasul/malaikat TIDAK PERNAH digambar/disimbolkan."""
    out = []
    for i in idx:
        n = K._norm(words[i][2])
        if n in SUCI or any(c in SUCI for c in K._cands(n)) or "allah" in n or "rasul" in n:
            continue
        ic = None
        for c in K._cands(n):
            if c in NOUN_EXTRA:
                ic = NOUN_EXTRA[c]
                break
        if not ic:
            m = K.match(words[i][2])
            if m and m[1] not in NO_BUBBLE_ICON:
                ic = m[1]
        if ic and ic not in out:
            out.append(ic)
    return out[:2]


def clause_beats(sc, words, cast, state, seed=0):
    """Satu babak untuk SETIAP anak kalimat yang diucapkan (waktu dari TTS)."""
    if not words:
        return []
    state = state if state is not None else {"home": "rumah", "last": "rumah", "seed": seed, "n": 0, "used": {}}
    used = state.setdefault("used", {})
    rng = random.Random(seed * 13 + state["n"] * 977 + state.get("seed", 0))
    ids = list(cast)
    A, B = ids[0], (ids[1] if len(ids) > 1 else None)
    side = rng.random() < 0.5
    pa, pb = ("kiri", "kanan") if side else ("kanan", "kiri")
    cl, pun = clauses(sc, words)
    ask = K.ask_flags(sc, words)
    setting = state["last"]
    night = False
    beats, last_pair = [], None
    speaker = A
    split = []
    for idx in cl:                                                       # 'ngupil ... tidak membatalkan' -> peragakan aksinya dulu
        hi = next((i for i in idx if any(c in KEYMAP and KEYMAP[c][0] != "mikir" for c in K._cands(K._norm(words[i][2])))), None)
        ri = next((i for i in idx if any(c in NEG_RULE or c in POS_RULE for c in K._cands(K._norm(words[i][2])))), None)
        if hi is not None and ri is not None and ri - hi >= 2 and idx.index(ri) >= 2:
            k_ = idx.index(ri) - (1 if K.negated(words, ri) else 0)
            split += [idx[:k_], idx[k_:]]
        else:
            split.append(idx)
    cl = [c for c in split if c]
    for ci, idx in enumerate(cl):
        toks = [K._norm(words[i][2]) for i in idx]
        cands = [K._cands(n) for n in toks]
        is_ask = any(ask[i] for i in idx) or any(n in TANYA_W for n in toks)
        hit, hit_i = None, None
        for k_, cs in enumerate(cands):
            h = next((KEYMAP[c] for c in cs if c in KEYMAP), None)
            if h and h[0] not in ("mikir",):
                hit, hit_i = h, idx[k_]
                break
        neg_rule = [i for k_, i in enumerate(idx) if any(c in NEG_RULE for c in cands[k_]) and not K.idiom(words, i)]
        pos_rule = [i for k_, i in enumerate(idx) if any(c in POS_RULE for c in cands[k_]) and not K.negated(words, i)]
        if any(n in SALAM for n in toks) and ci == 0:
            kind = "salam"
        elif is_ask:
            kind = "aksi" if hit else "ragu"
        elif neg_rule:
            kind = "positif" if all(K.negated(words, i) for i in neg_rule) else "negatif"
        elif any(n in CONCL for n in toks[:2]):
            kind = "paham"
        elif any(n in CONTRA for n in toks[:2]):
            kind = "kontras"
        elif hit:
            kind = "aksi"
        elif pos_rule:
            kind = "positif"
        elif any(n in KONDISI for n in toks[:2]):
            kind = "kondisi"
        elif any(n in SEBAB for n in toks[:2]):
            kind = "sebab"
        elif any(n in TEKAN for n in toks):
            kind = "tekan"
        else:
            kind = "jelaskan"
        if any(n in ("malam", "tidur", "sahur", "tahajud", "isya", "gelap") for n in toks):
            night = True
        icons = _icons(words, idx)
        efek = None
        if kind == "aksi":
            a, lat, bd, ef, a2 = hit
            u = used.get(a, [])
            if any(c in BODY for cs in cands for c in cs) and a in ("cuci_tangan", "wudhu", "mandi"):
                a, lat = state.get("topic") or a, "rumah"
            if lat != "rumah":
                setting = lat
            elif u and rng.random() < 0.6:
                setting = rng.choice([x for x in ("rumah", "halaman", "kantor", "jalan", "kamar", "dapur") if x != setting])
            solo = a in SOLO_OK and rng.random() < 0.3
            pool = ["kaget", "mikir", "geleng"] if a in ODD else ["angguk", "mikir", "tunjuk", "bicara"]
            pool = [x for x in pool if x not in [r_ for _s, r_ in u]] or pool
            rb = a2 if (a2 and not u) else rng.choice(pool)
            if rb == a and a not in ("salaman", "peluk"):
                rb = rng.choice([x for x in ("angguk", "mikir", "senang") if x != a])
            if is_ask:                                                     # pertanyaan: aksinya diperagakan, lawan main bertanya-tanya
                rb = rng.choice(["mikir", "pusing"])
                solo = False
                icons = (["tanya"] + icons)[:2]
            used.setdefault(a, []).append((setting, rb))
            tk = [{"id": A, "aksi": a, "emosi": "biasa", "posisi": "tengah" if (solo or not B) else pa, "benda": bd}]
            if B and not solo:
                tk.append({"id": B, "aksi": rb, "emosi": "biasa", "posisi": pb, "benda": None})
            bub_who = B if (B and not solo) else (A if icons else None)
            bub_kind = "pikir" if rb in ("mikir", "kaget", "geleng", "takut") or bub_who == A else "bicara"
            icons = [i for i in icons if i not in ("tetes",) or a not in ("wudhu", "mandi", "cuci_tangan")]
            efek = ef if ef in ("hati", "bintang", "cahaya", "jam", "uang", "zzz", "air", "hujan") else None
        else:
            acts_a, acts_b, bub_kind, base_icons, efek = TYPE_ACT[kind]
            if kind == "jelaskan" and B and rng.random() < 0.35:
                speaker = B if speaker == A else A                             # gantian yang menjelaskan
            spk = speaker if kind == "jelaskan" else A
            lis = (B if spk == A else A) if B else None
            aa = rng.choice(acts_a)
            ab = rng.choice([x for x in acts_b if x != aa] or acts_b)
            if last_pair == (aa, ab):
                aa = rng.choice(acts_a[::-1])
                ab = rng.choice([x for x in acts_b if x not in (ab, aa)] or acts_b)
            tk = [{"id": spk, "aksi": aa, "emosi": "senang" if kind in ("paham", "positif", "salam") else
                   ("bingung" if kind in ("ragu", "kondisi") else "biasa"), "posisi": pa if spk == A else pb, "benda": None}]
            if lis:
                tk.append({"id": lis, "aksi": ab, "emosi": "biasa", "posisi": pb if spk == A else pa, "benda": None})
            icons = (icons + [i for i in base_icons if i not in icons])[:2]
            bub_who = spk
        last_pair = (tk[0]["aksi"], tk[1]["aksi"] if len(tk) > 1 else None)
        t0 = 0.0 if ci == 0 else max(0.0, words[idx[0]][0] - 0.1)
        if kind == "aksi" and tk[0]["aksi"] == "lihat_jam" and rng.random() < 0.5:
            tk[0]["aksi"] = "lapar"
        beats.append({"_idx": idx, "kata": words[idx[0]][2], "latar": setting, "malam": night, "tokoh": tk, "efek": efek, "t0": t0,
                      "bubble": {"who": bub_who, "kind": bub_kind, "icons": icons} if bub_who and (icons or bub_kind == "bicara") else None,
                      "kind": kind})
    for j, b in enumerate(beats):
        b["t1"] = beats[j + 1]["t0"] if j + 1 < len(beats) else 9e9
    _shots(beats, words, cast, state, rng)
    state["last"] = setting
    state["n"] += 1
    return adab(beats, cast)


def _shots(beats, words, cast, state, rng):
    """Pilihan shot ala editor: close-up anatomi, kajian ulama, adegan bayangan, insert benda."""
    last_wide = None
    run = 0
    prev_shot = None
    last_part = state.get("last_part") or ("hidung" if state.get("topic") == "ngupil" else None)
    for b in beats:
        idx = b.get("_idx") or []
        toks = [K._norm(words[i][2]) for i in idx]
        cands = [set(K._cands(n)) | {n} for n in toks]
        allc = set().union(*cands) if cands else set()
        shot = None
        part = next((BODY[c] for cs in cands for c in cs if c in BODY), None)
        if not part and last_part and (allc & {"rongga", "pangkal", "pangkalnya", "batang", "lubang", "ujung"} or allc & INSERT_VERB or
                                       (allc & {"luar", "dalam"} and allc & (INSERT_VERB | {"area", "bagian", "sampai", "ke"}))):
            part = last_part
        if part:
            last_part = state["last_part"] = part
        if allc & ULAMA:
            shot = "kajian"
        elif part in ("hidung", "mulut", "telinga", "mata", "wajah", "kepala") and (
                allc & set(SPATIAL) or allc & INSERT_VERB or b.get("kind") in ("jelaskan", "aksi", "kontras", "kondisi")):
            shot = "dekat"
        elif b.get("kind") == "kondisi" or (allc & {"tindakan", "perbuatan", "dilakukan", "melakukan"}) or (allc & SENGAJA):
            shot = "bayang"
        elif b.get("kind") == "jelaskan" and b.get("bubble") and b["bubble"].get("icons") and prev_shot not in ("benda",) \
                and rng.random() < 0.55:
            shot = "benda"
        if shot and shot == prev_shot and shot not in ("dekat", "bayang"):
            run += 1
            if run >= 2:
                shot = None
        else:
            run = 0
        t0 = b["t0"]
        if shot == "dekat":
            labs = []
            for i, n, cs in zip(idx, toks, cands):
                key = next((SPATIAL[c] for c in cs if c in SPATIAL and c not in ("terlalu", "melebihi")), None) or                     next((BODY[c] for c in cs if c in BODY), None)
                if key and key not in [l_[2] for l_ in labs]:
                    labs.append((max(0.0, words[i][0] - t0), re.sub(r"[^\w\-]", "", words[i][2]).upper(), key))
            b.update(shot="dekat", part=part, labels=labs, finger=bool(allc & INSERT_VERB) or (part == "hidung" and state.get("topic") == "ngupil"
                     and bool(allc & {"benda", "sesuatu", "jari", "masuk", "memasukkan", "dalam", "luar", "rongga"})),
                     deep=bool(allc & {"dalam", "melebihi", "terlalu", "pangkal", "pangkalnya"}), kotoran="kotoran" in allc)
        elif shot == "kajian":
            if "U" not in cast:
                lk = _look("kakek", random.Random(state.get("seed", 0) + 5))
                lk["nama"] = "ulama"
                cast["U"] = lk
            ids = [c for c in cast if c != "U"][:2]
            tk = [{"id": "U", "aksi": "baca" if rng.random() < 0.5 else "bicara", "emosi": "tenang", "posisi": "kanan", "benda": "buku"}]
            for k_, cid in enumerate(ids):
                tk.append({"id": cid, "aksi": "duduk_sholat", "emosi": "biasa", "posisi": ("kiri", "tengah")[k_], "benda": None})
            ic = (b.get("bubble") or {}).get("icons") or []
            b.update(shot=None, latar="masjid", tokoh=tk, bubble={"who": "U", "kind": "bicara", "icons": (["buku"] + [x for x in ic if x != "buku"])[:2]})
        elif shot == "bayang":
            hit = next((KEYMAP[c][0] for cs in cands for c in cs if c in KEYMAP and KEYMAP[c][0] not in ("mikir", "tunjuk", "angguk")), None)
            act = hit or state.get("topic") or "bicara"
            cue = "seru" if allc & SENGAJA else ("tanya" if allc & {"lupa", "terlupa"} else None)
            b.update(shot="bayang", bayang_aksi=act, cue=cue, bayang_emo="kaget" if cue == "seru" else "biasa")
        elif shot == "benda":
            labs = []
            for i in idx:
                m = K.match(words[i][2])
                n = K._norm(words[i][2])
                if (m and m[1] in b["bubble"]["icons"]) or any(c in NOUN_EXTRA for c in K._cands(n)):
                    labs.append((max(0.0, words[i][0] - t0), re.sub(r"[^\w\-]", "", words[i][2]).upper(), n))
            b.update(shot="benda", icons=b["bubble"]["icons"], labels=labs[:2])
        if b.get("shot"):                                                  # shot khusus: tokoh tetap seperti babak lebar sebelumnya
            if last_wide:
                b["tokoh"] = [dict(x) for x in last_wide["tokoh"]]
                b["latar"], b["malam"] = last_wide["latar"], last_wide.get("malam")
            b["bubble"] = None
        else:
            last_wide = b
        prev_shot = b.get("shot") or ("kajian" if shot == "kajian" else None)
    # shot sama berurutan (close-up / bayangan) -> satu shot panjang, label bertambah mengikuti ucapan (tidak berkedip)
    out = []
    for b in beats:
        p = out[-1] if out else None
        if p and b.get("shot") in ("dekat", "bayang") and p.get("shot") == b.get("shot") and p.get("part") == b.get("part"):
            off = b["t0"] - p["t0"]
            p["t1"] = b["t1"]
            if b.get("shot") == "dekat":
                have = [l_[2] for l_ in p["labels"]]
                p["labels"] += [(tw + off, tx, ky) for tw, tx, ky in b.get("labels", []) if ky not in have]
                p["finger"] = p.get("finger") or b.get("finger")
                p["deep"] = p.get("deep") or b.get("deep")
                p["kotoran"] = p.get("kotoran") or b.get("kotoran")
            else:
                p["cue"] = p.get("cue") or b.get("cue")
                if b.get("cue") == "seru":
                    p["bayang_emo"] = "kaget"
            continue
        out.append(b)
    beats[:] = out


# ================================================================ balon bicara / pikiran
def draw_bubble(img, info, kind, icons, t, s, d, P, w, h):
    q = D.ease_back(min(1.0, max(0.0, t) / 0.3))
    if q <= 0.02:
        return
    hc, hr = info["head"], info["hr"]
    n = max(1, len(icons))
    bw, bh = (60 + 92 * n) * s * q, 112 * s * q
    cx = float(hc[0]) + d * (bw * 0.35 + hr * 0.4)
    cy = float(hc[1]) - hr * 1.3 - bh / 2 - 26 * s + 4 * math.sin(t * 3)
    cx = min(max(cx, bw / 2 + 10), w - bw / 2 - 10)
    cy = max(cy, bh / 2 + 8)
    x0, y0, x1, y1 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
    white = (255, 255, 255)
    if kind == "pikir":
        for k in range(9):                                                   # awan pikiran
            a = k / 9 * 2 * math.pi
            cv2.circle(img, (int(cx + math.cos(a) * bw * 0.42), int(cy + math.sin(a) * bh * 0.36)), max(1, int(bh * 0.32)), INK, -1, cv2.LINE_AA)
        for k in range(9):
            a = k / 9 * 2 * math.pi
            cv2.circle(img, (int(cx + math.cos(a) * bw * 0.42), int(cy + math.sin(a) * bh * 0.36)), max(1, int(bh * 0.32 - 3)), white, -1, cv2.LINE_AA)
        cv2.ellipse(img, (int(cx), int(cy)), (int(bw * 0.44), int(bh * 0.4)), 0, 0, 360, white, -1, cv2.LINE_AA)
        for k, r in enumerate((9, 6)):
            px = hc[0] + (cx - hc[0]) * (0.3 + 0.25 * k)
            py = hc[1] - hr + (y1 - hc[1] + hr) * (0.3 + 0.25 * k)
            cv2.circle(img, (int(px), int(py)), max(1, int(r * s * q)), white, -1, cv2.LINE_AA)
            cv2.circle(img, (int(px), int(py)), max(1, int(r * s * q)), INK, 2, cv2.LINE_AA)
    else:
        tail = np.int32([(cx - 14 * s, y1 - 2), (cx + 14 * s, y1 - 2), (hc[0] + d * hr * 0.6, hc[1] - hr * 0.9)])
        cv2.fillPoly(img, [tail], white, cv2.LINE_AA)
        cv2.polylines(img, [tail], False, INK, 3, cv2.LINE_AA)
        _rr(img, x0, y0, x1, y1, white, INK, 3)
        cv2.fillPoly(img, [np.int32([(cx - 11 * s, y1 - 5), (cx + 11 * s, y1 - 5), (cx, y1 + 3)])], white, cv2.LINE_AA)
    if q < 0.6:
        return
    if icons:
        sz = int(74 * s)
        for k, ic in enumerate(icons):
            ix = cx - (n - 1) * 46 * s + k * 92 * s
            D.icon(ic, sz, P).render(img, ix - sz / 2, cy - sz / 2 + 2 * math.sin(t * 4 + k), 1.0, 1.0, 0, 0)
    else:                                                                    # titik-titik "sedang menjelaskan"
        for k in range(3):
            r = int((6 + 3 * max(0.0, math.sin(t * 7 - k))) * s)
            cv2.circle(img, (int(cx - 26 * s + k * 26 * s), int(cy)), r, INK, -1, cv2.LINE_AA)


# ================================================================ nuansa (beda tiap video)
MOODS = ["cerah", "senja", "malam", "hujan", "pastel", "komik", "gugur"]
MOOD_DEF = {
    "cerah": dict(mul=(1.02, 1.02, 1.0), add=(4, 4, 0), c=1.05, part="kilau"),
    "senja": dict(mul=(1.06, 0.9, 0.76), add=(22, 8, -4), c=1.0, part="debu"),
    "malam": dict(mul=(0.82, 0.88, 1.05), add=(-4, 2, 18), c=1.0, part="kunang", night=True),
    "hujan": dict(mul=(0.88, 0.93, 1.0), add=(4, 10, 18), c=0.96, part="hujan", sat=0.72),
    "pastel": dict(mul=(0.86, 0.84, 0.9), add=(36, 30, 36), c=0.92, part="kelopak"),
    "komik": dict(mul=(1.0, 1.0, 1.0), add=(0, 0, 0), c=1.2, part="halftone"),
    "gugur": dict(mul=(1.06, 0.94, 0.8), add=(12, 4, -6), c=1.02, part="daun"),
}
_LUT = {}
_DOTS = {}


def _mood_lut(name):
    if name not in _LUT:
        m = MOOD_DEF[name]
        x = np.arange(256, dtype=np.float32)
        _LUT[name] = [np.clip(((x - 128) * m["c"] + 128) * mu + ad, 0, 255).astype(np.uint8) for mu, ad in zip(m["mul"], m["add"])]
    return _LUT[name]


def apply_mood(img, name, t, outdoor, gy):
    if not name or name not in MOOD_DEF:
        return img
    m = MOOD_DEF[name]
    lut = _mood_lut(name)
    ch = cv2.split(img)
    img = cv2.merge([cv2.LUT(c, l) for c, l in zip(ch, lut)])
    if m.get("sat"):
        g = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
        img = cv2.addWeighted(img, m["sat"], g, 1 - m["sat"], 0)
    h, w = img.shape[:2]
    part = m["part"]
    if part == "halftone":
        key = (w, h)
        if key not in _DOTS:
            dm = np.zeros((h, w), np.uint8)
            for y in range(0, h, 10):
                for x in range((y // 10 % 2) * 5, w, 10):
                    cv2.circle(dm, (x, y), 2, 26, -1)
            _DOTS[key] = cv2.merge([dm, dm, dm])
        img = cv2.subtract(img, _DOTS[key])
    elif part == "kilau":
        for k in range(10):
            ph = (t * 0.7 + k * 0.37) % 1.0
            x, y = int((k * 173 + 40) % w), int((k * 97 + 30) % max(1, gy - 60))
            r = int(9 * math.sin(ph * math.pi))
            if r > 1:
                cv2.line(img, (x - r, y), (x + r, y), (255, 255, 240), 2, cv2.LINE_AA)
                cv2.line(img, (x, y - r), (x, y + r), (255, 255, 240), 2, cv2.LINE_AA)
    elif part in ("debu", "kunang"):
        col = (255, 220, 120) if part == "debu" else (220, 255, 140)
        for k in range(16):
            x = (k * 131 + 50 * math.sin(t * 0.6 + k)) % w
            y = (k * 71 + 30 * math.cos(t * 0.8 + k * 2)) % gy
            a = 0.5 + 0.5 * math.sin(t * 3 + k)
            cv2.circle(img, (int(x), int(y)), int(2 + 3 * a), col, -1, cv2.LINE_AA)
    elif part == "hujan":
        if outdoor:
            for k in range(46):
                x = (k * 97 + 13) % w
                y = (t * 950 + k * 131) % (gy + 40)
                cv2.line(img, (int(x), int(y)), (int(x - 7), int(y + 24)), (190, 210, 235), 2, cv2.LINE_AA)
        else:                                                               # tetes air di "kaca" kamera
            for k in range(7):
                x = (k * 151 + 60) % w
                y = (t * (40 + k * 9) + k * 120) % h
                cv2.circle(img, (int(x), int(y)), 6, (225, 236, 248), -1, cv2.LINE_AA)
                cv2.line(img, (int(x), int(y) - 30), (int(x), int(y)), (215, 228, 244), 3, cv2.LINE_AA)
    elif part in ("kelopak", "daun"):
        cols = [(250, 190, 210), (255, 220, 230)] if part == "kelopak" else [(222, 120, 50), (240, 170, 60), (190, 80, 40)]
        for k in range(12):
            ph = (t * 0.18 + k / 12) % 1.0
            x = (k * 89 + 80 * math.sin(t * 1.2 + k)) % w
            y = ph * (gy + 40) - 20
            ang = (t * 90 + k * 40) % 360
            cv2.ellipse(img, (int(x), int(y)), (9, 5), ang, 0, 360, cols[k % len(cols)], -1, cv2.LINE_AA)
    return img


def comic_lines(img, cx, cy, t, w, h):
    """Garis aksi khas komik saat babak baru dimulai."""
    if t > 0.32:
        return
    a = 1 - t / 0.32
    ov = img.copy()
    for k in range(18):
        ang = k / 18 * 2 * math.pi + 0.2
        r0, r1 = 150 + 40 * (k % 3), 150 + 40 * (k % 3) + 160 * a
        cv2.line(ov, (int(cx + math.cos(ang) * r0), int(cy + math.sin(ang) * r0)),
                 (int(cx + math.cos(ang) * r1), int(cy + math.sin(ang) * r1)), (255, 255, 255), 6, cv2.LINE_AA)
    cv2.addWeighted(ov, 0.7 * a, img, 1 - 0.7 * a, 0, dst=img)


def blend_pose(p0, p1, q):
    if p0.get("rot") != p1.get("rot") or (p0.get("seat") is None) != (p1.get("seat") is None):
        return p1
    out = dict(p1)
    for k_, v in p1.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(p0.get(k_), (int, float)) and k_ != "seat":
            out[k_] = p0[k_] + (v - p0[k_]) * q
    return out


# ================================================================ SHOT KHUSUS (editor): close-up anatomi, insert benda, kajian, bayangan
BODY = {"hidung": "hidung", "mulut": "mulut", "bibir": "mulut", "gigi": "mulut", "lidah": "mulut", "kumur": "mulut",
        "tenggorokan": "mulut", "kerongkongan": "mulut", "telinga": "telinga", "kuping": "telinga", "mata": "mata",
        "wajah": "wajah", "muka": "wajah", "kepala": "kepala", "rambut": "kepala", "tangan": "tangan", "siku": "tangan",
        "jari": "tangan", "kaki": "kaki", "perut": "perut", "badan": "perut", "tubuh": "perut"}
SPATIAL = {"luar": "luar", "dalam": "dalam", "pangkal": "pangkal", "pangkalnya": "pangkal", "batang": "batang", "ujung": "ujung",
           "rongga": "rongga", "lubang": "rongga", "tenggorokan": "tenggorokan", "kerongkongan": "tenggorokan", "melebihi": "dalam",
           "terlalu": "dalam", "gigi": "gigi", "lidah": "lidah", "bibir": "mulut", "siku": "siku", "telapak": "telapak"}
INSERT_VERB = {"masuk", "memasukkan", "dimasukkan", "ngupil", "mengupil", "upil", "membersihkan", "korek", "mengorek", "kumur",
               "berkumur", "menyentuh", "sentuh"}
ULAMA = {"ulama", "ustadz", "ustad", "kyai", "kiai", "guru", "kajian", "syaikh", "syekh", "imam", "mazhab", "madzhab"}
SENGAJA = {"sengaja", "sadar", "sadarnya", "secara sengaja"}
LUPA = {"lupa", "terlupa", "tidak sengaja", "tak sengaja"}


def topic_action(script):
    """Aksi pokok video (paling sering disebut): dipakai untuk 'tindakan tersebut', shot bayangan, dll."""
    cnt = {}
    for a in script.get("adegan", []):
        for w in re.findall(r"[\w\-]+", ((a.get("narasi") or "") + " " + (a.get("penjelasan") or "")).lower()):
            for c in K._cands(K._norm(w)):
                if c in KEYMAP and KEYMAP[c][0] not in ("mikir", "jalan", "bicara", "angguk", "tunjuk", "lihat_jam", "senang"):
                    cnt[KEYMAP[c][0]] = cnt.get(KEYMAP[c][0], 0) + 1
                    break
    return max(cnt, key=cnt.get) if cnt else None


def _label_pill(img, text, x, y, P, k=1.0, col=None):
    blk = D.text_block(text, "hand", 34, (255, 255, 255), 400)[0]
    h, w = blk.shape[:2]
    s = max(0.05, k)
    pw, ph = (w + 26) * s, (h + 4) * s
    c = col or tuple(int(v) for v in D.rgb(P["accent"]))
    cv2.rectangle(img, (int(x - pw / 2), int(y - ph / 2)), (int(x + pw / 2), int(y + ph / 2)), INK, -1, cv2.LINE_AA)
    cv2.rectangle(img, (int(x - pw / 2 + 3), int(y - ph / 2 + 3)), (int(x + pw / 2 - 3), int(y + ph / 2 - 3)), c, -1, cv2.LINE_AA)
    if k > 0.5:
        D.blit(img, blk, x, y, scale=s, anchor="c")
    return pw, ph


def _arrow(img, a, b, col=INK, w=4):
    cv2.arrowedLine(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), col, w, cv2.LINE_AA, tipLength=0.08)


def render_closeup(img, b, lt, look, P, t_abs):
    """Close-up kepala dari samping: hidung (luar/dalam/batang/pangkal), mulut (gigi/lidah/tenggorokan), telinga, mata.
    Label muncul tepat saat katanya diucapkan; jari bergerak sesuai kata kerja."""
    h, w = img.shape[:2]
    part = b["part"]
    R = min(h * 0.34, 220)
    cx, cy = w * 0.36, h * 0.5
    z = 1.0 + 0.04 * min(1.0, lt / 2.5)                                           # dorong pelan
    R *= z
    skin, ink = look["skin"], INK
    female = look["jenis"] in ("wanita", "nenek", "anak_p")
    # leher + baju
    _poly(img, [(cx - R * 0.25, cy + R * 0.7), (cx + R * 0.45, cy + R * 0.7), (cx + R * 0.5, h + 5), (cx - R * 0.3, h + 5)], skin, ink, 4)
    _poly(img, [(cx - R * 1.1, h + 5), (cx - R * 0.6, cy + R * 1.05), (cx + R * 0.8, cy + R * 1.05), (cx + R * 1.3, h + 5)],
          look["shirt"], ink, 4)
    if female:
        cv2.circle(img, (int(cx - R * 0.08), int(cy - R * 0.02)), int(R * 1.16), look["hijab"], -1, cv2.LINE_AA)
        _poly(img, [(cx - R * 1.15, cy), (cx + R * 0.2, cy + R * 0.6), (cx + R * 0.4, cy + R * 1.4), (cx - R * 1.3, cy + R * 1.4)],
              look["hijab"], None, 0)
        cv2.circle(img, (int(cx - R * 0.08), int(cy - R * 0.02)), int(R * 1.16), ink, 4, cv2.LINE_AA)
    cv2.circle(img, (int(cx), int(cy)), int(R), skin, -1, cv2.LINE_AA)
    cv2.circle(img, (int(cx), int(cy)), int(R), ink, 5, cv2.LINE_AA)
    if not female and look.get("peci", True):
        _poly(img, [(cx - R * 0.9, cy - R * 0.42), (cx + R * 0.75, cy - R * 0.55), (cx + R * 0.62, cy - R * 1.02),
                    (cx - R * 0.82, cy - R * 0.98)], (40, 40, 44), ink, 3)
    # hidung, mata, mulut, telinga
    nose = [(cx + R * 0.74, cy - R * 0.3), (cx + R * 1.2, cy + R * 0.2), (cx + R * 1.06, cy + R * 0.33), (cx + R * 0.86, cy + R * 0.33)]
    _poly(img, nose, skin, ink, 5)
    cv2.line(img, (int(cx + R * 0.86), int(cy + R * 0.33)), (int(cx + R * 0.86), int(cy + R * 0.2)), skin, 7)
    nos = (cx + R * 0.98, cy + R * 0.27)
    cv2.ellipse(img, (int(nos[0]), int(nos[1])), (int(R * 0.07), int(R * 0.035)), 0, 0, 360, (90, 50, 50), -1, cv2.LINE_AA)
    blink = (t_abs * 0.9) % 3.3 > 3.18
    ey = (cx + R * 0.55, cy - R * 0.22)
    if blink:
        cv2.line(img, (int(ey[0] - R * 0.08), int(ey[1])), (int(ey[0] + R * 0.08), int(ey[1])), ink, 4)
    else:
        cv2.circle(img, (int(ey[0]), int(ey[1])), int(R * 0.06), ink, -1, cv2.LINE_AA)
    cv2.line(img, (int(ey[0] - R * 0.12), int(ey[1] - R * 0.14)), (int(ey[0] + R * 0.12), int(ey[1] - R * 0.18)), ink, 4, cv2.LINE_AA)
    mo = (cx + R * 0.82, cy + R * 0.58)
    cv2.ellipse(img, (int(mo[0]), int(mo[1])), (int(R * 0.14), int(R * 0.05)), 0, 0, 180, ink, 4, cv2.LINE_AA)
    if not female:
        ear = (cx - R * 0.08, cy + R * 0.02)
        cv2.ellipse(img, (int(ear[0]), int(ear[1])), (int(R * 0.12), int(R * 0.2)), 0, 0, 360, _dk(skin, 0.1), -1, cv2.LINE_AA)
        cv2.ellipse(img, (int(ear[0]), int(ear[1])), (int(R * 0.12), int(R * 0.2)), 0, 0, 360, ink, 3, cv2.LINE_AA)
        if look.get("beard"):
            cv2.ellipse(img, (int(cx + R * 0.55), int(cy + R * 0.72)), (int(R * 0.38), int(R * 0.2)), 15, 0, 180, (52, 44, 40), -1, cv2.LINE_AA)
    else:
        ear = (cx - R * 0.08, cy + R * 0.02)
    anchors = {"hidung": nos, "rongga": nos, "luar": nos, "ujung": (cx + R * 1.2, cy + R * 0.2),
               "batang": (cx + R * 0.97, cy - R * 0.05), "pangkal": (cx + R * 0.76, cy - R * 0.26), "dalam": (cx + R * 0.56, cy + R * 0.06),
               "mulut": mo, "gigi": (mo[0] - R * 0.02, mo[1] - R * 0.02), "lidah": (mo[0] - R * 0.1, mo[1] + R * 0.02),
               "tenggorokan": (cx + R * 0.22, cy + R * 0.78), "telinga": ear, "mata": ey, "wajah": (cx + R * 0.6, cy), "kepala": (cx, cy - R * 0.6)}
    # potongan rongga dalam (tembus pandang)
    if part in ("hidung", "mulut"):
        ov = img.copy()
        chan = [nos, (cx + R * 0.78, cy + R * 0.16), (cx + R * 0.56, cy + R * 0.06), (cx + R * 0.36, cy + R * 0.22),
                (cx + R * 0.24, cy + R * 0.8)] if part == "hidung" else \
               [mo, (mo[0] - R * 0.2, mo[1] - R * 0.02), (cx + R * 0.36, cy + R * 0.3), (cx + R * 0.24, cy + R * 0.8)]
        cv2.polylines(ov, [np.int32(chan)], False, (236, 150, 150), int(R * 0.12), cv2.LINE_AA)
        cv2.addWeighted(ov, 0.55, img, 0.45, 0, dst=img)
        for k in range(len(chan) - 1):                                        # garis putus-putus tepi rongga
            a, c2 = np.array(chan[k]), np.array(chan[k + 1])
            for q in np.linspace(0, 1, 6)[:-1]:
                p1, p2 = a + (c2 - a) * q, a + (c2 - a) * (q + 0.09)
                cv2.line(img, (int(p1[0]), int(p1[1] - R * 0.06)), (int(p2[0]), int(p2[1] - R * 0.06)), (170, 80, 80), 2, cv2.LINE_AA)
        # garis batas luar/dalam (hanya bila kata 'luar'/'dalam'/'batang'/'pangkal' memang diucapkan)
        keys = [lab[2] for lab in b.get("labels", [])]
        if part == "hidung" and any(k_ in keys for k_ in ("luar", "dalam", "batang", "pangkal")):
            bx = cx + R * 0.86
            for yy in np.linspace(cy - R * 0.25, cy + R * 0.4, 9):
                cv2.line(img, (int(bx), int(yy)), (int(bx), int(yy + R * 0.04)), tuple(int(v) for v in D.rgb(P["accent2"])), 4)
    # jari bergerak (kata kerja memasukkan/ngupil/membersihkan)
    if b.get("finger"):
        deep = b.get("deep") and lt >= min([tw for tw, _x, ky in b.get("labels", []) if ky in ("dalam", "pangkal")] or [0.0])
        target = np.array(anchors["dalam"] if deep else anchors["luar" if part == "hidung" else part], float)
        start = np.array([w * 0.95, h * 1.05])
        ph = 0.5 + 0.5 * math.sin(lt * 4.0)
        tip = target + np.array([R * 0.25, R * 0.12]) * (1 - min(1.0, lt / 0.4)) + np.array([R * 0.05, R * 0.02]) * ph
        if deep:
            tip = np.array(anchors["luar"]) + (target - np.array(anchors["luar"])) * (0.35 + 0.65 * ph)
        elbow = (start + tip) / 2 + np.array([R * 0.25, R * 0.25])
        _limb(img, [start, elbow, tip + np.array([R * 0.16, R * 0.05])], look["shirt"], R * 0.13)
        _limb(img, [tip + np.array([R * 0.16, R * 0.05]), tip], skin, R * 0.07)
        if b.get("kotoran") and ph < 0.3 and not deep:
            cv2.circle(img, (int(tip[0] + R * 0.02), int(tip[1])), int(R * 0.035), (140, 160, 90), -1, cv2.LINE_AA)
    # label tepat saat kata diucapkan
    labs = b.get("labels", [])
    xs = w * 0.83
    for n, (tw, text, key) in enumerate(labs[:4]):
        a = lt - tw
        if a < 0:
            continue
        k = D.ease_back(min(1.0, a / 0.3))
        y = h * 0.18 + n * (h * 0.2)
        anc = anchors.get(key, anchors.get(part, (cx, cy)))
        pulse = 1 + 0.25 * math.sin(a * 8)
        cv2.circle(img, (int(anc[0]), int(anc[1])), int(R * 0.09 * pulse * k), tuple(int(v) for v in D.rgb(P["accent2"])), 4, cv2.LINE_AA)
        if k > 0.4:
            _arrow(img, (xs - 70, y), anc, INK, 4)
        _label_pill(img, text, xs, y, P, k)


def render_benda(img, b, lt, look, P, s):
    """Insert benda: benda yang disebut tampil besar di tengah dengan sinar berputar + label kata yang diucapkan."""
    h, w = img.shape[:2]
    icons = b.get("icons") or ["bintang"]
    n = len(icons)
    ov = img.copy()
    cx, cy = w * 0.55, h * 0.45
    for k in range(14):
        a = k / 14 * 2 * math.pi + lt * 0.6
        cv2.line(ov, (int(cx), int(cy)), (int(cx + math.cos(a) * w), int(cy + math.sin(a) * w)), (255, 244, 200), 26)
    cv2.addWeighted(ov, 0.45, img, 0.55, 0, dst=img)
    for i, ic in enumerate(icons):
        q = D.ease_back(min(1.0, max(0.0, lt - i * 0.25) / 0.4))
        if q <= 0.02:
            continue
        sz = int(h * (0.5 if n == 1 else 0.38))
        x = cx + (i - (n - 1) / 2) * sz * 1.15
        D.icon(ic, sz, P).render(img, x - sz * q / 2, cy - sz * q / 2 + 6 * math.sin(lt * 3 + i), q, 1.0, 0, 0)
    for n_, (tw, text, _key) in enumerate(b.get("labels", [])[:2]):
        a = lt - tw
        if a >= 0:
            _label_pill(img, text, cx + (n_ - (min(2, len(b["labels"])) - 1) / 2) * 260, h * 0.84, P, D.ease_back(min(1.0, a / 0.3)))
    p = pose_of("tunjuk", lt, 0.4)
    draw_person(img, w * 0.12, h - 46, s * 0.85, 1, p, look, "senang", lt, 0.5)


def render_bayang(img, b, lt, cast, P, s, mood, ctx_talk, var):
    """Tokoh membayangkan: awan pikiran besar berisi adegan kecil (mis. 'jika dilakukan dengan sengaja')."""
    h, w = img.shape[:2]
    A = b["tokoh"][0]["id"]
    look = cast[A]
    draw_person(img, w * 0.16, h - 46, s, 1, pose_of("mikir", lt, 0.3), look, "bingung", lt, 0.0)
    q = D.ease_back(min(1.0, max(0.0, lt - 0.1) / 0.35))
    if q <= 0.02:
        return
    bw, bh = w * 0.64 * q, h * 0.74 * q
    cx, cy = w * 0.62, h * 0.44
    for k in range(12):                                                           # awan
        a = k / 12 * 2 * math.pi
        cv2.circle(img, (int(cx + math.cos(a) * bw * 0.46), int(cy + math.sin(a) * bh * 0.44)), max(1, int(bh * 0.2)), INK, -1, cv2.LINE_AA)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        cv2.circle(img, (int(cx + math.cos(a) * bw * 0.46), int(cy + math.sin(a) * bh * 0.44)), max(1, int(bh * 0.2 - 4)), (255, 255, 255), -1,
                   cv2.LINE_AA)
    for k, r in enumerate((10, 16)):
        cv2.circle(img, (int(w * 0.24 + k * 40), int(h * 0.42 - k * 30)), r, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(img, (int(w * 0.24 + k * 40), int(h * 0.42 - k * 30)), r, INK, 3, cv2.LINE_AA)
    if q < 0.7:
        return
    mw, mh = int(bw * 0.86), int(bh * 0.8)
    mgy = mh - 24
    mini = background(b.get("latar", "rumah"), bool(b.get("malam")), mw, mh, mgy, var).copy()
    act = b.get("bayang_aksi") or "bicara"
    p = pose_of(act, lt, 0.9)
    ms = min(1.0, (mgy - 30) / 300.0)
    if p["auto"] in ("kursi", "kasur", "sajadah", "shower"):
        draw_furniture(mini, p["auto"], mw * 0.45, mgy, ms, 1, lt)
    info = draw_person(mini, mw * 0.45, mgy, ms, 1, p, look, b.get("bayang_emo", "biasa"), lt, 0.0)
    if p["auto"] in ("kran", "meja", "kompor"):
        draw_furniture(mini, p["auto"], mw * 0.45, mgy, ms, 1, lt)
    cue = b.get("cue")
    if cue:
        draw_fx(mini, cue, info, ms, lt, 1, P)
    m = np.zeros((mh, mw), np.uint8)
    cv2.ellipse(m, (mw // 2, mh // 2), (mw // 2 - 4, mh // 2 - 4), 0, 0, 360, 255, -1, cv2.LINE_AA)
    x0, y0 = int(cx - mw / 2), int(cy - mh / 2)
    roi = img[max(0, y0):y0 + mh, max(0, x0):x0 + mw]
    mm = m[max(0, -y0):max(0, -y0) + roi.shape[0], max(0, -x0):max(0, -x0) + roi.shape[1]]
    mi = mini[max(0, -y0):max(0, -y0) + roi.shape[0], max(0, -x0):max(0, -x0) + roi.shape[1]]
    roi[mm > 0] = mi[mm > 0]
    cv2.ellipse(img, (int(cx), int(cy)), (mw // 2 - 4, mh // 2 - 4), 0, 0, 360, INK, 3, cv2.LINE_AA)


SHOT_PASS = True


# ================================================================ aktor panggung
POSX = {"kiri": 0.24, "tengah": 0.5, "kanan": 0.76}
ENTER = ["jalan", "pop", "jatuh"]
TRANS = ["iris", "geser", "kilat", "tirai"]
NEED_FRONT = {"kran": 0, "meja": 0, "kompor": 0}


class StoryA:
    """Panggung cerita satu adegan: x0..x1, y0..y1 (koordinat layar)."""

    def __init__(self, beats, cast, box, P, seed=0, sfx_out=None, mood=None):
        self.cast, self.P, self.seed, self.mood = cast, P, seed, mood
        self.night_all = bool(mood and MOOD_DEF.get(mood, {}).get("night"))
        self.x0, self.y0, self.x1, self.y1 = [int(v) for v in box]
        self.w, self.h = self.x1 - self.x0, self.y1 - self.y0
        self.gy = self.h - 46
        self.s = min(1.45, max(0.9, (self.gy - 60) / 300.0))
        rng = random.Random(seed)
        self.var = rng.randint(0, 9)
        self.beats = beats
        self.trans = [rng.choice(TRANS) for _ in beats]
        prev = {}
        for j, b in enumerate(beats):
            acts = {}
            n = len(b["tokoh"])
            used = set()
            for k, tk in enumerate(b["tokoh"]):
                pos = tk.get("posisi") or ""
                if pos not in POSX or pos in used:
                    pos = [["tengah"], ["kiri", "kanan"], ["kiri", "tengah", "kanan"]][n - 1][k]
                used.add(pos)
                acts[tk["id"]] = {"x": POSX[pos] * self.w, "aksi": tk["aksi"], "emo": tk.get("emosi") or "biasa",
                                  "benda": tk.get("benda"), "ph": rng.random() * 6}
            # salaman/peluk -> berdekatan di tengah
            pair = [i for i, a in acts.items() if a["aksi"] in ("salaman", "peluk")]
            if len(pair) >= 2:
                gap = 66 if acts[pair[0]]["aksi"] == "peluk" else 96
                acts[pair[0]]["x"], acts[pair[1]]["x"] = self.w / 2 - gap * self.s, self.w / 2 + gap * self.s
            # arah hadap: ke tokoh lain / ke tengah
            for k2, (i, a) in enumerate(acts.items()):
                others = [o["x"] for oi, o in acts.items() if oi != i]
                tx = sum(others) / len(others) if others else self.w / 2 + (1 if a["x"] < self.w / 2 else -1)
                a["d"] = 1 if tx >= a["x"] else -1
                if a["aksi"] in PRAY:
                    a["d"] = 1
                # masuk / pindah posisi
                if i in prev and not b.get("_cut"):
                    a["from"] = prev[i]["x"]
                    a["enter"] = None
                    a["prev_act"] = prev[i]["aksi"]
                else:
                    a["from"] = None
                    a["enter"] = rng.choice(ENTER) if j > 0 or k2 > 0 else rng.choice(["jalan", "pop"])
            b["_acts"] = acts
            same_set = j > 0 and beats[j - 1]["latar"] == b["latar"] and beats[j - 1].get("malam") == b.get("malam")
            b["_trans"] = None if (j == 0 or same_set) else self.trans[j]
            if b["_trans"]:
                for a in acts.values():
                    a["from"], a["enter"] = None, None                       # adegan baru: tokoh sudah di tempat
            b["_exit"] = {i: a for i, a in prev.items() if i not in acts} if same_set else {}
            prev = acts
        self.mask = None
        self._prev_cache = {}

    # -------------------------------------------------------- render babak ke kanvas panggung
    def _render_beat(self, j, t, ctx):
        b = self.beats[j]
        lt = t - b["t0"]
        shot = b.get("shot")
        if shot in ("dekat", "benda", "bayang"):
            main = b["tokoh"][0]["id"] if b.get("tokoh") else next(iter(self.cast))
            look = self.cast.get(main) or next(iter(self.cast.values()))
            if shot == "dekat":
                base = WALLS[(self.var + j) % len(WALLS)]
                img = _grad(self.h, self.w, _lt(base, 0.35), _dk(base, 0.08))
                if self.night_all:
                    img = (img * 0.7).astype(np.uint8)
                render_closeup(img, b, lt, look, self.P, ctx.get("tg", t))
            elif shot == "benda":
                img = background(b["latar"], bool(b.get("malam")) or self.night_all, self.w, self.h, self.gy, self.var).copy()
                img = cv2.addWeighted(img, 0.55, np.full_like(img, 255), 0.45, 0)
                render_benda(img, b, lt, look, self.P, self.s)
            else:
                img = background(b["latar"], bool(b.get("malam")) or self.night_all, self.w, self.h, self.gy, self.var).copy()
                render_bayang(img, b, lt, self.cast, self.P, self.s, self.mood, 0, self.var)
            comic_lines(img, self.w * 0.5, self.h * 0.5, lt, self.w, self.h)
            return img
        img = background(b["latar"], bool(b.get("malam")) or self.night_all, self.w, self.h, self.gy, self.var).copy()
        s, gy, P = self.s, self.gy, self.P
        talk = 0.0
        try:
            talk = min(1.0, float(ctx["mouth"](ctx.get("tg", 0.0))) * 1.4) if ctx.get("talking") else 0.0
        except Exception:
            talk = 0.0
        beat_bg = b.get("efek") in ("cahaya",)
        if beat_bg:
            beat_fx(img, "cahaya", lt, self.w, self.h, gy, P, s)
        # keluar (babak sebelumnya, latar sama): berjalan keluar layar
        for i, a in b["_exit"].items():
            if lt > 0.8 or i not in self.cast:
                continue
            look = self.cast[i]
            d = -1 if a["x"] < self.w / 2 else 1
            x = a["x"] + d * (lt / 0.8) * (self.w * 0.6)
            sc = s * (0.72 if look["jenis"].startswith("anak") else 1.0)
            draw_person(img, x, gy, sc, d, pose_of("jalan", lt, a["ph"]), look, "biasa", lt, 0.0)
        if b.get("kind") in ("aksi", "paham", "positif", "negatif", "tekan", "kontras") or self.mood == "komik":
            first = next(iter(b["_acts"].values()), None)
            if first:
                comic_lines(img, first["x"], gy - 170 * s, lt, self.w, self.h)
        infos = {}
        speakers = [i for i, a in b["_acts"].items() if pose_of(a["aksi"], 0, 0)["talk"]]
        order = sorted(b["_acts"].items(), key=lambda kv: kv[1]["x"])
        for idx, (i, a) in enumerate(order):
            if i not in self.cast:
                continue
            look = self.cast[i]
            sc = s * (0.72 if look["jenis"].startswith("anak") else (0.55 if look["jenis"] == "bayi" else 1.0))
            act, x, d, k_alpha, yoff, scale_k = a["aksi"], a["x"], a["d"], 1.0, 0.0, 1.0
            la = lt - 0.12 * idx
            if a.get("from") is not None and abs(a["from"] - a["x"]) > 8:
                mv = min(0.9, abs(a["from"] - a["x"]) / 420)
                if la < mv:
                    q = D.ease_out(max(0.0, la) / mv)
                    x = a["from"] + (a["x"] - a["from"]) * q
                    act = "jalan"
                    d = 1 if a["x"] > a["from"] else -1
            elif a.get("enter"):
                en = a["enter"]
                if la < 0:
                    continue
                if en == "jalan" and la < 0.85:
                    side = -1 if a["x"] < self.w / 2 else 1
                    x = a["x"] + side * (1 - D.ease_out(la / 0.85)) * (self.w * 0.55)
                    act = "jalan"
                    d = -side
                elif en == "pop" and la < 0.4:
                    scale_k = max(0.05, D.ease_back(la / 0.4))
                elif en == "jatuh" and la < 0.55:
                    q = la / 0.55
                    yoff = -(1 - q * q) * (self.h * 0.9)
                    if q > 0.85:
                        scale_k = 1.0
            p = pose_of(act, la, a["ph"])
            if act == a["aksi"] and a.get("prev_act") and a["prev_act"] != act and 0 <= la < 0.3:   # gerak menyambung halus
                p = blend_pose(pose_of(a["prev_act"], la + 2.0, a["ph"]), p, D.ease_out(la / 0.3))
            p["dy"] += yoff / max(0.3, sc)
            emo = a["emo"] if a["emo"] != "biasa" else DEFAULT_EMO.get(act, "biasa")
            if p["auto"] and act == a["aksi"]:
                if p["auto"] in ("kursi", "kasur", "sajadah", "shower"):
                    draw_furniture(img, p["auto"], x, gy, sc, d, la)
            tk = talk if (len(speakers) <= 1 or i == speakers[int(lt / 2.2) % len(speakers)]) else 0.0
            info = draw_person(img, x, gy, sc * scale_k, d, p, look, emo, la, tk)
            infos[i] = (info, sc, d)
            if p["auto"] in ("kran", "meja", "kompor") and act == a["aksi"]:
                draw_furniture(img, p["auto"], x, gy, sc, d, la)
            prop = a.get("benda") or {"makan": "piring", "minum": "gelas", "baca": "buku", "beri": "hadiah", "gendong": "bayi",
                                      "sapu": "sapu", "telepon": "hp", "bersin": "tisu"}.get(act)
            if prop and act == a["aksi"]:
                hold = p["hold"]
                if hold == "2":
                    draw_prop(img, prop, info["wrf"], sc, d, la, info["wrb"])
                else:
                    draw_prop(img, prop, info["wrf"] if hold == "f" else info["wrb"], sc, d, la)
            if p["fx"] and act == a["aksi"] and la > 0.2:
                draw_fx(img, p["fx"], info, sc, la - 0.2, d, P)
            if scale_k < 1.0 and a.get("enter") == "pop":
                for q in range(6):                                          # debu muncul
                    ang = q * math.pi / 3
                    r = 30 + 60 * (1 - scale_k)
                    cv2.circle(img, (int(x + math.cos(ang) * r), int(gy - 20 + math.sin(ang) * r * 0.4)), int(10 * (1 - scale_k) + 3),
                               (235, 235, 238), -1, cv2.LINE_AA)
        if not beat_bg:
            beat_fx(img, b.get("efek"), lt, self.w, self.h, gy, P, s)
        bub = b.get("bubble")
        if bub and bub.get("who") in infos:
            info, sc_, d_ = infos[bub["who"]]
            draw_bubble(img, info, bub["kind"], bub["icons"], lt - 0.12, sc_, d_, P, self.w, self.h)
        return img

    def _camera(self, img, j, t):
        b = self.beats[j]
        lt = t - b["t0"]
        span = max(1.0, b["t1"] - b["t0"])
        z = 1.0 + 0.06 * min(1.0, lt / span) + 0.05 * math.exp(-lt * 6.0)        # dorong pelan + hentakan saat babak mulai
        xs = [a["x"] for a in b["_acts"].values()] or [self.w / 2]
        fx = sum(xs) / len(xs)
        cw, ch = self.w / z, self.h / z
        cx = min(max(fx, cw / 2), self.w - cw / 2)
        cy = min(max(self.gy - ch * 0.42, ch / 2), self.h - ch / 2)
        x0, y0 = int(cx - cw / 2), int(cy - ch / 2)
        crop = img[y0:y0 + int(ch), x0:x0 + int(cw)]
        return cv2.resize(crop, (self.w, self.h), interpolation=cv2.INTER_LINEAR)

    def _frame(self, j, t, ctx):
        b = self.beats[j]
        fr = self._camera(self._render_beat(j, t, ctx), j, t)
        return apply_mood(fr, self.mood, t, b["latar"] in ("halaman", "jalan", "pasar"), self.gy)

    def draw(self, img, t, ctx):
        if not self.beats or t < 0:
            return None
        j = 0
        while j + 1 < len(self.beats) and t >= self.beats[j + 1]["t0"]:
            j += 1
        fr = self._frame(j, t, ctx)
        b = self.beats[j]
        lt = t - b["t0"]
        tr = b.get("_trans")
        if tr and lt < 0.45:
            if j not in self._prev_cache:
                self._prev_cache = {j: self._frame(j - 1, b["t0"] - 1e-3, ctx)}
            prev = self._prev_cache[j]
            q = D.ease_out(lt / 0.45)
            if tr == "iris":
                m = np.zeros((self.h, self.w), np.uint8)
                cv2.circle(m, (self.w // 2, self.h // 2), int(q * math.hypot(self.w, self.h) / 2), 255, -1, cv2.LINE_AA)
                a = (m.astype(np.float32) / 255)[..., None]
                fr = (fr * a + prev * (1 - a)).astype(np.uint8)
            elif tr == "geser":
                off = int((1 - q) * self.w)
                fr = np.concatenate([prev[:, self.w - off:] if off else prev[:, :0], fr[:, :self.w - off]], 1) if off else fr
                fr = np.ascontiguousarray(fr)
            elif tr == "tirai":
                cut = int(q * self.h)
                fr = fr.copy()
                fr[cut:] = prev[cut:]
            else:                                                                 # kilat
                fr = cv2.addWeighted(fr, q, np.full_like(fr, 255), 1 - q, 0)
        # tempel ke layar dengan sudut membulat + bingkai
        k = D.ease_out(min(1.0, t / 0.35))
        if self.mask is None:
            m = np.zeros((self.h, self.w), np.uint8)
            cv2.rectangle(m, (22, 0), (self.w - 23, self.h - 1), 255, -1)
            cv2.rectangle(m, (0, 22), (self.w - 1, self.h - 23), 255, -1)
            for cx, cy in ((22, 22), (self.w - 23, 22), (22, self.h - 23), (self.w - 23, self.h - 23)):
                cv2.circle(m, (cx, cy), 22, 255, -1, cv2.LINE_AA)
            self.mask = (m.astype(np.float32) / 255)[..., None]
        roi = img[self.y0:self.y1, self.x0:self.x1]
        a = self.mask * k
        roi[:] = (fr.astype(np.float32) * a + roi.astype(np.float32) * (1 - a)).astype(np.uint8)
        ink = tuple(int(v) for v in D.rgb(self.P["ink"]))
        _round_border(img, self.x0, self.y0, self.x1, self.y1, 22, ink, 5)
        self._flow(img, j, t)
        return None

    def _flow(self, img, j, t):
        """Alur cerita 1 → 2 → 3: nomor babak muncul satu per satu di pojok kiri atas panggung."""
        if len(self.beats) < 2:
            return
        acc = tuple(int(v) for v in D.rgb(self.P["accent"]))
        acc2 = tuple(int(v) for v in D.rgb(self.P["accent2"]))
        x, y = self.x0 + 44, self.y0 + 40
        for i in range(max(0, j - 5), j + 1):
            lt = t - self.beats[i]["t0"]
            pop = D.ease_back(min(1.0, lt / 0.35)) if i == j else 1.0
            r = int(22 * pop) + (2 if i == j else 0)
            if i > max(0, j - 5):
                cv2.arrowedLine(img, (x - 44, y), (x - 26, y), INK, 3, cv2.LINE_AA, tipLength=0.5)
            cv2.circle(img, (x, y), r + 3, INK, -1, cv2.LINE_AA)
            cv2.circle(img, (x, y), r, acc2 if i == j else acc, -1, cv2.LINE_AA)
            if pop > 0.6:
                lab = str(i + 1)
                cv2.putText(img, lab, (x - 8 * len(lab), y + 9), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255) if i != j else INK, 2,
                            cv2.LINE_AA)
            x += 62


def _round_border(img, x0, y0, x1, y1, r, col, w):
    cv2.line(img, (x0 + r, y0), (x1 - r, y0), col, w, cv2.LINE_AA)
    cv2.line(img, (x0 + r, y1 - 1), (x1 - r, y1 - 1), col, w, cv2.LINE_AA)
    cv2.line(img, (x0, y0 + r), (x0, y1 - r), col, w, cv2.LINE_AA)
    cv2.line(img, (x1 - 1, y0 + r), (x1 - 1, y1 - r), col, w, cv2.LINE_AA)
    for cx, cy, a0 in ((x0 + r, y0 + r, 180), (x1 - r - 1, y0 + r, 270), (x1 - r - 1, y1 - r - 1, 0), (x0 + r, y1 - r - 1, 90)):
        cv2.ellipse(img, (cx, cy), (r, r), 0, a0, a0 + 90, col, w, cv2.LINE_AA)


def plan_story(sc, seg, beats, cast, box, P, seed=0, state=None, mood=None):
    """-> (StoryA, sfx) untuk satu adegan (waktu relatif awal adegan).
    beats=None -> SETIAP anak kalimat yang diucapkan jadi babak (clause_beats); selain itu babak manual/LLM (timed_beats)."""
    if beats is None:
        tb = clause_beats(sc, seg.get("words") or [], cast, state, seed)
        if tb:
            tb[-1]["t1"] = seg["dur"] + 0.5
    elif not beats:
        return None, []
    else:
        tb = timed_beats(beats, seg.get("words") or [], seg["speech"], seg["dur"])
    if not tb:
        return None, []
    st = StoryA(tb, cast, box, P, seed, mood=mood or (state or {}).get("mood"))
    sfx = [(0.05, "pop2", 0.5)]
    for j, b in enumerate(tb[1:], 1):
        if b.get("_trans"):
            sfx.append((b["t0"], "swish", 0.55))
        elif b.get("kind", "aksi") != "jelaskan":
            sfx.append((b["t0"], "pop", 0.3))
        if b.get("efek") in ("hati", "bintang", "cahaya", "lampu"):
            sfx.append((b["t0"] + 0.2, "sparkle", 0.45))
    return st, sfx
