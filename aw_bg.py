"""
Latar bertema + ilustrasi di belakang adegan (stateless, fungsi dari waktu):
  background()  awan, bulan sabit, bokeh, sinar, siluet masjid & kurma, pola bintang islami (adegan dalil)
  rain()        hujan hati / bintang / konfeti (penutup, fakta, dalil, bicara)
  halo()        cahaya berdenyut + bintang mengorbit di belakang figur ustad
Semua digambar sebelum aktor, jadi tidak menutupi teks. k = intensitas efek (aw_fx.level_k).
"""
import math

import cv2
import numpy as np

import aw_doodle as D
from aw_fx import W, H, _col, _mixc, _star4

# ---------------------------------------------------------------- util gambar RGBA (kanvas 4 kanal)


def _canvas(h, w):
    return np.zeros((h, w, 4), np.uint8)


def _c4(c, a=255):
    return (int(c[0]), int(c[1]), int(c[2]), int(a))


def _paste(img, layer, x, y, alpha=1.0):
    h, w = layer.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = layer[y0 - y:y1 - y, x0 - x:x1 - x]
    a = sub[:, :, 3:4].astype(np.float32) / 255.0 * alpha
    roi = img[y0:y1, x0:x1]
    roi[:] = (roi * (1 - a) + sub[:, :, :3] * a).astype(np.uint8)


def _dome(c, cx, cy, rx, ry, col):
    cv2.ellipse(c, (cx, cy), (rx, ry), 0, 180, 360, col, -1, cv2.LINE_AA)
    cv2.line(c, (cx, cy - ry), (cx, cy - ry - int(ry * 0.35)), col, 5, cv2.LINE_AA)
    cv2.circle(c, (cx, cy - ry - int(ry * 0.4)), 8, col, -1, cv2.LINE_AA)


def _minaret(c, cx, top, base, col, w=34):
    cv2.rectangle(c, (cx - w // 2, top + 60), (cx + w // 2, base), col, -1, cv2.LINE_AA)
    cv2.rectangle(c, (cx - w // 2 - 9, top + 60), (cx + w // 2 + 9, top + 74), col, -1, cv2.LINE_AA)
    cv2.fillConvexPoly(c, np.array([(cx - w // 2 - 3, top + 60), (cx + w // 2 + 3, top + 60), (cx, top)], np.int32), col, cv2.LINE_AA)
    cv2.circle(c, (cx, top - 6), 6, col, -1, cv2.LINE_AA)


def _palm(c, x, base, h, col, lean=1):
    pts = [(x, base), (x + lean * h * 0.08, base - h * 0.5), (x + lean * h * 0.2, base - h)]
    cv2.polylines(c, [np.array(pts, np.int32)], False, col, 12, cv2.LINE_AA)
    tx, ty = pts[-1]
    for ang in (-160, -130, -100, -70, -40, -15):
        a = math.radians(ang)
        ex, ey = tx + math.cos(a) * h * 0.42, ty + math.sin(a) * h * 0.30 + h * 0.14
        mx, my = tx + math.cos(a) * h * 0.22, ty + math.sin(a) * h * 0.30 - h * 0.05
        cv2.polylines(c, [np.array([(tx, ty), (mx, my), (ex, ey)], np.int32)], False, col, 9, cv2.LINE_AA)


def _crescent(c, cx, cy, r, col):
    layer = np.zeros(c.shape[:2], np.uint8)
    cv2.circle(layer, (cx, cy), r, 255, -1, cv2.LINE_AA)
    cv2.circle(layer, (cx + int(r * 0.42), cy - int(r * 0.12)), int(r * 0.86), 0, -1, cv2.LINE_AA)
    c[layer > 0] = col
    _star4(c, cx + int(r * 1.15), cy + int(r * 0.2), r * 0.32, col)


def _heart(img, cx, cy, r, col):
    cv2.circle(img, (int(cx - r * 0.5), int(cy - r * 0.2)), int(r * 0.55), col, -1, cv2.LINE_AA)
    cv2.circle(img, (int(cx + r * 0.5), int(cy - r * 0.2)), int(r * 0.55), col, -1, cv2.LINE_AA)
    cv2.fillConvexPoly(img, np.array([(cx - r * 1.01, cy - r * 0.05), (cx + r * 1.01, cy - r * 0.05), (cx, cy + r * 1.0)], np.int32), col, cv2.LINE_AA)


# ---------------------------------------------------------------- aset statis (dibuat sekali per palet)
_ASSETS = {}


def _assets(P):
    key = (P["paper"], P["accent"], P["accent2"], P["water"])
    if key in _ASSETS:
        return _ASSETS[key]
    paper = _col(P["paper"])
    far = _mixc(paper, P["accent"], 0.13)
    near = _mixc(paper, P["accent"], 0.24)
    gold = _mixc(paper, P["accent2"], 0.40)
    sky = _canvas(430, W)
    for cx, s in ((120, 0.7), (330, 0.55), (800, 0.6), (980, 0.75)):                 # bangunan jauh
        _dome(sky, cx, 330, int(70 * s), int(60 * s), _c4(far))
        cv2.rectangle(sky, (cx - int(80 * s), 330), (cx + int(80 * s), 430), _c4(far), -1)
    _minaret(sky, 40, 150, 430, _c4(far), 26)
    _minaret(sky, 1040, 130, 430, _c4(far), 26)
    _palm(sky, 215, 430, 300, _c4(far), 1)
    _palm(sky, 880, 430, 330, _c4(far), -1)
    cv2.rectangle(sky, (390, 270), (690, 430), _c4(near), -1, cv2.LINE_AA)           # masjid utama
    _dome(sky, 540, 270, 118, 105, _c4(near))
    _dome(sky, 440, 290, 42, 36, _c4(near))
    _dome(sky, 640, 290, 42, 36, _c4(near))
    _minaret(sky, 350, 110, 430, _c4(near))
    _minaret(sky, 730, 110, 430, _c4(near))
    for wx in (440, 540, 640):
        cv2.rectangle(sky, (wx - 16, 350), (wx + 16, 430), _c4(paper, 120), -1)
        cv2.ellipse(sky, (wx, 350), (16, 16), 0, 180, 360, _c4(paper, 120), -1, cv2.LINE_AA)
    cloud = _canvas(180, 420)
    for ox, oy, r in ((90, 110, 52), (160, 85, 70), (240, 100, 60), (310, 115, 48), (200, 125, 62)):
        cv2.circle(cloud, (ox, oy), r, _c4(_mixc(paper, P["water"], 0.16)), -1, cv2.LINE_AA)
    cloud[:, :, 3] = cv2.GaussianBlur(cloud[:, :, 3], (0, 0), 2.5)
    moon = _canvas(260, 260)
    gl = np.zeros((260, 260), np.float32)
    cv2.circle(gl, (130, 130), 95, 1.0, -1, cv2.LINE_AA)
    gl = cv2.GaussianBlur(gl, (0, 0), 30)
    moon[:, :, :3] = _col(_mixc(paper, P["accent2"], 0.55))
    moon[:, :, 3] = (gl * 110).astype(np.uint8)
    mc = _canvas(260, 260)
    _crescent(mc, 120, 130, 52, _c4(_mixc(paper, P["accent2"], 0.75)))
    a = mc[:, :, 3:4].astype(np.float32) / 255
    moon[:, :, :3] = (moon[:, :, :3] * (1 - a) + mc[:, :, :3] * a).astype(np.uint8)
    moon[:, :, 3] = np.maximum(moon[:, :, 3], mc[:, :, 3])
    tile = _canvas(180, 180)                                                           # pola bintang islami
    for ang in (0, 45):
        pts = [(90 + 74 * math.cos(math.radians(ang + k * 90)), 90 + 74 * math.sin(math.radians(ang + k * 90))) for k in range(4)]
        cv2.polylines(tile, [np.array(pts, np.int32)], True, _c4(gold), 3, cv2.LINE_AA)
    cv2.circle(tile, (90, 90), 28, _c4(gold), 2, cv2.LINE_AA)
    for cx, cy in ((0, 0), (180, 0), (0, 180), (180, 180)):
        cv2.circle(tile, (cx, cy), 40, _c4(gold), 2, cv2.LINE_AA)
    lat = np.tile(tile, (5, 6, 1))                                                     # 900 x 1080
    _ASSETS[key] = {"sky": sky, "cloud": cloud, "moon": moon, "lat": lat}
    return _ASSETS[key]


# ---------------------------------------------------------------- latar
def background(img, tg, tl, kind, P, k):
    if k <= 0:
        return
    A = _assets(P)
    ka = min(1.0, 0.55 + 0.45 * k)
    ov = img.copy()
    cols = [P["water"], P["accent2"], P["accent"], P["water"], P["accent2"], P["accent"], P["red"]]
    for i in range(7):                                                                 # bokeh besar melayang
        r = 90 + 40 * ((i * 37) % 5)
        x = (i * 211 + 120 * math.sin(tg * 0.21 + i)) % (W + 160) - 80
        y = 380 + (i * 173 + 60 * math.cos(tg * 0.17 + i * 2)) % 1000
        cv2.circle(ov, (int(x), int(y)), int(r * (1 + 0.06 * math.sin(tg * 0.9 + i))), _col(cols[i]), -1, cv2.LINE_AA)
    if kind in ("quran", "hadits", "tanya", "fakta"):                                  # sinar dari atas
        R = 1700
        for i in range(7):
            a0 = math.pi * 0.28 + i * 0.30 + 0.06 * math.sin(tg * 0.5)
            pts = np.array([(W * 0.5, -120), (W * 0.5 + R * math.cos(a0), -120 + R * math.sin(a0)),
                            (W * 0.5 + R * math.cos(a0 + 0.13), -120 + R * math.sin(a0 + 0.13))], np.int32)
            cv2.fillConvexPoly(ov, pts, _col(P["accent2"]), cv2.LINE_AA)
    cv2.addWeighted(ov, 0.09 * ka, img, 1 - 0.09 * ka, 0, img)
    if kind in ("quran", "hadits"):
        o = int(tg * 14) % 180
        _paste(img, A["lat"][o:o + 720], 0, 340, 0.22 * ka)
    for i, (y0, sp, al) in enumerate(((300, 26, 0.9), (470, 17, 0.7), (640, 11, 0.5))):   # awan
        x = int((i * 430 + sp * tg) % (W + 520) - 420)
        _paste(img, A["cloud"], x, y0 + int(8 * math.sin(tg * 0.6 + i)), al * ka)
    _paste(img, A["moon"], 800 + int(10 * math.sin(tg * 0.5)), 250 + int(8 * math.cos(tg * 0.7)), 0.95 * ka)
    rise = D.ease_out(min(1.0, tl / 0.8))
    _paste(img, A["sky"], int(6 * math.sin(tg * 0.3)), int(1000 + 80 * (1 - rise)), ka)


# ---------------------------------------------------------------- hujan hati/bintang/konfeti
def rain(img, tg, tl, kind, P, k):
    if k <= 0 or kind not in ("penutup", "fakta", "quran", "hadits", "bicara"):
        return
    n = {"penutup": 16, "fakta": 14, "quran": 7, "hadits": 7, "bicara": 5}[kind]
    n = max(3, int(n * min(1.0, 0.4 + 0.6 * k)))
    pal = [P["accent"], P["accent2"], P["water"], P["red"], P["ok"]]
    for i in range(n):
        ph = (i * 0.61803) % 1.0
        sp = 120 + 90 * ((i * 7) % 5) / 4
        y = ((tl * sp + ph * (H + 300)) % (H + 300)) - 150
        if kind == "bicara":
            y = H + 150 - ((tl * sp * 0.6 + ph * (H + 300)) % (H + 300))
        x = (ph * 977 + i * 131) % W + 30 * math.sin(tl * 1.5 + i)
        col = _col(pal[i % len(pal)])
        r = 14 + 10 * ((i * 3) % 3)
        if kind == "penutup" and i % 2 == 0:
            _heart(img, x, y, r, _col(P["red"]))
        elif kind in ("quran", "hadits", "bicara") or i % 3 == 0:
            _star4(img, x, y, r * 1.1, _col(P["accent2"]))
        else:
            a = tl * 3 + i
            c, s = math.cos(a), math.sin(a)
            w_, h_ = r, r * 0.5
            pts = np.array([(x + c * w_ - s * h_, y + s * w_ + c * h_), (x - c * w_ - s * h_, y - s * w_ + c * h_),
                            (x - c * w_ + s * h_, y - s * w_ - c * h_), (x + c * w_ + s * h_, y + s * w_ - c * h_)], np.int32)
            cv2.fillConvexPoly(img, pts, col, cv2.LINE_AA)


# ---------------------------------------------------------------- halo figur
_HALO = {}


def halo(img, cx, cy, r, color, tg, k, p=1.0):
    if k <= 0:
        return
    key = int(r)
    if key not in _HALO:
        g = np.zeros((int(r * 2.4), int(r * 2.4)), np.float32)
        cv2.circle(g, (g.shape[1] // 2, g.shape[0] // 2), int(r), 1.0, -1, cv2.LINE_AA)
        _HALO[key] = cv2.GaussianBlur(g, (0, 0), r * 0.28)
    g = _HALO[key]
    pulse = (0.34 + 0.08 * math.sin(tg * 2.0)) * min(1.0, 0.5 + 0.5 * k) * p
    h, w = g.shape
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
    if xb > xa and yb > ya:
        a = (g[ya - y0:yb - y0, xa - x0:xb - x0] * pulse)[:, :, None]
        roi = img[ya:yb, xa:xb]
        roi[:] = (roi * (1 - a) + np.array(_col(color), np.float32) * a).astype(np.uint8)
    for i in range(5):
        ang = tg * 0.8 + i * 2 * math.pi / 5
        rr = r * (1.02 + 0.06 * math.sin(tg * 2.2 + i))
        tw = 0.5 + 0.5 * math.sin(tg * 3.1 + i * 1.7)
        _star4(img, cx + rr * math.cos(ang), cy + rr * 0.8 * math.sin(ang), 11 + 9 * tw * k, _col(color))
