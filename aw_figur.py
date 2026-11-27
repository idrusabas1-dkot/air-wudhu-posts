"""
Figur ustad dari GAMBAR/FOTO -> animasi: potong latar, (opsional) gaya kartun, lalu digerakkan per frame
(napas, kepala goyang & mengangguk, kedip, mulut membuka mengikuti suara) dengan warp mesh halus.

Gambar: assets/figur-ustad.jpeg (ilustrasi 765x1024, latar abu polos). Ganti file ini untuk mengganti figur.
Titik wajah LM dalam piksel gambar asli; kalau gambar diganti, sesuaikan LM di sini atau di config.json -> "figur_lm".
Gaya: asli (gambar apa adanya) | kartun / doodle (olah tambahan, untuk foto asli).
"""
import json
import math
import os

import cv2
import numpy as np

import aw_common as C

FIG_PATH = os.path.join(C.BASE, "assets", "figur-ustad.jpeg")
S = 0.9                                           # skala internal sprite (gambar sudah besar -> ~resolusi tampil)
LM = {"eye_l": (311, 281), "eye_r": (406, 271), "eye_rx": 21, "eye_ry": 10, "eye_ang": -6,
      "mouth": (369, 372), "mouth_hw": 42, "mouth_ang": -6,
      "head_y0": 395, "head_y1": 475,            # kepala ikut miring di atas y0; bahu diam di bawah y1
      "neck": (385, 470), "chin": 442,
      "open": 11, "mouth_gain": 0.62, "mouth_floor": 0.14, "unit": 1.85,   # open = bukaan mulut maks (px gambar) relatif senyum dasar
      # gambar dasar = senyum terbuka (gigi atas terlihat). 'seam' = tepi bawah gigi: titik kiri, tengah, kanan.
      # Saat bicara rahang turun dari garis ini dan rongga gelap terbuka di bawah gigi.
      "seam": ((331, 372), (370, 373.5), (408, 366)),
      "lip_thick": 17,                            # tebal bibir bawah di gambar (px) untuk penipisan saat membuka
      # tangan kanan-ke-dada: poligon pemotong (px gambar) mencakup lengan sampai kelim lengan baju; engsel di kelim (lengan tidak 'putus')
      "hand_poly": ((250, 700), (268, 686), (300, 640), (330, 600), (375, 568), (450, 585), (498, 598), (498, 722), (462, 738),
                    (402, 778), (340, 794), (310, 804), (296, 807), (262, 807), (250, 790)),
      "hand_pivot": (282, 806),
      # lengan bawah kanan (siku -> manset) yang dihapus saat tangan bergerak bebas (aw_gestur)
      "arm_poly": ((58, 800), (75, 768), (262, 704), (306, 744), (310, 878), (182, 940), (95, 950), (58, 905)),
      "elbow": (86, 872), "wrist": (292, 776),
      "placket": ((372, (70, 66, 70), 3), (344, (196, 198, 208), 2), (410, (196, 198, 208), 2))}
PAD_L = 175                                       # ruang kosong kiri sprite (px gambar) agar tangan menunjuk ke kiri tak terpotong


def _oval(w):
    """Profil bukaan 0..1 sepanjang bibir: oval membulat (dasar agak datar), bukan lancip."""
    w = np.clip(w, 0.0, 1.0)
    return np.clip(1.0 - np.abs(2.0 * w - 1.0) ** 3.4, 0.0, 1.0) ** 0.6


def _smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _cut_background(im):
    """Latar polos terang -> flood fill dari tepi (berhenti di garis tinta). Fallback: grabCut."""
    h, w = im.shape[:2]
    corners = np.array([im[3, 3], im[3, w - 4], im[h // 2, 3], im[h // 2, w - 4]], np.float32)
    if corners.std(axis=0).max() < 10:
        bgm = np.zeros((h + 2, w + 2), np.uint8)
        flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
        work = im.copy()
        tol = (13, 13, 13)
        for sx, sy in ((3, 3), (w - 4, 3), (3, h // 2), (w - 4, h // 2), (w // 2, 3), (3, h // 4), (w - 4, h // 4), (w // 8, 3), (w - w // 8, 3)):
            if bgm[sy + 1, sx + 1] == 0 and np.abs(im[sy, sx].astype(int) - corners.mean(0)).max() < 25:
                cv2.floodFill(work, bgm, (sx, sy), 0, tol, tol, flags)
        fg = (bgm[1:-1, 1:-1] == 0).astype(np.uint8) * 255
    else:
        m = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
        m[int(h * .03):, int(w * .03):int(w * .97)] = cv2.GC_PR_FGD
        bg = np.zeros((1, 65), np.float64)
        fgm = np.zeros((1, 65), np.float64)
        cv2.grabCut(im, m, (int(w * .03), int(h * .03), int(w * .94), int(h * .97)), bg, fgm, 6, cv2.GC_INIT_WITH_RECT)
        fg = ((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)).astype(np.uint8) * 255
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 2:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = ((lab == keep) * 255).astype(np.uint8)
    inv = 255 - fg                                    # tutup lubang kecil di dalam
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 1500:
            fg[lab == i] = 255
    return fg


def _cartoon(rgb, strength=1.0):
    sm = rgb.copy()
    for _ in range(4):
        sm = cv2.bilateralFilter(sm, 9, 50, 9)
    lab = cv2.cvtColor(sm, cv2.COLOR_RGB2LAB).astype(np.float32)
    q = 26.0
    lab[:, :, 0] = np.round(lab[:, :, 0] / q) * q * 0.3 + lab[:, :, 0] * 0.7
    lab[:, :, 1:] = (lab[:, :, 1:] - 128) * 1.03 + 128
    out = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    g = cv2.medianBlur(cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (0, 0), 1.3), 7)
    edges = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 9)
    e3 = (cv2.GaussianBlur(edges, (0, 0), 0.8).astype(np.float32) / 255.0)[:, :, None]
    ink = np.array([38, 30, 26], np.float32)
    out = out.astype(np.float32) * (1 - (1 - e3) * 0.75 * strength) + ink * (1 - e3) * 0.35 * strength
    return np.clip(out, 0, 255).astype(np.uint8)


def _extract_hand(im, lm):
    """Mask tangan (kulit + garis tinta + gelang) di dalam poligon lm['hand_poly']."""
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    Hh, Ss, Vv = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin = (Hh >= 3) & (Hh <= 24) & (Ss > 55) & (Vv > 110)
    bead = (Hh >= 3) & (Hh <= 24) & (Ss > 90) & (Vv >= 40) & (Vv <= 140)
    dark = Vv < 85
    near = cv2.dilate((skin | bead).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    poly = np.zeros(skin.shape, np.uint8)
    cv2.fillPoly(poly, [np.array(lm["hand_poly"], np.int32)], 255)
    m = ((skin | bead | (dark & near)) & (poly > 0)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 2:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        m = ((lab == keep) * 255).astype(np.uint8)
    inv = 255 - m
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 300:
            m[lab == i] = 255
    return m


class Figure:
    def __init__(self, path=FIG_PATH, style="asli", lm=None):
        self.lm = dict(LM)
        self.lm.update(lm or {})
        try:
            with open(C.CONFIG_FILE, encoding="utf-8") as f:
                self.lm.update(json.load(f).get("figur_lm") or {})
        except (OSError, ValueError):
            pass
        im = cv2.imread(path)
        if im is None:
            raise FileNotFoundError(path)
        mask = _cut_background(im)
        hmask = _extract_hand(im, self.lm)
        hole = cv2.dilate(hmask, np.ones((7, 7), np.uint8))
        base_bgr = cv2.inpaint(im, hole, 9, cv2.INPAINT_TELEA)             # latar di bawah tangan (jubah) untuk saat tangan bergerak
        hx0 = int(self.lm.get("shawl_x", 446))
        cl = np.roll(im, -56, axis=1)                                         # tekstur selendang dari 56 px di kanan
        wx = np.clip((np.arange(im.shape[1]) - (hx0 - 6)) / 14.0, 0, 1).astype(np.float32)[None, :, None]
        robe = np.median(im[600:700, 160:230].reshape(-1, 3), 0)               # warna jubah bersih di kiri tangan
        flat = np.empty_like(im)
        flat[:] = robe.astype(np.uint8)
        hole_s = cv2.GaussianBlur(hole, (0, 0), 2.0).astype(np.float32)[:, :, None] / 255.0
        base_bgr = (base_bgr * (1 - hole_s) + flat * hole_s).astype(np.uint8)    # jubah polos, bukan noda inpaint
        wgt = wx * (hole[:, :, None] > 0)
        base_bgr = (base_bgr * (1 - wgt) + cl * wgt).astype(np.uint8)
        rgb = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2RGB)
        hand_full = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        if style in ("kartun", "doodle"):
            rgb = _cartoon(rgb, 1.5 if style == "doodle" else 1.0)
            hand_full = _cartoon(hand_full, 1.5 if style == "doodle" else 1.0)
        ys, xs = np.where(hmask > 0)
        mg = 4
        bx0, bx1, by0, by1 = max(0, xs.min() - mg), xs.max() + mg + 1, max(0, ys.min() - mg), ys.max() + mg + 1
        hc = hand_full[by0:by1, bx0:bx1]
        ha = cv2.GaussianBlur(hmask[by0:by1, bx0:bx1], (0, 0), 0.8)
        ih = cv2.INTER_AREA if S < 1 else cv2.INTER_CUBIC
        self.hand_rgb = cv2.resize(hc, None, fx=S, fy=S, interpolation=ih)
        self.hand_a = cv2.resize(ha, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
        self.hand_org = (bx0 * S, by0 * S)
        interp = cv2.INTER_AREA if S < 1 else cv2.INTER_CUBIC
        rgb = cv2.resize(rgb, None, fx=S, fy=S, interpolation=interp)
        a = cv2.resize(mask, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
        a = cv2.GaussianBlur(a, (0, 0), 1.0)
        a = cv2.erode(a, np.ones((3, 3), np.uint8))     # kikis sedikit agar sisa latar abu tak terlihat
        self.rgb, self.alpha = rgb, a
        # versi tanpa lengan bawah kanan & tangan: dasar untuk gerak tangan bebas (aw_gestur).
        # Lubang diisi dengan melanjutkan baju secara VERTIKAL (garis kancing/bordir menyambung), selendang pakai tekstur geser.
        armf = np.zeros(mask.shape, np.uint8)
        cv2.fillPoly(armf, [np.array(self.lm["arm_poly"], np.int32)], 255)
        holef = cv2.dilate(armf | hole, np.ones((5, 5), np.uint8))
        na_bgr = base_bgr.copy()
        H0 = im.shape[0]
        robe_hi = np.percentile(im[600:700, 160:230].reshape(-1, 3), 85, axis=0).astype(np.float32)
        vfill_mask = np.zeros(mask.shape, np.uint8)
        for x in range(0, min(hx0 - 4, im.shape[1])):
            col = holef[:, x] > 0
            if not col.any():
                continue
            ys = np.flatnonzero(col)
            runs = np.split(ys, np.flatnonzero(np.diff(ys) > 1) + 1)
            for r_ in runs:
                a_, b_ = int(r_[0]), int(r_[-1]) + 1
                top = np.median(im[max(0, a_ - 4):a_, x].reshape(-1, 3), 0) if a_ > 3 and mask[a_ - 1, x] else None
                bot = np.median(im[b_:min(H0, b_ + 4), x].reshape(-1, 3), 0) if b_ < H0 - 3 and mask[b_, x] else None
                if top is None and bot is None:
                    continue
                if top is None:
                    top = bot
                if bot is None:
                    bot = top
                t_ = np.linspace(0, 1, b_ - a_)[:, None]
                v_ = top[None, :] * (1 - t_) + bot[None, :] * t_
                # garis (kancing/kelim) hanya diteruskan bila atas & bawah sama-sama gelap & mirip
                v_ = np.maximum(v_, robe_hi[None, :] * 0.95)                # putih baju polos (tanpa belang)
                vfill_mask[a_:b_, x] = 1
                na_bgr[a_:b_, x] = v_.astype(np.uint8)
        sm = cv2.GaussianBlur(na_bgr, (0, 0), sigmaX=9, sigmaY=3)          # haluskan bagian polos (tanpa belang)
        vm = cv2.GaussianBlur(vfill_mask.astype(np.float32), (0, 0), 1.0)[:, :, None]
        na_bgr = (na_bgr * (1 - vm) + sm * vm).astype(np.uint8)
        for (lx, col, wd) in self.lm.get("placket", ()):                    # garis kancing/kelim yang tertutup tangan
            ys_l = np.flatnonzero(holef[:, lx] > 0)
            if len(ys_l):
                cv2.line(na_bgr, (lx, int(ys_l.min()) - 2), (lx, int(ys_l.max()) + 2), col[::-1], wd, cv2.LINE_AA)
        na = cv2.cvtColor(na_bgr, cv2.COLOR_BGR2RGB)
        if style in ("kartun", "doodle"):
            na = _cartoon(na, 1.5 if style == "doodle" else 1.0)
        na = cv2.resize(na, (rgb.shape[1], rgb.shape[0]), interpolation=interp)
        ysh, xsh = np.where(holef > 0)
        self.rgb_na = na
        self.na_box = (max(0, int(xsh.min() * S) - 4), max(0, int(ysh.min() * S) - 4), min(na.shape[1], int(xsh.max() * S) + 5),
                       min(na.shape[0], int(ysh.max() * S) + 5))
        # lapisan lengan bawah (lengan baju) dari gambar asli, ujung siku dibuat lembut
        am_full = np.zeros(mask.shape, np.uint8)
        cv2.fillPoly(am_full, [np.array(self.lm["arm_poly"], np.int32)], 255)
        sl = ((am_full > 0) & (mask > 0) & (cv2.dilate(hmask, np.ones((3, 3), np.uint8)) == 0)).astype(np.uint8) * 255
        ys_, xs_ = np.where(sl > 0)
        sx0, sx1, sy0, sy1 = xs_.min(), xs_.max() + 1, ys_.min(), ys_.max() + 1
        fe = np.clip((np.arange(sx0, sx1, dtype=np.float32) - 60) / 45.0, 0, 1)[None, :]
        sa = (cv2.GaussianBlur(sl[sy0:sy1, sx0:sx1], (0, 0), 0.8).astype(np.float32) * fe).astype(np.uint8)
        self.slv_rgb = cv2.resize(hand_full[sy0:sy1, sx0:sx1], None, fx=S, fy=S, interpolation=ih)
        self.slv_a = cv2.resize(sa, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
        self.slv_org = (sx0 * S, sy0 * S)
        self.robe_rgb = tuple(int(v) for v in np.percentile(im[600:700, 160:230].reshape(-1, 3), 80, axis=0)[::-1])
        hs = self.hand_rgb[self.hand_a > 200]
        hs = hs[(hs.astype(int).sum(1) > 330)] if len(hs) else hs
        self.skin_hand = tuple(int(v) for v in np.median(hs, 0)) if len(hs) else (232, 172, 128)
        self.skin_hand_d = tuple(int(v * 0.78) for v in self.skin_hand)
        self.h, self.w = rgb.shape[:2]
        yy, xx = [g.astype(np.float32) for g in np.mgrid[0:self.h, 0:self.w]]
        self.xx, self.yy = xx, yy
        L = self.lm
        self.pivot = (L["neck"][0] * S, L["neck"][1] * S)
        self.wh = 1 - _smooth((yy / S - L["head_y0"]) / (L["head_y1"] - L["head_y0"]))
        self.wb = _smooth((yy / S - L["head_y1"]) / 160.0)
        self.u = L.get("unit", 1.85)                                       # skala gerak relatif (1 = foto 415px)
        self.mx, self.my = L["mouth"][0] * S, L["mouth"][1] * S
        (qx0, _), _, (qx2, _) = L["seam"]
        pad_x = 0.12 * (qx2 - qx0)
        tcol = (np.arange(self.w, dtype=np.float32) / S - (qx0 - pad_x)) / ((qx2 - qx0) + 2 * pad_x)   # 0..1 sepanjang bukaan
        gcol = _oval(tcol)
        gcol = cv2.GaussianBlur(gcol.reshape(1, -1), (0, 0), 2.5 * S).reshape(-1)       # tepi lembut
        self.gcol = gcol
        gx = np.broadcast_to(gcol[None, :], xx.shape)
        (sx0, sy0), (sx1, sy1), (sx2, sy2) = L["seam"]
        tt = np.linspace(0, 1, 60)
        scx, scy = 2 * sx1 - (sx0 + sx2) / 2, 2 * sy1 - (sy0 + sy2) / 2
        Xc = (1 - tt) ** 2 * sx0 + 2 * (1 - tt) * tt * scx + tt ** 2 * sx2
        Yc = (1 - tt) ** 2 * sy0 + 2 * (1 - tt) * tt * scy + tt ** 2 * sy2
        seam_y = np.interp(np.arange(self.w, dtype=np.float32), Xc * S, Yc * S).astype(np.float32)
        self.seam_y = seam_y
        below = _smooth((yy - seam_y[None, :] - 1.0 * S) / (3.0 * S))        # rahang bergeser mulai tepat di bawah tepi bawah gigi
        fall = 1 - _smooth((yy / S - (L["chin"] - 40)) / 50.0)
        # bibir bawah menipis saat mulut terbuka: tepi atasnya turun penuh, tepi bawahnya ~55% (bukan ikut turun utuh = tebal)
        lipfall = 1.0 - 0.45 * _smooth((yy - seam_y[None, :] - 2.0 * S) / (L["lip_thick"] * S))
        self.jaw = (gx * below * lipfall * fall).astype(np.float32)
        mxc, myc = int(370 * S), int(375 * S)                                           # warna rongga asli (di bawah gigi)
        cp = rgb[myc:int(myc + 2.5 * S), mxc - int(8 * S):mxc + int(8 * S)]
        self.cav = tuple(int(v) for v in np.median(cp.reshape(-1, 3), 0))

        def skin_at(p):
            x, y = p[0] * S, (p[1] + 28) * S
            patch = rgb[int(y - 4 * S):int(y + 4 * S), int(x - 8 * S):int(x + 8 * S)]
            return tuple(int(v) for v in np.median(patch.reshape(-1, 3), 0))
        self.skin, self.skin_r = skin_at(L["eye_l"]), skin_at(L["eye_r"])

    # ------------------------------------------------------------ satu frame
    def frame(self, mouth=0.0, blink=0.0, nod=0.0, tilt=0.0, breath=0.0, wide=0.0, hand=None, gesture=None):
        """mouth 0..1, blink 0..1 (1=tertutup), nod/tilt derajat, breath -1..1, wide -1(bulat 'o')..1(lebar 'e').
        hand = (dx, dy, rot_derajat, skala) gerak tangan dalam px gambar. Hasil RGBA."""
        xx, yy, wh = self.xx, self.yy, self.wh
        px, py = self.pivot
        u = self.u
        ang = math.radians(tilt)
        dx, dy = xx - px, yy - py
        a_w = ang * wh
        cw, sw = np.cos(-a_w), np.sin(-a_w)
        sx = px + dx * cw - dy * sw
        sy = py + dx * sw + dy * cw
        sy = sy - self.wb * breath * 5.0 * u * S
        sy = sy - nod * u * S * 1.2 * wh * (1 - 0.4 * _smooth((yy / S - 250) / 120))
        # bicara biasa: bukaan kecil, menutup di sela suku kata (ambang bawah), tidak pernah menganga lebar
        fl = self.lm["mouth_floor"]
        mouth = float(np.clip((mouth - fl) / (1.0 - fl), 0.0, 1.0)) ** 1.25 * self.lm["mouth_gain"]
        hs = 1.0 - 0.18 * wide
        d = mouth * self.lm["open"] * S * hs
        sy = sy - d * self.jaw
        mapx, mapy = sx.astype(np.float32), sy.astype(np.float32)
        rgb = cv2.remap(self.rgb, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        al = cv2.remap(self.alpha, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

        def to_out(x, y):                                                   # titik gambar -> posisi hasil
            ddx, ddy = x * S - px, y * S - py
            w_ = 1 - float(_smooth((y - self.lm["head_y0"]) / (self.lm["head_y1"] - self.lm["head_y0"])))
            a2 = ang * w_
            ox = px + ddx * math.cos(a2) - ddy * math.sin(a2)
            oy = py + ddx * math.sin(a2) + ddy * math.cos(a2) + nod * u * S * 1.2 * w_
            return ox, oy
        if blink > 0.02:
            for key, skin in (("eye_l", self.skin), ("eye_r", self.skin_r)):
                ex, ey = to_out(*self.lm[key])
                self._lid(rgb, ex, ey, blink, skin, self.lm["eye_ang"] + tilt)
        if mouth > 0.04:
            self._mouth(rgb, to_out, d)
        al8 = np.clip(al, 0, 255).astype(np.uint8)
        prm, bw = gesture if gesture else (None, 0.0)
        PL = int(PAD_L * S)
        if prm is None or bw <= 0.0:
            self._draw_hand(rgb, al8, hand, breath)
            return self._pad(rgb, al8, PL)
        if bw < 1.0:                                                        # perpindahan dari/ke tangan asli di dada
            rgb_o, al_o = rgb.copy(), al8.copy()
            self._draw_hand(rgb_o, al_o, hand, breath)
            out_o = self._pad(rgb_o, al_o, PL)
        x0, y0, x1, y1 = self.na_box
        rgb[y0:y1, x0:x1] = cv2.remap(self.rgb_na, mapx[y0:y1, x0:x1], mapy[y0:y1, x0:x1], cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REPLICATE)
        out = self._pad(rgb, al8, PL)
        self._draw_arm(out, prm, breath * 5.0 * self.u * S, PL)
        if bw < 1.0:
            out = cv2.addWeighted(out_o, 1.0 - bw, out, bw, 0)
        return out

    @staticmethod
    def _pad(rgb, al8, PL):
        out = np.zeros((rgb.shape[0], rgb.shape[1] + PL, 4), np.uint8)
        out[:, PL:, :3] = rgb
        out[:, PL:, 3] = al8
        return out

    def _draw_arm(self, out, prm, by, PL):
        """Lengan bawah + tangan ASLI diputar: tangan di pergelangan (ph), lalu semuanya di siku (th)."""
        L = self.lm
        ex, ey = L["elbow"][0] * S + PL, L["elbow"][1] * S + by
        wx, wy = L["wrist"][0] * S + PL, L["wrist"][1] * S + by
        Re = np.vstack([cv2.getRotationMatrix2D((ex, ey), prm["th"], 1.0), [0, 0, 1]])
        Rw = np.vstack([cv2.getRotationMatrix2D((wx, wy), prm["ph"], 1.0), [0, 0, 1]])
        size = (out.shape[1], out.shape[0])
        # sendi siku (warna jubah) di bawah lengan agar sambungan tidak bolong
        r = int(50 * S)
        cv2.circle(out, (int(ex), int(ey)), r, self.robe_rgb + (255,), -1, cv2.LINE_AA)
        for (rgbL, aL, org, M2) in ((self.slv_rgb, self.slv_a, self.slv_org, Re),
                                    (self.hand_rgb, self.hand_a, self.hand_org, Re @ Rw)):
            T0 = np.array([[1, 0, org[0] + PL], [0, 1, org[1] + by], [0, 0, 1]], np.float64)
            M = (M2 @ T0)[:2]
            pts = np.array([[0, 0, 1], [aL.shape[1], 0, 1], [0, aL.shape[0], 1], [aL.shape[1], aL.shape[0], 1]], np.float64) @ M.T
            bx0, by0 = max(0, int(pts[:, 0].min()) - 2), max(0, int(pts[:, 1].min()) - 2)
            bx1, by1 = min(size[0], int(pts[:, 0].max()) + 3), min(size[1], int(pts[:, 1].max()) + 3)
            if bx1 <= bx0 or by1 <= by0:
                continue
            Mr = M.copy()
            Mr[0, 2] -= bx0
            Mr[1, 2] -= by0
            sz = (bx1 - bx0, by1 - by0)
            lr = cv2.warpAffine(rgbL, Mr, sz, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            la = cv2.warpAffine(aL, Mr, sz, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            a = la.astype(np.float32)[:, :, None] / 255.0
            roi = out[by0:by1, bx0:bx1]
            roi[:, :, :3] = (roi[:, :, :3] * (1 - a) + lr * a).astype(np.uint8)
            roi[:, :, 3] = np.maximum(roi[:, :, 3], la)

    def _draw_hand(self, rgb, al8, hand, breath):
        """Tangan = lapisan terpisah, diputar di pergelangan + digeser, ditempel di atas badan."""
        dx, dy, rot, sc = hand if hand else (0.0, 0.0, 0.0, 1.0)
        L = self.lm
        pvx, pvy = L["hand_pivot"][0] * S, L["hand_pivot"][1] * S
        by = breath * 5.0 * self.u * S                                       # ikut napas badan
        hh, hw = self.hand_a.shape
        ox, oy = self.hand_org
        mg = int(60 * S)
        rx0, ry0 = max(0, int(ox - mg)), max(0, int(oy - mg))
        rx1, ry1 = min(self.w, int(ox + hw + mg)), min(self.h, int(oy + hh + mg))
        T0 = np.array([[1, 0, ox], [0, 1, oy], [0, 0, 1]], np.float64)
        R = cv2.getRotationMatrix2D((pvx, pvy), rot, sc)
        R3 = np.vstack([R, [0, 0, 1]])
        T1 = np.array([[1, 0, dx * S - rx0], [0, 1, dy * S + by - ry0], [0, 0, 1]], np.float64)
        M = (T1 @ R3 @ T0)[:2]
        size = (rx1 - rx0, ry1 - ry0)
        hr = cv2.warpAffine(self.hand_rgb, M, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        ha = cv2.warpAffine(self.hand_a, M, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        a = ha.astype(np.float32)[:, :, None] / 255.0
        roi = rgb[ry0:ry1, rx0:rx1]
        roi[:] = (roi * (1 - a) + hr * a).astype(np.uint8)
        al8[ry0:ry1, rx0:rx1] = np.maximum(al8[ry0:ry1, rx0:rx1], ha)

    def _lid(self, rgb, cx, cy, p, skin, angle):
        rx, ry = self.lm["eye_rx"] * S + 2, self.lm["eye_ry"] * S + 2
        H_, W_ = rgb.shape[:2]
        x0, x1 = max(0, int(cx - rx - 8)), min(W_, int(cx + rx + 8))
        y0, y1 = max(0, int(cy - ry - 8)), min(H_, int(cy + ry + 8))
        if x1 <= x0 or y1 <= y0:
            return
        a = math.radians(angle)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        xl = (xx - cx) * math.cos(a) + (yy - cy) * math.sin(a)             # koordinat lokal sejajar mata
        yl = -(xx - cx) * math.sin(a) + (yy - cy) * math.cos(a)
        y_lid = -ry + 2 * ry * min(1.0, p)
        inside = ((xl / rx) ** 2 + (yl / ry) ** 2) < 1.0
        m = (inside & (yl < y_lid)).astype(np.uint8) * 255
        m = cv2.GaussianBlur(m, (0, 0), 1.0).astype(np.float32)[:, :, None] / 255.0
        sub = rgb[y0:y1, x0:x1]
        sub[:] = (sub * (1 - m) + np.array(skin, np.float32) * m).astype(np.uint8)
        ox, oy = -math.sin(a) * y_lid, math.cos(a) * y_lid                 # garis kelopak di y_lid
        p0 = (int(cx - rx * math.cos(a) + ox), int(cy - rx * math.sin(a) + oy))
        p1 = (int(cx + rx * math.cos(a) + ox), int(cy + rx * math.sin(a) + oy))
        mid = (int((p0[0] + p1[0]) / 2 - math.sin(a) * 3 * S), int((p0[1] + p1[1]) / 2 + 3 * S * math.cos(a)))
        cv2.polylines(rgb, [np.array([p0, mid, p1], np.int32)], False, (40, 28, 24), max(2, int(3 * S)), cv2.LINE_AA)

    def _mouth(self, rgb, to_out, d):
        """Gambar dasar sudah senyum terbuka. Saat rahang turun, celah di bawah gigi diisi rongga gelap (warna asli gambar)."""
        L = self.lm
        (x0, y0), (x1, y1), (x2, y2) = L["seam"]
        n = 40
        t = np.linspace(0, 1, n)
        cx_, cy_ = 2 * x1 - (x0 + x2) / 2, 2 * y1 - (y0 + y2) / 2
        X = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx_ + t ** 2 * x2
        Y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy_ + t ** 2 * y2
        gi = np.clip((X * S).astype(int), 0, len(self.gcol) - 1)
        h = d * self.gcol[gi]                                                        # sama dengan pergeseran rahang
        if h.max() < 0.8:
            return
        U = np.array([to_out(x, y) for x, y in zip(X, Y)], np.float32)
        Lo = U.copy()
        Lo[:, 1] += h
        poly = np.vstack([U, Lo[::-1]])
        bx0, by0 = np.floor(poly.min(0)).astype(int) - 6
        bx1, by1 = np.ceil(poly.max(0)).astype(int) + 7
        bx0, by0 = max(0, bx0), max(0, by0)
        bx1, by1 = min(rgb.shape[1], bx1), min(rgb.shape[0], by1)
        if bx1 <= bx0 or by1 <= by0:
            return
        reg = rgb[by0:by1, bx0:bx1]
        P = ((poly - np.array([bx0, by0], np.float32)) * 16).astype(np.int32)
        cv2.fillPoly(reg, [P], self.cav, cv2.LINE_AA, shift=4)

    # ------------------------------------------------------------ stiker (outline putih + tinta)
    def sticker(self, rgba, white="#FFFDF6", ink="#23201C", w1=14, w2=4):
        pad = 18
        rgba = np.pad(rgba, ((pad, pad), (pad, pad), (0, 0)))
        rgba[-pad:, pad:-pad] = rgba[-pad - 1:-pad, pad:-pad]               # tepi bawah terpotong -> lanjutkan
        rgba[:pad, pad:-pad] = 0
        a = cv2.resize(rgba[:, :, 3], None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        k1 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (w1 // 2 + 1, w1 // 2 + 1))
        k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, ((w1 + w2) // 2 + 1, (w1 + w2) // 2 + 1))
        sz = (rgba.shape[1], rgba.shape[0])
        d1 = cv2.resize(cv2.dilate(a, k1), sz, interpolation=cv2.INTER_LINEAR)
        d2 = cv2.resize(cv2.dilate(a, k2), sz, interpolation=cv2.INTER_LINEAR)
        d1 = cv2.GaussianBlur(d1, (0, 0), 1.0).astype(np.float32)[:, :, None] / 255.0
        d2 = cv2.GaussianBlur(d2, (0, 0), 1.0)
        ink_c = np.array([int(ink[i:i + 2], 16) for i in (1, 3, 5)], np.float32)
        white_c = np.array([int(white[i:i + 2], 16) for i in (1, 3, 5)], np.float32)
        col = ink_c * (1 - d1) + white_c * d1
        fa = rgba[:, :, 3:4].astype(np.float32) / 255.0
        col = col * (1 - fa) + rgba[:, :, :3] * fa
        out = np.empty_like(rgba)
        out[:, :, :3] = col.astype(np.uint8)
        out[:, :, 3] = d2
        return out


_FIG = {}


def get_figure(style="asli"):
    if style not in _FIG:
        _FIG[style] = Figure(style=style)
    return _FIG[style]


def available():
    return os.path.exists(FIG_PATH)
