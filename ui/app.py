"""
UI web Air Wudhu (desain sama dengan UI engine lain: Anime / criminal_reel_youtube).

Alur di tab Studio: Topik -> Bahan (riset web) -> Naskah (storyboard + verifikasi dalil, setujui) -> Render.
Proses berat (riset, naskah LLM, render) dijalankan sebagai subprocess aw_main.py; UI mengelola proyek,
pengaturan, tampilan (preview), hasil, upload FB, dan riwayat job.

Jalankan:  run_ui.bat  ->  http://127.0.0.1:8600
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

UI_DIR = Path(__file__).resolve().parent
BASE_DIR = UI_DIR.parent
DATA_DIR = UI_DIR / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
FB_DIR = DATA_DIR / "fb_accounts"
FB_ACTIVE_FILE = DATA_DIR / "fb_active.txt"
SIBLING_FB_DIRS = {"Criminal Reel": BASE_DIR.parent / "criminal_reel_youtube" / "ui" / "data" / "fb_accounts",
                   "One Piece": BASE_DIR.parent / "Anime" / "ui" / "data" / "fb_accounts"}
ENGINE_PYTHON = os.getenv("ENGINE_PYTHON") or sys.executable
VIDEO_RE = re.compile(r"^auto_video_(\d+)_final\.mp4$")

DATA_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE_DIR))
import aw_common as C  # noqa: E402

app = FastAPI(title="Air Wudhu Engine")
_lock = threading.Lock()
_plock = threading.Lock()
_procs: dict[str, subprocess.Popen] = {}


def _fbu():
    return C.fb_module()


# ========================= CONFIG
def _cfg() -> dict:
    return C.load_config()


@app.get("/api/config")
def config_get():
    with open(C.CONFIG_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    raw["style"] = C.style_of(raw)
    return raw


class ConfigReq(BaseModel):
    config: dict


@app.post("/api/config")
def config_save(r: ConfigReq):
    with open(C.CONFIG_FILE, encoding="utf-8") as f:
        cur = json.load(f)
    new = r.config
    for k in ("output_dir", "account_name"):
        if k in new and not str(new.get(k, "")).strip():
            raise HTTPException(400, f"{k} wajib diisi")
    for t in new.get("upload_times_wib", []):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            raise HTTPException(400, f"Jam upload tidak valid: {t} (format HH:MM)")
    if "style" in new:
        st = C.style_of({"style": new["style"]})
        new["style"] = {k: st[k] for k in C.STYLE_DEFAULTS}
    merged = {**cur, **new}
    C.save_config(merged)
    return config_get()


# ========================= JOBS
def _load_jobs() -> list:
    try:
        return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_jobs(jobs: list):
    JOBS_FILE.write_text(json.dumps(jobs[:200], ensure_ascii=False, indent=2), encoding="utf-8")


def _update_job(job_id: str, **fields):
    with _lock:
        jobs = _load_jobs()
        for j in jobs:
            if j["id"] == job_id:
                j.update(fields)
        _save_jobs(jobs)


def _refresh_status(jobs: list) -> list:
    for j in jobs:
        if j["status"] == "running" and j["id"] not in _procs and not (j.get("pid") and psutil.pid_exists(j["pid"])):
            j["status"] = "unknown"
    return jobs


def _running(kind: str | None = None, project: str | None = None) -> list:
    return [j for j in _load_jobs() if j["id"] in _procs and (kind is None or j["kind"] == kind)
            and (project is None or j.get("project") == project)]


def _spawn(kind: str, script: str, args: list[str], summary: str, project: str = "") -> dict:
    job_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]
    log_path = DATA_DIR / f"{job_id}.log"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    log_f = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen([ENGINE_PYTHON, "-u", script, *args], cwd=BASE_DIR, env=env,
                            stdin=subprocess.DEVNULL, stdout=log_f, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    job = {"id": job_id, "kind": kind, "summary": summary, "status": "running", "pid": proc.pid, "project": project,
           "started": time.strftime("%Y-%m-%d %H:%M:%S"), "finished": None, "exit_code": None}
    with _lock:
        _save_jobs([job] + _load_jobs())
    _procs[job_id] = proc

    def _wait():
        code = proc.wait()
        log_f.close()
        _update_job(job_id, status="done" if code == 0 else "failed", exit_code=code,
                    finished=time.strftime("%Y-%m-%d %H:%M:%S"))
        _procs.pop(job_id, None)

    threading.Thread(target=_wait, daemon=True).start()
    return job


def _tail(path: Path, lines: int = 300) -> str:
    try:
        data = path.read_bytes()[-80000:]
    except OSError:
        return ""
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[-lines:])


@app.get("/api/jobs")
def jobs():
    return _refresh_status(_load_jobs())


@app.get("/api/jobs/{job_id}/log")
def job_log(job_id: str):
    return {"log": _tail(DATA_DIR / f"{Path(job_id).name}.log", 400)}


@app.post("/api/jobs/{job_id}/stop")
def job_stop(job_id: str):
    proc = _procs.get(job_id)
    if not proc:
        raise HTTPException(404, "Job tidak sedang berjalan dari UI ini")
    try:
        parent = psutil.Process(proc.pid)
        for c in parent.children(recursive=True):
            c.kill()
        parent.kill()
    except psutil.Error:
        pass
    _update_job(job_id, status="stopped")
    return {"ok": True}


def _ollama_ok() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=1)
        return True
    except Exception:
        return False


@app.get("/api/status")
def status():
    run = _running()
    eng = [j for j in run if j["kind"] != "upload"]
    up = [j for j in run if j["kind"] == "upload"]
    return {"engine_running": bool(eng), "engine_job": eng[0]["id"] if eng else "",
            "engine_kind": eng[0]["kind"] if eng else "", "engine_project": eng[0].get("project", "") if eng else "",
            "upload_running": bool(up), "upload_job": up[0]["id"] if up else "",
            "fb_active": _fb_label(_fb_active()) if _fb_active() else "", "ollama": _ollama_ok()}


# ========================= PROYEK
def _proj(pid: str) -> dict:
    try:
        return C.load_project(Path(pid).name)
    except (OSError, ValueError):
        raise HTTPException(404, "Proyek tidak ada")


def _light(p: dict) -> dict:
    sc = p.get("script") or {}
    return {"id": p["id"], "topik": p["topik"], "sudut": p.get("sudut", ""), "status": p.get("status", ""),
            "created": p.get("created", ""), "updated": p.get("updated", ""), "approved": p.get("approved", False),
            "sources": len(p.get("sources", [])), "sources_used": sum(1 for s in p.get("sources", []) if s.get("use")),
            "scenes": len(sc.get("adegan", [])), "issues": sc.get("masalah", 0), "videos": len(p.get("videos", [])),
            "judul": sc.get("judul_pendek", "")}


@app.get("/api/projects")
def projects():
    return [_light(p) for p in C.list_projects()]


class NewProjReq(BaseModel):
    topik: str
    sudut: str = ""
    research: bool = True


@app.post("/api/projects")
def project_new(r: NewProjReq):
    if len(r.topik.strip()) < 5:
        raise HTTPException(400, "Tulis topik minimal 5 huruf")
    p = C.new_project(r.topik, r.sudut)
    job = None
    if r.research:
        job = _start(p["id"], "research")
    return {"project": _light(p), "job": job}


@app.get("/api/projects/{pid}")
def project_get(pid: str):
    p = _proj(pid)
    for s in p.get("sources", []):
        s["preview"] = (s.get("text") or "")[:1800]
        s.pop("text", None)
    p["running"] = [j["kind"] for j in _running(project=p["id"])]
    return p


@app.post("/api/projects/{pid}/delete")
def project_delete(pid: str):
    p = _proj(pid)
    if _running(project=p["id"]):
        raise HTTPException(400, "Proyek sedang diproses")
    shutil.rmtree(C.project_dir(p["id"]), ignore_errors=True)
    return {"ok": True}


class TopicReq(BaseModel):
    topik: str
    sudut: str = ""


@app.post("/api/projects/{pid}/topic")
def project_topic(pid: str, r: TopicReq):
    with _plock:
        p = _proj(pid)
        p["topik"], p["sudut"] = r.topik.strip() or p["topik"], r.sudut.strip()
        C.save_project(p)
    return _light(p)


def _start(pid: str, step: str, extra: list[str] | None = None) -> dict:
    if _running(project=pid):
        raise HTTPException(400, "Proyek ini sedang diproses — tunggu selesai")
    if step == "render" and _running("render"):
        raise HTTPException(400, "Render lain sedang berjalan (satu per satu agar laptop tidak berat)")
    p = _proj(pid)
    label = {"research": "Riset bahan", "script": "Tulis naskah", "render": "Render video"}[step]
    return _spawn(step, "aw_main.py", [step, "--project", pid, *(extra or [])], f"{label} · {p['topik'][:60]}", pid)


@app.post("/api/projects/{pid}/research")
def project_research(pid: str):
    return _start(pid, "research")


@app.post("/api/projects/{pid}/script")
def project_script(pid: str):
    p = _proj(pid)
    if not any(s.get("use") for s in p.get("sources", [])):
        raise HTTPException(400, "Pilih minimal satu bahan (centang) atau tambah catatan sendiri")
    import aw_research as R
    info = R.assess(p.get("sources", []), C.load_config())
    if not info["cukup"]:
        raise HTTPException(400, f"Bahan belum cukup: {'; '.join(info['kurang'])}. Klik 'Cari ulang bahan', centang bahan lain, "
                                 "atau tambah URL artikel / catatan sendiri — supaya video tidak tipis rujukannya.")
    return _start(pid, "script")


class RenderReq(BaseModel):
    date: str = ""


@app.post("/api/projects/{pid}/render")
def project_render(pid: str, r: RenderReq):
    p = _proj(pid)
    if not p.get("approved"):
        raise HTTPException(400, "Setujui naskah dulu")
    extra = ["--date", r.date] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.date or "") else []
    return _start(pid, "render", extra)


class SourcesReq(BaseModel):
    use: list[int] = []
    add_url: str = ""
    note_title: str = ""
    note_text: str = ""
    remove: int | None = None


@app.post("/api/projects/{pid}/sources")
def project_sources(pid: str, r: SourcesReq):
    import aw_research as R
    with _plock:
        p = _proj(pid)
        src = p.setdefault("sources", [])
        for i, s in enumerate(src):
            s["use"] = i in r.use
        if r.remove is not None and 0 <= r.remove < len(src):
            src.pop(r.remove)
        if r.add_url.strip():
            try:
                R.add_url(p, r.add_url.strip())
            except Exception as e:
                raise HTTPException(400, f"Halaman tidak terbaca: {str(e)[:150]}")
        if r.note_text.strip():
            if len(r.note_text.strip()) < 40:
                raise HTTPException(400, "Catatan terlalu pendek")
            R.add_note(p, r.note_title.strip(), r.note_text.strip())
        if p.get("status") == "baru" and src:
            p["status"] = "riset"
        p["riset"] = {**(p.get("riset") or {}), **R.assess(src, C.load_config())}
        C.save_project(p)
    return project_get(pid)


class ScriptReq(BaseModel):
    script: dict


@app.post("/api/projects/{pid}/script/save")
def project_script_save(pid: str, r: ScriptReq):
    import aw_script as S
    with _plock:
        p = _proj(pid)
        old = p.get("script") or {}
        sc = S.normalize(r.script)
        for k in ("sumber", "model", "fakta"):
            if k in old:
                sc[k] = old[k]
        # tanda "sudah dicek manual" dipertahankan bila dalilnya tidak berubah
        checked = {_dalil_key(a) for a in old.get("adegan", []) if a.get("dicek")}
        S.verify(sc, p, log=lambda *_: None)
        for a in sc["adegan"]:
            if _dalil_key(a) in checked:
                a["dicek"] = True
        p["script"] = sc
        p["approved"] = False
        p["status"] = "naskah"
        C.save_project(p)
    return project_get(pid)


def _dalil_key(a: dict) -> str:
    if a.get("tipe") == "quran":
        return f"q{a.get('surat')}:{a.get('ayat')}"
    if a.get("tipe") == "hadits":
        return "h" + re.sub(r"\W+", "", (a.get("kutipan") or "").lower())[:80]
    return ""


class ApproveReq(BaseModel):
    approved: bool
    checked: list[int] = []


@app.post("/api/projects/{pid}/approve")
def project_approve(pid: str, r: ApproveReq):
    with _plock:
        p = _proj(pid)
        sc = p.get("script")
        if not sc:
            raise HTTPException(400, "Naskah belum ada")
        for i, a in enumerate(sc["adegan"]):
            if a.get("tipe") in ("quran", "hadits"):
                a["dicek"] = i in r.checked
        if r.approved:
            import aw_script as S
            cfg = C.load_config()
            n, need = S.spoken_words(sc), int(int(cfg.get("target_words", 140)) * 0.55)
            if n < need:
                raise HTTPException(400, f"Naskah terlalu pendek ({n} kata, minimal {need}) — video akan tipis. "
                                         "Tulis ulang naskah setelah menambah bahan, atau perpanjang narasi di editor.")
            bad = [i + 1 for i, a in enumerate(sc["adegan"]) if a.get("tipe") in ("quran", "hadits")
                   and a.get("status") != "ok" and not a.get("dicek")]
            if bad:
                raise HTTPException(400, f"Adegan {', '.join(map(str, bad))}: dalil belum terverifikasi. "
                                         "Centang 'sudah saya cek' atau hapus adegannya.")
        p["approved"] = r.approved
        C.save_project(p)
    return project_get(pid)


_pv_lock = threading.Lock()


class PreviewReq(BaseModel):
    project: str = ""
    index: int = 0
    script: dict | None = None
    style: dict | None = None


SAMPLE = {
    "judul_pendek": "Kenapa Harus *Mandi Wajib*?",
    "adegan": [
        {"tipe": "tanya", "narasi": "Habis berhubungan suami istri, kenapa sih wajib mandi?", "teks": "Habis berhubungan, kenapa *wajib mandi*?"},
        {"tipe": "bicara", "narasi": "Kondisi ini disebut junub.", "teks": "Kondisi ini disebut *junub* (hadas besar)", "ikon": ["air", "sajadah"]},
        {"tipe": "quran", "narasi": "Allah berfirman dalam surat Al-Maidah ayat enam.", "tampil": "Jika kamu dalam keadaan junub, mandilah.",
         "ref_label": "QS. Al-Ma'idah: 6", "ayat_data": {"arab": ""}},
        {"tipe": "poin", "narasi": "Hikmahnya apa?", "judul": "Hikmahnya", "poin": [{"ikon": "daun", "teks": "Badan kembali *segar*"},
                                                                                       {"ikon": "tetes", "teks": "Suci lagi untuk ibadah"}]},
        {"tipe": "langkah", "narasi": "Caranya singkat.", "judul": "Cara singkat", "langkah": ["Niat", "Cuci kemaluan", "Wudhu", "Siram seluruh tubuh"]},
        {"tipe": "fakta", "narasi": "Jadi hukumnya wajib.", "besar": "WAJIB", "kecil": "Sebelum shalat, mandi junub dulu"},
        {"tipe": "penutup", "narasi": "Kamu biasanya gimana?", "tanya": "Kamu biasanya gimana?", "a": "Langsung mandi", "b": "Ditunda"},
    ]}


@app.post("/api/preview")
def preview(r: PreviewReq):
    import aw_render as RD
    cfg = _cfg()
    if r.style:
        cfg["style"] = C.style_of({"style": r.style})
    if r.script:
        sc = r.script
    elif r.project:
        sc = _proj(r.project).get("script") or SAMPLE
    else:
        sc = SAMPLE
    if not sc.get("adegan"):
        raise HTTPException(400, "Naskah kosong")
    idx = max(0, min(r.index, len(sc["adegan"]) - 1))
    out = DATA_DIR / f"pv_{uuid.uuid4().hex[:8]}.jpg"
    try:
        with _pv_lock:
            RD.preview_scene(sc, idx, cfg, str(out))
        return {"image": "data:image/jpeg;base64," + base64.b64encode(out.read_bytes()).decode(), "index": idx,
                "count": len(sc["adegan"])}
    except Exception as e:
        raise HTTPException(400, f"Preview gagal: {str(e)[:300]}")
    finally:
        out.unlink(missing_ok=True)


@app.get("/api/icons")
def icons():
    import aw_doodle as D
    return {"icons": D.ICON_NAMES, "poses": list(D.POSES), "expr": list(D.EXPRS)}


# ========================= HASIL
def _out_dir() -> Path:
    return Path(_cfg()["output_dir"])


def _res_folder(name: str) -> Path:
    p = (_out_dir() / Path(name).name).resolve()
    if not p.is_dir():
        raise HTTPException(404, "Folder hasil tidak ada")
    return p


@app.get("/api/outputs")
def outputs():
    od = _out_dir()
    if not od.exists():
        return []
    res = []
    for d in sorted((x for x in od.iterdir() if x.is_dir()), key=lambda x: x.name, reverse=True):
        n = len([f for f in d.iterdir() if VIDEO_RE.match(f.name)])
        if n:
            res.append({"name": d.name, "videos": n})
    return res


@app.get("/api/output")
def output(folder: str, account: str = ""):
    import aw_upload_fb
    d = _res_folder(folder)
    acc = account or _fb_active()
    log = {}
    for name in ([f"fb_upload_log_{acc}.json"] if acc else []):
        try:
            log.update(json.loads((d / name).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    cfg = _cfg()
    plan = {os.path.basename(f): s.strftime("%Y-%m-%dT%H:%M") for f, s in aw_upload_fb.plan(str(d), cfg["upload_times_wib"])}
    vids = []
    for f in sorted(d.iterdir(), key=lambda x: int(VIDEO_RE.match(x.name).group(1)) if VIDEO_RE.match(x.name) else 0):
        if not VIDEO_RE.match(f.name):
            continue
        cap = f.with_name(f.name.replace("_final.mp4", "_caption.txt"))
        meta = f.with_name(f.name.replace("_final.mp4", "_meta.json"))
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            m = {}
        vids.append({"name": f.name, "size_mb": round(f.stat().st_size / 1e6, 1),
                     "caption": cap.read_text(encoding="utf-8") if cap.exists() else "",
                     "duration": m.get("duration"), "topik": m.get("topik", ""), "hook": m.get("hook", ""),
                     "dalil": m.get("dalil", []), "uploaded": log.get(f.name), "plan": plan.get(f.name, "")})
    return {"folder": d.name, "path": str(d), "videos": vids}


class CaptionReq(BaseModel):
    folder: str
    name: str
    text: str


@app.post("/api/caption")
def caption_save(r: CaptionReq):
    if not VIDEO_RE.match(Path(r.name).name):
        raise HTTPException(400, "Nama file tidak valid")
    d = _res_folder(r.folder)
    (d / Path(r.name).name.replace("_final.mp4", "_caption.txt")).write_text(r.text, encoding="utf-8")
    return {"ok": True}


@app.get("/api/file")
def get_file(folder: str, name: str):
    d = _res_folder(folder)
    f = d / Path(name).name
    if not VIDEO_RE.match(f.name) or not f.exists():
        raise HTTPException(404, "File tidak ada")
    return FileResponse(f, media_type="video/mp4")


class UploadItem(BaseModel):
    name: str
    wib: str


class UploadReq(BaseModel):
    folder: str
    account: str
    items: list[UploadItem]


@app.post("/api/upload")
def upload(r: UploadReq):
    if _running("upload"):
        raise HTTPException(400, "Upload lain masih berjalan")
    if r.account not in _fb_ids():
        raise HTTPException(400, "Pilih Halaman Facebook (tab Akun Facebook)")
    if not r.items:
        raise HTTPException(400, "Pilih minimal satu video")
    d = _res_folder(r.folder)
    lead = getattr(_fbu(), "MIN_LEAD_MINUTES", 11)
    now = time.time() + (lead + 1) * 60
    plan = []
    for it in r.items:
        if not VIDEO_RE.match(Path(it.name).name) or not (d / Path(it.name).name).exists():
            raise HTTPException(400, f"Video tidak ada: {it.name}")
        try:
            t = time.mktime(time.strptime(it.wib, "%Y-%m-%dT%H:%M"))
        except ValueError:
            raise HTTPException(400, f"Jadwal tidak valid: {it.name}")
        if t < now:
            raise HTTPException(400, f"{it.name}: jadwal minimal {lead + 1} menit dari sekarang")
        plan.append({"name": Path(it.name).name, "wib": it.wib.replace("T", " ")})
    plan_path = DATA_DIR / f"fbplan_{uuid.uuid4().hex[:8]}.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return _spawn("upload", "aw_upload_fb.py",
                  ["--folder", str(d), "--plan", str(plan_path), "--account-dir", str(FB_DIR / r.account), "--yes"],
                  f"{len(plan)} Reels → {_fb_label(r.account)} ({d.name})")


# ========================= PILIH FOLDER (dialog Windows)
_PICK = r"""
import sys, tkinter as tk
from tkinter import filedialog
start = sys.argv[1]
root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
p = filedialog.askdirectory(initialdir=start or None, title="Pilih folder")
sys.stdout.write(p or "")
"""


@app.get("/api/pick")
def pick(start: str = ""):
    start = start.strip().strip('"')
    init = start if os.path.isdir(start) else str(BASE_DIR)
    out = subprocess.run([sys.executable, "-c", _PICK, init], capture_output=True, text=True, encoding="utf-8", timeout=600)
    return {"path": os.path.normpath(out.stdout.strip()) if out.stdout.strip() else ""}


# ========================= AKUN FACEBOOK (format sama dengan engine lain)
def _fb_id(raw: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", (raw or "").strip().lower()).strip("-")[:40]


def _fb_ids(base: Path = FB_DIR) -> list[str]:
    return sorted(d.name for d in base.iterdir() if d.is_dir() and (d / "token.txt").exists()) if base.exists() else []


def _fb_meta(acc: str, base: Path = FB_DIR) -> dict:
    try:
        return json.loads((base / acc / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _fb_active() -> str:
    ids = _fb_ids()
    try:
        a = FB_ACTIVE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        a = ""
    return a if a in ids else (ids[0] if ids else "")


def _fb_label(acc: str) -> str:
    m = _fb_meta(acc)
    return m.get("page_name") or m.get("name") or acc


def _fb_call(fn, *a, **kw):
    fbu = _fbu()
    try:
        return fn(*a, **kw)
    except fbu.GraphError as e:
        raise HTTPException(400, f"Facebook: {e}")


@app.get("/api/fb/accounts")
def fb_accounts():
    act = _fb_active()
    others = []
    for label, base in SIBLING_FB_DIRS.items():
        for i in _fb_ids(base):
            others.append({"id": i, "from": label, "label": _fb_meta(i, base).get("page_name") or i, "exists": i in _fb_ids()})
    return {"accounts": [{"id": i, **{k: _fb_meta(i).get(k, "") for k in ("name", "page_id", "page_name", "link", "verified_at")},
                          "active": i == act} for i in _fb_ids()], "others": others}


class FbAccountReq(BaseModel):
    name: str
    page_id: str
    token: str


def _fb_save(acc: str, name: str, page_id: str, page_token: str, info: dict):
    d = FB_DIR / acc
    d.mkdir(parents=True, exist_ok=True)
    (d / "token.txt").write_text(page_token, encoding="utf-8")
    (d / "meta.json").write_text(json.dumps({
        "name": name, "page_id": str(info.get("id") or page_id), "page_name": info.get("name", ""),
        "link": info.get("link", ""), "verified_at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")


@app.post("/api/fb/accounts")
def fb_account_add(r: FbAccountReq):
    name, page_id, token = r.name.strip(), r.page_id.strip(), r.token.strip()
    acc = _fb_id(name)
    if not acc:
        raise HTTPException(400, "Isi nama akun")
    if not re.fullmatch(r"\d{5,25}", page_id):
        raise HTTPException(400, "Page ID harus berupa angka")
    if len(token) < 20:
        raise HTTPException(400, "Token terlalu pendek")
    page_token, info = _fb_call(_fbu().resolve_token, page_id, token)
    _fb_save(acc, name, page_id, page_token, info)
    if not FB_ACTIVE_FILE.exists():
        FB_ACTIVE_FILE.write_text(acc, encoding="utf-8")
    return {"id": acc, "page_name": info.get("name", "")}


class ImportReq(BaseModel):
    id: str
    source: str


@app.post("/api/fb/import")
def fb_import(r: ImportReq):
    base = SIBLING_FB_DIRS.get(r.source)
    acc = Path(r.id).name
    if not base or acc not in _fb_ids(base):
        raise HTTPException(404, "Akun tidak ada")
    meta = _fb_meta(acc, base)
    token = (base / acc / "token.txt").read_text(encoding="utf-8").strip()
    page_token, info = _fb_call(_fbu().resolve_token, meta.get("page_id", ""), token)
    _fb_save(acc, meta.get("name") or acc, meta.get("page_id", ""), page_token, info)
    if not FB_ACTIVE_FILE.exists():
        FB_ACTIVE_FILE.write_text(acc, encoding="utf-8")
    return {"id": acc, "page_name": info.get("name", "")}


@app.post("/api/fb/accounts/{acc}/activate")
def fb_activate(acc: str):
    if acc not in _fb_ids():
        raise HTTPException(404, "Akun tidak ada")
    FB_ACTIVE_FILE.write_text(acc, encoding="utf-8")
    return {"ok": True}


@app.post("/api/fb/accounts/{acc}/verify")
def fb_verify(acc: str):
    if acc not in _fb_ids():
        raise HTTPException(404, "Akun tidak ada")
    m = _fb_meta(acc)
    token = (FB_DIR / acc / "token.txt").read_text(encoding="utf-8").strip()
    page_token, info = _fb_call(_fbu().resolve_token, m.get("page_id", ""), token)
    _fb_save(acc, m.get("name") or acc, m.get("page_id", ""), page_token, info)
    return {"page_name": info.get("name", "")}


@app.post("/api/fb/accounts/{acc}/delete")
def fb_delete(acc: str):
    if acc not in _fb_ids():
        raise HTTPException(404, "Akun tidak ada")
    shutil.rmtree(FB_DIR / acc)
    if FB_ACTIVE_FILE.exists() and FB_ACTIVE_FILE.read_text(encoding="utf-8").strip() == acc:
        FB_ACTIVE_FILE.unlink()
    return {"ok": True}


# ========================= HALAMAN
@app.get("/")
def index():
    return FileResponse(UI_DIR / "static" / "index.html", headers={"Cache-Control": "no-store, must-revalidate"})


app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("UI_PORT", "8600")))
