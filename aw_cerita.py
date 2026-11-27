"""
Ilustrasi cerita: tokoh keluarga (suami, istri, anak, bayi, ibu, ayah, kakek, nenek, teman) digambar gaya doodle,
MUNCUL tepat saat kata perannya diucapkan (waktu per kata dari edge-tts) di sebuah "panggung gambar",
berekspresi sesuai kata emosi (marah, sedih, senang, cinta, kaget, bingung), ditemani benda penjelas (rumah, uang, masjid ...).

  person(...)            Drawing tokoh (di-cache) -- origin di tengah kaki
  portrait(d, kind, ink) wajah+bahu untuk ikon bulat (dipakai aw_doodle.icon & stiker di adegan lain)
  plan_cast(sc, seg ...) bangun panggung + tokoh untuk satu adegan, atau None bila tidak ada kata peran
Tidak ada gambar Nabi/sahabat; tokoh hanya orang biasa. Hanya MENGGAMBARKAN kata yang memang diucapkan di narasi.
"""
import functools
import math
import zlib

import cv2
import numpy as np

import aw_doodle as D
import aw_fx as FX
import aw_kata as K
import aw_dunia as DN

W, H = D.W, D.H
rgb = D.rgb

# ------------------------------------------------------------------ spesifikasi tokoh
SPEC = {
    "suami": dict(sex="m", cloth="#4F86C6", pants="#4A4F5A", hr=50, tl=132, ll=128, skin="#E9B88B", hair="#26201C", hat="#26201C"),
    "ayah": dict(sex="m", cloth="#7A8F6A", pants="#3F4756", hr=50, tl=134, ll=130, skin="#DDA777", hair="#26201C", hat="#26201C",
                 beard="#2A2320"),
    "kakek": dict(sex="m", cloth="#F2EEE3", pants="#9AA0A8", hr=48, tl=124, ll=118, skin="#E3B48A", hair="#F4F4F4", hat="#FFFFFF",
                  beard="#F1F1F1", cane=True),
    "teman": dict(sex="m", cloth="#3FA7A0", pants="#4A4F5A", hr=50, tl=130, ll=126, skin="#E9B88B", hair="#3A2A20"),
    "anak": dict(sex="m", cloth="#F2B544", pants="#4F86C6", hr=46, tl=66, ll=62, skin="#EDBE92", hair="#26201C", kid=True),
    "istri": dict(sex="f", cloth="#D9648F", hijab="#6B4FB5", hr=48, tl=130, ll=120, skin="#EDBE92"),
    "ibu": dict(sex="f", cloth="#E8A33D", hijab="#2F7F6F", hr=48, tl=130, ll=120, skin="#E3B48A"),
    "nenek": dict(sex="f", cloth="#8E93A9", hijab="#E8E4F2", hr=47, tl=124, ll=112, skin="#DDB08C"),
    "anak_p": dict(sex="f", cloth="#F08FB0", hijab="#B07CD8", hr=46, tl=62, ll=58, skin="#EDBE92", kid=True),
    "bayi": dict(sex="b", cloth="#FFF1CE", hr=48, skin="#F0C79F", hair="#26201C", kid=True),
}
KINDS = tuple(SPEC)
LABEL = {"suami": "SUAMI", "ayah": "AYAH", "kakek": "KAKEK", "teman": "TEMAN", "anak": "ANAK", "istri": "ISTRI", "ibu": "IBU",
         "nenek": "NENEK", "anak_p": "ANAK", "bayi": "BAYI"}

# kata -> jenis tokoh (diperiksa setelah imbuhan dibuang: istrinya -> istri)
PERSON = {
    "istri": "istri", "isteri": "istri", "bini": "istri", "perempuan": "istri", "wanita": "istri", "ummahat": "ibu",
    "suami": "suami", "laki-laki": "suami", "lelaki": "suami", "pria": "suami",
    "anak": "anak", "putra": "anak", "putri": "anak_p", "bayi": "bayi", "balita": "bayi",
    "ibu": "ibu", "bunda": "ibu", "umi": "ibu", "ayah": "ayah", "bapak": "ayah", "abi": "ayah",
    "kakek": "kakek", "nenek": "nenek", "teman": "teman", "tetangga": "teman",
}
GROUP = {"keluarga": ("ayah", "ibu", "anak"), "anak-anak": ("anak", "anak_p"), "orangtua": ("ayah", "ibu"),
         "suami-istri": ("suami", "istri")}

EMO = {
    "marah": "marah", "kesal": "marah", "benci": "marah", "bentak": "marah", "bertengkar": "marah", "kasar": "marah",
    "zalim": "marah", "emosi": "marah", "murka": "marah", "menyakiti": "marah",
    "sedih": "sedih", "menangis": "sedih", "tangis": "sedih", "kecewa": "sedih", "terluka": "sedih", "lelah": "sedih",
    "capek": "sedih", "derita": "sedih",
    "senang": "senang", "bahagia": "senang", "gembira": "senang", "tersenyum": "senang", "senyum": "senang", "tenang": "senang",
    "harmonis": "senang", "damai": "senang", "syukur": "senang", "ridha": "senang", "rukun": "senang",
    "cinta": "cinta", "sayang": "cinta", "kasih": "cinta", "mesra": "cinta", "peduli": "cinta", "lembut": "cinta",
    "kaget": "kaget", "terkejut": "kaget",
    "bingung": "bingung", "ragu": "bingung", "heran": "bingung",
}
PROP_ICONS = {"rumah", "koin", "piring", "tidur", "masjid", "sajadah", "buku", "kabah", "jam", "api", "pohon", "timbangan", "cincin",
              "tas", "panci", "sekolah", "hati", "lampu", "bintang", "matahari"}


def _match(word, table):
    w = K._norm(word)
    if not w or w in K.STOP:
        return None
    if w in table:
        return table[w]
    for c in K._cands(w):
        if c in table:
            return table[c]
    return None


# ------------------------------------------------------------------ menggambar tokoh
def _brows(d, ink, fx, fy, hr, expr, w=5):
    w = max(2.0, min(4.2, w * hr / 44.0))
    dx, yb = 0.38 * hr, fy - 0.36 * hr
    L = 0.24 * hr
    if expr == "sedih":
        pairs = [((fx - dx - L, yb + 0.1 * hr), (fx - dx + L, yb - 0.1 * hr)), ((fx + dx - L, yb - 0.1 * hr), (fx + dx + L, yb + 0.1 * hr))]
    elif expr == "marah":
        pairs = [((fx - dx - L, yb - 0.1 * hr), (fx - dx + L, yb + 0.12 * hr)), ((fx + dx - L, yb + 0.12 * hr), (fx + dx + L, yb - 0.1 * hr))]
    elif expr == "kaget":
        yb -= 0.14 * hr
        pairs = [((fx - dx - L, yb), (fx - dx + L, yb - 0.05 * hr)), ((fx + dx - L, yb - 0.05 * hr), (fx + dx + L, yb))]
    elif expr == "bingung":
        pairs = [((fx - dx - L, yb), (fx - dx + L, yb + 0.02 * hr)), ((fx + dx - L, yb - 0.2 * hr), (fx + dx + L, yb - 0.12 * hr))]
    else:
        pairs = [((fx - dx - L, yb + 0.02 * hr), (fx - dx + L, yb - 0.02 * hr)), ((fx + dx - L, yb - 0.02 * hr), (fx + dx + L, yb + 0.02 * hr))]
    for a, b in pairs:
        d.line([a, b], ink, w)


def _face(d, ink, fx, fy, hr, expr, blink, cheeks="#F1A39A"):
    """Mata, alis, mulut, pipi di wajah berpusat (fx, fy)."""
    dx, ey = 0.38 * hr, fy - 0.02 * hr
    r = max(2.4, 0.105 * hr)
    lw = max(2.0, min(4.2, 5.0 * hr / 44.0))
    _brows(d, ink, fx, fy, hr, expr)
    if blink:
        for s in (-1, 1):
            d.line([(fx + s * dx - r * 1.2, ey), (fx + s * dx + r * 1.2, ey)], ink, lw)
    elif expr == "senang" or expr == "cinta":
        for s in (-1, 1):
            d.line(D.arc_pts(fx + s * dx, ey + 0.06 * hr, 0.17 * hr, 0.14 * hr, math.pi * 1.1, math.pi * 1.9, 10), ink, lw)
    elif expr == "kaget":
        for s in (-1, 1):
            d.circle(fx + s * dx, ey, r * 1.9, ink, "#FFFFFF", max(1.5, lw * 0.6))
            d.circle(fx + s * dx, ey, r * 0.9, ink, ink, 2)
    else:
        for s in (-1, 1):
            d.circle(fx + s * dx, ey, r, ink, ink, 2)
            d.circle(fx + s * dx + r * 0.35, ey - r * 0.4, r * 0.32, "#FFFFFF", "#FFFFFF", 1)
    if expr in ("senang", "cinta", "kaget", "marah"):
        col = "#E86A6A" if expr == "marah" else cheeks
        for s in (-1, 1):
            d.fill(D.arc_pts(fx + s * 0.62 * hr, ey + 0.4 * hr, 0.17 * hr, 0.1 * hr), D.mix(rgb(col), (255, 255, 255), 0.35 if expr != "marah" else 0.0))
    my = fy + 0.5 * hr
    if expr in ("senang", "cinta"):
        pts = D.quad((fx - 0.3 * hr, my - 0.04 * hr), (fx, my + 0.62 * hr), (fx + 0.3 * hr, my - 0.04 * hr), 16)
        d.shape(pts, ink, "#D9645F", max(1.8, lw * 0.55))
    elif expr == "sedih":
        d.line(D.quad((fx - 0.26 * hr, my + 0.22 * hr), (fx, my - 0.16 * hr), (fx + 0.26 * hr, my + 0.22 * hr)), ink, lw)
    elif expr == "marah":
        d.line([(fx - 0.28 * hr, my + 0.12 * hr), (fx - 0.1 * hr, my), (fx + 0.1 * hr, my + 0.12 * hr), (fx + 0.28 * hr, my)], ink, lw)
    elif expr == "kaget":
        d.shape(D.arc_pts(fx, my + 0.1 * hr, 0.14 * hr, 0.2 * hr), ink, "#A33A3A", max(2.0, lw * 0.8))
    elif expr == "bingung":
        d.line([(fx - 0.24 * hr, my + 0.02 * hr), (fx - 0.08 * hr, my - 0.06 * hr), (fx + 0.08 * hr, my + 0.08 * hr), (fx + 0.24 * hr, my)], ink, lw)
    else:
        d.line(D.quad((fx - 0.24 * hr, my - 0.03 * hr), (fx, my + 0.2 * hr), (fx + 0.24 * hr, my - 0.03 * hr)), ink, lw)


def _head(d, sp, hcx, hcy, hr, ysh, sw, expr, blink, ink, w=6):
    """Kepala lengkap: hijab / rambut / peci / janggut + wajah. ysh = garis bahu, sw = setengah lebar bahu (untuk jubah hijab)."""
    skin = sp["skin"]
    if sp["sex"] == "f":
        hj = sp["hijab"]
        r = hr * 1.2
        left, right = (hcx - r, hcy + 0.1 * hr), (hcx + r, hcy + 0.1 * hr)
        bl, br = (hcx - sw - 4, ysh + 0.5 * hr + 14), (hcx + sw + 4, ysh + 0.5 * hr + 14)
        outline = np.concatenate([
            D.bezier(bl, (bl[0] - 6, hcy + hr * 1.0), (left[0] - 2, hcy + hr * 0.6), left, 12),
            D.arc_pts(hcx, hcy + 0.1 * hr, r, r * 1.06, math.pi, 2 * math.pi, 22),
            D.bezier(right, (right[0] + 2, hcy + hr * 0.6), (br[0] + 6, hcy + hr * 1.0), br, 12),
            D.quad(br, (hcx, ysh + 0.5 * hr + 34), bl, 14)])
        d.shape(outline, ink, hj, w)
        d.line(D.quad((hcx - hr * 0.4, hcy + hr * 1.12), (hcx, hcy + hr * 1.5), (hcx + hr * 0.4, hcy + hr * 1.12)), D.mix(rgb(hj), (0, 0, 0), 0.3), 4)
        d.circle(hcx, hcy + 0.06 * hr, hr * 0.88, ink, skin, 5, ry=hr * 0.94)
        _face(d, ink, hcx, hcy + 0.06 * hr, hr * 0.92, expr, blink)
        return
    d.circle(hcx, hcy, hr, ink, skin, w)
    d.circle(hcx - hr, hcy + 0.1 * hr, 0.17 * hr, ink, skin, 4)
    d.circle(hcx + hr, hcy + 0.1 * hr, 0.17 * hr, ink, skin, 4)
    hair = sp.get("hair")
    if sp.get("beard"):
        chin = np.concatenate([D.arc_pts(hcx, hcy, hr * 0.98, hr * 0.98, math.pi * 0.28, math.pi * 0.72, 10),
                               [(hcx - 0.34 * hr, hcy + hr * 0.78), (hcx, hcy + hr * 1.3), (hcx + 0.34 * hr, hcy + hr * 0.78)]])
        d.fill(chin, sp["beard"])
        d.line(chin, ink, 3)
    if sp.get("hat"):
        pc = D.rrect_pts(hcx - 0.92 * hr, hcy - 1.28 * hr, hcx + 0.92 * hr, hcy - 0.42 * hr, 0.3 * hr)
        d.shape(pc, ink, sp["hat"], w)
        if sp["hat"] != "#FFFFFF":
            d.line(D.quad((hcx - 0.7 * hr, hcy - 0.72 * hr), (hcx, hcy - 0.84 * hr), (hcx + 0.7 * hr, hcy - 0.72 * hr)),
                   D.mix(rgb(sp["hat"]), (255, 255, 255), 0.3), 3)
    elif hair:
        cap = D.arc_pts(hcx, hcy, hr * 1.02, hr * 1.02, math.pi * 1.04, math.pi * 1.96, 18)
        d.shape(np.concatenate([cap, [(hcx + 0.6 * hr, hcy - 0.5 * hr), (hcx, hcy - 0.38 * hr), (hcx - 0.6 * hr, hcy - 0.5 * hr)]]), hair, hair, 3)
    _face(d, ink, hcx, hcy, hr, expr, blink)


def _arm_targets(mode, sw, ysh, tl, hcy, hr):
    side = sw + 8
    down = (side + 2, ysh + tl * 1.2)
    if mode == "naik":
        return (-(sw + 52), ysh - 78), (sw + 52, ysh - 78)
    if mode == "pinggang":
        return (-(sw - 6), ysh + tl * 0.62), (sw - 6, ysh + tl * 0.62)
    if mode == "wajah":
        return (-hr * 1.05, hcy + hr * 0.95), (hr * 1.05, hcy + hr * 0.95)
    if mode == "lambai":
        return (-down[0], down[1]), (sw + 58, ysh - 52)
    return (-down[0], down[1]), down


@functools.lru_cache(maxsize=800)
def person(kind, expr="biasa", blink=False, arms="turun", ink="#23201C"):
    sp = SPEC[kind]
    d = D.Drawing()
    w = 6
    if kind == "bayi":
        hr = sp["hr"]
        hcy = -118
        for s in (-1, 1):
            d.shape(D.arc_pts(s * 36, -12, 24, 13), ink, sp["skin"], 4)
        d.shape(D.arc_pts(0, -44, 50, 44), ink, sp["cloth"], w)
        d.line(D.quad((-30, -56), (0, -40), (30, -56)), D.mix(rgb(sp["cloth"]), (0, 0, 0), 0.25), 4)
        up = arms in ("naik", "lambai")
        for s in (-1, 1):
            tip = (s * (66 if up else 56), -118 if up else -52)
            d.line([(s * 38, -66), tip], ink, 24)
            d.line([(s * 38, -66), tip], sp["cloth"], 15)
            d.circle(tip[0], tip[1], 11, ink, sp["skin"], 4)
        d.circle(0, hcy, hr, ink, sp["skin"], w)
        d.shape(np.concatenate([D.arc_pts(0, hcy, hr, hr, math.pi * 1.28, math.pi * 1.72, 8), [(6, hcy - hr - 12), (-6, hcy - hr + 4)]]),
                sp["hair"], sp["hair"], 3)
        d.circle(-hr, hcy + 4, 8, ink, sp["skin"], 3)
        d.circle(hr, hcy + 4, 8, ink, sp["skin"], 3)
        _face(d, ink, 0, hcy + 4, hr, expr, blink)
        return d
    hr, tl, ll = sp["hr"], sp["tl"], sp["ll"]
    f = sp["sex"] == "f"
    sw = tl * 0.34 + 22
    ysh = -(ll + tl)
    hcy = ysh - 8 - hr
    if f:
        flare = 20 + tl * 0.16
        hem = D.quad((sw + flare, -8), (0, 6), (-sw - flare, -8), 14)
        pts = np.concatenate([[(-sw, ysh + 8), (sw, ysh + 8)], D.bezier((sw, ysh + 8), (sw + 2, ysh + tl * 0.7), (sw + flare * 0.6, -ll * 0.6), (sw + flare, -8), 14), hem,
                              D.bezier((-sw - flare, -8), (-sw - flare * 0.6, -ll * 0.6), (-sw - 2, ysh + tl * 0.7), (-sw, ysh + 8), 14)])
        d.shape(pts, ink, sp["cloth"], w)
        d.line([(-sw + 4, ysh + tl * 0.56), (sw - 4, ysh + tl * 0.56)], D.mix(rgb(sp["cloth"]), (0, 0, 0), 0.3), 4)
        for s in (-1, 1):
            d.shape(D.arc_pts(s * sw * 0.5, -2, 21, 8), ink, "#5A4636", 3)
    else:
        for s in (-1, 1):
            d.line([(s * sw * 0.45, ysh + tl), (s * sw * 0.45, -10)], ink, 40)
            d.line([(s * sw * 0.45, ysh + tl), (s * sw * 0.45, -10)], sp["pants"], 30)
            d.shape(D.arc_pts(s * sw * 0.5, -6, 26, 10), ink, "#5A4636", 3)
        d.shape(D.rrect_pts(-sw, ysh, sw, ysh + tl + 6, 24), ink, sp["cloth"], w)
        d.line([(0, ysh + 10), (0, ysh + tl - 4)], D.mix(rgb(sp["cloth"]), (0, 0, 0), 0.3), 4)
        if not sp.get("kid"):
            for k in range(3):
                d.circle(0, ysh + 30 + k * 30, 4, D.mix(rgb(sp["cloth"]), (255, 255, 255), 0.6), D.mix(rgb(sp["cloth"]), (255, 255, 255), 0.6), 2)
    a = b = max(34.0, tl * 0.52)
    tl_, tr_ = _arm_targets(arms, sw, ysh, tl, hcy, hr)
    for side, tg in ((-1, tl_), (1, tr_)):
        sh = (side * (sw - 6), ysh + 18)
        elbow, hand = D._ik(sh, tg, a, b, side)
        d.line([sh, elbow, hand], ink, 34)
        d.line([sh, elbow, hand], sp["cloth"], 24)
        d.circle(hand[0], hand[1], 14, ink, sp["skin"], 4)
    if sp.get("cane"):
        d.line([(sw + 14, ysh + tl * 0.95), (sw + 22, -4)], "#7A5A3A", 9)
    _head(d, sp, 0, hcy, hr, ysh, sw, expr, blink, ink, w)
    return d


def geom(kind):
    sp = SPEC[kind]
    if kind == "bayi":
        return dict(hr=sp["hr"], hcy=-114, top=-170, h=170)
    hr, tl, ll = sp["hr"], sp["tl"], sp["ll"]
    hcy = -(ll + tl) - 8 - hr
    return dict(hr=hr, hcy=hcy, top=hcy - hr * 1.25, h=-(hcy - hr * 1.25))


def portrait(d, kind, ink="#23201C"):
    """Wajah + bahu dalam kotak 100x100 (untuk ikon bulat / stiker)."""
    if kind == "keluarga":
        for k, dx, dy, s in (("ayah", -2, 6, 0.62), ("ibu", 44, 6, 0.62), ("anak", 22, 42, 0.5)):
            sub = D.Drawing()
            portrait(sub, k, ink)
            d.add(sub, dx, dy, s)
        return d
    sp = SPEC.get(kind, SPEC["teman"])
    if sp["sex"] == "b":
        d.shape(D.arc_pts(50, 100, 34, 22), ink, sp["cloth"], 4)
        d.circle(50, 52, 32, ink, sp["skin"], 4)
        d.shape(np.concatenate([D.arc_pts(50, 50, 30, 30, math.pi * 1.3, math.pi * 1.7, 6), [(53, 14), (47, 24)]]), sp["hair"], sp["hair"], 2)
        _face(d, ink, 50, 56, 32, "biasa", False)
        return d
    ysh, sw = 72, 40
    left = D.bezier((50 - sw, 114), (50 - sw, ysh + 6), (50 - sw * 0.5, ysh - 2), (50, ysh - 2), 12)
    right = D.bezier((50, ysh - 2), (50 + sw * 0.5, ysh - 2), (50 + sw, ysh + 6), (50 + sw, 114), 12)
    d.shape(np.concatenate([left, right]), ink, sp["cloth"], 4)
    _head(d, sp, 50, 42, 26, ysh, sw - 6, "biasa", False, ink, 4)
    return d


# ------------------------------------------------------------------ aktor
class PersonA:
    """Tokoh di panggung: digambar-on (draw-on) saat muncul, napas/bob, kedip, ekspresi sesuai kata emosi, melompat saat disebut lagi."""

    def __init__(self, kind, x, gy, s, t_in, t_out, emos, hops, P, side):
        self.kind, self.x, self.gy, self.s, self.t_in, self.t_out = kind, x, gy, s, t_in, t_out
        self.emos, self.hops, self.P, self.side = sorted(emos), sorted(hops), P, side
        self.g = geom(kind)
        self.ph = (x * 0.017) % 6.28

    def state(self, t):
        expr, te = "biasa", None
        for t0, e in self.emos:
            if t0 <= t:
                expr, te = e, t0
        if te is not None and t - te > 3.4:               # emosi mereda -> kembali biasa
            expr, te = "biasa", None
        a = t - self.t_in
        arms = {"senang": "naik", "cinta": "naik", "kaget": "naik", "marah": "pinggang", "sedih": "wajah"}.get(expr)
        if arms is None:
            arms = "lambai" if a < 1.5 else "turun"
        return expr, arms, te

    def draw(self, img, t, ctx):
        if t < self.t_in:
            return None
        end = None if self.t_out is None else self.t_out + 0.35
        if end is not None and t > end:
            return None
        fk = ctx.get("fxk", 1.0)
        a = t - self.t_in
        k = D.ease_back(min(1.0, a / 0.5))
        if end is not None:
            k *= D.clamp01((end - t) / 0.35)
        if k <= 0.02:
            return None
        xoff = (1 - D.ease_out(min(1.0, a / 0.65))) * self.side * 240
        expr, arms, te = self.state(t)
        blink = ((t + self.ph) % 3.6) < 0.12
        hop = 0.0
        for h in self.hops:
            dt = t - h
            if 0 < dt < 0.42:
                hop = max(hop, 30 * math.sin(math.pi * dt / 0.42))
        if te is not None and t - te < 0.4 and expr in ("senang", "cinta", "kaget", "marah"):
            hop = max(hop, 22 * math.sin(math.pi * (t - te) / 0.4))
        bob = 4.5 * math.sin(a * 2.7 + self.ph) * fk
        sc = self.s * (0.55 + 0.45 * min(k, 1.15)) * (1 + 0.012 * math.sin(a * 2.7 + self.ph) * fk)
        d = person(self.kind, expr, blink, arms, self.P["ink_char"])
        cx, gy = self.x + xoff, self.gy - bob * 0.5 - hop * fk
        # bayangan tanah
        ov = img.copy()
        cv2.ellipse(ov, (int(cx), int(self.gy + 4)), (int(70 * self.s * k + 10), int(11 * self.s * k + 3)), 0, 0, 360, (60, 50, 40), -1, cv2.LINE_AA)
        cv2.addWeighted(ov, 0.14, img, 0.86, 0, dst=img)
        prog = min(1.0, a / 0.75)
        seed = (ctx["frame"] // 4) if ctx.get("boil") else 0
        d.render(img, cx, gy, sc, prog, seed, 1.1 if ctx.get("boil") else 0)
        if prog < 1.0:
            return None
        self._extras(img, t, cx, gy, sc, expr, te, fk)
        return None

    def _extras(self, img, t, cx, gy, sc, expr, te, fk):
        hr, hcy = self.g["hr"], self.g["hcy"]
        hx, hy = cx, gy + hcy * sc
        if expr == "sedih":
            for i, s in enumerate((-1, 1)):
                ph = (t * 1.25 + i * 0.5) % 1.0
                ex, ey = hx + s * 0.38 * hr * sc, hy + 0.08 * hr * sc
                y = ey + ph * 0.95 * hr * sc
                r = max(3, int(0.085 * hr * sc * (1 - ph * 0.4)))
                if ph < 0.9:
                    cv2.ellipse(img, (int(ex), int(y)), (r, int(r * 1.5)), 0, 0, 360, (79, 179, 232), -1, cv2.LINE_AA)
        elif expr == "marah" and te is not None:
            pul = 0.85 + 0.2 * math.sin(t * 14)
            ax, ay = hx + hr * 0.95 * sc, hy - hr * 1.0 * sc
            r1, r2 = 0.12 * hr * sc * pul, 0.4 * hr * sc * pul
            for kk in range(4):
                ang = math.radians(45 + kk * 90)
                p1 = (ax + r1 * math.cos(ang), ay + r1 * math.sin(ang))
                p2 = (ax + r2 * math.cos(ang), ay + r2 * math.sin(ang))
                cv2.line(img, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (224, 90, 71), 6, cv2.LINE_AA)
        elif expr == "kaget" and te is not None:
            bx, by = hx + hr * 1.15 * sc, hy - hr * 1.1 * sc
            cv2.rectangle(img, (int(bx - 5), int(by - 38)), (int(bx + 5), int(by - 8)), (224, 90, 71), -1, cv2.LINE_AA)
            cv2.circle(img, (int(bx), int(by + 4)), 6, (224, 90, 71), -1, cv2.LINE_AA)


class StageA:
    """Panggung gambar: bingkai bulat dengan ruangan/halaman hidup (aw_dunia), tumbuh saat tokoh pertama muncul."""
    X0, Y0, X1, Y1, GY = 40, 725, 725, 1408, 1372

    def __init__(self, t0, setting="dalam", seed=0, crowd=False, night=False, rainy=False, dunia=True):
        self.t0, self.setting, self.seed, self.crowd, self.night, self.rainy, self.dunia = t0, setting, seed, crowd, night, rainy, dunia

    def draw(self, img, t, ctx):
        if t < self.t0:
            return None
        k = D.ease_out(min(1.0, (t - self.t0) / 0.4))
        fk = ctx.get("fxk", 1.0)
        pim, mask, poly = DN.panel(self.setting, self.night and self.dunia, self.rainy and self.dunia)
        fr = pim.copy()
        if self.dunia and fk > 0:
            DN.back(fr, t, self.setting, self.seed, self.crowd, self.night, self.rainy, fk)
        roi = img[self.Y0:self.Y1, self.X0:self.X1]
        blend = (fr.astype(np.float32) * k + roi.astype(np.float32) * (1 - k)).astype(np.uint8)
        roi[mask] = blend[mask]
        cv2.polylines(roi, [poly], True, tuple(int(v) for v in rgb(ctx["P"]["ink"])), 5, cv2.LINE_AA)
        if self.dunia and fk > 0:
            DN.ring(img, (self.X0 + self.X1) / 2, (self.Y0 + self.Y1) / 2, t - self.t0, ctx["P"])
        return None


# ------------------------------------------------------------------ perencana
POS = {1: [382], 2: [235, 535], 3: [165, 385, 605]}
SCALE = {1: 1.25, 2: 1.2, 3: 1.02}
OUTDOOR = {"masjid", "mesjid", "jalan", "taman", "sekolah", "pasar", "kantor", "kerja", "bekerja", "tetangga", "teman", "kebun", "toko",
           "layangan", "mobil", "motor", "bola", "kupu", "kupu-kupu", "burung", "pagi", "hujan", "malam", "bermain", "main", "jamaah", "desa"}
# kata -> hewan/benda/cuaca yang MUNCUL di panggung saat diucapkan (aw_dunia.LifeA)
PROPS = {"kucing": "cat", "kitten": "cat", "burung": "bird", "merpati": "bird", "kupu": "butterfly", "kupu-kupu": "butterfly",
         "bola": "ball", "main": "ball", "bermain": "ball", "layangan": "kite", "layang-layang": "kite", "hujan": "hujan",
         "mobil": "car", "motor": "car"}
NIGHT = {"malam", "tahajud", "subuh", "isya", "gelap"}
CROWD = {"orang-orang", "masyarakat", "jamaah", "ramai", "tetangga", "warga", "umat", "manusia", "banyak"}


def person_events(words):
    """[(waktu, jenis)] urut waktu; 'orang tua' = ayah + ibu."""
    toks = [(t, K._norm(w)) for t, _d, w in words]
    ev, i = [], 0
    while i < len(toks):
        t, w = toks[i]
        nxt = toks[i + 1][1] if i + 1 < len(toks) else ""
        if w == "orang" and nxt.startswith("tua"):
            ev += [(t, "ayah", True), (t, "ibu", True)]
            i += 2
            continue
        if w.replace("nya", "") == "orangtua" or w == "orangtua":
            ev += [(t, "ayah", True), (t, "ibu", True)]
        elif w in GROUP or w.endswith("nya") and w[:-3] in GROUP:
            ev += [(t, k, True) for k in GROUP[w if w in GROUP else w[:-3]]]
        else:
            k = _match(w, PERSON)
            if k:
                ev.append((t, k, False))
            elif "-" in w:
                for part in w.split("-"):
                    k = _match(part, PERSON)
                    if k:
                        ev.append((t, k, False))
                        break
        i += 1
    return ev


def emotion_events(words):
    out = []
    for t, _d, w in words:
        e = _match(w, EMO)
        if e:
            out.append((t, e))
    return out


def plan_cast(sc, seg, P, st):
    """-> {'actors','sfx','pulses'} untuk adegan ini, atau None (tidak ada kata peran -> tampilan lama)."""
    words = seg.get("words") or []
    if not words or not st.get("ilustrasi", True) or sc.get("tipe") not in ("tanya", "bicara"):
        return None
    ev = person_events(words)
    if not ev:
        return None
    kinds = []
    for _t, k, grp in ev:
        if k not in kinds and not (grp and kinds):        # kata kelompok tidak menambah tokoh bila sudah ada tokoh lain
            kinds.append(k)
    n = min(3, len(kinds))
    # tentukan slot: tokoh baru menempati slot kosong; bila penuh, tokoh paling lama pergi
    slots = []                 # dict(kind, idx, t_in, t_out, hops)
    free = list(range(n))
    for t, k, grp in ev:
        cur = next((s for s in slots if s["kind"] == k and s["t_out"] is None), None)
        if grp and not cur and slots:                     # "keluarga"/"orang tua": semua yang tampil melompat senang
            for s in slots:
                if s["t_out"] is None and t - s["t_in"] > 0.8 and (not s["hops"] or t - s["hops"][-1] > 0.8):
                    s["hops"].append(t)
            continue
        if cur:
            if t - cur["t_in"] > 0.8:
                cur["hops"].append(t)
            continue
        active = [s for s in slots if s["t_out"] is None]
        if len(active) >= n:
            old = active[0]
            old["t_out"] = max(t - 0.05, old["t_in"] + 1.0)
            free.append(old["idx"])
        idx = free.pop(0) if free else 0
        slots.append(dict(kind=k, idx=idx, t_in=max(0.0, t - 0.05), t_out=None, hops=[], emos=[]))
    # emosi: kata emosi ikut tokoh yang terakhir disebut; cinta/sayang -> semua tokoh yang tampil
    for te, e in emotion_events(words):
        act = [s for s in slots if s["t_in"] <= te and (s["t_out"] is None or s["t_out"] > te)]
        if not act:
            act = [s for s in slots if s["t_in"] > te][:1]
        if not act:
            continue
        if e == "cinta":
            tgt = act
        else:
            prev = [(tt, kk) for tt, kk, gg in ev if tt <= te + 0.05 and not gg]
            last_k = prev[-1][1] if prev else act[0]["kind"]
            tgt = [s for s in act if s["kind"] == last_k] or act[:1]
        for s in tgt:
            s["emos"].append((te, e))
    setting = "luar" if any(K._norm(w) in OUTDOOR for _t, _d, w in words) else "dalam"
    dunia = st.get("dunia", True)
    seed = zlib.crc32((sc.get("narasi") or "x").encode()) % 997
    norm = [(t, K._norm(w)) for t, _d, w in words]
    props = [(t, PROPS[w]) for t, w in norm if w in PROPS and PROPS[w] != "car"]
    night = any(w in NIGHT for _t, w in norm)
    rainy = any(PROPS.get(w) == "hujan" for _t, w in norm)
    crowd = any(w in CROWD for _t, w in norm)
    if dunia and not any(k_ in ("cat", "butterfly", "ball", "kite", "bird") for _t, k_ in props):   # hewan/benda penghias bawaan
        t_amb = slots[0]["t_in"] + 1.2
        props.append((t_amb, ("butterfly", "ball", "kite")[seed % 3] if setting == "luar" else ("cat", "cat", "bird")[seed % 3]))
    xs, sc_ = POS[n], SCALE[n]
    A = [StageA(slots[0]["t_in"] - 0.05, setting, seed, crowd, night, rainy, dunia)]
    S, pulses = [], []
    for s in slots:
        x = xs[min(s["idx"], len(xs) - 1)]
        A.append(PersonA(s["kind"], x, StageA.GY, sc_, s["t_in"], s["t_out"], s["emos"], s["hops"], P, -1 if x < 380 else 1))
        S.append((s["t_in"], "pop2", 0.7))
        pulses.append((s["t_in"], 0.02, 0))
    if dunia:
        A.append(DN.LifeA([p for p in props if p[1] != "hujan"] + [(t, "hujan") for t, k_ in props if k_ == "hujan"], setting, seed, rainy))
        for t, k_ in props:
            if k_ in ("cat", "bird", "butterfly", "ball", "kite") and t > slots[0]["t_in"] + 1.3:
                S.append((t, "sparkle", 0.5))
        emo_ev = sorted({(te, e) for s in slots for te, e in s["emos"]})
        if emo_ev:
            A.append(DN.MoodA(emo_ev, seed))
    for te, e in sorted({(te, e) for s in slots for te, e in s["emos"]}):
        mx = sum(xs[:n]) / n
        if e == "cinta":
            A.append(FX.BurstA(mx, 900, te + 0.1, "hearts", 12, P, 1.3, 0.8))
            S.append((te, "sparkle", 0.6))
        elif e == "senang":
            A.append(FX.BurstA(mx, 930, te + 0.1, "stars", 8, P, 0.9, 0.6))
            S.append((te, "sparkle", 0.5))
        elif e == "marah":
            S.append((te, "stamp", 0.5))
            pulses.append((te, 0.03, 6))
        elif e == "kaget":
            S.append((te, "stamp", 0.4))
            pulses.append((te, 0.04, 8))
        elif e == "sedih":
            pulses.append((te, 0.0, 0))
    return {"actors": A, "sfx": S, "pulses": pulses}
