"""
Lapisan efek visual Air Wudhu (semua stateless: fungsi dari waktu -> bisa dirender ulang / preview).

  ambient()      gelembung/bintang/tetes melayang di latar kertas
  camera()       push-in pelan + punch-in tiap "beat" + goyang halus + shake saat stempel
  BurstA         ledakan konfeti / bintang / tetes air (aktor, dipakai di build_scene)
  transition()   geser | lingkar (riak air) | tinta (gelombang) | hapus | kilat
  progress_bar() bar progres tipis di atas (menahan penonton sampai habis)
  flash()        kilatan putih singkat saat ganti adegan
  sunburst()     sinar berputar di belakang kata besar

Level (style["fx"]): off | halus | sedang | maksimal  -> faktor intensitas LEVELS.
"""
import math

import cv2
import numpy as np

import aw_doodle as D

W, H = D.W, D.H
LEVELS = {"off": 0.0, "halus": 0.55, "sedang": 1.0, "maksimal": 1.5}
CAM_C = (W / 2, 820)                      # pusat zoom kamera
TRANSITIONS = ["geser", "lingkar", "tirai", "tinta", "lingkar", "tirai", "hapus", "geser", "tinta"]   # urutan untuk mode "variasi"


def level_k(st):
    return LEVELS.get(st.get("fx", "sedang"), 1.0)


def _col(c):
    if isinstance(c, str):
        return tuple(int(v) for v in D.rgb(c))
    return tuple(int(v) for v in c)


def _mixc(a, b, t):
    a, b = _col(a), _col(b)
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


# ---------------------------------------------------------------- ambient
def _star4(img, cx, cy, r, color):
    pts = np.array([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
                    (cx, cy + r), (cx - r * 0.28, cy + r * 0.28), (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], np.int32)
    cv2.fillConvexPoly(img, pts, color, cv2.LINE_AA)


_AMB = None


def ambient(img, tg, P, k):
    """Benda-benda halus melayang naik; dibuat sangat pucat agar tidak mengganggu teks."""
    global _AMB
    if k <= 0:
        return
    if _AMB is None:
        rng = np.random.default_rng(11)
        _AMB = [(rng.uniform(40, W - 40), rng.uniform(0, H + 200), rng.uniform(26, 70), rng.uniform(0.6, 1.6),
                 rng.uniform(0, 6.28), int(rng.integers(0, 3))) for _ in range(22)]
    paper = _col(P["paper"])
    water = _mixc(paper, P["water"], 0.20)
    gold = _mixc(paper, P["accent2"], 0.24)
    green = _mixc(paper, P["accent"], 0.16)
    n = int(len(_AMB) * min(1.0, 0.45 + 0.55 * k))
    for x0, y0, r, sp, ph, kind in _AMB[:n]:
        y = (y0 - 38 * sp * tg) % (H + 200) - 100
        x = x0 + 26 * math.sin(tg * 0.7 * sp + ph)
        if kind == 0:                                           # gelembung air
            cv2.circle(img, (int(x), int(y)), int(r * 0.55), water, 4, cv2.LINE_AA)
            cv2.circle(img, (int(x - r * 0.18), int(y - r * 0.2)), max(2, int(r * 0.09)), water, -1, cv2.LINE_AA)
        elif kind == 1:                                         # bintang kecil berkedip
            tw = 0.55 + 0.45 * math.sin(tg * 2.2 * sp + ph)
            _star4(img, x, y, r * 0.42 * tw, gold)
        else:                                                   # tetes air
            rr = r * 0.30
            pts = np.array([(x, y - rr * 1.6), (x + rr, y + rr * 0.3), (x, y + rr * 1.0), (x - rr, y + rr * 0.3)], np.int32)
            cv2.fillConvexPoly(img, pts, green, cv2.LINE_AA)
            cv2.circle(img, (int(x), int(y + rr * 0.35)), int(rr * 1.0), green, -1, cv2.LINE_AA)


# ---------------------------------------------------------------- kamera
def camera(img, t, dur, tg, pulses, k):
    """t = detik dalam adegan; pulses = [(t, amp, shake)]. Mengembalikan frame baru (zoom >= 1)."""
    if k <= 0:
        return img
    scale = 1.0 + 0.045 * k * min(1.0, t / max(1.0, dur))      # push-in pelan sepanjang adegan
    dx = dy = 0.0
    for tp, amp, shake in pulses:
        tau = t - tp
        if tau < 0:
            continue
        scale += k * amp * min(1.0, tau / 0.05) * math.exp(-tau / 0.22)
        if shake:
            dx += k * shake * math.sin(tau * 75) * math.exp(-tau / 0.13)
            dy += k * shake * 0.6 * math.cos(tau * 63) * math.exp(-tau / 0.13)
    ang = 0.35 * k * math.sin(tg * 0.9)                        # goyang napas
    if scale < 1.0015 and abs(ang) < 0.02 and abs(dx) + abs(dy) < 0.5:
        return img
    M = cv2.getRotationMatrix2D(CAM_C, ang, scale)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------- ledakan partikel
class BurstA:
    """Ledakan sekali jalan di (x,y) pada waktu t0. kind: confetti | stars | drops."""

    def __init__(self, x, y, t0, kind="confetti", n=26, P=None, life=1.15, spread=1.0):
        self.x, self.y, self.t0, self.kind, self.n, self.life, self.spread = x, y, t0, kind, n, life, spread
        self.P = P
        rng = np.random.default_rng(int(t0 * 997) + int(x) + int(y))
        pal = [P["accent"], P["accent2"], P["water"], P["red"], P["ok"]] if P else ["#1F7A6C"]
        self.parts = []
        for _ in range(n):
            a = rng.uniform(-math.pi, 0) if kind != "drops" else rng.uniform(-math.pi * 0.95, -math.pi * 0.05)
            sp = rng.uniform(260, 820) * spread
            self.parts.append((math.cos(a) * sp, math.sin(a) * sp, rng.uniform(10, 24), rng.uniform(0, 6.28),
                               rng.uniform(-9, 9), _col(pal[int(rng.integers(0, len(pal)))])))

    def draw(self, img, t, ctx):
        k = ctx.get("fxk", 1.0)
        tau = t - self.t0
        if k <= 0 or tau < 0 or tau > self.life:
            return None
        fade = 1.0 - tau / self.life
        cnt = max(4, int(self.n * min(1.0, 0.5 + 0.5 * k)))
        for vx, vy, sz, ph, spin, col in self.parts[:cnt]:
            px = self.x + vx * tau * (1 - 0.35 * tau)
            py = self.y + vy * tau + 1100 * tau * tau * 0.5
            r = sz * (0.4 + 0.6 * fade)
            if self.kind == "confetti":
                a = ph + spin * tau
                c, s = math.cos(a), math.sin(a)
                w, h = r, r * 0.5
                pts = np.array([(px + c * w - s * h, py + s * w + c * h), (px - c * w - s * h, py - s * w + c * h),
                                (px - c * w + s * h, py - s * w - c * h), (px + c * w + s * h, py + s * w - c * h)], np.int32)
                cv2.fillConvexPoly(img, pts, col, cv2.LINE_AA)
            elif self.kind == "stars":
                _star4(img, px, py, r * 1.1, col)
            elif self.kind == "hearts":
                rr = r * 0.9
                red = _col(self.P["red"]) if self.P else col
                cv2.circle(img, (int(px - rr * 0.5), int(py - rr * 0.2)), int(rr * 0.55), red, -1, cv2.LINE_AA)
                cv2.circle(img, (int(px + rr * 0.5), int(py - rr * 0.2)), int(rr * 0.55), red, -1, cv2.LINE_AA)
                cv2.fillConvexPoly(img, np.array([(px - rr * 1.0, py - rr * 0.05), (px + rr * 1.0, py - rr * 0.05), (px, py + rr)], np.int32), red, cv2.LINE_AA)
            else:
                cv2.circle(img, (int(px), int(py)), max(2, int(r * 0.55)), _col(self.P["water"]) if self.P else col, -1, cv2.LINE_AA)
        return None


# ---------------------------------------------------------------- sinar
def sunburst(img, cx, cy, t, color, alpha=0.16, rays=16):
    ov = img.copy()
    R = 1500
    for i in range(rays):
        a0 = t * 0.25 + i * 2 * math.pi / rays
        a1 = a0 + math.pi / rays
        pts = np.array([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], np.int32)
        cv2.fillConvexPoly(ov, pts, _col(color), cv2.LINE_AA)
    cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)


# ---------------------------------------------------------------- progres & kilat
def progress_bar(img, f, n, P, k):
    if k <= 0:
        return
    y0, y1 = 44, 52
    w = int((W - 80) * min(1.0, f / max(1, n - 1)))
    track = _mixc(P["paper"], P["mute"], 0.25)
    cv2.rectangle(img, (40, y0), (W - 40, y1), track, -1, cv2.LINE_AA)
    if w > 2:
        cv2.rectangle(img, (40, y0), (40 + w, y1), _col(P["accent2"]), -1, cv2.LINE_AA)
        cv2.circle(img, (40 + w, (y0 + y1) // 2), 9, _col(P["accent"]), -1, cv2.LINE_AA)


def flash(img, p, k):
    if k <= 0 or p >= 1:
        return
    a = 0.42 * min(1.0, k) * (1 - p) ** 2
    if a > 0.01:
        cv2.addWeighted(np.full_like(img, 255), a, img, 1 - a, 0, img)


# ---------------------------------------------------------------- transisi
def transition(img, prev, p, mode, P, y0, y1):
    """img = adegan baru (diubah di tempat), prev = frame terakhir adegan lama."""
    e = D.ease_out(p)
    if mode == "geser":
        o = int(W * e)
        if o <= 0:
            img[y0:y1] = prev[y0:y1]
            return
        new = img[y0:y1].copy()
        img[y0:y1, :W - o] = prev[y0:y1, o:]
        img[y0:y1, W - o:] = new[:, :o]
    elif mode == "lingkar":                         # riak air: adegan baru membuka dari tengah
        cy = (y0 + y1) // 2
        R = int(math.hypot(W / 2, (y1 - y0) / 2) * 1.05 * e)
        mask = np.zeros((y1 - y0, W), np.uint8)
        cv2.circle(mask, (W // 2, cy - y0), R, 255, -1, cv2.LINE_AA)
        m = mask[:, :, None] > 127
        new = img[y0:y1].copy()
        img[y0:y1] = np.where(m, new, prev[y0:y1])
        if 0 < R < 1400:
            for j, (dr, th) in enumerate(((0, 14), (26, 8), (48, 4))):
                cv2.circle(img[y0:y1], (W // 2, cy - y0), R + dr, _col(P["water"]), th, cv2.LINE_AA)
    elif mode == "tinta":                           # tepi bergelombang menyapu dari atas
        h = y1 - y0
        xs = np.arange(W, dtype=np.float32)
        edge = (h * 1.15) * e - 40 + 38 * np.sin(xs / 70.0 + p * 9) + 18 * np.sin(xs / 31.0 - p * 5)
        rows = np.arange(h, dtype=np.float32)[:, None]
        m = (rows < edge[None, :])[:, :, None]
        new = img[y0:y1].copy()
        img[y0:y1] = np.where(m, new, prev[y0:y1])
        ye = np.clip(edge, 0, h - 1).astype(np.int32)
        pts = np.stack([xs.astype(np.int32), ye], 1).reshape(-1, 1, 2)
        if 0 < e < 0.98:
            cv2.polylines(img[y0:y1], [pts], False, _col(P["accent"]), 9, cv2.LINE_AA)
    elif mode == "tirai":                           # tirai vertikal membuka bergantian
        bw = W // 9
        xs = np.arange(W)
        pi = np.clip(p * 1.6 - (xs // bw) * 0.08, 0, 1)
        pi = pi * pi * (3 - 2 * pi)
        m = (((xs % bw) < bw * pi + 1) & (pi > 0))[None, :, None]
        new = img[y0:y1].copy()
        img[y0:y1] = np.where(m, new, prev[y0:y1])
    else:                                           # hapus / kilat: pudar silang
        a = 1 - e
        img[y0:y1] = (img[y0:y1].astype(np.float32) * (1 - a) + prev[y0:y1].astype(np.float32) * a).astype(np.uint8)


class SunA:
    """Sinar berputar di belakang kata besar (aktor)."""

    def __init__(self, x, y, color):
        self.x, self.y, self.color = x, y, color

    def draw(self, img, t, ctx):
        if ctx.get("fxk", 1.0) > 0:
            a = 0.16 * min(1.0, t / 0.5)
            sunburst(img, self.x, self.y, t, self.color, a)
        return None
