"""
Render storyboard (script["adegan"]) menjadi Reels doodle 1080x1920 @30fps.

Alur: TTS per adegan -> timeline -> aktor per adegan (goresan, teks, tokoh, ikon) -> frame RGB di-pipe ke ffmpeg
-> campur narasi + SFX (+ BGM opsional) -> MP4.
preview_scene() memakai kode yang sama untuk gambar diam (thumbnail di UI).
"""
import math
import os
import pickle
import random
import shutil
import subprocess
import sys
import tempfile
import time
import wave
import zlib

import cv2
import numpy as np

import aw_ai as ai
import aw_common as C
import aw_doodle as D
import aw_bg as BG
import aw_figur as FG
import aw_kata as K
import aw_cerita as CT
import aw_dunia as DN
import aw_fx as FX
import aw_holo as HL
import aw_kisah as KS
import aw_aura as AU
import aw_gestur as GS
import aw_latar as AL
import aw_layout as LY
import aw_stik as SK

W, H, FPS = D.W, D.H, 30
SR = 48000
STAGE_TOP, FEET_Y, SUB_TOP = 330, 1392, 1436
SPEECH_DELAY = 0.3


# ================================================================ aktor
class PhotoCharA:
    """Ustad dari foto (aw_figur): napas, goyang kepala, kedip, mulut mengikuti suara, ikon ekspresi."""
    EXPR_ICON = {"kaget": "seru", "bingung": "tanya", "senang": "bintang", "serius": None}
    TILT = {"mikir": 6.0, "tunjuk": -3.0, "lambai": 3.5}

    def __init__(self, x, y, s, pose, expr, t0, style, aura=False, intro=False, name=None):
        self.x, self.y, self.s, self.pose, self.expr, self.t0 = x, y, s, pose, expr, t0
        self.fig = FG.get_figure(style)
        self.aura, self.intro, self.name = aura, intro, name
        self.walk = False
        self.gest = None                                                   # jadwal gerak tangan per kata (aw_gestur)

    def _walk(self, t, tg):
        """Gus Idrus melangkah: masuk dari kanan (adegan 1), lalu mondar-mandir pelan di pojoknya.
        Pola dari waktu global -> posisi menyambung antar adegan. Return (dx, dy, goyang)."""
        if not self.walk:
            return 0.0, 0.0, 0.0
        mv, dx = 0.0, 0.0
        if self.intro and t < 1.5:
            p = t / 1.5
            dx = (1 - (1 - (1 - p) ** 2)) * 430
            mv = 1.0 if p < 0.92 else (1 - p) / 0.08
        else:
            per, A = 10.0, 125.0
            q = tg % per
            if q < 3.6:
                dx = 0.0
            elif q < 5.0:
                p = (q - 3.6) / 1.4
                dx, mv = -A * (0.5 - 0.5 * math.cos(math.pi * p)), math.sin(math.pi * p) ** 0.5
            elif q < 8.6:
                dx = -A
            else:
                p = (q - 8.6) / 1.4
                dx, mv = -A + A * (0.5 - 0.5 * math.cos(math.pi * p)), math.sin(math.pi * p) ** 0.5
        step = tg * 2 * math.pi * 1.9
        dy = -11.0 * abs(math.sin(step)) * mv
        return dx, dy, 3.2 * math.sin(step) * mv

    def hand_motion(self, t, tg, m, talking, fk):
        """Gerak tangan: HANYA berputar di kelim lengan baju (engsel) -> lengan tidak terputus. Positif = jari naik."""
        if fk <= 0:
            return None
        ramp = min(1.0, (t - self.t0) / 0.6)
        A = (1.0 if talking else 0.3) * min(1.2, 0.6 + 0.4 * fk) * ramp
        ph = tg * 2.5
        rot = A * (3.2 + 2.8 * math.sin(ph + 0.6)) + 1.2 * m * A
        pose = self.pose
        if pose == "tunjuk":
            q = 0.5 + 0.5 * math.sin(tg * 2.0)
            rot += ramp * (5.0 + 3.0 * q)
        elif pose == "mikir":
            rot += 11.0 * ramp
        elif pose == "lambai":
            rot = ramp * (7.0 + 7.0 * math.sin(tg * 7.0))
        if self.expr == "kaget":
            rot += 6.0 * ramp
        return (0.0, 0.0, rot, 1.0 + 0.012 * A * math.sin(ph))

    def draw(self, img, t, ctx):
        if t < self.t0:
            return None
        tg = ctx["tg"]
        fk = ctx.get("fxk", 1.0)
        talking = ctx["talking"]
        m = min(1.0, ctx["mouth"](tg) * 1.15) if talking else 0.0
        ph = tg % 3.6
        blink = max(0.0, 1.0 - abs(ph - 3.45) / 0.09) if ph > 3.36 else 0.0
        ph2 = (tg + 1.7) % 5.9
        blink = max(blink, max(0.0, 1.0 - abs(ph2 - 5.75) / 0.09) if ph2 > 5.66 else 0.0)
        tilt = self.TILT.get(self.pose, 0.0) + (2.0 * math.sin(tg * 0.9) + (1.6 * math.sin(tg * 2.6) * (0.4 + m) if talking else 0.5 * math.sin(tg * 1.7))) * (0.5 + 0.5 * fk)
        nod = (1.4 * m + (0.9 * math.sin(tg * 4.4) if talking else 0.0)) * fk
        breath = math.sin(tg * 2.1) * fk
        if self.expr == "kaget":
            nod -= 1.2
        shape = ctx["shape"](tg) if "shape" in ctx and talking else 0.0
        wx, wy, wt = self._walk(t - self.t0, tg)
        tilt += wt
        hand = self.hand_motion(t, tg, m, talking, fk)
        gst = GS.pose_at(self.gest, t - self.t0) if self.gest else None
        fr = self.fig.frame(mouth=m, blink=blink, nod=nod, tilt=tilt, breath=breath, wide=shape, hand=hand, gesture=gst)
        fr = self.fig.sticker(fr)
        k = 1.0 if self.walk else D.ease_back(min(1.0, (t - self.t0) / 0.35))
        target_w = 560 * (self.s / 0.78) * (1.0 + 0.012 * breath)             # lebar tampil figur (px layar)
        sc = target_w / self.fig.w * max(0.05, k)
        padl = (fr.shape[1] - self.fig.w - 36) * sc                          # ruang kiri untuk tangan (aw_figur.PAD_L)
        w, h = self.fig.w * sc, fr.shape[0] * sc                            # w = lebar badan saja
        x = min(max(self.x, w / 2 + 6), W - w / 2 - 6) + wx
        xc = x - padl / 2                                                    # pusat sprite (termasuk ruang kiri)
        bottom = self.y + 34 + wy
        if self.aura:                                                      # aura Gus Idrus (aw_aura)
            AU.ustad_back(img, x, bottom - h * 0.55, bottom, w, h, tg, t - self.t0, talking, m, min(1.0, k), self.intro)
            nw, nh = max(1, int(fr.shape[1] * sc)), max(1, int(fr.shape[0] * sc))
            al = cv2.resize(fr[:, :, 3], (nw, nh), interpolation=cv2.INTER_AREA)
            AU.ustad_glow(img, al, int(round(xc - nw / 2)), int(round(bottom - h / 2 - nh / 2)), tg, m, min(1.0, k))
        else:
            BG.halo(img, x, bottom - h * 0.62, w * 0.42, ctx["P"]["accent2"], tg, fk, min(1.0, k))
        D.blit(img, fr, xc, bottom - h / 2, scale=sc, anchor="c")
        if self.aura:
            AU.ustad_front(img, x, bottom, w, h, tg, t - self.t0, 1.0, self.intro, self.name)
        ic = self.EXPR_ICON.get(self.expr)
        if ic and t - self.t0 > 0.4:
            P = ctx["P"]
            sz = int(130 * self.s / 0.78)
            pop = D.ease_back(min(1.0, (t - self.t0 - 0.4) / 0.4))
            D.icon(ic, sz, P).render(img, x + w * 0.30 - sz / 2, bottom - h - sz * 0.25 + 4 * math.sin(tg * 3), max(0.05, pop), 1.0, 0, 0)
        return None


def char_a(st, x, y, s, pose, expr, t0=0.0, intro=False, name=None, walk=False, gest=None):
    if LY.pojok():                                                     # tata letak pojok: Gus Idrus kecil di kanan bawah
        x, y, s = LY.UX, LY.UY, LY.US
    if st.get("figur", "asli") != "tokoh" and FG.available():
        a = PhotoCharA(x, y, s, pose, expr, t0, st.get("figur", "asli"), aura=st.get("aura", True), intro=intro,
                       name=name if st.get("papan_nama", True) else None)
        a.walk = bool(walk and st.get("ustad_jalan", True))
        a.gest = gest if st.get("gestur", True) else None
        return a
    return CharA(x, y, s, pose, expr, t0)


class DrawA:
    def __init__(self, drawing, x, y, s=1.0, t0=0.0, dur=0.6, pop=False, boil=True, pen=True, bob=False):
        self.d, self.x, self.y, self.s, self.t0, self.dur, self.pop, self.boil, self.pen = drawing, x, y, s, t0, dur, pop, boil, pen
        self.bob, self.ph = bob, (x * 0.013 + y * 0.007)

    def draw(self, img, t, ctx):
        if t < self.t0:
            return None
        p = (t - self.t0) / max(1e-3, self.dur)
        seed = (ctx["frame"] // 4) if (self.boil and ctx["boil"]) else 0
        if self.pop:
            k = D.ease_back(min(1.0, p))
            cx, cy = self.x, self.y
            self.d.render(img, cx, cy, self.s * max(0.05, k), 1.0, seed, 1.2 if ctx["boil"] else 0)
            return None
        yy = self.y
        if self.bob and p > 1.0 and ctx.get("fxk", 1.0) > 0:        # ikon melayang pelan setelah selesai digambar
            yy += 9 * ctx.get("fxk", 1.0) * min(1.0, p - 1.0) * math.sin((t - self.t0) * 2.4 + self.ph)
        tip = self.d.render(img, self.x, yy, self.s, min(1.0, p), seed, 1.3 if ctx["boil"] else 0)
        return tip if (p < 1 and self.pen) else None


class TextA:
    def __init__(self, block, x, y, t0=0.0, dur=0.8, mode="wipe", anchor="tc"):
        self.arr, self.rects, self.rtl = block[0], block[1], block[2]
        self.x, self.y, self.t0, self.dur, self.mode, self.anchor = x, y, t0, dur, mode, anchor

    @property
    def h(self):
        return self.arr.shape[0]

    def draw(self, img, t, ctx):
        if t < self.t0:
            return None
        p = min(1.0, (t - self.t0) / max(1e-3, self.dur))
        if self.mode == "pop":
            D.blit(img, self.arr, self.x, self.y + self.h / 2 if self.anchor == "tc" else self.y, scale=max(0.05, D.ease_back(p)),
                   anchor="c" if self.anchor == "tc" else self.anchor)
            return None
        if self.mode == "fade":
            D.blit(img, self.arr, self.x, self.y, alpha=D.ease_out(p), anchor=self.anchor)
            return None
        return D.blit(img, self.arr, self.x, self.y, reveal=p if p < 1 else 1.0, rects=self.rects, rtl=self.rtl, anchor=self.anchor)


class CharA:
    def __init__(self, x, y, s, pose, expr, t0=0.0):
        self.x, self.y, self.s, self.pose, self.expr, self.t0 = x, y, s, pose, expr, t0

    def draw(self, img, t, ctx):
        if t < self.t0:
            return None
        tg = ctx["tg"]
        mouth = ctx["mouth"](tg)
        talking = ctx["talking"]
        blink = (tg % 3.3) < 0.12
        d = D.character(ctx["style"], ctx["P"], self.pose, self.expr, mouth if talking else 0.0, blink, tg, talking)
        k = D.ease_back(min(1.0, (t - self.t0) / 0.35))
        seed = (ctx["frame"] // 4) if ctx["boil"] else 0
        fk = ctx.get("fxk", 1.0)
        dy = fk * (3.0 * math.sin(tg * 3.1) - (9.0 * mouth if talking else 0.0))     # napas + angguk saat bicara
        d.render(img, self.x, self.y + dy, self.s * max(0.05, k), 1.0, seed, 1.0 if ctx["boil"] else 0)
        return None


# ================================================================ adegan
def _bubble(x0, y0, x1, y1, tail_to, P):
    d = D.Drawing()
    d.rrect(x0, y0, x1, y1, 40, P["ink"], P["card"], 6)
    tx, ty = tail_to
    mx = min(max(tx, x0 + 80), x1 - 120)
    tail = [(mx, y1 - 4), (tx, ty), (mx + 70, y1 - 4)]
    d.fill(tail, P["card"])
    d.line(tail, P["ink"], 6)
    return d


def _card(y0, y1, P, accent):
    d = D.Drawing()
    d.rrect(60, y0, 1020, y1, 36, P["ink"], P["card"], 6)
    d.line(D.rrect_pts(80, y0 + 20, 1000, y1 - 20, 26), accent, 3)
    for cx, cy in ((80, y0 + 20), (1000, y0 + 20), (80, y1 - 20), (1000, y1 - 20)):
        d.shape([(cx, cy - 12), (cx + 12, cy), (cx, cy + 12), (cx - 12, cy)], accent, accent, 2)
    return d


def _pill(text, fill, color, size=40):
    blk = D.text_block(text, "hand", size, color, 900)
    h, w = blk[0].shape[:2]
    d = D.Drawing()
    d.rrect(-w / 2 - 18, -h / 2 + 2, w / 2 + 18, h / 2 - 2, h / 2, "#23201C", fill, 4)
    return d, blk


def _burst(cx, cy, rx, ry, color, n=14):
    d = D.Drawing()
    for k in range(n):
        a = k * 2 * math.pi / n
        r0, r1 = 1.0, 1.18 + 0.08 * (k % 2)
        d.line([(cx + rx * r0 * math.cos(a), cy + ry * r0 * math.sin(a)), (cx + rx * r1 * math.cos(a), cy + ry * r1 * math.sin(a))], color, 7)
    return d


def build_scene(sc, speech, P, st, cfg, stage=False, story=False, info=None):
    """Return (aktor, sfx[(t, nama, vol)]). Waktu relatif awal adegan; speech = (mulai, selesai) narasi.
    story=True (tata letak pojok): judul/teks di atas, sisanya panggung cerita stickman -> info["top"] = batas atas panggung."""
    A, S = [], []
    info = info if info is not None else {}
    pj = LY.pojok()
    ink, acc, acc2 = P["ink"], P["accent"], P["accent2"]
    tp = sc.get("tipe", "bicara")
    s0, s1 = speech
    span = max(1.0, s1 - s0)

    if tp == "tanya" and story:
        blk = D.fit_text(sc.get("teks") or "", "hand", 76, ink, 960, 200, min_size=44, hi_color=P["hi"])
        A.append(TextA(blk, W / 2, 352, 0.15, min(1.4, 0.35 + 0.03 * len(sc.get("teks", ""))), "wipe"))
        A.append(char_a(st, 540, FEET_Y, 0.78, "mikir", "bingung", 0.0))
        info["top"] = 352 + blk[0].shape[0] + 14
        S += [(0.9, "question", 0.8)]

    elif tp == "bicara" and story:
        blk = D.fit_text(sc.get("teks") or "", "hand", 54, ink, 960, 128, min_size=34, hi_color=P["hi"])
        A.append(TextA(blk, W / 2, 348, 0.3, min(1.3, 0.3 + 0.03 * len(sc.get("teks", ""))), "wipe"))
        A.append(char_a(st, 540, FEET_Y, 0.78, sc.get("pose") or "jelasin", sc.get("ekspresi") or "biasa", 0.0))
        info["top"] = 348 + blk[0].shape[0] + 12
        S.append((0.05, "swish", 0.5))

    elif tp == "tanya":
        blk = D.fit_text(sc.get("teks") or "", "hand", 88, ink, 940, 380, hi_color=P["hi"])
        A.append(TextA(blk, W / 2, 370, 0.15, min(1.6, 0.35 + 0.03 * len(sc.get("teks", ""))), "wipe"))
        if stage:                                         # ustad mengecil di pojok, panggung gambar (aw_cerita) di kiri
            A.append(char_a(st, 905, FEET_Y, 0.46, "mikir", "bingung", 0.0))
            A.append(DrawA(D.icon("tanya", 120, P), 900 - 60, 800 - 60, 1.0, 0.9, 0.45))
            S += [(0.9, "question", 0.8)]
        else:
            A.append(char_a(st, 540, FEET_Y, 0.78, "mikir", "bingung", 0.0))
            for i, (x, y, sz) in enumerate(((150, 800, 130), (860, 760, 150))):
                A.append(DrawA(D.icon("tanya", sz, P), x - sz / 2, y - sz / 2, 1.0, 0.9 + i * 0.35, 0.45))
            S += [(0.9, "question", 0.8)]
            A.append(FX.BurstA(150, 800, 1.05, "stars", 8, P, 0.8, 0.5))
            A.append(FX.BurstA(860, 760, 1.4, "stars", 8, P, 0.8, 0.5))

    elif tp == "bicara":
        blk = D.fit_text(sc.get("teks") or "", "hand", 64, ink, 820, 330, hi_color=P["hi"])
        th = blk[0].shape[0]
        y0, y1 = 360, 360 + th + 56
        cx = 905 if stage else 560
        A.append(DrawA(_bubble(70, y0, 1010, y1, (cx - 40, y1 + 90), P), 0, 0, 1.0, 0.0, 0.45, pen=False))
        A.append(TextA(blk, W / 2, y0 + 24, 0.4, min(1.5, 0.3 + 0.03 * len(sc.get("teks", ""))), "wipe"))
        A.append(char_a(st, cx, FEET_Y, 0.46 if stage else 0.78, sc.get("pose") or "jelasin", sc.get("ekspresi") or "biasa", 0.0))
        ics = [] if stage else (sc.get("ikon") or [])[:2]
        spots = ((180, 920), (900, 930)) if pj else ((180, 1070), (900, 1080))
        for i, name in enumerate(ics):
            t0 = s0 + span * (0.25 + 0.35 * i)
            A.append(DrawA(D.icon(name, 190, P), spots[i][0] - 95, spots[i][1] - 95, 1.0, t0, 0.6, bob=True))
            A.append(FX.BurstA(spots[i][0], spots[i][1], t0 + 0.4, "stars", 9, P, 0.8, 0.5))
            S.append((t0, "pop", 0.7))
        S.append((0.05, "swish", 0.5))

    elif tp in ("quran", "hadits"):
        y0, y1 = 352, 1012
        A.append(DrawA(_card(y0, y1, P, acc if tp == "quran" else acc2), 0, 0, 1.0, 0.0, 0.5, pen=False))
        head = "قَالَ اللّٰهُ تَعَالَى" if tp == "quran" else "قَالَ رَسُوْلُ اللّٰهِ ﷺ"
        hb = D.text_block(head, "arab_bold", 50, acc if tp == "quran" else mix_hex(acc2, ink), 860)
        items = [(hb, "fade", 0.35)]
        arab = (sc.get("arab_tampil") or (sc.get("ayat_data") or {}).get("arab", "")) if tp == "quran" else ""
        trans = sc.get("tampil") or sc.get("kutipan") or ""
        room = (y1 - y0) - 60 - hb[0].shape[0] - 80
        if arab and len(arab) <= 260:
            ab = D.fit_text(arab, "arab", 64, ink, 860, int(room * 0.5), min_size=40)
            items.append((ab, "wipe", 0.8))
            room -= ab[0].shape[0]
        tb = D.fit_text(f"“{trans}”", "hand_reg", 48, ink, 860, max(120, room), min_size=28, hi_color=P["hi"])
        items.append((tb, "wipe", 1.0))
        total = sum(b[0].shape[0] for b, _, _ in items) + 20 * (len(items) - 1)
        y = y0 + 34 + max(0, ((y1 - y0) - 90 - total) / 2)
        t = 0.45
        for b, mode, dd in items:
            dur = dd if mode != "wipe" else min(2.2, 0.4 + b[0].shape[0] / 160 + len(b[1]) * 0.25)
            A.append(TextA(b, W / 2, y, t, dur, mode))
            y += b[0].shape[0] + 20
            t += dur * 0.85
        ref = sc.get("ref_label") or ""
        if ref:
            pd, pb = _pill(ref, acc if tp == "quran" else acc2, (255, 255, 255) if tp == "quran" else D.rgb("#23201C"), 40)
            A.append(DrawA(pd, W / 2, y1, 1.0, t, 0.35, pop=True))
            A.append(TextA(pb, W / 2, y1 - pb[0].shape[0] / 2, t + 0.05, 0.3, "pop"))
            S.append((t, "stamp", 0.6))
            A.append(FX.BurstA(W / 2, y1, t, "confetti", 34, P, 1.3))
        if tp == "quran":
            note = D.text_block("Terjemah: Kemenag RI", "hand_reg", 30, P["mute"], 600)
            A.append(TextA(note, 780, y1 + 26, t + 0.3, 0.4, "fade"))
        A.append(char_a(st, 170, FEET_Y, 0.5, "tunjuk" if tp == "quran" else "jelasin", "serius", 0.0))
        if not pj:
            A.append(DrawA(D.icon("buku" if tp == "quran" else "lampu", 190, P), 760, 1110, 1.0, t + 0.2, 0.6, bob=True))
        S += [(0.05, "swish", 0.5), (0.5, "sparkle", 0.6)]

    elif tp == "poin":
        tb = D.fit_text(sc.get("judul") or "", "hand", 70, ink, 940, 170, hi_color=P["hi"])
        A.append(TextA(tb, W / 2, 352, 0.1, 0.7, "wipe"))
        und = D.Drawing().line(D.quad((300, 0), (540, 14), (780, 0)), acc2, 8)
        A.append(DrawA(und, 0, 352 + tb[0].shape[0] + 4, 1.0, 0.7, 0.35, pen=False))
        pts = (sc.get("poin") or [])[:3]
        n = max(1, len(pts))
        top = 352 + tb[0].shape[0] + 50
        rowh = min(215, (1080 - top) / n)
        for i, po in enumerate(pts):
            cy = top + i * rowh + rowh / 2
            t0 = max(0.6, s0 + span * i / n)
            circ = D.Drawing().circle(0, 0, 82, ink, P["paper2"], 5)
            A.append(DrawA(circ, 175, cy, 1.0, t0, 0.35, pop=True))
            A.append(DrawA(D.icon(po.get("ikon", ""), 120, P), 115, cy - 60, 1.0, t0 + 0.15, 0.5, bob=True))
            A.append(FX.BurstA(175, cy, t0 + 0.15, "drops", 10, P, 0.8, 0.5))
            blk = D.fit_text(po.get("teks", ""), "hand", 50, ink, 560, int(rowh - 10), min_size=32, align="left", hi_color=P["hi"])
            A.append(TextA(blk, 290, cy - blk[0].shape[0] / 2, t0 + 0.35, 0.7, "wipe", anchor="tl"))
            S.append((t0, "pop", 0.7))
        A.append(char_a(st, 935, FEET_Y, 0.48, "jelasin", "biasa", 0.0))

    elif tp == "langkah":
        tb = D.fit_text(sc.get("judul") or "", "hand", 70, ink, 940, 170, hi_color=P["hi"])
        A.append(TextA(tb, W / 2, 352, 0.1, 0.7, "wipe"))
        steps = (sc.get("langkah") or [])[:5]
        n = max(1, len(steps))
        top = 352 + tb[0].shape[0] + 40
        rowh = min(150, ((1100 if pj else 1180) - top) / n)
        for i, stp in enumerate(steps):
            cy = top + i * rowh + rowh / 2
            t0 = max(0.5, s0 + span * i / n)
            box = D.Drawing().rrect(-30, -30, 30, 30, 10, ink, P["card"], 5)
            A.append(DrawA(box, 120, cy, 1.0, t0, 0.3))
            blk = D.fit_text(stp, "hand", 48, ink, 640, int(rowh - 8), min_size=30, align="left", hi_color=P["hi"])
            A.append(TextA(blk, 180, cy - blk[0].shape[0] / 2, t0 + 0.25, 0.6, "wipe", anchor="tl"))
            chk = D.Drawing().line([(-22, 0), (-6, 18), (30, -30)], P["ok"], 11)
            A.append(DrawA(chk, 124, cy - 4, 1.0, t0 + 0.9, 0.25, pen=False))
            S.append((t0 + 0.9, "tick", 0.8))
            A.append(FX.BurstA(124, cy, t0 + 0.9, "stars", 8, P, 0.7, 0.45))
        A.append(char_a(st, 960, FEET_Y, 0.45, "jelasin", "senang", 0.0))

    elif tp == "fakta":
        bb = D.fit_text(sc.get("besar") or "", "hand", 150, acc, 900, 330, min_size=70, stroke=3, stroke_color=P["ink"])
        h = bb[0].shape[0]
        cy = 380 + h / 2
        A.append(DrawA(_burst(W / 2, cy, min(470, bb[0].shape[1] / 2 + 40), h / 2 + 30, acc2), 0, 0, 1.0, 0.45, 0.4, pen=False))
        A.append(TextA(bb, W / 2, 380, 0.15, 0.4, "pop"))
        kb = D.fit_text(sc.get("kecil") or "", "hand_reg", 54, ink, 920, 260, hi_color=P["hi"])
        A.append(TextA(kb, W / 2, 380 + h + 60, 0.8, 0.9, "wipe"))
        A.append(char_a(st, 540, FEET_Y, 0.66, "senang", "kaget", 0.0))
        S += [(0.15, "sparkle", 0.7)]
        A.insert(0, FX.SunA(W / 2, cy, P["accent2"]))
        A.append(FX.BurstA(W / 2, cy, 0.2, "confetti", 40, P, 1.5, 1.2))

    elif tp == "penutup":
        qb = D.fit_text(sc.get("tanya") or "", "hand", 72, ink, 940, 270, hi_color=P["hi"])
        A.append(TextA(qb, W / 2, 360, 0.1, 0.9, "wipe"))
        y0 = 360 + qb[0].shape[0] + 40
        a, b = (sc.get("a") or "").strip(), (sc.get("b") or "").strip()
        if a and b:
            for i, (lab, txt, col) in enumerate((("A", a, acc), ("B", b, acc2))):
                x0 = 70 + i * 490
                box = D.Drawing().rrect(x0, y0, x0 + 450, y0 + 200, 30, P["ink"], col, 6)
                A.append(DrawA(box, 0, 0, 1.0, 1.0 + i * 0.5, 0.4, pen=False))
                tc = (255, 255, 255) if i == 0 else D.rgb("#23201C")
                tb = D.fit_text(f"{lab}. {txt}", "hand", 50, tc, 400, 180, min_size=30)
                A.append(TextA(tb, x0 + 225, y0 + 100 - tb[0].shape[0] / 2, 1.2 + i * 0.5, 0.5, "pop"))
                S.append((1.0 + i * 0.5, "pop2", 0.7))
            y0 += 230
        else:
            tb = D.text_block("Tulis jawabanmu di kolom komentar", "hand", 52, acc, 900)
            A.append(TextA(tb, W / 2, y0, 1.0, 0.8, "wipe"))
            y0 += tb[0].shape[0] + 30
        fb = D.text_block(f"Follow {cfg.get('account_name', '')} untuk penjelasan lainnya", "hand_reg", 40, P["mute"], 940)
        A.append(TextA(fb, W / 2, y0, 1.8, 0.5, "fade"))
        A.append(char_a(st, 540, FEET_Y, 0.6, "lambai", "senang", 0.0))
        S += [(1.8, "notif", 0.5)]
        A.append(FX.BurstA(W / 2, 700, 1.8, "stars", 16, P, 1.2, 0.9))

    return A, S


PULSE = {"stamp": (0.055, 9), "sparkle": (0.04, 0), "pop": (0.022, 0), "pop2": (0.03, 0), "tick": (0.018, 0),
         "question": (0.04, 0), "notif": (0.03, 0), "swish": (0.0, 0)}


def scene_pulses(tp, S, speech):
    """Beat kamera: awal adegan, tiap SFX penting, dan satu denyut di tengah narasi."""
    pulses = [(0.0, 0.06 if tp in ("tanya", "fakta") else 0.04, 0)]
    for t, name, _v in S:
        amp, shake = PULSE.get(name, (0, 0))
        if amp:
            pulses.append((t, amp, shake))
    a, b = speech
    if tp in ("bicara", "poin", "langkah", "quran", "hadits"):
        pulses.append((a + (b - a) * 0.55, 0.03, 0))
    return pulses


def mix_hex(c, ink):
    return D.mix(c, ink, 0.35)


def header_actors(script, P, st, cfg):
    if not st["header"]:
        return []
    A = []
    title = script.get("judul_pendek") or ""
    tb = D.fit_text(title, "hand", 58, P["ink"], 940, 128, min_size=36, hi_color=P["hi"])
    th = tb[0].shape[0]
    y1 = 178 + th + 18
    box = D.Drawing().rrect(40, 112, 1040, y1, 30, P["ink"], P["card"], 5)
    A.append(DrawA(box, 0, 0, 1.0, 0.0, 0.5, pen=False, boil=False))
    lab = cfg.get("series_label") or ""
    if lab:
        pd, pb = _pill(lab, P["accent"], (255, 255, 255), 34)
        A.append(DrawA(pd, W / 2, 112, 1.0, 0.25, 0.3, pop=True, boil=False))
        A.append(TextA(pb, W / 2, 112 - pb[0].shape[0] / 2, 0.3, 0.3, "pop"))
    A.append(TextA(tb, W / 2, 168, 0.4, 0.8, "wipe"))
    return A


# ================================================================ subtitle
def sub_chunks(text, a, b, max_chars=26):
    words = (text or "").replace("*", "").split()
    chunks, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > max_chars:
            chunks.append(" ".join(cur))
            cur = []
        cur.append(w)
        if w[-1:] in ".,!?;:" and len(" ".join(cur)) > 12:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    tot = sum(len(c) + 3 for c in chunks) or 1
    out, t = [], a
    for c in chunks:
        d = (b - a) * (len(c) + 3) / tot
        out.append((t, t + d, c))
        t += d
    return out


def sub_chunks_words(words, max_chars=26):
    """Potongan subtitle dari waktu kata asli: [(mulai, selesai, teks, [(mulai,selesai)...])] (waktu relatif adegan)."""
    chunks, cur = [], []
    for w in words:
        txt = " ".join(x[2] for x in cur)
        gap = (w[0] - (cur[-1][0] + cur[-1][1])) if cur else 0
        if cur and (len(txt) + 1 + len(w[2]) > max_chars or (gap > 0.28 and len(txt) > 10)):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    out = []
    for i, ch in enumerate(chunks):
        a = ch[0][0]
        b = ch[-1][0] + ch[-1][1] + 0.08
        if i + 1 < len(chunks) and chunks[i + 1][0][0] - b < 0.35:
            b = chunks[i + 1][0][0]
        out.append((a, b, " ".join(x[2] for x in ch), [(x[0], x[0] + x[1]) for x in ch]))
    return out


_SUB_CACHE = {}
_WORD_CACHE = {}


def _word(w, size, color):
    key = (w, size, color if isinstance(color, str) else tuple(color))
    if key not in _WORD_CACHE:
        if len(_WORD_CACHE) > 800:
            _WORD_CACHE.clear()
        arr = D.text_block(w, "hand", size, color, 900)[0]
        cols = np.where(arr[:, :, 3].max(axis=0) > 20)[0] if arr.ndim == 3 and arr.shape[2] == 4 else []
        if len(cols):
            arr = arr[:, max(0, cols[0] - 2):cols[-1] + 3]
        _WORD_CACHE[key] = arr
    return _WORD_CACHE[key]


def draw_sub(img, text, p, P, st, frac=None, cur=None, kw=None):
    """p = detik sejak potongan muncul (animasi masuk); frac 0..1 = posisi dalam potongan -> kata yang diucapkan disorot."""
    key = (text, st["sub_size"], P["ink"], P["sub_bg"])
    if key not in _SUB_CACHE:
        blk = D.text_block(text, "hand", st["sub_size"], P["ink"], 900)
        h, w = blk[0].shape[:2]
        box = D.Drawing().rrect(-w / 2 - 24, 0, w / 2 + 24, h + 14, 24, P["ink"], P["sub_bg"], 4)
        if len(_SUB_CACHE) > 300:
            _SUB_CACHE.clear()
        _SUB_CACHE[key] = (blk, box)
    blk, box = _SUB_CACHE[key]
    k = 0.92 + 0.08 * D.ease_out(p / 0.15) if p < 0.15 else 1.0
    SUB_TOP = LY.SUB_TOP
    box.render(img, W / 2, SUB_TOP, k, 1.0, 0, 0)
    words = text.split()
    if frac is None or len(words) < 2 or not st.get("sub_karaoke", True):
        D.blit(img, blk[0], W / 2, SUB_TOP + 7 + blk[0].shape[0] / 2, scale=k, anchor="c")
        return
    size = st["sub_size"]
    base = [_word(w, size, P["ink"]) for w in words]
    lit = [_word(w, size, P["hi"]) for w in words]
    gap = int(size * 0.46)
    total = sum(b.shape[1] for b in base) + gap * (len(words) - 1)
    if total > blk[0].shape[1] + 70:
        D.blit(img, blk[0], W / 2, SUB_TOP + 7 + blk[0].shape[0] / 2, scale=k, anchor="c")
        return
    if cur is None:
        wts = [len(w) + 1 for w in words]
        acc, cur = 0.0, len(words) - 1
        for i, wt in enumerate(wts):
            acc += wt / sum(wts)
            if frac <= acc:
                cur = i
                break
    cur = min(cur, len(words) - 1)
    x = W / 2 - total / 2
    cy = SUB_TOP + 7 + blk[0].shape[0] / 2
    for i, (b, l) in enumerate(zip(base, lit)):
        cx = x + b.shape[1] / 2
        if i == cur and kw and i < len(kw) and kw[i]:                 # kata bermakna: merah & lebih besar
            D.blit(img, _word(words[i], size, P["red"]), cx, cy - 4, scale=1.26 * k, anchor="c")
        elif i == cur:
            D.blit(img, l, cx, cy - 3, scale=1.14 * k, anchor="c")
        else:
            D.blit(img, b, cx, cy, scale=k, alpha=1.0 if i < cur else 0.78, anchor="c")
        x += b.shape[1] + gap


# ================================================================ audio
def _read_wav_mono(path):
    with wave.open(path, "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


def _to_wav(src, dst):
    C.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", dst])
    return dst


_SFX = {}


def sfx(name):
    if name not in _SFX:
        src = os.path.join(C.SFX_DIR, f"{name}.wav")
        if not os.path.exists(src):
            _SFX[name] = None
        else:
            cache = os.path.join(C.CACHE_DIR, "sfx")
            os.makedirs(cache, exist_ok=True)
            dst = os.path.join(cache, f"{name}.wav")
            if not os.path.exists(dst):
                _to_wav(src, dst)
            _SFX[name] = _read_wav_mono(dst)
    return _SFX[name]


def _shape(narr, n_frames):
    """Bentuk mulut dari warna suara: -1 = bulat ('o','u', frekuensi rendah) .. +1 = lebar ('e','i', frekuensi tinggi)."""
    hop = SR // FPS
    win = np.hanning(hop * 2)
    out = np.zeros(n_frames, np.float32)
    freqs = np.fft.rfftfreq(hop * 2, 1.0 / SR)
    for i in range(n_frames):
        seg = narr[max(0, i * hop - hop // 2):max(0, i * hop - hop // 2) + hop * 2]
        if len(seg) < hop * 2 or float(np.abs(seg).max()) < 0.01:
            continue
        sp = np.abs(np.fft.rfft(seg * win))
        sp[freqs > 4000] = 0
        sp[freqs < 120] = 0
        c = float((sp * freqs).sum() / (sp.sum() + 1e-6))
        out[i] = np.clip((c - 1250.0) / 800.0, -1.0, 1.0)
    return np.convolve(out, [0.2, 0.3, 0.3, 0.2], mode="same")


def _envelope(narr, n_frames):
    """Bukaan mulut 0..1 per frame: mengikuti ritme suku kata (buka di vokal, nyaris menutup di konsonan/jeda), tanpa getaran."""
    hop = SR // FPS
    rms = np.zeros(n_frames, np.float32)
    for i in range(n_frames):
        seg = narr[i * hop:(i + 1) * hop]
        if len(seg):
            rms[i] = float(np.sqrt(np.mean(seg ** 2)))
    ref = np.percentile(rms[rms > 0.003], 90) if np.any(rms > 0.003) else 1.0
    ab = np.clip(rms / (ref * 0.9 + 1e-6), 0, 1)                          # level absolut
    ab = np.convolve(ab, [0.25, 0.5, 0.25], mode="same")
    k = 4                                                                  # jendela lokal ±4 frame (~suku kata)
    pad = np.pad(ab, k, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * k + 1)
    lmax, lmin = win.max(axis=1), win.min(axis=1)
    rel = np.clip((ab - lmin) / (lmax - lmin + 0.12), 0, 1)                # level relatif: puncak vokal = 1, lembah = 0
    out = ab * (0.35 + 0.65 * rel)
    out = np.where(ab > 0.10, out, 0.0)                                    # jeda -> menutup
    out = np.convolve(out, [0.2, 0.6, 0.2], mode="same")                   # mulus antar frame
    return np.clip(out * 1.1, 0, 1).astype(np.float32)


# ================================================================ timeline
def _speak_scene(sc, work, key, cfg, rate=None):
    """Narasi ustad: pengantar -> (ayat dibaca Arab -> terjemah dibaca) -> penjelasan. Dalil benar-benar DIBACAKAN, bukan hanya ditempel."""
    import aw_voice as V
    narasi, pen = sc.get("narasi", ""), sc.get("penjelasan", "")
    rp = None if rate is None else _rate_pct(rate)
    tp = sc.get("tipe")
    if tp in ("quran", "hadits") and cfg.get("bacaan_dalil", True):
        parts = [("id", narasi), ("jeda", 0.25)]
        arab = sc.get("arab_tampil") or (sc.get("ayat_data") or {}).get("arab", "") if tp == "quran" else ""
        if arab:
            parts += [("ar", arab.replace("…", "").strip())]
        trans = (sc.get("tampil") or sc.get("kutipan") or "").replace("…", "").strip()
        if trans:
            parts += [("baca", trans), ("jeda", 0.2)]
        if pen:
            parts += [("id", pen)]
    else:
        parts = [("id", (narasi + " " + pen).strip())]
    return V.speak(parts, work, key, cfg, rp)


def plan(script, work, cfg, log=print, fake=None, rate=None):
    """TTS per adegan -> daftar (mulai, durasi, speech(a,b), audio). fake=detik -> tanpa TTS (preview)."""
    out, t = [], 0.0
    scenes = script["adegan"]
    for i, sc in enumerate(scenes):
        if fake is not None:
            aud, dur_sp, words = None, fake, []
        else:
            aud, words = _speak_scene(sc, work, f"tts_{i:02d}", cfg, rate)
            dur_sp = len(aud) / SR
            words = [(SPEECH_DELAY + o, d, w) for o, d, w in words]
        tail = 1.6 if i == len(scenes) - 1 else 0.45
        extra = 0.0
        if sc.get("tipe") in ("quran", "hadits") and dur_sp < 5:
            extra = 5 - dur_sp                      # beri waktu membaca kartu dalil
        dur = max(2.8, SPEECH_DELAY + dur_sp + tail + extra)
        out.append({"start": t, "dur": dur, "speech": (SPEECH_DELAY, SPEECH_DELAY + dur_sp), "audio": aud, "words": words})
        t += dur
    return out, t


def _rate_pct(r):
    try:
        return float(str(r).replace("%", "").replace("+", ""))
    except ValueError:
        return 4.0


def _fit_duration(script, work, cfg, tl, total, log):
    """Usahakan video ±target_sec (default 60 detik) dengan menyesuaikan kecepatan suara (-10%..+18%)."""
    target = float(cfg.get("target_sec", 60))
    if target - 4 <= total <= target + 6:
        return tl, total
    sp = sum(seg["speech"][1] - seg["speech"][0] for seg in tl)
    fixed = total - sp
    want = max(10.0, target + 1 - fixed)
    r0 = _rate_pct(cfg.get("voice_rate", "+4%"))
    r1 = max(-10.0, min(18.0, (100 + r0) * sp / want - 100))
    if script.get("format") == "kisah":                                   # bercerita: jangan dipercepat berlebihan
        r1 = min(r1, float(cfg.get("kisah_max_rate", 6)))
    if abs(r1 - r0) < 2:
        return tl, total
    rate = f"{r1:+.0f}%"
    log(f"   🎚️ durasi {total:.0f} dtk → kecepatan suara {cfg.get('voice_rate', '+4%')} → {rate} (target ±{target:.0f} dtk)")
    tl2, total2 = plan(script, work, cfg, log, rate=rate)
    return (tl2, total2) if abs(total2 - target) < abs(total - target) else (tl, total)


def render_video(script, cfg, out_path, log=print):
    st = cfg["style"]
    P = D.palette(st)
    LY.apply(st)
    work = tempfile.mkdtemp(prefix="aw_")
    try:
        ai.set_allah_ucap(cfg.get("allah_ucap"))
        log("   🎙️ narasi (edge-tts)…")
        tl, total = plan(script, work, cfg, log)
        tl, total = _fit_duration(script, work, cfg, tl, total, log)
        n_frames = int(math.ceil(total * FPS))
        log(f"   ⏱️ durasi {total:.1f} detik, {len(tl)} adegan, {n_frames} frame")
        if total > float(cfg.get("max_video_sec", 90)):
            log(f"   ⚠️ lebih panjang dari batas {cfg.get('max_video_sec')} detik — pertimbangkan meringkas narasi")

        # adegan (aktor) + audio: narasi + sfx
        narr = np.zeros(int(total * SR) + SR, np.float32)
        for seg in tl:
            a = int((seg["start"] + seg["speech"][0]) * SR)
            narr[a:a + len(seg["audio"])] += seg["audio"]
        mixd = narr.copy()
        B = _build_all(script, cfg, tl, log)
        if st["sfx"]:
            for i, seg in enumerate(tl):
                for t0, name, vol in B["sfx"][i]:
                    s = sfx(name)
                    if s is None:
                        continue
                    a = int((seg["start"] + t0) * SR)
                    b = min(len(mixd), a + len(s))
                    mixd[a:b] += s[:b - a] * vol * float(st["sfx_volume"])
        peak = float(np.max(np.abs(mixd))) or 1.0
        if peak > 0.98:
            mixd *= 0.98 / peak
        wav_path = os.path.join(work, "mix.wav")
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((np.clip(mixd[:int(total * SR)], -1, 1) * 32767).astype(np.int16).tobytes())
        env = _envelope(narr, n_frames)
        shp = _shape(narr, n_frames)

        # video: dibagi ke beberapa proses (semua inti CPU), lalu disambung tanpa encode ulang
        nw = _n_workers(cfg, n_frames)
        tlx = [{k_: v for k_, v in seg.items() if k_ != "audio"} for seg in tl]
        ranges = [(n_frames * i // nw, n_frames * (i + 1) // nw) for i in range(nw)]
        segs = [os.path.join(work, f"part_{i:02d}.mp4") for i in range(nw)]
        t_start = time.time()
        if nw <= 1:
            log("   🖌️ menggambar frame…")
            _render_range(script, cfg, tlx, total, n_frames, env, shp, 0, n_frames, segs[0], log, B)
        else:
            log(f"   🖌️ menggambar frame paralel di {nw} proses…")
            pkl = os.path.join(work, "state.pkl")
            with open(pkl, "wb") as f:
                pickle.dump({"script": script, "cfg": cfg, "tl": tlx, "total": total, "n_frames": n_frames, "env": env,
                             "shp": shp}, f)
            procs = []
            for (f0, f1), out in zip(ranges, segs):
                procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", pkl, str(f0), str(f1), out],
                                              cwd=C.BASE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
            last_log = 0.0
            while any(p.poll() is None for p in procs):
                time.sleep(1.0)
                done = 0
                for out in segs:
                    try:
                        with open(out + ".prog", encoding="utf-8") as f:
                            done += int(f.read().strip() or 0)
                    except (OSError, ValueError):
                        pass
                if time.time() - last_log > 15:
                    last_log = time.time()
                    log(f"      {done / FPS:.0f}/{total:.0f} detik ({done * 100 // max(1, n_frames)}%)")
            errs = [p.stderr.read().decode("utf-8", "replace") for p in procs if p.returncode != 0]
            if errs:
                raise RuntimeError("render paralel gagal: " + errs[0][-1500:])
        log(f"   ⏱️ gambar selesai dalam {time.time() - t_start:.0f} dtk")
        lst = os.path.join(work, "parts.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for p_ in segs:
                f.write(f"file '{p_.replace(os.sep, '/')}'\n")
        bgm = _pick_bgm() if st["bgm"] else None
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav_path]
        if bgm:
            cmd += ["-stream_loop", "-1", "-i", bgm, "-filter_complex",
                    f"[2:a]volume={float(st['bgm_volume']):.3f}[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,"
                    f"afade=t=out:st={max(0, total - 1):.2f}:d=1[a]", "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        tmp_out = os.path.join(work, "final.mp4")
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", tmp_out]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg gagal: {r.stderr.decode('utf-8', 'replace')[-800:]}")
        shutil.move(tmp_out, out_path)
        return total
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _n_workers(cfg, n_frames):
    """Jumlah proses render: config 'render_workers' (0/kosong = otomatis: inti CPU - 2, maks 8)."""
    v = int(cfg.get("render_workers") or 0)
    if v <= 0:
        v = min(8, max(1, (os.cpu_count() or 2) - 2))
    return max(1, min(v, n_frames // (FPS * 4) or 1))                      # tiap bagian minimal ±4 detik


def _build_all(script, cfg, tl, log=print):
    """Bangun aktor tiap adegan (deterministik: proses pekerja membangun ulang hasil yang sama)."""
    st = cfg["style"]
    P = D.palette(st)
    LY.apply(st)
    scenes_built, scene_pulses_l, sfx_l = [], [], []
    kstate = {"last_icon": {}, "n": 0}
    sseed = zlib.crc32((script.get("judul") or script.get("judul_pendek") or "x").encode("utf-8"))
    cast_v = SK.make_cast(script, sseed)                                  # tokoh stickman tetap satu video
    sstate = SK.story_state(script, sseed)
    if LY.pojok() and st.get("cerita_stik", True):
        log(f"   🎭 cerita stickman: {SK.cast_text(cast_v)} · nuansa {sstate['mood']}")
    wajah = AL.assign(script, st)                                         # variasi latar kisah per adegan
    for i, (sc, seg) in enumerate(zip(script["adegan"], tl)):
        if sc.get("tipe") == "kisah":                                        # format kisah: ilustrasi layar penuh (aw_kisah)
            actors, sfxs = KS.plan_scene(i, dict(sc, _wajah=wajah[i]) if wajah[i] else sc, seg, P, st)
            if st.get("kisah_ustad", True):                                  # Gus Idrus bercerita di pojok sejak awal
                actors.insert(1, char_a(st, LY.UX or 872, LY.UY, LY.US or 0.42, sc.get("pose") or ("tunjuk" if i == 0 else "jelasin"),
                                        sc.get("ekspresi") or "biasa", 0.0, intro=(i == 0), name=cfg.get("character_name"), walk=True,
                                        gest=GS.plan(seg.get("words") or [], sc.get("narasi", ""), seed=i)))
            scenes_built.append(actors)
            scene_pulses_l.append([])
            if i > 0 and st["transition"] != "tidak":
                sfxs = sfxs + [(0.0, "whoosh", 0.35)]
            sfx_l.append(sfxs)
            continue
        story_on = LY.pojok() and st.get("cerita_stik", True) and sc.get("tipe") in ("tanya", "bicara")
        cast = None if LY.pojok() else CT.plan_cast(sc, seg, P, st)          # ilustrasi tokoh lama (tata letak tengah)
        sinfo = {}
        actors, sfxs = build_scene(sc, seg["speech"], P, st, cfg, stage=bool(cast), story=story_on, info=sinfo)
        if story_on:                                                         # panggung cerita stickman
            manual = sc.get("cerita") or cfg.get("stik_llm")
            beats = SK.storyboard(sc, cast_v, cfg, topik=script.get("judul", ""), log=log, state=sstate) if manual else None
            story, ssfx = SK.plan_story(sc, seg, beats, cast_v, (40, sinfo.get("top", 480), 1040, LY.PANEL_BOTTOM), P,
                                        seed=sseed + i * 17, state=sstate)
            if story:
                actors = [story] + actors
                sfxs = sfxs + ssfx
        kstate["scene"] = i
        ka, ks, kp = K.plan_scene(sc, seg, P, kstate, st, stage=bool(cast) or story_on)   # gambar & efek per kata (waktu dari TTS)
        holo = HL.plan_scene(i, sc, seg, P, st, actors)                       # hologram tiap kata yang diucapkan
        if cast:
            actors = actors + cast["actors"]
            sfxs = sfxs + cast["sfx"]
            kp = kp + cast["pulses"]
        glow = [a for a in ka if isinstance(a, K.GlowA)]                     # sinar 'Allah' di BELAKANG tokoh
        actors = glow + actors + [a for a in ka if not isinstance(a, K.GlowA)]
        if holo:                                                             # proyektor di belakang ustad, subtitle hologram paling depan
            actors = holo["back"] + actors + holo["front"]
            sfxs = sfxs + holo["sfx"]
        sfxs = sfxs + ks
        scenes_built.append(actors)
        scene_pulses_l.append(scene_pulses(sc.get("tipe", "bicara"), sfxs, seg["speech"]) + kp)
        if i > 0 and st["transition"] != "tidak":
            sfxs = sfxs + [(0.0, "whoosh", 0.35)]
        sfx_l.append(sfxs)
    return {"scenes": scenes_built, "pulses": scene_pulses_l, "sfx": sfx_l, "hdr": header_actors(script, P, st, cfg),
            "kinds": [sc.get("tipe", "bicara") for sc in script["adegan"]]}


def _paper_subs(script, tl, st):
    subs = []
    if st["subtitles"] and not HL.sub_on(st):
        for sc, seg in zip(script["adegan"], tl):
            a, b = seg["speech"]
            if seg.get("words"):
                allfl = [f and not q for f, q in zip(K.is_keyword_flags(seg["words"]), K.ask_flags(sc, seg["words"]))]
                wi = 0
                for x, y, c, wt in sub_chunks_words(seg["words"]):
                    fl = allfl[wi:wi + len(wt)]
                    wi += len(wt)
                    subs.append((seg["start"] + x, seg["start"] + y, c, [(seg["start"] + u, seg["start"] + v) for u, v in wt], fl))
            else:
                subs += [(seg["start"] + x, seg["start"] + y, c, None, None) for x, y, c in sub_chunks(sc.get("narasi", ""), a, b)]
    return subs


def _render_range(script, cfg, tl, total, n_frames, env, shp, f0, f1, out, log=print, B=None):
    """Gambar frame [f0, f1) ke out (video saja). Mulai di tengah transisi -> frame terakhir adegan sebelumnya dihitung dulu."""
    st = cfg["style"]
    P = D.palette(st)
    LY.apply(st)
    ai.set_allah_ucap(cfg.get("allah_ucap"))
    B = B or _build_all(script, cfg, tl, log=lambda *_a, **_k: None)
    scenes_built, pulses, hdr, kinds = B["scenes"], B["pulses"], B["hdr"], B["kinds"]
    fxk = FX.level_k(st)
    subs = _paper_subs(script, tl, st)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "2", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    base = D.paper(st["theme"])
    trans = 0.45 if st["transition"] != "tidak" else 0.0
    wm = D.text_block("@" + cfg["account_name"].replace(" ", ""), "hand_reg", 32, P["mute"], 800) if cfg.get("account_name") else None
    R = {"prev_last": None, "sub_i": 0}

    def scene_of(tg):
        k = 0
        while k + 1 < len(tl) and tg >= tl[k + 1]["start"]:
            k += 1
        return k

    def frame(f):
        tg = f / FPS
        k = scene_of(tg)
        seg = tl[k]
        tl_local = tg - seg["start"]
        img = base.copy()
        kind = kinds[k]
        kisah = kind == "kisah"
        if not kisah:
            if st.get("dunia", True):
                DN.backdrop(img, tg, tl_local, kind, P, fxk)
            BG.background(img, tg, tl_local, kind, P, fxk)
            FX.ambient(img, tg, P, fxk)
            BG.rain(img, tg, tl_local, kind, P, fxk)
        a, b = seg["speech"]
        ctx = {"frame": f, "tg": tg, "boil": st["boil"], "style": st, "P": P, "fxk": fxk,
               "talking": a <= tl_local <= b + 0.1, "mouth": lambda x: float(env[min(len(env) - 1, int(x * FPS))]),
               "shape": lambda x: float(shp[min(len(shp) - 1, int(x * FPS))])}
        tip = None
        for actor in scenes_built[k]:
            r = actor.draw(img, tl_local, ctx)
            tip = r or tip
        if st.get("dunia", True) and not kisah:
            DN.finish(img, tg, tl_local, kind, P, fxk, f)
        if fxk > 0 and not kisah:
            img = FX.camera(img, tl_local, seg["dur"], tg, pulses[k], fxk)
        if k > 0 and tl_local < trans and R["prev_last"] is not None:
            _transition(img, R["prev_last"], tl_local / trans, _mode_for(st["transition"], k), P)
            tip = None
            FX.flash(img, tl_local / trans, fxk if st["transition"] == "variasi" else 0)
        if tg + 1.0 / FPS >= seg["start"] + seg["dur"] - 1e-6 or (k + 1 < len(tl) and tg + 1.0 / FPS >= tl[k + 1]["start"]):
            R["prev_last"] = img.copy()
        for actor in (hdr if not kisah else ()):
            actor.draw(img, tg, ctx)
        FX.progress_bar(img, f, n_frames, P, fxk)
        if subs:
            while R["sub_i"] + 1 < len(subs) and tg >= subs[R["sub_i"]][1]:
                R["sub_i"] += 1
            s_a, s_b, s_t, s_w, s_f = subs[R["sub_i"]]
            if s_a <= tg < s_b + 0.05:
                cur_w = None
                if s_w:
                    cur_w = max([j for j, (ws, _we) in enumerate(s_w) if ws <= tg + 0.02] or [0])
                draw_sub(img, s_t, (tg - s_a), P, st, (tg - s_a) / max(1e-3, s_b - s_a), cur_w, s_f)
        if st["watermark"] and wm is not None:
            D.blit(img, wm[0], LY.WM[0], LY.WM[1], anchor="tc", alpha=0.85)
        if st["pen"] and tip:
            D.pen(img, tip, P["ink"])
        return img

    k0 = scene_of(f0 / FPS)
    if k0 > 0 and f0 / FPS - tl[k0]["start"] < trans + 1.0 / FPS:          # butuh frame terakhir adegan sebelumnya
        frame(max(0, int(math.ceil(tl[k0]["start"] * FPS)) - 1))
    try:
        for f in range(f0, f1):
            proc.stdin.write(frame(f).tobytes())
            if (f - f0) % 30 == 0:
                try:
                    with open(out + ".prog", "w", encoding="utf-8") as pf:
                        pf.write(str(f - f0))
                except OSError:
                    pass
                if B is not None and f and f % (FPS * 10) == 0:
                    log(f"      {f / FPS:.0f}/{total:.0f} detik")
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg gagal: {err[-800:]}")
    with open(out + ".prog", "w", encoding="utf-8") as pf:
        pf.write(str(f1 - f0))


def _worker_main(argv):
    pkl, f0, f1, out = argv[0], int(argv[1]), int(argv[2]), argv[3]
    with open(pkl, "rb") as f:
        S = pickle.load(f)
    _render_range(S["script"], S["cfg"], S["tl"], S["total"], S["n_frames"], S["env"], S["shp"], f0, f1, out,
                  log=lambda *_a, **_k: None)


def _mode_for(mode, k):
    return FX.TRANSITIONS[(k - 1) % len(FX.TRANSITIONS)] if mode == "variasi" else mode


def _transition(img, prev, p, mode, P):
    FX.transition(img, prev, p, mode, P, STAGE_TOP - 18, LY.TRANS_Y1)


def _pick_bgm():
    if not os.path.isdir(C.BGM_DIR):
        return None
    fs = [os.path.join(C.BGM_DIR, f) for f in os.listdir(C.BGM_DIR) if f.lower().endswith((".mp3", ".wav", ".m4a"))]
    return random.choice(fs) if fs else None


# ================================================================ preview
def preview_scene(script, idx, cfg, out_jpg, at=None):
    """Satu frame adegan ke-idx (default: saat semua elemen sudah muncul) tanpa TTS."""
    import cv2
    st = cfg["style"]
    P = D.palette(st)
    LY.apply(st)
    sc = script["adegan"][idx]
    est = max(2.5, len((sc.get("narasi") or "").split()) / 2.6)
    speech = (SPEECH_DELAY, SPEECH_DELAY + est)
    if sc.get("tipe") == "kisah":
        ws = (sc.get("narasi") or "").split()
        words = [(SPEECH_DELAY + est * j / max(1, len(ws)), est / max(1, len(ws)), w) for j, w in enumerate(ws)]
        actors, _ = KS.plan_scene(idx, sc, {"words": words, "speech": speech, "dur": est + 1.0}, P, st)
        img = D.paper(st["theme"]).copy()
        t = at if at is not None else SPEECH_DELAY + est * 0.8
        for a in actors:
            a.draw(img, t, {"frame": 0, "tg": t, "boil": False, "style": st, "P": P})
        cv2.imwrite(out_jpg, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        return out_jpg
    story_on = LY.pojok() and st.get("cerita_stik", True) and sc.get("tipe") in ("tanya", "bicara")
    sinfo = {}
    actors, _ = build_scene(sc, speech, P, st, cfg, story=story_on, info=sinfo)
    t = at if at is not None else SPEECH_DELAY + est + 0.4
    if story_on:
        sseed = zlib.crc32((script.get("judul") or "x").encode("utf-8"))
        cv = SK.make_cast(script, sseed)
        beats = SK.storyboard(sc, cv, cfg, state=SK.story_state(script, sseed), use_llm=False)
        story, _s = SK.plan_story(sc, {"words": [], "speech": speech, "dur": est + 1}, beats, cv,
                                  (40, sinfo.get("top", 480), 1040, LY.PANEL_BOTTOM), P, seed=sseed + idx * 17)
        if story:
            actors = [story] + actors
            t = min(t, story.beats[0]["t1"] - 0.2) if len(story.beats) > 1 else t
    sample = next((w for w in (sc.get("narasi") or "").split() if K.match(w)), None) or ((sc.get("narasi") or "").split() or [""])[0]
    holo = HL.plan_scene(idx, sc, {"words": [(t - 0.6, 0.3, sample)] if sample else []}, P, st, actors)
    if holo:                                                          # pratinjau hologram: proyektor + satu kata
        actors = holo["back"] + actors + holo["front"]
    img = D.paper(st["theme"]).copy()
    ctx = {"frame": 0, "tg": 1.0, "boil": False, "style": st, "P": P, "talking": False, "mouth": lambda x: 0.0}
    for a in actors:
        a.draw(img, t, ctx)
    for a in header_actors(script, P, st, cfg):
        a.draw(img, 9.0, ctx)
    if st["subtitles"] and not HL.sub_on(st):
        ch = sub_chunks(sc.get("narasi", ""), 0, 1)
        if ch:
            draw_sub(img, ch[0][2], 1.0, P, st)
    if st["watermark"] and cfg.get("account_name"):
        wm = D.text_block("@" + cfg["account_name"].replace(" ", ""), "hand_reg", 32, P["mute"], 800)
        D.blit(img, wm[0], LY.WM[0], LY.WM[1], anchor="tc", alpha=0.85)
    cv2.imwrite(out_jpg, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out_jpg


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--worker":     # proses pekerja render paralel
    _worker_main(sys.argv[2:])
