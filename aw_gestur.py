"""
Gerak tangan Gus Idrus mengikuti kata yang diucapkan (2026-11-22).

Lengan bawah + telapak kanan (sisi kiri layar) DIPOTONG DARI GAMBAR ASLI lalu diputar di siku dan di pergelangan
(aw_figur.Figure: rgb_na = badan tanpa lengan bawah). Jari & gaya gambar tetap persis aslinya.

plan(words, narasi) -> jadwal [(t0, t1, pose)] dari waktu kata TTS.  pose_at(jadwal, t) -> parameter pose atau None.
Matikan: style["gestur"] = false.
"""
import math
import re

import cv2
import numpy as np

INK = (40, 30, 26)
ROBE = (246, 246, 248)
FOLD = (206, 208, 220)

# Pose = putaran bagian GAMBAR ASLI (lengan bawah + tangan) -> bentuk jari & gaya gambar tetap sama dengan aslinya.
# th = putar lengan bawah di siku (derajat, + = berlawanan jarum jam / naik), ph = putar telapak di pergelangan,
# wav = (amplitudo, Hz) goyang telapak, sw = (amplitudo, Hz) ayun lengan. Arah jari asli ~ -35 derajat (kanan atas).
POSES = {
    "dada":   dict(th=0, ph=0, wav=(0, 0), sw=(0, 0)),         # gambar asli: tangan di dada
    "jelas":  dict(th=24, ph=6, wav=(5, 0.9), sw=(0, 0)),      # tangan terangkat sedikit, menjelaskan
    "angkat": dict(th=50, ph=6, wav=(0, 0), sw=(0, 0)),        # angkat tangan setinggi bahu (takbir)
    "atas":   dict(th=60, ph=0, wav=(0, 0), sw=(3, 1.4)),      # tangan menjulang ke atas (Allah, langit)
    "ingat":  dict(th=40, ph=14, wav=(9, 2.0), sw=(0, 0)),     # tangan diayun memberi penekanan
    "tolak":  dict(th=44, ph=10, wav=(15, 2.6), sw=(0, 0)),    # telapak digoyang: tidak / bukan
    "tanya":  dict(th=12, ph=-26, wav=(0, 0), sw=(4, 1.3)),    # telapak membuka ke samping: bertanya
    "tunjuk": dict(th=78, ph=38, wav=(0, 0), sw=(0, 0)),       # tangan mengarah ke cerita (kiri atas), sopan
    "kitab":  dict(th=-12, ph=-14, wav=(0, 0), sw=(0, 0)),     # tangan mengarah ke Al-Qur'an yang dipegang
    "semua":  dict(th=36, ph=12, wav=(0, 0), sw=(20, 0.6)),    # sapuan lebar: semua / para ulama
}
POSES.update(satu=POSES["ingat"], dua=POSES["ingat"], tiga=POSES["ingat"], jempol=POSES["jelas"])

# kata (awalan, huruf kecil tanpa tanda baca) -> pose. Urutan penting: frasa lebih spesifik di atas.
KATA = [
    (("angkat", "mengangkat", "diangkat", "takbir", "takbiratul", "telinga", "bahu", "berdoa", "doa"), "angkat"),
    (("allah", "rabb", "tuhan", "langit", "surga", "akhirat", "ridha", "rida"), "atas"),
    (("ingat", "ingatlah", "perhatikan", "penting", "hati-hati", "waspada", "pahami", "wajib", "sunnah", "sunah", "rukun",
      "syarat", "hukum", "hukumnya", "intinya", "kesimpulannya"), "ingat"),
    (("satu", "pertama", "sebuah"), "satu"),
    (("dua", "kedua"), "dua"),
    (("tiga", "ketiga"), "tiga"),
    (("tidak", "tak", "bukan", "jangan", "haram", "batal", "tanpa", "dilarang", "makruh", "belum"), "tolak"),
    (("apakah", "bagaimana", "kenapa", "mengapa", "apa", "benarkah", "bolehkah", "siapa", "kapan"), "tanya"),
    (("boleh", "sah", "dibolehkan", "mubah", "cukup", "bagus", "sempurna"), "jempol"),
    (("hadits", "hadis", "dalil", "kitab", "quran", "al-quran", "alquran", "ayat", "riwayat", "diriwayatkan", "fikih", "fiqih",
      "sabda", "bersabda", "menukil", "dinukil", "disebutkan", "tertulis"), "kitab"),
    (("berbeda", "beda", "sedangkan", "namun", "tetapi", "tapi", "sebaliknya", "padahal"), "tanya"),
    (("ucap", "ucapan", "mengucapkan", "diucapkan", "lafal", "melafalkan", "dilafalkan", "lafadz", "lafaz", "bacaan", "membaca",
      "dibaca", "usholli", "lisan", "berkata", "mengatakan", "menjelaskan", "dijelaskan", "ternyata"), "jelas"),
    (("semua", "seluruh", "banyak", "para", "ulama", "jumhur", "mayoritas", "mazhab", "madzhab", "kebanyakan"), "semua"),
    (("lihat", "seperti", "contoh", "misalnya", "ini", "itu", "dia", "mereka", "beliau", "orang", "jamaah", "jemaah",
      "pak", "bu", "mas", "mbak", "anak", "temannya"), "tunjuk"),
    (("hati", "niat", "berniat", "ikhlas", "iman", "jiwa", "batin", "sabar", "tenang"), "dada"),
]
_STRONG = ("tolak", "angkat", "atas", "satu", "dua", "tiga")
_NEG = ("tidak", "tak", "bukan", "belum", "jangan")
_IDLE = ("jelas", "dada", "jelas", "dada")        # isian saat lama tanpa kata kunci (tidak monoton)


def _norm(w):
    return re.sub(r"[^a-z0-9\-]", "", (w or "").lower())


def _pose_of(w):
    for keys, pose in KATA:
        for k in keys:
            if w == k or (len(k) >= 5 and w.startswith(k)):
                return pose
    return None


def plan(words, narasi="", seed=0):
    """Jadwal pose dari waktu kata [(start, dur, teks)]. Tiap pose ditahan >= 0.9 dtk; jeda panjang diisi gerak menjelaskan."""
    sched = []
    last_t = -9.0
    prev = ""
    q_sentence = "?" in (narasi or "")
    for j, (t, d, txt) in enumerate(words or []):
        w = _norm(txt)
        pose = _pose_of(w)
        if pose in ("jempol",) and prev in _NEG:                           # 'tidak sah' -> tetap menolak
            pose = None
        if pose == "tanya" and not q_sentence and w == "apa":
            pose = None
        if pose == "tunjuk" and w in ("ini", "itu") and sched and t - sched[-1][0] < 2.4:
            pose = None                                                     # 'ini/itu' terlalu sering -> jangan tiap kali
        prev = w
        if not pose:
            continue
        t0 = max(0.0, t - 0.18)                                             # antisipasi: tangan bergerak sebelum kata
        if sched and t0 - sched[-1][0] < 0.85:                              # terlalu rapat -> pose sebelumnya menang,
            if pose in _STRONG and sched[-1][2] not in _STRONG and t0 - sched[-1][0] > 0.3:
                sched[-1][1] = t0                                           # ...kecuali kata kuat (tidak/angkat/Allah)
            else:
                continue
        sched.append([t0, t + max(0.9, d + 0.6), pose])
        last_t = t
    # isi jeda panjang dengan gerak menjelaskan bergantian
    if words:
        end = words[-1][0] + words[-1][1]
        fill, cur, k = [], words[0][0], seed
        for s in sched + [[end, end, None]]:
            while s[0] - cur > 2.6 and cur + 1.6 < end:
                fill.append([cur + 0.4, min(cur + 1.9, s[0] - 0.3), _IDLE[k % len(_IDLE)]])
                cur += 2.3
                k += 1
            cur = max(cur, s[1])
        sched = sorted(sched + fill)
    for a, b in zip(sched, sched[1:]):                                      # jangan tumpang tindih
        a[1] = min(a[1], b[0])
    return [tuple(s) for s in sched]


def _lerp(a, b, k):
    return a + (b - a) * k


def _mix(p, q, k):
    return {key: (_lerp(p[key][0], q[key][0], k), _lerp(p[key][1], q[key][1], k)) if isinstance(p[key], tuple)
            else _lerp(p[key], q[key], k) for key in p}


def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


TR = 0.32          # lama perpindahan pose (dtk)


def pose_at(sched, t):
    """Return (prm, b): prm = parameter pose (dict) dan b = bobot 0..1 terhadap gambar asli (0 = tangan di dada asli)."""
    if not sched:
        return None, 0.0
    cur, prev_name, start = "dada", "dada", -9.0
    for (a, b_, name) in sched:
        if t >= a:
            if t < b_:
                prev_name, cur, start = cur, name, a
            else:
                prev_name, cur, start = name, "dada", b_
        else:
            break
    k = _ease((t - start) / TR)
    p = _mix(POSES[prev_name], POSES[cur], k)
    # bobot gambar asli: 0 bila pose = dada & perpindahan selesai
    if cur == "dada" and prev_name == "dada":
        return None, 0.0
    if cur == "dada":
        bw = 1.0 - _ease((k - 0.75) / 0.25)
    elif prev_name == "dada":
        bw = _ease(k / 0.25)
    else:
        bw = 1.0
    ramp = min(1.0, max(0.0, (t - start) / 0.4))
    a, hz = p["wav"]
    if a:
        p["ph"] += a * math.sin(t * 2 * math.pi * hz) * ramp
    a, hz = p["sw"]
    if a:
        p["th"] += a * math.sin(t * 2 * math.pi * hz) * ramp
    return p, bw
