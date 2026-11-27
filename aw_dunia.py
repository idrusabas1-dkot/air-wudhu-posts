"""
Dunia sinematik: latar profesional + simulasi kehidupan (figuran, hewan, benda, cuaca) + efek emosi.

  backdrop()   gradasi langit per jenis adegan, bukit parallax 3 lapis berpohon, debu cahaya melayang
  finish()     berkas cahaya, vignette, grain film (dipanggil setelah semua aktor, sebelum kamera)
  panel()      gambar statis panggung cerita (ruang tamu lengkap / halaman luar desa), siang/malam
  back()       lapisan hidup DI BELAKANG tokoh: jam, sinar jendela, awan, burung, figuran berjalan, mobil, layangan
  LifeA        lapisan hidup DI DEPAN tokoh: kucing, burung, kupu-kupu, bola+anak, hujan, daun jatuh
  MoodA        efek emosi layar penuh: petir (marah), hujan (sedih), pelangi (senang), hati (cinta), kilat (kaget)
Semua fungsi stateless terhadap waktu (aman untuk render frame demi frame). k = intensitas efek (aw_fx.level_k).
"""
import math
import zlib

import cv2
import numpy as np

import aw_bg as BG
import aw_doodle as D
from aw_fx import W, H, _col, _mixc, _star4

INK = (35, 32, 28)
rgb = D.rgb


# ---------------------------------------------------------------- primitif gambar
def _i(v):
    return int(round(v))


def _poly(img, pts, fill=None, line=INK, w=3):
    p = np.array([(_i(x), _i(y)) for x, y in pts], np.int32)
    if fill is not None:
        cv2.fillPoly(img, [p], fill, cv2.LINE_AA)
    if line is not None and w > 0:
        cv2.polylines(img, [p], True, line, max(1, _i(w)), cv2.LINE_AA)


def _circ(img, x, y, r, fill=None, line=INK, w=3):
    c, r = (_i(x), _i(y)), max(1, _i(r))
    if fill is not None:
        cv2.circle(img, c, r, fill, -1, cv2.LINE_AA)
    if line is not None and w > 0:
        cv2.circle(img, c, r, line, max(1, _i(w)), cv2.LINE_AA)


def _ell(img, x, y, rx, ry, fill=None, line=INK, w=3, ang=0.0):
    c, ax = (_i(x), _i(y)), (max(1, _i(rx)), max(1, _i(ry)))
    if fill is not None:
        cv2.ellipse(img, c, ax, ang, 0, 360, fill, -1, cv2.LINE_AA)
    if line is not None and w > 0:
        cv2.ellipse(img, c, ax, ang, 0, 360, line, max(1, _i(w)), cv2.LINE_AA)


def _ln(img, a, b, col=INK, w=3):
    cv2.line(img, (_i(a[0]), _i(a[1])), (_i(b[0]), _i(b[1])), col, max(1, _i(w)), cv2.LINE_AA)


def _pl(img, pts, col=INK, w=3):
    cv2.polylines(img, [np.array([(_i(x), _i(y)) for x, y in pts], np.int32)], False, col, max(1, _i(w)), cv2.LINE_AA)


def _rr(img, x0, y0, x1, y1, fill=None, line=INK, w=3, r=8):
    _poly(img, D.rrect_pts(x0, y0, x1, y1, r), fill, line, w)


def _vgrad(h, w, stops):
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, 3), np.float32)
    for c in range(3):
        out[:, c] = np.interp(ys, [s[0] for s in stops], [s[1][c] for s in stops])
    return np.repeat(out[:, None, :], w, axis=1).astype(np.uint8)


def _blend(dst, src, a):
    cv2.addWeighted(src, a, dst, 1 - a, 0, dst)


def _light(c, t):                     # campur warna ke putih
    return tuple(int(v + (255 - v) * t) for v in c)


def _dark(c, t):
    return tuple(int(v * (1 - t)) for v in c)


# ---------------------------------------------------------------- tokoh mini, hewan, benda (cv2, cepat)
CLOTHES = [(79, 134, 198), (217, 100, 143), (63, 167, 160), (242, 181, 68), (142, 147, 169), (122, 143, 106), (232, 163, 61), (176, 124, 216)]
HIJABS = [(107, 79, 181), (47, 127, 111), (232, 228, 242), (200, 80, 90), (60, 90, 150)]


def mini(img, x, gy, s, t, ph, sex="m", kid=False, cloth=(79, 134, 198), hijab=(107, 79, 181), face=1, walk=True, wave=False):
    """Orang kecil berjalan (kaki & tangan berayun), kaki di (x, gy), tinggi ±105*s."""
    hs = 0.64 if kid else 1.0
    sw = math.sin(t * 7.5 + ph) if walk else 0.0
    leg, body, hr = 42 * s * hs, 42 * s * hs, (12 if not kid else 11) * s
    hip = gy - leg
    skin = (233, 184, 139)
    pants = (74, 79, 90)
    for sd in (-1, 1):
        foot = (x + sd * sw * 14 * s * hs, gy - 5 * s * max(0.0, sd * sw))
        a, b = (x + sd * 4 * s, hip), foot
        _ln(img, a, b, INK, 8.5 * s)
        _ln(img, a, b, pants if sex == "m" else _dark(cloth, 0.2), 5.2 * s)
    if sex == "f":
        _poly(img, [(x - 12 * s, hip - body + 6 * s), (x + 12 * s, hip - body + 6 * s), (x + 19 * s, hip + 14 * s * hs),
                    (x - 19 * s, hip + 14 * s * hs)], cloth, INK, 2.4)
    else:
        _rr(img, x - 12 * s, hip - body, x + 12 * s, hip + 4 * s, cloth, INK, 2.4, 6 * s)
    shy = hip - body + 8 * s
    for sd in (-1, 1):
        if wave and sd == 1:
            hand = (x + 22 * s, shy - 26 * s + 5 * s * math.sin(t * 9 + ph))
        else:
            hand = (x + sd * 13 * s - sd * sw * 9 * s * 0.6 + sd * 3 * s, shy + 30 * s * hs)
        _ln(img, (x + sd * 11 * s, shy), hand, INK, 7.5 * s)
        _ln(img, (x + sd * 11 * s, shy), hand, cloth, 4.4 * s)
        _circ(img, hand[0], hand[1], 3.6 * s, skin, INK, 1.6)
    hy = hip - body - hr + 3 * s
    if sex == "f":
        _circ(img, x, hy + 1 * s, hr * 1.38, hijab, INK, 2.4)
        _poly(img, [(x - hr * 1.3, hy + 2 * s), (x + hr * 1.3, hy + 2 * s), (x + 14 * s, shy + 10 * s), (x - 14 * s, shy + 10 * s)], hijab, None, 0)
        _circ(img, x, hy + 2 * s, hr * 0.92, skin, INK, 1.8)
    else:
        _circ(img, x, hy, hr, skin, INK, 2.2)
        _rr(img, x - hr * 0.95, hy - hr * 1.3, x + hr * 0.95, hy - hr * 0.35, (38, 32, 28), INK, 1.6, hr * 0.3)
    for sd in (-1, 1):
        _circ(img, x + sd * hr * 0.38 + face * hr * 0.25, hy + 1 * s, max(1.2, hr * 0.1), INK, None, 0)


def cat(img, x, gy, s, t, mode="walk", d=1, col=(232, 160, 80), ph=0.0):
    """Kucing samping. mode: walk | sit. d=+1 menghadap kanan."""
    dk, wag = _dark(col, 0.25), math.sin(t * 4.2 + ph)
    blink = ((t + ph) % 3.4) < 0.12
    if mode == "sit":
        tail = [(x - d * 12 * s, gy - 6 * s), (x - d * 30 * s, gy - 4 * s), (x - d * 38 * s, gy - 18 * s - 7 * s * wag), (x - d * 32 * s, gy - 34 * s - 9 * s * wag)]
        _pl(img, tail, INK, 9 * s)
        _pl(img, tail, col, 5.5 * s)
        _ell(img, x, gy - 22 * s, 17 * s, 24 * s, col, INK, 2.6)
        _ell(img, x + d * 8 * s, gy - 8 * s, 6 * s, 9 * s, _light(col, 0.5), INK, 1.8)
        hx, hy = x + d * 5 * s, gy - 54 * s + 1.2 * s * math.sin(t * 2 + ph)
    else:
        sw = math.sin(t * 9 + ph)
        for dx in (-16, 14):
            for sd in (-1, 1):
                _ln(img, (x + dx * s, gy - 18 * s), (x + dx * s + sd * sw * 9 * s * d * (1 if dx > 0 else -1), gy), INK, 7 * s)
                _ln(img, (x + dx * s, gy - 18 * s), (x + dx * s + sd * sw * 9 * s * d * (1 if dx > 0 else -1), gy), dk, 4 * s)
        tail = [(x - d * 26 * s, gy - 26 * s), (x - d * 40 * s, gy - 34 * s), (x - d * 44 * s, gy - 52 * s - 6 * s * wag), (x - d * 38 * s, gy - 66 * s - 8 * s * wag)]
        _pl(img, tail, INK, 9 * s)
        _pl(img, tail, col, 5.5 * s)
        _ell(img, x, gy - 26 * s, 29 * s, 15 * s, col, INK, 2.6)
        for k in (-1, 0, 1):
            _ln(img, (x + k * 11 * s, gy - 38 * s), (x + k * 11 * s + 2 * s, gy - 30 * s), dk, 2.4 * s)
        hx, hy = x + d * 30 * s, gy - 38 * s
    r = 12.5 * s
    for sd in (-1, 1):
        _poly(img, [(hx + sd * r * 0.95, hy - r * 0.35), (hx + sd * r * 0.7, hy - r * 1.45), (hx + sd * r * 0.1, hy - r * 0.85)], col, INK, 2.2)
    _circ(img, hx, hy, r, col, INK, 2.6)
    for sd in (-1, 1):
        ex = hx + sd * r * 0.42 + d * r * 0.15
        if blink:
            _ln(img, (ex - 2.5 * s, hy - 1 * s), (ex + 2.5 * s, hy - 1 * s), INK, 1.6)
        else:
            _circ(img, ex, hy - 1 * s, 2.3 * s, INK, None, 0)
        _ln(img, (hx + d * r * 0.2, hy + 3.5 * s), (hx + d * r * 0.2 + sd * r * 1.05, hy + (3 + sd) * s), INK, 1.2)
    _circ(img, hx + d * r * 0.18, hy + 3 * s, 1.8 * s, (226, 120, 130), None, 0)


def bird(img, x, y, s, t, ph, d=1, col=(70, 90, 150)):
    flap = math.sin(t * 15 + ph)
    _poly(img, [(x - d * 12 * s, y), (x - d * 26 * s, y - 4 * s), (x - d * 24 * s, y + 5 * s)], _dark(col, 0.25), INK, 1.8)
    _ell(img, x, y, 14 * s, 8.5 * s, col, INK, 2.2)
    _poly(img, [(x - d * 6 * s, y - 2 * s), (x - d * 2 * s - d * 8 * s, y - (22 + 4 * flap) * s * flap - 3 * s),
                (x + d * 9 * s, y - 2 * s)], _light(col, 0.25), INK, 1.8)
    _circ(img, x + d * 13 * s, y - 4 * s, 6.5 * s, col, INK, 2.2)
    _poly(img, [(x + d * 18 * s, y - 6 * s), (x + d * 26 * s, y - 3.5 * s), (x + d * 18 * s, y - 2 * s)], (245, 180, 60), INK, 1.4)
    _circ(img, x + d * 15 * s, y - 5.5 * s, 1.6 * s, INK, None, 0)


def butterfly(img, x, y, s, t, ph, col=(232, 106, 140)):
    f = 0.25 + 0.75 * abs(math.cos(t * 9 + ph))
    for sd in (-1, 1):
        _ell(img, x + sd * 9 * s * f, y - 7 * s, 10 * s * f, 12 * s, col, INK, 1.8, sd * -28)
        _ell(img, x + sd * 7 * s * f, y + 8 * s, 7 * s * f, 8.5 * s, _light(col, 0.35), INK, 1.8, sd * 22)
    _ln(img, (x, y - 10 * s), (x, y + 12 * s), INK, 3 * s)
    _ln(img, (x, y - 10 * s), (x - 5 * s, y - 20 * s), INK, 1.4)
    _ln(img, (x, y - 10 * s), (x + 5 * s, y - 20 * s), INK, 1.4)


def ball(img, x, y, r, t):
    _circ(img, x, y, r, (250, 250, 245), INK, 3)
    a = t * 5
    for k in range(3):
        aa = a + k * 2.09
        _circ(img, x + math.cos(aa) * r * 0.5, y + math.sin(aa) * r * 0.5, r * 0.28, (231, 90, 71), None, 0)
    _circ(img, x, y, r, None, INK, 3)


def car(img, x, gy, s, t, col=(224, 90, 71), d=1):
    _rr(img, x - 46 * s, gy - 28 * s, x + 46 * s, gy - 8 * s, col, INK, 2.6, 7 * s)
    _poly(img, [(x - 26 * s, gy - 28 * s), (x - 16 * s, gy - 46 * s), (x + 20 * s, gy - 46 * s), (x + 32 * s, gy - 28 * s)], col, INK, 2.6)
    for a, b in ((-12, 2), (6, 20)):
        _poly(img, [(x + a * s, gy - 29 * s), (x + (a + 3) * s, gy - 43 * s), (x + (b + 1) * s, gy - 43 * s), (x + (b + 6) * s, gy - 29 * s)], (200, 232, 246), INK, 1.5)
    for wx in (-26, 26):
        _circ(img, x + wx * s, gy - 8 * s, 10 * s, (60, 60, 66), INK, 2)
        for k in range(3):
            aa = t * 14 * d + k * 2.09
            _ln(img, (x + wx * s, gy - 8 * s), (x + wx * s + math.cos(aa) * 8 * s, gy - 8 * s + math.sin(aa) * 8 * s), (200, 200, 205), 1.6)
    _circ(img, x + d * 44 * s, gy - 20 * s, 3.5 * s, (255, 236, 140), INK, 1.4)


def kite(img, x, y, s, t, hand, col=(231, 90, 71)):
    sway = 0.18 * math.sin(t * 2.3)
    c, sn = math.cos(sway), math.sin(sway)
    pts = [(0, -34), (22, 0), (0, 40), (-22, 0)]
    P = [(x + (px * c - py * sn) * s, y + (px * sn + py * c) * s) for px, py in pts]
    string = [(x, y + 40 * s), (x + (hand[0] - x) * 0.3 + 10 * math.sin(t * 2), y + (hand[1] - y) * 0.35),
              (x + (hand[0] - x) * 0.7, y + (hand[1] - y) * 0.75), hand]
    _pl(img, D.bezier(string[0], string[1], string[2], string[3], 14), (90, 80, 70), 1.6)
    _poly(img, P, col, INK, 2.6)
    _ln(img, P[0], P[2], INK, 1.6)
    _ln(img, P[1], P[3], INK, 1.6)
    _poly(img, [P[0], P[1], P[2], P[3]], None, INK, 2)
    for k in range(4):
        bx, by = P[2][0] + 6 * math.sin(t * 5 + k) * s + (k * 4) * s * sn, P[2][1] + (10 + k * 13) * s
        _poly(img, [(bx - 6 * s, by - 4 * s), (bx + 6 * s, by - 4 * s), (bx, by + 5 * s)], (242, 181, 68) if k % 2 else (79, 134, 198), INK, 1.4)


def cloud(img, x, y, s, col=(255, 255, 255)):
    for dx, dy, r in ((0, 0, 24), (26, -9, 31), (58, 0, 26), (30, 8, 28)):
        _circ(img, x + dx * s, y + dy * s, r * s, col, None, 0)


# ---------------------------------------------------------------- 1) latar sinematik
_MOOD = {"tanya": ((184, 222, 244), (247, 238, 218)), "bicara": ((208, 234, 232), (250, 244, 226)),
         "quran": ((250, 228, 158), (252, 244, 218)), "hadits": ((247, 214, 168), (252, 240, 214)),
         "poin": ((216, 236, 204), (251, 245, 224)), "langkah": ((204, 226, 244), (250, 244, 226)),
         "fakta": ((251, 204, 166), (253, 238, 212)), "penutup": ((246, 196, 214), (253, 238, 226))}
_GR = {}
_HILLS = {}
_MOTES = None


def _grad(kind):
    if kind not in _GR:
        top, bot = _MOOD.get(kind, _MOOD["bicara"])
        _GR[kind] = _vgrad(H, W, [(0.0, top), (0.30, _mixc(top, bot, 0.55)), (0.58, bot), (1.0, bot)])
    return _GR[kind]


def _hills(P):
    key = (P["paper"], P["accent"], P["water"])
    if key in _HILLS:
        return _HILLS[key]
    paper = _col(P["paper"])
    rng = np.random.default_rng(5)
    layers = []
    specs = ((330, 0.20, "water", 0.55, 3, 5, 38, 0.0), (330, 0.30, "accent", 0.65, 2, 4, 52, 1.7), (320, 0.46, "accent", 0.75, 3, 6, 44, 3.1))
    for hh, mixv, colkey, alpha, n1, n2, amp, ph in specs:
        base = _mixc(paper, P[colkey], mixv)
        lay = np.zeros((hh, W, 4), np.uint8)
        xs = np.arange(W)
        yy = hh * 0.42 + amp * np.sin(2 * math.pi * xs / W * n1 + ph) + amp * 0.45 * np.sin(2 * math.pi * xs / W * n2 + ph * 2)
        pts = np.concatenate([np.stack([xs, yy], 1), [(W, hh), (0, hh)]]).astype(np.int32)
        cv2.fillPoly(lay, [pts], (*base, int(255 * alpha)), cv2.LINE_AA)
        if colkey == "accent":                                               # pohon bulat di punggung bukit
            for i in range(9 if mixv > 0.4 else 6):
                tx = int(rng.uniform(0, W))
                ty = int(yy[min(W - 1, tx)])
                tr = int(rng.uniform(26, 44) * (1.3 if mixv > 0.4 else 0.9))
                tcol = _mixc(base, (255, 255, 255), 0.0)
                for off in (0, -W, W):
                    cv2.rectangle(lay, (tx + off - 5, ty - 6), (tx + off + 5, ty + tr), _c4(_dark(tcol, 0.2), 230), -1)
                    cv2.circle(lay, (tx + off, ty - tr // 2), tr, _c4(_dark(tcol, 0.08), 235), -1, cv2.LINE_AA)
                    cv2.circle(lay, (tx + off - tr // 3, ty - tr // 2 - tr // 4), int(tr * 0.55), _c4(_light(tcol, 0.12), 235), -1, cv2.LINE_AA)
        layers.append(lay)
    _HILLS[key] = layers
    return layers


def _c4(c, a=255):
    return (int(c[0]), int(c[1]), int(c[2]), int(a))


def backdrop(img, tg, tl, kind, P, k):
    """Dipanggil SEBELUM BG.background: gradasi langit + bukit parallax + debu cahaya."""
    if k <= 0:
        return
    if sum(_col(P["paper"])) > 560:                                          # tema terang saja
        _blend(img, _grad(kind), 0.78)
    L = _hills(P)
    for lay, y0, sp, al in ((L[0], 1180, 5, 0.9), (L[1], 1260, 11, 0.9), (L[2], 1340, 20, 0.95)):
        o = int(tg * sp) % W
        BG._paste(img, lay, -o, y0, al)
        BG._paste(img, lay, W - o, y0, al)
    base = _mixc(P["paper"], P["accent"], 0.46)                              # tanah di bawah bukit terdekat
    seg = img[1655:]
    cv2.addWeighted(seg, 0.30, np.full_like(seg, base), 0.70, 0, seg)
    global _MOTES
    if _MOTES is None:
        rng = np.random.default_rng(23)
        _MOTES = [(rng.uniform(0, W), rng.uniform(0, 1500), rng.uniform(3, 9), rng.uniform(8, 30), rng.uniform(0, 6.28)) for _ in range(34)]
    ov = img.copy()
    n = max(8, int(len(_MOTES) * min(1.0, 0.4 + 0.6 * k)))
    gold = _col(P["accent2"])
    for x0, y0, r, sp, ph in _MOTES[:n]:
        x = (x0 + 18 * math.sin(tg * 0.5 + ph) + tg * sp * 0.3) % W
        y = (y0 - tg * sp) % 1500 + 150
        rr = r * (1 + 0.25 * math.sin(tg * 1.6 + ph))
        cv2.circle(ov, (_i(x), _i(y)), _i(rr), _light(gold, 0.55), -1, cv2.LINE_AA)
    _blend(img, ov, 0.34)


_FIN = {}


def _finish_maps():
    if _FIN:
        return _FIN
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.47) / (H * 0.62)) ** 2)
    v = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.7
    _FIN["vig"] = np.stack([v * 62 * 0.80, v * 62 * 0.90, v * 62], 2).astype(np.uint8)
    _FIN["edge"] = (np.clip((r - 0.45) / 0.55, 0, 1) ** 1.6 * 255).astype(np.uint8)
    m = np.zeros((H, W), np.uint8)
    for i, (a0, wd) in enumerate(((0.62, 0.10), (0.84, 0.07), (1.05, 0.12))):
        pts = np.array([(-120, -80), (-120 + 2600 * math.cos(a0), -80 + 2600 * math.sin(a0)),
                        (-120 + 2600 * math.cos(a0 + wd), -80 + 2600 * math.sin(a0 + wd))], np.int32)
        cv2.fillConvexPoly(m, pts, 255, cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), 38)
    sh = np.stack([m * 0.17, m * 0.14, m * 0.07], 2)
    _FIN["shaft"] = np.clip(sh, 0, 255).astype(np.uint8)
    rng = np.random.default_rng(3)
    _FIN["grain"] = [np.repeat(rng.integers(0, 6, (H, W, 1)).astype(np.uint8), 3, axis=2) for _ in range(3)]
    _FIN["edgec"] = {}
    return _FIN


def _edge_layer(color):
    F = _finish_maps()
    if color not in F["edgec"]:
        e = F["edge"].astype(np.float32) / 255.0
        F["edgec"][color] = np.stack([e * color[0], e * color[1], e * color[2]], 2).astype(np.uint8)
    return F["edgec"][color]


def finish(img, tg, tl, kind, P, k, frame=0):
    """Berkas cahaya, vignette, grain film. Tema terang: vignette hangat tipis; kuat bila k besar."""
    if k <= 0:
        return
    F = _finish_maps()
    a = (0.55 + 0.45 * math.sin(tg * 0.55 + 1.0)) * min(1.0, 0.6 + 0.4 * k)
    cv2.add(img, cv2.convertScaleAbs(F["shaft"], alpha=a), img)
    cv2.subtract(img, F["vig"], img)
    cv2.add(img, F["grain"][(frame // 2) % 3], img)


# ---------------------------------------------------------------- 2) panggung: gambar statis
_PAN = {}
PW, PH_, PGY = 685, 683, 647


def panel(setting, night=False, rainy=False):
    key = (setting, night, rainy)
    if key in _PAN:
        return _PAN[key]
    w, h, gy = PW, PH_, PGY
    if setting == "luar":
        img = _vgrad(h, w, [(0, (140, 208, 238)), (0.5, (205, 236, 246)), (0.62, (232, 246, 244)), (1, (190, 226, 170))])
        rng = np.random.default_rng(9)
        cv2.circle(img, (w - 105, 105), 58, (255, 236, 160), -1, cv2.LINE_AA)
        cv2.circle(img, (w - 105, 105), 42, (255, 214, 90), -1, cv2.LINE_AA)
        for hc, base, amp, ph, col in ((410, 30, 34, 0.5, (150, 200, 190)), (440, 30, 28, 2.2, (120, 184, 150))):
            xs = np.arange(w)
            yy = hc + amp * np.sin(xs / w * 2 * math.pi * 1.5 + ph) + 12 * np.sin(xs / w * 2 * math.pi * 4 + ph)
            _poly(img, [(0, h)] + [(x, y) for x, y in zip(xs[::6], yy[::6])] + [(w, h)], col, None, 0)
        _rr(img, 38, 396, 98, 448, (251, 232, 190), INK, 2, 4)                       # masjid mungil di kejauhan
        cv2.ellipse(img, (68, 396), (24, 22), 0, 180, 360, (70, 160, 140), -1, cv2.LINE_AA)
        _ln(img, (68, 374), (68, 362), (90, 80, 70), 2)
        _rr(img, 106, 384, 118, 448, (251, 232, 190), INK, 2, 3)
        _poly(img, [(104, 384), (120, 384), (112, 366)], (70, 160, 140), INK, 1.6)
        for hx, col in ((170, (240, 170, 120)), (262, (160, 190, 230)), (350, (245, 210, 120))):
            _rr(img, hx, 410, hx + 58, 460, (252, 244, 226), INK, 2, 3)
            _poly(img, [(hx - 6, 412), (hx + 29, 380), (hx + 64, 412)], col, INK, 2)
            _rr(img, hx + 22, 430, hx + 38, 460, (140, 100, 70), INK, 1.5, 2)
        for tx in (440, 520, 590, 640):                                              # barisan pohon jauh
            _ln(img, (tx, 460), (tx, 410), (110, 90, 70), 5)
            _circ(img, tx, 396, 30, (96, 170, 120), INK, 2)
            _circ(img, tx - 8, 388, 16, (130, 196, 140), None, 0)
        _poly(img, [(0, 462), (w, 462), (w, 508), (0, 508)], (150, 150, 156), None, 0)        # jalan
        _ln(img, (0, 460), (w, 460), INK, 2)
        for x in range(10, w, 60):
            _ln(img, (x, 485), (x + 30, 485), (250, 246, 230), 3)
        _poly(img, [(0, 508), (w, 508), (w, 536), (0, 536)], (216, 206, 188), None, 0)         # trotoar
        _ln(img, (0, 508), (w, 508), INK, 2)
        img[536:gy - 6] = _vgrad(gy - 6 - 536, w, [(0, (160, 210, 140)), (1, (190, 226, 160))])
        for fx in range(0, 200, 22):                                                 # pagar kayu kiri
            _rr(img, fx + 6, 440, fx + 22, 508, (232, 202, 150), INK, 1.6, 2)
        _ln(img, (0, 462), (200, 462), INK, 2)
        _ln(img, (0, 490), (200, 490), INK, 2)
        for _ in range(46):                                                          # rumput & bunga
            fx, fy = rng.uniform(0, w), rng.uniform(545, gy)
            col = [(244, 112, 140), (252, 214, 90), (255, 255, 255), (176, 124, 216)][int(rng.integers(0, 4))]
            _ln(img, (fx, fy), (fx, fy - 12), (80, 150, 80), 2)
            _circ(img, fx, fy - 14, 4.5, col, None, 0)
        _rr(img, w - 112, 296, w - 96, 540, (128, 96, 66), INK, 2.5, 3)                 # pohon besar kanan
        for dx, dy, r in ((0, 0, 70), (-56, 30, 56), (50, 34, 54), (-10, -48, 52)):
            _circ(img, w - 104 + dx, 278 + dy, r, (84, 160, 104), INK, 2.5)
        for dx, dy, r in ((-14, -10, 26), (30, 50, 20), (-60, 40, 18)):
            _circ(img, w - 104 + dx, 278 + dy, r, (118, 190, 130), None, 0)
        img[gy - 6:] = _vgrad(h - gy + 6, w, [(0, (214, 196, 156)), (1, (194, 172, 132))])
    else:
        img = _vgrad(h, w, [(0, (253, 244, 226)), (1, (244, 226, 190))])
        for y in range(30, 420, 44):                                                 # wallpaper
            for x in range(20 + (y // 44 % 2) * 22, w, 44):
                _poly(img, [(x, y - 6), (x + 5, y), (x, y + 6), (x - 5, y)], (240, 222, 188), None, 0)
        _poly(img, [(0, 428), (w, 428), (w, gy - 10), (0, gy - 10)], (226, 196, 150), None, 0)  # wainscot
        for x in range(10, w, 120):
            _rr(img, x + 8, 452, x + 104, gy - 30, None, (201, 168, 120), 2.5, 6)
        _ln(img, (0, 428), (w, 428), (190, 154, 106), 7)
        _ln(img, (0, 436), (w, 436), (214, 182, 136), 3)
        img[gy - 10:] = _vgrad(h - gy + 10, w, [(0, (206, 160, 112)), (1, (180, 134, 92))])
        for x in range(0, w, 58):
            _ln(img, (x, gy - 10), (x - 22, h), (172, 128, 86), 2)
        _ln(img, (0, gy - 10), (w, gy - 10), (160, 120, 80), 4)
        _ell(img, w / 2, gy + 24, 250, 16, (200, 90, 100), (150, 60, 70), 3)
        _ell(img, w / 2, gy + 24, 200, 10, None, (250, 220, 170), 2)
        sky = _vgrad(122, 126, [(0, (170, 220, 246)), (1, (240, 248, 252))])             # jendela
        img[41:163, 77:203] = sky
        _circ(img, 170, 70, 16, (255, 226, 130), None, 0)
        _rr(img, 70, 34, 210, 170, None, (138, 106, 68), 7, 4)
        _ln(img, (140, 41), (140, 163), (138, 106, 68), 5)
        _ln(img, (77, 102), (203, 102), (138, 106, 68), 5)
        _rr(img, 60, 168, 222, 184, (160, 124, 84), INK, 2.5, 4)
        for sd, x0 in ((-1, 50), (1, 232)):                                         # tirai
            _poly(img, [(x0 - 4, 20), (x0 + sd * 54 - 4, 20), (x0 + sd * 46, 196), (x0 + sd * 2, 204)] if sd > 0 else
                  [(x0 + 4, 20), (x0 + sd * 54 + 4, 20), (x0 + sd * 46, 196), (x0 + sd * 2, 204)], (206, 96, 118), INK, 2.5)
            for fx in (14, 28, 40):
                _ln(img, (x0 + sd * fx, 24), (x0 + sd * (fx - 2), 196), (170, 66, 90), 2)
        _ln(img, (30, 20), (260, 20), (120, 90, 60), 6)
        _rr(img, w - 230, 44, w - 110, 142, (243, 217, 168), (138, 98, 62), 7, 4)              # bingkai masjid
        cv2.ellipse(img, (w - 170, 112), (24, 22), 0, 180, 360, (52, 140, 124), -1, cv2.LINE_AA)
        _rr(img, w - 196, 112, w - 144, 132, (52, 140, 124), None, 0, 2)
        _circ(img, w - 190, 68, 11, (224, 161, 0), None, 0)
        _circ(img, w - 186, 66, 10, (243, 217, 168), None, 0)
        _rr(img, w - 218, 188, w - 52, 198, (160, 124, 84), INK, 2.5, 3)                      # rak buku
        for i, bc in enumerate(((200, 90, 80), (79, 134, 198), (242, 181, 68), (63, 167, 160), (160, 110, 190), (230, 120, 60))):
            _rr(img, w - 212 + i * 16, 150 - (i % 3) * 6, w - 198 + i * 16, 188, bc, INK, 1.6, 2)
        _rr(img, w - 108, 156, w - 74, 188, (196, 110, 70), INK, 2, 3)                        # pot kecil
        for ang in (-40, 0, 40):
            _ell(img, w - 91 + ang * 0.6, 142 - abs(ang) * 0.2, 7, 17, (76, 160, 96), INK, 1.6, ang)
        _ln(img, (34, 300), (34, gy - 8), (120, 100, 80), 6)                                # lampu berdiri
        _poly(img, [(8, 332), (60, 332), (50, 286), (18, 286)], (252, 226, 150), INK, 2.5)
        _ell(img, 34, gy - 6, 22, 6, (120, 100, 80), INK, 2)
        _rr(img, w - 68, gy - 70, w - 22, gy - 10, (196, 110, 70), INK, 2.5, 5)                 # tanaman besar
        for ang in (-50, -20, 10, 40):
            _ell(img, w - 45 + ang * 0.9, gy - 100 - abs(ang) * 0.3, 11, 34, (66, 150, 90), INK, 1.8, ang)
    if rainy:
        img = (img.astype(np.float32) * np.array([0.82, 0.86, 0.94], np.float32)).astype(np.uint8)
    if night:
        img = (img.astype(np.float32) * np.array([0.42, 0.48, 0.78], np.float32)).astype(np.uint8)
        rng = np.random.default_rng(4)
        if setting == "luar":
            for _ in range(30):
                _circ(img, rng.uniform(10, w - 10), rng.uniform(8, 300), rng.uniform(1.2, 2.8), (255, 250, 220), None, 0)
            _circ(img, w - 105, 105, 48, (250, 240, 200), None, 0)
            _circ(img, w - 90, 96, 44, (60, 72, 120), None, 0)
    m = np.zeros((h, w), np.uint8)
    poly = np.round(D.rrect_pts(0, 0, w - 1, h - 1, 38)).astype(np.int32)
    cv2.fillPoly(m, [poly], 255, cv2.LINE_AA)
    _PAN[key] = (img, m > 127, poly)
    return _PAN[key]


# ---------------------------------------------------------------- 2b) panggung: lapisan hidup di belakang tokoh
def _pulse_glow(fr, x, y, r, col, a):
    ov = fr.copy()
    for k in range(4):
        cv2.circle(ov, (_i(x), _i(y)), _i(r * (1 - k * 0.22)), col, -1, cv2.LINE_AA)
    cv2.addWeighted(ov, a, fr, 1 - a, 0, fr)


def back(fr, t, setting, seed, crowd=False, night=False, rainy=False, k=1.0):
    """Animasi latar panggung (fr = gambar panel w x h RGB, diubah di tempat)."""
    w, h, gy = PW, PH_, PGY
    if setting != "luar":
        beam = np.array([(80, 168), (200, 168), (w * 0.60, gy - 12), (w * 0.14, gy - 12)], np.int32)
        ov = fr.copy()
        cv2.fillPoly(ov, [beam], (255, 240, 170) if not night else (150, 170, 255), cv2.LINE_AA)
        _blend(fr, ov, (0.17 + 0.04 * math.sin(t * 0.9)) * (1 if not rainy else 0.5))
        win = fr[41:163, 77:203]                                                    # awan & burung di jendela
        cloud(win, ((t * 9) % 220) - 70, 52, 0.7, (255, 255, 255))
        bird(win, ((t * 36 + seed % 70) % 240) - 40, 90 + 8 * math.sin(t * 2), 0.5, t, seed, 1, (70, 80, 120))
        _ln(fr, (140, 41), (140, 163), (138, 106, 68), 5)
        _ln(fr, (77, 102), (203, 102), (138, 106, 68), 5)
        for i in range(14):                                                         # debu di sinar
            f = (i * 0.137 + 0.11 * t * (0.4 + (i % 3) * 0.2)) % 1.0
            px = 90 + (w * 0.42 - 90) * f + 22 * math.sin(t * 0.8 + i) + (i % 5) * 24 * f
            py = 168 + (gy - 168) * f + 6 * math.cos(t + i)
            _circ(fr, px, py, 1.6 + (i % 3), (255, 252, 230), None, 0)
        cx, cy = w / 2, 78                                                          # jam dinding
        _circ(fr, cx, cy, 36, (255, 252, 244), (138, 98, 62), 5)
        for a in range(12):
            an = a * math.pi / 6
            _ln(fr, (cx + math.sin(an) * 29, cy - math.cos(an) * 29), (cx + math.sin(an) * 33, cy - math.cos(an) * 33), INK, 2)
        for ln_, per, wd, col in ((20, 3600.0, 4, INK), (28, 60.0, 3, INK), (30, 1.0, 1.6, (200, 70, 60))):
            an = (t % per) / per * 2 * math.pi
            if per == 3600.0:
                an = (0.35 + t / 3600.0) * 2 * math.pi
            _ln(fr, (cx, cy), (cx + math.sin(an) * ln_, cy - math.cos(an) * ln_), col, wd)
        _circ(fr, cx, cy, 3, INK, None, 0)
        lx, ly = 470, 4                                                             # lampu gantung
        _ln(fr, (lx, 0), (lx, 40), (90, 80, 70), 3)
        _poly(fr, [(lx - 30, 70), (lx + 30, 70), (lx + 16, 40), (lx - 16, 40)], (250, 214, 120), INK, 2.5)
        _pulse_glow(fr, lx, 82, 62 + 4 * math.sin(t * 2), (255, 236, 160), 0.12)
        _circ(fr, lx, 74, 7, (255, 250, 210), None, 0)
        return
    ph = (seed % 100) / 10.0
    if not night:                                                                   # sinar matahari berputar
        ov = fr.copy()
        sx, sy = w - 105, 105
        for i in range(10):
            a = t * 0.18 + i * math.pi / 5
            p = [(sx, sy), (sx + 700 * math.cos(a), sy + 700 * math.sin(a)), (sx + 700 * math.cos(a + 0.11), sy + 700 * math.sin(a + 0.11))]
            cv2.fillConvexPoly(ov, np.array(p, np.int32), (255, 246, 190), cv2.LINE_AA)
        _blend(fr, ov, 0.10)
    for i, (cy, sp, sc) in enumerate(((70, 14, 1.1), (130, 9, 0.8), (190, 6, 0.65))):
        cloud(fr, ((t * sp + i * 260 + ph * 20) % (w + 300)) - 150, cy, sc, (255, 255, 255) if not night else (110, 120, 160))
    for j in range(3):                                                              # kawanan burung jauh
        bx = ((t * 52 + j * 36 + ph * 30) % (w + 260)) - 130
        bird(fr, bx, 150 + 26 * j + 8 * math.sin(t * 2 + j), 0.42, t, j, 1, (80, 90, 130))
    nw = 7 if crowd else 3                                                          # figuran jalan di trotoar
    for i in range(nw):
        d = 1 if i % 2 == 0 else -1
        sp = 30 + (i % 3) * 8
        x = ((t * sp * d + i * 131 + ph * 40) % (w + 120)) - 60
        mini(fr, x, 532, 0.5 + 0.06 * (i % 3), t, i * 1.7, "f" if i % 3 == 1 else "m", i % 4 == 3, CLOTHES[(i + seed) % 8], HIJABS[i % 5], d)
    cyc = (t + (seed % 5)) % 11.0                                                   # mobil lewat tiap ±11 dtk
    if cyc < 6.0:
        d = 1 if (seed % 2 == 0) else -1
        p = cyc / 6.0
        car(fr, (-70 + (w + 140) * p) if d > 0 else (w + 70 - (w + 140) * p), 500, 0.6, t, CLOTHES[(seed + 1) % 8], d)


# ---------------------------------------------------------------- 2c) panggung: lapisan hidup di DEPAN tokoh
class LifeA:
    """Hewan/benda/cuaca di depan tokoh. props = [(t_muncul, jenis)], jenis: cat bird butterfly ball kite hujan."""
    X0, Y0, X1, Y1 = 40, 725, 725, 1408

    def __init__(self, props, setting, seed, rainy=False):
        self.props, self.setting, self.seed, self.rainy = sorted(props), setting, seed, rainy

    def draw(self, img, t, ctx):
        k = ctx.get("fxk", 1.0)
        if k <= 0:
            return None
        pim, mask, _p = panel(self.setting)
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        fr = roi.copy()
        any_ = False
        for t0, kind in self.props:
            tau = t - t0
            if tau < 0:
                continue
            any_ = True
            ph = (zlib.crc32(f"{kind}{t0:.2f}".encode()) % 628) / 100.0
            pop = D.ease_back(min(1.0, tau / 0.45))
            sc = max(0.05, pop)
            if kind == "cat":
                cyc = tau % 9.0
                if cyc < 3.0:
                    x, mode, d = 40 + (PW - 120) * (cyc / 3.0), "walk", 1
                elif cyc < 5.0:
                    x, mode, d = 40 + (PW - 120), "sit", -1
                elif cyc < 8.0:
                    x, mode, d = 40 + (PW - 120) * (1 - (cyc - 5.0) / 3.0), "walk", -1
                else:
                    x, mode, d = 40, "sit", 1
                if tau < 0.6:
                    x = -60 + (x + 60) * D.ease_out(tau / 0.6) if d > 0 else x
                cat(fr, x, PGY + 24, 1.25 * sc, t, mode, d, [(232, 160, 80), (150, 150, 158), (60, 56, 62)][self.seed % 3], ph)
            elif kind == "bird":
                x = ((tau * 120 + ph * 40) % (PW + 200)) - 100
                bird(fr, x, 190 + 40 * math.sin(tau * 1.6 + ph), 0.95 * sc, t, ph, 1, CLOTHES[(self.seed + 3) % 8])
            elif kind == "butterfly":
                x = PW * 0.5 + 250 * math.sin(tau * 0.55 + ph) + 40 * math.sin(tau * 2.1)
                y = 230 + 110 * math.sin(tau * 0.83 + ph * 2) + 18 * math.sin(tau * 3.3)
                butterfly(fr, x, y, 1.1 * sc, t, ph, CLOTHES[(self.seed + 2) % 8] if tau else (232, 106, 140))
            elif kind == "ball":
                bx = PW * 0.5 + 240 * math.sin(tau * 0.8 + ph)
                dirn = 1 if math.cos(tau * 0.8 + ph) > 0 else -1
                hop = abs(math.sin(tau * 3.3)) * 78
                by = PGY + 6 - 16 - hop
                mini(fr, bx - dirn * 72, PGY + 18, 0.8 * sc, t, ph, "m", True, (242, 181, 68), HIJABS[0], dirn)
                ball(fr, bx, by, 17 * sc, tau)
                if hop < 4:
                    _ell(fr, bx, PGY + 12, 22, 5, (70, 60, 50), None, 0)
            elif kind == "kite":
                hand = (96, PGY - 18)
                mini(fr, 96, PGY - 6, 0.78 * sc, t, ph, "f", True, (240, 143, 176), HIJABS[3], 1, False, True)
                kite(fr, 210 + 70 * math.sin(tau * 0.7 + ph), 150 + 24 * math.cos(tau * 0.9), 1.25 * sc, tau, (hand[0] + 18, hand[1] - 62))
        if self.rainy or any(kd == "hujan" and t >= t0 for t0, kd in self.props):
            ov = fr.copy()
            for i in range(90):
                x = (i * 83.7 + t * 180) % (PW + 60) - 30
                y = (i * 47.3 + t * 900 * (0.7 + (i % 4) * 0.12)) % (PH_ + 40) - 20
                cv2.line(ov, (_i(x), _i(y)), (_i(x - 9), _i(y + 26)), (190, 214, 240), 2, cv2.LINE_AA)
            _blend(fr, ov, 0.6)
            any_ = True
        if not any_:
            return None
        roi[mask] = fr[mask]
        return None


# ---------------------------------------------------------------- 3) efek emosi layar penuh
class MoodA:
    """Efek besar saat kata emosi diucapkan: marah=petir+merah, sedih=hujan+biru, senang=pelangi+emas,
    cinta=hati melayang+merah muda, kaget=kilat+garis kecepatan."""
    DUR = 2.8
    X0, Y0, X1, Y1 = 40, 725, 725, 1408

    def __init__(self, events, seed=0):
        self.ev, self.seed = sorted(events), seed

    def draw(self, img, t, ctx):
        k = ctx.get("fxk", 1.0)
        if k <= 0:
            return None
        for t0, e in self.ev:
            tau = t - t0
            if tau < 0 or tau > self.DUR:
                continue
            f = D.clamp01(tau / 0.3) * D.clamp01((self.DUR - tau) / 0.9) * min(1.0, 0.55 + 0.45 * k)
            fn = getattr(self, "_" + e, None)
            if fn:
                fn(img, tau, f, k, t0)
        return None

    def _edge(self, img, color, a):
        cv2.add(img, cv2.convertScaleAbs(_edge_layer(color), alpha=max(0.0, a)), img)

    def _marah(self, img, tau, f, k, t0):
        self._edge(img, (255, 60, 40), f * (0.75 + 0.25 * math.sin(tau * 18)))
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        cv2.subtract(roi, (30 * f, 34 * f, 30 * f, 0), roi)
        ov = roi.copy()
        for i, (cx, r) in enumerate(((90, 60), (240, 78), (400, 66), (560, 80), (660, 56))):
            _ell(ov, cx, 24 + 10 * math.sin(tau * 3 + i), r, r * 0.46, (70, 66, 82), None, 0)
        _blend(roi, ov, 0.78 * f)
        for fl in (0.12, 0.34):
            if 0 < tau - fl < 0.09:
                cv2.add(img, (110, 110, 80, 0), img)
                rng = np.random.default_rng(int(self.seed + fl * 100 + t0 * 10))
                x, y, pts = 160 + rng.uniform(-60, 380), 60, []
                while y < 540:
                    pts.append((x, y))
                    x += rng.uniform(-44, 44)
                    y += rng.uniform(34, 62)
                ov2 = roi.copy()
                _pl(ov2, pts, (255, 236, 120), 12)
                _blend(roi, ov2, 0.5)
                _pl(roi, pts, (255, 255, 250), 4)
                break

    def _sedih(self, img, tau, f, k, t0):
        self._edge(img, (50, 80, 160), f * 0.6)
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        cv2.subtract(roi, (22 * f, 16 * f, 4 * f, 0), roi)
        ov = roi.copy()
        for i in range(70):
            x = (i * 97.3) % (self.X1 - self.X0)
            y = (i * 61.7 + tau * 760 * (0.75 + (i % 4) * 0.1)) % (self.Y1 - self.Y0)
            cv2.line(ov, (_i(x), _i(y)), (_i(x - 5), _i(y + 22)), (186, 206, 236), 2, cv2.LINE_AA)
        _blend(roi, ov, 0.55 * f)
        ov = roi.copy()
        for i, (cx, r) in enumerate(((120, 70), (320, 88), (540, 76))):
            _ell(ov, cx, 20 + 6 * math.sin(tau * 2 + i), r, r * 0.42, (118, 124, 148), None, 0)
        _blend(roi, ov, 0.6 * f)

    def _senang(self, img, tau, f, k, t0):
        self._edge(img, (255, 200, 70), f * 0.55)
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        ov = roi.copy()
        cols = [(231, 90, 71), (245, 150, 60), (250, 214, 80), (96, 190, 110), (79, 160, 232), (140, 100, 210)]
        grow = D.ease_out(min(1.0, tau / 0.9))
        for i, c in enumerate(cols):
            r = (330 - i * 17) * grow
            cv2.ellipse(ov, (342, 560), (_i(r), _i(r * 0.95)), 0, 180, 360, c, 15, cv2.LINE_AA)
        _blend(roi, ov, 0.5 * f)

    def _cinta(self, img, tau, f, k, t0):
        self._edge(img, (255, 110, 150), f * 0.7)
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        ov = roi.copy()
        for i in range(12):
            x = 40 + (i * 61) % 610 + 16 * math.sin(tau * 2 + i)
            y = 600 - (tau * (150 + (i % 4) * 40) + i * 40) % 640
            BG._heart(ov, x, y, 14 + (i % 3) * 7, (240, 90, 120))
        _blend(roi, ov, 0.75 * f)

    def _kaget(self, img, tau, f, k, t0):
        if tau < 0.14:
            cv2.add(img, (150, 150, 140, 0), img)
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        ov = roi.copy()
        cx, cy = 342, 340
        for i in range(30):
            a = i * 2 * math.pi / 30 + 0.05 * math.sin(i * 3)
            r0, r1 = 120 + 220 * tau, 330 + 520 * tau
            cv2.line(ov, (_i(cx + r0 * math.cos(a)), _i(cy + r0 * math.sin(a))), (_i(cx + r1 * math.cos(a)), _i(cy + r1 * math.sin(a))), (60, 56, 52), 4 if i % 2 else 2, cv2.LINE_AA)
        _blend(roi, ov, 0.4 * D.clamp01(1 - tau / 0.9))


# ---------------------------------------------------------------- pembuka panggung: gelombang kejut
def ring(img, cx, cy, tau, P):
    if tau < 0 or tau > 0.7:
        return
    p = tau / 0.7
    ov = img.copy()
    cv2.circle(ov, (_i(cx), _i(cy)), _i(60 + 420 * D.ease_out(p)), _col(P["accent2"]), max(2, _i(22 * (1 - p))), cv2.LINE_AA)
    _blend(img, ov, 0.55 * (1 - p))
