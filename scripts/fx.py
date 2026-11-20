"""Shared drawing pieces for DKOT stories and reels."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import make_menu_story as M

W, H = M.W, M.H
CREAM, GOLD, DEEP = M.CREAM, M.GOLD, M.DEEP
LINK = "linktr.ee/dkot_official"
AREA = "Halim • Cawang • Cililitan • Kalimalang"


def rays(n=16, color=(255, 236, 180), alpha=60, center=(W // 2, 1000), phase=0.0, length=1500):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = center
    for i in range(n):
        a0 = phase + i * 2 * math.pi / n
        a1 = a0 + math.pi / n * 0.55
        d.polygon([(cx, cy), (cx + length * math.cos(a0), cy + length * math.sin(a0)),
                   (cx + length * math.cos(a1), cy + length * math.sin(a1))], fill=color + (alpha,))
    return lay.filter(ImageFilter.GaussianBlur(10))


def ice(size, rot=0):
    s = int(size)
    im = Image.new("RGBA", (s + 20, s + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, s + 10, s + 10], radius=s // 5, fill=(220, 240, 255, 150), outline=(255, 255, 255, 230), width=max(2, s // 18))
    d.rounded_rectangle([10 + s * 0.15, 10 + s * 0.12, 10 + s * 0.55, 10 + s * 0.3], radius=s // 10, fill=(255, 255, 255, 200))
    d.line([(10 + s * 0.7, 10 + s * 0.7), (10 + s * 0.85, 10 + s * 0.55)], fill=(255, 255, 255, 180), width=max(2, s // 16))
    return im.rotate(rot, expand=True, resample=Image.BICUBIC)


def bean(size, rot=0):
    s = int(size)
    im = Image.new("RGBA", (s + 10, int(s * 1.4) + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([5, 5, s + 5, s * 1.4 + 5], fill=(92, 52, 26, 255))
    d.ellipse([5 + s * 0.12, 5 + s * 0.08, s * 0.6 + 5, s * 0.7 + 5], fill=(128, 76, 40, 255))
    d.arc([5 + s * 0.3, 5, 5 + s * 0.7, s * 1.4 + 5], 100, 260, fill=(40, 20, 10, 255), width=max(2, s // 7))
    return im.rotate(rot, expand=True, resample=Image.BICUBIC)


def sparkle(d, x, y, r, color=(255, 250, 220, 230)):
    d.polygon([(x, y - r), (x + r * 0.22, y - r * 0.22), (x + r, y), (x + r * 0.22, y + r * 0.22),
               (x, y + r), (x - r * 0.22, y + r * 0.22), (x - r, y), (x - r * 0.22, y - r * 0.22)], fill=color)


def sticker(text_lines, color=(232, 48, 64), size=210, rot=-12):
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    for i in range(32):
        a = i * math.pi / 16
        r = s / 2 - 4 if i % 2 == 0 else s / 2 - 20
        pts.append((s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)))
    d.polygon(pts, fill=color + (255,))
    d.ellipse([22, 22, s - 22, s - 22], outline=(255, 255, 255, 230), width=4)
    f1 = ImageFont.truetype(M.ANTON, int(s * 0.2))
    y = s / 2 - (len(text_lines) - 1) * s * 0.11
    for ln in text_lines:
        d.text((s / 2, y), ln, font=f1, fill=(255, 255, 255), anchor="mm")
        y += s * 0.22
    return im.rotate(rot, expand=True, resample=Image.BICUBIC)


def load_cup(cutdir, cutfile):
    cup = M.polish_cup(Image.open(f"{cutdir}/{cutfile}.png"))
    if cutfile == "orange":
        cup = cup.crop((0, 0, cup.width, cup.height - 8))
    return cup


def fit(cup, max_w, max_h):
    s = min(max_w / cup.width, max_h / cup.height)
    return cup.resize((max(1, int(cup.width * s)), max(1, int(cup.height * s))), Image.LANCZOS)


def cup_layer(cup, cx, bottom, shadow=True):
    """Return full-frame RGBA with cup + soft shadows, cup bottom-centered at (cx, bottom)."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x0, y0 = int(cx - cup.width / 2), int(bottom - cup.height)
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([cx - cup.width * 0.45, bottom - 22, cx + cup.width * 0.45, bottom + 26], fill=(20, 12, 4, 180))
        lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
        ds = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        blk = Image.new("RGBA", cup.size, (0, 0, 0, 255))
        blk.putalpha(cup.getchannel("A").point(lambda p: int(p * 0.5)))
        ds.alpha_composite(blk, (x0 + 24, y0 + 24))
        lay.alpha_composite(ds.filter(ImageFilter.GaussianBlur(28)))
    lay.alpha_composite(cup, (x0, y0))
    rim = Image.new("RGBA", cup.size, (255, 244, 214, 0))
    rim.putalpha(cup.getchannel("A").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(3)).point(lambda p: min(170, p * 2)))
    lay.alpha_composite(rim, (x0, y0))
    return lay


def podium(py, half=330):
    pod = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pod)
    pd.ellipse([W / 2 - half - 30, py - 20, W / 2 + half + 30, py + 120], fill=(0, 0, 0, 130))
    pod = pod.filter(ImageFilter.GaussianBlur(18))
    pd = ImageDraw.Draw(pod)
    pd.ellipse([W / 2 - half, py + 0, W / 2 + half, py + 80], fill=(186, 150, 104, 255))
    pd.rectangle([W / 2 - half, py - 50, W / 2 + half, py + 40], fill=(206, 172, 124, 255))
    pd.ellipse([W / 2 - half, py - 100, W / 2 + half, py], fill=(244, 226, 196, 255))
    pd.ellipse([W / 2 - half + 30, py - 88, W / 2 + half - 30, py - 12], outline=(255, 246, 228, 160), width=4)
    return pod


def floaters(seed, cx, cy, spread_x, spread_y, n_ice=5, n_bean=6, t=0.0, avoid=0):
    """Ice cubes and beans around a point; t animates a gentle bob/rotation."""
    rnd = random.Random(seed)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    items = [("ice", rnd.uniform(70, 120)) for _ in range(n_ice)] + [("bean", rnd.uniform(38, 60)) for _ in range(n_bean)]
    for i, (kind, s) in enumerate(items):
        ang = rnd.uniform(0, 2 * math.pi)
        rx = rnd.uniform(0.75, 1.0) * spread_x
        ry = rnd.uniform(0.55, 1.0) * spread_y
        x = cx + rx * math.cos(ang)
        y = cy + ry * math.sin(ang) + 18 * math.sin(t * 2 * math.pi * 0.6 + i)
        if avoid and abs(x - cx) < avoid:
            x = cx + (avoid if x >= cx else -avoid)
        rot = rnd.uniform(0, 360) + 40 * t * (1 if i % 2 else -1)
        im = ice(s, rot) if kind == "ice" else bean(s, rot)
        if rnd.random() < 0.35:
            im = im.filter(ImageFilter.GaussianBlur(3))
        lay.alpha_composite(im, (int(x - im.width / 2), int(y - im.height / 2)))
    return lay
