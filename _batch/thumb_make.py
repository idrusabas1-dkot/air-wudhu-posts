"""Thumbnail menarik untuk semua video Fanspage Air-Wudhu (2026-11-22).

  python _batch/thumb_make.py            # buat semua -> output/thumbnail/<video_id>.jpg + lembar pratinjau
  python _batch/thumb_make.py --upload   # pasang ke Facebook (POST /{video_id}/thumbnails, is_preferred)

Isi penting di zona tengah 4:5 (y 285..1635) supaya tidak terpotong di feed.
Kata dalam *bintang* = kuning.
"""
import json
import math
import os
import sys
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = r"I:\AG\air-wudhu"
sys.path.insert(0, BASE)
os.chdir(BASE)
import aw_common as C  # noqa: E402

OUT = os.path.join(BASE, "output", "thumbnail")
FR = os.path.join(OUT, "frames")
FONT = os.path.join(BASE, "assets", "fonts")
ANTON = os.path.join(FONT, "Anton-Regular.ttf")
POPX = os.path.join(FONT, "Poppins-ExtraBold.ttf")
W, H = 1080, 1920
YEL = (255, 214, 0)
RED = (226, 38, 44)
GREEN = (22, 120, 84)

# id: (hook merah, judul 3 baris dengan *kata kunci*, proyek kisah lokal / None, latar cadangan, frame cadangan)
SPEC = {
    "4100414023599532": ("SERING DIPERDEBATKAN", "GERAKKAN *JARI*\nSAAT TAHIYAT\nITU *WAJIB?*",
                         "20261123_190026_menggerak-gerakkan-jari-telunj"),
    "1618768156956859": ("BANYAK YANG KELIRU!", "*JARI KAKI* TAK\nHADAP KIBLAT,\nSHOLAT *BATAL?*",
                         "20261123_190026_jari-kaki-tidak-menghadap-kibl"),
    "1948658552966004": ("BANYAK YANG KELIRU!", "SUJUD TAPI\n*HIDUNG* TAK NEMPEL,\nSHOLAT *SAH?*",
                         "20261123_190026_sujud-tapi-hidung-tidak-menemp"),
    "2382712619166389": ("BANYAK YANG KELIRU!", "*RUKUK* KILAT\nTANPA BERHENTI,\nSHOLAT *SAH?*",
                         "20261122_171527_rukuk-terlalu-cepat-tanpa-berh"),
    "1880322186184234": ("SERING DIPERDEBATKAN", "*MEREM* SAAT\nSHOLAT, ITU\n*MAKRUH?*",
                         "20261122_171526_mata-merem-saat-sholat-biar-le"),
    "1036710859447656": ("BANYAK YANG KELIRU!", "BACA *AL-FATIHAH*\nDALAM *HATI*,\nSHOLAT *SAH?*",
                         "20261122_171527_membaca-al-fatihah-dalam-hati"),
    "2241524710099581": ("SERING DIPERDEBATKAN", "BACA *USHOLLI*\nSEBELUM TAKBIR\nITU *WAJIB?*",
                         "20261122_004203_membaca-usholli-itu-wajib-sebe"),
    "915402391562859": ("BANYAK YANG KELIRU!", "ANGKAT TANGAN\nSETINGGI *TELINGA*\nITU *WAJIB?*",
                        "20261122_004203_takbiratul-ihram-sambil-mengan"),
    "1119537370840271": ("SERING DIPERDEBATKAN", "NIAT SHOLAT\nHARUS *DIUCAPKAN*\nBIAR *SAH?*",
                         "20261122_004203_niat-sholat-harus-dilafalkan-p"),
    "1719126066488114": ("JARANG YANG TAHU", "TAYAMMUM PAKAI\nDEBU *TEMBOK CAT*\nITU *SAH?*",
                         "20261120_210947_tayammum-bisa-pakai-debu-yang"),
    "1864312948054694": ("SERING TERJADI!", "KOTORAN *CICAK*\nDI SAJADAH,\nSHOLAT *BATAL?*",
                         "20261120_210947_kotoran-cicak-yang-kering-di-s"),
    "1479041317540510": ("MUSLIMAH WAJIB TAHU", "KEPUTIHAN\n*BATAL WUDHU*\nDAN *NAJIS?*",
                         "20261120_210947_keputihan-pada-wanita-selalu-m"),
    "1125394803640426": ("SERING TERJADI!", "DARAH *NYAMUK*\nDI BAJU, SHOLAT\n*TIDAK SAH?*",
                         "20261120_092130_kisah-darah-nyamuk-di-baju-sho"),
    "1153197413957348": ("KATA SIAPA?", "KENCING\n*BERDIRI*\n*HARAM* MUTLAK?",
                         "20261120_092130_kisah-kencing-berdiri-haram-mu"),
    "1130507052899779": ("HATI-HATI!", "LIUR *ANJING*\nCUKUP DICUCI\n*SABUN?*", "masjid"),
    "2197175771675972": ("MENURUT ISLAM", "BATAS *AURAT*\nDI ZAMAN\n*MODERN*", "majelis"),
    "1678002830400018": ("PESAN AL-QUR'AN", "*JAGA*\n*PANDANGAN* DI\nRUANG PUBLIK", "serambi"),
    "28841890932180587": ("RENUNGAN", "TUBUH KITA,\nSIAPA YANG\n*MENGATUR?*", "pendopo"),
    "1756843762066963": ("SERING DISEPELEKAN", "KUMUR SAAT\nWUDHU *BOLEH*\n*DITINGGAL?*", "pesantren"),
    "1135276919362654": ("MUSLIMAH WAJIB TAHU", "*KUTEK HALAL*\nTETAP BIKIN\nWUDHU *TIDAK SAH?*", "ruang_tamu"),
    "1510767997578778": ("SERING TERJADI!", "*NGOBROL*\nSAAT WUDHU,\nWUDHU *BATAL?*", "masjid"),
    "1833220701225771": ("TERNYATA BUKAN!", "MENGUSAP *LEHER*\nSAAT WUDHU\nITU *SUNNAH?*", "serambi"),
    "1450116067335005": ("BEDA MAZHAB!", "*SENTUH*\nLAWAN JENIS,\nWUDHU *BATAL?*", "majelis"),
    "1179515511402612": ("CEK HUKUMNYA", "*NGUPIL* SAAT\nPUASA & WUDHU\nLANGSUNG *BATAL?*", "pendopo"),
    "1181142097929228": ("BANYAK YANG RAGU", "WUDHU DI KAMAR\nMANDI ADA *WC*\n*TIDAK SAH?*", "ruang_tamu"),
    "2414224725990802": ("INI BATASANNYA", "KENAPA ISTRI\nHARUS *TAAT*\nPADA *SUAMI?*", "pesantren"),
    "1132271632944424": ("3 PENDAPAT ULAMA", "LAKI-LAKI WAJIB\n*BERJAMAAH*\nDI *MASJID?*", "masjid"),
    "1788815205734231": ("YUK, KETAHUI!", "KENAPA *WUDHU*\nHARUS SEBELUM\n*SHOLAT?*", "serambi"),
    "2647360872392083": ("PASUTRI WAJIB TAHU", "KENAPA *MANDI*\n*WAJIB* SETELAH\nBERHUBUNGAN?", "majelis"),
}


# ---------------------------------------------------------------- latar
def scene_bg(pid):
    """Adegan pembuka kisah dirender ulang TANPA subtitle, kartu, dan judul (RGB)."""
    import aw_render as RD
    cfg = C.load_config()
    p = C.load_project(pid)
    sc = dict(p["script"]["adegan"][0], narasi="x", kartu=[], judul="")
    s2 = dict(p["script"], adegan=[sc, sc])
    tmp = os.path.join(OUT, "_scene.jpg")
    RD.preview_scene(s2, 1, cfg, tmp, at=0.3)
    return cv2.cvtColor(cv2.imread(tmp), cv2.COLOR_BGR2RGB)


def latar_bg(var):
    import aw_latar as AL
    img = AL.base(var, var == "pesantren")
    if img is None:                                               # 'kitab' = rak buku bawaan kisah
        import aw_kisah as KS
        import aw_doodle as D
        img = D.paper("terang").copy() if hasattr(D, "paper") else np.full((H, W, 3), 240, np.uint8)
        try:
            KS._latar_kitab(img) if hasattr(KS, "_latar_kitab") else None
        except Exception:
            pass
    return img.copy()


def grade(img):
    f = img.astype(np.float32) / 255.0
    f = np.clip((f - 0.5) * 1.12 + 0.5, 0, 1)                    # kontras
    g = f.mean(axis=2, keepdims=True)
    f = np.clip(g + (f - g) * 1.25, 0, 1)                         # saturasi
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    top = np.clip(1 - yy / 0.42, 0, 1) ** 1.3                     # gelap atas -> judul terbaca
    bot = np.clip((yy - 0.80) / 0.20, 0, 1) ** 1.5
    f = f * (1 - 0.70 * top) * (1 - 0.55 * bot)
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]
    vig = 1 - 0.28 * (xx ** 2) * 0.8 - 0.12 * ((yy * 2 - 1) ** 2)
    f *= vig
    return (f * 255).astype(np.uint8)


# ---------------------------------------------------------------- Gus Idrus
_FIGS = {}


def ustad():
    if "s" not in _FIGS:
        import aw_figur as F
        fig = F.get_figure()
        fr = fig.frame()
        st = fig.sticker(fr, w1=16, w2=6)
        ys, xs = np.where(st[:, :, 3] > 10)
        _FIGS["s"] = st[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return _FIGS["s"]


def paste(dst, rgba, x, y):
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    a = s[:, :, 3:4] / 255.0
    roi = dst[y0:y1, x0:x1].astype(np.float32)
    dst[y0:y1, x0:x1] = (roi * (1 - a) + s[:, :, :3] * a).astype(np.uint8)


def add_light(img, cx, cy, r, col, k=1.0):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    ang = np.arctan2(yy - cy, xx - cx)
    rays = 0.5 + 0.5 * np.cos(ang * 14)
    m = np.clip(1 - d, 0, 1) ** 1.6 * (0.55 + 0.45 * rays) + np.clip(1 - d * 2.2, 0, 1) ** 2 * 0.8
    add = m[:, :, None] * np.array(col, np.float32)[None, None] * k
    return np.clip(img.astype(np.float32) + add, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- teks
def parse(line):
    out, on = [], False
    for i, part in enumerate(line.split("*")):
        if part:
            out.append((part, on))
        on = not on
    return out


def headline(draw, text, cx, y, maxw=1000, size=158):
    lines = text.split("\n")
    while True:
        f = ImageFont.truetype(ANTON, size)
        widths = [sum(draw.textlength(p, font=f) for p, _ in parse(l)) for l in lines]
        if max(widths) <= maxw or size < 90:
            break
        size -= 4
    lh = int(size * 1.08)
    for l, wdt in zip(lines, widths):
        x = cx - wdt / 2
        for part, key in parse(l):
            draw.text((x + 6, y + 9), part, font=f, fill=(0, 0, 0, 170), stroke_width=12, stroke_fill=(0, 0, 0, 170))
            draw.text((x, y), part, font=f, fill=YEL if key else (255, 255, 255), stroke_width=11, stroke_fill=(18, 14, 12))
            x += draw.textlength(part, font=f)
        y += lh
    return y


def pill(img, text, cx, cy, font, fill, fg=(255, 255, 255), pad=(34, 16), angle=0.0, outline=None):
    d0 = ImageDraw.Draw(img)
    tw = d0.textlength(text, font=font)
    asc, desc = font.getmetrics()
    w, h = int(tw + pad[0] * 2), int(asc + desc + pad[1] * 2)
    lay = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((24, 26, 24 + w, 26 + h), radius=h // 2, fill=(0, 0, 0, 120))
    d.rounded_rectangle((18, 18, 18 + w, 18 + h), radius=h // 2, fill=fill, outline=outline, width=5 if outline else 0)
    d.text((18 + pad[0], 18 + pad[1] - 2), text, font=font, fill=fg)
    if angle:
        lay = lay.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
    return h


# ---------------------------------------------------------------- susun
def make(vid, spec, logo):
    hook, title, src = spec
    kisah = src and src.startswith("2026")
    bg = scene_bg(src) if kisah else latar_bg(src)
    if bg.shape[:2] != (H, W):
        bg = cv2.resize(bg, (W, H))
    img = grade(bg)
    seed = zlib.crc32(vid.encode())
    # Gus Idrus besar, kanan bawah, dengan cahaya emas
    st = ustad()
    tgt_h = 840 if kisah else 900
    sc = tgt_h / st.shape[0]
    spr = cv2.resize(st, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
    x = W - spr.shape[1] + (40 if kisah else -10)
    y = H - spr.shape[0] + 30
    img = add_light(img, x + spr.shape[1] * 0.55, y + spr.shape[0] * 0.30, 760, (255, 196, 90), 0.85)
    paste(img, spr, x, y)
    pim = Image.fromarray(img).convert("RGBA")
    d = ImageDraw.Draw(pim)
    # logo + seri
    if logo is not None:
        pim.alpha_composite(logo, (40, 300))
    f_ser = ImageFont.truetype(POPX, 38)
    pill(pim, "NGAJI SANTAI  •  GUS IDRUS", 40 + 130 + 270, 360, f_ser, GREEN + (255,), outline=(255, 214, 0))
    # hook merah miring
    f_hook = ImageFont.truetype(POPX, 52)
    pill(pim, hook, W / 2, 500, f_hook, RED + (255,), angle=2.0 if seed % 2 else -2.0, outline=(255, 255, 255))
    # judul
    yb = headline(d, title, W / 2, 570)
    # ajakan
    f_cta = ImageFont.truetype(POPX, 46)
    cta_y, cta_x = 1575, 350
    hh = pill(pim, "      SIMAK JAWABANNYA", cta_x, cta_y, f_cta, (255, 214, 0, 255), fg=(24, 20, 16), outline=(24, 20, 16))
    tw = ImageDraw.Draw(pim).textlength("      SIMAK JAWABANNYA", font=f_cta) + 68
    tx = cta_x - tw / 2 + 38
    ImageDraw.Draw(pim).polygon([(tx, cta_y - 20), (tx, cta_y + 20), (tx + 32, cta_y)], fill=(226, 38, 44))
    # tanda tanya besar dekoratif dekat judul (hanya bila judul pertanyaan)
    if "?" in title and not kisah:
        fq = ImageFont.truetype(ANTON, 420)
        lay = Image.new("RGBA", (360, 560), (0, 0, 0, 0))
        dq = ImageDraw.Draw(lay)
        dq.text((40, 0), "?", font=fq, fill=(255, 214, 0, 235), stroke_width=12, stroke_fill=(24, 20, 16))
        lay = lay.rotate(-12, resample=Image.BICUBIC, expand=True)
        pim.alpha_composite(lay, (40, 980))
    return pim.convert("RGB")


def load_logo(size=120):
    p = os.path.join(BASE, "assets", "profile halaman.webp")
    try:
        im = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return None
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size + 12, size + 12), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, size + 11, size + 11), fill=(255, 214, 0, 255))
    im.putalpha(m)
    out.alpha_composite(im, (6, 6))
    return out


def build(only=None):
    logo = load_logo()
    files = []
    for vid, spec in SPEC.items():
        if only and vid not in only:
            continue
        im = make(vid, spec, logo)
        fp = os.path.join(OUT, f"{vid}.jpg")
        im.save(fp, quality=92)
        files.append(fp)
        print("ok", vid, flush=True)
    # lembar pratinjau
    th = [Image.open(f).resize((216, 384)) for f in files]
    cols = 6
    sheet = Image.new("RGB", (216 * cols, 384 * math.ceil(len(th) / cols)), (0, 0, 0))
    for i, t in enumerate(th):
        sheet.paste(t, ((i % cols) * 216, (i // cols) * 384))
    sheet.save(os.path.join(OUT, "_pratinjau.jpg"), quality=88)


def upload():
    fb = C.fb_module()
    D = os.path.join(BASE, "ui", "data", "fb_accounts", "air-wudhu")
    tok, _ = fb.resolve_token("1534857413035794", open(os.path.join(D, "token.txt")).read().strip())
    log_p = os.path.join(OUT, "upload_log.json")
    log = json.load(open(log_p, encoding="utf-8")) if os.path.exists(log_p) else {}
    for vid in SPEC:
        fp = os.path.join(OUT, f"{vid}.jpg")
        try:
            fb.set_thumbnail(vid, tok, fp, tries=2, wait=5)
            log[vid] = "ok"
            print("✅", vid, flush=True)
        except Exception as e:
            log[vid] = f"gagal: {e}"
            print("❌", vid, e, flush=True)
        json.dump(log, open(log_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if "--upload" in sys.argv:
        upload()
    else:
        build([a for a in sys.argv[1:] if a.isdigit()] or None)
