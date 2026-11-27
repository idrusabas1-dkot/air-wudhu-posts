"""Suara ustad yang lebih natural: narasi dipecah per klausa dengan nada/kecepatan yang bervariasi + jeda napas,
ayat dibacakan dengan suara Arab (tartil), terjemah/hadits dibacakan pelan. Semua tetap edge-tts (gratis)."""
import os, re, zlib
import numpy as np

import aw_ai as ai

SR = 24000          # sama dengan aw_render.SR (dibaca ulang saat dipakai)
ARAB_VOICE = "ar-SA-HamedNeural"


def _clauses(text):
    """Pecah teks jadi (klausa, tanda_baca_akhir). Klausa terlalu pendek digabung ke tetangganya."""
    text = re.sub(r"\s+", " ", text or "").strip()
    raw = re.findall(r"[^.!?,;:]+[.!?,;:]?", text)
    out = []
    for r in raw:
        r = r.strip()
        if not r:
            continue
        p = r[-1] if r[-1] in ".!?,;:" else "."
        body = r.rstrip(".!?,;:").strip()
        if not body:
            continue
        if out and len(body.split()) < 3 and out[-1][1] in ",;:":
            out[-1] = (out[-1][0] + ", " + body, p)
        else:
            out.append((body, p))
    return out


def _trim(a, thr=0.012, keep=0.03):
    if len(a) == 0:
        return a, 0
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a, 0
    s = max(0, idx[0] - int(keep * SR))
    e = min(len(a), idx[-1] + int(keep * SR))
    return a[s:e], s


def _wav(mp3, R):
    return R._read_wav_mono(R._to_wav(mp3, mp3[:-4] + ".wav"))


def _prosody(body, punct, i, n, base_rate, base_pitch):
    """Variasi halus per klausa supaya tidak datar: tanya naik, akhir kalimat turun & melambat, tiap klausa sedikit beda."""
    h = zlib.crc32(body.encode("utf-8")) & 0xFFFF
    rate = base_rate + (h % 5) - 2                    # -2..+2 %
    pitch = base_pitch + ((h >> 3) % 5) - 2           # -2..+2 Hz
    if punct == "?":
        pitch += 4
    elif punct == "!":
        pitch += 2
        rate += 2
    elif punct == ".":
        rate -= 3
        pitch -= 2
    elif punct in ",;:":
        pitch += 1
    if i == 0:
        rate += 1
    return f"{rate:+d}%", f"{pitch:+d}Hz"


def _narasi_ai():
    import sys
    d = os.path.join("I:" + os.sep, "AG", "narasi")
    if d not in sys.path:
        sys.path.append(d)
    import nr_ai
    return nr_ai


PAUSE = {".": 0.34, "?": 0.42, "!": 0.34, ",": 0.15, ";": 0.2, ":": 0.2}


def speak(parts, work, key, cfg, rate_pct=None):
    """parts: list (jenis, teks): 'id' (narasi), 'baca' (terjemah dibaca lebih pelan), 'ar' (ayat Arab), 'jeda' (detik).
    Mengembalikan (audio float32 mono SR, [(mulai, durasi, kata)] relatif awal audio)."""
    import aw_render as R
    global SR
    SR = R.SR
    voice = cfg.get("voice", "id-ID-ArdiNeural")
    base_rate = int(round(rate_pct if rate_pct is not None else float(str(cfg.get("voice_rate", "-2%")).replace("%", "").replace("+", ""))))
    base_pitch = int(cfg.get("voice_pitch_hz", -2))
    chunks, words, t = [], [], 0.0
    k = 0

    def add(a, off_words=None, pause=0.0):
        nonlocal t
        chunks.append(a)
        if off_words:
            for o, d, w in off_words:
                words.append((t + o, d, w))
        t += len(a) / SR
        if pause > 0:
            chunks.append(np.zeros(int(pause * SR), np.float32))
            t += pause

    for jenis, teks in parts:
        if jenis == "jeda":
            add(np.zeros(0, np.float32), pause=float(teks))
            continue
        if jenis == "ar":
            mp3 = os.path.join(work, f"{key}_{k:02d}.mp3"); k += 1
            ai.tts_raw(teks, mp3, ARAB_VOICE, "-12%", "+0Hz")
            a = _wav(mp3, R)
            a = _trim(a)[0]
            add(a, None, 0.5)
            continue
        if cfg.get("tts") == "f5":
            # suara klon F5-TTS (mesin dari engine narasi), resample 24k -> SR engine ini
            na = _narasi_ai()
            o = dict(cfg.get("f5") or {})
            o["speed"] = float(o.get("speed", 1.0)) * (0.92 if jenis == "baca" else 1.0)
            a, ws = na.ucapkan_f5(teks, "tenang", work, f"{key}_{k:02d}",
                                  {"tts": "f5", "f5": o, "jeda_kali": float(cfg.get("f5_jeda_kali", 1.0))},
                                  ucap_fn=lambda x: ai._tulisan(ai._natural(x)))  # F5 Indonesia sudah fasih "Allah"
            k += 1
            if SR != na.SR:
                a = np.interp(np.arange(0, len(a), na.SR / SR), np.arange(len(a)), a).astype(np.float32)
            add(a, ws, 0.15)
            continue
        cl = _clauses(teks)
        for i, (body, p) in enumerate(cl):
            mp3 = os.path.join(work, f"{key}_{k:02d}.mp3"); k += 1
            br = base_rate - (8 if jenis == "baca" else 0)
            rate, pitch = _prosody(body, p, i, len(cl), br, base_pitch + (-1 if jenis == "baca" else 0))
            ai.tts_raw(body + (p if p in "?!" else ""), mp3, voice, rate, pitch)
            a = _wav(mp3, R)
            a, s0 = _trim(a)
            ws = [(max(0.0, o - s0 / SR), d, w) for o, d, w in ai.WORDS.get(mp3, [])]
            last = (i == len(cl) - 1)
            add(a, ws, PAUSE.get(p, 0.2) * (1.0 if last or p != "," else 1.0))
    if not chunks:
        return np.zeros(int(0.3 * SR), np.float32), []
    aud = np.concatenate(chunks).astype(np.float32)
    # rapikan: sedikit kompresi lembut agar volume merata (tidak mengubah timing)
    pk = float(np.max(np.abs(aud))) or 1.0
    aud = np.tanh(aud / pk * 1.35) / np.tanh(1.35) * pk
    return aud, words
