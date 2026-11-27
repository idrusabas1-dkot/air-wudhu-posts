"""
Format KISAH (gaya "kisah nyata bersumber"): adegan ilustrasi datar layar penuh + kamera bergerak + kartu sumber.

Adegan naskah bertipe "kisah":
  {"tipe": "kisah", "narasi": "...",
   "shot": {"latar": "bukit|desa|mata_air|sawah|irisan|api", "hijau": [a, b] (0 gundul .. 1 hutan lebat),
            "aksi": "jalan|cangkul|tanam|angkut|tunjuk|diam|bangga", "warga": "angkut|tunjuk|antri|..." (opsional),
            "kambing": bool, "hujan": bool, "kamera": "dorong|mundur|geser|naik|turun", "fokus": [x, y]},
   "judul": "Teks *disorot* besar di atas" (opsional, pembuka),
   "kunci": ["kata", ...]   kata yang diberi kotak merah di subtitle (opsional),
   "kartu": [{"jenis": "lokasi|profil|tahun|angka|kutipan|label|penghargaan|tukar", "pada": "kata pemicu",
              ..., "sumber": "detikJateng 2024"}]}

Semua fakta di kartu WAJIB punya "sumber" (ditulis kecil di kartu). Modul ini hanya menggambar; isi naskah tetap
dari sumber yang sudah dibaca. Tidak ada gambar Nabi/sahabat; tokoh = orang biasa (petani, warga).
plan_scene(i, sc, seg, P, st) -> (aktor, sfx). Waktu relatif awal adegan; seg["words"] = [(t, dur, kata)].
"""
import functools

import aw_aura as AU
import aw_latar as AL
import math
import os
import re
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
HORIZON = 930

# ------------------------------------------------------------------ warna (RGB)
SKY_T, SKY_B = (168, 205, 228), (236, 230, 210)
SKY_FIRE_T, SKY_FIRE_B = (120, 92, 96), (236, 168, 112)
MOUNT = (150, 172, 186)
DRY, DRY_D, DRY_L = (214, 178, 126), (176, 138, 92), (228, 198, 152)
HILL_DRY, HILL_DRY_D = (200, 158, 108), (170, 128, 84)
GRASS, GRASS_D, GRASS_L = (128, 176, 92), (96, 146, 72), (156, 196, 112)
LEAF, LEAF_D, LEAF_L = (86, 158, 82), (62, 128, 66), (128, 192, 104)
TRUNK = (118, 88, 66)
WATER, WATER_D, WATER_L = (92, 170, 222), (60, 128, 190), (186, 226, 246)
ROOF, ROOF_D, WALL = (192, 74, 52), (150, 52, 38), (242, 238, 228)
STONE, STONE_D = (150, 148, 138), (112, 110, 102)
INK = (40, 36, 32)
RED = (224, 64, 56)

SKIN = (176, 120, 84)
FARMER = dict(shirt=(104, 128, 80), pants=(52, 50, 54), skin=SKIN, hat=(220, 190, 120), cap=None)
VILLAGERS = [dict(shirt=(70, 110, 170), pants=(60, 64, 76), skin=(196, 142, 100), hat=None, cap=(40, 36, 34)),
             dict(shirt=(214, 120, 140), pants=(90, 70, 110), skin=(204, 150, 110), hat=None, hijab=(200, 90, 120)),
             dict(shirt=(230, 230, 220), pants=(80, 84, 96), skin=(186, 132, 92), hat=None, cap=None),
             dict(shirt=(80, 150, 140), pants=(70, 60, 80), skin=(196, 142, 100), hat=None, hijab=(70, 90, 150))]


def _i(v):
    return int(round(v))


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def _ease(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def _back(p):
    p = max(0.0, min(1.0, p))
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def _rng(*xs):
    return np.random.RandomState(zlib.crc32(repr(xs).encode()) & 0x7FFFFFFF)


def _poly(img, pts, col, line=None, w=2):
    p = np.array([(_i(x), _i(y)) for x, y in pts], np.int32)
    cv2.fillPoly(img, [p], col, cv2.LINE_AA)
    if line is not None:
        cv2.polylines(img, [p], True, line, w, cv2.LINE_AA)


def _gradient(img, y0, y1, c0, c1):
    n = max(1, y1 - y0)
    t = np.linspace(0, 1, n)[:, None]
    col = (np.array(c0)[None, :] * (1 - t) + np.array(c1)[None, :] * t).astype(np.uint8)
    img[y0:y1] = col[:, None, :]


# ------------------------------------------------------------------ teks (PIL)
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
FONT_R = "C:/Windows/Fonts/segoeui.ttf"
FONT_M = "C:/Windows/Fonts/consola.ttf"


@functools.lru_cache(maxsize=64)
def _font(path, size):
    for p in (path, FONT_B, "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def blit(img, rgba, x, y, scale=1.0, alpha=1.0):
    """Tempel sprite RGBA dengan pusat (x, y)."""
    if rgba is None or alpha <= 0.01 or scale <= 0.02:
        return
    a = rgba
    if abs(scale - 1.0) > 0.01:
        a = cv2.resize(rgba, (max(1, _i(rgba.shape[1] * scale)), max(1, _i(rgba.shape[0] * scale))), interpolation=cv2.INTER_LINEAR)
    h, w = a.shape[:2]
    x0, y0 = _i(x - w / 2), _i(y - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xa >= xb or ya >= yb:
        return
    s = a[ya - y0:yb - y0, xa - x0:xb - x0]
    al = s[:, :, 3:4].astype(np.float32) * (alpha / 255.0)
    roi = img[ya:yb, xa:xb]
    roi[:] = (roi * (1 - al) + s[:, :, :3] * al).astype(np.uint8)


def _to_np(im):
    return np.array(im, dtype=np.uint8)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t.replace("*", ""), font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


@functools.lru_cache(maxsize=512)
def title_sprite(text, size=78, max_w=960, hi=(120, 200, 255)):
    """Judul pembuka: putih tebal, garis gelap; kata di antara *...* diberi warna sorot."""
    f = _font(FONT_B, size)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = _wrap(tmp, text, f, max_w)
    lh = int(size * 1.12)
    im = Image.new("RGBA", (max_w + 40, lh * len(lines) + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    on = False
    for li, ln in enumerate(lines):
        x = 20
        for tok in re.split(r"(\*)", ln):
            if tok == "*":
                on = not on
                continue
            if not tok:
                continue
            d.text((x, 16 + li * lh), tok, font=f, fill=hi + (255,) if on else (255, 255, 255, 255),
                   stroke_width=max(3, size // 14), stroke_fill=(30, 34, 40, 235))
            x += d.textlength(tok, font=f)
    return _to_np(im)


# ------------------------------------------------------------------ kartu
def _shadow_card(w, h, r=26, fill=(252, 249, 240), border=None, pad=24):
    im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + w, pad + h + 8), r, fill=(0, 0, 0, 70))
    sh = Image.fromarray(cv2.GaussianBlur(_to_np(sh), (0, 0), 7))
    im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, pad + w, pad + h), r, fill=fill + (255,), outline=border, width=3 if border else 0)
    return im, d, pad


def _src(d, x, y, text, col=(120, 116, 106)):
    if text:
        d.text((x, y), "sumber: " + text, font=_font(FONT_M, 21), fill=col + (255,))


@functools.lru_cache(maxsize=256)
def card_sprite(jenis, a="", b="", c="", src=""):
    """a/b/c arti per jenis: lokasi(a=tempat, b=keterangan), profil(a=nama, b=peran), tahun(a=tahun, b=ket),
    angka(a=angka, b=satuan, c=ket), kutipan(a=isi, b=oleh), penghargaan(a=nama, b=ket), tukar(a=kiri, b=kanan, c=ket)."""
    if jenis == "balon":                                                    # balon dialog tokoh
        f = _font(FONT_B, 42)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        lines = _wrap(tmp, a, f, 560)
        w = int(max(tmp.textlength(l, font=f) for l in lines) + 60)
        h = len(lines) * 52 + 40
        im = Image.new("RGBA", (w + 40, h + 70), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((10, 10, 10 + w, 10 + h), 30, fill=(255, 255, 255, 255), outline=(40, 36, 32, 255), width=4)
        left = (b or "kiri") == "kiri"
        tx = 60 if left else w - 60
        tip = (tx - 30, h + 62) if left else (tx + 34, h + 62)
        d.polygon([(tx - 18, 8 + h), (tx + 22, 8 + h), tip], fill=(255, 255, 255, 255))
        d.line([(tx - 18, 10 + h), tip, (tx + 22, 10 + h)], fill=(40, 36, 32, 255), width=4)
        for i, ln in enumerate(lines):
            d.text((40, 24 + i * 52), ln, font=f, fill=(34, 32, 30, 255))
        return _to_np(im)
    if jenis in ("hadits", "pendapat"):
        accent = {"hadits": (46, 140, 96), "pendapat": (214, 140, 40)}[jenis]
        big = len(a) < 120
        f = _font(FONT_B, 40 if big else 35)
        lh = 50 if big else 44
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        lines = _wrap(tmp, a, f, 760)
        hh = 58 if c else 0
        h = 70 + hh + len(lines) * lh + 70
        im, d, p = _shadow_card(860, h, border=accent)
        if c:
            fh = _font(FONT_B, 30)
            hw = tmp.textlength(c, font=fh) + 40
            d.rounded_rectangle((p + 40, p + 22, p + 40 + hw, p + 68), 14, fill=accent + (255,))
            d.text((p + 60, p + 25), c, font=fh, fill=(255, 255, 255, 255))
        d.text((p + 22, p + 2 + hh), "\u201C", font=_font(FONT_B, 90), fill=accent + (255,))
        for i, ln in enumerate(lines):
            d.text((p + 60, p + 34 + hh + i * lh), ln, font=f, fill=(34, 32, 30, 255))
        yb = p + 40 + hh + len(lines) * lh
        d.text((p + 60, yb + 4), "\u2014 " + b, font=_font(FONT_R, 30), fill=(70, 66, 60, 255))
        _src(d, p + 60, yb + 42, src)
        return _to_np(im)
    if jenis == "kutipan":
        f = _font(FONT_B, 40)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        lines = _wrap(tmp, a, f, 760)
        h = 70 + len(lines) * 50 + 70
        im, d, p = _shadow_card(860, h)
        d.text((p + 22, p + 2), "\u201C", font=_font(FONT_B, 90), fill=(150, 196, 226, 255))
        for i, ln in enumerate(lines):
            d.text((p + 60, p + 34 + i * 50), ln, font=f, fill=(34, 32, 30, 255))
        yb = p + 40 + len(lines) * 50
        d.text((p + 60, yb + 4), "\u2014 " + b, font=_font(FONT_R, 30), fill=(70, 66, 60, 255))
        _src(d, p + 60, yb + 42, src)
        return _to_np(im)
    if jenis == "angka":
        fa = _font(FONT_B, 92)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        wa = tmp.textlength(a, font=fa)
        fb = _font(FONT_B, 40)
        wb = tmp.textlength(b, font=fb)
        wc = tmp.textlength(c, font=_font(FONT_R, 30)) if c else 0
        w = int(max(wa + wb + 34, wc, 300) + 70)
        im, d, p = _shadow_card(w, 210 if c else 170, fill=(30, 36, 40), r=24)
        x0 = p + (w - (wa + wb + 14)) / 2
        d.text((x0, p + 14), a, font=fa, fill=(110, 232, 170, 255))
        d.text((x0 + wa + 14, p + 62), b, font=fb, fill=(110, 232, 170, 255))
        if c:
            d.text((p + (w - wc) / 2, p + 124), c, font=_font(FONT_R, 30), fill=(232, 232, 226, 255))
        _src(d, p + 30, p + (172 if c else 130), src, (160, 166, 170))
        return _to_np(im)
    if jenis == "tahun":
        fa = _font(FONT_B, 84)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        w = int(max(tmp.textlength(a, font=fa), tmp.textlength(b, font=_font(FONT_R, 30)) if b else 0, 260) + 60)
        im, d, p = _shadow_card(w, 190 if b else 150)
        d.rectangle((p + 22, p + 92, p + 22 + tmp.textlength(a, font=fa) + 8, p + 112), fill=(250, 214, 92, 255))
        d.text((p + 26, p + 6), a, font=fa, fill=(30, 28, 26, 255))
        if b:
            d.text((p + 28, p + 116), b, font=_font(FONT_R, 30), fill=(70, 66, 60, 255))
        _src(d, p + 28, p + (156 if b else 118), src)
        return _to_np(im)
    if jenis in ("lokasi", "profil", "penghargaan"):
        fa = _font(FONT_B, 50)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        wtxt = max(tmp.textlength(a, font=fa), tmp.textlength(b, font=_font(FONT_R, 32)) if b else 0, 330)
        w = int(wtxt + 190)
        im, d, p = _shadow_card(w, 190)
        cx, cy = p + 78, p + 92
        if jenis == "lokasi":
            d.ellipse((cx - 34, cy - 58, cx + 34, cy + 10), fill=(224, 64, 56, 255))
            d.polygon([(cx - 26, cy - 8), (cx + 26, cy - 8), (cx, cy + 46)], fill=(224, 64, 56, 255))
            d.ellipse((cx - 13, cy - 37, cx + 13, cy - 11), fill=(252, 249, 240, 255))
        elif jenis == "profil":
            d.ellipse((cx - 56, cy - 56, cx + 56, cy + 56), fill=(206, 226, 236, 255))
            d.ellipse((cx - 22, cy - 30, cx + 22, cy + 14), fill=SKIN + (255,))
            d.polygon([(cx - 58, cy - 26), (cx + 58, cy - 26), (cx, cy - 66)], fill=FARMER["hat"] + (255,))
            d.pieslice((cx - 46, cy + 18, cx + 46, cy + 110), 180, 360, fill=FARMER["shirt"] + (255,))
        else:
            d.ellipse((cx - 50, cy - 60, cx + 50, cy + 30), fill=(244, 196, 72, 255))
            d.rectangle((cx - 10, cy + 20, cx + 10, cy + 50), fill=(214, 160, 50, 255))
            d.rectangle((cx - 36, cy + 50, cx + 36, cy + 64), fill=(150, 110, 60, 255))
            for k in range(5):
                ang = -math.pi / 2 + (k - 2) * 0.5
                d.ellipse((cx + 34 * math.cos(ang) - 9, cy - 16 + 34 * math.sin(ang) - 9,
                           cx + 34 * math.cos(ang) + 9, cy - 16 + 34 * math.sin(ang) + 9), fill=(120, 170, 80, 255))
        d.text((p + 160, p + 22), a, font=fa, fill=(30, 28, 26, 255))
        if b:
            d.text((p + 162, p + 88), b, font=_font(FONT_R, 32), fill=(80, 76, 70, 255))
        _src(d, p + 162, p + 144, src)
        return _to_np(im)
    if jenis == "tukar":
        f = _font(FONT_B, 42)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        wa, wb = tmp.textlength(a, font=f), tmp.textlength(b, font=f)
        w = int(wa + wb + 150)
        im, d, p = _shadow_card(w, 170 if c else 130)
        d.text((p + 30, p + 26), a, font=f, fill=(30, 28, 26, 255))
        ax = p + 30 + wa + 18
        d.line((ax, p + 56, ax + 60, p + 56), fill=(224, 64, 56, 255), width=7)
        d.polygon([(ax + 60, p + 42), (ax + 82, p + 56), (ax + 60, p + 70)], fill=(224, 64, 56, 255))
        d.text((ax + 96, p + 26), b, font=f, fill=(50, 120, 60, 255))
        if c:
            d.text((p + 32, p + 86), c, font=_font(FONT_R, 28), fill=(80, 76, 70, 255))
        _src(d, p + 32, p + (130 if c else 92), src)
        return _to_np(im)
    # label: pil kecil berwarna
    f = _font(FONT_B, 34)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = int(tmp.textlength(a, font=f) + 44)
    col = {"merah": (220, 62, 52), "hijau": (52, 160, 92), "biru": (52, 120, 200), "coklat": (110, 84, 64)}.get(b or "merah", (220, 62, 52))
    hh = 58 + (28 if src else 0)
    im = Image.new("RGBA", (max(w, 260 if src else 0) + 16, hh + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, 8 + w, 8 + 58), 14, fill=col + (255,), outline=(255, 255, 255, 255), width=3)
    d.text((8 + 22, 8 + 6), a, font=f, fill=(255, 255, 255, 255))
    if src:
        d.rounded_rectangle((8, 70, 8 + max(w, 250), 70 + 30), 8, fill=(40, 40, 44, 200))
        d.text((16, 72), "sumber: " + src, font=_font(FONT_M, 20), fill=(230, 230, 230, 255))
    return _to_np(im)


# ------------------------------------------------------------------ tokoh datar
def _limb(img, p0, p1, col, w):
    cv2.line(img, (_i(p0[0]), _i(p0[1])), (_i(p1[0]), _i(p1[1])), col, max(1, _i(w)), cv2.LINE_AA)
    cv2.circle(img, (_i(p1[0]), _i(p1[1])), max(1, _i(w / 2)), col, -1, cv2.LINE_AA)


def _pt(p, ang, ln, face):
    """ang (derajat) dari arah bawah; positif = ke depan (arah hadap)."""
    a = math.radians(ang)
    return (p[0] + face * math.sin(a) * ln, p[1] + math.cos(a) * ln)


def pose_at(aksi, t, ph=0.0):
    """-> dict sudut sendi + offset. lean: badan condong ke depan; ua/fa: lengan atas/bawah (depan & belakang); th/sh: paha/betis."""
    t = t + ph
    P = dict(lean=0, ua1=8, fa1=12, ua2=-8, fa2=-4, th1=2, sh1=0, th2=-2, sh2=0, dy=0.0, dx=0.0, tool=None, tool_ang=0)
    if aksi == "jalan" or aksi == "angkut":
        s = math.sin(t * 6.0)
        P.update(th1=24 * s, sh1=max(0, -18 * s) + 4, th2=-24 * s, sh2=max(0, 18 * s) + 4, dy=-abs(math.cos(t * 6.0)) * 6)
        if aksi == "jalan":
            P.update(ua1=-20 * s, fa1=-10 * s + 14, ua2=20 * s, fa2=10 * s + 14)
        else:
            P.update(ua1=6, fa1=4, ua2=-6, fa2=-4, tool="jeriken")
    elif aksi == "cangkul":
        c = (t % 1.3) / 1.3
        up = _ease(c / 0.55) if c < 0.55 else 1 - _ease((c - 0.55) / 0.2) if c < 0.75 else 0.0
        P.update(lean=14 + 10 * (1 - up), ua1=40 + 140 * up, fa1=70 + 110 * up, ua2=30 + 140 * up, fa2=60 + 110 * up,
                 th1=18, sh1=-6, th2=-14, sh2=6, tool="cangkul", tool_ang=80 + 150 * up)
    elif aksi == "tanam":
        b = math.sin(t * 2.4)
        P.update(lean=34, ua1=70 + 8 * b, fa1=40 + 10 * b, ua2=50, fa2=30, th1=84, sh1=-84, th2=8, sh2=-92, dy=23, tool="bibit")
    elif aksi == "tunjuk":
        b = math.sin(t * 9.0)
        P.update(ua1=82, fa1=88, ua2=-10, fa2=40, lean=-4 + 2 * b, dy=-2 * abs(b))
    elif aksi == "bangga":
        P.update(ua1=40, fa1=150, ua2=30, fa2=140, tool="piala", dy=-2 * math.sin(t * 2.0))
    elif aksi == "mikir":
        P.update(ua1=150, fa1=200, ua2=-6, fa2=30, lean=-3, dy=-1.2 * math.sin(t * 2.0))
    elif aksi == "bicara":
        b = math.sin(t * 3.4)
        P.update(ua1=50 + 18 * b, fa1=95 + 20 * b, ua2=-10, fa2=10, dy=-1.5 * math.sin(t * 2.2))
    elif aksi == "kaget":
        P.update(ua1=150, fa1=170, ua2=-150, fa2=-170, lean=-8, dy=-2 * abs(math.sin(t * 6)))
    elif aksi == "cuci":
        b = math.sin(t * 7.0)
        P.update(lean=30, ua1=62 + 10 * b, fa1=78 + 12 * b, ua2=52 - 8 * b, fa2=70 - 10 * b, th1=84, sh1=-84, th2=8, sh2=-92, dy=23,
                 tool="mangkuk")
    elif aksi == "sholat":
        P.update(ua1=14, fa1=128, ua2=10, fa2=122, dy=-0.6 * math.sin(t * 1.6))
    elif aksi == "tepuk":
        c = (t % 1.1) / 1.1
        k = 1.0 - abs(math.sin(math.pi * min(1.0, c / 0.35))) if c < 0.35 else 1.0
        P.update(ua1=70, fa1=96 - 30 * k, ua2=70, fa2=150 + 20 * k, lean=4)
    elif aksi == "cek":
        P.update(ua1=30, fa1=120, ua2=20, fa2=100, lean=12, dy=-0.8 * math.sin(t * 2.0))
    elif aksi == "pikul":
        P.update(ua1=-150, fa1=-200, ua2=150, fa2=195, tool="pikul", dy=-1.5 * math.sin(t * 2.2))
    elif aksi in ("duduk", "dengar", "baca", "tanya", "ngobrol"):           # duduk bersila (tampak samping)
        P.update(th1=86, sh1=-172, th2=80, sh2=-166, dy=33, ua1=24, fa1=70, ua2=16, fa2=60, sit=True)
        if aksi == "dengar":
            P.update(nod=1.6 * max(0.0, math.sin(t * 2.6)))
        elif aksi == "baca":
            P.update(ua1=46, fa1=112, ua2=36, fa2=104, lean=10, tool="buku", nod=0.6 * math.sin(t * 1.4))
        elif aksi == "tanya":
            P.update(ua1=168 + 6 * math.sin(t * 5), fa1=176, ua2=16, fa2=60)
        elif aksi == "ngobrol":
            b = math.sin(t * 3.4)
            P.update(ua1=50 + 16 * b, fa1=96 + 18 * b)
    elif aksi == "ruku":
        P.update(lean=86, ua1=-6, fa1=-4, ua2=-10, fa2=-6, th1=-4, th2=4)
    elif aksi == "sujud":
        P.update(lean=124, ua1=52, fa1=82, ua2=46, fa2=78, th1=30, sh1=-120, th2=26, sh2=-116, dy=19)
    elif aksi == "sholat_gerak":                                             # rangkaian gerak sholat (jamaah serempak)
        return _seq_pose(SHOLAT_SEQ, t)
    elif aksi == "tepuk_dinding":
        P.update(ua1=84, fa1=86, ua2=78, fa2=82, lean=6)
    elif aksi == "usap_wajah":
        P.update(ua1=128, fa1=196, ua2=122, fa2=192, lean=-2)
    elif aksi == "usap_tangan":
        P.update(ua1=40, fa1=118, ua2=30, fa2=96, lean=8)
    elif aksi == "tayammum":
        return _seq_pose(TAYAMMUM_SEQ, t)
    elif aksi == "takbir":                                                 # kedua tangan diangkat, telapak dekat telinga
        P.update(ua1=68, fa1=180, ua2=62, fa2=176, lean=-2, dy=-0.5 * math.sin(t * 1.6))
    elif aksi == "takbir_gerak":                                           # berdiri -> angkat tangan -> sedekap
        return _seq_pose(TAKBIR_SEQ, t)
    elif aksi == "dada":                                                   # tangan di dada (niat di hati)
        P.update(ua1=22, fa1=150, ua2=-6, fa2=6, lean=-2, dy=-0.8 * math.sin(t * 1.8))
    elif aksi == "lega":
        P.update(ua1=60, fa1=150, ua2=-12, fa2=10, lean=-4, dy=-2.5 * abs(math.sin(t * 2.4)))
    elif aksi == "lambai":
        P.update(ua1=160, fa1=150 + 30 * math.sin(t * 8), ua2=-8, fa2=-4)
    else:
        P.update(dy=-1.5 * math.sin(t * 2.2))
    return P


TAYAMMUM_SEQ = [(0.0, "diam"), (0.5, "tepuk_dinding"), (1.4, "tepuk_dinding"), (1.9, "usap_wajah"), (3.0, "usap_wajah"),
                (3.5, "usap_tangan"), (4.6, "usap_tangan"), (5.2, "diam")]
TAKBIR_SEQ = [(0.0, "diam"), (0.7, "diam"), (1.2, "takbir"), (2.4, "takbir"), (2.9, "sholat"), (4.6, "sholat")]
SHOLAT_SEQ = [(0.0, "sholat"), (3.0, "sholat"), (3.6, "ruku"), (5.0, "ruku"), (5.6, "diam"), (6.4, "diam"), (7.2, "sujud"),
              (8.6, "sujud"), (9.2, "duduk"), (10.4, "duduk"), (11.0, "sujud"), (12.2, "sujud"), (13.0, "sholat")]


def _blend(A, B, k):
    out = dict(A)
    for key, v in B.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(A.get(key, 0), (int, float)):
            out[key] = A.get(key, 0) + (v - A.get(key, 0)) * k
        elif k >= 0.5:
            out[key] = v
    return out


def _seq_pose(seq, t):
    period = seq[-1][0]
    tt = t % period
    for (ta, pa), (tb, pb) in zip(seq, seq[1:]):
        if ta <= tt <= tb:
            k = 0.0 if pa == pb else _ease((tt - ta) / max(1e-3, tb - ta))
            return _blend(pose_at(pa, 0.0), pose_at(pb, 0.0), k)
    return pose_at(seq[0][1], t)


OUT = (46, 40, 38)


def _shade(img, x, y, rx, ry, k=0.7):
    """Bayangan lembut (menggelapkan elips) di (x, y)."""
    rx, ry = max(2, _i(rx)), max(1, _i(ry))
    x0, y0, x1, y1 = max(0, _i(x - rx)), max(0, _i(y - ry)), min(img.shape[1], _i(x + rx)), min(img.shape[0], _i(y + ry))
    if x0 >= x1 or y0 >= y1:
        return
    roi = img[y0:y1, x0:x1]
    m = np.zeros(roi.shape[:2], np.float32)
    cv2.ellipse(m, (_i(x) - x0, _i(y) - y0), (rx, ry), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    f = 1.0 - (1.0 - k) * m
    roi[:] = (roi * f[:, :, None]).astype(np.uint8)


def _chain(img, segs, ow):
    """segs = [(p0, p1, warna, tebal)]: semua garis tepi dulu, baru isi -> sambungan mulus bergaris tepi."""
    for p0, p1, col, w in segs:
        _limb(img, p0, p1, OUT, w + ow)
    for p0, p1, col, w in segs:
        _limb(img, p0, p1, col, w)


def person(img, x, y, h, spec, aksi="diam", t=0.0, face=1, ph=0.0, emote=True):
    """Tokoh datar bergaya ilustrasi (garis tepi, bayangan, wajah). (x, y) = titik kaki; h = tinggi. -> posisi kepala."""
    P = pose_at(aksi, t, ph)
    u = h / 100.0
    ow = max(2.0, 2.2 * u)
    _shade(img, x + face * (6 * u if P.get("sit") else 0), y + 1.5 * u, (30 if P.get("sit") else 17) * u, 4.2 * u, 0.62)
    hip = (x + P["dx"] * u, y - 47 * u + P["dy"] * u)
    up = 180 - P["lean"]                                                    # lean positif = condong ke depan
    sh = _pt(hip, up, 32 * u, face)
    neck = _pt(hip, up, 35 * u, face)
    head = _pt(hip, up, 44 * u, face)
    head = (head[0], head[1] + P.get("nod", 0) * u)
    lw = 7.5 * u
    shirt, pants, skin = spec["shirt"], spec["pants"], spec["skin"]
    darker = lambda c, k=0.78: tuple(int(v * k) for v in c)
    gamis = spec.get("gamis") or spec.get("hijab")                          # wanita: gamis panjang, lengan tertutup
    sarung = spec.get("sarung")
    arm_lo = shirt if gamis else skin
    # kaki & lengan belakang
    k2 = _pt(hip, P["th2"], 24 * u, face)
    f2 = _pt(k2, P["th2"] + P["sh2"], 23 * u, face)
    e2 = _pt(sh, P["ua2"], 15 * u, face)
    h2 = _pt(e2, P["fa2"], 14 * u, face)
    legc2 = darker(sarung or pants)
    _chain(img, [(hip, k2, legc2, lw * 1.15), (k2, f2, legc2, lw)], ow)
    cv2.ellipse(img, (_i(f2[0] + face * 3 * u), _i(f2[1])), (_i(5 * u), _i(2.6 * u)), 0, 0, 360, (40, 36, 34), -1, cv2.LINE_AA)
    _chain(img, [(sh, e2, darker(shirt), lw * 0.95), (e2, h2, darker(arm_lo), lw * 0.8)], ow)
    if gamis:
        cv2.circle(img, (_i(h2[0]), _i(h2[1])), max(1, _i(2.6 * u)), darker(skin), -1, cv2.LINE_AA)
    # kaki depan
    k1 = _pt(hip, P["th1"], 24 * u, face)
    f1 = _pt(k1, P["th1"] + P["sh1"], 23 * u, face)
    legc = sarung or pants
    _chain(img, [(hip, k1, legc, lw * 1.15), (k1, f1, legc, lw)], ow)
    cv2.ellipse(img, (_i(f1[0] + face * 3 * u), _i(f1[1])), (_i(5 * u), _i(2.6 * u)), 0, 0, 360, (40, 36, 34), -1, cv2.LINE_AA)
    if sarung and not P.get("sit"):                                         # motif kotak sarung
        for k in range(3):
            q = 0.25 + 0.25 * k
            a_ = (hip[0] + (k1[0] - hip[0]) * q, hip[1] + (k1[1] - hip[1]) * q)
            cv2.line(img, (_i(a_[0] - 5 * u), _i(a_[1])), (_i(a_[0] + 5 * u), _i(a_[1])), darker(sarung, 0.6), max(1, _i(1.1 * u)), cv2.LINE_AA)
    # badan (+ gamis)
    bw = 9.5 * u
    if gamis and not P.get("sit"):
        fy = max(f1[1], f2[1]) - 3 * u
        cx_ = (f1[0] + f2[0]) / 2
        skirt = [(hip[0] - 7 * u, hip[1] - 4 * u), (hip[0] + 7 * u, hip[1] - 4 * u), (cx_ + 13 * u, fy), (cx_ - 13 * u, fy)]
        _poly(img, skirt, shirt, OUT, max(1, _i(ow * 0.6)))
    elif gamis:
        _poly(img, [(hip[0] - 9 * u, hip[1] - 6 * u), (hip[0] + 9 * u, hip[1] - 6 * u), (hip[0] + face * 30 * u, y - 2 * u),
                    (hip[0] - face * 12 * u, y - 2 * u)], shirt, OUT, max(1, _i(ow * 0.6)))
    _chain(img, [(hip, sh, shirt, bw * 2)], ow)
    if spec.get("noda"):
        nx, ny = hip[0] + (sh[0] - hip[0]) * 0.62 + face * 4 * u, hip[1] + (sh[1] - hip[1]) * 0.62
        cv2.circle(img, (_i(nx), _i(ny)), max(2, _i(2.6 * u)), (196, 30, 36), -1, cv2.LINE_AA)
        cv2.circle(img, (_i(nx + 3 * u), _i(ny + 2 * u)), max(1, _i(1.2 * u)), (196, 30, 36), -1, cv2.LINE_AA)
    # kepala
    hr = 8.2 * u
    _limb(img, neck, neck, skin, 5 * u)
    if spec.get("hijab"):
        cv2.circle(img, (_i(head[0]), _i(head[1])), _i(hr * 1.25 + ow / 2), OUT, -1, cv2.LINE_AA)
        _poly(img, [(head[0] - hr * 1.3, head[1]), (head[0] + hr * 1.3, head[1]), (sh[0] + 10 * u, sh[1] + 7 * u),
                    (sh[0] - 10 * u, sh[1] + 7 * u)], spec["hijab"], OUT, max(1, _i(ow * 0.6)))
        cv2.circle(img, (_i(head[0]), _i(head[1])), _i(hr * 1.25), spec["hijab"], -1, cv2.LINE_AA)
        fc = (head[0] + face * 1.8 * u, head[1] + 0.6 * u)
        cv2.circle(img, (_i(fc[0]), _i(fc[1])), _i(hr * 0.8), skin, -1, cv2.LINE_AA)
    else:
        cv2.circle(img, (_i(head[0]), _i(head[1])), _i(hr + ow / 2), OUT, -1, cv2.LINE_AA)
        cv2.circle(img, (_i(head[0]), _i(head[1])), _i(hr), skin, -1, cv2.LINE_AA)
        hair = spec.get("rambut", (44, 36, 32))
        a0, a1 = (150, 335) if face > 0 else (205, 390)                    # rambut di atas & belakang, mata tetap terlihat
        cv2.ellipse(img, (_i(head[0] - face * 0.8 * u), _i(head[1] - 1.2 * u)), (_i(hr * 1.02), _i(hr * 0.92)), 0, a0, a1, hair, -1, cv2.LINE_AA)
        cv2.circle(img, (_i(head[0] - face * 0.4 * hr), _i(head[1] + 0.5 * u)), max(1, _i(2.0 * u)), darker(skin, 0.86), -1, cv2.LINE_AA)
        if spec.get("peci"):
            pc = spec["peci"] if isinstance(spec["peci"], tuple) else (34, 34, 38)
            cv2.rectangle(img, (_i(head[0] - hr * 0.95), _i(head[1] - hr * 1.18)), (_i(head[0] + hr * 0.95), _i(head[1] - hr * 0.42)), pc, -1, cv2.LINE_AA)
            cv2.ellipse(img, (_i(head[0]), _i(head[1] - hr * 1.18)), (_i(hr * 0.95), _i(hr * 0.22)), 0, 0, 360, pc, -1, cv2.LINE_AA)
        elif spec.get("cap"):
            cv2.ellipse(img, (_i(head[0]), _i(head[1] - 2 * u)), (_i(hr * 1.02), _i(hr * 0.9)), 0, 180, 360, spec["cap"], -1, cv2.LINE_AA)
    # mata (berkedip) + mulut + pipi
    ex, ey = head[0] + face * 4.2 * u, head[1] - 0.8 * u
    blink = ((t + ph * 1.7) % 3.6) < 0.12
    if blink:
        cv2.line(img, (_i(ex - 1.3 * u), _i(ey)), (_i(ex + 1.3 * u), _i(ey)), (30, 26, 24), max(1, _i(0.7 * u)), cv2.LINE_AA)
    else:
        cv2.circle(img, (_i(ex), _i(ey)), max(1, _i(1.15 * u)), (30, 26, 24), -1, cv2.LINE_AA)
    mx, my = head[0] + face * 4.6 * u, head[1] + 3.6 * u
    if aksi in ("bicara", "ngobrol", "tunjuk", "tanya") and math.sin((t + ph) * 11) > 0:
        cv2.ellipse(img, (_i(mx), _i(my)), (_i(1.7 * u), _i(1.3 * u)), 0, 0, 360, (110, 40, 40), -1, cv2.LINE_AA)
    elif aksi == "kaget":
        cv2.ellipse(img, (_i(mx), _i(my)), (_i(1.4 * u), _i(1.9 * u)), 0, 0, 360, (110, 40, 40), -1, cv2.LINE_AA)
    elif aksi in ("mikir", "cek"):
        cv2.line(img, (_i(mx - 1.6 * u), _i(my)), (_i(mx + 1.4 * u), _i(my - 0.4 * u)), (90, 50, 44), max(1, _i(0.7 * u)), cv2.LINE_AA)
    else:
        cv2.ellipse(img, (_i(mx), _i(my - 0.8 * u)), (_i(1.9 * u), _i(1.4 * u)), 0, 20, 160, (90, 50, 44), max(1, _i(0.7 * u)), cv2.LINE_AA)
    cv2.circle(img, (_i(head[0] + face * 2.4 * u), _i(head[1] + 2.4 * u)), max(1, _i(1.6 * u)), _mix(skin, (232, 120, 120), 0.35), -1, cv2.LINE_AA)
    if spec.get("hat"):                                                     # caping
        hx, hy = head[0], head[1] - hr * 0.55
        _poly(img, [(hx - 17 * u, hy + 3 * u), (hx + 17 * u, hy + 3 * u), (hx, hy - 9 * u)], spec["hat"], darker(spec["hat"], 0.7), max(1, _i(u)))
    # lengan depan + alat
    e1 = _pt(sh, P["ua1"], 15 * u, face)
    h1 = _pt(e1, P["fa1"], 14 * u, face)
    tool = P["tool"]
    if tool == "cangkul":
        a = math.radians(P["tool_ang"])
        tip = (h1[0] + face * math.sin(a) * 34 * u, h1[1] + math.cos(a) * 34 * u)
        tail = (h1[0] - face * math.sin(a) * 6 * u, h1[1] - math.cos(a) * 6 * u)
        cv2.line(img, (_i(tail[0]), _i(tail[1])), (_i(tip[0]), _i(tip[1])), (140, 100, 64), max(2, _i(2.6 * u)), cv2.LINE_AA)
        bl = (tip[0] + face * math.sin(a + math.pi / 2) * 9 * u, tip[1] + math.cos(a + math.pi / 2) * 9 * u)
        cv2.line(img, (_i(tip[0]), _i(tip[1])), (_i(bl[0]), _i(bl[1])), (90, 92, 96), max(3, _i(5 * u)), cv2.LINE_AA)
    _chain(img, [(sh, e1, shirt, lw * 0.95), (e1, h1, arm_lo, lw * 0.8)], ow)
    if gamis:
        cv2.circle(img, (_i(h1[0]), _i(h1[1])), max(1, _i(2.6 * u)), skin, -1, cv2.LINE_AA)
    if tool == "bibit":
        bx, by = h1[0] + face * 2 * u, h1[1]
        cv2.line(img, (_i(bx), _i(by + 4 * u)), (_i(bx), _i(by - 16 * u)), (90, 140, 60), max(2, _i(1.6 * u)), cv2.LINE_AA)
        for k, (dx, dy) in enumerate(((-5, -12), (5, -9), (-4, -6), (4, -16))):
            cv2.ellipse(img, (_i(bx + dx * u), _i(by + dy * u)), (_i(3.4 * u), _i(1.8 * u)), 30 if dx > 0 else -30, 0, 360, LEAF, -1, cv2.LINE_AA)
        cv2.ellipse(img, (_i(bx), _i(by + 6 * u)), (_i(4 * u), _i(3 * u)), 0, 0, 360, (110, 80, 56), -1, cv2.LINE_AA)
    elif tool == "jeriken":
        for hp in (h1, h2):
            x0, y0 = hp[0] - 5 * u, hp[1] + 1 * u
            cv2.rectangle(img, (_i(x0), _i(y0)), (_i(x0 + 10 * u), _i(y0 + 13 * u)), (70, 140, 210), -1, cv2.LINE_AA)
            cv2.rectangle(img, (_i(x0 + 3 * u), _i(y0 - 2 * u)), (_i(x0 + 7 * u), _i(y0)), (40, 90, 160), -1)
    elif tool == "mangkuk":
        px, py = (h1[0] + h2[0]) / 2, (h1[1] + h2[1]) / 2
        bowl(img, px, py + 4 * u, 13 * u, wet=True)
    elif tool == "piala":
        px, py = (h1[0] + h2[0]) / 2, min(h1[1], h2[1]) - 6 * u
        cv2.ellipse(img, (_i(px), _i(py)), (_i(6 * u), _i(7 * u)), 0, 0, 360, (240, 190, 60), -1, cv2.LINE_AA)
        cv2.rectangle(img, (_i(px - 1.5 * u), _i(py + 6 * u)), (_i(px + 1.5 * u), _i(py + 10 * u)), (210, 160, 50), -1)
        cv2.rectangle(img, (_i(px - 5 * u), _i(py + 10 * u)), (_i(px + 5 * u), _i(py + 12 * u)), (140, 100, 60), -1)
    elif tool == "buku":                                                    # kitab terbuka di tangan
        px, py = (h1[0] + h2[0]) / 2 + face * 2 * u, min(h1[1], h2[1]) - 2 * u
        bc = spec.get("buku", (46, 120, 80))
        _poly(img, [(px - 9 * u, py - 5 * u), (px, py - 2 * u), (px + 9 * u, py - 5 * u), (px + 9 * u, py + 4 * u), (px, py + 6 * u),
                    (px - 9 * u, py + 4 * u)], bc, OUT, max(1, _i(0.8 * u)))
        _poly(img, [(px - 7.5 * u, py - 4 * u), (px, py - 1.2 * u), (px + 7.5 * u, py - 4 * u), (px + 7.5 * u, py + 2.6 * u), (px, py + 4.6 * u),
                    (px - 7.5 * u, py + 2.6 * u)], (250, 246, 232))
        for k in range(3):
            yy = py - 1.5 * u + k * 1.8 * u
            cv2.line(img, (_i(px - 6 * u), _i(yy - 1.2 * u)), (_i(px - 1.5 * u), _i(yy)), (170, 160, 140), 1, cv2.LINE_AA)
            cv2.line(img, (_i(px + 1.5 * u), _i(yy)), (_i(px + 6 * u), _i(yy - 1.2 * u)), (170, 160, 140), 1, cv2.LINE_AA)
    if emote:
        _emote(img, head, hr, aksi, t + ph, face, u, (h1, h2))
    return head


@functools.lru_cache(maxsize=16)
def _glyph(ch, size, col):
    f = _font(FONT_B, size)
    im = Image.new("RGBA", (size + 24, size + 34), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((12, 4), ch, font=f, fill=col + (255,), stroke_width=max(3, size // 10), stroke_fill=(255, 255, 255, 255))
    return _to_np(im)


def _emote(img, head, hr, aksi, t, face, u, hands):
    """Ekspresi di atas kepala: ? mikir, ! kaget, gelombang suara bicara, PLAK tepuk, kilau lega."""
    hx, hy = head[0], head[1] - hr * 1.6
    if aksi == "mikir" or aksi == "cek":
        for k in range(3):                                                  # titik-titik pikiran
            ph = (t * 0.8 + k * 0.33) % 1.0
            cv2.circle(img, (_i(hx + face * (6 + k * 5) * u), _i(hy - k * 4 * u)), max(2, _i((0.9 + k * 0.5) * u)), (255, 255, 255), -1, cv2.LINE_AA)
        if aksi == "mikir":
            bob = math.sin(t * 3.0) * 2 * u
            blit(img, _glyph("?", 74, (240, 150, 40)), hx + face * 24 * u, hy - 18 * u + bob, scale=max(0.5, u / 3.6),
                 alpha=0.6 + 0.4 * abs(math.sin(t * 2)))
    elif aksi == "kaget":
        blit(img, _glyph("!", 80, (226, 60, 50)), hx + face * 14 * u, hy - 14 * u - abs(math.sin(t * 7)) * 3 * u, scale=max(0.5, u / 3.6))
        for k in range(5):                                                  # garis kejut
            a = math.radians(-150 + k * 30)
            r0, r1 = hr * 1.7, hr * 2.4 + abs(math.sin(t * 9)) * 2 * u
            cv2.line(img, (_i(head[0] + math.cos(a) * r0), _i(head[1] + math.sin(a) * r0)),
                     (_i(head[0] + math.cos(a) * r1), _i(head[1] + math.sin(a) * r1)), (60, 50, 46), max(2, _i(0.9 * u)), cv2.LINE_AA)
        dx = head[0] - face * hr * 1.1                                       # tetes keringat
        cv2.ellipse(img, (_i(dx), _i(head[1] - hr * 0.2 + (t * 20 % 6) * u)), (_i(1.6 * u), _i(2.4 * u)), 0, 0, 360, (130, 200, 240), -1, cv2.LINE_AA)
    elif aksi in ("bicara", "ngobrol", "tunjuk"):
        for k in range(3):
            ph = (t * 1.6 + k / 3.0) % 1.0
            r = (4 + ph * 9) * u
            col = _mix((255, 255, 255), (200, 200, 200), ph)
            cv2.ellipse(img, (_i(head[0] + face * hr * 1.2), _i(head[1] + 2 * u)), (_i(r), _i(r)), 0, -40 if face > 0 else 140,
                        40 if face > 0 else 220, col, max(1, _i(0.9 * u * (1 - ph) + 0.4)), cv2.LINE_AA)
    elif aksi == "tepuk":
        c = (t % 1.1) / 1.1
        if c < 0.3:
            k = 1 - c / 0.3
            px, py = (hands[0][0] + hands[1][0]) / 2, (hands[0][1] + hands[1][1]) / 2
            for j in range(8):
                a = j * math.pi / 4 + 0.3
                r0, r1 = 5 * u, (8 + 8 * (1 - k)) * u
                cv2.line(img, (_i(px + math.cos(a) * r0), _i(py + math.sin(a) * r0)), (_i(px + math.cos(a) * r1), _i(py + math.sin(a) * r1)),
                         (250, 210, 70), max(2, _i(1.1 * u)), cv2.LINE_AA)
    elif aksi in ("lega", "bangga"):
        for k in range(4):
            ph = (t * 0.7 + k / 4.0) % 1.0
            a = k * 1.6 + t * 0.5
            sx, sy = hx + math.cos(a) * 16 * u, hy - ph * 14 * u
            s = (1.0 - abs(ph - 0.5) * 2) * 3.2 * u
            if s > 0.5:
                _sparkle(img, sx, sy, s, (255, 220, 90))
    elif aksi == "tanya":
        blit(img, _glyph("?", 64, (80, 150, 230)), hx + face * 18 * u, hy - 16 * u + math.sin(t * 3) * 2 * u, scale=max(0.5, u / 3.6))


def _sparkle(img, x, y, s, col):
    pts = [(x, y - s * 2.2), (x + s * 0.5, y - s * 0.5), (x + s * 2.2, y), (x + s * 0.5, y + s * 0.5), (x, y + s * 2.2),
           (x - s * 0.5, y + s * 0.5), (x - s * 2.2, y), (x - s * 0.5, y - s * 0.5)]
    _poly(img, pts, col)


def cat(img, x, y, h, t, face=1, tidur=False, col=(226, 150, 80)):
    """Kucing oranye. tidur=True: meringkuk, ekor mengibas pelan."""
    u = h / 100.0
    dark = tuple(int(v * 0.75) for v in col)
    _shade(img, x, y + 2 * u, 40 * u, 6 * u, 0.7)
    if tidur:
        cv2.ellipse(img, (_i(x), _i(y - 16 * u)), (_i(38 * u), _i(18 * u)), 0, 180, 360, col, -1, cv2.LINE_AA)
        cv2.rectangle(img, (_i(x - 38 * u), _i(y - 17 * u)), (_i(x + 38 * u), _i(y)), col, -1)
        for k in range(3):
            cv2.line(img, (_i(x - 10 * u + k * 12 * u), _i(y - 32 * u)), (_i(x - 14 * u + k * 12 * u), _i(y - 20 * u)), dark, max(1, _i(2.4 * u)), cv2.LINE_AA)
        hx, hy = x + face * 32 * u, y - 14 * u
        cv2.circle(img, (_i(hx), _i(hy)), _i(14 * u), col, -1, cv2.LINE_AA)
        for s_ in (-1, 1):
            _poly(img, [(hx + s_ * 4 * u, hy - 10 * u), (hx + s_ * 13 * u, hy - 8 * u), (hx + s_ * 10 * u, hy - 22 * u)], col)
        cv2.ellipse(img, (_i(hx + face * 3 * u), _i(hy)), (_i(3 * u), _i(1.2 * u)), 0, 0, 180, (40, 30, 26), max(1, _i(1.2 * u)), cv2.LINE_AA)
        sw = math.sin(t * 1.4) * 0.5
        tx = x - face * 38 * u
        pts = [(tx - face * (12 * k) * u, y - 3 * u - 10 * math.sin(k * 0.7 + sw) * u) for k in range(5)]
        cv2.polylines(img, [np.array([(_i(a), _i(b)) for a, b in pts], np.int32)], False, col, max(2, _i(6 * u)), cv2.LINE_AA)
        zz = (t * 0.5) % 1.0                                               # "z" tidur
        cv2.putText(img, "z", (_i(hx + 10 * u), _i(hy - 26 * u - zz * 20 * u)), cv2.FONT_HERSHEY_SIMPLEX, 0.9 * u / 2.0 + 0.4, (90, 90, 120), 2, cv2.LINE_AA)
        return
    b = math.sin(t * 6.0)
    body = (x, y - 30 * u)
    for k, dx in enumerate((-22, -12, 14, 24)):
        sw = (8 if k % 2 == 0 else -8) * b
        _limb(img, (body[0] + face * dx * u, body[1]), (body[0] + face * (dx + sw * 0.5) * u, y), dark if k in (0, 2) else col, 6 * u)
    cv2.ellipse(img, (_i(body[0]), _i(body[1])), (_i(32 * u), _i(13 * u)), 0, 0, 360, col, -1, cv2.LINE_AA)
    hx, hy = body[0] + face * 34 * u, body[1] - 12 * u
    cv2.circle(img, (_i(hx), _i(hy)), _i(13 * u), col, -1, cv2.LINE_AA)
    for s_ in (-1, 1):
        _poly(img, [(hx + s_ * 4 * u, hy - 9 * u), (hx + s_ * 12 * u, hy - 7 * u), (hx + s_ * 9 * u, hy - 20 * u)], col)
    cv2.circle(img, (_i(hx + face * 5 * u), _i(hy - 2 * u)), max(1, _i(1.8 * u)), (40, 30, 26), -1, cv2.LINE_AA)
    a = math.sin(t * 3.0) * 0.4
    tx, ty = body[0] - face * 30 * u, body[1] - 4 * u
    cv2.line(img, (_i(tx), _i(ty)), (_i(tx - face * 16 * u), _i(ty - (26 + 8 * a) * u)), col, max(2, _i(5 * u)), cv2.LINE_AA)


def gecko(img, x, y, s, t, ang=0.0, col=(120, 116, 84)):
    """Cicak merayap (tampak atas). ang = arah kepala (derajat, 0 = kanan)."""
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    P = lambda fx, fy: (x + (fx * ca - fy * sa) * s, y + (fx * sa + fy * ca) * s)
    w = math.sin(t * 8.0)
    tail = [P(-22 - k * 9, 6 * math.sin(k * 0.8 + t * 3)) for k in range(6)]
    cv2.polylines(img, [np.array([(_i(px), _i(py)) for px, py in tail], np.int32)], False, col, max(2, _i(4 * s)), cv2.LINE_AA)
    for fx, side in ((12, 1), (12, -1), (-14, 1), (-14, -1)):                 # kaki
        k = w if (fx > 0) == (side > 0) else -w
        p0 = P(fx, 0)
        p1 = P(fx + 6 * k, side * 14)
        cv2.line(img, (_i(p0[0]), _i(p0[1])), (_i(p1[0]), _i(p1[1])), col, max(1, _i(2.4 * s)), cv2.LINE_AA)
        cv2.circle(img, (_i(p1[0]), _i(p1[1])), max(1, _i(2.2 * s)), col, -1, cv2.LINE_AA)
    c = P(0, 0)
    cv2.ellipse(img, (_i(c[0]), _i(c[1])), (_i(22 * s), _i(7 * s)), ang, 0, 360, col, -1, cv2.LINE_AA)
    h = P(26, 0)
    cv2.ellipse(img, (_i(h[0]), _i(h[1])), (_i(9 * s), _i(6 * s)), ang, 0, 360, col, -1, cv2.LINE_AA)
    for side in (-1, 1):
        e = P(28, side * 4)
        cv2.circle(img, (_i(e[0]), _i(e[1])), max(1, _i(1.4 * s)), (30, 26, 24), -1, cv2.LINE_AA)


def droppings(img, x, y, s, n=3, seed=0):
    """Kotoran cicak kering: butir gelap dengan ujung putih."""
    r = _rng("tahi", seed)
    for k in range(n):
        px, py = x + r.uniform(-40, 40) * s, y + r.uniform(-14, 14) * s
        ang = r.uniform(0, 180)
        cv2.ellipse(img, (_i(px), _i(py)), (_i(7 * s), _i(3 * s)), ang, 0, 360, (54, 44, 38), -1, cv2.LINE_AA)
        cv2.circle(img, (_i(px + math.cos(math.radians(ang)) * 6 * s), _i(py + math.sin(math.radians(ang)) * 6 * s)),
                   max(1, _i(2.4 * s)), (244, 244, 236), -1, cv2.LINE_AA)


def dust_puff(img, x, y, t, s=1.0, col=(150, 128, 104)):
    """Kepulan debu berulang (tangan menepuk tembok/tanah)."""
    for k in range(10):
        ph = (t * 0.9 + k / 10.0) % 1.0
        a = k * 2.4
        px, py = x + math.cos(a) * 60 * ph * s, y + math.sin(a) * 40 * ph * s - 30 * ph * s
        r = (4 + 10 * ph) * s
        cv2.circle(img, (_i(px), _i(py)), max(1, _i(r)), _mix(col, (230, 220, 205), ph * 0.7), -1 if ph < 0.55 else 3, cv2.LINE_AA)


def chicken(img, x, y, h, t, face=1, col=(250, 246, 236)):
    u = h / 100.0
    peck = max(0.0, math.sin(t * 2.3)) ** 6
    _shade(img, x, y + 1 * u, 24 * u, 4 * u, 0.72)
    for dx in (-5, 5):
        cv2.line(img, (_i(x + dx * u), _i(y - 22 * u)), (_i(x + dx * u), _i(y)), (220, 150, 50), max(1, _i(2.4 * u)), cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y - 34 * u)), (_i(24 * u), _i(17 * u)), 0, 0, 360, col, -1, cv2.LINE_AA)
    _poly(img, [(x - face * 18 * u, y - 40 * u), (x - face * 34 * u, y - 60 * u), (x - face * 28 * u, y - 36 * u)], (200, 120, 70))
    hx, hy = x + face * (22 + 10 * peck) * u, y - (54 - 34 * peck) * u
    _limb(img, (x + face * 14 * u, y - 40 * u), (hx, hy), col, 11 * u)
    cv2.circle(img, (_i(hx), _i(hy)), _i(8 * u), col, -1, cv2.LINE_AA)
    _poly(img, [(hx - 3 * u, hy - 7 * u), (hx + 3 * u, hy - 12 * u), (hx + 5 * u, hy - 6 * u)], (220, 50, 50))
    _poly(img, [(hx + face * 7 * u, hy - 1 * u), (hx + face * 14 * u, hy + 1 * u), (hx + face * 7 * u, hy + 3 * u)], (240, 170, 50))
    cv2.circle(img, (_i(hx + face * 3 * u), _i(hy - 2 * u)), max(1, _i(1.3 * u)), (30, 26, 24), -1, cv2.LINE_AA)


def bird(img, x, y, s, t, col=(60, 60, 70)):
    f = math.sin(t * 9.0)
    cv2.line(img, (_i(x - 14 * s), _i(y - 6 * s * f)), (_i(x), _i(y)), col, max(1, _i(2.2 * s)), cv2.LINE_AA)
    cv2.line(img, (_i(x), _i(y)), (_i(x + 14 * s), _i(y - 6 * s * f)), col, max(1, _i(2.2 * s)), cv2.LINE_AA)


def butterfly(img, x, y, s, t, col=(250, 180, 60)):
    f = 0.3 + 0.7 * abs(math.sin(t * 12.0))
    for sd in (-1, 1):
        cv2.ellipse(img, (_i(x + sd * 6 * s * f), _i(y - 3 * s)), (_i(6 * s * f + 1), _i(7 * s)), sd * 20, 0, 360, col, -1, cv2.LINE_AA)
        cv2.ellipse(img, (_i(x + sd * 4 * s * f), _i(y + 5 * s)), (_i(4 * s * f + 1), _i(4 * s)), 0, 0, 360, _mix(col, (255, 255, 255), 0.3), -1, cv2.LINE_AA)
    cv2.line(img, (_i(x), _i(y - 7 * s)), (_i(x), _i(y + 8 * s)), (50, 40, 36), max(1, _i(1.5 * s)), cv2.LINE_AA)


def steam(img, x, y, s, t):
    for k in range(3):
        ph = (t * 0.5 + k / 3.0) % 1.0
        pts = [(x + (k - 1) * 8 * s + 6 * s * math.sin(ph * 6 + j * 0.8 + k), y - ph * 60 * s - j * 9 * s) for j in range(5)]
        a = 1.0 - ph
        col = _mix((210, 205, 200), (255, 255, 255), ph)
        if a > 0.15:
            cv2.polylines(img, [np.array([(_i(px), _i(py)) for px, py in pts], np.int32)], False, col, max(1, _i(3 * s * a)), cv2.LINE_AA)


def bucket(img, x, y, s, col=(70, 140, 210), gayung=True):
    _shade(img, x, y + 3 * s, 46 * s, 8 * s, 0.7)
    _poly(img, [(x - 40 * s, y - 70 * s), (x + 40 * s, y - 70 * s), (x + 32 * s, y), (x - 32 * s, y)], col, OUT, max(1, _i(2 * s)))
    cv2.ellipse(img, (_i(x), _i(y - 70 * s)), (_i(40 * s), _i(10 * s)), 0, 0, 360, tuple(int(v * 0.7) for v in col), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y - 68 * s)), (_i(34 * s), _i(7 * s)), 0, 0, 360, WATER, -1, cv2.LINE_AA)
    if gayung:
        cv2.line(img, (_i(x + 6 * s), _i(y - 74 * s)), (_i(x + 44 * s), _i(y - 104 * s)), (230, 90, 70), max(2, _i(6 * s)), cv2.LINE_AA)
        cv2.ellipse(img, (_i(x - 6 * s), _i(y - 74 * s)), (_i(16 * s), _i(7 * s)), 0, 0, 360, (240, 110, 90), -1, cv2.LINE_AA)



def goat(img, x, y, h, t, face=1, col=(240, 236, 228)):
    u = h / 100.0
    b = math.sin(t * 5.0)
    body = (x, y - 52 * u + abs(b) * 2 * u)
    for k, dx in enumerate((-22, -14, 16, 24)):
        sw = (10 if k % 2 == 0 else -10) * b
        top = (body[0] + face * dx * u, body[1] + 10 * u)
        foot = (top[0] + face * sw * 0.6 * u, y)
        _limb(img, top, foot, (150, 140, 130) if k in (0, 2) else (190, 182, 172), 4.5 * u)
    cv2.ellipse(img, (_i(body[0]), _i(body[1])), (_i(34 * u), _i(18 * u)), 0, 0, 360, col, -1, cv2.LINE_AA)
    hx, hy = body[0] + face * 38 * u, body[1] - 16 * u
    _limb(img, (body[0] + face * 26 * u, body[1] - 6 * u), (hx, hy), col, 11 * u)
    cv2.ellipse(img, (_i(hx + face * 6 * u), _i(hy + 2 * u)), (_i(11 * u), _i(7 * u)), face * 25, 0, 360, col, -1, cv2.LINE_AA)
    cv2.line(img, (_i(hx - face * 2 * u), _i(hy - 6 * u)), (_i(hx - face * 9 * u), _i(hy - 16 * u)), (120, 104, 86), max(1, _i(2.4 * u)), cv2.LINE_AA)
    cv2.circle(img, (_i(hx + face * 6 * u), _i(hy)), max(1, _i(1.4 * u)), (30, 26, 24), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(body[0] - face * 34 * u), _i(body[1] - 10 * u)), (_i(4 * u), _i(7 * u)), face * -30, 0, 360, col, -1, cv2.LINE_AA)


def bowl(img, x, y, r, wet=False):
    """Mangkuk: (x, y) = tengah bibir mangkuk, r = jari-jari."""
    cv2.ellipse(img, (_i(x), _i(y)), (_i(r), _i(r * 0.62)), 0, 0, 180, (90, 130, 170), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y)), (_i(r), _i(r * 0.3)), 0, 0, 360, (210, 226, 236), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y + r * 0.02)), (_i(r * 0.82), _i(r * 0.22)), 0, 0, 360, (150, 196, 226) if wet else (178, 196, 206), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y)), (_i(r), _i(r * 0.3)), 0, 0, 360, (70, 100, 130), max(1, _i(r * 0.06)), cv2.LINE_AA)


def dog(img, x, y, h, t, face=1, lick=False, col=(196, 150, 96)):
    """Anjing datar. (x, y) = kaki; lick=True -> kepala menunduk menjilat (lidah bergerak)."""
    u = h / 100.0
    dark = tuple(int(v * 0.72) for v in col)
    body = (x, y - 48 * u)
    for k, dx in enumerate((-26, -16, 18, 28)):
        top = (body[0] + face * dx * u, body[1] + 8 * u)
        _limb(img, top, (top[0], y), dark if k in (0, 2) else col, 7 * u)
    wag = math.sin(t * 12.0) * 22
    tail0 = (body[0] - face * 34 * u, body[1] - 8 * u)
    a = math.radians(-50 + wag)
    _limb(img, tail0, (tail0[0] - face * math.cos(a) * 26 * u, tail0[1] + math.sin(a) * 26 * u), col, 5 * u)
    cv2.ellipse(img, (_i(body[0]), _i(body[1])), (_i(38 * u), _i(17 * u)), 0, 0, 360, col, -1, cv2.LINE_AA)
    if lick:
        nod = 3 * math.sin(t * 9.0)
        hx, hy = body[0] + face * 46 * u, body[1] + 20 * u + nod * u
    else:
        hx, hy = body[0] + face * 40 * u, body[1] - 22 * u
    _limb(img, (body[0] + face * 26 * u, body[1] - 4 * u), (hx, hy), col, 16 * u)
    cv2.circle(img, (_i(hx), _i(hy)), _i(13 * u), col, -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(hx + face * 13 * u), _i(hy + 4 * u)), (_i(10 * u), _i(7 * u)), 0, 0, 360, col, -1, cv2.LINE_AA)
    cv2.circle(img, (_i(hx + face * 22 * u), _i(hy + 2 * u)), max(1, _i(3 * u)), (40, 30, 26), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(hx - face * 6 * u), _i(hy - 6 * u)), (_i(6 * u), _i(12 * u)), face * 20, 0, 360, dark, -1, cv2.LINE_AA)
    cv2.circle(img, (_i(hx + face * 4 * u), _i(hy - 3 * u)), max(1, _i(2 * u)), (30, 24, 20), -1, cv2.LINE_AA)
    if lick:
        L = (6 + 5 * abs(math.sin(t * 9.0))) * u
        cv2.ellipse(img, (_i(hx + face * 18 * u), _i(hy + 10 * u + L / 2)), (_i(4 * u), _i(L / 2 + 2 * u)), 0, 0, 360, (232, 120, 140), -1, cv2.LINE_AA)


def mosquito(img, x, y, s, t):
    """Nyamuk kecil terbang (sayap berkedip)."""
    flap = abs(math.sin(t * 40.0))
    for side in (-1, 1):
        cv2.ellipse(img, (_i(x + side * 6 * s), _i(y - 8 * s)), (_i(9 * s), _i((3 + 5 * flap) * s)), side * 30, 0, 360,
                    (226, 236, 244), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y)), (_i(11 * s), _i(4 * s)), 15, 0, 360, (50, 46, 44), -1, cv2.LINE_AA)
    cv2.circle(img, (_i(x + 11 * s), _i(y - 3 * s)), _i(3.4 * s), (50, 46, 44), -1, cv2.LINE_AA)
    cv2.line(img, (_i(x + 13 * s), _i(y - 3 * s)), (_i(x + 22 * s), _i(y + 2 * s)), (50, 46, 44), max(1, _i(1.2 * s)), cv2.LINE_AA)
    for k in range(3):
        cv2.line(img, (_i(x - 2 * s + k * 4 * s), _i(y + 2 * s)), (_i(x - 6 * s + k * 6 * s), _i(y + 12 * s)), (50, 46, 44), 1, cv2.LINE_AA)


def soil_pile(img, x, y, s):
    cv2.ellipse(img, (_i(x), _i(y)), (_i(60 * s), _i(16 * s)), 0, 0, 360, (200, 200, 196), -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y - 4 * s)), (_i(44 * s), _i(26 * s)), 0, 180, 360, (130, 92, 60), -1, cv2.LINE_AA)
    for k in range(7):
        cv2.circle(img, (_i(x - 30 * s + k * 10 * s), _i(y - 8 * s - (k % 3) * 5 * s)), max(1, _i(3 * s)), (100, 70, 46), -1, cv2.LINE_AA)


def tree(img, x, y, s, k=1.0, kind=0):
    """Pohon beringin/ficus datar. s = skala (tinggi ≈ 160*s), k = pertumbuhan 0..1."""
    if k <= 0.02:
        return
    s = s * (0.25 + 0.75 * _ease(k))
    th = 70 * s
    cv2.line(img, (_i(x), _i(y)), (_i(x), _i(y - th)), TRUNK, max(2, _i(9 * s)), cv2.LINE_AA)
    if s > 0.5:                                                            # akar gantung khas beringin
        for dx in (-22, -8, 12, 26):
            cv2.line(img, (_i(x + dx * s), _i(y - th - 6 * s)), (_i(x + dx * s), _i(y - th * 0.45)), (150, 120, 90), max(1, _i(1.6 * s)), cv2.LINE_AA)
    cy = y - th - 22 * s
    blobs = ((-34, 6, 30), (30, 8, 30), (0, -14, 38), (-18, -30, 24), (20, -28, 26), (0, 10, 30))
    for dx, dy, r in blobs:
        cv2.circle(img, (_i(x + dx * s), _i(cy + dy * s + 5 * s)), _i(r * s), LEAF_D, -1, cv2.LINE_AA)
    for dx, dy, r in blobs:
        cv2.circle(img, (_i(x + dx * s - 3 * s), _i(cy + dy * s)), _i(r * s * 0.92), LEAF if kind % 3 else (98, 166, 88), -1, cv2.LINE_AA)
    for dx, dy, r in blobs[:3]:
        cv2.circle(img, (_i(x + dx * s - 9 * s), _i(cy + dy * s - 9 * s)), _i(r * s * 0.42), LEAF_L, -1, cv2.LINE_AA)


def sapling(img, x, y, s):
    cv2.line(img, (_i(x), _i(y)), (_i(x), _i(y - 40 * s)), (110, 140, 70), max(1, _i(3 * s)), cv2.LINE_AA)
    for dx, dy in ((-8, -30), (8, -24), (-7, -18), (7, -38)):
        cv2.ellipse(img, (_i(x + dx * s), _i(y + dy * s)), (_i(7 * s), _i(3.4 * s)), 30 if dx > 0 else -30, 0, 360, LEAF, -1, cv2.LINE_AA)
    cv2.ellipse(img, (_i(x), _i(y)), (_i(14 * s), _i(5 * s)), 0, 0, 360, (150, 110, 74), -1, cv2.LINE_AA)


def house(img, x, y, s, flip=False):
    w, h = 190 * s, 110 * s
    cv2.rectangle(img, (_i(x - w / 2), _i(y - h)), (_i(x + w / 2), _i(y)), WALL, -1, cv2.LINE_AA)
    cv2.rectangle(img, (_i(x - w / 2), _i(y - 18 * s)), (_i(x + w / 2), _i(y)), (214, 204, 186), -1)
    _poly(img, [(x - w / 2 - 22 * s, y - h), (x + w / 2 + 22 * s, y - h), (x + w / 2 - 20 * s, y - h - 70 * s), (x - w / 2 + 20 * s, y - h - 70 * s)], ROOF)
    _poly(img, [(x - w / 2 - 22 * s, y - h), (x + w / 2 + 22 * s, y - h), (x + w / 2 + 22 * s, y - h + 8 * s), (x - w / 2 - 22 * s, y - h + 8 * s)], ROOF_D)
    dx = -40 if flip else 40
    cv2.rectangle(img, (_i(x + dx * s - 16 * s), _i(y - 76 * s)), (_i(x + dx * s + 16 * s), _i(y)), (140, 96, 64), -1)
    cv2.rectangle(img, (_i(x - dx * s - 22 * s), _i(y - 80 * s)), (_i(x - dx * s + 22 * s), _i(y - 44 * s)), (90, 110, 120), -1)
    cv2.rectangle(img, (_i(x - dx * s - 22 * s), _i(y - 80 * s)), (_i(x - dx * s + 22 * s), _i(y - 44 * s)), (140, 96, 64), max(1, _i(3 * s)))


# ------------------------------------------------------------------ latar statis (di-cache per proses)
def _cracks(img, y0, y1, col, seed, cell=70):
    r = _rng("crack", seed)
    pts = []
    for y in range(y0, y1 + cell, cell):
        sc = 0.55 + 0.9 * (y - y0) / max(1, y1 - y0)
        for x in range(-cell, W + cell, int(cell * sc * 1.4)):
            pts.append((x + r.uniform(-22, 22) * sc, y + r.uniform(-14, 14)))
    sub = cv2.Subdiv2D((-200, y0 - 200, W + 400, (y1 - y0) + 600))
    for p in pts:
        try:
            sub.insert((float(p[0]), float(p[1])))
        except cv2.error:
            pass
    facets, _ = sub.getVoronoiFacetList([])
    keep = img[:y0].copy()
    for f in facets:
        poly = np.array(f, np.int32)
        cv2.polylines(img, [poly], True, col, 2, cv2.LINE_AA)
    img[:y0] = keep


def _hill_curve(x):
    return 860 + 260 * (1 - math.exp(-((x - 600) / 380.0) ** 2)) - 40 * math.sin(x / 160.0) * 0.3


@functools.lru_cache(maxsize=24)
def backdrop(latar, green, fire=False, malam=False):
    """Latar statis: green = 0 (kering) / 1 (hijau). Dikembalikan uint8 HxWx3."""
    img = np.zeros((H, W, 3), np.uint8)
    if latar == "irisan":
        _gradient(img, 0, 600, (172, 200, 216), (214, 222, 220))
        top = 600
        _gradient(img, top, top + 70, GRASS if green else HILL_DRY, GRASS_D if green else HILL_DRY_D)
        _gradient(img, top + 70, 1080, (118, 84, 60), (96, 68, 50))
        _gradient(img, 1080, 1560, (150, 148, 140), (120, 118, 112))
        _gradient(img, 1560, H, (86, 140, 196), (52, 96, 150))
        r = _rng("ir", green)
        for _ in range(140):
            x, y = r.uniform(0, W), r.uniform(top + 80, 1070)
            cv2.circle(img, (_i(x), _i(y)), _i(r.uniform(2, 6)), (140, 104, 76), -1, cv2.LINE_AA)
        for _ in range(26):                                                 # celah batu
            x, y = r.uniform(0, W), r.uniform(1090, 1540)
            pts = [(x, y)]
            for k in range(5):
                x, y = x + r.uniform(-40, 40), y + r.uniform(10, 50)
                pts.append((x, y))
            cv2.polylines(img, [np.array(pts, np.int32)], False, (96, 94, 88), 3, cv2.LINE_AA)
        if not green:                                                       # kerak tanah gundul
            cv2.rectangle(img, (0, top), (W, top + 18), (186, 150, 106), -1)
        return img
    if latar in ("teras", "cuci", "kitab", "wc", "musholla"):
        return _indoor(latar, malam)
    if fire:
        _gradient(img, 0, HORIZON, SKY_FIRE_T, SKY_FIRE_B)
        img[HORIZON:] = SKY_FIRE_B
    else:
        _gradient(img, 0, HORIZON, SKY_T, SKY_B)
        img[HORIZON:] = SKY_B
    r = _rng(latar, green)
    if latar in ("bukit", "api", "desa"):
        # gunung jauh (Lawu)
        pts = [(0, 820)] + [(x, 600 + 210 * abs(math.sin((x - 520) / 900.0 * math.pi)) + 12 * math.sin(x / 37.0)) for x in range(0, W + 20, 20)] + [(W, 820)]
        _poly(img, pts + [(W, HORIZON), (0, HORIZON)], _mix(MOUNT, SKY_B, 0.25))
        for i in range(4):                                                  # awan
            cx, cy = r.uniform(80, 1000), r.uniform(160, 460)
            for k in range(4):
                cv2.ellipse(img, (_i(cx + k * 46 - 70), _i(cy - (k % 2) * 16)), (60, 30), 0, 0, 360, _mix(SKY_B, (255, 255, 255), 0.6) if not fire else (190, 140, 130), -1, cv2.LINE_AA)
    ground_top = HORIZON
    if latar in ("bukit", "api"):
        col, cold = (GRASS, GRASS_D) if green else (HILL_DRY, HILL_DRY_D)
        hill = [(x, _hill_curve(x)) for x in range(-20, W + 40, 20)]
        _poly(img, hill + [(W + 20, 1260), (-20, 1260)], col)
        for k in range(40):                                                 # alur erosi / rumput
            x = r.uniform(80, 1000)
            y = _hill_curve(x) + r.uniform(20, 200)
            if green:
                cv2.ellipse(img, (_i(x), _i(y)), (_i(r.uniform(14, 30)), 6), 0, 180, 360, cold, -1, cv2.LINE_AA)
            else:
                cv2.line(img, (_i(x), _i(y)), (_i(x + r.uniform(-30, 30)), _i(y + r.uniform(40, 110))), cold, 3, cv2.LINE_AA)
        ground_top = 1180
    elif latar == "desa":
        hill = [(x, 960 + 40 * math.sin(x / 210.0)) for x in range(-20, W + 40, 20)]
        _poly(img, hill + [(W + 20, 1300), (-20, 1300)], GRASS_D if green else HILL_DRY)
        ground_top = 1060
    elif latar == "sawah":
        _gradient(img, 0, 420, SKY_T, SKY_B)
        ground_top = 420
    elif latar == "mata_air":
        ground_top = 0
    # tanah depan
    gcol = (GRASS, GRASS_L) if green else (DRY, DRY_L)
    _gradient(img, ground_top, H, gcol[0], gcol[1])
    if latar == "sawah":
        for row in range(9):
            y0 = 440 + row * row * 19 + row * 40
            y1 = 440 + (row + 1) * (row + 1) * 19 + (row + 1) * 40
            n = 4 + (8 - row) // 2
            for c in range(-1, n + 1):
                x0, x1 = c * W / n + (row % 2) * 40, (c + 1) * W / n + (row % 2) * 40
                colp = (150, 196, 98) if green else (196, 170, 120)
                if green and (c + row) % 3 == 0:
                    colp = (224, 196, 92)
                _poly(img, [(x0 + 6, y0 + 4), (x1 - 6, y0 + 4), (x1 - 6, y1 - 4), (x0 + 6, y1 - 4)], colp)
                if green:
                    for k in range(int((x1 - x0) / 18)):
                        xx = x0 + 10 + k * 18
                        cv2.line(img, (_i(xx), _i(y0 + 8)), (_i(xx), _i(y1 - 8)), _mix(colp, (90, 140, 60), 0.35), 1, cv2.LINE_AA)
            cv2.line(img, (0, _i(y1)), (W, _i(y1)), (120, 150, 80) if green else (170, 140, 96), 5, cv2.LINE_AA)
    elif latar == "mata_air":
        _gradient(img, 0, 900, (120, 150, 104) if green else (176, 150, 112), (150, 176, 120) if green else (200, 172, 128))
        cv2.rectangle(img, (0, 300), (W, 1000), (96, 92, 84), -1)
        for row in range(9):                                                # dinding batu tak beraturan
            x = -60 + r.uniform(0, 60)
            while x < W + 80:
                rx, ry = r.uniform(48, 86), r.uniform(30, 44)
                y = 330 + row * 76 + r.uniform(-6, 6)
                tone = r.uniform(-14, 14)
                base = tuple(int(min(255, max(0, v + tone))) for v in STONE)
                cv2.ellipse(img, (_i(x), _i(y + 4)), (_i(rx), _i(ry)), r.uniform(-8, 8), 0, 360, STONE_D, -1, cv2.LINE_AA)
                cv2.ellipse(img, (_i(x - 3), _i(y - 2)), (_i(rx - 6), _i(ry - 5)), r.uniform(-8, 8), 0, 360, base, -1, cv2.LINE_AA)
                cv2.ellipse(img, (_i(x - rx * 0.3), _i(y - ry * 0.35)), (_i(rx * 0.35), _i(ry * 0.22)), 0, 0, 360,
                            tuple(min(255, v + 18) for v in base), -1, cv2.LINE_AA)
                if green and r.rand() < 0.45:
                    cv2.ellipse(img, (_i(x - 6), _i(y - ry + 6)), (_i(rx * 0.6), 10), 0, 180, 360, (104, 148, 84), -1, cv2.LINE_AA)
                x += rx * 1.75
        _gradient(img, 0, 300, (120, 160, 100) if green else (196, 166, 120), (100, 140, 84) if green else (180, 150, 106))
        if green:
            for k in range(7):
                tree(img, 80 + k * 160 + r.uniform(-30, 30), 300, 1.1 + r.uniform(0, 0.4), 1.0, k)
        _gradient(img, 1000, H, (184, 160, 120) if not green else (130, 150, 110), (210, 188, 146) if not green else (150, 170, 120))
        cv2.ellipse(img, (540, 1330), (420, 150), 0, 0, 360, STONE_D, -1, cv2.LINE_AA)
        if green:                                                           # kolam
            cv2.ellipse(img, (540, 1330), (380, 120), 0, 0, 360, WATER_D, -1, cv2.LINE_AA)
            cv2.ellipse(img, (530, 1318), (350, 100), 0, 0, 360, WATER, -1, cv2.LINE_AA)
        else:
            cv2.ellipse(img, (540, 1330), (380, 120), 0, 0, 360, (170, 150, 120), -1, cv2.LINE_AA)
        # pipa bambu
        cv2.line(img, (100, 760), (470, 820), (150, 140, 70), 34, cv2.LINE_AA)
        cv2.line(img, (100, 752), (470, 812), (196, 184, 100), 14, cv2.LINE_AA)
        cv2.ellipse(img, (472, 822), (12, 18), -10, 0, 360, (110, 100, 50), -1, cv2.LINE_AA)
    elif green and latar != "irisan":
        for k in range(160):
            x, y = r.uniform(0, W), r.uniform(ground_top + 20, H)
            s = 0.6 + 0.8 * (y - ground_top) / (H - ground_top)
            cv2.ellipse(img, (_i(x), _i(y)), (_i(16 * s), _i(5 * s)), 0, 180, 360, GRASS_D, -1, cv2.LINE_AA)
    elif latar != "irisan":
        _cracks(img, ground_top + 40, H, DRY_D, latar)
        for k in range(30):
            x, y = r.uniform(0, W), r.uniform(ground_top + 40, H)
            cv2.ellipse(img, (_i(x), _i(y)), (_i(r.uniform(10, 26)), _i(r.uniform(5, 10))), 0, 0, 360, (150, 140, 128), -1, cv2.LINE_AA)
    return img


def _indoor(latar, malam=False):
    img = _indoor_base(latar)
    _props(img, latar, malam)
    return img


def _indoor_base(latar):
    img = np.zeros((H, W, 3), np.uint8)
    r = _rng(latar)
    if latar == "teras":                                                   # depan rumah: dinding, pintu, jendela, lantai ubin
        _gradient(img, 0, 1240, (236, 226, 204), (222, 210, 186))
        cv2.rectangle(img, (0, 0), (W, 140), (150, 64, 46), -1)
        for x in range(0, W, 60):
            cv2.line(img, (x, 0), (x + 30, 140), (120, 48, 34), 3, cv2.LINE_AA)
        cv2.rectangle(img, (110, 520), (390, 1240), (128, 86, 58), -1)            # pintu
        cv2.rectangle(img, (130, 540), (370, 870), (110, 72, 48), 6)
        cv2.rectangle(img, (130, 900), (370, 1220), (110, 72, 48), 6)
        cv2.circle(img, (340, 900), 10, (230, 190, 90), -1, cv2.LINE_AA)
        cv2.rectangle(img, (560, 560), (960, 900), (120, 160, 180), -1)           # jendela
        cv2.rectangle(img, (560, 560), (960, 900), (128, 86, 58), 16)
        cv2.line(img, (760, 560), (760, 900), (128, 86, 58), 10)
        cv2.line(img, (560, 730), (960, 730), (128, 86, 58), 10)
        for k in range(3):
            cv2.line(img, (600 + k * 120, 600), (640 + k * 120, 680), (200, 226, 236), 6, cv2.LINE_AA)
        _gradient(img, 1240, H, (196, 170, 140), (214, 190, 160))               # lantai ubin
        for k in range(12):
            y = 1240 + k * k * 6 + k * 18
            cv2.line(img, (0, y), (W, y), (170, 144, 116), 2, cv2.LINE_AA)
        for k in range(-8, 18):
            cv2.line(img, (540 + k * 60, 1240), (540 + k * 190, H), (170, 144, 116), 2, cv2.LINE_AA)
        cv2.rectangle(img, (0, 1226), (W, 1246), (176, 150, 120), -1)
        for x in (470, 1000):                                                # pot tanaman
            _poly(img, [(x - 46, 1180), (x + 46, 1180), (x + 34, 1250), (x - 34, 1250)], (190, 100, 70))
            for k in range(6):
                cv2.ellipse(img, (x - 30 + k * 12, 1150 - (k % 2) * 30), (14, 44), -30 + k * 12, 0, 360, LEAF_D if k % 2 else LEAF, -1, cv2.LINE_AA)
    elif latar == "cuci":                                                  # tempat cuci: dinding keramik, keran, bak, lantai semen
        _gradient(img, 0, 1180, (222, 234, 238), (206, 220, 226))
        for y in range(0, 1180, 90):
            cv2.line(img, (0, y), (W, y), (186, 204, 212), 3)
        for x in range(0, W, 90):
            cv2.line(img, (x, 0), (x, 1180), (186, 204, 212), 3)
        _gradient(img, 1180, H, (170, 172, 168), (190, 192, 188))
        cv2.rectangle(img, (0, 1170), (W, 1196), (150, 152, 148), -1)
        cv2.line(img, (300, 0), (300, 820), (150, 156, 164), 26, cv2.LINE_AA)
        cv2.line(img, (300, 820), (400, 820), (150, 156, 164), 26, cv2.LINE_AA)
        cv2.rectangle(img, (392, 806), (430, 860), (120, 126, 136), -1)
        cv2.rectangle(img, (296, 790), (340, 806), (196, 60, 52), -1)
        cv2.ellipse(img, (420, 1340), (230, 70), 0, 0, 360, (120, 124, 120), -1, cv2.LINE_AA)
        cv2.ellipse(img, (420, 1330), (200, 54), 0, 0, 360, WATER_D, -1, cv2.LINE_AA)
        cv2.ellipse(img, (410, 1322), (180, 42), 0, 0, 360, WATER, -1, cv2.LINE_AA)
    elif latar == "wc":                                                    # lorong toilet umum: pintu bertanda, wastafel, cermin
        _gradient(img, 0, 1240, (214, 228, 226), (198, 214, 212))
        for y in range(0, 1240, 80):
            cv2.line(img, (0, y), (W, y), (182, 200, 198), 2)
        for i, (x0, sign) in enumerate(((60, "pria"), (400, "wanita"))):
            cv2.rectangle(img, (x0, 420), (x0 + 280, 1240), (92, 128, 150), -1)
            cv2.rectangle(img, (x0 + 16, 436), (x0 + 264, 1240), (110, 150, 172), -1)
            cv2.circle(img, (x0 + 240, 860), 12, (230, 200, 110), -1, cv2.LINE_AA)
            cx, cy = x0 + 140, 560
            cv2.rectangle(img, (cx - 60, cy - 80), (cx + 60, cy + 80), (250, 250, 246), -1)
            cv2.circle(img, (cx, cy - 42), 16, (60, 70, 80), -1, cv2.LINE_AA)
            if sign == "pria":
                cv2.rectangle(img, (cx - 20, cy - 22), (cx + 20, cy + 30), (60, 70, 80), -1)
                cv2.rectangle(img, (cx - 18, cy + 30), (cx - 4, cy + 64), (60, 70, 80), -1)
                cv2.rectangle(img, (cx + 4, cy + 30), (cx + 18, cy + 64), (60, 70, 80), -1)
            else:
                _poly(img, [(cx - 30, cy + 40), (cx + 30, cy + 40), (cx + 14, cy - 22), (cx - 14, cy - 22)], (60, 70, 80))
                cv2.rectangle(img, (cx - 14, cy + 40), (cx - 4, cy + 64), (60, 70, 80), -1)
                cv2.rectangle(img, (cx + 4, cy + 40), (cx + 14, cy + 64), (60, 70, 80), -1)
        cv2.rectangle(img, (760, 520), (1020, 820), (200, 222, 230), -1)          # cermin
        cv2.rectangle(img, (760, 520), (1020, 820), (150, 160, 166), 10)
        cv2.line(img, (800, 560), (860, 660), (236, 244, 248), 8, cv2.LINE_AA)
        cv2.rectangle(img, (740, 900), (1040, 950), (236, 238, 238), -1)          # wastafel
        cv2.ellipse(img, (890, 950), (130, 40), 0, 0, 180, (220, 224, 226), -1, cv2.LINE_AA)
        cv2.line(img, (890, 900), (890, 860), (150, 156, 164), 12, cv2.LINE_AA)
        _gradient(img, 1240, H, (176, 186, 186), (196, 204, 204))
        for k in range(10):
            y = 1240 + k * k * 7 + k * 20
            cv2.line(img, (0, y), (W, y), (156, 166, 166), 2, cv2.LINE_AA)
        cv2.rectangle(img, (0, 1226), (W, 1246), (150, 160, 160), -1)
    elif latar == "musholla":                                              # musholla: dinding, jendela lengkung, karpet sajadah
        _gradient(img, 0, 1180, (238, 232, 216), (226, 218, 198))
        for x0 in (120, 620):
            cv2.rectangle(img, (x0, 420), (x0 + 340, 900), (120, 168, 186), -1)
            cv2.ellipse(img, (x0 + 170, 420), (170, 170), 0, 180, 360, (120, 168, 186), -1, cv2.LINE_AA)
            cv2.rectangle(img, (x0, 420), (x0 + 340, 900), (150, 120, 80), 14)
            cv2.ellipse(img, (x0 + 170, 420), (170, 170), 0, 180, 360, (150, 120, 80), 14, cv2.LINE_AA)
            cv2.line(img, (x0 + 170, 260), (x0 + 170, 900), (150, 120, 80), 8)
        cv2.rectangle(img, (0, 1000), (W, 1030), (180, 150, 110), -1)
        _gradient(img, 1180, H, (70, 120, 90), (60, 106, 80))                   # karpet hijau bergaris shaf
        for k in range(8):
            y = 1180 + k * k * 8 + k * 30
            cv2.line(img, (0, y), (W, y), (214, 190, 110), 4, cv2.LINE_AA)
        cv2.rectangle(img, (0, 1166), (W, 1186), (140, 110, 74), -1)
    else:                                                                  # kitab: rak buku + meja kayu + kitab terbuka
        _gradient(img, 0, 1240, (232, 222, 200), (214, 202, 178))
        for row in range(4):
            y0 = 160 + row * 230
            cv2.rectangle(img, (60, y0 + 196), (W - 60, y0 + 214), (120, 84, 56), -1)
            x = 80
            while x < W - 90:
                bw = int(r.uniform(26, 50))
                bh = int(r.uniform(140, 190))
                col = [(150, 60, 50), (50, 90, 120), (60, 110, 80), (170, 130, 60), (110, 70, 110)][int(r.randint(0, 5))]
                cv2.rectangle(img, (x, y0 + 196 - bh), (x + bw, y0 + 196), col, -1)
                cv2.line(img, (x + 4, y0 + 196 - bh + 20), (x + bw - 4, y0 + 196 - bh + 20), (230, 200, 120), 3)
                x += bw + 4
        _gradient(img, 1240, H, (150, 104, 70), (128, 88, 58))
        cv2.rectangle(img, (0, 1236), (W, 1262), (110, 76, 50), -1)
        pass
    return img


NIGHT_GLASS = (30, 42, 78)


def _night_window(img, x0, y0, x1, y1, seed):
    """Kaca jendela malam: biru tua, bintang, kadang bulan sabit."""
    roi = img[y0:y1, x0:x1]
    glass = np.all(np.abs(roi.astype(np.int16) - np.array([120, 166, 184], np.int16)) < 26, axis=2) | \
        np.all(np.abs(roi.astype(np.int16) - np.array([120, 160, 180], np.int16)) < 26, axis=2)
    roi[glass] = NIGHT_GLASS
    r = _rng("bintang", seed)
    for _ in range(14):
        x, y = _i(r.uniform(x0 + 10, x1 - 10)), _i(r.uniform(y0 + 10, y1 - 10))
        if glass[min(y - y0, glass.shape[0] - 1), min(x - x0, glass.shape[1] - 1)]:
            cv2.circle(img, (x, y), int(r.uniform(1, 3)), (250, 244, 210), -1, cv2.LINE_AA)
    if seed % 2 == 0:
        mx, my = _i((x0 + x1) / 2 + 40), _i(y0 + (y1 - y0) * 0.3)
        cv2.circle(img, (mx, my), 34, (250, 238, 190), -1, cv2.LINE_AA)
        cv2.circle(img, (mx + 16, my - 8), 30, NIGHT_GLASS, -1, cv2.LINE_AA)


def _star8(img, cx, cy, r, col, line=None):
    pts = []
    for k in range(16):
        a = k * math.pi / 8
        rr = r if k % 2 == 0 else r * 0.62
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    _poly(img, pts, col, line, 3)


def _clock(img, cx, cy, r):
    cv2.circle(img, (cx, cy), r + 8, (110, 80, 54), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), r, (250, 248, 240), -1, cv2.LINE_AA)
    for k in range(12):
        a = k * math.pi / 6
        cv2.line(img, (_i(cx + math.cos(a) * r * 0.8), _i(cy + math.sin(a) * r * 0.8)), (_i(cx + math.cos(a) * r * 0.92), _i(cy + math.sin(a) * r * 0.92)),
                 (60, 56, 52), 3, cv2.LINE_AA)


def _shelf_books(img, x0, x1, y_base, h0, h1, seed, cols=None):
    r = _rng("rak", seed)
    cols = cols or [(46, 120, 80), (30, 96, 64), (150, 60, 50), (190, 150, 60), (50, 90, 120)]
    x = x0
    while x < x1 - 20:
        bw = int(r.uniform(16, 30))
        bh = int(r.uniform(h0, h1))
        col = cols[int(r.randint(0, len(cols)))]
        cv2.rectangle(img, (x, y_base - bh), (x + bw, y_base), col, -1)
        cv2.line(img, (x + 3, y_base - bh + 12), (x + bw - 3, y_base - bh + 12), (230, 200, 120), 2)
        x += bw + 3


def _props(img, latar, malam):
    """Properti statis tambahan supaya ruangan terasa 'hidup' (di-cache bersama latar)."""
    if latar == "musholla":
        if malam:
            for x0 in (120, 620):
                _night_window(img, x0, 250, x0 + 340, 900, x0)
        _clock(img, 540, 330, 46)
        cv2.rectangle(img, (478, 470), (602, 800), (150, 112, 60), -1)                   # bingkai ornamen geometris (tanpa tulisan)
        cv2.rectangle(img, (490, 482), (590, 788), (36, 86, 64), -1)
        for k, cy in enumerate((540, 635, 730)):
            _star8(img, 540, cy, 34, (222, 186, 96))
            _star8(img, 540, cy, 16, (36, 86, 64))
        cv2.rectangle(img, (690, 1040), (1010, 1168), (128, 90, 58), -1)                 # rak Al-Qur'an
        cv2.rectangle(img, (690, 1100), (1010, 1110), (100, 70, 44), -1)
        _shelf_books(img, 700, 1000, 1098, 40, 54, 1, [(30, 96, 64), (46, 120, 80), (40, 70, 110)])
        _shelf_books(img, 700, 1000, 1164, 38, 50, 2, [(30, 96, 64), (190, 150, 60), (46, 120, 80)])
        for k, x in enumerate((90, 150)):                                                 # sandal di tepi karpet
            cv2.ellipse(img, (x, 1196), (22, 8), 0, 0, 360, (60, 70, 90) if k else (150, 70, 60), -1, cv2.LINE_AA)
    elif latar == "teras":
        if malam:
            _night_window(img, 560, 560, 960, 900, 4)
        cv2.rectangle(img, (420, 640), (450, 700), (60, 56, 52), -1)                    # lampu dinding
        cv2.ellipse(img, (435, 712), (26, 16), 0, 0, 360, (250, 236, 180), -1, cv2.LINE_AA)
        x0 = 640                                                                           # kursi kayu + meja kecil
        cv2.rectangle(img, (x0, 980), (x0 + 16, 1240), (120, 80, 52), -1)
        cv2.rectangle(img, (x0 + 150, 980), (x0 + 166, 1240), (120, 80, 52), -1)
        cv2.rectangle(img, (x0 - 6, 1110), (x0 + 172, 1130), (140, 96, 62), -1)
        for k in range(4):
            cv2.rectangle(img, (x0 + 4, 990 + k * 28), (x0 + 162, 1002 + k * 28), (150, 104, 68), -1)
        cv2.rectangle(img, (x0 + 196, 1110), (x0 + 300, 1126), (140, 96, 62), -1)
        cv2.rectangle(img, (x0 + 206, 1126), (x0 + 218, 1240), (120, 80, 52), -1)
        cv2.rectangle(img, (x0 + 278, 1126), (x0 + 290, 1240), (120, 80, 52), -1)
        cv2.rectangle(img, (x0 + 226, 1084), (x0 + 254, 1110), (250, 250, 246), -1)           # cangkir
        cv2.ellipse(img, (x0 + 256, 1096), (8, 10), 0, -90, 90, (250, 250, 246), 4, cv2.LINE_AA)
        cv2.rectangle(img, (150, 1250), (350, 1290), (170, 70, 60), -1)                  # keset + sandal
        for k, x in enumerate((185, 245, 300)):
            cv2.ellipse(img, (x, 1300 + (k % 2) * 6), (24, 9), 0, 0, 360, [(60, 70, 90), (210, 120, 60), (60, 70, 90)][k], -1, cv2.LINE_AA)
    elif latar == "wc":
        cv2.rectangle(img, (740, 440), (1040, 500), (46, 120, 80), -1)                  # papan tanda
        cv2.putText(img, "JAGA KEBERSIHAN", (756, 482), cv2.FONT_HERSHEY_SIMPLEX, 0.92, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.rectangle(img, (1000, 600), (1040, 660), (236, 236, 236), -1)               # kotak tisu
        cv2.rectangle(img, (1008, 586), (1032, 604), (250, 250, 250), -1)
        _poly(img, [(700, 1150), (750, 1150), (742, 1240), (708, 1240)], (110, 120, 130))  # tempat sampah
        cv2.rectangle(img, (696, 1140), (754, 1152), (90, 100, 110), -1)
        for x in (110, 470):                                                               # keset di depan pintu
            cv2.rectangle(img, (x, 1252), (x + 200, 1274), (90, 110, 140), -1)
    elif latar == "cuci":
        cv2.rectangle(img, (560, 180), (980, 520), (120, 166, 184), -1)                  # jendela
        cv2.rectangle(img, (560, 180), (980, 520), (210, 214, 216), 14)
        cv2.line(img, (770, 180), (770, 520), (210, 214, 216), 10)
        if malam:
            _night_window(img, 560, 180, 980, 520, 2)
        cv2.rectangle(img, (600, 640), (960, 660), (150, 156, 164), -1)                  # rak piring
        cv2.rectangle(img, (600, 800), (960, 820), (150, 156, 164), -1)
        for k in range(7):
            cx = 630 + k * 48
            cv2.ellipse(img, (cx, 730), (16, 64), 0, 0, 360, [(240, 240, 236), (230, 220, 180), (200, 226, 236)][k % 3], -1, cv2.LINE_AA)
            cv2.ellipse(img, (cx, 730), (16, 64), 0, 0, 360, (170, 176, 180), 2, cv2.LINE_AA)
        for k in range(3):                                                                 # gelas
            cv2.rectangle(img, (640 + k * 70, 580), (680 + k * 70, 640), (200, 226, 236), -1)
        cv2.rectangle(img, (520, 1100), (560, 1170), (240, 120, 60), -1)                 # sabun & spons
        cv2.rectangle(img, (530, 1084), (550, 1100), (250, 250, 250), -1)
        cv2.rectangle(img, (580, 1146), (650, 1170), (240, 210, 60), -1)
        cv2.rectangle(img, (580, 1158), (650, 1170), (60, 160, 90), -1)


@functools.lru_cache(maxsize=24)
def light_layer(latar, malam):
    """Sinar cahaya (god rays) per latar, uint8 untuk ditambahkan ke kanvas."""
    L = np.zeros((H, W, 3), np.uint8)
    warm = (120, 96, 52) if not malam else (40, 50, 80)
    if latar == "musholla":
        for x0 in (120, 620):
            _poly(L, [(x0 + 20, 300), (x0 + 320, 300), (x0 + 560, 1720), (x0 + 160, 1720)], warm)
    elif latar == "teras":
        _poly(L, [(0, 0), (380, 0), (900, 1900), (380, 1900)], warm)
        _poly(L, [(520, 0), (700, 0), (1080, 1300), (1080, 1700)], tuple(int(v * 0.6) for v in warm))
    elif latar == "cuci":
        _poly(L, [(580, 200), (960, 200), (900, 1600), (420, 1600)], warm)
    elif latar == "kitab":
        _poly(L, [(0, 0), (300, 0), (760, 1500), (360, 1500)], tuple(int(v * 0.7) for v in warm))
    elif latar in ("bukit", "desa", "sawah", "mata_air", "api"):
        for k in range(5):
            a0 = math.radians(100 + k * 14)
            a1 = a0 + math.radians(5)
            cx, cy = 980, -80
            _poly(L, [(cx, cy), (cx + math.cos(a0) * 2600, cy + math.sin(a0) * 2600), (cx + math.cos(a1) * 2600, cy + math.sin(a1) * 2600)],
                  (90, 80, 50))
    else:
        return None
    L = cv2.GaussianBlur(L, (0, 0), 38)
    return L


@functools.lru_cache(maxsize=2)
def vignette(strength=0.30):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.46) / (H * 0.6)) ** 2)
    v = 1.0 - strength * np.clip(d - 0.55, 0, 1) ** 1.4 / (0.45 ** 1.4)
    v = np.clip(v, 1 - strength, 1)
    return cv2.merge([(v * 255).astype(np.uint8)] * 3)


@functools.lru_cache(maxsize=4)
def fg_leaves(kind=0):
    """Dedaunan blur di depan kamera (parallax), RGBA."""
    im = np.zeros((520, 520, 4), np.uint8)
    r = _rng("daun", kind)
    for k in range(9):
        cx, cy = r.uniform(40, 300), r.uniform(40, 300)
        ang = r.uniform(0, 180)
        col = [LEAF_D, LEAF, (70, 130, 64)][k % 3]
        cv2.ellipse(im, (_i(cx), _i(cy)), (_i(r.uniform(60, 120)), _i(r.uniform(22, 36))), ang, 0, 360, col + (255,), -1, cv2.LINE_AA)
    im = cv2.GaussianBlur(im, (0, 0), 7)
    return im


@functools.lru_cache(maxsize=16)
def hill_spots(n=70, seed=3):
    r = _rng("spots", seed)
    out = []
    for k in range(n):
        x = r.uniform(60, 1020)
        top = _hill_curve(x)
        y = r.uniform(top + 20, 1170)
        out.append((x, y, r.rand()))
    out.sort(key=lambda p: p[2])                                           # urutan tumbuh
    return out


# ------------------------------------------------------------------ aktor: adegan
class KisahA:
    """Melukis seluruh layar: latar + kehidupan + tokoh + kamera."""

    def __init__(self, shot, dur, speech, seed):
        self.s, self.dur, self.speech, self.seed = shot, dur, speech, seed
        hj = shot.get("hijau", 0)
        self.h0, self.h1 = (hj, hj) if not isinstance(hj, (list, tuple)) else (hj[0], hj[1])
        self.latar = shot.get("latar", "bukit")

    def green(self, t):
        a, b = self.speech
        return self.h0 + (self.h1 - self.h0) * _ease((t - a) / max(0.5, (b - a)))

    INDOOR = ("teras", "cuci", "kitab", "wc", "musholla")

    def draw(self, img, t, ctx):
        s = self.s
        g = self.green(t)
        lat = self.latar
        fire = lat == "api"
        malam = bool(s.get("malam")) and lat in self.INDOOR
        fx = s.get("efek", True)
        dry = backdrop(lat, False, fire, malam)
        if g <= 0.01 or fire:
            canvas = dry.copy()
        elif g >= 0.99:
            canvas = backdrop(lat, True, False, malam).copy()
        else:
            canvas = cv2.addWeighted(dry, 1 - _ease(min(1, g * 1.6)), backdrop(lat, True, False, malam), _ease(min(1, g * 1.6)), 0)
        tg = ctx["tg"]
        var = s.get("_wajah")
        if var and var != lat:                                              # variasi latar (aw_latar)
            vb = AL.base(var, malam)
            if vb is not None:
                canvas = vb.copy()
                AL.life(var, canvas, t, tg, fx)
            else:
                var = None
        if fx and lat not in self.INDOOR:
            self._sky_life(canvas, t, g, tg)
        if lat in ("bukit", "api"):
            self._hill(canvas, t, g, tg)
        elif lat == "desa":
            self._desa(canvas, t, g, tg)
        elif lat == "mata_air":
            self._spring(canvas, t, g, tg)
        elif lat == "sawah":
            self._sawah(canvas, t, g, tg)
        elif lat == "irisan":
            self._section(canvas, t, g, tg)
        elif lat in ("teras", "cuci", "kitab", "wc", "musholla"):
            self._indoor(canvas, t, tg)
        if s.get("hujan"):
            self._rain(canvas, tg)
        if fx:
            L = light_layer(lat, malam) if not s.get("hujan") and var != "pesantren" else None
            if L is not None:                                               # sinar cahaya berdenyut pelan
                a = (0.55 if lat in self.INDOOR else 0.35) * (0.85 + 0.15 * math.sin(tg * 0.9))
                cv2.addWeighted(canvas, 1.0, L, a, 0, canvas)
                self._motes(canvas, tg, lat)
            if malam:
                self._lamp_glow(canvas, tg)
        lfx = fx and s.get("_latar_fx", True)
        if lfx:                                                             # bintang nur + bokeh jauh (aw_aura)
            AU.bg_under(canvas, t, tg, lat, malam, self.seed, lat in self.INDOOR)
        out = self._camera(canvas, t)
        if fx:
            if lat in ("teras", "bukit", "desa", "sawah", "mata_air") and s.get("daun", True):
                p = _ease(t / max(1.0, self.dur))                          # daun dekat kamera bergerak lebih cepat
                blit(out, fg_leaves(0), 110 - 70 * p, 120 + 20 * math.sin(tg * 0.7), scale=1.25, alpha=0.95)
            if malam:
                out = cv2.addWeighted(out, 0.86, np.full_like(out, (24, 30, 70)), 0.14, 0)
            out = cv2.multiply(out, vignette(), scale=1 / 255.0)
        if lfx:                                                             # sapuan kilau, light leak, gelombang kartu, grain
            AU.bg_over(out, t, tg, self.dur, lat, malam, self.seed, s.get("_hits") or (), s.get("_hitpos") or (),
                       lat in self.INDOOR)
        img[:] = out
        return None

    # ---- efek
    def _motes(self, c, tg, lat):
        """Debu/serbuk cahaya melayang di jalur sinar."""
        n = 26 if lat in self.INDOOR else 14
        for k in range(n):
            ph = (tg * (0.025 + 0.01 * (k % 4)) + k * 0.137) % 1.0
            x = (k * 211.3 + 40 * math.sin(tg * 0.4 + k)) % W
            y = 260 + ph * 1400
            tw = 0.5 + 0.5 * math.sin(tg * 2.0 + k * 1.7)
            col = (255, 248, 220) if not self.s.get("malam") else (200, 210, 255)
            cv2.circle(c, (_i(x), _i(y)), 2 + (k % 3), _mix(tuple(int(v) for v in c[min(H - 1, _i(y)), min(W - 1, _i(x))]), col, 0.35 + 0.45 * tw),
                       -1, cv2.LINE_AA)

    def _lamp_glow(self, c, tg):
        for (x, y) in self._lamps():
            ov = c.copy()
            r = _i(150 + 8 * math.sin(tg * 3.1 + x))
            cv2.circle(ov, (_i(x), _i(y)), r, (255, 220, 140), -1, cv2.LINE_AA)
            cv2.addWeighted(ov, 0.16, c, 0.84, 0, c)

    def _lamps(self):
        return {"musholla": [(300, 236), (800, 236)], "teras": [(435, 712)], "cuci": [(300, 120)], "kitab": [(633, 1320)], "wc": [(540, 90)]}.get(self.latar, [])

    def _sky_life(self, c, t, g, tg):
        """Luar ruangan: awan berarak, kawanan burung, kupu-kupu (bila hijau)."""
        if self.latar not in ("mata_air",):
            for k in range(2):
                cx = (k * 560 + tg * 14) % (W + 400) - 200
                cy = 220 + k * 160
                for j in range(4):
                    cv2.ellipse(c, (_i(cx + j * 52 - 80), _i(cy - (j % 2) * 18)), (66, 32), 0, 0, 360, (246, 246, 242), -1, cv2.LINE_AA)
            for k in range(5):                                              # kawanan burung
                ph = (tg * 0.06 + 0.3) % 1.0
                bx = -120 + ph * (W + 240) - (k % 3) * 46
                by = 420 + (k // 3) * 30 + (k % 3) * 22 + 10 * math.sin(tg * 1.3 + k)
                bird(c, bx, by, 1.4, tg + k * 0.3)
        if g > 0.3:
            for k in range(3):
                bx = 120 + k * 220 + 70 * math.sin(tg * 0.9 + k * 2)
                by = 1300 + k * 90 + 40 * math.sin(tg * 1.7 + k)
                butterfly(c, bx, by, 2.0, tg + k, [(250, 180, 60), (250, 250, 250), (240, 120, 150)][k])

    # ---- isi latar
    def _actors(self, c, t, tg, y, scale=1.0):
        s = self.s
        aksi = s.get("aksi")
        if aksi:
            x = s.get("x", 360)
            face = s.get("hadap", 1)
            if aksi in ("jalan", "angkut", "pikul"):
                x = x + face * 60 * (t - 0.0) * scale
            person(c, x, y, 340 * scale, FARMER, aksi, tg, face)
            if s.get("kambing"):
                goat(c, x - face * 190 * scale, y + 6, 150 * scale, tg if aksi in ("jalan",) else 0, face)
            if aksi == "tanam":
                sapling(c, x + face * 100 * scale, y + 2, 1.6 * scale)
        w = s.get("warga")
        if w:
            n = 2 if w != "antri" else 3
            for k in range(n):
                spec = VILLAGERS[k % len(VILLAGERS)]
                wx = s.get("wx", 760) + k * 120
                wy = y - 40 + k * 18
                wa = {"angkut": "angkut", "tunjuk": "tunjuk", "antri": "angkut", "jalan": "jalan"}.get(w, "diam")
                if w == "tunjuk" and k == 1:
                    wa = "diam"
                face = -1 if w != "angkut" else 1
                xx = wx + (face * 50 * t if wa in ("angkut", "jalan") else 0)
                person(c, xx, wy, 290 * scale, spec, wa, tg, face, ph=k * 0.7)

    def _crowd(self, c, t, tg):
        """Figuran & properti bergerak di belakang tokoh utama (matikan dengan shot["ramai"] = false)."""
        s = self.s
        lat = self.latar
        fx = s.get("efek", True)
        tok_x = [o.get("x", 300) for o in (s.get("tokoh") or [])]
        free = lambda x, d=170: all(abs(x - q) > d for q in tok_x)
        if lat == "musholla":
            for x in (300, 800):                                             # lampu gantung berayun
                a = math.radians(3 * math.sin(tg * 1.1 + x))
                lx, ly = x + math.sin(a) * 200, math.cos(a) * 200
                cv2.line(c, (x, 0), (_i(lx), _i(ly)), (90, 80, 70), 3, cv2.LINE_AA)
                _poly(c, [(lx - 44, ly + 40), (lx + 44, ly + 40), (lx + 20, ly), (lx - 20, ly)], (214, 170, 80), OUT, 2)
                cv2.ellipse(c, (_i(lx), _i(ly + 44)), (30, 12), 0, 0, 360, (255, 244, 200), -1, cv2.LINE_AA)
            if s.get("ramai", True):
                jm = [dict(shirt=(236, 236, 228), pants=(60, 64, 76), skin=(196, 142, 100), hat=None, peci=True, sarung=(70, 96, 130)),
                      dict(shirt=(120, 170, 140), pants=(60, 64, 76), skin=(186, 132, 92), hat=None, peci=True, sarung=(130, 80, 70)),
                      dict(shirt=(200, 210, 230), pants=(60, 64, 76), skin=(204, 150, 110), hat=None, peci=True, sarung=(60, 110, 90))]
                for k, x in enumerate((540, 660, 780)):                      # shaf belakang: jamaah sholat serempak
                    person(c, x, 1300, 230, jm[k], "sholat_gerak", tg + 1.5, 1, ph=0.06 * k, emote=False)
        elif lat == "wc":
            fl = 0.75 + 0.25 * (1 if (tg * 7.3) % 5.1 > 0.25 else 0)          # lampu neon sedikit berkedip
            cv2.rectangle(c, (340, 56), (740, 84), _mix((180, 180, 170), (255, 255, 240), fl), -1)
            cv2.rectangle(c, (330, 48), (750, 56), (150, 156, 160), -1)
            for k in range(4):                                              # tetes air wastafel
                ph = (tg * 0.9 + k / 4.0) % 1.0
                cv2.circle(c, (890, _i(904 + ph * 40)), 4, WATER, -1, cv2.LINE_AA)
            bucket(c, 690, 1318, 0.9)
            for k in range(3):                                              # genangan berkilau
                ph = (tg * 0.5 + k / 3.0) % 1.0
                cv2.ellipse(c, (640, 1470), (_i(40 + 120 * ph), _i(8 + 20 * ph)), 0, 0, 360, _mix((220, 236, 240), (176, 186, 186), ph), 2, cv2.LINE_AA)
            if s.get("ramai", True):                                         # orang lewat di belakang
                per = 12.0
                ph = ((tg + 3.0) % per) / per
                if ph < 0.75:
                    x = 1180 - ph / 0.75 * 1360
                    sp = dict(shirt=(200, 150, 80), pants=(60, 64, 76), skin=(190, 136, 96), hat=None)
                    person(c, x, 1330, 330, sp, "jalan", tg, -1, emote=False)
        elif lat == "teras":
            a = math.radians(5 * math.sin(tg * 1.4))                        # sangkar burung berayun
            bx, by = 520 + math.sin(a) * 200, 140 + math.cos(a) * 200
            cv2.line(c, (520, 140), (_i(bx), _i(by)), (90, 80, 70), 3, cv2.LINE_AA)
            cv2.ellipse(c, (_i(bx), _i(by + 70)), (56, 70), 0, 180, 360, (170, 130, 70), 3, cv2.LINE_AA)
            for k in range(-2, 3):
                cv2.line(c, (_i(bx + k * 22), _i(by + 10 + abs(k) * 6)), (_i(bx + k * 24), _i(by + 70)), (170, 130, 70), 2, cv2.LINE_AA)
            cv2.rectangle(c, (_i(bx - 60), _i(by + 70)), (_i(bx + 60), _i(by + 80)), (150, 110, 60), -1)
            hop = abs(math.sin(tg * 4.0)) * 10
            cv2.ellipse(c, (_i(bx), _i(by + 56 - hop)), (16, 12), 0, 0, 360, (250, 210, 60), -1, cv2.LINE_AA)
            cv2.circle(c, (_i(bx + 12), _i(by + 46 - hop)), 8, (250, 210, 60), -1, cv2.LINE_AA)
            cv2.circle(c, (_i(bx + 14), _i(by + 44 - hop)), 2, (30, 26, 24), -1, cv2.LINE_AA)
            steam(c, 880, 1084, 0.8, tg)
            if s.get("ramai", True):
                if free(600) and not s.get("anjing"):
                    cat(c, 600, 1330, 90, tg, 1, tidur=True)
                for k, (px, py) in enumerate(((470, 1100), (1000, 1080))):
                    butterfly(c, px + 50 * math.sin(tg * 0.8 + k * 3), py + 40 * math.sin(tg * 1.3 + k), 1.8, tg + k, [(250, 180, 60), (240, 120, 150)][k])
        elif lat == "cuci":
            a = math.radians(4 * math.sin(tg * 1.2))                        # handuk berayun
            cv2.circle(c, (1000, 880), 8, (120, 126, 136), -1, cv2.LINE_AA)
            _poly(c, [(970, 884), (1030, 884), (1030 + math.sin(a) * 240, 884 + 240), (970 + math.sin(a) * 240, 884 + 240)], (226, 110, 110), OUT, 2)
            for k in range(3):
                yy = 960 + k * 50
                cv2.line(c, (_i(972 + math.sin(a) * (yy - 884)), yy), (_i(1028 + math.sin(a) * (yy - 884)), yy), (250, 230, 230), 4, cv2.LINE_AA)
            if not s.get("busa"):
                for j in range(6):
                    ph = (tg * 0.25 + j / 6.0) % 1.0
                    cv2.circle(c, (_i(250 + j * 60 + 20 * math.sin(tg + j)), _i(1300 - ph * 500)), _i(6 + (j % 3) * 4), (236, 246, 252), 2, cv2.LINE_AA)
        elif lat == "kitab":
            var = [("baca", "dengar", None), ("tanya", "dengar", "guru"), ("baca", "baca", None), ("dengar", "ngobrol", "guru"),
                   ("dengar", "baca", None)][self.seed % 5]
            guru = var[2] and not s.get("_hadits")                           # pengajar: orang biasa masa kini, bukan tokoh riwayat
            slots = [(160, var[0], (236, 236, 228)), (380 if guru else 420, var[1], (120, 170, 140))]
            if s.get("ramai", True):
                for k, (x, aks, baju) in enumerate(slots):
                    if free(x):
                        sp = dict(shirt=baju, pants=(60, 64, 76), skin=(196, 142, 100) if k else (186, 132, 92), hat=None, peci=True,
                                  sarung=(70, 96, 130))
                        person(c, x, 1560, 380, sp, aks, tg, 1, ph=k * 1.3, emote=aks == "tanya")
                if guru and free(640, 140):
                    sp = dict(shirt=(250, 250, 246), pants=(60, 64, 76), skin=(190, 136, 96), hat=None, peci=(250, 250, 246),
                              sarung=(90, 70, 60), rambut=(200, 200, 196))
                    person(c, 650, 1560, 400, sp, "ngobrol", tg, -1, ph=0.4, emote=False)
            self._ngaji_table(c, tg, fx, lamp=not (guru and s.get("ramai", True)))

    def _ngaji_table(self, c, tg, fx, lamp=True):
        cv2.rectangle(c, (40, 1500), (760, 1530), (150, 98, 60), -1)         # meja ngaji panjang (rendah)
        cv2.rectangle(c, (40, 1530), (760, 1640), (124, 80, 50), -1)
        cv2.rectangle(c, (40, 1530), (760, 1540), (100, 64, 40), -1)
        cv2.rectangle(c, (40, 1500), (760, 1640), OUT, 3)
        for x in (80, 400, 720):
            cv2.rectangle(c, (x - 14, 1640), (x + 14, 1700), (100, 64, 40), -1)
        _shade(c, 400, 1708, 380, 16, 0.75)
        for k, (bx, col) in enumerate(((60, (150, 60, 50)), (66, (50, 90, 120)), (56, (190, 150, 60)))):  # tumpukan kitab
            cv2.rectangle(c, (bx, 1500 - 22 * (k + 1)), (bx + 110, 1500 - 22 * k), col, -1)
            cv2.line(c, (bx + 6, 1500 - 22 * k - 11), (bx + 104, 1500 - 22 * k - 11), (230, 200, 120), 2)
        if lamp:
            cv2.rectangle(c, (626, 1330), (640, 1500), (60, 60, 64), -1)     # lampu meja
            _poly(c, [(586, 1330), (680, 1330), (660, 1280), (606, 1280)], (46, 120, 80), OUT, 2)
            cv2.ellipse(c, (633, 1500), (40, 8), 0, 0, 360, (60, 60, 64), -1, cv2.LINE_AA)
        cv2.rectangle(c, (520, 1456), (560, 1500), (250, 250, 246), -1)       # gelas teh beruap
        cv2.rectangle(c, (524, 1466), (556, 1500), (200, 130, 70), -1)
        steam(c, 540, 1450, 0.7, tg)
        for k, bx in enumerate((300, 470)):                                  # kitab terbuka di atas rehal
            cv2.line(c, (bx - 40, 1500), (bx + 40, 1462), (110, 76, 50), 6, cv2.LINE_AA)
            cv2.line(c, (bx + 40, 1500), (bx - 40, 1462), (110, 76, 50), 6, cv2.LINE_AA)
            _poly(c, [(bx - 56, 1460), (bx, 1470), (bx + 56, 1460), (bx + 56, 1430), (bx, 1440), (bx - 56, 1430)], (250, 244, 226), OUT, 2)
            flip = (tg * 0.25 + k * 0.5) % 1.0                                # halaman berbalik sesekali
            if flip < 0.18:
                q = flip / 0.18
                px = bx + 52 * math.cos(math.pi * q)
                _poly(c, [(bx, 1440), (px, 1430 - 26 * math.sin(math.pi * q)), (px, 1458 - 26 * math.sin(math.pi * q)), (bx, 1470)], (255, 252, 240), OUT, 1)
            if fx:                                                          # cahaya ilmu naik dari kitab
                for j in range(5):
                    ph = (tg * 0.35 + j / 5.0 + k * 0.1) % 1.0
                    gx = bx + 30 * math.sin(tg * 1.2 + j * 1.9)
                    gy = 1430 - ph * 260
                    s_ = (1 - ph) * 3.0
                    if s_ > 0.6:
                        _sparkle(c, gx, gy, s_, (255, 226, 120))

    def _indoor(self, c, t, tg):
        s = self.s
        lat = self.latar
        self._crowd(c, t, tg)
        if lat == "teras":
            bx = s.get("mangkuk_x", 640)
            if s.get("mangkuk", True):
                bowl(c, bx, 1500, 70, wet=bool(s.get("anjing")))
            if s.get("anjing"):
                dog(c, bx - 190, 1560, 260, tg, 1, lick=True)
        elif lat == "cuci":
            a, b = self.speech
            if s.get("air", True):
                for k in range(3):
                    cv2.line(c, (411 + (k - 1) * 5, 862), (411 + (k - 1) * 5, 1300), WATER_L if k == 1 else WATER, 8 if k == 1 else 5, cv2.LINE_AA)
                for k in range(8):
                    ph = (tg * 2 + k / 8.0) % 1.0
                    cv2.circle(c, (_i(411 + math.cos(k * 2.3) * 70 * ph), _i(1300 - math.sin(math.pi * ph) * 40)), 6, WATER_L, -1, cv2.LINE_AA)
            if s.get("tanah"):
                soil_pile(c, s.get("tanah_x", 640), 1470, 1.2)
            if s.get("busa"):
                for j in range(12):
                    ph = (tg * 0.8 + j / 12.0) % 1.0
                    yy = 1520 - ph * 220
                    cv2.circle(c, (_i(330 + (j % 6) * 40 + 14 * math.sin(tg * 3 + j)), _i(yy)), _i(7 + (j % 3) * 4), (240, 248, 252), 2, cv2.LINE_AA)
        if lat == "musholla" and s.get("sajadah", True):
            for x0 in (s.get("sajadah_x", 230),):
                _poly(c, [(x0 - 120, 1700), (x0 + 120, 1700), (x0 + 96, 1430), (x0 - 96, 1430)], (150, 50, 60))
                _poly(c, [(x0 - 100, 1680), (x0 + 100, 1680), (x0 + 80, 1450), (x0 - 80, 1450)], (176, 70, 76))
                cv2.ellipse(c, (x0, 1480), (50, 40), 0, 180, 360, (214, 180, 96), 4, cv2.LINE_AA)
        if s.get("tahi"):                                                    # kotoran cicak kering (di sajadah/lantai)
            tx, ty = s.get("tahi_xy", (s.get("sajadah_x", 230) + 20, 1560))
            droppings(c, tx, ty, float(s.get("tahi_s", 1.6)), int(s.get("tahi_n", 4)))
            if s.get("tahi_tanda", True):
                k = 0.5 + 0.5 * math.sin(tg * 4)
                cv2.circle(c, (_i(tx), _i(ty)), _i(70 + 10 * k), (240, 200, 60), 3, cv2.LINE_AA)
        if s.get("cicak"):                                                   # cicak merayap di dinding
            n = int(s.get("cicak")) if not isinstance(s.get("cicak"), bool) else 1
            for k in range(n):
                per = 14.0
                ph = ((tg + k * 5.0) % per) / per
                cx0, cy0 = s.get("cicak_xy", (560, 900))
                gx = cx0 + 300 * math.sin(ph * 2 * math.pi + k) * (0.6 + 0.4 * k)
                gy = cy0 - 160 * math.cos(ph * 2 * math.pi * 0.5 + k)
                dx = math.cos(ph * 2 * math.pi + k)
                gecko(c, gx, gy, 2.7, tg + k, ang=0 if dx > 0 else 180)
        if s.get("debu"):                                                    # tangan menepuk tembok -> debu
            dx_, dy_ = s.get("debu_xy", (600, 1200))
            dust_puff(c, dx_, dy_, tg, 1.4)
        if s.get("nyamuk"):
            n = int(s.get("nyamuk")) if not isinstance(s.get("nyamuk"), bool) else 2
            for k in range(n):
                mx = s.get("nyamuk_x", 420) + 120 * math.sin(tg * 1.3 + k * 2.1) + k * 60
                my = s.get("nyamuk_y", 1050) + 70 * math.sin(tg * 2.1 + k) + k * 40
                mosquito(c, mx, my, 2.2, tg + k)
        for k, o in enumerate(s.get("tokoh") or []):
            spec = {"pria": dict(shirt=(70, 110, 170), pants=(60, 64, 76), skin=(196, 142, 100), hat=None, cap=(40, 36, 34)),
                    "wanita": dict(shirt=(214, 120, 140), pants=(90, 70, 110), skin=(204, 150, 110), hat=None, hijab=(120, 90, 160)),
                    "anak": dict(shirt=(240, 180, 70), pants=(70, 100, 160), skin=(206, 150, 106), hat=None, cap=(40, 36, 34))}.get(o.get("jenis", "pria"))
            hgt = o.get("tinggi", 420 if o.get("jenis") != "anak" else 290)
            if o.get("jenis", "pria") != "wanita":
                spec = dict(spec, cap=None)
                if o.get("peci", lat in ("musholla", "kitab")):
                    spec["peci"] = True
                if o.get("sarung", lat == "musholla" and o.get("jenis", "pria") == "pria"):
                    spec["sarung"] = tuple(o["sarung"]) if isinstance(o.get("sarung"), (list, tuple)) else (70, 96, 130)
            if o.get("noda"):
                spec = dict(spec, noda=True)
            if o.get("baju"):
                spec = dict(spec, shirt=tuple(o["baju"]))
            if o.get("jilbab") and spec.get("hijab"):
                spec = dict(spec, hijab=tuple(o["jilbab"]))
            person(c, o.get("x", 300), o.get("y", 1660), hgt, spec, o.get("aksi", "diam"), tg, o.get("hadap", 1), ph=k * 0.9)

    def _hill(self, c, t, g, tg):
        spots = hill_spots()
        n = len(spots)
        for k, (x, y, o) in enumerate(spots):
            th = k / n
            if g > th:
                d = 0.45 + 0.75 * (y - 860) / 320.0
                tree(c, x, y, d, min(1.0, (g - th) * n / 6.0), k)
        if self.latar == "api":
            for k in range(26):                                            # api & asap
                x = 60 + k * 40
                y = _hill_curve(x) + 40 + 30 * math.sin(k * 1.7)
                fl = 50 + 30 * math.sin(tg * 9 + k * 1.3)
                _poly(c, [(x - 22, y), (x + 22, y), (x + 4 * math.sin(tg * 7 + k), y - fl)], (238, 122, 52))
                _poly(c, [(x - 11, y), (x + 11, y), (x + 3 * math.sin(tg * 8 + k), y - fl * 0.55)], (252, 210, 90))
            for k in range(9):
                ph = (tg * 0.25 + k / 9.0) % 1.0
                x = 120 + k * 110 + 40 * math.sin(tg + k)
                y = 860 - ph * 520
                r = int(40 + 90 * ph)
                ov = c.copy()
                cv2.circle(ov, (_i(x), _i(y)), r, (110, 100, 100), -1, cv2.LINE_AA)
                cv2.addWeighted(ov, 0.25 * (1 - ph), c, 1 - 0.25 * (1 - ph), 0, c)
            for x, y in ((180, 1040), (420, 990), (760, 1010), (930, 1080)):  # tunggul
                cv2.rectangle(c, (x - 10, y - 30), (x + 10, y), (70, 56, 46), -1)
        self._actors(c, t, tg, 1560)

    def _desa(self, c, t, g, tg):
        for k, x in enumerate((120, 380, 640, 900)):
            if g > 0.3:
                tree(c, x + 120, 1000, 0.55, 1.0, k)
            house(c, x, 1080 + (k % 2) * 20, 0.9, k % 2 == 1)
        if self.s.get("keran"):                                            # keran air warga
            x, y = self.s.get("keran_x", 620), 1500
            cv2.rectangle(c, (x - 60, y - 10), (x + 60, y + 20), (150, 150, 150), -1)
            cv2.line(c, (x, y - 10), (x, y - 140), (120, 120, 126), 14, cv2.LINE_AA)
            cv2.line(c, (x, y - 140), (x + 50, y - 140), (120, 120, 126), 14, cv2.LINE_AA)
            for k in range(6):
                yy = y - 130 + ((tg * 240 + k * 22) % 120)
                cv2.circle(c, (x + 50, _i(yy)), 6, WATER, -1, cv2.LINE_AA)
            cv2.rectangle(c, (x + 26, y - 20), (x + 76, y + 18), (230, 230, 220), -1)
        if self.s.get("ramai", True):
            for k, (hx, hy) in enumerate(((520, 1330), (300, 1390), (420, 1440))):
                chicken(c, hx + 30 * math.sin(tg * 0.3 + k), hy, 80, tg + k * 0.9, 1 if k % 2 else -1)
        self._actors(c, t, tg, 1600, 1.0)

    def _spring(self, c, t, g, tg):
        if g > 0.2:                                                        # air pancuran
            k = min(1.0, (g - 0.2) / 0.5)
            w = int(6 + 16 * k)
            pts = []
            for i in range(26):
                u = i / 25.0
                pts.append((480 + 120 * u, 826 + 420 * u * u + 0 * u))
            for j in range(3):
                off = (j - 1) * w * 0.35
                cv2.polylines(c, [np.array([(_i(x + off), _i(y)) for x, y in pts], np.int32)], False,
                              WATER_L if j == 1 else WATER, max(2, w // (2 if j == 1 else 1)), cv2.LINE_AA)
            for i in range(10):                                             # percikan
                ph = (tg * 1.8 + i / 10.0) % 1.0
                x = 600 + math.cos(i * 2.1) * 60 * ph
                y = 1246 - math.sin(math.pi * ph) * 50
                cv2.circle(c, (_i(x), _i(y)), 5, WATER_L, -1, cv2.LINE_AA)
            for i in range(4):                                              # riak
                ph = (tg * 0.6 + i / 4.0) % 1.0
                cv2.ellipse(c, (600, 1262), (_i(30 + 200 * ph), _i(10 + 60 * ph)), 0, 0, 360,
                            _mix(WATER_L, WATER, ph), 2, cv2.LINE_AA)
        # ember
        cv2.rectangle(c, (300, 1200), (400, 1300), (80, 150, 210), -1, cv2.LINE_AA)
        cv2.ellipse(c, (350, 1200), (50, 14), 0, 0, 360, (60, 120, 180), -1, cv2.LINE_AA)
        for x, y, s_ in ((60, 1700, 1.0), (1000, 1720, 1.1), (900, 1500, 0.7)):
            if g > 0.4:
                for k in range(5):
                    cv2.ellipse(c, (_i(x + k * 14 - 30), _i(y)), (_i(10 * s_), _i(50 * s_)), -20 + k * 10, 180, 360, GRASS_D, -1, cv2.LINE_AA)
        self._actors(c, t, tg, 1620, 0.95)

    def _sawah(self, c, t, g, tg):
        for k in range(14):                                                 # kilau air di petak
            x = (k * 173 + tg * 20) % W
            y = 600 + (k * 97) % 1200
            cv2.line(c, (_i(x), _i(y)), (_i(x + 30), _i(y)), (230, 240, 250), 2, cv2.LINE_AA)
        self._actors(c, t, tg, 1680, 0.9)

    def _section(self, c, t, g, tg):
        top = 600
        a, b = self.speech
        grow = _ease((t - a) / max(0.6, (b - a) * 0.6))
        # pohon di atas irisan
        tree(c, 540, top + 6, 2.2, 1.0, 0)
        tree(c, 170, top + 6, 1.2, 1.0, 1)
        tree(c, 900, top + 6, 1.4, 1.0, 2)
        roots = []
        r = _rng("roots")
        for k in range(9):
            x0 = 540 + (k - 4) * 14
            pts = [(x0, top + 10)]
            ang = (k - 4) * 0.22
            x, y = x0, top + 10
            for j in range(14):
                ang += r.uniform(-0.25, 0.25)
                x += math.sin(ang) * 34
                y += math.cos(ang) * 34
                pts.append((x, y))
            roots.append(pts)
        for pts in roots:
            n = max(2, int(len(pts) * grow))
            p = np.array([(_i(x), _i(y)) for x, y in pts[:n]], np.int32)
            cv2.polylines(c, [p], False, (226, 206, 170), 9, cv2.LINE_AA)
            cv2.polylines(c, [p], False, (180, 150, 112), 3, cv2.LINE_AA)
        # tetes hujan menyusuri akar
        if t > a + 1.0:
            for k in range(24):
                pts = roots[k % len(roots)]
                ph = (tg * 0.35 + k / 24.0) % 1.0
                L = len(pts) - 1
                fi = ph * L
                i0 = int(fi)
                fr = fi - i0
                x = pts[i0][0] + (pts[min(L, i0 + 1)][0] - pts[i0][0]) * fr
                y = pts[i0][1] + (pts[min(L, i0 + 1)][1] - pts[i0][1]) * fr
                cv2.circle(c, (_i(x), _i(y)), 7, WATER, -1, cv2.LINE_AA)
                cv2.circle(c, (_i(x - 2), _i(y - 2)), 3, WATER_L, -1, cv2.LINE_AA)
        # air tanah beriak
        for k in range(12):
            x = (k * 97 + tg * 40) % W
            cv2.line(c, (_i(x), 1600 + (k % 3) * 60), (_i(x + 50), 1600 + (k % 3) * 60), WATER_L, 3, cv2.LINE_AA)
        if self.s.get("hujan") is None:
            self._rain(c, tg, top)

    def _rain(self, c, tg, y_max=None):
        y_max = y_max or H
        for k in range(90):
            x = (k * 137.3 + tg * 60) % W
            y = (k * 211.7 + tg * 1300) % y_max
            cv2.line(c, (_i(x), _i(y)), (_i(x - 6), _i(y + 26)), (210, 226, 238), 2, cv2.LINE_AA)

    def _camera(self, c, t):
        mode = self.s.get("kamera", "dorong")
        p = _ease(t / max(1.0, self.dur))
        fx, fy = self.s.get("fokus", (540, 1000))
        z0, z1 = {"dorong": (1.0, 1.12), "mundur": (1.14, 1.0), "geser": (1.1, 1.1), "naik": (1.12, 1.12), "turun": (1.12, 1.12)}.get(mode, (1.0, 1.08))
        z = z0 + (z1 - z0) * p
        sx = sy = 0.0
        for h in self.s.get("_hits") or ():                                # hentakan kecil saat kartu muncul
            d = t - h
            if 0 <= d < 0.45 and self.s.get("efek", True):
                e = math.exp(-d * 9.0)
                z += 0.022 * e
                sx += 7 * e * math.sin(d * 55)
                sy += 5 * e * math.cos(d * 47)
        cw, ch = W / z, H / z
        cx, cy = fx + sx, fy + sy
        if mode == "geser":
            cx = fx - 50 + 100 * p
        elif mode == "naik":
            cy = fy + 90 - 180 * p
        elif mode == "turun":
            cy = fy - 90 + 180 * p
        x0 = min(max(0, cx - cw / 2), W - cw)
        y0 = min(max(0, cy - ch / 2), H - ch)
        if z <= 1.001 and abs(sx) + abs(sy) < 0.01:
            return c
        M = np.array([[z, 0, -x0 * z], [0, z, -y0 * z]], np.float32)
        return cv2.warpAffine(c, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


class CardA:
    """Kartu info: muncul (pop) tepat saat kata pemicu diucapkan, melayang pelan, keluar di akhir adegan."""

    def __init__(self, spec, t0, t1, x, y, counter=None):
        self.spec, self.t0, self.t1, self.x, self.y, self.counter = spec, t0, t1, x, y, counter
        if counter is None:
            self.spr = self._sprite(spec.get("a", ""))

    def _sprite(self, a):
        sp = self.spec
        return card_sprite(sp["jenis"], a, sp.get("b", ""), sp.get("c", ""), sp.get("sumber", ""))

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1 + 0.3:
            return None
        k = _back((t - self.t0) / 0.35)
        out = max(0.0, (t - self.t1) / 0.3)
        spr = self.spr if self.counter is None else self._sprite(self._num(t))
        y = self.y + 6 * math.sin((t - self.t0) * 1.8)
        sp = self.spec
        if sp["jenis"] == "label" and sp.get("ke"):                         # garis penunjuk
            px, py = sp["ke"]
            if k > 0.5:
                cv2.line(img, (_i(self.x), _i(y + 20)), (_i(px), _i(py)), (255, 255, 255), 5, cv2.LINE_AA)
                cv2.line(img, (_i(self.x), _i(y + 20)), (_i(px), _i(py)), (220, 62, 52) if sp.get("b", "merah") == "merah" else (52, 160, 92), 2, cv2.LINE_AA)
                cv2.circle(img, (_i(px), _i(py)), 9, (255, 255, 255), -1, cv2.LINE_AA)
        blit(img, spr, self.x, y, scale=max(0.05, k) * (1 - 0.15 * out), alpha=1 - out)
        return None

    def _num(self, t):
        target, fmt = self.counter
        lama = float(self.spec.get("lama_hitung", 1.2))
        if lama > 2:                                                       # hitung bertahap (1, 2, 3 ...)
            v = int(math.floor(target * min(1.0, (t - self.t0) / lama))) + 1
            v = min(target, v)
        else:
            v = int(round(target * _ease((t - self.t0) / lama)))
        return fmt.format(v).replace(",", ".")


class TitleA:
    def __init__(self, text, t0, t1):
        self.spr, self.t0, self.t1 = title_sprite(text), t0, t1

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1 + 0.4:
            return None
        k = _ease((t - self.t0) / 0.4)
        out = max(0.0, (t - self.t1) / 0.4)
        blit(img, self.spr, W / 2, 300 + 30 * (1 - k), alpha=k * (1 - out))
        return None


# ------------------------------------------------------------------ subtitle gaya reel
FUNC = set("yang dan di ke dari ini itu dia ia pun juga untuk dengan pada atau tapi tetapi lalu kini saat sudah akan bisa ada "
           "sebuah satu para kita kami mereka nya lah kah sangat lebih masih baru".split())


def _norm(w):
    return re.sub(r"[^\w\-]", "", w.lower())


@functools.lru_cache(maxsize=1024)
def _word_spr(text, red):
    f = _font(FONT_B, 58)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = int(tmp.textlength(text, font=f)) + 30
    im = Image.new("RGBA", (w + 8, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if red:
        d.rounded_rectangle((2, 12, w + 4, 84), 12, fill=(222, 56, 48, 255))
        d.text((16, 10), text, font=f, fill=(255, 255, 255, 255))
    else:
        d.text((16, 10), text, font=f, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(28, 30, 34, 230))
    return _to_np(im)


class SubA:
    def __init__(self, chunks, y):
        self.chunks, self.y = chunks, y

    def draw(self, img, t, ctx):
        for c in self.chunks:
            if c["t0"] <= t < c["t1"]:
                sprs = [(_word_spr(w["text"], w["key"] and t >= w["ws"] - 0.05), w) for w in c["words"]]
                total = sum(s.shape[1] - 14 for s, _ in sprs)
                x = W / 2 - total / 2
                k = _ease((t - c["t0"]) / 0.12)
                for s, w in sprs:
                    on = t >= w["ws"] - 0.08
                    blit(img, s, x + s.shape[1] / 2, self.y + (0 if on else 4), alpha=k * (1.0 if on else 0.55))
                    x += s.shape[1] - 14
                return None
        return None


def sub_chunks(words, kunci, max_chars=24):
    out, cur = [], []

    def flush():
        if not cur:
            return
        ws = [{"text": words[j][2], "ws": words[j][0], "key": False} for j in cur]
        cand = [i for i, j in enumerate(cur) if _norm(words[j][2]) in kunci]
        if not cand:
            cand = sorted([i for i, j in enumerate(cur) if _norm(words[j][2]) not in FUNC and len(_norm(words[j][2])) >= 4],
                          key=lambda i: -len(_norm(words[cur[i]][2])))[:1]
        for i in cand[:1]:
            ws[i]["key"] = True
        out.append(ws)

    for j, w in enumerate(words):
        txt = " ".join(words[i][2] for i in cur)
        gap = (w[0] - (words[cur[-1]][0] + words[cur[-1]][1])) if cur else 0
        if cur and (len(txt) + 1 + len(w[2]) > max_chars or (gap > 0.28 and len(txt) > 8) or txt.endswith((".", "?", "!"))):
            flush()
            cur = []
        cur.append(j)
    flush()
    res = []
    for ci, ws in enumerate(out):
        t0 = max(0.0, ws[0]["ws"] - 0.06)
        res.append({"t0": t0, "words": ws})
    for ci, c in enumerate(res):
        c["t1"] = res[ci + 1]["t0"] if ci + 1 < len(res) else c["words"][-1]["ws"] + 1.2
    return res


# ------------------------------------------------------------------ rencana adegan
def _find(words, kata, after=0.0):
    if not kata:
        return None
    ks = [_norm(x) for x in kata.split()]
    for j in range(len(words)):
        if words[j][0] < after:
            continue
        if all(j + i < len(words) and _norm(words[j + i][2]).startswith(ks[i]) for i in range(len(ks))):
            return words[j][0]
    return None


SLOTS = {"atas": (540, 330), "atas2": (540, 560), "kiri": (330, 420), "kanan": (750, 420), "tengah": (540, 700)}


def plan_scene(i, sc, seg, P=None, st=None):
    words = seg.get("words") or []
    a, b = seg["speech"]
    dur = seg.get("dur", b + 0.5)
    shot = dict(sc.get("shot") or {})
    hits = []
    for n, k in enumerate(sc.get("kartu") or []):
        if k.get("jenis") not in ("label",):
            t0 = _find(words, k.get("pada"), 0.0)
            hits.append(t0 if t0 is not None else a + 0.3 + n * 0.8)
    shot["_hits"] = hits
    hp = []
    for k in (sc.get("kartu") or []):
        if k.get("jenis") not in ("label",):
            pos = k.get("pos", "atas")
            x, y = SLOTS.get(pos, (540, 330)) if isinstance(pos, str) else pos
            hp.append((x, y + 110))
    shot["_hitpos"] = hp
    shot["_latar_fx"] = (st or {}).get("latar_fx", True)
    if sc.get("_wajah"):
        shot["_wajah"] = sc["_wajah"]
    shot["_hadits"] = any(k.get("jenis") == "hadits" for k in (sc.get("kartu") or []))
    if "malam" not in shot and re.search(r"\bmalam\b", (sc.get("narasi") or "").lower()):
        shot["malam"] = True
    A = [KisahA(shot, dur, (a, b), i)]
    S = [(0.05, "swish", 0.35)]
    if sc.get("judul"):
        A.append(TitleA(sc["judul"], 0.1, dur - 0.2))
    used = 0.0
    for n, k in enumerate(sc.get("kartu") or []):
        t0 = _find(words, k.get("pada"), 0.0)
        if t0 is None:
            t0 = a + 0.3 + n * 0.8
        t1 = dur - 0.25 if k.get("tahan", True) else min(dur - 0.25, t0 + float(k.get("lama", 3.0)))
        pos = k.get("pos", "atas")
        x, y = SLOTS.get(pos, (540, 330)) if isinstance(pos, str) else pos
        counter = None
        if k["jenis"] == "angka" and k.get("hitung"):
            counter = (int(k["hitung"]), k.get("format", "{:,}"))
        A.append(CardA(k, t0, t1, x, y, counter))
        S.append((t0, "pop" if k["jenis"] != "label" else "tick", 0.55))
        used = max(used, t0)
    kunci = frozenset(_norm(x) for x in (sc.get("kunci") or []))
    if words:
        A.append(SubA(sub_chunks(words, kunci), sc.get("sub_y", 1180)))
    return A, S
