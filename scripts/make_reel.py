"""DKOT Coffee reel: 15 s, 1080x1920, 30 fps, cut to a 128 BPM beat.

Usage: python3 make_reel.py CUT_DIR OUT_DIR INDEX [--frames t1,t2,...]
"""
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import fx
import make_menu_story as M

W, H, FPS = 1080, 1920, 30
BEAT = 60 / 128
DUR = 32 * BEAT
HOOKS = [("HAUS?", "PANAS?"), ("NGANTUK?", "BUTUH KOPI!"), ("WARGA", "JAKTIM?"), ("MAGER", "KELUAR?"),
         ("LAGI", "SUMPEK?"), ("BOSEN", "KOPI ITU-ITU AJA?")]
STICK = [["WAJIB", "COBA!"], ["FAVORIT", "DKOT"], ["SEGAR", "BANGET"], ["BIKIN", "NAGIH"]]
FLASH_COLS = [(246, 196, 92), (238, 77, 45), (0, 177, 79), (255, 246, 228)]


def ease_out_back(x, s=1.7):
    x = min(max(x, 0), 1) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def text_layer(txt, size, color, stroke=0, shadow=True, font=M.ANTON, max_w=980):
    f = M.fit_font(font, txt, max_w, size)
    bb = f.getbbox(txt, stroke_width=stroke)
    w, h = bb[2] - bb[0] + 60, bb[3] - bb[1] + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((30 - bb[0] + 4, 30 - bb[1] + 10), txt, font=f, fill=(0, 0, 0, 190), stroke_width=stroke, stroke_fill=(0, 0, 0, 190))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(im).text((30 - bb[0], 30 - bb[1]), txt, font=f, fill=color, stroke_width=stroke, stroke_fill=(20, 40, 24))
    return im


def paste_center(base, im, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, expand=True, resample=Image.BILINEAR)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda p: int(p * alpha))
        im = im.copy()
        im.putalpha(a)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    # clip to canvas
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, W - x), min(im.height, H - y)
    if ex <= sx or ey <= sy:
        return
    base.alpha_composite(im.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def slam(base, layer, cx, cy, t, t0, dur=0.22):
    """Text that slams in at t0 from big to normal size."""
    if t < t0:
        return
    k = (t - t0) / dur
    if k < 1:
        s = 2.2 - 1.2 * (1 - (1 - k) ** 3)
        paste_center(base, layer, cx, cy, s, min(1, k * 2.5))
    else:
        paste_center(base, layer, cx, cy, 1.0)


def pop(base, layer, cx, cy, t, t0, dur=0.3, rot=0):
    if t < t0:
        return
    s = ease_out_back((t - t0) / dur)
    paste_center(base, layer, cx, cy, s, 1.0, rot)


def tight_cup(cutdir, cutfile, max_w, max_h):
    cup = fx.fit(fx.load_cup(cutdir, cutfile), max_w, max_h)
    lay = fx.cup_layer(cup, W / 2, H / 2 + cup.height / 2)
    bb = lay.getbbox()
    c = lay.crop(bb)
    # vertical offset of cup centre inside the crop
    # dy: cup centre minus crop centre (paste crop centre at Y - dy to put the cup centre at Y)
    return c, (H / 2) - bb[1] - c.height / 2, cup.height


class Reel:
    def __init__(self, cutdir, idx):
        self.idx = idx
        key, cutfile, lines, tag = M.MENU[idx]
        self.cutfile = cutfile
        rnd = random.Random(idx)
        bg = M.foliage(300 + idx).convert("RGB")
        self.bg = bg.resize((int(W * 1.12), int(H * 1.12)), Image.LANCZOS)
        self.dark = Image.new("RGBA", (W, H), (0, 0, 0, 150))
        hook = HOOKS[idx % len(HOOKS)]
        self.hook1 = text_layer(hook[0], 230, M.CREAM)
        self.hook2 = text_layer(hook[1], 200, M.GOLD)
        group = cutfile in ("duo", "trio")
        self.hero, self.hero_dy, self.hero_h = tight_cup(cutdir, cutfile, 900 if group else 660, 620)
        self.hero_small, self.hero_small_dy, _ = tight_cup(cutdir, cutfile, 620 if group else 440, 470)
        self.name = [text_layer(l, 150 if j == len(lines) - 1 else 110, M.GOLD if j == len(lines) - 1 else M.CREAM) for j, l in enumerate(lines)]
        self.tag = text_layer(tag, 46, M.CREAM, font=M.ITAL, shadow=True)
        self.badge = Image.new("RGBA", (420, 76), (0, 0, 0, 0))
        M.pill(ImageDraw.Draw(self.badge), (0, 0, 420, 76), M.CREAM, "DKOT COFFEE", ImageFont.truetype(M.BOLD, 40), M.DEEP)
        self.sticker = fx.sticker(STICK[idx % len(STICK)], [(232, 48, 64), (240, 120, 30), (220, 40, 110)][idx % 3], 240, 0)
        self.podium = fx.podium(1420)
        # montage: 8 other menus
        others = [m for j, m in enumerate(M.MENU) if j != idx and m[1] != cutfile]
        rnd.shuffle(others)
        seen, mont = set(), []
        for m in others:
            if m[1] in seen and m[1] == "aren":
                continue
            seen.add(m[1])
            mont.append(m)
        self.mont = []
        for m in mont[:8]:
            c, dy, _ = tight_cup(cutdir, m[1], 760 if m[1] in ("duo", "trio") else 600, 700)
            self.mont.append((c, dy, text_layer(" ".join(m[2]), 120, M.CREAM, max_w=960)))
        self.mont_title = text_layer("MENU LAINNYA", 80, M.GOLD)
        # CTA
        self.order = text_layer("ORDER", 210, M.CREAM)
        self.now = text_layer("SEKARANG!", 190, M.GOLD)
        fp = ImageFont.truetype(M.BOLD, 52)
        self.shopee = Image.new("RGBA", (440, 100), (0, 0, 0, 0))
        M.pill(ImageDraw.Draw(self.shopee), (0, 0, 440, 100), (238, 77, 45), "ShopeeFood", fp, (255, 255, 255))
        self.grab = Image.new("RGBA", (440, 100), (0, 0, 0, 0))
        M.pill(ImageDraw.Draw(self.grab), (0, 0, 440, 100), (0, 177, 79), "GrabFood", fp, (255, 255, 255))
        self.link = Image.new("RGBA", (760, 86), (0, 0, 0, 0))
        M.pill(ImageDraw.Draw(self.link), (0, 0, 760, 86), M.GOLD, fx.LINK, ImageFont.truetype(M.BOLD, 44), M.DEEP)
        self.area = Image.new("RGBA", (920, 150), (0, 0, 0, 0))
        ad = ImageDraw.Draw(self.area)
        ad.rounded_rectangle((0, 0, 920, 150), radius=36, fill=(8, 30, 18, 225), outline=M.GOLD + (255,), width=3)
        # map pin
        ad.ellipse((40, 30, 92, 82), fill=(232, 48, 64))
        ad.polygon([(44, 66), (88, 66), (66, 118)], fill=(232, 48, 64))
        ad.ellipse((56, 46, 76, 66), fill=(255, 255, 255))
        ad.text((500, 50), "ANTAR KE JAKARTA TIMUR", font=ImageFont.truetype(M.BOLD, 44), fill=M.GOLD, anchor="mm")
        ad.text((500, 108), fx.AREA, font=ImageFont.truetype(M.MED, 34), fill=M.CREAM, anchor="mm")

    def bg_at(self, t, zoom_extra=0.0):
        z = 1.0 + 0.06 * (t / DUR) + zoom_extra
        cw, ch = int(W * 1.12 / z), int(H * 1.12 / z)
        x0 = (self.bg.width - cw) // 2
        y0 = (self.bg.height - ch) // 2
        return self.bg.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR).convert("RGBA")

    def frame(self, t):
        b = t / BEAT
        bi = int(b)
        since = t - bi * BEAT
        kick = math.exp(-since * 12) if b >= 4 else 0.0
        shake = 0
        if b < 4:  # hook
            img = self.bg_at(t)
            img.alpha_composite(self.dark)
            jit = 6 * math.sin(t * 60) * math.exp(-since * 6)
            slam(img, self.hook1, W / 2 + jit, 800, t, 0.0)
            slam(img, self.hook2, W / 2 - jit, 1060, t, 2 * BEAT)
            # warning-tape bars pulsing near drop
            if b > 3:
                k = (b - 3)
                d = ImageDraw.Draw(img)
                d.rectangle((0, 0, W, int(60 * k)), fill=M.GOLD)
                d.rectangle((0, H - int(60 * k), W, H), fill=M.GOLD)
        elif b < 16:  # hero
            tt = t - 4 * BEAT
            img = self.bg_at(t, 0.02 * kick)
            img.alpha_composite(fx.rays(n=18, phase=tt * 0.35, center=(W // 2, 1060), alpha=int(55 + 40 * kick)))
            img.alpha_composite(self.podium)
            img.alpha_composite(fx.floaters(900 + self.idx, W / 2, 1050, 470, 330, 3, 4, t=tt, avoid=280))
            s = 1 + 0.45 * math.exp(-tt * 5) * math.cos(tt * 14) + 0.03 * kick
            s = max(s, 0.6)
            cy = 1420 - 45 - self.hero_h / 2 - self.hero_dy * s
            paste_center(img, self.hero, W / 2, cy - (s - 1) * self.hero_h * 0.5, s)
            img.alpha_composite(fx.floaters(1900 + self.idx, W / 2, 1150, 470, 260, 2, 3, t=tt * 1.3, avoid=330))
            paste_center(img, self.badge, W / 2, 150, 1.0, min(1, tt * 4))
            y = 290
            for j, nl in enumerate(self.name):
                slam(img, nl, W / 2, y + nl.height / 2 - 30, t, (5 + j) * BEAT)
                y += nl.height - 40
            if t > 7 * BEAT:
                paste_center(img, self.tag, W / 2, y + 30, 1.0, min(1, (t - 7 * BEAT) * 4))
            wob = 8 * math.sin(t * 6)
            pop(img, self.sticker, W - 210, y + 220, t, 9 * BEAT, rot=-12 + wob)
            d = ImageDraw.Draw(img)
            r = random.Random(bi)
            for _ in range(6):
                fx.sparkle(d, r.uniform(120, W - 120), r.uniform(650, 1350), r.uniform(10, 26) * (0.4 + kick))
        elif b < 24:  # montage
            k = bi - 16
            c, dy, nm = self.mont[k % len(self.mont)]
            img = self.bg_at(t)
            tint = Image.new("RGBA", (W, H), FLASH_COLS[k % 4] + (40,))
            img.alpha_composite(tint)
            img.alpha_composite(fx.rays(n=14, phase=t * 0.6 + k, center=(W // 2, 960), alpha=50))
            s = 1.18 - 0.18 * (1 - math.exp(-since * 14))
            paste_center(img, c, W / 2, 960 - dy * s, s)
            paste_center(img, self.mont_title, W / 2, 300, 1.0)
            paste_center(img, nm, W / 2 + 40 * math.exp(-since * 12) * (1 if k % 2 else -1), 1430, 1.0)
            # beat counter dots
            d = ImageDraw.Draw(img)
            for j in range(8):
                x = W / 2 - 7 * 22 + j * 44
                d.ellipse((x - 9, 395, x + 9, 413), fill=M.GOLD if j <= k else (255, 255, 255, 90))
        else:  # CTA
            img = self.bg_at(t, 0.015 * kick)
            img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 80)))
            img.alpha_composite(fx.rays(n=18, phase=t * 0.3, center=(W // 2, 860), alpha=45))
            slam(img, self.order, W / 2, 300, t, 24 * BEAT)
            slam(img, self.now, W / 2, 500, t, 25 * BEAT)
            cy = 880 - self.hero_small_dy
            pop(img, self.hero_small, W / 2, cy, t, 24 * BEAT, 0.4)
            pop(img, self.shopee, 295, 1210, t, 26 * BEAT)
            pop(img, self.grab, 785, 1210, t, 26.5 * BEAT)
            pop(img, self.link, W / 2, 1335, t, 27.5 * BEAT)
            pop(img, self.area, W / 2, 1480, t, 28.5 * BEAT)
        # flashes on section changes
        for fb_, col in ((4, (255, 255, 255)), (16, M.GOLD), (24, (255, 255, 255))):
            dt = t - fb_ * BEAT
            if 0 <= dt < 0.2:
                img.alpha_composite(Image.new("RGBA", (W, H), col + (int(230 * (1 - dt / 0.2)),)))
        if 16 <= b < 24 and since < 0.08:
            img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(120 * (1 - since / 0.08)))))
        return img.convert("RGB")


def render(cutdir, outdir, idx, audio):
    r = Reel(cutdir, idx)
    key = M.MENU[idx][0]
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tmp = outdir / f".{key}.tmp.mp4"
    final = outdir / f"{key}.mp4"
    nframes = int(round(DUR * FPS))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(tmp)],
                         stdin=subprocess.PIPE)
    for i in range(nframes):
        p.stdin.write(r.frame(i / FPS).tobytes())
    p.stdin.close()
    if p.wait() == 0:
        tmp.rename(final)
        print("ok", final)
    else:
        print("FAILED", key)


if __name__ == "__main__":
    cutdir, outdir, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
    if len(sys.argv) > 4 and sys.argv[4] == "--frames":
        r = Reel(cutdir, idx)
        for ts in sys.argv[5].split(","):
            r.frame(float(ts)).save(f"{outdir}/f_{idx}_{ts}.jpg", quality=85)
    else:
        render(cutdir, outdir, idx, sys.argv[4] if len(sys.argv) > 4 else "audio/beat0.wav")
