"""DKOT IG profile picture + highlight covers. Usage: python3 make_profile.py CUT_DIR OUT_DIR"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fx
import make_menu_story as M

GOLD, CREAM, DEEP = M.GOLD, M.CREAM, M.DEEP


def profile(cutdir, out):
    S = 1080
    bg = M.foliage(77).convert("RGB").crop((0, 420, 1080, 1500)).convert("RGBA")
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([190, 190, 890, 890], fill=(255, 226, 160, 150))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(110)))
    cup = fx.fit(fx.load_cup(cutdir, "aren"), 600, 700)
    x0, y0 = (S - cup.width) // 2, (S - cup.height) // 2 + 30
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    blk = Image.new("RGBA", cup.size, (0, 0, 0, 255))
    blk.putalpha(cup.getchannel("A").point(lambda p: int(p * 0.5)))
    sh.alpha_composite(blk, (x0 + 22, y0 + 22))
    bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(26)))
    bg.alpha_composite(cup, (x0, y0))
    d = ImageDraw.Draw(bg)
    d.ellipse([18, 18, S - 18, S - 18], outline=GOLD, width=26)
    bg.convert("RGB").save(out, quality=92)


def icon_cup(d, cx, cy, s, col):
    d.polygon([(cx - s * 0.32, cy - s * 0.25), (cx + s * 0.32, cy - s * 0.25), (cx + s * 0.24, cy + s * 0.45), (cx - s * 0.24, cy + s * 0.45)], fill=col)
    d.rounded_rectangle([cx - s * 0.4, cy - s * 0.38, cx + s * 0.4, cy - s * 0.25], radius=int(s * 0.05), fill=col)
    d.line([(cx + s * 0.08, cy - s * 0.38), (cx + s * 0.22, cy - s * 0.62)], fill=col, width=int(s * 0.07))
    d.ellipse([cx - s * 0.14, cy - s * 0.02, cx + s * 0.14, cy + s * 0.26], fill=DEEP)


def icon_bag(d, cx, cy, s, col):
    d.rounded_rectangle([cx - s * 0.38, cy - s * 0.2, cx + s * 0.38, cy + s * 0.48], radius=int(s * 0.08), fill=col)
    d.arc([cx - s * 0.2, cy - s * 0.5, cx + s * 0.2, cy - s * 0.05], 180, 360, fill=col, width=int(s * 0.08))
    d.line([(cx - s * 0.16, cy + s * 0.08), (cx - s * 0.02, cy + s * 0.24), (cx + s * 0.2, cy - s * 0.02)], fill=DEEP, width=int(s * 0.08))


def icon_pin(d, cx, cy, s, col):
    d.ellipse([cx - s * 0.3, cy - s * 0.55, cx + s * 0.3, cy + s * 0.05], fill=col)
    d.polygon([(cx - s * 0.27, cy - s * 0.12), (cx + s * 0.27, cy - s * 0.12), (cx, cy + s * 0.5)], fill=col)
    d.ellipse([cx - s * 0.12, cy - s * 0.37, cx + s * 0.12, cy - s * 0.13], fill=DEEP)


def icon_promo(d, cx, cy, s, col):
    pts = []
    for i in range(24):
        a = i * math.pi / 12
        r = s * (0.48 if i % 2 == 0 else 0.4)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=col)
    d.text((cx, cy), "%", font=ImageFont.truetype(M.ANTON, int(s * 0.5)), fill=DEEP, anchor="mm")


def icon_star(d, cx, cy, s, col):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = s * (0.5 if i % 2 == 0 else 0.21)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=col)


def highlight(icon, label, out, seed):
    W, H = 1080, 1920
    img = M.foliage(seed)
    img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))
    d = ImageDraw.Draw(img)
    cx, cy, R = W / 2, H / 2, 380
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=DEEP + (255,), outline=GOLD, width=18)
    icon(d, cx, cy - 40, 360, GOLD)
    d.text((cx, cy + 250), label, font=ImageFont.truetype(M.ANTON, 90), fill=CREAM, anchor="mm")
    img.convert("RGB").save(out, quality=92)


if __name__ == "__main__":
    cutdir, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    profile(cutdir, out / "foto-profil.jpg")
    for i, (ic, lb, fn) in enumerate([(icon_cup, "MENU", "1-menu"), (icon_bag, "ORDER", "2-order"), (icon_pin, "LOKASI", "3-lokasi"),
                                       (icon_promo, "PROMO", "4-promo"), (icon_star, "TESTI", "5-testimoni")]):
        highlight(ic, lb, out / f"highlight-{fn}.jpg", 40 + i)
    print("done")
