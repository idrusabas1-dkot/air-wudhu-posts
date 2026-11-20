"""DKOT Coffee menu story v2: rays, floating ice & beans, sticker, linktree + area.

Usage: python3 make_story_v2.py CUT_DIR OUT_DIR [keys...]
"""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import fx
import make_menu_story as M

W, H = fx.W, fx.H
STICKERS = [["WAJIB", "COBA!"], ["FAVORIT", "DKOT"], ["SEGAR", "BANGET"], ["BIKIN", "NAGIH"]]
STICKER_COLORS = [(232, 48, 64), (240, 120, 30), (220, 40, 110)]


def make(i, key, cutfile, lines, tagline, cutdir, out):
    rnd = random.Random(500 + i)
    img = M.foliage(100 + i)
    img.alpha_composite(fx.rays(phase=rnd.uniform(0, 1), center=(W // 2, 1050), alpha=55))

    d = ImageDraw.Draw(img)
    fb = ImageFont.truetype(M.BOLD, 40)
    bw = fb.getlength("DKOT COFFEE") + 90
    M.pill(d, (W / 2 - bw / 2, 70, W / 2 + bw / 2, 140), M.CREAM, "DKOT COFFEE", fb, M.DEEP)

    y = 215
    for j, ln in enumerate(lines):
        last = j == len(lines) - 1
        f = M.fit_font(M.ANTON, ln, 960, 160 if last else 112)
        M.text_shadowed(img, (W / 2, y), ln, f, M.GOLD if last else M.CREAM, anchor="mt", blur=14, off=(0, 8))
        y += int(f.size * 1.1)
    M.text_shadowed(img, (W / 2, y + 8), tagline, ImageFont.truetype(M.ITAL, 42), M.CREAM, anchor="mt", blur=8, off=(0, 3))
    text_bottom = y + 70

    py = 1345
    img.alpha_composite(fx.podium(py))
    group = cutfile in ("duo", "trio")
    cup = fx.fit(fx.load_cup(cutdir, cutfile), 900 if group else 720, (py - 45) - (text_bottom + 40))
    cy = py - 45 - cup.height / 2
    # floaters behind (blurred) and in front
    img.alpha_composite(fx.floaters(900 + i, W / 2, cy, cup.width * 0.75 + 60, cup.height * 0.5, n_ice=3, n_bean=4, avoid=cup.width * 0.45))
    img.alpha_composite(fx.cup_layer(cup, W / 2, py - 45))
    img.alpha_composite(fx.floaters(1900 + i, W / 2, cy + 80, cup.width * 0.68 + 70, cup.height * 0.42, n_ice=2, n_bean=3, avoid=cup.width * 0.5 + 30))
    d = ImageDraw.Draw(img)
    for _ in range(9):
        fx.sparkle(d, rnd.uniform(80, W - 80), rnd.uniform(text_bottom, py - 60), rnd.uniform(10, 26))

    st = fx.sticker(STICKERS[i % len(STICKERS)], STICKER_COLORS[i % len(STICKER_COLORS)], 230, rot=rnd.choice([-14, 12]))
    sx = int(W / 2 + cup.width / 2 - 70) if not group else W - 260
    sx = min(sx, W - st.width - 20)
    img.alpha_composite(st, (sx, int(text_bottom + 10)))

    # CTA panel
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([50, 1440, W - 50, 1770], radius=46, fill=(8, 30, 18, 215), outline=M.GOLD + (255,), width=3)
    img.alpha_composite(panel)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 1488), "ORDER ONLINE SEKARANG", font=ImageFont.truetype(M.BOLD, 40), fill=M.CREAM, anchor="mm")
    fp = ImageFont.truetype(M.BOLD, 46)
    M.pill(d, (95, 1525, 525, 1612), (238, 77, 45), "ShopeeFood", fp, (255, 255, 255))
    M.pill(d, (555, 1525, 985, 1612), (0, 177, 79), "GrabFood", fp, (255, 255, 255))
    d.text((W / 2, 1654), fx.LINK, font=ImageFont.truetype(M.BOLD, 40), fill=M.GOLD, anchor="mm")
    d.text((W / 2, 1712), "Antar cepat: " + fx.AREA, font=ImageFont.truetype(M.MED, 29), fill=M.CREAM, anchor="mm")

    img.convert("RGB").save(out, "JPEG", quality=90, optimize=True)


if __name__ == "__main__":
    cutdir, outdir = sys.argv[1], Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3:] or None
    for i, (key, cf, lines, tag) in enumerate(M.MENU):
        if only and key not in only:
            continue
        make(i, key, cf, lines, tag, cutdir, outdir / f"{key}.jpg")
    print("done")
