"""Rapikan Page Facebook Air-Wudhu lewat Graph API: foto sampul + About + Deskripsi.
  python aw_fb_profile.py --account-dir ui/data/fb_accounts/air-wudhu [--profile-pic] [--dry]
Butuh izin token: pages_manage_metadata + pages_manage_posts."""
import argparse, json, os, sys
import aw_common as C

BASE = os.path.dirname(os.path.abspath(__file__))
ABOUT = ("Doodle dakwah singkat tentang fiqih ibadah: santai, jelas, dan berdalil. "
         "Yuk belajar bareng dan saling mengingatkan dalam kebaikan! 💧🤝")
DESC = ("Air-Wudhu hadir lewat video doodle singkat (Reels) yang membahas fiqih ibadah sehari-hari — "
        "wudhu, mandi wajib, shalat, dan adab — dengan bahasa santai dan merujuk pada dalil Al-Qur'an dan hadits.\n\n"
        "Tujuannya sederhana: belajar bareng dan saling mengingatkan dalam kebaikan.\n\n"
        "Konten bersifat edukasi umum. Untuk persoalan khusus, silakan bertanya kepada ustadz/ulama terpercaya.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-dir", required=True)
    ap.add_argument("--profile-pic", action="store_true", help="unggah juga logo sebagai foto profil")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    fb = C.fb_module()
    d = os.path.join(BASE, a.account_dir) if not os.path.isabs(a.account_dir) else a.account_dir
    page_id = str(json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["page_id"])
    t, _ = fb.resolve_token(page_id, open(os.path.join(d, "token.txt")).read().strip())
    cover = os.path.join(BASE, "assets", "cover-halaman.png")
    print("About :", ABOUT, "\nDesc  :", DESC[:80], "...")
    if a.dry:
        return
    r = fb._post_multipart(f"{fb.GRAPH}/{page_id}/photos", {"access_token": t, "published": "false"}, "source", cover, what="cover")
    print("cover set:", fb.graph_post(page_id, t, {"cover": r["id"], "no_feed_story": "true"}))
    print("info set :", fb.graph_post(page_id, t, {"about": ABOUT, "description": DESC}))
    if a.profile_pic:
        from PIL import Image
        png = os.path.join(BASE, "assets", "profile-halaman.png")
        Image.open(os.path.join(BASE, "assets", "profile halaman.webp")).convert("RGB").save(png)
        print("picture  :", fb._post_multipart(f"{fb.GRAPH}/{page_id}/picture", {"access_token": t}, "source", png, what="profile"))


if __name__ == "__main__":
    main()
