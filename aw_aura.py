"""
Efek tambahan (2026-11-22):
  * Latar kisah: bokeh cahaya melayang, kilau sapuan (light sweep), light leak hangat, bintang nur berkelip,
    gelombang cahaya saat kartu muncul, grain film halus.  -> bg_under(), bg_over()
  * Gus Idrus: sinar aura berputar, cakram cahaya di kaki, cincin suara (ikut volume), partikel nur naik,
    glow tepi (rim) berdenyut saat bicara, kilatan masuk, papan nama.  -> ustad_back(), ustad_glow(), ustad_front()
Semua deterministik dari waktu (aman untuk render paralel). Matikan: style["aura"]=false / style["latar_fx"]=false.
"""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
GOLD = (255, 214, 120)
NUR = (255, 246, 214)


def _i(v):
    return int(round(v))


def _add(img, layer, x0, y0, a=1.0):
    """Tambahkan (additive) layer uint8 HxWx3 ke img pada (x0,y0) dengan klip tepi."""
    h, w = layer.shape[:2]
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xb <= xa or yb <= ya:
        return
    roi = img[ya:yb, xa:xb]
    cv2.addWeighted(roi, 1.0, layer[ya - y0:yb - y0, xa - x0:xb - x0], a, 0, roi)


def _screen(img, layer, x0, y0, a=1.0):
    """Blend 'screen' (lebih lembut dari additive, tidak gosong)."""
    h, w = layer.shape[:2]
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xb <= xa or yb <= ya:
        return
    roi = img[ya:yb, xa:xb].astype(np.float32)
    L = layer[ya - y0:yb - y0, xa - x0:xb - x0].astype(np.float32) * a
    img[ya:yb, xa:xb] = (255.0 - (255.0 - roi) * (255.0 - L) / 255.0).astype(np.uint8)


@functools.lru_cache(maxsize=64)
def _ctint(kind, r, col):
    return _tint(_bokeh(r) if kind == "b" else _soft_dot(r), col)


def _tint(gray, col):
    g = gray.astype(np.float32)[:, :, None] / 255.0
    return (g * np.array(col, np.float32)).astype(np.uint8)


# ================================================================ sprite (cache)
@functools.lru_cache(maxsize=8)
def _soft_dot(r):
    s = int(r * 3)
    g = np.zeros((s, s), np.uint8)
    cv2.circle(g, (s // 2, s // 2), int(r), 255, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(g, (0, 0), r * 0.35)


@functools.lru_cache(maxsize=8)
def _bokeh(r):
    """Lingkaran bokeh: isi tipis + tepi sedikit lebih terang."""
    s = int(r * 2.6)
    g = np.zeros((s, s), np.float32)
    cv2.circle(g, (s // 2, s // 2), int(r), 0.55, -1, cv2.LINE_AA)
    cv2.circle(g, (s // 2, s // 2), int(r), 1.0, max(2, int(r * 0.08)), cv2.LINE_AA)
    g = cv2.GaussianBlur(g, (0, 0), max(1.5, r * 0.06))
    return (np.clip(g, 0, 1) * 255).astype(np.uint8)


@functools.lru_cache(maxsize=4)
def _rays(R, n=18):
    """Sinar aura (sunburst) memudar ke luar."""
    s = 2 * R
    g = np.zeros((s, s), np.float32)
    for k in range(n):
        a0 = 2 * math.pi * k / n
        w = math.radians(4.5 if k % 2 else 7.5)
        pts = np.array([(R, R), (R + 2 * R * math.cos(a0 - w), R + 2 * R * math.sin(a0 - w)),
                        (R + 2 * R * math.cos(a0 + w), R + 2 * R * math.sin(a0 + w))], np.int32)
        cv2.fillPoly(g, [pts], 1.0 if k % 2 else 0.7, cv2.LINE_AA)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.sqrt((xx - R) ** 2 + (yy - R) ** 2) / R
    fall = np.clip(1.0 - d, 0, 1) ** 1.6 * np.clip(d * 3.0, 0, 1)
    g = cv2.GaussianBlur(g * fall, (0, 0), R * 0.02 + 2)
    return (np.clip(g, 0, 1) * 255).astype(np.uint8)


@functools.lru_cache(maxsize=2)
def _sweep_band():
    """Pita kilau diagonal (dipakai light sweep)."""
    g = np.zeros((H, 520), np.float32)
    g[:, 200:320] = 1.0
    g[:, 160:200] = 0.35
    g[:, 320:360] = 0.35
    g = cv2.GaussianBlur(g, (0, 0), 30)
    M = cv2.getRotationMatrix2D((260, H / 2), -18, 1.0)
    g = cv2.warpAffine(g, M, (520, H))
    return (np.clip(g, 0, 1) * 255).astype(np.uint8)


@functools.lru_cache(maxsize=1)
def _sweep_col():
    return _tint(_sweep_band(), (255, 250, 230))


@functools.lru_cache(maxsize=4)
def _rays_col(R):
    return _tint(_rays(R), GOLD)


@functools.lru_cache(maxsize=4)
def _leak(kind):
    """Light leak hangat (resolusi 1/4, di-upscale saat dipakai)."""
    h, w = H // 4, W // 4
    L = np.zeros((h, w, 3), np.float32)
    r = np.random.RandomState(31 + kind)
    cols = [(255, 170, 80), (255, 120, 90), (255, 210, 130), (120, 170, 255)]
    for k in range(3):
        cx, cy = r.choice([0, w]), r.uniform(0, h * 0.6)
        c = np.zeros((h, w), np.float32)
        cv2.circle(c, (_i(cx), _i(cy)), _i(r.uniform(70, 130)), 1.0, -1)
        c = cv2.GaussianBlur(c, (0, 0), 40)
        L += c[:, :, None] * np.array(cols[(k + kind) % len(cols)], np.float32) * 0.7
    L = np.clip(L, 0, 255).astype(np.uint8)
    return cv2.resize(L, (W, H), interpolation=cv2.INTER_LINEAR)


@functools.lru_cache(maxsize=4)
def _grain(k):
    r = np.random.RandomState(100 + k)
    n = r.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_NEAREST)
    n = np.clip(n * 4.0, -12, 12)
    pos = cv2.merge([np.clip(n, 0, None).astype(np.uint8)] * 3)
    neg = cv2.merge([np.clip(-n, 0, None).astype(np.uint8)] * 3)
    return pos, neg


def _star(img, x, y, r, col, a=1.0):
    """Bintang 4 sudut berkilau."""
    if r < 1.5 or a <= 0.02:
        return
    r = max(2, _i(r))
    L, D = _star_spr(r, tuple(col))
    _add(img, L, _i(x - r * 1.6), _i(y - r * 1.6), a)
    _add(img, D, _i(x - r * 1.35), _i(y - r * 1.35), 0.5 * a)


@functools.lru_cache(maxsize=256)
def _star_spr(r, col):
    s = _i(r * 3.2)
    L = np.zeros((s, s), np.uint8)
    c = s // 2
    pts = np.array([(c, c - r * 1.5), (c + r * 0.28, c - r * 0.28), (c + r * 1.5, c), (c + r * 0.28, c + r * 0.28),
                    (c, c + r * 1.5), (c - r * 0.28, c + r * 0.28), (c - r * 1.5, c), (c - r * 0.28, c - r * 0.28)], np.int32)
    cv2.fillPoly(L, [pts], 255, cv2.LINE_AA)
    L = cv2.GaussianBlur(L, (0, 0), 0.8)
    return _tint(L, col), _tint(_soft_dot(max(2, _i(r * 0.9))), col)


# ================================================================ latar kisah
def bg_under(c, t, tg, lat, malam, seed, indoor):
    """Di kanvas SEBELUM kamera (ikut zoom): bintang nur berkelip di dinding / langit, bokeh jauh."""
    r = np.random.RandomState(700 + seed)
    # bintang nur berkelip (dinding atas / langit)
    n = 16 if indoor else 10
    for k in range(n):
        x, y = r.uniform(40, W - 40), r.uniform(150, 900)
        ph = r.uniform(0, 6.28)
        tw = max(0.0, math.sin(tg * (1.3 + 0.4 * (k % 3)) + ph))
        tw = tw ** 3
        col = (200, 215, 255) if malam else NUR
        _star(c, x, y, 5 + 9 * tw, col, 0.85 * tw)
    # bokeh jauh (besar, pelan, transparan)
    for k in range(7):
        rr = 26 + (k * 13) % 40
        x = (r.uniform(0, W) + tg * (8 + k * 3) * (1 if k % 2 else -1)) % (W + 200) - 100
        y = r.uniform(200, 1300) + 30 * math.sin(tg * 0.35 + k)
        col = [(255, 214, 140), (255, 190, 150), (210, 240, 220), (190, 210, 255)][k % 4] if not malam else (170, 190, 255)
        a = 0.16 + 0.10 * (0.5 + 0.5 * math.sin(tg * 0.8 + k * 1.3))
        b = _ctint("b", rr, col)
        _screen(c, b, _i(x - b.shape[1] / 2), _i(y - b.shape[0] / 2), a)


def bg_over(out, t, tg, dur, lat, malam, seed, hits=(), hitpos=(), indoor=True):
    """Di frame SETELAH kamera: light sweep, light leak, gelombang kartu, bokeh dekat, grain."""
    # 1) light leak hangat bernafas di tepi
    a = 0.10 + 0.06 * math.sin(tg * 0.45 + seed)
    if not malam:
        cv2.addWeighted(out, 1.0, _leak(seed % 4), a, 0, out)
    # 2) kilau sapuan diagonal tiap ~5.5 dtk
    per = 5.5
    ph = ((tg + seed * 1.7) % per) / 1.6
    if ph < 1.0:
        x0 = _i(-560 + ph * (W + 1120))
        _add(out, _sweep_col(), x0, 0, 0.16 if not malam else 0.08)
    # 3) gelombang cahaya saat kartu muncul
    for h, pos in zip(hits, hitpos or [None] * len(hits)):
        d = t - h
        if 0 <= d < 0.7:
            cx, cy = pos or (540, 420)
            p = d / 0.7
            e = (1 - p) ** 2
            ov = np.zeros((900, 1300, 3), np.uint8)
            cv2.ellipse(ov, (650, 450), (_i(160 + 520 * p), _i(80 + 300 * p)), 0, 0, 360, GOLD, _i(10 + 16 * (1 - p)), cv2.LINE_AA)
            ov = cv2.GaussianBlur(ov, (0, 0), 6)
            _add(out, ov, _i(cx - 650), _i(cy - 450), 0.9 * e)
            for k in range(10):                                             # percikan
                ang = k * 2 * math.pi / 10 + 0.3
                rr = 120 + 460 * p
                _star(out, cx + rr * math.cos(ang), cy + rr * 0.55 * math.sin(ang), 10 * e + 2, GOLD, e)
    # 4) bokeh dekat (depan, besar & kabur) di tepi atas/bawah
    for k in range(4):
        rr = 70 + 25 * k
        side = k % 2
        x = (side * W) + (-1 if side else 1) * (60 + 50 * math.sin(tg * 0.3 + k))
        y = 300 + k * 380 + 60 * math.sin(tg * 0.25 + k * 2)
        b = _ctint("b", rr, (255, 220, 160) if not malam else (160, 180, 255))
        _screen(out, b, _i(x - b.shape[1] / 2), _i(y - b.shape[0] / 2), 0.13)
    # 5) grain film halus
    _apply_grain(out, tg)


def _apply_grain(out, tg):
    pos, neg = _grain(int(tg * 12) % 4)
    cv2.add(out, pos, out)
    cv2.subtract(out, neg, out)


# ================================================================ Gus Idrus
def ustad_back(img, cx, cy, bottom, w, h, tg, t, talking, m, k=1.0, intro=False):
    """Di BELAKANG figur: sinar aura berputar, cakram cahaya kaki, cincin suara, partikel nur."""
    if k <= 0.02:
        return
    # sinar aura berputar
    R = _i(max(w, h) * 0.46)
    rays = _rays_col(R)
    M = cv2.getRotationMatrix2D((R, R), (tg * 9.0) % 360, 1.0 + 0.04 * math.sin(tg * 1.3))
    rot = cv2.warpAffine(rays, M, (2 * R, 2 * R))
    a = (0.20 + 0.12 * m) * k
    _screen(img, rot, _i(cx - R), _i(cy - h * 0.12 - R), a)
    # cakram cahaya di kaki
    disc = _disc(_i(w / 4) * 4)
    _add(img, disc, _i(cx - disc.shape[1] / 2), _i(bottom - 110), (0.32 + 0.1 * math.sin(tg * 2.0)) * k)
    # cincin suara (memancar saat bicara, besar kecil ikut volume)
    if talking:
        ov = np.zeros((_i(h * 1.3), _i(w * 2.0), 3), np.uint8)
        oc = (ov.shape[1] // 2, _i(ov.shape[0] * 0.42))
        for j in range(3):
            p = ((tg * 1.4) + j / 3.0) % 1.0
            rx, ry = _i(w * (0.30 + 0.40 * p)), _i(h * (0.20 + 0.28 * p))
            cv2.ellipse(ov, oc, (rx, ry), 0, 0, 360, (255, 236, 170), _i(2 + 3 * (1 - p)), cv2.LINE_AA)
        _add(img, ov, _i(cx - oc[0]), _i(cy - h * 0.12 - oc[1]), (0.10 + 0.28 * m) * k)
    # partikel nur naik di sekeliling
    for j in range(8):
        ph = (tg * (0.16 + 0.03 * (j % 4)) + j * 0.173) % 1.0
        px = cx + (j - 3.5) / 3.5 * w * 0.55 + 14 * math.sin(tg * 1.7 + j)
        py = bottom - 20 - ph * h * 1.05
        fade = math.sin(ph * math.pi)
        rr = 3 + (j % 3) * 2
        _add(img, _ctint("d", rr, NUR), _i(px - rr * 1.5), _i(py - rr * 1.5), 0.9 * fade * k)
        if j % 4 == 0:
            _star(img, px, py, 6 * fade + 1, GOLD, fade * k)


@functools.lru_cache(maxsize=8)
def _disc(w):
    disc = np.zeros((140, _i(w * 1.5), 3), np.uint8)
    cv2.ellipse(disc, (disc.shape[1] // 2, 70), (_i(w * 0.6), 38), 0, 0, 360, (255, 226, 150), -1, cv2.LINE_AA)
    return cv2.GaussianBlur(disc, (0, 0), 14)


def ustad_glow(img, alpha, x0, y0, tg, m, k=1.0, col=GOLD):
    """Glow tepi (outer rim) dari siluet figur; dipanggil SEBELUM figur ditempel."""
    if k <= 0.02:
        return
    h, w = alpha.shape
    small = cv2.resize(alpha, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    pad = 12
    small = np.pad(small, pad)
    small = cv2.dilate(small, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    small = cv2.GaussianBlur(small, (0, 0), 2.2)
    big = cv2.resize(small, ((w // 4 + 2 * pad) * 4, (h // 4 + 2 * pad) * 4), interpolation=cv2.INTER_LINEAR)
    a = (0.28 + 0.18 * m + 0.05 * math.sin(tg * 3.0)) * k
    _add(img, _tint(big, col), x0 - pad * 4, y0 - pad * 4, a)


@functools.lru_cache(maxsize=4)
def _name_sprite(name, sub):
    f1 = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 40)
    f2 = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
    w1, w2 = f1.getlength(name), f2.getlength(sub)
    Wd = int(max(w1, w2) + 70)
    im = Image.new("RGBA", (Wd + 16, 104), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 12, Wd + 10, 98), 22, fill=(0, 0, 0, 70))
    d.rounded_rectangle((6, 6, Wd + 6, 92), 22, fill=(22, 92, 64, 245), outline=(255, 214, 120, 255), width=3)
    d.rounded_rectangle((6, 6, 20, 92), 7, fill=(255, 214, 120, 255))
    d.text((40, 8), name, font=f1, fill=(255, 255, 255, 255))
    d.text((41, 56), sub, font=f2, fill=(255, 226, 160, 255))
    return np.array(im)


def ustad_front(img, cx, bottom, w, h, tg, t, k=1.0, intro=False, name=None, sub="pencerita kisah"):
    """Di DEPAN figur: kilatan masuk (adegan pertama) + papan nama."""
    if intro and t < 1.1:
        p = t / 1.1
        e = (1 - p) ** 1.5
        ov = np.zeros((_i(h * 1.4), _i(w * 2.2), 3), np.uint8)
        oc = (ov.shape[1] // 2, ov.shape[0] // 2)
        cv2.circle(ov, oc, _i(w * (0.2 + 0.9 * p)), (255, 240, 190), _i(14 * e + 2), cv2.LINE_AA)
        ov = cv2.GaussianBlur(ov, (0, 0), 5)
        _add(img, ov, _i(cx - oc[0]), _i(bottom - h * 0.55 - oc[1]), e)
        for j in range(12):
            ang = j * 2 * math.pi / 12
            rr = w * (0.25 + 0.85 * p)
            _star(img, cx + rr * math.cos(ang), bottom - h * 0.55 + rr * math.sin(ang), 12 * e + 2, GOLD, e)
    if name:
        spr = _name_sprite(name, sub)
        if intro:
            p = min(1.0, max(0.0, (t - 0.5) / 0.45))
            p = 1 - (1 - p) ** 3
        else:
            p = 1.0
        if p <= 0:
            return
        sh, sw = spr.shape[:2]
        x = cx - sw / 2 + (1 - p) * 260
        y = min(H - sh - 14, bottom - 30) + 2 * math.sin(tg * 1.6)
        x0, y0 = _i(x), _i(y)
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + sw), min(H, y0 + sh)
        if xb <= xa or yb <= ya:
            return
        s = spr[ya - y0:yb - y0, xa - x0:xb - x0]
        al = s[:, :, 3:4].astype(np.float32) / 255.0 * p
        roi = img[ya:yb, xa:xb]
        roi[:] = (roi * (1 - al) + s[:, :, :3] * al).astype(np.uint8)
        # kilau lewat di papan nama tiap 4 dtk
        q = ((tg + 1.0) % 4.0) / 0.7
        if q < 1.0:
            gx = _i(q * (xb - xa))
            ov = roi.copy()
            cv2.line(ov, (gx, 8), (gx - 30, yb - ya - 8), (255, 250, 230), 6, cv2.LINE_AA)
            m = (s[:, :, 3] > 200)[:, :, None]                              # kilau hanya di dalam papan
            roi[:] = np.where(m, ov, roi)
