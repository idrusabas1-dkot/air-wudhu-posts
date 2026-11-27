"""LLM lokal (Ollama) + suara narasi (edge-tts). Mandiri, tanpa bergantung proyek lain."""
import asyncio
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class AIUnavailable(RuntimeError):
    pass


def _ollama_up():
    try:
        urllib.request.urlopen(OLLAMA_URL, timeout=2)
        return True
    except Exception:
        return False


def ensure_ollama():
    if _ollama_up():
        return True
    cand = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama")
    if os.path.isdir(cand):
        os.environ["PATH"] = cand + os.pathsep + os.environ.get("PATH", "")
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return False
    for _ in range(20):
        time.sleep(1)
        if _ollama_up():
            return True
    return False


def unload(model):
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/generate", data=json.dumps({"model": model, "keep_alive": 0}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


def chat(prompt, system=None, model="gemma2:9b", json_mode=False, temperature=0.4, max_tokens=1800,
         num_ctx=8192, timeout=900):
    if not ensure_ollama():
        raise AIUnavailable("Ollama tidak berjalan")
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": msgs, "stream": False, "keep_alive": "5m",
               "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": max_tokens}}
    if json_mode:
        payload["format"] = "json"
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = json.loads(e.read().decode("utf-8", "replace")).get("error", "")
            except Exception:
                pass
            if e.code == 404:
                raise AIUnavailable(f"model {model} belum ada (ollama pull {model})")
            if "memory" in body:
                raise MemoryError(body)
            if attempt == 2:
                raise
            print(f"   ⚠️ Ollama HTTP {e.code} -> bongkar model & ulangi")
            unload(model)
            time.sleep(8)


def installed_models():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []


def chat_auto(prompt, models, log=print, **kw):
    """Coba model berurutan; pindah ke model lebih kecil kalau RAM tidak cukup / model tidak ada. Return (teks, model)."""
    have = installed_models()
    tried = []
    top = int(kw.pop("num_ctx", 6144))
    ladder = sorted({top, min(top, 6144), 4096}, reverse=True)       # mis. 8192 -> 6144 -> 4096 kalau RAM tidak cukup
    for m in models:
        if have and m not in have:
            continue
        for ctx in ladder:
            try:
                return chat(prompt, model=m, num_ctx=ctx, **kw), m
            except MemoryError as e:
                tried.append(f"{m}@{ctx}: {str(e)[:80]}")
                log(f"   ⚠️ {m} (konteks {ctx}): RAM tidak cukup")
                unload(m)
    raise AIUnavailable("Tidak ada model yang muat di RAM: " + "; ".join(tried) if tried else
                        f"Model tidak terpasang: {', '.join(models)}")


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def chat_json(prompt, **kw):
    return parse_json(chat(prompt, json_mode=True, **kw))


# ---------------------------------------------------------------- suara
# Lafaz "Allah": TULISAN tetap "Allah" (layar, subtitle, caption), hanya UCAPAN yang diganti ejaan fonetik
# supaya suara TTS Indonesia mengucap "Awloh" (bukan "Alah"). Bisa diubah lewat config.json: "allah_ucap".
ALLAH_UCAP = "Awloh"
_LLAH_UCAP = "lloh"                       # akhiran majemuk: Subhanallah -> Subhanalloh, Rasulullah -> Rasululloh


def set_allah_ucap(v):
    global ALLAH_UCAP
    if v and str(v).strip():
        ALLAH_UCAP = str(v).strip()


def _lafaz(t):
    """Ganti ejaan Allah -> fonetik untuk TTS saja."""
    def solo(m):
        suf = (m.group(1) or "").lower()
        return ALLAH_UCAP + suf
    t = re.sub(r"(?<![A-Za-z])all[aâ]h(u|umma|i)?(?![A-Za-z])", solo, t, flags=re.I)
    t = re.sub(r"(?i)(?<=\w)ll[aâ]h", _LLAH_UCAP, t)                      # majemuk: ...llah -> ...lloh
    return t


def _tulisan(w):
    """Kebalikannya: kata hasil TTS (waktu per kata) dikembalikan ke tulisan 'Allah' agar subtitle/gambar benar."""
    if not w:
        return w
    w = re.sub(re.escape(ALLAH_UCAP), "Allah", w, flags=re.I)
    return re.sub(r"(?i)(?<=\w)" + _LLAH_UCAP, "llah", w)


def _natural(text):
    t = re.sub(r"[*_#]", "", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace("ﷺ", "shallallahu 'alaihi wa sallam").replace("SAW", "shallallahu 'alaihi wa sallam")
    t = re.sub(r"\bSWT\b", "subhanahu wa ta'ala", t)
    t = re.sub(r"\bQS\.?\s*", "Surat ", t)
    t = re.sub(r"\bHR\.?\s*", "Hadits riwayat ", t)
    t = _lafaz(t)
    if t and t[-1] not in ".!?":
        t += "."
    return t


WORDS = {}          # out_path -> [(mulai_dtk, durasi_dtk, kata)] dari edge-tts (waktu per kata)


def tts(text, out_path, voice="id-ID-ArdiNeural", rate="+4%", pitch="+0Hz"):
    import edge_tts

    async def go():
        com = edge_tts.Communicate(_natural(text), voice, rate=rate, pitch=pitch, boundary="WordBoundary")
        words = []
        with open(out_path, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    words.append((ch["offset"] / 1e7, ch["duration"] / 1e7, _tulisan(ch["text"])))
        WORDS[out_path] = words

    last = None
    for _ in range(3):
        try:
            asyncio.run(go())
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                return out_path
        except Exception as e:      # jaringan putus sesaat
            last = e
            time.sleep(2)
    raise AIUnavailable(f"edge-tts gagal (butuh internet): {last}")


def tts_raw(text, out_path, voice, rate, pitch):
    return tts(text, out_path, voice, rate, pitch)
