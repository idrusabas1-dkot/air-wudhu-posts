"""
Jadwalkan video hasil engine Air Wudhu ke Fanspage Facebook (Reels) lewat Graph API resmi
(facebook_uploader dari criminal_reel_youtube).

  python aw_upload_fb.py --folder output/2026-11-15 --plan plan.json --account-dir ui/data/fb_accounts/<akun> --yes

plan.json: [{"name": "auto_video_1_final.mp4", "wib": "2026-11-15 05:30"}]
Video yang sudah terunggah dicatat di fb_upload_log_<akun>.json di folder itu (tidak terunggah dua kali).
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

import aw_common as C

WIB = dt.timezone(dt.timedelta(hours=7))


def plan(folder, times, min_lead=11):
    files = sorted(glob.glob(os.path.join(folder, "auto_video_*_final.mp4")),
                   key=lambda p: int(re.search(r"auto_video_(\d+)_", p).group(1)))
    try:
        day = dt.date.fromisoformat(os.path.basename(os.path.normpath(folder)))
    except ValueError:
        day = dt.date.today()
    day = max(day, dt.date.today())
    now = dt.datetime.now(WIB) + dt.timedelta(minutes=min_lead + 1)
    slots, d = [], day
    while len(slots) < len(files):
        for t in times:
            hh, mm = map(int, t.split(":"))
            s = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=WIB)
            if s > now and len(slots) < len(files):
                slots.append(s)
        d += dt.timedelta(days=1)
    return list(zip(files, slots))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--account-dir", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    fb = C.fb_module()
    folder = os.path.abspath(a.folder)
    acc = os.path.basename(os.path.normpath(a.account_dir))
    log_path = os.path.join(folder, f"fb_upload_log_{acc}.json")
    done = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else {}
    with open(a.plan, encoding="utf-8") as f:
        items = [(os.path.join(folder, os.path.basename(p["name"])),
                  dt.datetime.strptime(p["wib"], "%Y-%m-%d %H:%M").replace(tzinfo=WIB)) for p in json.load(f)]
    items = [(f, s) for f, s in items if os.path.basename(f) not in done]
    if not items:
        print("Tidak ada video baru untuk diunggah.")
        return
    for f, s in items:
        print(f"  {os.path.basename(f):28s} -> {s:%Y-%m-%d %H:%M} WIB")
    if not a.yes:
        print("\n(dry run) Tambahkan --yes untuk mengunggah.")
        return
    with open(os.path.join(a.account_dir, "token.txt"), encoding="utf-8") as f:
        token = f.read().strip()
    with open(os.path.join(a.account_dir, "meta.json"), encoding="utf-8") as f:
        page_id = str(json.load(f)["page_id"])
    token, info = fb.resolve_token(page_id, token)
    print(f"📘 Halaman: {info.get('name')}")
    ok = 0
    for f, s in items:
        cap_path = f.replace("_final.mp4", "_caption.txt")
        caption = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""
        title = caption.splitlines()[0] if caption else None
        utc = s.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            res = fb.upload_reel(page_id, token, f, caption, publish_at_utc=utc, title=title)
        except fb.GraphError as e:
            print(f"❌ {os.path.basename(f)}: {e}")
            continue
        done[os.path.basename(f)] = {"video_id": res["video_id"], "jadwal_wib": f"{s:%Y-%m-%d %H:%M}",
                                     "link": fb.permalink(res["video_id"]), "page": info.get("name", "")}
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(done, fh, ensure_ascii=False, indent=2)
        ok += 1
        print(f"✅ {os.path.basename(f)} terjadwal {s:%Y-%m-%d %H:%M} WIB (id {res['video_id']})")
    print(f"\nSelesai: {ok}/{len(items)} video terjadwal.")
    if ok < len(items):
        sys.exit(1)


if __name__ == "__main__":
    main()
