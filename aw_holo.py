"""
Hologram per kata: SETIAP kata yang diucapkan Gus Idrus muncul sebagai proyeksi hologram, tepat pada waktunya
(waktu per kata dari edge-tts WordBoundary).

  plan_scene(...)  -> {"back": [...], "front": [...], "sfx": [...]} untuk satu adegan
  HoloStageA       piringan proyektor di kaki ustad (cincin berputar, denyut tiap kata, boot saat adegan mulai)
  HoloBeamA        sorot cahaya proyektor (ikut keras-pelan suara) + partikel data naik
  HoloHudA         bingkai HUD di sudut panggung + garis pindai yang menyapu layar
  WordHoloA        panel kata hologram; 7 gaya masuk x 5 gaya keluar, bergantian supaya tidak monoton
  IconHoloA        ikon hologram berputar 3D di atas piringan (menggantikan stiker kata penting)
  StampHoloA       kata hukum besar (WAJIB, JANGAN, ...) menghentak dengan glitch + gelombang kejut

Warna: tema bergilir per adegan (sian, toska, ungu, biru langit), emas untuk adegan ayat/hadits & kata
Allah/ibadah, hijau untuk wajib/sunnah/sah, merah untuk jangan/haram/batal.
Gaya (config style["holo"]): "semua" (tiap kata) | "penting" (hanya kata bermakna) | "off".
Hanya MENAMPILKAN kata yang memang diucapkan; tidak menambah isi.
"""
import functools
import math
import os
import random
import re
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import aw_doodle as D
import aw_kata as K
import aw_layout as LY

W, H = D.W, D.H
STAGE_TOP, FEET_Y, SUB_TOP = 330, 1392, 1436
LANE_Y = 1282                                    # pusat jalur kata hologram (di atas subtitle, di dalam sorot proyektor)
PLATE = np.array([6, 14, 30], np.float32)        # kaca gelap panel hologram

# (glow = warna cahaya di atas kaca gelap, deep = warna garis di atas kertas terang)
THEMES = [
    {"glow": (80, 232, 255), "deep": (0, 138, 186)},     # sian
    {"glow": (90, 255, 205), "deep": (0, 150, 118)},     # toska
    {"glow": (196, 150, 255), "deep": (112, 66, 214)},   # ungu
    {"glow": (120, 196, 255), "deep": (28, 104, 206)},   # biru langit
]
GOLD = {"glow": (255, 214, 110), "deep": (186, 124, 0)}
GREEN = {"glow": (120, 255, 160), "deep": (22, 150, 78)}
RED = {"glow": (255, 112, 112), "deep": (200, 40, 48)}

POS_KEYS = {"wajib", "sunnah", "sunah", "sah", "boleh", "benar"}
NEG_KEYS = {"jangan", "batal", "haram", "larang", "salah", "dosa", "maksiat", "najis"}
SACRED_ICONS = {"bulan", "bintang", "buku", "kabah", "masjid", "sajadah"}
FUNC = K.STOP | {"di", "ke", "si", "pun", "lah", "tak", "tidak", "bila", "jika", "kalau", "maka", "agar", "supaya", "karena",
                 "sebab", "oleh", "dalam", "bagi", "tapi", "tetapi", "namun", "sudah", "telah", "masih", "lagi", "ada", "bisa",
                 "dapat", "harus", "para", "sang", "nah", "ya", "kan", "pula", "saja", "hanya", "seperti", "ketika", "saat",
                 "sambil", "bahwa", "tersebut", "kami", "mereka", "dia", "ia", "kalian", "anda", "sangat", "lebih", "paling"}

ENTER_FULL = ["scan", "glitch", "flip", "zoom", "type", "rise", "pixel", "echo", "swing"]
ENTER_SMALL = ["flip", "type", "pixel", "rise"]
ENTER_KEY = ["zoom", "glitch", "scan", "echo", "swing"]
EXITS = ["up", "shatter", "squash", "side", "glitchout"]


# ================================================================ util
def _c(c):
    return np.array(c, np.float32)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _h(*xs):
    return zlib.crc32(repr(xs).encode()) & 0xFFFFFFFF


def _rnd(*xs):
    return (_h(*xs) % 10007) / 10007.0


def _flicker(t, seed, k=1.0):
    """Kedip khas hologram: denyut cepat halus + sesekali padam sesaat."""
    f = 0.9 + 0.1 * math.sin(t * 47.0 + seed) * math.sin(t * 13.0 + seed * 0.7)
    if _h(int(t * 30), seed) % 37 == 0:
        f *= 0.45
    return 1.0 - (1.0 - f) * k


@functools.lru_cache(maxsize=48)
def _font(size):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "bahnschrift.ttf")
    if os.path.exists(p):
        f = ImageFont.truetype(p, size)
        try:
            names = f.get_variation_names()
            pick = next((n for n in names if n.strip().lower() in (b"bold", "bold")), None) or \
                next((n for n in names if b"Bold" in (n if isinstance(n, bytes) else n.encode()) and
                      b"Condensed" not in (n if isinstance(n, bytes) else n.encode())), None)
            if pick:
                f.set_variation_by_name(pick)
        except Exception:
            pass
        return f
    return D.font("hand", size)


def _blend(img, dark, light, cx, cy, k=1.0, kd=1.0):
    """Tempel sprite hologram: kaca gelap (alpha) lalu cahaya aditif. Pusat di (cx, cy)."""
    h, w = light.shape[:2]
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0 or (k <= 0.01 and kd <= 0.01):
        return
    sx, sy = x0 - x, y0 - y
    roi = img[y0:y1, x0:x1].astype(np.float32)
    if dark is not None and kd > 0.01:
        a = dark[sy:sy + y1 - y0, sx:sx + x1 - x0, None] * kd
        roi += (PLATE - roi) * a
    if k > 0.01:
        roi += light[sy:sy + y1 - y0, sx:sx + x1 - x0] * k
    np.clip(roi, 0, 255, out=roi)
    img[y0:y1, x0:x1] = roi.astype(np.uint8)


def _overlay(img, box, alpha, fn):
    """Gambar dengan cv2 ke salinan ROI lalu campur dengan alpha (fn menerima (roi, x0, y0))."""
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(img.shape[1], x1), min(img.shape[0], y1)
    if x1 <= x0 or y1 <= y0 or alpha <= 0.01:
        return
    roi = img[y0:y1, x0:x1]
    ov = roi.copy()
    fn(ov, x0, y0)
    cv2.addWeighted(ov, float(min(1.0, alpha)), roi, float(1 - min(1.0, alpha)), 0, dst=roi)


def _resize(a, sx, sy):
    h, w = a.shape[:2]
    nw, nh = max(2, int(w * sx)), max(2, int(h * sy))
    if nw == w and nh == h:
        return a
    return cv2.resize(a, (nw, nh), interpolation=cv2.INTER_LINEAR)


# ================================================================ sprite (di-cache)
_CACHE = {}


def _cached(key, fn):
    if key not in _CACHE:
        if len(_CACHE) > 900:
            _CACHE.clear()
        _CACHE[key] = fn()
    return _CACHE[key]


def _chamfer(x, y, w, h, c):
    return np.array([(x + c, y), (x + w - 1, y), (x + w - 1, y + h - 1 - c), (x + w - 1 - c, y + h - 1), (x, y + h - 1), (x, y + c)],
                    np.int32)


def word_sprite(text, size, glow):
    """-> (dark HxW, light HxWx3, lebar_panel). Panel kaca bersudut potong + teks bercahaya + garis pindai."""
    def build():
        f = _font(size)
        l, t, r, b = f.getbbox(text)
        tw, th = max(1, r - l), max(1, b - t)
        pi, py = int(size * 0.34), int(size * 0.24)
        pw, ph = tw + 2 * pi, th + 2 * py
        g = int(size * 0.45) + 8
        Wc, Hc = pw + 2 * g, ph + 2 * g
        im = Image.new("L", (Wc, Hc), 0)
        ImageDraw.Draw(im).text((g + pi - l, g + py - t), text, font=f, fill=255)
        tm = np.asarray(im, np.float32) / 255.0
        poly = _chamfer(g, g, pw, ph, int(ph * 0.3))
        plate = np.zeros((Hc, Wc), np.uint8)
        cv2.fillPoly(plate, [poly], 255)
        edge = np.zeros_like(plate)
        cv2.polylines(edge, [poly], True, 255, 2, cv2.LINE_AA)
        cv2.line(edge, tuple(poly[5]), tuple(poly[0]), 255, 5, cv2.LINE_AA)          # aksen sudut
        cv2.line(edge, tuple(poly[2]), tuple(poly[3]), 255, 5, cv2.LINE_AA)
        pm, em = plate / 255.0, edge / 255.0
        col = _c(glow)
        core = _c(_mix(glow, (255, 255, 255), 0.62))
        gl = cv2.GaussianBlur(tm, (0, 0), max(2.0, size * 0.15))
        eg = cv2.GaussianBlur(em, (0, 0), 5)
        scan = (((np.arange(Hc) % 4) == 0).astype(np.float32)[:, None] * pm) * 0.12
        light = tm[..., None] * core + (gl * 1.55 + em * 0.95 + eg * 0.6 + scan)[..., None] * col
        dark = np.clip(pm * 0.84 + cv2.GaussianBlur(pm, (0, 0), 9) * 0.2, 0, 0.88)
        return dark.astype(np.float32), light.astype(np.float32), pw
    return _cached(("w", text, size, glow), build)


def icon_sprite(name, size, glow, P):
    """Ikon doodle -> hologram: garis tinta jadi cahaya terang, isian jadi cahaya redup, + pendaran."""
    def build():
        pad = 24
        c = size + 2 * pad
        wht = np.full((c, c, 3), 255, np.uint8)
        blk = np.zeros((c, c, 3), np.uint8)
        dr = D.icon(name, size, P)
        dr.render(wht, pad, pad, 1.0, 1.0, 0, 0)
        dr.render(blk, pad, pad, 1.0, 1.0, 0, 0)
        a = 1.0 - (wht.astype(np.float32) - blk.astype(np.float32)).mean(2) / 255.0
        a = np.clip(a, 0, 1)
        col_img = blk.astype(np.float32) / np.maximum(a[..., None], 1e-3)
        lum = np.clip(col_img.mean(2), 0, 255) / 255.0
        inten = a * (0.3 + 0.7 * (1.0 - lum))
        rows = (0.78 + 0.22 * ((np.arange(c) % 3) != 0)).astype(np.float32)[:, None]
        inten = inten * rows
        col = _c(glow)
        core = _c(_mix(glow, (255, 255, 255), 0.45))
        gl = cv2.GaussianBlur(inten, (0, 0), 6)
        light = inten[..., None] * core + gl[..., None] * col * 1.4
        return light.astype(np.float32)
    return _cached(("i", name, size, glow), build)


def disc_sprite(R, glow):
    """Kaca bulat gelap + cincin bercahaya (alas ikon hologram)."""
    def build():
        g = 22
        c = 2 * (R + g)
        pm = np.zeros((c, c), np.uint8)
        cv2.circle(pm, (c // 2, c // 2), R, 255, -1, cv2.LINE_AA)
        em = np.zeros_like(pm)
        cv2.circle(em, (c // 2, c // 2), R, 255, 3, cv2.LINE_AA)
        cv2.circle(em, (c // 2, c // 2), int(R * 0.84), 160, 1, cv2.LINE_AA)
        pm, em = pm / 255.0, em / 255.0
        col = _c(glow)
        rows = (((np.arange(c) % 4) == 0).astype(np.float32)[:, None] * pm) * 0.1
        light = (em + cv2.GaussianBlur(em, (0, 0), 6) * 0.9 + rows)[..., None] * col
        light += (cv2.GaussianBlur(pm, (0, 0), R * 0.5) * pm * 0.18)[..., None] * col      # cahaya dari dalam
        dark = np.clip(pm * 0.8 + cv2.GaussianBlur(pm, (0, 0), 8) * 0.2, 0, 0.86)
        return dark.astype(np.float32), light.astype(np.float32)
    return _cached(("d", R, glow), build)


def beam_sprite(rx, h, top_scale, col_deep, col_glow):
    """Sorot proyektor (RGBA float): melebar ke atas, terang di bawah, tepi bercahaya + garis-garis vertikal."""
    def build():
        wt = int(rx * top_scale * 2) + 8
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]               # 0 atas .. 1 bawah
        half = (rx + (rx * top_scale - rx) * (1 - yy))                      # setengah lebar per baris
        xx = np.abs(np.arange(wt, dtype=np.float32)[None, :] - wt / 2)
        inside = np.clip((half - xx) / 10.0, 0, 1)
        edge = np.exp(-((xx - half + 4) ** 2) / 30.0)
        vert = np.power(yy, 1.4)
        rnd = np.random.RandomState(_h(rx, h) % 100000)
        streak = np.zeros(wt, np.float32)
        for _ in range(9):
            x = rnd.randint(8, wt - 8)
            streak[x - 1:x + 2] += rnd.uniform(0.4, 1.0)
        a = inside * vert * 0.26 + edge * vert * 0.5
        st = inside * np.clip(streak[None, :], 0, 1) * 0.22
        colm = np.stack([np.full((h, wt), c, np.float32) for c in _mix(col_deep, col_glow, 0.45)], 2)
        return a.astype(np.float32), st.astype(np.float32), colm
    return _cached(("b", rx, h, top_scale, col_deep, col_glow), build)


# ================================================================ efek pada sprite
def _glitch(light, amt, seed):
    """Pisah kanal RGB + geser pita horizontal."""
    if amt <= 0.5:
        return light
    out = light.copy()
    d = int(amt)
    out[:, :, 0] = np.roll(light[:, :, 0], d, axis=1)
    out[:, :, 2] = np.roll(light[:, :, 2], -d, axis=1)
    h = out.shape[0]
    for j in range(2):
        r = _rnd(seed, j)
        y0 = int(r * h * 0.8)
        y1 = min(h, y0 + max(3, int(h * (0.08 + 0.12 * _rnd(seed, j, 1)))))
        out[y0:y1] = np.roll(out[y0:y1], int((_rnd(seed, j, 2) - 0.5) * 3 * amt), axis=1)
    return out


def _pixelate(a, block):
    if block <= 1:
        return a
    h, w = a.shape[:2]
    s = cv2.resize(a, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_AREA)
    return cv2.resize(s, (w, h), interpolation=cv2.INTER_NEAREST)


def _shards(img, cx, cy, w, h, e, col, seed, n=16):
    """Pecahan panel beterbangan (gaya keluar 'shatter')."""
    if e <= 0 or e >= 1:
        return
    a = 1.0 - e

    def fn(ov, x0, y0):
        for i in range(n):
            ang = _rnd(seed, i) * 2 * math.pi
            sp = 120 + 260 * _rnd(seed, i, 1)
            px = cx + (_rnd(seed, i, 2) - 0.5) * w + math.cos(ang) * sp * e
            py = cy + (_rnd(seed, i, 3) - 0.5) * h + math.sin(ang) * sp * e - 60 * e
            s = int(4 + 9 * _rnd(seed, i, 4) * (1 - e * 0.6))
            cv2.rectangle(ov, (int(px - s - x0), int(py - s - y0)), (int(px + s - x0), int(py + s - y0)),
                          col if i % 3 else (255, 255, 255), -1)
    _overlay(img, (cx - w - 320, cy - h - 340, cx + w + 320, cy + h + 300), a * 0.9, fn)


# ================================================================ aktor
class WordHoloA:
    ENT = 0.2      # durasi animasi masuk
    EXT = 0.34     # durasi animasi keluar

    def __init__(self, text, t0, t1, x, y, size, theme, enter, exit_, seed, lane_cx):
        self.text, self.t0, self.t1, self.x, self.y, self.size = text, t0, t1, x, y, size
        self.th, self.enter, self.exit, self.seed, self.lane_cx = theme, enter, exit_, seed, lane_cx
        self.side = -1 if seed % 2 else 1

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1 + self.EXT:
            return None
        dark, light, pw = word_sprite(self.text, self.size, self.th["glow"])
        if pw > W - 70:                                                # frasa panjang -> perkecil agar muat layar
            f = (W - 70) / pw
            dark, light = _cached(("ws", self.text, self.size, self.th["glow"]), lambda: (_resize(dark, f, f), _resize(light, f, f)))
            pw = W - 70
        h, w = light.shape[:2]
        x = min(max(self.x, pw / 2 + 24), W - pw / 2 - 24)
        y = self.y
        a = t - self.t0
        p = _clamp01(a / self.ENT)
        e = _clamp01((t - self.t1) / self.EXT) if t > self.t1 else 0.0
        sx = sy = 1.0
        k = kd = 1.0
        gl = 0.0
        dark_m, light_m = dark, light
        y += 3.0 * math.sin(a * 4.0 + self.seed)                       # melayang halus
        en = self.enter
        if p < 1.0:
            if en == "scan":                                            # pindai dari bawah ke atas
                cut = int(h * (1 - D.ease_out(p)))
                light_m = light.copy()
                dark_m = dark.copy()
                light_m[:cut] = 0
                dark_m[:cut] = 0
                light_m[max(0, cut - 2):cut + 3] += _c(self.th["glow"]) * 1.6
            elif en == "glitch":
                gl = (1 - p) * 22
                k = 0.4 + 0.6 * p
            elif en == "flip":                                          # kartu berputar masuk (3D)
                sx = max(0.04, abs(math.cos((1 - D.ease_out(p)) * math.pi / 2)))
                sx = max(0.04, D.ease_back(p)) if p > 0.5 else sx
            elif en == "zoom":
                s = 1 + (1 - D.ease_out(p)) * 0.85
                sx = sy = s
                k = kd = p
            elif en == "type":                                          # diketik huruf demi huruf
                light_m = light.copy()
                g = (w - pw) // 2
                cut = int(g + pw * p)
                light_m[:, cut:] *= 0.0
                light_m[:, max(0, cut - 6):cut] += _c(self.th["glow"]) * 1.4 * (0.5 + 0.5 * math.sin(a * 60))
            elif en == "rise":                                          # naik dari piringan proyektor
                y += (1 - D.ease_out(p)) * 110
                sy = 0.25 + 0.75 * D.ease_out(p)
                k = kd = 0.3 + 0.7 * p
            elif en == "pixel":                                         # piksel kasar -> tajam
                light_m = _pixelate(light, 1 + int((1 - p) * 16))
                kd = p
            elif en == "echo":                                          # bayangan-bayangan menyusut menyatu
                for j in (3, 2, 1):
                    gs = 1 + (1 - D.ease_out(p)) * 0.35 * j
                    _blend(img, None, _resize(light, gs, gs), x, y, 0.35 * (1 - p) / j, 0)
                k = kd = 0.25 + 0.75 * p
            elif en == "swing":                                         # melayang dari piringan menyusuri busur
                q = D.ease_out(p)
                x += self.side * (1 - q) * 260
                y += math.sin((1 - q) * math.pi) * -70 + (1 - q) * 120
                sx = sy = 0.5 + 0.5 * q
                k = kd = 0.3 + 0.7 * p
        if e > 0:
            ex = self.exit
            if ex == "up":
                y -= D.ease_out(e) * 130
                sx = sy = 1 - 0.3 * e
                k = kd = 1 - e
            elif ex == "shatter":
                k = kd = max(0.0, 1 - e * 2.2)
                _shards(img, x, y, pw, h - 30, e, self.th["glow"], self.seed)
            elif ex == "squash":                                        # runtuh jadi garis lalu titik
                sy = max(0.03, 1 - e * 1.4)
                sx = 1 + 0.25 * e if e < 0.6 else max(0.03, (1 - e) * 3.0)
                k = 1.0 + e
                kd = 1 - e
            elif ex == "side":
                x += self.side * D.ease_out(e) * 320
                sx = sy = 1 - 0.45 * e
                k = kd = 1 - e
            elif ex == "glitchout":
                gl = e * 30
                k = kd = 1 - e
        fl = _flicker(t, self.seed, ctx.get("fxk", 1.0) or 0.4)
        if gl <= 0 and _h(int(t * 30), self.seed, 9) % 11 == 0:
            gl = 7                                                      # cegukan glitch acak sesekali
        if gl > 0:
            light_m = _glitch(light_m, gl, self.seed + int(t * 24))
        if sx != 1.0 or sy != 1.0:
            dark_m = _resize(dark_m, sx, sy)
            light_m = _resize(light_m, sx, sy)
        _blend(img, dark_m, light_m, x, y, k * fl, kd)
        return None


class IconHoloA:
    """Ikon hologram berputar 3D (mendarat menghadap depan) di atas kaca bulat, label di bawahnya."""

    def __init__(self, x, y, icon, label, t0, t1, P, R, theme, digit=None, seed=0):
        self.x, self.y, self.icon, self.label, self.t0, self.t1, self.P = x, y, icon, label, t0, t1, P
        self.R, self.th, self.digit, self.seed = int(R), theme, digit, seed

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1:
            return None
        a = t - self.t0
        R, th = self.R, self.th
        cx, cy = self.x, self.y + 6 * math.sin(a * 3.0 + self.seed)
        grow = D.ease_back(_clamp01((a - 0.08) / 0.32))
        out = _clamp01((self.t1 - t) / 0.3)
        fl = _flicker(t, self.seed, ctx.get("fxk", 1.0) or 0.4)
        if a < 0.14:                                                  # sinar pindai turun dulu
            hh = int(R * 2.4 * a / 0.14)
            _overlay(img, (cx - 4, cy - R * 1.2, cx + 4, cy - R * 1.2 + hh), 0.85,
                     lambda ov, x0, y0: cv2.rectangle(ov, (0, 0), (ov.shape[1], ov.shape[0]), th["glow"], -1))
        if grow <= 0.02:
            return None
        sq = out if out < 1 else 1.0                                   # keluar: dipipihkan vertikal
        dk, lt = disc_sprite(R, th["glow"])
        s = grow
        _blend(img, _resize(dk, s, s * sq), _resize(lt, s, s * sq), cx, cy, fl * out, out)
        # cincin putus-putus berputar di luar kaca
        rot = a * 140 + self.seed * 37

        def ring(ov, x0, y0):
            for i in range(4):
                a0 = rot + i * 90
                cv2.ellipse(ov, (int(cx - x0), int(cy - y0)), (int((R + 14) * s), int((R + 14) * s * sq)), 0, a0, a0 + 52,
                            th["deep"], 4, cv2.LINE_AA)
            for i in range(12):
                ang = math.radians(-rot * 0.6 + i * 30)
                r0, r1 = (R + 26) * s, (R + 34) * s
                cv2.line(ov, (int(cx - x0 + r0 * math.cos(ang)), int(cy - y0 + r0 * math.sin(ang) * sq)),
                         (int(cx - x0 + r1 * math.cos(ang)), int(cy - y0 + r1 * math.sin(ang) * sq)), th["deep"], 2, cv2.LINE_AA)
        _overlay(img, (cx - R - 50, cy - R - 50, cx + R + 50, cy + R + 50), 0.9 * out, ring)
        # isi: ikon (putar Y 3D, mendarat menghadap depan) atau angka
        if self.digit:
            dk2, lt2, _pw = word_sprite(self.digit, int(R * 1.05), th["glow"])
            sp = D.ease_out(_clamp01(a / 0.7))
            sxs = max(0.05, abs(math.cos((1 - sp) * math.pi * 2)))
            _blend(img, None, _resize(lt2, sxs * s, s * sq), cx, cy, fl * out, 0)
        else:
            isz = int(R * 1.2)
            lt2 = icon_sprite(self.icon, isz, th["glow"], self.P)
            sp = D.ease_out(_clamp01(a / 0.9))
            ang = (1 - sp) * math.pi * 3 + 0.22 * math.sin(a * 2.2) * sp
            c = math.cos(ang)
            spr = lt2 if c >= 0 else lt2[:, ::-1]
            _blend(img, None, _resize(spr, max(0.05, abs(c)) * s, s * sq), cx, cy - 2, fl * out * 1.05, 0)
        if self.label and a > 0.25:
            dk3, lt3, _pw = word_sprite(self.label, 34, th["glow"])
            pl = D.ease_out(_clamp01((a - 0.25) / 0.25))
            _blend(img, _resize(dk3, pl, sq), _resize(lt3, pl, sq), cx, cy + R * s + 30, fl * out, out)
        return None


class StampHoloA:
    """Kata hukum besar menghentak: masuk dari besar + glitch, gelombang kejut, garis pindai ganda."""

    def __init__(self, text, t0, t1, theme, y=665, seed=0):
        self.text, self.t0, self.t1, self.th, self.y, self.seed = text, t0, t1, theme, y, seed

    def draw(self, img, t, ctx):
        if t < self.t0 or t > self.t1:
            return None
        a = t - self.t0
        dk, lt, pw = word_sprite(self.text, 132, self.th["glow"])
        if pw > W - 80:
            f = (W - 80) / pw
            dk, lt = _resize(dk, f, f), _resize(lt, f, f)
        out = _clamp01((self.t1 - t) / 0.22)
        s = 1.0 + 0.7 * math.exp(-a * 11.0)
        gl = 26 * math.exp(-a * 8.0) + (18 if out < 1 else 0) * (1 - out)
        lt2 = _glitch(lt, gl, self.seed + int(t * 30)) if gl > 0.5 else lt
        # gelombang kejut
        e = _clamp01(a / 0.55)
        if e < 1:
            def ring(ov, x0, y0):
                r = int(80 + 520 * D.ease_out(e))
                cv2.ellipse(ov, (int(W / 2 - x0), int(self.y - y0)), (r, int(r * 0.42)), 0, 0, 360, self.th["deep"],
                            max(2, int(10 * (1 - e))), cv2.LINE_AA)
            _overlay(img, (0, self.y - 300, W, self.y + 300), 0.8 * (1 - e), ring)
        fl = _flicker(t, self.seed, ctx.get("fxk", 1.0) or 0.4)
        _blend(img, _resize(dk, s, s), _resize(lt2, s, s), W / 2, self.y, fl * out, out)
        return None


class HoloStageA:
    """Piringan proyektor di kaki ustad. Digambar DI BELAKANG ustad. Tiap kata yang diucapkan memancarkan denyut cincin."""

    def __init__(self, cx, s, theme, starts, feet=FEET_Y):
        self.cx, self.th, self.starts = cx, theme, starts
        self.rx = int(max(150, 300 * s / 0.78))
        self.ry = int(self.rx * 0.21)
        self.cy = int(feet) - 4
        self.gbot = SUB_TOP - 6 if not LY.pojok() else self.cy + 80
        self.hexa = False

    def draw(self, img, t, ctx):
        boot = D.ease_back(_clamp01(t / 0.45))
        if boot <= 0.02:
            return None
        cx, cy, th = self.cx, self.cy, self.th
        rx, ry = int(self.rx * boot), max(2, int(self.ry * boot))
        rot = t * 60.0
        pulses = [(t - s0) / 0.65 for s0 in self.starts if 0 <= t - s0 < 0.65]

        def base(ov, x0, y0):
            c = (int(cx - x0), int(cy - y0))
            cv2.ellipse(ov, c, (rx, ry), 0, 0, 360, tuple(int(v) for v in PLATE), -1, cv2.LINE_AA)
        _overlay(img, (cx - rx - 10, cy - ry - 10, cx + rx + 10, cy + ry + 10), 0.38, base)

        # lantai grid hologram (perspektif, bergulir pelan ke arah penonton)
        gx = int(self.rx * 1.9 * boot)
        vy = cy - 300

        def grid(ov, x0, y0):
            col = th["deep"]
            ytop, ybot = cy - ry - 26, self.gbot
            for i in range(-6, 7):
                bx = cx + i * gx / 6
                tx = cx + (bx - cx) * ((ytop - vy) / (ybot - vy))
                cv2.line(ov, (int(tx - x0), int(ytop - y0)), (int(bx - x0), int(ybot - y0)), col, 1, cv2.LINE_AA)
            for j in range(5):
                f = ((j + (t * 0.6) % 1.0) / 5.0) ** 1.8
                yy = ytop + (ybot - ytop) * f
                half = gx * (yy - vy) / (ybot - vy)
                cv2.line(ov, (int(cx - half - x0), int(yy - y0)), (int(cx + half - x0), int(yy - y0)), col, 1, cv2.LINE_AA)
        _overlay(img, (cx - gx - 4, cy - ry - 30, cx + gx + 4, self.gbot + 6), 0.42 * boot, grid)

        def rings(ov, x0, y0):
            c = (int(cx - x0), int(cy - y0))
            if self.hexa:                                             # varian heksagon berputar
                for rr, wd, colk in ((1.0, 4, "deep"), (0.62, 2, "glow")):
                    pts = [(c[0] + rx * rr * math.cos(math.radians(rot * (0.5 if rr < 1 else 0.25) + i * 60)),
                            c[1] + ry * rr * math.sin(math.radians(rot * (0.5 if rr < 1 else 0.25) + i * 60))) for i in range(6)]
                    cv2.polylines(ov, [np.int32(pts)], True, th[colk], wd, cv2.LINE_AA)
            cv2.ellipse(ov, c, (rx, ry), 0, 0, 360, th["deep"], 4 if not self.hexa else 2, cv2.LINE_AA)
            cv2.ellipse(ov, c, (int(rx * 0.7), int(ry * 0.7)), 0, rot, rot + 290, th["glow"], 3, cv2.LINE_AA)
            for i in range(6):
                a0 = -rot * 1.4 + i * 60
                cv2.ellipse(ov, c, (int(rx * 0.86), int(ry * 0.86)), 0, a0, a0 + 26, th["deep"], 5, cv2.LINE_AA)
            cv2.ellipse(ov, c, (int(rx * 0.4), int(ry * 0.4)), 0, 0, 360, th["glow"], 2, cv2.LINE_AA)
        _overlay(img, (cx - rx - 10, cy - ry - 10, cx + rx + 10, cy + ry + 10), 0.95, rings)
        if pulses:
            def pl(ov, x0, y0):
                for e in pulses[-3:]:
                    r = 1.0 + 0.55 * D.ease_out(e)
                    cv2.ellipse(ov, (int(cx - x0), int(cy - y0)), (int(rx * r), int(ry * r)), 0, 0, 360, th["deep"],
                                max(1, int(6 * (1 - e))), cv2.LINE_AA)
            e0 = min(pulses)
            _overlay(img, (cx - rx * 1.7, cy - ry * 1.7, cx + rx * 1.7, cy + ry * 1.7), 0.75 * (1 - e0 * 0.5), pl)
        if t < 0.6:                                                   # boot: cincin melebar
            e = t / 0.6

            def bootr(ov, x0, y0):
                r = 0.3 + 1.6 * D.ease_out(e)
                cv2.ellipse(ov, (int(cx - x0), int(cy - y0)), (int(self.rx * r), int(self.ry * r)), 0, 0, 360, th["glow"],
                            max(1, int(8 * (1 - e))), cv2.LINE_AA)
            _overlay(img, (cx - self.rx * 2, cy - self.ry * 2, cx + self.rx * 2, cy + self.ry * 2), 0.9 * (1 - e), bootr)
        return None


class HoloBeamA:
    """Sorot proyektor (terang mengikuti suara) + partikel data naik. Digambar di DEPAN ustad, tipis/transparan."""

    def __init__(self, cx, rx, theme, top, seed=0, feet=FEET_Y):
        self.cx, self.rx, self.th, self.seed = cx, int(rx), theme, seed
        self.top = int(top)
        self.feet = int(feet)
        self.h = int(self.feet - 4 - self.top)

    def draw(self, img, t, ctx):
        boot = _clamp01((t - 0.15) / 0.35)
        if boot <= 0:
            return None
        th = self.th
        a, st, colm = beam_sprite(self.rx, self.h, 1.35, th["deep"], th["glow"])
        try:
            m = float(ctx["mouth"](ctx.get("tg", 0.0))) if ctx.get("talking") else 0.0
        except Exception:
            m = 0.0
        fl = _flicker(t, self.seed, 0.8)
        k = boot * fl * (0.55 + 0.75 * min(1.0, m * 1.6))
        if t < 0.5:                                                   # boot berkedip
            k *= 1.0 if (_h(int(t * 30), self.seed) % 3) else 0.25
        hh, ww = a.shape
        yy = np.arange(hh, dtype=np.float32)[:, None]
        move = 0.5 + 0.5 * np.sin(yy * 0.045 + t * 9.0)                  # garis cahaya mengalir naik
        alpha = (a + st * move) * k
        x = int(self.cx - ww / 2)
        x0, x1 = max(0, x), min(W, x + ww)
        if x1 <= x0:
            return None
        sl = slice(x0 - x, x1 - x)
        roi = img[self.top:self.top + hh, x0:x1].astype(np.float32)
        al = alpha[:, sl, None]
        roi += (colm[:, sl] - roi) * al
        img[self.top:self.top + hh, x0:x1] = np.clip(roi, 0, 255).astype(np.uint8)
        # partikel data naik di dalam sorot
        n = 16

        def parts(ov, x0_, y0_):
            for i in range(n):
                ph = (t * (0.35 + 0.25 * _rnd(self.seed, i)) + _rnd(self.seed, i, 1)) % 1.0
                py = self.feet - 20 - ph * (self.h + 60)
                spread = self.rx * (1 + 0.35 * ph)
                px = self.cx + (_rnd(self.seed, i, 2) - 0.5) * 2 * spread * 0.85
                sz = 3 + int(4 * _rnd(self.seed, i, 3))
                col = th["deep"] if i % 2 else th["glow"]
                if i % 4 == 0:
                    cv2.line(ov, (int(px - x0_ - sz), int(py - y0_)), (int(px - x0_ + sz), int(py - y0_)), col, 2)
                    cv2.line(ov, (int(px - x0_), int(py - y0_ - sz)), (int(px - x0_), int(py - y0_ + sz)), col, 2)
                else:
                    cv2.rectangle(ov, (int(px - x0_), int(py - y0_)), (int(px - x0_ + sz), int(py - y0_ + sz)), col, -1)
        _overlay(img, (self.cx - self.rx * 1.6, self.top - 80, self.cx + self.rx * 1.6, self.feet), 0.7 * boot, parts)
        return None


class HoloHudA:
    """Bingkai HUD di sudut panggung + garis pindai yang menyapu dari atas ke bawah."""

    def __init__(self, theme, seed=0):
        self.th, self.seed = theme, seed

    def draw(self, img, t, ctx):
        th = self.th
        boot = _clamp01(t / 0.4)
        L = int(70 * D.ease_out(boot))
        x0, y0, x1, y1 = 34, STAGE_TOP + 6, W - 34, (SUB_TOP - 18 if not LY.pojok() else LY.LANE_Y + 100)
        if L > 2:
            fl = 0.75 * _flicker(t, self.seed + 5, 1.0)

            def br(ov, ox, oy):
                c = th["deep"]
                for (px, py, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                    cv2.line(ov, (px - ox, py - oy), (px - ox + dx * L, py - oy), c, 4, cv2.LINE_AA)
                    cv2.line(ov, (px - ox, py - oy), (px - ox, py - oy + dy * L), c, 4, cv2.LINE_AA)
                    cv2.circle(ov, (px - ox + dx * (L + 12), py - oy), 3, c, -1, cv2.LINE_AA)
                # tanda kecil di sisi (ticks)
                for i in range(5):
                    yy = int(y0 + (y1 - y0) * (0.3 + 0.1 * i))
                    w = 14 if i == 2 else 7
                    cv2.line(ov, (x0 - ox, yy - oy), (x0 - ox + w, yy - oy), c, 2)
                    cv2.line(ov, (x1 - ox, yy - oy), (x1 - ox - w, yy - oy), c, 2)
            _overlay(img, (0, y0 - 10, W, y1 + 10), fl, br)
        # garis pindai menyapu (periode 3.4 dtk, bervariasi per adegan)
        per = 3.4 + (self.seed % 3) * 0.4
        ph = ((t + self.seed * 0.37) % per) / per
        yb = int(y0 + ph * (y1 - y0))
        band = 46
        ya = max(0, yb - band)
        if yb > ya:
            g = np.linspace(0, 1, yb - ya, dtype=np.float32) ** 2 * 0.13
            g[-3:] = 0.42
            roi = img[ya:yb].astype(np.float32)
            roi += (_c(_mix(th["deep"], th["glow"], 0.5)) - roi) * g[:, None, None]
            img[ya:yb] = roi.astype(np.uint8)
        return None


# ================================================================ penjadwal
def theme_for(idx, tp):
    return GOLD if tp in ("quran", "hadits") else THEMES[idx % len(THEMES)]


def semantic(m, base):
    """Warna menurut makna kata (hanya warna; teks tetap kata yang diucapkan)."""
    if not m:
        return base
    key, icon = m[0], m[1]
    if key in POS_KEYS:
        return GREEN
    if key in NEG_KEYS:
        return RED
    if key == "allah" or icon in SACRED_ICONS:
        return GOLD
    return base


def _clean(txt):
    s = re.sub(r"[^\w'’\-?!]", "", txt or "", flags=re.U).strip("-")
    return s.replace("’", "'")


def mode_of(st):
    v = st.get("holo", "semua")
    if v is True:
        return "semua"
    if not v:
        return "off"
    return v


def plan_scene(idx, sc, seg, P, st, actors):
    """Aktor hologram untuk satu adegan. Waktu relatif awal adegan. actors = aktor adegan (dipakai mencari posisi ustad)."""
    mode = mode_of(st)
    if mode == "off":
        return None
    tp = sc.get("tipe", "bicara")
    who = next((a for a in actors if hasattr(a, "pose") and hasattr(a, "expr") and hasattr(a, "s")), None)
    cx, s = (float(who.x), float(who.s)) if who else (W / 2, 0.6)
    th = theme_for(idx, tp)
    words = seg.get("words") or []
    feet = float(getattr(who, "y", FEET_Y)) if who else FEET_Y
    stage = HoloStageA(int(cx), s, th, [w[0] for w in words], feet)
    stage.hexa = idx % 2 == 1
    lane_y = LY.LANE_Y
    lane_top = lane_y - 150 if not LY.pojok() else feet - 430
    front = [HoloBeamA(int(cx), stage.rx * 0.95, th, lane_top, seed=idx * 13 + 1, feet=feet), HoloHudA(th, seed=idx)]
    lane_cx = cx if not LY.pojok() else W / 2
    rng = random.Random(idx * 7919 + len(words) * 31)
    prev_en, prev_ex = None, None
    lane = []
    asks = K.ask_flags(sc, words)
    if mode == "semua":                                                  # subtitle hologram = satu-satunya subtitle
        chunks = []
        idxs = sub_chunks(words)
        for ci, ix in enumerate(idxs):
            ws = []
            for j in ix:
                txt = words[j][2]
                m = None if (K.idiom(words, j) or K.negated(words, j) or asks[j]) else K.match(txt)
                ws.append({"text": _clean(txt) or txt, "ws": words[j][0], "col": semantic(m, th)})
            t0 = max(0.0, words[ix[0]][0] - 0.08)
            last = words[ix[-1]]
            t1 = (words[idxs[ci + 1][0]][0] - 0.3) if ci + 1 < len(idxs) else last[0] + last[1] + 0.6
            t1 = min(t1, last[0] + last[1] + 1.4)
            chunks.append({"t0": t0, "t1": max(t0 + 0.4, t1), "words": ws})
        if chunks:
            front.append(HoloSubA(chunks, th, lane_y, seed=idx * 97 + 3))
        return {"back": [stage], "front": front, "sfx": [(0.02, "holo_boot", 0.32)]}
    for j, (t, d, txt) in enumerate(words):
        word = _clean(txt)
        if not word:
            continue
        m = None if K.idiom(words, j) else K.match(txt)
        n = K._norm(txt)
        func = (n in FUNC) or len(word) <= 2
        if m and K.negated(words, j):
            # 'tidak membatalkan' -> satu panel utuh berwarna netral, supaya hukumnya tidak terbaca terbalik
            j0 = next(i for i in (j - 1, j - 2) if i >= 0 and K._norm(words[i][2]) in K.NEG)
            word = " ".join(_clean(w[2]) for w in words[j0:j + 1])
            m = None
            func = False
        elif mode == "penting" and not m:
            continue
        tier = 2 if m else (0 if func else 1)
        pool = ENTER_KEY if tier == 2 else (ENTER_SMALL if tier == 0 else ENTER_FULL)
        en = rng.choice([x for x in pool if x != prev_en] or pool)
        ex = rng.choice([x for x in EXITS if x != prev_ex])
        prev_en, prev_ex = en, ex
        nxt = words[j + 1][0] if j + 1 < len(words) else t + d + 0.6
        t0 = max(0.0, t - 0.05)
        t1 = max(t0 + 0.26, min(nxt - 0.03, t + d + 0.55))
        size = (56, 80, 98)[tier]
        jitter = ((j % 3) - 1) * 46 + (rng.random() - 0.5) * 30
        y = lane_y + (10 if tier == 0 else 0) + (rng.random() - 0.5) * 18
        lane.append(WordHoloA(word.upper(), t0, t1, lane_cx + jitter, y, size, th if asks[j] else semantic(m, th), en, ex, seed=idx * 1000 + j,
                              lane_cx=lane_cx))
    front += lane
    sfx = [(0.02, "holo_boot", 0.32)]
    return {"back": [stage], "front": front, "sfx": sfx}


# ================================================================ SUBTITLE HOLOGRAM (satu-satunya subtitle)
def text_sprite(text, size, glow):
    """Teks bercahaya tanpa panel (dipakai per kata di subtitle hologram). -> (light, lebar_teks, pad)."""
    def build():
        f = _font(size)
        l, _t, r, _b = f.getbbox(text)
        asc, desc = f.getmetrics()
        g = int(size * 0.4) + 6
        Wc, Hc = max(1, r - l) + 2 * g, asc + desc + 2 * g
        im = Image.new("L", (Wc, Hc), 0)
        ImageDraw.Draw(im).text((g - l, g), text, font=f, fill=255)
        tm = np.asarray(im, np.float32) / 255.0
        core = _c(_mix(glow, (255, 255, 255), 0.6))
        gl = cv2.GaussianBlur(tm, (0, 0), max(2.0, size * 0.14))
        light = tm[..., None] * core + (gl * 1.6)[..., None] * _c(glow)
        return light.astype(np.float32), r - l, g
    return _cached(("t", text, size, glow), build)


def plate_sprite(pw, ph, glow):
    def build():
        g = 26
        Wc, Hc = pw + 2 * g, ph + 2 * g
        poly = _chamfer(g, g, pw, ph, int(ph * 0.3))
        plate = np.zeros((Hc, Wc), np.uint8)
        cv2.fillPoly(plate, [poly], 255)
        edge = np.zeros_like(plate)
        cv2.polylines(edge, [poly], True, 255, 2, cv2.LINE_AA)
        cv2.line(edge, tuple(poly[5]), tuple(poly[0]), 255, 6, cv2.LINE_AA)
        cv2.line(edge, tuple(poly[2]), tuple(poly[3]), 255, 6, cv2.LINE_AA)
        pm, em = plate / 255.0, edge / 255.0
        col = _c(glow)
        scan = (((np.arange(Hc) % 4) == 0).astype(np.float32)[:, None] * pm) * 0.1
        light = (em * 0.95 + cv2.GaussianBlur(em, (0, 0), 5) * 0.6 + scan)[..., None] * col
        dark = np.clip(pm * 0.86 + cv2.GaussianBlur(pm, (0, 0), 10) * 0.2, 0, 0.9)
        return dark.astype(np.float32), light.astype(np.float32)
    return _cached(("p", pw, ph, glow), build)


SUB_ENTER = ["scan", "flip", "zoom", "glitch", "rise", "pixel"]
WORD_FX = ["pop", "drop", "glitch", "flip", "zoom"]


class HoloSubA:
    """Subtitle hologram: satu panel per potongan kalimat; kata menyala satu per satu tepat saat diucapkan
    (efek masuk tiap kata bervariasi), kata yang sedang diucapkan paling terang + garis sorot, kata bermakna berwarna."""
    ENT, EXT = 0.2, 0.22

    def __init__(self, chunks, theme, y, seed=0):
        self.chunks, self.th, self.y, self.seed = chunks, theme, y, seed
        rng = random.Random(seed)
        prev = None
        for c in chunks:
            c["enter"] = rng.choice([e for e in SUB_ENTER if e != prev])
            prev = c["enter"]
            c["exit"] = rng.choice(EXITS)
            size = 64
            while True:
                gap = int(size * 0.32)
                ws = [text_sprite(w["text"], size, w["col"]["glow"]) for w in c["words"]]
                total = sum(s[1] for s in ws) + gap * (len(ws) - 1)
                if total <= 900 or size <= 40:
                    break
                size -= 4
            c["size"], c["gap"], c["total"] = size, gap, total
            x = -total / 2
            for w, s in zip(c["words"], ws):
                w["cx"] = x + s[1] / 2
                w["wfx"] = rng.choice(WORD_FX)
                x += s[1] + gap

    def draw(self, img, t, ctx):
        for i, c in enumerate(self.chunks):
            if c["t0"] - 0.02 <= t <= c["t1"] + self.EXT:
                self._chunk(img, c, t, ctx, i)
        return None

    def _chunk(self, img, c, t, ctx, i):
        th = self.th
        size = c["size"]
        pw, ph = int(c["total"] + size * 0.9), int(size * 1.45)
        dk, lt = plate_sprite(pw, ph, th["glow"])
        a = t - c["t0"]
        p = _clamp01(a / self.ENT)
        e = _clamp01((t - c["t1"]) / self.EXT) if t > c["t1"] else 0.0
        cx, cy = W / 2, self.y
        sx = sy = 1.0
        k = kd = 1.0
        gl = 0.0
        en = c["enter"]
        if p < 1:
            if en == "flip":
                sx = max(0.03, D.ease_back(p))
            elif en == "zoom":
                sx = sy = 1 + (1 - D.ease_out(p)) * 0.4
                k = kd = p
            elif en == "glitch":
                gl = (1 - p) * 26
            elif en == "rise":
                cy += (1 - D.ease_out(p)) * 70
                k = kd = p
            elif en == "scan":
                sy = max(0.03, D.ease_out(p))
            else:
                gl = (1 - p) * 10
                kd = p
        if e > 0:
            ex = c["exit"]
            if ex == "up":
                cy -= D.ease_out(e) * 60
                k = kd = 1 - e
            elif ex == "squash":
                sy = max(0.03, 1 - e)
                k = 1 + e
                kd = 1 - e
            elif ex == "side":
                cx += (1 if i % 2 else -1) * D.ease_out(e) * 260
                k = kd = 1 - e
            else:
                gl = e * 26
                k = kd = 1 - e
        fl = _flicker(t, self.seed + i, ctx.get("fxk", 1.0) or 0.4)
        lt2 = _glitch(lt, gl, self.seed + i + int(t * 24)) if gl > 0.5 else lt
        if sx != 1 or sy != 1:
            dk, lt2 = _resize(dk, sx, sy), _resize(lt2, sx, sy)
        _blend(img, dk, lt2, cx, cy, fl * k, kd)
        if sy < 0.5 or sx < 0.3:
            return
        cur = None
        for j, w in enumerate(c["words"]):
            if w["ws"] <= t + 0.02:
                cur = j
        for j, w in enumerate(c["words"]):
            wa = t - w["ws"]
            light, tw, g = text_sprite(w["text"], size, w["col"]["glow"])
            if wa < -0.02:                                                   # belum diucapkan: tampil redup (bisa dibaca duluan)
                spr = _resize(light, sx, sy) if (sx != 1 or sy != 1) else light
                _blend(img, None, spr, cx + w["cx"] * sx, cy + 2, fl * k * 0.4, 0)
                continue
            q = _clamp01(wa / 0.16)
            wsx = wsy = 1.0
            wk = 1.0
            dy = 0.0
            wgl = 0.0
            fx = w["wfx"]
            if q < 1:
                if fx == "pop":
                    wsx = wsy = 1 + 0.45 * (1 - D.ease_out(q))
                elif fx == "drop":
                    dy = -(1 - D.ease_out(q)) * 40
                elif fx == "glitch":
                    wgl = (1 - q) * 16
                elif fx == "flip":
                    wsx = max(0.05, D.ease_out(q))
                else:
                    wsx = wsy = 0.6 + 0.4 * D.ease_back(q)
                wk = 0.4 + 0.6 * q
            is_cur = j == cur
            if is_cur:
                wsx *= 1.1
                wsy *= 1.1
                wk *= 1.35
            else:
                wk *= 0.82
            spr = _glitch(light, wgl, j + int(t * 30)) if wgl > 0.5 else light
            if wsx * sx != 1 or wsy * sy != 1:
                spr = _resize(spr, wsx * sx, wsy * sy)
            x = cx + w["cx"] * sx
            _blend(img, None, spr, x, cy + dy + 2, fl * k * wk, 0)
            if is_cur and e == 0:
                y0 = int(cy + size * 0.52)
                x0, x1 = max(0, int(x - tw / 2)), min(img.shape[1], int(x + tw / 2))
                if 0 <= y0 < img.shape[0] - 4 and x1 > x0:
                    roi = img[y0:y0 + 4, x0:x1].astype(np.float32)
                    roi += _c(w["col"]["glow"]) * 0.9
                    img[y0:y0 + 4, x0:x1] = np.clip(roi, 0, 255).astype(np.uint8)


def sub_chunks(words, max_chars=24):
    """Potong kata (waktu TTS) jadi potongan subtitle; jeda > 0.28 dtk juga memotong."""
    chunks, cur = [], []
    for j, w in enumerate(words):
        txt = " ".join(words[i][2] for i in cur)
        gap = (w[0] - (words[cur[-1]][0] + words[cur[-1]][1])) if cur else 0
        if cur and (len(txt) + 1 + len(w[2]) > max_chars or (gap > 0.28 and len(txt) > 10)):
            chunks.append(cur)
            cur = []
        cur.append(j)
    if cur:
        chunks.append(cur)
    return chunks


def sub_on(st):
    """Subtitle hologram menggantikan subtitle kertas (mode 'semua')."""
    return mode_of(st) == "semua"
