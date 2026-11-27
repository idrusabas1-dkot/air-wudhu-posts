"""
Primitif animasi doodle (gambar tangan) untuk render 1080x1920.

- Drawing  : kumpulan goresan (stroke) + isian warna (fill). Bisa "digambar" bertahap (progress 0..1),
             garis bergoyang halus ("boil") supaya terasa digambar tangan.
- Teks     : PIL (anti-alias) + dukungan Arab (arabic_reshaper + python-bidi), wipe kiri->kanan / kanan->kiri.
- Ikon     : pustaka ikon prosedural (air, pancuran, masjid, buku, hati, dll).
- Tokoh    : rig karakter berpeci dengan pose (IK lengan) & ekspresi, mulut ikut suara.
"""
import functools
import math
import os
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import aw_common as C

W, H = 1080, 1920


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = rgb(c1) if isinstance(c1, str) else c1, rgb(c2) if isinstance(c2, str) else c2
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def ease_back(p):
    p = min(1.0, max(0.0, p))
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


# ================================================================ geometri
def resample(pts, step=7.0):
    pts = np.asarray(pts, dtype=np.float32)
    if len(pts) < 2:
        return pts
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    L = float(seg.sum())
    if L < 1e-3:
        return pts[:1]
    n = max(2, int(L / step) + 1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    d = np.linspace(0, L, n)
    return np.stack([np.interp(d, cum, pts[:, 0]), np.interp(d, cum, pts[:, 1])], axis=1).astype(np.float32)


def arc_pts(cx, cy, rx, ry, a0=0.0, a1=2 * math.pi, n=None):
    n = n or max(12, int(abs(a1 - a0) * max(rx, ry) / 6))
    t = np.linspace(a0, a1, n)
    return np.stack([cx + rx * np.cos(t), cy + ry * np.sin(t)], axis=1)


def bezier(p0, p1, p2, p3, n=30):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.asarray, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def quad(p0, p1, p2, n=24):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = map(np.asarray, (p0, p1, p2))
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def rrect_pts(x0, y0, x1, y1, r):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -math.pi / 2), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, math.pi / 2), (x0 + r, y0 + r, math.pi)):
        pts.append(arc_pts(cx, cy, r, r, a0, a0 + math.pi / 2, 10))
    p = np.concatenate(pts)
    return np.concatenate([p, p[:1]])


def _noise(n, seed, amp, freq=6):
    if amp <= 0 or n < 2:
        return np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(seed)
    k = max(2, n // freq + 2)
    base = rng.normal(size=(k, 2)).astype(np.float32)
    xs = np.linspace(0, k - 1, n)
    return np.stack([np.interp(xs, np.arange(k), base[:, 0]), np.interp(xs, np.arange(k), base[:, 1])], axis=1) * amp


# ================================================================ Drawing
class Drawing:
    """Goresan + isian. Koordinat lokal (piksel pada skala 1)."""

    def __init__(self):
        self.strokes = []     # (pts, color, width)
        self.fills = []       # (pts, color)
        self._len = None

    def line(self, pts, color, width=6, closed=False):
        pts = np.asarray(pts, np.float32)
        if closed:
            pts = np.concatenate([pts, pts[:1]])
        self.strokes.append((resample(pts), rgb(color) if isinstance(color, str) else color, width))
        self._len = None
        return self

    def fill(self, pts, color):
        self.fills.append((np.asarray(pts, np.float32), rgb(color) if isinstance(color, str) else color))
        return self

    def shape(self, pts, stroke, fill=None, width=6, closed=True):
        if fill:
            self.fill(pts, fill)
        return self.line(pts, stroke, width, closed)

    def circle(self, cx, cy, r, stroke, fill=None, width=6, ry=None):
        p = arc_pts(cx, cy, r, ry or r, -0.3, 2 * math.pi + 0.25)     # sedikit overshoot = khas coretan tangan
        if fill:
            self.fill(arc_pts(cx, cy, r, ry or r), fill)
        return self.line(p, stroke, width)

    def rrect(self, x0, y0, x1, y1, r, stroke, fill=None, width=6):
        p = rrect_pts(x0, y0, x1, y1, r)
        if fill:
            self.fill(p, fill)
        return self.line(p, stroke, width)

    def add(self, other, dx=0.0, dy=0.0, s=1.0):
        for p, c, w in other.strokes:
            self.strokes.append((p * s + (dx, dy), c, max(1, w * s)))
        for p, c in other.fills:
            self.fills.append((p * s + (dx, dy), c))
        self._len = None
        return self

    def length(self):
        if self._len is None:
            self._len = [float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 1.0 for p, _, _ in self.strokes]
        return self._len

    def render(self, img, x, y, s=1.0, progress=1.0, seed=0, wob=1.4, fill_p=None, alpha=1.0):
        """Gambar ke img (H,W,3 uint8). Return posisi ujung pena (x,y) kalau sedang menggambar, else None."""
        lens = self.length()
        total = sum(lens) or 1.0
        drawn = progress * total
        fp = clamp01((progress - 0.55) / 0.4) if fill_p is None else fill_p
        if self.fills and fp > 0:
            self._render_fills(img, x, y, s, fp * alpha, seed, wob)
        tip, acc = None, 0.0
        for i, (p, c, w) in enumerate(self.strokes):
            if acc >= drawn:
                break
            q = p * s + (x, y)
            if wob > 0:
                q = q + _noise(len(q), seed * 131 + i * 7, wob * (0.6 + s * 0.4))
            if acc + lens[i] > drawn:
                k = max(2, int(len(q) * (drawn - acc) / max(lens[i], 1e-3)))
                q = q[:k]
                tip = (float(q[-1][0]), float(q[-1][1]))
            acc += lens[i]
            col = c if alpha >= 1 else None
            if col is None:
                continue
            cv2.polylines(img, [np.round(q * 4).astype(np.int32)], False, col, max(1, int(round(w * s))), cv2.LINE_AA, shift=2)
        if alpha < 1:
            self._render_strokes_alpha(img, x, y, s, alpha, seed, wob)
        return tip

    def _bbox(self, x, y, s, pad=20):
        allp = [p for p, _, _ in self.strokes] + [p for p, _ in self.fills]
        if not allp:
            return None
        a = np.concatenate(allp) * s + (x, y)
        x0, y0 = np.floor(a.min(0) - pad).astype(int)
        x1, y1 = np.ceil(a.max(0) + pad).astype(int)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(img_w(), x1), min(img_h(), y1)
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    def _render_fills(self, img, x, y, s, a, seed, wob):
        bb = self._bbox(x, y, s)
        if not bb:
            return
        x0, y0, x1, y1 = bb
        roi = img[y0:y1, x0:x1]
        tmp = roi.copy()
        for j, (p, c) in enumerate(self.fills):
            q = p * s + (x - x0, y - y0)
            if wob > 0:
                q = q + _noise(len(q), seed * 17 + j, wob * 0.8, 10) + (2.5 * s, 2.0 * s)   # isian sedikit meleset = gaya spidol
            cv2.fillPoly(tmp, [np.round(q * 4).astype(np.int32)], c, cv2.LINE_AA, shift=2)
        if a >= 0.999:
            roi[:] = tmp
        else:
            cv2.addWeighted(tmp, a, roi, 1 - a, 0, dst=roi)

    def _render_strokes_alpha(self, img, x, y, s, a, seed, wob):
        bb = self._bbox(x, y, s)
        if not bb:
            return
        x0, y0, x1, y1 = bb
        roi = img[y0:y1, x0:x1]
        tmp = roi.copy()
        for i, (p, c, w) in enumerate(self.strokes):
            q = p * s + (x - x0, y - y0)
            if wob > 0:
                q = q + _noise(len(q), seed * 131 + i * 7, wob)
            cv2.polylines(tmp, [np.round(q * 4).astype(np.int32)], False, c, max(1, int(round(w * s))), cv2.LINE_AA, shift=2)
        cv2.addWeighted(tmp, a, roi, 1 - a, 0, dst=roi)


_IMG_W, _IMG_H = W, H


def img_w():
    return _IMG_W


def img_h():
    return _IMG_H


# ================================================================ teks
FONTS = {
    "hand": "Kalam-Bold.ttf",
    "hand_reg": "Kalam-Regular.ttf",
    "arab": "Amiri-Regular.ttf",
    "arab_bold": "Amiri-Bold.ttf",
}


@functools.lru_cache(maxsize=64)
def font(name, size):
    p = os.path.join(C.FONT_DIR, FONTS.get(name, name))
    if not os.path.exists(p):
        for alt in ("C:/Windows/Fonts/segoeprb.ttf", "C:/Windows/Fonts/arial.ttf"):
            if os.path.exists(alt):
                p = alt
                break
    return ImageFont.truetype(p, size)


_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def is_arabic(s):
    return bool(_ARABIC.search(s or ""))


_RESHAPER = None


def shape_arabic(s):
    global _RESHAPER
    from bidi.algorithm import get_display
    if _RESHAPER is None:
        from arabic_reshaper import ArabicReshaper
        _RESHAPER = ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True})
    return get_display(_RESHAPER.reshape(s))


def _tokens(text):
    """'kata *penting*? lain' -> [(kata, False, False), (penting, True, False), (?, False, True), ...]; glue=tanpa spasi."""
    out, hi, glue = [], False, False
    for m in re.finditer(r"\*|\s+|[^\s*]+", text or ""):
        tok = m.group(0)
        if tok == "*":
            hi = not hi
            continue
        if tok.isspace():
            glue = False
            continue
        out.append((tok, hi, glue and bool(out)))
        glue = True
    return out


@functools.lru_cache(maxsize=256)
def text_block(text, fname, size, color, max_w, align="center", hi_color=None, line_h=1.18, max_lines=0,
               stroke=0, stroke_color=None):
    """Render teks ber-wrap ke RGBA. Return (arr RGBA, [rect baris (x0,y0,x1,y1)], rtl)."""
    f = font(fname, size)
    rtl = is_arabic(text)
    toks = [(w, False, False) for w in text.split()] if rtl else _tokens(text)
    space = f.getlength(" ")
    lines, cur, cw = [], [], 0.0

    def wlen(w):
        return f.getlength(shape_arabic(w) if rtl else w)

    for w, hi, gl in toks:
        lw = wlen(w)
        if cur and not gl and cw + space + lw > max_w:
            lines.append(cur)
            cur, cw = [], 0.0
        cur.append((w, hi, gl))
        cw += (space if len(cur) > 1 and not gl else 0) + lw
    if cur:
        lines.append(cur)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lw, lh, lg = lines[-1][-1]
        lines[-1][-1] = (lw.rstrip(".,;:") + "…", lh, lg)
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * line_h)
    pad = 8 + stroke
    widths = []
    for ln in lines:
        if rtl:
            widths.append(f.getlength(shape_arabic(" ".join(t[0] for t in ln))))
        else:
            widths.append(sum(f.getlength(t[0]) for t in ln) + space * sum(1 for j, t in enumerate(ln) if j and not t[2]))
    bw = int(max(widths or [1])) + pad * 2
    bh = lh * len(lines) + pad * 2 + (desc if rtl else 0)
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rects = []
    col = color if isinstance(color, tuple) else rgb(color)
    hcol = (hi_color if isinstance(hi_color, tuple) else rgb(hi_color)) if hi_color else col
    sc = (stroke_color if isinstance(stroke_color, tuple) else rgb(stroke_color)) if stroke_color else None
    for i, ln in enumerate(lines):
        lw = widths[i]
        x = pad + (bw - 2 * pad - lw) / 2 if align == "center" else (bw - pad - lw if (align == "right" or rtl) else pad)
        y = pad + i * lh
        rects.append((int(x), int(y), int(x + lw), int(y + lh)))
        if rtl:
            dr.text((x, y), shape_arabic(" ".join(t[0] for t in ln)), font=f, fill=col + (255,),
                    stroke_width=stroke, stroke_fill=(sc + (255,)) if sc else None)
            continue
        for j, (w, hi, gl) in enumerate(ln):
            if j and gl:
                x -= space
            dr.text((x, y), w, font=f, fill=(hcol if hi else col) + (255,), stroke_width=stroke,
                    stroke_fill=(sc + (255,)) if sc else None)
            x += f.getlength(w) + space
    return np.array(im), rects, rtl


def fit_text(text, fname, size, color, max_w, max_h, min_size=26, **kw):
    """Perkecil huruf sampai muat dalam max_h."""
    s = size
    while True:
        arr, rects, rtl = text_block(text, fname, s, color, max_w, **kw)
        if arr.shape[0] <= max_h or s <= min_size:
            return arr, rects, rtl, s
        s = max(min_size, int(s * 0.92))


def blit(img, rgba, x, y, reveal=1.0, rects=None, rtl=False, scale=1.0, alpha=1.0, anchor="tl"):
    """Tempel RGBA ke img. reveal<1 -> wipe per baris. Return ujung pena (x,y) saat wipe berjalan."""
    a = rgba
    if scale != 1.0:
        nw, nh = max(1, int(a.shape[1] * scale)), max(1, int(a.shape[0] * scale))
        a = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_LINEAR)
    h, w = a.shape[:2]
    if anchor == "c":
        x, y = x - w / 2, y - h / 2
    elif anchor == "tc":
        x = x - w / 2
    x, y = int(round(x)), int(round(y))
    alpha_ch = a[:, :, 3].astype(np.float32) / 255.0 * alpha
    tip = None
    if reveal < 1.0 and rects:
        mask = np.zeros_like(alpha_ch)
        total = sum(r[2] - r[0] for r in rects) or 1
        left = reveal * total
        for r in rects:
            rw = r[2] - r[0]
            if left <= 0:
                break
            show = min(rw, left)
            r = [int(v * scale) for v in r]
            show_s = int(show * scale)
            if rtl:
                mask[r[1]:r[3] + 6, r[2] - show_s:r[2]] = 1
                tip = (x + r[2] - show_s, y + (r[1] + r[3]) / 2)
            else:
                mask[r[1]:r[3] + 6, r[0]:r[0] + show_s] = 1
                tip = (x + r[0] + show_s, y + (r[1] + r[3]) / 2)
            left -= rw
        alpha_ch = alpha_ch * mask
    elif reveal <= 0:
        return None
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return tip
    sub = a[y0 - y:y1 - y, x0 - x:x1 - x, :3].astype(np.float32)
    al = alpha_ch[y0 - y:y1 - y, x0 - x:x1 - x, None]
    roi = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (roi * (1 - al) + sub * al).astype(np.uint8)
    return tip


# ================================================================ pena
def pen(img, tip, ink):
    """Spidol kecil yang 'sedang menggambar' di ujung goresan."""
    if not tip:
        return
    x, y = tip
    d = Drawing()
    body = np.array([(0, 0), (16, -26), (40, -6), (22, 18)], np.float32)
    d.fill(np.array([(0, 0), (14, -10), (22, 2)]), ink)
    d.shape(body + (8, -6), "#333333", "#E8E2D0", 4)
    d.shape(np.array([(30, -40), (150, -150), (174, -126), (54, -16)], np.float32), "#333333", "#3E8ED0", 4)
    d.render(img, x, y, 0.8, 1.0, 0, 0)


# ================================================================ ikon
ICON_ALIASES = {
    "air": "tetes", "tetes": "tetes", "tetesan": "tetes", "water": "tetes", "bersih": "tetes", "suci": "tetes",
    "mandi": "pancuran", "pancuran": "pancuran", "shower": "pancuran", "keramas": "pancuran",
    "gayung": "gayung", "ember": "gayung",
    "masjid": "masjid", "mesjid": "masjid", "shalat": "sajadah", "salat": "sajadah", "sholat": "sajadah", "sajadah": "sajadah",
    "quran": "buku", "alquran": "buku", "al-quran": "buku", "buku": "buku", "kitab": "buku", "ilmu": "buku", "hadits": "buku",
    "hati": "hati", "cinta": "hati", "kasih": "hati", "sayang": "hati", "keluarga": "keluarga", "nikah": "cincin", "cincin": "cincin",
    "benar": "centang", "centang": "centang", "boleh": "centang", "wajib": "centang", "ya": "centang", "sah": "centang",
    "salah": "silang", "silang": "silang", "larangan": "silang", "haram": "silang", "tidak": "silang", "batal": "silang",
    "waktu": "jam", "jam": "jam", "segera": "jam",
    "bulan": "bulan", "islam": "bulan", "malam": "bulan", "ramadhan": "bulan", "ramadan": "bulan",
    "bintang": "bintang", "pahala": "bintang", "keutamaan": "bintang",
    "ide": "lampu", "lampu": "lampu", "hikmah": "lampu", "fakta": "lampu",
    "tanya": "tanya", "bingung": "tanya", "pertanyaan": "tanya", "seru": "seru", "penting": "seru", "peringatan": "seru",
    "kabah": "kabah", "ka'bah": "kabah", "haji": "kabah", "umrah": "kabah", "kiblat": "kabah",
    "sabun": "sabun", "kebersihan": "sabun",
    "segar": "daun", "daun": "daun", "sehat": "daun", "kesehatan": "daun", "alam": "daun",
    "energi": "petir", "semangat": "petir", "kuat": "petir", "tenaga": "petir",
    "matahari": "matahari", "pagi": "matahari", "siang": "matahari",
    "doa": "tangan", "tangan": "tangan", "berdoa": "tangan", "niat": "tangan",
    "tidur": "tidur", "istirahat": "tidur", "mata": "mata", "lihat": "mata", "aurat": "mata",
    "makan": "piring", "makanan": "piring", "puasa": "piring", "rezeki": "koin", "uang": "koin", "sedekah": "koin", "zakat": "koin",
    "rumah": "rumah", "kamar": "rumah",
    "wajah": "wajah", "muka": "wajah", "kepala": "kepala", "rambut": "kepala", "telinga": "telinga", "kaki": "kaki", "kumur": "mulut", "mulut": "mulut",
    "hidung": "hidung", "api": "api", "panas": "api", "neraka": "api", "dosa": "awan", "kotor": "awan", "najis": "awan", "hadats": "awan", "maksiat": "awan",
    "surga": "pohon", "taman": "pohon", "pohon": "pohon", "adil": "timbangan", "timbangan": "timbangan", "seimbang": "timbangan",
    "istri": "istri", "suami": "suami", "anak": "anak", "putri": "anak_p", "bayi": "bayi", "ibu": "ibu", "ayah": "ayah",
    "kakek": "kakek", "nenek": "nenek", "teman": "teman", "tetangga": "teman", "tas": "tas", "kerja": "tas", "nafkah": "koin", "gaji": "koin",
    "masak": "panci", "dapur": "panci", "panci": "panci", "sekolah": "sekolah", "anak-anak": "anak",
    "senang": "senyum", "bahagia": "senyum", "gembira": "senyum", "syukur": "senyum", "tersenyum": "senyum", "sedih": "sedih", "menangis": "sedih", "awan": "awan", "senyum": "senyum", "angka": "bintang",
}
ICON_NAMES = sorted(set(ICON_ALIASES.values()))


def icon_key(name):
    n = (name or "").strip().lower()
    if n in ICON_ALIASES:
        return ICON_ALIASES[n]
    for k, v in ICON_ALIASES.items():
        if k in n:
            return v
    return "bintang"


def icon(name, size, P):
    """Ikon di kotak [0,size]. P = palet (ink, accent, accent2, water, red...)."""
    k = icon_key(name)
    s = size / 100.0
    ink, w = P["ink"], 5
    d = Drawing()
    fn = _ICONS.get(k, _ICONS["bintang"])
    fn(d, ink, P, w)
    out = Drawing()
    out.add(d, 0, 0, s)
    return out


def _i_tetes(d, ink, P, w):
    p = np.concatenate([quad((50, 8), (50, 8), (50, 8), 2), bezier((50, 8), (30, 40), (18, 58), (24, 72)),
                        bezier((24, 72), (32, 96), (68, 96), (76, 72)), bezier((76, 72), (82, 58), (70, 40), (50, 8))])
    d.shape(p, ink, P["water"], w)
    d.line(quad((36, 66), (36, 80), (48, 84)), "#FFFFFF", 5)


def _i_pancuran(d, ink, P, w):
    d.line([(20, 8), (20, 30), (52, 30)], ink, w)
    d.shape(np.concatenate([[(40, 30)], arc_pts(56, 40, 20, 12, math.pi, 2 * math.pi, 12), [(72, 40)]]), ink, P["mute2"], w)
    for i, x in enumerate((42, 52, 62, 72)):
        for j in range(2):
            y = 54 + j * 18 + (i % 2) * 8
            d.line([(x - 2, y), (x - 5, y + 9)], P["water"], 5)


def _i_gayung(d, ink, P, w):
    d.shape(np.concatenate([[(14, 40)], arc_pts(42, 40, 28, 30, 0, math.pi, 16)[::-1][::-1], [(70, 40)]]), ink, P["accent"], w)
    d.line(arc_pts(42, 40, 28, 30, 0, math.pi, 16), ink, w)
    d.line([(14, 40), (70, 40)], ink, w)
    d.shape([(70, 36), (96, 26), (98, 34), (72, 46)], ink, P["accent2"], w)
    d.shape(arc_pts(42, 40, 22, 5), P["water"], P["water"], 3)


def _i_masjid(d, ink, P, w):
    d.shape([(14, 92), (14, 52), (86, 52), (86, 92)], ink, "#FFFFFF", w)
    d.shape(np.concatenate([arc_pts(50, 52, 26, 30, math.pi, 2 * math.pi, 18)]), ink, P["accent"], w)
    d.line([(50, 22), (50, 10)], ink, 4)
    d.line(arc_pts(52, 8, 5, 5, 1.2, 5.6, 10), ink, 3)
    d.shape([(42, 92), (42, 72), (50, 64), (58, 72), (58, 92)], ink, P["accent2"], 4)
    d.shape([(88, 92), (88, 30), (96, 30), (96, 92)], ink, "#FFFFFF", 4)
    d.shape([(86, 30), (92, 18), (98, 30)], ink, P["accent"], 4)


def _i_buku(d, ink, P, w):
    d.shape([(50, 26), (12, 18), (12, 80), (50, 88)], ink, "#FFFFFF", w)
    d.shape([(50, 26), (88, 18), (88, 80), (50, 88)], ink, "#FFFFFF", w)
    d.line([(50, 26), (50, 88)], ink, w)
    for y in (36, 48, 60):
        d.line([(20, y), (42, y + 3)], P["mute"], 3)
        d.line([(58, y + 3), (80, y)], P["mute"], 3)
    d.shape([(8, 82), (50, 94), (92, 82), (92, 88), (50, 99), (8, 88)], ink, P["accent"], 4)


def _i_hati(d, ink, P, w):
    p = np.concatenate([bezier((50, 30), (40, 8), (6, 14), (12, 42)), bezier((12, 42), (18, 64), (42, 78), (50, 92)),
                        bezier((50, 92), (58, 78), (82, 64), (88, 42)), bezier((88, 42), (94, 14), (60, 8), (50, 30))])
    d.shape(p, ink, P["red"], w)
    d.line(quad((24, 34), (26, 24), (36, 22)), "#FFFFFF", 5)


def _i_cincin(d, ink, P, w):
    d.circle(50, 62, 30, ink, None, 9)
    d.circle(50, 62, 30, P["accent2"], None, 5)
    d.shape([(38, 30), (50, 14), (62, 30), (50, 40)], ink, P["water"], 4)


def _i_centang(d, ink, P, w):
    d.circle(50, 50, 42, ink, P["ok"], w)
    d.line([(30, 52), (44, 66), (72, 34)], "#FFFFFF", 9)


def _i_silang(d, ink, P, w):
    d.circle(50, 50, 42, ink, P["red"], w)
    d.line([(33, 33), (67, 67)], "#FFFFFF", 9)
    d.line([(67, 33), (33, 67)], "#FFFFFF", 9)


def _i_jam(d, ink, P, w):
    d.circle(50, 52, 42, ink, "#FFFFFF", w)
    for k in range(12):
        a = k * math.pi / 6
        d.line([(50 + 34 * math.cos(a), 52 + 34 * math.sin(a)), (50 + 38 * math.cos(a), 52 + 38 * math.sin(a))], ink, 3)
    d.line([(50, 52), (50, 26)], ink, 6)
    d.line([(50, 52), (68, 60)], P["red"], 5)


def _i_bulan(d, ink, P, w):
    outer = arc_pts(46, 50, 40, 40, 0.75, 2 * math.pi - 0.75, 30)
    inner = arc_pts(62, 44, 32, 32, 2 * math.pi - 1.05, 1.05, 24)
    p = np.concatenate([outer, inner])
    d.shape(p, ink, P["accent2"], w)
    _star(d, 80, 30, 12, ink, P["accent2"], 4)


def _star(d, cx, cy, r, ink, fill, w):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.shape(pts, ink, fill, w)


def _i_bintang(d, ink, P, w):
    _star(d, 50, 54, 44, ink, P["accent2"], w)


def _i_lampu(d, ink, P, w):
    p = np.concatenate([arc_pts(50, 40, 30, 30, 2.4, 2 * math.pi + 0.74, 26), [(66, 64), (62, 74), (38, 74), (34, 64)]])
    d.shape(p, ink, "#FFE27A", w)
    d.shape([(38, 76), (62, 76), (60, 90), (40, 90)], ink, P["mute2"], 4)
    for a in (-2.6, -2.0, -1.57, -1.14, -0.55):
        d.line([(50 + 38 * math.cos(a), 40 + 38 * math.sin(a)), (50 + 48 * math.cos(a), 40 + 48 * math.sin(a))], P["accent2"], 4)
    d.line(quad((44, 62), (46, 46), (52, 52)), ink, 3)


def _i_tanya(d, ink, P, w):
    d.line(np.concatenate([arc_pts(50, 34, 22, 22, math.pi * 1.05, math.pi * 2.35, 20), quad((60, 52), (50, 58), (50, 68))]),
           P.get("hi", P["accent"]), 11)
    d.circle(50, 86, 5, P.get("hi", P["accent"]), P.get("hi", P["accent"]), 6)


def _i_seru(d, ink, P, w):
    d.shape([(42, 10), (58, 10), (54, 66), (46, 66)], ink, P["red"], w)
    d.circle(50, 84, 8, ink, P["red"], 5)


def _i_kabah(d, ink, P, w):
    d.shape([(14, 36), (58, 26), (90, 36), (90, 86), (58, 96), (14, 86)], ink, "#1E1E1E", w)
    d.line([(58, 26), (58, 96)], "#444444", 3)
    d.fill([(14, 46), (58, 37), (90, 46), (90, 54), (58, 45), (14, 54)], P["accent2"])
    d.line([(14, 46), (58, 37), (90, 46)], P["accent2"], 3)
    d.shape([(30, 60), (40, 58), (40, 80), (30, 82)], P["accent2"], None, 3)


def _i_sabun(d, ink, P, w):
    d.rrect(14, 46, 76, 84, 12, ink, "#F7B4C8", w)
    d.line([(24, 58), (50, 56)], "#FFFFFF", 4)
    for cx, cy, r in ((70, 28, 12), (88, 44, 8), (52, 22, 7)):
        d.circle(cx, cy, r, P["water"], None, 4)


def _i_daun(d, ink, P, w):
    p = np.concatenate([bezier((14, 86), (10, 40), (50, 10), (90, 12)), bezier((90, 12), (88, 56), (60, 90), (14, 86))])
    d.shape(p, ink, P["ok"], w)
    d.line(quad((18, 82), (46, 52), (78, 22)), ink, 4)


def _i_petir(d, ink, P, w):
    d.shape([(58, 6), (20, 56), (46, 56), (36, 96), (82, 38), (54, 38), (68, 6)], ink, "#FFD43B", w)


def _i_matahari(d, ink, P, w):
    d.circle(50, 50, 22, ink, "#FFC83D", w)
    for k in range(8):
        a = k * math.pi / 4
        d.line([(50 + 30 * math.cos(a), 50 + 30 * math.sin(a)), (50 + 44 * math.cos(a), 50 + 44 * math.sin(a))], P["accent2"], 6)


def _i_tangan(d, ink, P, w):
    for sx in (1, -1):
        cx = 50 + sx * 16
        p = [(cx - sx * 4, 90), (cx - sx * 2, 50), (cx + sx * 6, 22), (cx + sx * 20, 26), (cx + sx * 18, 60), (cx + sx * 14, 90)]
        d.shape(bezier(p[0], p[1], p[2], p[3], 16).tolist() + bezier(p[3], p[4], p[5], p[0], 16).tolist(), ink, P["skin"], w)
    d.line([(36, 96), (64, 96)], ink, 4)


def _i_sajadah(d, ink, P, w):
    d.shape([(26, 8), (74, 8), (74, 92), (26, 92)], ink, P["accent"], w)
    d.shape([(34, 34), (50, 18), (66, 34), (66, 82), (34, 82)], P["accent2"], None, 4)
    for x in (30, 40, 50, 60, 70):
        d.line([(x, 92), (x, 99)], ink, 3)


def _i_tidur(d, ink, P, w):
    d.shape(np.concatenate([arc_pts(40, 58, 30, 30, 0.6, 5.7, 24)]), ink, "#9DB7E8", w)
    for i, (x, y, sz) in enumerate(((66, 40, 14), (80, 24, 10), (90, 10, 7))):
        d.line([(x, y), (x + sz, y), (x, y + sz), (x + sz, y + sz)], ink, 4)


def _i_mata(d, ink, P, w):
    d.shape(np.concatenate([quad((8, 50), (50, 10), (92, 50)), quad((92, 50), (50, 90), (8, 50))]), ink, "#FFFFFF", w)
    d.circle(50, 50, 16, ink, P["accent"], 4)
    d.circle(50, 50, 6, ink, ink, 3)


def _i_piring(d, ink, P, w):
    d.circle(50, 58, 40, ink, "#FFFFFF", w, ry=18)
    d.circle(50, 56, 24, P["mute2"], None, 3, ry=9)
    d.line([(14, 20), (14, 46)], ink, 4)
    d.line([(86, 20), (86, 46)], ink, 4)


def _i_koin(d, ink, P, w):
    d.circle(56, 56, 34, ink, P["accent2"], w)
    d.circle(56, 56, 24, ink, None, 3)
    d.circle(34, 40, 26, ink, "#FFD43B", w)


def _i_rumah(d, ink, P, w):
    d.shape([(8, 50), (50, 12), (92, 50)], ink, P["red"], w)
    d.shape([(18, 46), (82, 46), (82, 92), (18, 92)], ink, "#FFFFFF", w)
    d.shape([(42, 92), (42, 64), (58, 64), (58, 92)], ink, P["accent2"], 4)



# ---------------------------------------------------------------- ikon tambahan (anggota tubuh wudhu, api, awan, pohon, dll)
def _union_poly(circles, rects=()):
    """Gabungan lingkaran/persegi -> kontur luar (poligon di kotak 100x100) agar bisa digambar satu garis tepi."""
    k = 4
    m = np.zeros((100 * k, 100 * k), np.uint8)
    for cx, cy, r in circles:
        cv2.circle(m, (int(cx * k), int(cy * k)), int(r * k), 255, -1, cv2.LINE_AA)
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(m, (int(x0 * k), int(y0 * k)), (int(x1 * k), int(y1 * k)), 255, -1)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2) / float(k)
    return c


def _i_wajah(d, ink, P, w):
    d.circle(50, 54, 36, ink, P["skin"], w)
    d.shape(arc_pts(50, 54, 37, 33, math.pi * 1.13, math.pi * 1.87, 18), ink, "#3A2A22", w)
    for x in (37, 63):
        d.circle(x, 52, 3.6, ink, ink, 2)
    d.line(quad((38, 68), (50, 78), (62, 68)), ink, 4)
    d.circle(30, 62, 5, "#F2A59B", "#F2A59B", 1)
    d.circle(70, 62, 5, "#F2A59B", "#F2A59B", 1)
    for x, y in ((12, 22), (88, 26)):                                     # tetes air membasuh wajah
        d.shape(np.concatenate([bezier((x, y - 9), (x - 7, y + 1), (x - 5, y + 9), (x, y + 9), 8), bezier((x, y + 9), (x + 5, y + 9), (x + 7, y + 1), (x, y - 9), 8)]),
                ink, P["water"], 3)


def _i_kepala(d, ink, P, w):
    d.circle(50, 58, 32, ink, P["skin"], w)
    d.shape(arc_pts(50, 58, 33, 33, math.pi * 1.13, math.pi * 1.87, 20), ink, "#2B2B2B", w)
    d.line(quad((40, 66), (50, 74), (60, 66)), ink, 4)
    for x in (39, 61):
        d.circle(x, 56, 3, ink, ink, 2)
    for x in (24, 50, 76):                                                # tetes air di kepala
        d.shape(np.concatenate([bezier((x, 4), (x - 5, 11), (x - 4, 17), (x, 17), 8), bezier((x, 17), (x + 4, 17), (x + 5, 11), (x, 4), 8)]), ink, P["water"], 3)


def _i_telinga(d, ink, P, w):
    p = np.concatenate([bezier((46, 10), (14, 8), (10, 52), (30, 72), 14), bezier((30, 72), (42, 84), (40, 92), (56, 90), 10),
                        bezier((56, 90), (82, 84), (88, 20), (46, 10), 16)])
    d.shape(p, ink, P["skin"], w)
    d.line(bezier((46, 28), (66, 28), (70, 54), (52, 62), 12), ink, 4)
    d.line(bezier((52, 62), (44, 66), (42, 74), (48, 78), 8), ink, 4)


def _i_kaki(d, ink, P, w):
    p = [(36, 6), (62, 6), (62, 52), (84, 60), (94, 78), (92, 92), (30, 92), (26, 70), (36, 52)]
    d.shape(p, ink, P["skin"], w)
    for i, (x, r) in enumerate(((88, 4), (78, 3.6), (68, 3.2))):         # jari kaki
        d.circle(x, 88 - i * 0, r, ink, P["skin"], 3)
    for x, y in ((14, 64), (16, 82)):                                     # tetes air
        d.shape(np.concatenate([bezier((x, y - 8), (x - 6, y), (x - 5, y + 8), (x, y + 8), 8), bezier((x, y + 8), (x + 5, y + 8), (x + 6, y), (x, y - 8), 8)]), ink, P["water"], 3)


def _i_mulut(d, ink, P, w):
    up = np.concatenate([bezier((10, 52), (26, 30), (42, 38), (50, 44), 10), bezier((50, 44), (58, 38), (74, 30), (90, 52), 10)])
    lo = bezier((90, 52), (80, 84), (20, 84), (10, 52), 18)
    d.shape(np.concatenate([up, lo]), ink, "#D9594C", w)
    d.line([(12, 52), (50, 58), (88, 52)], ink, 4)
    d.shape(np.concatenate([bezier((30, 20), (24, 12), (24, 8), (30, 6), 6), bezier((30, 6), (36, 8), (36, 14), (30, 20), 6)]), ink, P["water"], 3)


def _i_api(d, ink, P, w):
    p = np.concatenate([bezier((50, 4), (34, 28), (14, 40), (18, 66), 14), bezier((18, 66), (22, 92), (78, 92), (82, 66), 14),
                        bezier((82, 66), (84, 46), (66, 40), (62, 24), 12), bezier((62, 24), (58, 30), (54, 20), (50, 4), 10)])
    d.shape(p, ink, "#F2762E", w)
    q = np.concatenate([bezier((50, 40), (42, 56), (32, 62), (36, 76), 10), bezier((36, 76), (40, 90), (62, 90), (64, 76), 10),
                        bezier((64, 76), (66, 64), (56, 56), (50, 40), 10)])
    d.shape(q, "#F2762E", "#FFD84D", 2)


def _i_awan(d, ink, P, w):
    poly = _union_poly([(28, 62, 16), (44, 44, 20), (66, 46, 22), (78, 64, 16), (50, 66, 18)], [(28, 62, 78, 80)])
    d.shape(poly, ink, "#9AA3AD", w)
    for x in (34, 52, 70):
        d.line([(x, 86), (x - 4, 96)], P["water"], 4)


def _i_pohon(d, ink, P, w):
    d.shape([(44, 52), (56, 52), (58, 94), (42, 94)], ink, "#8A5A3A", w)
    poly = _union_poly([(30, 40, 20), (50, 26, 24), (70, 40, 20), (50, 50, 20)])
    d.shape(poly, ink, "#4CAF6A", w)
    for x, y in ((38, 36), (60, 30), (58, 48)):
        d.circle(x, y, 3.2, "#E0A100", "#FFD84D", 2)


def _i_timbangan(d, ink, P, w):
    d.line([(50, 14), (50, 90)], ink, w)
    d.line([(26, 90), (74, 90)], ink, w)
    d.line([(14, 28), (86, 28)], ink, w)
    for cx in (14, 86):
        d.line([(cx, 28), (cx - 10, 54)], ink, 3)
        d.line([(cx, 28), (cx + 10, 54)], ink, 3)
        d.shape(np.concatenate([[(cx - 14, 54)], arc_pts(cx, 54, 14, 12, 0, math.pi, 12), [(cx + 14, 54)]]), ink, P["accent2"], 4)
    d.circle(50, 14, 6, ink, P["accent"], 4)


def _i_senyum(d, ink, P, w):
    d.circle(50, 50, 40, ink, "#FFD84D", w)
    for x in (36, 64):
        d.circle(x, 42, 4.5, ink, ink, 2)
    d.line(bezier((28, 58), (36, 80), (64, 80), (72, 58), 14), ink, 5)


def _i_sedih(d, ink, P, w):
    d.circle(50, 50, 40, ink, "#FFD84D", w)
    for x in (36, 64):
        d.circle(x, 42, 4.5, ink, ink, 2)
    d.line(bezier((30, 72), (38, 58), (62, 58), (70, 72), 14), ink, 5)
    d.shape(np.concatenate([bezier((70, 50), (64, 58), (66, 66), (70, 66), 8), bezier((70, 66), (75, 66), (76, 58), (70, 50), 8)]), ink, P["water"], 3)


def _i_hidung(d, ink, P, w):
    p = np.concatenate([bezier((46, 8), (42, 40), (30, 58), (22, 70), 14), bezier((22, 70), (20, 86), (40, 92), (50, 86), 10),
                        bezier((50, 86), (60, 92), (80, 86), (78, 70), 10), bezier((78, 70), (70, 58), (58, 40), (54, 8), 14)])
    d.shape(p, ink, P["skin"], w)
    d.circle(38, 78, 4, ink, ink, 2)
    d.circle(62, 78, 4, ink, ink, 2)
    d.shape(np.concatenate([bezier((86, 20), (80, 28), (82, 36), (86, 36), 8), bezier((86, 36), (91, 36), (92, 28), (86, 20), 8)]), ink, P["water"], 3)


# ---------------------------------------------------------------- ikon tokoh (wajah+bahu, digambar aw_cerita) & benda cerita
def _mk_person_icon(kind):
    def fn(d, ink, P, w):
        import aw_cerita as CT
        CT.portrait(d, kind, ink)
    return fn


for _k in ("istri", "suami", "anak", "anak_p", "bayi", "ibu", "ayah", "kakek", "nenek", "teman", "keluarga"):
    globals()["_i_" + _k] = _mk_person_icon(_k)


def _i_tas(d, ink, P, w):
    d.shape(bezier((36, 38), (36, 14), (64, 14), (64, 38), 10), ink, None, w, closed=False)
    d.shape(rrect_pts(10, 34, 90, 86, 10), ink, "#B88A5E", w)
    d.line([(10, 56), (90, 56)], ink, 4)
    d.shape(rrect_pts(43, 50, 57, 64, 3), ink, P["accent2"], 3)


def _i_panci(d, ink, P, w):
    d.shape(rrect_pts(20, 46, 80, 86, 10), ink, "#C9D1D8", w)
    d.shape(arc_pts(50, 46, 34, 9), ink, "#E3E8EC", 4)
    d.circle(14, 58, 6, ink, None, 4)
    d.circle(86, 58, 6, ink, None, 4)
    d.circle(50, 34, 4, ink, ink, 2)
    for x in (36, 50, 64):
        d.line(quad((x, 28), (x + 7, 20), (x, 10)), P["mute2"], 4)


def _i_sekolah(d, ink, P, w):
    d.shape([(8, 44), (50, 16), (92, 44)], ink, P["red"], w)
    d.shape([(16, 44), (84, 44), (84, 90), (16, 90)], ink, "#FFFFFF", w)
    d.shape([(42, 90), (42, 64), (58, 64), (58, 90)], ink, P["accent2"], 4)
    d.shape([(24, 54), (36, 54), (36, 66), (24, 66)], ink, "#CFEAF6", 3)
    d.shape([(64, 54), (76, 54), (76, 66), (64, 66)], ink, "#CFEAF6", 3)
    d.line([(50, 16), (50, 4)], ink, 4)
    d.shape([(50, 4), (66, 9), (50, 14)], ink, P["accent"], 3)


_ICONS = {k[3:]: v for k, v in globals().items() if k.startswith("_i_")}


# ================================================================ tokoh
POSES = {
    # target tangan (kiri, kanan) relatif kaki tengah, tokoh setinggi ±700 px
    "diam": ((-112, -206), (112, -206)),
    "jelasin": ((-112, -206), (205, -390)),
    "tunjuk": ((-112, -206), (215, -640)),
    "mikir": ((-112, -206), (62, -470)),
    "senang": ((-205, -690), (205, -690)),
    "bingung": ((-205, -430), (205, -430)),
    "doa": ((-60, -420), (60, -420)),
    "lambai": ((-112, -206), (200, -660)),
}
EXPRS = ("biasa", "senang", "bingung", "kaget", "serius")


def _ik(sh, target, a, b, bend):
    sx, sy = sh
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    d = max(1e-3, min(math.hypot(dx, dy), a + b - 1))
    base = math.atan2(dy, dx)
    cos_a = (a * a + d * d - b * b) / (2 * a * d)
    ac = math.acos(max(-1, min(1, cos_a)))
    sols = [(sx + a * math.cos(base + k * ac), sy + a * math.sin(base + k * ac)) for k in (1, -1)]
    ex, ey = max(sols, key=lambda e: e[0] * bend + 0.35 * e[1])     # siku ke arah luar badan & sedikit ke bawah
    ux, uy = (tx - ex), (ty - ey)
    n = math.hypot(ux, uy) or 1
    return (ex, ey), (ex + ux / n * b, ey + uy / n * b)


def character(st, P, pose="diam", expr="biasa", mouth=0.0, blink=False, t=0.0, talking=False):
    """Drawing tokoh berpeci; origin di tengah bawah (kaki)."""
    ink, w = P["ink_char"], 6
    skin, shirt, pants, peci = st["skin"], st["shirt"], st["pants"], st["peci"]
    d = Drawing()
    bob = math.sin(t * 9) * 4 if talking else math.sin(t * 2.2) * 2
    # kaki & sandal
    for sx in (-1, 1):
        d.line([(sx * 34, -230), (sx * 42, -14)], ink, 36)
        d.line([(sx * 34, -232), (sx * 42, -16)], pants, 26)
    d.shape(arc_pts(-50, -8, 32, 12), ink, "#6B4A2E", 4)
    d.shape(arc_pts(50, -8, 32, 12), ink, "#6B4A2E", 4)
    # badan (baju koko)
    by = bob * 0.3
    body = np.concatenate([[(-92, -458 + by)], bezier((-92, -458 + by), (-118, -380), (-118, -300), (-108, -222)),
                           [(108, -222)], bezier((108, -222), (118, -300), (118, -380), (92, -458 + by))[::1]])
    d.shape(body, ink, shirt, w)
    d.line([(0, -452 + by), (0, -260)], mix(shirt, "#000000", 0.35), 4)
    for yy in (-420, -380, -340):
        d.circle(0, yy + by, 5, mix(shirt, "#FFFFFF", 0.6), mix(shirt, "#FFFFFF", 0.6), 2)
    d.line(np.concatenate([[(-34, -458 + by)], quad((-34, -458 + by), (0, -430 + by), (34, -458 + by))]), ink, 5)
    # lengan (IK)
    targets = POSES.get(pose, POSES["diam"])
    for side, (tx, ty) in zip((-1, 1), targets):
        if talking and pose in ("jelasin", "tunjuk", "lambai"):
            if side == 1:
                tx += math.sin(t * 5) * (22 if pose == "lambai" else 10)
                ty += math.cos(t * 4) * 8
        elif pose == "diam" or (pose != "senang" and side == -1):
            ty += math.sin(t * 2.2 + side) * 3
        sh = (side * 90, -446 + by)
        elbow, hand = _ik(sh, (tx, ty), 128, 122, side)
        d.line([sh, elbow, hand], ink, 40)
        d.line([sh, elbow, hand], shirt, 30)
        d.circle(hand[0], hand[1], 19, ink, skin, 4)
    # kepala
    hy = -566 + bob
    d.fill([(-16, -452 + by), (-16, hy + 70), (16, hy + 70), (16, -452 + by)], skin)
    d.circle(0, hy, 96, ink, skin, w)
    d.circle(-97, hy + 6, 15, ink, skin, 4)
    d.circle(97, hy + 6, 15, ink, skin, 4)
    # peci
    pc = [(-84, hy - 40), (-80, hy - 112), (-40, hy - 120), (40, hy - 120), (80, hy - 112), (84, hy - 40),
          (40, hy - 50), (-40, hy - 50)]
    d.shape(np.concatenate([bezier(pc[0], pc[1], pc[2], pc[3], 10), bezier(pc[3], pc[4], pc[5], pc[5], 10),
                            bezier(pc[5], pc[6], pc[7], pc[0], 12)]), ink, peci, w)
    d.line(quad((-70, hy - 66), (0, hy - 78), (70, hy - 66)), mix(peci, "#FFFFFF", 0.25), 4)
    # janggut tipis
    if st.get("beard", True):
        chin = np.concatenate([arc_pts(0, hy, 97, 97, math.radians(58), math.radians(122), 14), [(-22, hy + 104), (0, hy + 122), (22, hy + 104)]])
        d.fill(chin, mix(ink, skin, 0.25))
    # alis
    ey = hy - 6
    br = {"biasa": ((-56, ey - 34, -18, ey - 36), (18, ey - 36, 56, ey - 34)),
          "senang": ((-56, ey - 34, -18, ey - 42), (18, ey - 42, 56, ey - 34)),
          "bingung": ((-56, ey - 30, -18, ey - 34), (18, ey - 48, 56, ey - 40)),
          "kaget": ((-56, ey - 50, -18, ey - 54), (18, ey - 54, 56, ey - 50)),
          "serius": ((-56, ey - 42, -18, ey - 32), (18, ey - 32, 56, ey - 42))}[expr if expr in EXPRS else "biasa"]
    for x0, y0, x1, y1 in br:
        d.line([(x0, y0), (x1, y1)], ink, 7)
    # mata
    if blink:
        d.line([(-46, ey), (-26, ey)], ink, 6)
        d.line([(26, ey), (46, ey)], ink, 6)
    elif expr == "senang":
        d.line(arc_pts(-36, ey + 6, 12, 10, math.pi * 1.1, math.pi * 1.9, 10), ink, 6)
        d.line(arc_pts(36, ey + 6, 12, 10, math.pi * 1.1, math.pi * 1.9, 10), ink, 6)
    else:
        r = 13 if expr == "kaget" else 10
        lx = 4 if expr == "bingung" else 0
        d.circle(-36 + lx, ey, r, ink, ink, 3)
        d.circle(36 + lx, ey, r, ink, ink, 3)
        d.circle(-33 + lx, ey - 4, 3, "#FFFFFF", "#FFFFFF", 2)
        d.circle(39 + lx, ey - 4, 3, "#FFFFFF", "#FFFFFF", 2)
    # pipi
    if expr in ("senang", "kaget") or talking:
        d.fill(arc_pts(-60, ey + 32, 14, 8), mix(skin, "#E86A6A", 0.45))
        d.fill(arc_pts(60, ey + 32, 14, 8), mix(skin, "#E86A6A", 0.45))
    # mulut
    my = hy + 46
    if mouth > 0.08:
        h = 6 + 22 * min(1.0, mouth)
        d.shape(arc_pts(0, my, 20 + 6 * mouth, h), ink, "#7A2E2E", 4)
        d.fill(arc_pts(0, my + h * 0.45, 10, h * 0.35), "#E07B7B")
    elif expr == "kaget":
        d.shape(arc_pts(0, my, 13, 17), ink, "#7A2E2E", 4)
    elif expr == "bingung":
        d.line([(-22, my), (-8, my - 6), (6, my + 4), (22, my - 4)], ink, 5)
    elif expr == "senang":
        d.shape(np.concatenate([[(-30, my - 8)], quad((-30, my - 8), (0, my + 34), (30, my - 8))]), ink, "#7A2E2E", 4)
    elif expr == "serius":
        d.line([(-18, my + 2), (18, my + 2)], ink, 5)
    else:
        d.line(quad((-24, my - 4), (0, my + 14), (24, my - 4)), ink, 5)
    return d


# ================================================================ kertas
@functools.lru_cache(maxsize=4)
def paper(theme, w=W, h=H):
    th = C.THEMES[theme]
    base = np.full((h, w, 3), rgb(th["paper"]), np.uint8).astype(np.float32)
    rng = np.random.default_rng(7)
    n = cv2.GaussianBlur(rng.normal(0, 1, (h // 4, w // 4)).astype(np.float32), (0, 0), 1.2)
    n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    base += n[:, :, None] * (3.5 if theme == "kertas" else 5.0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = 1 - 0.10 * (((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h / 2) / (h * 0.75)) ** 2)
    base *= v[:, :, None]
    if theme == "kertas":
        dot = rgb(th["paper2"])
        img = np.clip(base, 0, 255).astype(np.uint8)
        for y in range(60, h, 60):
            for x in range(60, w, 60):
                cv2.circle(img, (x, y), 2, dot, -1, cv2.LINE_AA)
        return img
    if theme == "papan":
        img = np.clip(base, 0, 255).astype(np.uint8)
        smudge = cv2.GaussianBlur(rng.normal(0, 1, (h // 16, w // 16)).astype(np.float32), (0, 0), 2)
        smudge = cv2.resize(smudge, (w, h))
        return np.clip(img.astype(np.float32) + smudge[:, :, None] * 6, 0, 255).astype(np.uint8)
    return np.clip(base, 0, 255).astype(np.uint8)


def palette(st):
    th = C.THEMES[st["theme"]]
    dark = st["theme"] != "kertas"
    return {"ink": th["ink"], "ink_char": "#23201C" if not dark else "#14110E", "mute": th["mute"], "paper": th["paper"],
            "paper2": th["paper2"], "sub_bg": th["sub_bg"], "accent": st["accent"], "accent2": st["accent2"],
            "water": "#4FB3E8", "red": "#E05A47", "ok": "#2FA866", "mute2": "#B9C2C9", "skin": st["skin"],
            "card": "#FFFDF6" if not dark else mix(th["paper"], "#FFFFFF", 0.08), "card_ink": th["ink"],
            "hi": st["accent"] if not dark else "#%02X%02X%02X" % mix(st["accent"], "#FFFFFF", 0.6)}
