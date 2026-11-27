"""
Kata kunci -> gambar & efek tepat saat kata diucapkan (waktu per kata dari edge-tts).

  keywords(words)          deteksi kata bermakna (kamus LEX; mengabaikan imbuhan: membasuh -> basuh)
  plan_scene(...)          pilih kata (prioritas, jarak minimal, cooldown ikon) -> aktor stiker/stempel/efek + SFX
  StickerA                 lencana bulat putih + ikon + label kata, muncul membal, melayang, lalu mengecil
  StampA                   kata besar (WAJIB, JANGAN, ...) menghentak di tengah layar
  GlowA                    sinar emas berdenyut (untuk "Allah")
Hanya MENGULANG kata yang memang diucapkan di narasi; tidak menambah klaim.
"""
import math
import re

import numpy as np

import aw_doodle as D
import aw_fx as FX

W, H = D.W, D.H

# akar kata -> (ikon, prioritas, efek, label_tampil|None)
#   efek: None | burst_hati | burst_air | confetti | cahaya | stempel
LEX = {
    # --- tokoh keluarga (juga memicu ILUSTRASI tokoh di panggung, lihat aw_cerita)
    "istri": ("istri", 6, None, "ISTRI"), "isteri": ("istri", 6, None, "ISTRI"), "suami": ("suami", 6, None, "SUAMI"),
    "anak": ("anak", 5, None, "ANAK"), "anak-anak": ("anak", 5, None, "ANAK"), "putra": ("anak", 5, None, "ANAK"), "putri": ("anak_p", 5, None, "ANAK"),
    "bayi": ("bayi", 5, None, "BAYI"), "ibu": ("ibu", 5, None, "IBU"), "bunda": ("ibu", 5, None, "IBU"), "umi": ("ibu", 5, None, "IBU"),
    "ayah": ("ayah", 5, None, "AYAH"), "bapak": ("ayah", 5, None, "AYAH"), "abi": ("ayah", 5, None, "AYAH"),
    "kakek": ("kakek", 5, None, "KAKEK"), "nenek": ("nenek", 5, None, "NENEK"), "teman": ("teman", 4, None, "TEMAN"), "tetangga": ("teman", 4, None, "TETANGGA"),
    "keluarga": ("keluarga", 5, None, "KELUARGA"), "perempuan": ("istri", 4, None, "PEREMPUAN"), "wanita": ("istri", 4, None, "WANITA"),
    "laki-laki": ("suami", 4, None, "LAKI-LAKI"), "lelaki": ("suami", 4, None, "LAKI-LAKI"),
    # --- benda cerita
    "nafkah": ("koin", 5, None, "NAFKAH"), "gaji": ("koin", 4, None, None), "uang": ("koin", 4, None, None), "harta": ("koin", 4, None, None),
    "kerja": ("tas", 4, None, None), "bekerja": ("tas", 4, None, None), "kantor": ("tas", 3, None, None),
    "masak": ("panci", 4, None, None), "memasak": ("panci", 4, None, None), "dapur": ("panci", 3, None, None),
    "sekolah": ("sekolah", 4, None, None), "belajar": ("buku", 3, None, None), "didik": ("sekolah", 4, None, None), "pendidikan": ("sekolah", 4, None, None),
    "nikah": ("cincin", 5, "burst_hati", "NIKAH"), "menikah": ("cincin", 5, "burst_hati", "NIKAH"), "pernikahan": ("cincin", 5, "burst_hati", "NIKAH"),
    "mahar": ("cincin", 4, None, None),
    # --- wudhu & anggota tubuh
    "wudhu": ("tetes", 5, "burst_air", "WUDHU"), "wudu": ("tetes", 5, "burst_air", "WUDHU"),
    "air": ("tetes", 4, "burst_air", None), "tetes": ("tetes", 3, "burst_air", None),
    "basuh": ("pancuran", 4, "burst_air", None), "bilas": ("pancuran", 3, "burst_air", None), "mandi": ("pancuran", 4, "burst_air", None),
    "cuci": ("sabun", 3, None, None), "bersih": ("sabun", 4, "confetti", None), "suci": ("tetes", 4, "burst_air", None),
    "wajah": ("wajah", 5, "burst_air", None), "muka": ("wajah", 4, "burst_air", None),
    "tangan": ("tangan", 4, None, None), "siku": ("tangan", 3, None, None),
    "kepala": ("kepala", 5, "burst_air", None), "rambut": ("kepala", 3, None, None), "usap": ("kepala", 3, None, None),
    "telinga": ("telinga", 5, None, None), "kaki": ("kaki", 5, "burst_air", None),
    "kumur": ("mulut", 5, "burst_air", None), "mulut": ("mulut", 4, None, None), "hidung": ("hidung", 5, "burst_air", None),
    "mata": ("mata", 3, None, None),
    # --- ibadah & iman
    "sholat": ("sajadah", 5, None, "SHOLAT"), "shalat": ("sajadah", 5, None, "SHOLAT"), "salat": ("sajadah", 5, None, "SHOLAT"),
    "sajadah": ("sajadah", 3, None, None), "masjid": ("masjid", 4, None, None), "mesjid": ("masjid", 4, None, None),
    "kiblat": ("kabah", 4, None, None), "kabah": ("kabah", 4, None, None), "haji": ("kabah", 3, None, None), "umrah": ("kabah", 3, None, None),
    "allah": ("bulan", 6, "cahaya", "ALLAH"), "ta'ala": ("bintang", 3, "cahaya", None), "tuhan": ("bulan", 4, "cahaya", None),
    "quran": ("buku", 5, None, "AL-QUR'AN"), "alquran": ("buku", 5, None, "AL-QUR'AN"), "ayat": ("buku", 3, None, None), "kitab": ("buku", 3, None, None),
    "hadits": ("buku", 4, None, None), "ilmu": ("lampu", 4, None, None), "hikmah": ("lampu", 5, "confetti", "HIKMAH"),
    "doa": ("tangan", 5, None, "DOA"), "berdoa": ("tangan", 5, None, "DOA"), "niat": ("hati", 5, "burst_hati", "NIAT"),
    "hati": ("hati", 5, "burst_hati", None), "ikhlas": ("hati", 5, "burst_hati", "IKHLAS"), "tenang": ("hati", 4, "burst_hati", None),
    "sabar": ("hati", 4, "burst_hati", None), "cinta": ("hati", 4, "burst_hati", None), "sayang": ("hati", 4, "burst_hati", None),
    "taubat": ("tangan", 4, None, None), "ampun": ("hati", 4, "burst_hati", None), "maaf": ("hati", 3, "burst_hati", None),
    "pahala": ("bintang", 5, "confetti", "PAHALA"), "kebaikan": ("bintang", 4, "confetti", None), "keutamaan": ("bintang", 4, "confetti", None),
    "surga": ("pohon", 5, "confetti", "SURGA"), "taman": ("pohon", 3, None, None),
    "dosa": ("awan", 5, None, "DOSA"), "kotor": ("awan", 4, None, None), "najis": ("awan", 4, None, None), "hadats": ("awan", 4, None, None),
    "maksiat": ("awan", 3, None, None), "kesalahan": ("awan", 3, None, None),
    # --- hukum / penekanan (hanya mengulang kata yang diucapkan)
    "wajib": ("centang", 6, "stempel", "WAJIB"), "sunnah": ("centang", 6, "stempel", "SUNNAH"), "sunah": ("centang", 6, "stempel", "SUNNAH"),
    "sah": ("centang", 5, "stempel", "SAH"), "boleh": ("centang", 5, None, None), "benar": ("centang", 4, None, None),
    "jangan": ("silang", 6, "stempel", "JANGAN"), "batal": ("silang", 6, "stempel", "BATAL"), "haram": ("silang", 5, None, None),
    "larang": ("silang", 4, None, None), "salah": ("silang", 4, None, None),
    "penting": ("seru", 5, None, "PENTING"), "ingat": ("seru", 4, None, None), "awas": ("seru", 4, None, None),
    "kenapa": ("tanya", 4, None, None), "mengapa": ("tanya", 4, None, None), "bagaimana": ("tanya", 4, None, None), "tanya": ("tanya", 3, None, None),
    # --- waktu & alam
    "waktu": ("jam", 3, None, None), "subuh": ("matahari", 5, None, "SUBUH"), "pagi": ("matahari", 4, None, None), "siang": ("matahari", 3, None, None),
    "malam": ("bulan", 4, None, None), "ramadhan": ("bulan", 5, "confetti", "RAMADHAN"), "ramadan": ("bulan", 5, "confetti", "RAMADHAN"),
    "api": ("api", 4, None, None), "panas": ("api", 3, None, None), "dingin": ("tetes", 4, "burst_air", None),
    "sehat": ("daun", 4, None, None), "segar": ("daun", 4, None, None), "kuat": ("petir", 3, None, None), "semangat": ("petir", 4, None, None),
    "tidur": ("tidur", 4, None, None), "makan": ("piring", 3, None, None), "rezeki": ("koin", 4, None, None), "sedekah": ("koin", 4, None, None),
    "zakat": ("koin", 4, None, None), "rumah": ("rumah", 3, None, None), "adil": ("timbangan", 4, None, None),
    "senang": ("senyum", 4, "confetti", None), "bahagia": ("senyum", 5, "confetti", None), "gembira": ("senyum", 4, "confetti", None),
    "syukur": ("senyum", 5, "confetti", None), "alhamdulillah": ("senyum", 6, "confetti", "ALHAMDULILLAH"),
    "subhanallah": ("bintang", 6, "confetti", "SUBHANALLAH"), "masyaallah": ("bintang", 6, "confetti", "MASYAALLAH"),
    "sedih": ("sedih", 4, None, None), "menangis": ("sedih", 4, None, None),
}
NUM = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
       "pertama": 1, "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5}
STOP = {"yang", "itu", "ini", "dan", "atau", "dengan", "untuk", "dari", "pada", "kita", "kamu", "saya", "adalah", "akan", "juga"}

_PRE = ("meng", "meny", "mem", "men", "me", "peng", "peny", "pem", "pen", "per", "ber", "ter", "di", "ke", "se")
_SUF = ("kanlah", "kan", "lah", "kah", "nya", "an", "i")


def _norm(w):
    return re.sub(r"[^a-z0-9'’\-]", "", (w or "").lower().replace("’", "'")).strip("-")


def _cands(w):
    out = [w]
    for suf in _SUF:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            out.append(w[:-len(suf)])
    base = list(out)
    for b in base:
        for pre in _PRE:
            if b.startswith(pre) and len(b) - len(pre) >= 3:
                out.append(b[len(pre):])
                if pre in ("meny", "peny"):
                    out.append("s" + b[len(pre):])
                if pre in ("mem", "pem"):
                    out.append("p" + b[len(pre):])
                if pre in ("men", "pen"):
                    out.append("t" + b[len(pre):])
                if pre in ("meng", "peng"):
                    out.append("k" + b[len(pre):])
    return out


def match(word):
    """-> (kunci, ikon, prioritas, efek, label) atau None."""
    w = _norm(word)
    if not w or w in STOP:
        return None
    if w.isdigit() and 1 <= int(w) <= 20:
        return (w, "angka", 3, None, w)
    for c in _cands(w):
        if c in NUM:
            return (c, "angka", 3, None, str(NUM[c]))
        if c in LEX:
            ic, pr, fx, lab = LEX[c]
            return (c, ic, pr, fx, lab or w.upper())
    return None


NEG = {"tidak", "tak", "bukan", "belum", "tanpa", "nggak", "gak", "enggak", "tiada"}


def negated(words, i):
    """True bila kata ke-i didahului penyangkal (mis. 'tidak membatalkan') -> jangan dicap/diwarnai sebagai hukumnya."""
    for j in (i - 1, i - 2):
        if j >= 0:
            w = _norm(words[j][2])
            if w in NEG:
                return True
            if w not in {"otomatis", "langsung", "akan", "sampai", "harus", "perlu", "pernah", "terlalu", "begitu"}:
                return False
    return False


IDIOM = {("salah", "satu"), ("salah", "seorang"), ("benar", "benar"), ("tidak", "salah"), ("air", "mata"), ("mata", "air")}


def idiom(words, i):
    """'salah satu', 'benar-benar' ... bukan kata hukum."""
    w = _norm(words[i][2])
    nxt = _norm(words[i + 1][2]) if i + 1 < len(words) else ""
    prv = _norm(words[i - 1][2]) if i > 0 else ""
    return (w, nxt) in IDIOM or (prv, w) in IDIOM and w in ("salah",)


def spoken_text(sc):
    parts = [sc.get("narasi") or ""]
    if sc.get("tipe") in ("quran", "hadits"):
        parts.append(sc.get("tampil") or sc.get("kutipan") or "")
    parts.append(sc.get("penjelasan") or "")
    return " ".join(p for p in parts if p)


def ask_flags(sc, words):
    """True untuk kata TTS yang berada di dalam kalimat tanya ('... langsung batal?') -> jangan dicap/diwarnai sebagai jawaban."""
    toks = []
    for m in re.finditer(r"[^.!?]+[.!?]?", spoken_text(sc)):
        q = m.group(0).strip().endswith("?")
        toks += [(_norm(w), q) for w in re.findall(r"[\w\-'’]+", m.group(0))]
    out, j = [], 0
    for _t, _d, w in words:
        n = _norm(w)
        hit = next((k for k in range(j, min(len(toks), j + 5)) if toks[k][0] == n), None)
        if hit is not None:
            j = hit + 1
            out.append(toks[hit][1])
        else:
            out.append(toks[j][1] if j < len(toks) else False)
    return out


def keywords(words):
    """words = [(mulai, durasi, teks)] -> daftar dict kata bermakna (kata yang disangkal dilewati)."""
    out = []
    for i, (t, d, txt) in enumerate(words):
        m = match(txt)
        if m and (negated(words, i) or idiom(words, i)):
            continue
        if m:
            out.append({"i": i, "t": t, "d": d, "text": txt, "key": m[0], "icon": m[1], "pri": m[2], "fx": m[3], "label": m[4]})
    return out


def is_keyword_flags(words):
    return [match(txt) is not None and not negated(words, i) and not idiom(words, i) for i, (_t, _d, txt) in enumerate(words)]


# ---------------------------------------------------------------- aktor
_CACHE = {}


def _badge(icon, P, R, digit=None):
    key = ("b", icon, P["ink"], P["accent"], P["card"], R, digit)
    if key in _CACHE:
        return _CACHE[key]
    d = D.Drawing()
    d.circle(R, R, R - 5, P["ink"], P["card"], 6)
    d.circle(R, R, R - 16, P["accent2"], None, 3)
    if icon != "angka":
        isz = int(R * 1.15)
        d.add(D.icon(icon, isz, P), R - isz / 2, R - isz / 2 - 2, 1.0)
    _CACHE[key] = d
    return d


def _label(txt, P):
    key = ("l", txt, P["accent"], P["ink"])
    if key not in _CACHE:
        blk = D.text_block(txt, "hand", 44, (255, 255, 255), 900)
        h, w = blk[0].shape[:2]
        d = D.Drawing()
        d.rrect(-w / 2 - 20, 0, w / 2 + 20, h + 4, (h + 4) / 2, P["ink"], P["accent"], 4)
        _CACHE[key] = (blk[0], d, h)
    return _CACHE[key]


def _digit(txt, P):
    key = ("d", txt, P["accent"])
    if key not in _CACHE:
        _CACHE[key] = D.text_block(txt, "hand", 120, P["accent"], 400)[0]
    return _CACHE[key]


class StickerA:
    def __init__(self, x, y, icon, label, t0, t1, P, R=100, digit=None):
        self.x, self.y, self.icon, self.label, self.t0, self.t1, self.P, self.R, self.digit = x, y, icon, label, t0, t1, P, R, digit

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1:
            return None
        fk = ctx.get("fxk", 1.0)
        a = t - self.t0
        k = D.ease_back(min(1.0, a / 0.3))
        if self.t1 - t < 0.25:
            k *= max(0.0, (self.t1 - t) / 0.25)
        if k <= 0.02:
            return None
        wob = 1.0 + (0.035 * math.sin(a * 9.0) * math.exp(-a * 1.2) if fk > 0 else 0.0)
        bob = 7 * math.sin(a * 3.0) * min(1.0, a / 0.5) * (1 if fk > 0 else 0)
        R, P = self.R, self.P
        s = k * wob
        cx, cy = self.x, self.y + bob
        _badge(self.icon, P, R, self.digit).render(img, cx - R * s, cy - R * s, s, 1.0, int(a * 8), 1.1 if ctx["boil"] else 0)
        if self.digit:
            blk = _digit(self.digit, P)
            D.blit(img, blk, cx, cy, scale=s * (R / 100.0), anchor="c")
        if self.label and self.icon != "angka":
            blk, pill, h = _label(self.label, P)
            ly = cy + R * s + 6
            pill.render(img, cx, ly, s, 1.0, 0, 0)
            D.blit(img, blk, cx, ly + 2 * s + h * s / 2, scale=s, anchor="c")
        return None


class StampA:
    """Kata besar menghentak di tengah layar (mengulang kata yang diucapkan)."""

    def __init__(self, text, t0, t1, P, y=760):
        self.t0, self.t1, self.P, self.y = t0, t1, P, y
        self.blk = D.fit_text(text, "hand", 170, P["red"], 900, 240, min_size=90, stroke=5, stroke_color=P["ink"])

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1:
            return None
        a = t - self.t0
        k = 1.0 + 0.6 * math.exp(-a * 9.0) if a < 0.5 else 1.0                    # slam 1.6 -> 1.0
        if self.t1 - t < 0.2:
            k *= max(0.0, (self.t1 - t) / 0.2)
        al = min(1.0, a / 0.06) * (min(1.0, (self.t1 - t) / 0.2))
        D.blit(img, self.blk[0], W / 2, self.y, scale=k, alpha=max(0.0, al), anchor="c")
        return None


class GlowA:
    """Sinar emas berdenyut di belakang (untuk 'Allah')."""

    def __init__(self, t0, t1, color, y=900):
        self.t0, self.t1, self.color, self.y = t0, t1, color, y

    def draw(self, img, t, ctx):
        if ctx.get("fxk", 1.0) <= 0 or t < self.t0 or t > self.t1:
            return None
        e = min(1.0, (t - self.t0) / 0.3) * min(1.0, (self.t1 - t) / 0.4)
        FX.sunburst(img, W / 2, self.y, t * 1.3, self.color, 0.28 * max(0.0, e), 14)
        return None


# ---------------------------------------------------------------- penjadwal
ZONES = {   # posisi stiker per jenis adegan (menghindari tokoh, teks, dan ikon bawaan adegan)
    "tanya": [(150, 1000), (930, 1000)], "bicara": [(150, 780), (930, 780)], "quran": [(560, 1210)], "hadits": [(560, 1210)],
    "poin": [(250, 1215), (560, 1215)], "langkah": [(230, 1235), (520, 1235)], "fakta": [(150, 960), (930, 960)],
    "penutup": [(150, 1200), (930, 1200)],
}
RADIUS = {"quran": 80, "hadits": 80, "poin": 80, "langkah": 72, "bicara": 92}


PERSON_ICONS = {"istri", "suami", "anak", "anak_p", "bayi", "ibu", "ayah", "kakek", "nenek", "teman", "keluarga"}
STAGE_ZONES = [(150, 792), (385, 792), (620, 792)]      # di atas kepala tokoh pada panggung gambar (aw_cerita)
EMO_ICONS = {"sedih", "senyum"}                         # ekspresi sudah diperankan tokoh di panggung


def plan_scene(sc, seg, P, state, st, stage=False):
    """-> (aktor, sfx[(t, nama, vol)], pulses[(t, amp, shake)]) memakai waktu relatif awal adegan.
    state = {'last_icon': {ikon: waktu_global}, 'last_t': waktu_global, 'n': jumlah} dipakai lintas adegan."""
    words = seg.get("words") or []
    if not words or not st.get("kata_gambar", True):
        return [], [], []
    tp = sc.get("tipe", "bicara")
    zones = ZONES.get(tp, ZONES["bicara"])
    R = RADIUS.get(tp, 100)
    cand = keywords(words)
    ask = ask_flags(sc, words)
    cand = [c for c in cand if not (ask[c["i"]] and c["fx"] == "stempel")]     # kalimat tanya: belum ada jawaban -> tanpa stempel
    import aw_layout as LY
    if LY.pojok():                                                             # tata letak pojok: jauhi panggung cerita, kata hologram & subtitle
        zones, R = ((115, 700), (965, 700)), 58
        if not stage and tp not in ("fakta",):
            zones, R = ((110, 1040), (970, 1040)), 55
        if stage:                                                              # benda sudah tampil di balon tokoh -> hanya stempel
            cand = [c for c in cand if c["fx"] == "stempel"]
    elif stage:                                                                # tokoh digambar di panggung -> stiker hanya untuk benda
        zones, R = STAGE_ZONES, 68
        cand = [c for c in cand if c["icon"] not in PERSON_ICONS and c["icon"] not in EMO_ICONS]
    chosen = []
    for c in sorted(cand, key=lambda c: (-c["pri"], c["t"])):                  # prioritas dulu, lalu urutan
        g = seg["start"] + c["t"]
        if state["last_icon"].get(c["icon"], -99) > g - 7.0:                  # cooldown ikon yang sama
            continue
        if any(abs(o["t"] - c["t"]) < 1.25 for o in chosen):                  # jarak antar stiker
            continue
        if len(chosen) >= (3 if stage else 4):
            break
        chosen.append(c)
        state["last_icon"][c["icon"]] = g
    chosen.sort(key=lambda c: c["t"])
    A, S, pulses = [], [], []
    HL = None
    if st.get("holo", "semua") not in ("off", False, None):                   # mode hologram (aw_holo)
        import aw_holo as HL
        base = HL.theme_for(state.get("scene", 0), tp)
    for n, c in enumerate(chosen):
        t0 = max(0.0, c["t"] - 0.04)
        dur = max(1.55, c["d"] + 1.15)
        x, y = zones[(state["n"] + n) % len(zones)]
        digit = c["label"] if c["icon"] == "angka" else None
        if c["key"] in ("allah", "tuhan", "ta'ala"):                      # lafaz Allah: hanya cahaya lembut, tanpa gambar/simbol
            A.insert(0, GlowA(t0, t0 + dur, P["accent2"]))
            continue
        if c["fx"] == "stempel":
            if HL:
                A.append(HL.StampHoloA(c["label"], t0, t0 + 1.15, HL.semantic((c["key"], c["icon"]), base), seed=state["n"] + n))
                S.append((t0, "holo_glitch", 0.55))
            else:
                A.append(StampA(c["label"], t0, t0 + 1.1, P))
            S.append((t0, "stamp", 0.7))
            pulses.append((t0, 0.05, 9))
            # stempel dipasang tanpa stiker agar layar tidak penuh
            continue
        if HL:
            A.append(HL.IconHoloA(x, y, c["icon"], c["label"], t0, t0 + dur, P, R * 0.92,
                                  HL.semantic((c["key"], c["icon"]), base), digit, seed=state["n"] + n))
            S.append((t0, "holo_on", 0.55))
        else:
            A.append(StickerA(x, y, c["icon"], c["label"], t0, t0 + dur, P, R, digit))
            S.append((t0, "pop2" if c["pri"] >= 5 else "pop", 0.75))
        fx = c["fx"]
        if fx == "burst_air":
            A.append(FX.BurstA(x, y, t0 + 0.15, "drops", 14, P, 1.0, 0.7))
        elif fx == "burst_hati":
            A.append(FX.BurstA(x, y, t0 + 0.15, "hearts", 10, P, 1.2, 0.7))
        elif fx == "confetti":
            A.append(FX.BurstA(x, y, t0 + 0.15, "confetti", 22, P, 1.3, 1.0))
            S.append((t0 + 0.1, "sparkle", 0.6))
        elif fx == "cahaya":
            A.insert(0, GlowA(t0, t0 + dur, P["accent2"]))
            A.append(FX.BurstA(x, y, t0 + 0.15, "stars", 14, P, 1.2, 0.9))
            S.append((t0 + 0.1, "sparkle", 0.7))
        else:
            A.append(FX.BurstA(x, y, t0 + 0.15, "stars", 8, P, 0.8, 0.5))
        pulses.append((t0, 0.025, 0))
    state["n"] += len(chosen)
    return A, S, pulses
