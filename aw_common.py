"""Konfigurasi, path, gaya tampilan, dan state bersama engine Air Wudhu (animasi doodle edukasi Islam)."""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
FONT_DIR = os.path.join(ASSETS, "fonts")
SFX_DIR = os.path.join(ASSETS, "sfx")
BGM_DIR = os.path.join(ASSETS, "bgm")
CACHE_DIR = os.path.join(BASE, "cache")
PROJECTS_DIR = os.path.join(BASE, "projects")
CONFIG_FILE = os.path.join(BASE, "config.json")

# modul yang dipakai ulang dari proyek saudara (facebook_uploader)
SIBLING = os.environ.get("SIBLING_DIR") or os.path.join(os.path.dirname(BASE), "criminal_reel_youtube")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"))
except ImportError:
    pass

# Tampilan video (tab Tampilan di UI). Disimpan di config.json -> "style".
STYLE_DEFAULTS = {
    "theme": "kertas",            # kertas | papan | malam
    "accent": "#1F7A6C",          # hijau
    "accent2": "#E0A100",         # emas
    "shirt": "#3E8ED0",           # baju koko tokoh
    "peci": "#2B2B2B",
    "skin": "#F2C9A0",
    "pants": "#4A4F5A",
    "beard": True,
    "boil": True,                 # garis "bergetar" khas animasi gambar tangan
    "pen": True,                  # pena ikut menggambar
    "header": True,
    "subtitles": True,
    "sub_size": 52,
    "watermark": True,
    "sfx": True,
    "sfx_volume": 0.35,
    "bgm": False,                 # musik latar (taruh mp3 di assets/bgm). Banyak penonton dakwah lebih suka tanpa musik.
    "bgm_volume": 0.08,
    "transition": "variasi",      # variasi | geser | lingkar | tinta | hapus | tidak
    "fx": "sedang",               # efek visual: off | halus | sedang | maksimal (gelembung, kamera zoom, ledakan, progres)
    "figur": "asli",              # figur ustad dari assets/figur-ustad.jpeg: asli | kartun | doodle | tokoh (tokoh gambar bawaan)
    "ilustrasi": True,            # tokoh cerita (istri, suami, anak, ...) digambar di panggung saat kata perannya diucapkan
    "kata_gambar": True,          # tiap kata bermakna memicu gambar/efek (stiker, stempel, ledakan)
    "dunia": True,                # latar sinematik + panggung hidup (hewan, figuran, cuaca, efek emosi) -- aw_dunia.py
    "sub_karaoke": True,          # kata yang sedang diucapkan disorot di subtitle
    "holo": "semua",              # hologram per kata (aw_holo): semua | penting | off
    "tata": "pojok",              # tata letak: pojok (cerita stickman besar, subtitle tengah, ustad pojok kanan) | tengah (lama)
    "cerita_stik": True,          # panggung cerita stickman saat ustad menjelaskan (aw_stik)
}

THEMES = {
    "kertas": {"paper": "#FBF6EA", "paper2": "#F1E9D6", "ink": "#23201C", "mute": "#7A7266", "sub_bg": "#FFFDF6"},
    "papan": {"paper": "#24463B", "paper2": "#2E5649", "ink": "#F4F1E6", "mute": "#A9C4B8", "sub_bg": "#1B362D"},
    "malam": {"paper": "#1E2433", "paper2": "#283046", "ink": "#F5F0E1", "mute": "#9AA3B8", "sub_bg": "#161B27"},
}


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    work = cfg.get("work_dir") or os.path.join(os.path.dirname(BASE), "_scratch", "airwudhu_work")
    os.makedirs(work, exist_ok=True)
    tempfile.tempdir = work
    cfg["style"] = style_of(cfg)
    return cfg


def save_config(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


def style_of(cfg):
    st = dict(STYLE_DEFAULTS)
    st.update({k: v for k, v in (cfg.get("style") or {}).items() if k in STYLE_DEFAULTS})
    if st["theme"] not in THEMES:
        st["theme"] = "kertas"
    return st


# ---------------------------------------------------------------- proyek
def slug(text, n=40):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:n].strip("-") or "topik"


def project_dir(pid):
    return os.path.join(PROJECTS_DIR, os.path.basename(pid))


def load_project(pid):
    with open(os.path.join(project_dir(pid), "project.json"), encoding="utf-8") as f:
        return json.load(f)


def save_project(p):
    d = project_dir(p["id"])
    os.makedirs(d, exist_ok=True)
    p["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = os.path.join(d, "project.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(d, "project.json"))
    return p


def new_project(topik, sudut=""):
    pid = time.strftime("%Y%m%d_%H%M%S") + "_" + slug(topik, 30)
    p = {"id": pid, "topik": topik.strip(), "sudut": (sudut or "").strip(), "created": time.strftime("%Y-%m-%d %H:%M:%S"),
         "status": "baru", "sources": [], "script": None, "approved": False, "videos": []}
    return save_project(p)


def list_projects():
    out = []
    for f in glob.glob(os.path.join(PROJECTS_DIR, "*", "project.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            pass
    return sorted(out, key=lambda p: p.get("created", ""), reverse=True)


# ---------------------------------------------------------------- ffmpeg
def ensure_ffmpeg():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    local = os.environ.get("LOCALAPPDATA", "")
    cands = [r"I:\Berita_Kini\ffmpeg-8.0.1-full_build\bin", os.path.join(local, "Microsoft", "WinGet", "Links"),
             *glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin")),
             r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]
    for c in cands:
        if os.path.exists(os.path.join(c, "ffmpeg.exe")):
            os.environ["PATH"] = c + os.pathsep + os.environ.get("PATH", "")
            return
    print("❌ ffmpeg tidak ditemukan. Instal: winget install Gyan.FFmpeg")


ensure_ffmpeg()


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"Perintah gagal: {' '.join(cmd[:4])} ...\n{r.stderr[-1500:]}")
    return r.stdout


def probe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path])
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


def next_index(out_dir):
    nums = [int(m.group(1)) for f in glob.glob(os.path.join(out_dir, "auto_video_*_final.mp4"))
            if (m := re.search(r"auto_video_(\d+)_final", os.path.basename(f)))]
    return max(nums, default=0) + 1


def fb_module():
    if SIBLING not in sys.path:
        sys.path.insert(0, SIBLING)
    import facebook_uploader
    return facebook_uploader
