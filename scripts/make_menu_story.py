"""DKOT Coffee menu stories: cut-out cup on a foliage background (1080x1920 JPEG).

Usage: python3 make_menu_story.py CUT_DIR OUT_DIR
"""
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920
GF = "/usr/share/fonts/truetype/google-fonts/"
ANTON = GF + "ofl/anton/Anton-Regular.ttf"
BOLD = GF + "Poppins-Bold.ttf"
MED = GF + "Poppins-Medium.ttf"
ITAL = GF + "Poppins-MediumItalic.ttf"
CREAM = (255, 246, 228)
GOLD = (246, 196, 92)
DEEP = (14, 46, 28)

# key, cutout file, name lines, tagline
MENU = [
    ("01-gula-aren", "aren", ["ICED KOPI", "GULA AREN"], "Manis legit gula aren asli"),
    ("02-matcha", "matcha", ["ICED MATCHA", "LATTE"], "Lembut, segar di tiap tegukan"),
    ("03-orange-espresso", "orange", ["ICED ORANGE", "ESPRESSO"], "Espresso + jeruk segar. Wajib coba!"),
    ("04-americano", "americano", ["ICED", "AMERICANO"], "Bold, segar, tanpa basa-basi"),
    ("05-caramel", "caramel", ["ICED KOPI SUSU", "CARAMEL"], "Manis karamel yang bikin senyum"),
    ("06-bareng", "trio", ["NGOPI", "RAME-RAME"], "Satu order buat satu geng"),
    ("07-coklat", "coklat", ["ICED", "COKLAT"], "Cokelat pekat, dingin menyegarkan"),
    ("08-pandan", "pandan", ["ICED KOPI SUSU", "PANDAN"], "Wangi pandan, rasa nusantara"),
    ("09-butterscotch", "aren", ["ICED KOPI SUSU", "BUTTERSCOTCH"], "Creamy, manis, bikin nagih"),
    ("10-mocca", "mocca", ["ICED KOPI SUSU", "MOCCA"], "Kopi susu ketemu cokelat"),
    ("11-berdua", "duo", ["NGOPI", "BERDUA"], "Lebih nikmat kalau dibagi"),
    ("12-vanila", "aren", ["ICED KOPI SUSU", "VANILA"], "Lembut dengan wangi vanila"),
]

GREENS = [(20, 70, 38), (28, 92, 48), (40, 115, 58), (56, 135, 66), (74, 150, 72), (16, 58, 32), (95, 160, 80)]


def leaf(length, width, color, rnd):
    """Return an RGBA leaf pointing up, with midrib and veins."""
    pad = 10
    img = Image.new("RGBA", (int(width * 2 + pad * 2), int(length + pad * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = img.width / 2
    left, right = [], []
    n = 40
    for i in range(n + 1):
        t = i / n
        w = width * (math.sin(math.pi * t) ** 0.75) * (1 - 0.25 * t)
        y = pad + length * (1 - t)
        bend = 0.08 * width * math.sin(math.pi * t)
        left.append((cx - w + bend, y))
        right.append((cx + w + bend, y))
    poly = left + right[::-1]
    d.polygon(poly, fill=color + (255,))
    # lighter half for volume
    light = tuple(min(255, int(c * 1.25 + 8)) for c in color)
    d.polygon([(cx + 0.08 * width * math.sin(math.pi * (i / n)), pad + length * (1 - i / n)) for i in range(n + 1)] + right[::-1],
              fill=light + (255,))
    rib = tuple(min(255, int(c * 1.6 + 30)) for c in color)
    d.line([(cx, pad + length), (cx + 0.08 * width, pad + length * 0.5), (cx, pad)], fill=rib + (200,), width=max(2, int(width / 18)))
    for i in range(1, 9):
        t = i / 9
        y = pad + length * (1 - t)
        w = width * (math.sin(math.pi * t) ** 0.75) * 0.85
        bx = cx + 0.08 * width * math.sin(math.pi * t)
        for s in (-1, 1):
            d.line([(bx, y), (bx + s * w, y - length * 0.07)], fill=rib + (110,), width=max(1, int(width / 30)))
    return img


def foliage(seed):
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H), (10, 34, 20))
    # base gradient
    g = np.linspace(0, 1, H)[:, None]
    arr = np.zeros((H, W, 3))
    top, bot = np.array([18, 62, 34]), np.array([6, 24, 14])
    arr[:] = (top * (1 - g) + bot * g)[:, None, :].reshape(H, 1, 3)
    bg = Image.fromarray(arr.astype("uint8"))

    def layer(count, size, blur, darken, edge_bias=False):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for _ in range(count):
            L = rnd.uniform(*size)
            col = rnd.choice(GREENS)
            col = tuple(int(c * darken) for c in col)
            lf = leaf(L, L * rnd.uniform(0.28, 0.4), col, rnd).rotate(rnd.uniform(0, 360), expand=True, resample=Image.BICUBIC)
            if edge_bias:
                side = rnd.choice(["l", "r", "t", "b", "l", "r"])
                if side == "l":
                    x, y = rnd.uniform(-L * 0.7, 80), rnd.uniform(-100, H)
                elif side == "r":
                    x, y = rnd.uniform(W - 220, W - L * 0.2), rnd.uniform(-100, H)
                elif side == "t":
                    x, y = rnd.uniform(-100, W), rnd.uniform(-L * 0.7, -L * 0.2)
                else:
                    x, y = rnd.uniform(-100, W), rnd.uniform(H - 260, H - 60)
            else:
                x, y = rnd.uniform(-L * 0.5, W), rnd.uniform(-L * 0.5, H)
            lay.alpha_composite(lf, (int(x - lf.width / 2 + L / 2), int(y - lf.height / 2 + L / 2)))
        if blur:
            lay = lay.filter(ImageFilter.GaussianBlur(blur))
        return lay

    bgA = bg.convert("RGBA")
    bgA.alpha_composite(layer(70, (220, 420), 14, 0.55))
    bgA.alpha_composite(layer(40, (260, 480), 6, 0.8))
    # warm sun glow behind the cup
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W / 2 - 420, 620, W / 2 + 420, 1500], fill=(255, 226, 160, 120))
    bgA.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
    # bokeh dots
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bok)
    for _ in range(26):
        r = rnd.uniform(10, 38)
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        bd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 240, 190, rnd.randint(25, 70)))
    bgA.alpha_composite(bok.filter(ImageFilter.GaussianBlur(4)))
    bgA.alpha_composite(layer(16, (380, 620), 0, 1.0, edge_bias=True))
    # vignette
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.6)) ** 2)
    v = np.clip((dist - 0.55) * 1.1, 0, 0.75)
    vig = Image.fromarray((v * 255).astype("uint8"))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    black.putalpha(vig)
    bgA.alpha_composite(black)
    return bgA


def polish_cup(cup):
    rgb, a = cup.convert("RGB"), cup.getchannel("A")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.1)
    rgb = ImageEnhance.Color(rgb).enhance(1.15)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.6)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.04)
    # tighten soft matte edges
    a = a.point(lambda p: 0 if p < 30 else min(255, int((p - 30) * 1.15)))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def text_shadowed(base, xy, txt, font, fill, anchor="mm", shadow=(0, 0, 0, 170), blur=10, off=(0, 6)):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + off[0], xy[1] + off[1]), txt, font=font, fill=shadow, anchor=anchor)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(base).text(xy, txt, font=font, fill=fill, anchor=anchor)


def fit_font(path, txt, max_w, start):
    s = start
    while s > 40:
        f = ImageFont.truetype(path, s)
        if f.getlength(txt) <= max_w:
            return f
        s -= 4
    return ImageFont.truetype(path, s)


def pill(d, box, fill, text, font, tcol):
    d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, font=font, fill=tcol, anchor="mm")


def make(key, cutfile, lines, tagline, cutdir, out, seed):
    img = foliage(seed)

    # brand badge
    d = ImageDraw.Draw(img)
    fb = ImageFont.truetype(BOLD, 40)
    bw = fb.getlength("DKOT COFFEE") + 90
    pill(d, (W / 2 - bw / 2, 80, W / 2 + bw / 2, 150), CREAM, "DKOT COFFEE", fb, DEEP)

    # menu name
    y = 250
    for i, ln in enumerate(lines):
        f = fit_font(ANTON, ln, 940, 150 if i == len(lines) - 1 else 110)
        col = GOLD if i == len(lines) - 1 else CREAM
        text_shadowed(img, (W / 2, y), ln, f, col, anchor="mt", blur=12)
        y += int(f.size * 1.12)
    text_shadowed(img, (W / 2, y + 10), tagline, ImageFont.truetype(ITAL, 42), CREAM, anchor="mt", blur=8, off=(0, 3))
    text_bottom = y + 75

    # podium
    py = 1395
    pod = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pod)
    pd.ellipse([W / 2 - 360, py - 20, W / 2 + 360, py + 120], fill=(0, 0, 0, 120))
    pod = pod.filter(ImageFilter.GaussianBlur(18))
    pd = ImageDraw.Draw(pod)
    pd.rounded_rectangle([W / 2 - 330, py - 50, W / 2 + 330, py + 40], radius=40, fill=(214, 196, 168, 255))
    pd.ellipse([W / 2 - 330, py - 100, W / 2 + 330, py], fill=(246, 236, 218, 255))
    pd.ellipse([W / 2 - 330, py + 0, W / 2 + 330, py + 80], fill=(196, 176, 146, 255))
    pd.rectangle([W / 2 - 330, py - 50, W / 2 + 330, py + 40], fill=(222, 204, 176, 255))
    pd.ellipse([W / 2 - 330, py - 100, W / 2 + 330, py], fill=(246, 236, 218, 255))
    img.alpha_composite(pod)

    # cup
    cup = polish_cup(Image.open(Path(cutdir) / f"{cutfile}.png"))
    if cutfile == "orange":
        cup = cup.crop((0, 0, cup.width, cup.height - 8))
    max_h = (py - 40) - (text_bottom + 30)
    max_w = 760 if cutfile not in ("duo", "trio") else 900
    s = min(max_h / cup.height, max_w / cup.width)
    cup = cup.resize((int(cup.width * s), int(cup.height * s)), Image.LANCZOS)
    cx, bottom = W // 2, py - 40
    x0, y0 = cx - cup.width // 2, bottom - cup.height
    # contact shadow
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - cup.width * 0.42, bottom - 24, cx + cup.width * 0.42, bottom + 22], fill=(40, 25, 10, 170))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    # soft drop shadow
    ds = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = cup.getchannel("A").point(lambda p: int(p * 0.45))
    blk = Image.new("RGBA", cup.size, (0, 0, 0, 255))
    blk.putalpha(a)
    ds.alpha_composite(blk, (x0 + 26, y0 + 22))
    img.alpha_composite(ds.filter(ImageFilter.GaussianBlur(26)))
    # rim light
    rim = Image.new("RGBA", cup.size, (255, 244, 214, 0))
    edge = cup.getchannel("A").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(3)).point(lambda p: min(160, p * 2))
    rim.putalpha(edge)
    img.alpha_composite(cup, (x0, y0))
    img.alpha_composite(rim, (x0, y0))

    # CTA panel
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([60, 1475, W - 60, 1735], radius=44, fill=(8, 30, 18, 205))
    img.alpha_composite(panel)
    d = ImageDraw.Draw(img)
    d.text((W / 2, 1525), "ORDER SEKARANG DI", font=ImageFont.truetype(BOLD, 40), fill=CREAM, anchor="mm")
    fp = ImageFont.truetype(BOLD, 46)
    pill(d, (100, 1565, 525, 1655), (238, 77, 45), "ShopeeFood", fp, (255, 255, 255))
    pill(d, (555, 1565, 980, 1655), (0, 177, 79), "GrabFood", fp, (255, 255, 255))
    d.text((W / 2, 1697), "KLIK LINK DI BIO  •  @dkot_coffee", font=ImageFont.truetype(BOLD, 34), fill=GOLD, anchor="mm")

    img.convert("RGB").save(out, "JPEG", quality=90, optimize=True)


if __name__ == "__main__":
    cutdir, outdir = sys.argv[1], Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3:] or None
    for i, (key, cf, lines, tag) in enumerate(MENU):
        if only and key not in only:
            continue
        make(key, cf, lines, tag, cutdir, outdir / f"{key}.jpg", seed=100 + i)
    print("done")
