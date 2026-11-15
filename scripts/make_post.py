import sys, os
from PIL import Image, ImageDraw, ImageFont

# usage: make_post.py out.png "Judul" "Isi" "Sumber"
out, title, body, source = sys.argv[1:5]
W = H = 1080
HERE = os.path.dirname(os.path.abspath(__file__))
banner = Image.open(os.path.join(HERE, "..", "assets", "banner.jpg")).convert("RGB")
bh = round(banner.height * W / banner.width)
banner = banner.resize((W, bh), Image.LANCZOS)

img = Image.new("RGB", (W, H), "#F6EFD9")
d = ImageDraw.Draw(img)
img.paste(banner, (0, H - bh))

area_bottom = H - bh - 20
d.rounded_rectangle([40, 30, W - 40, area_bottom], 32, fill="#FFFBEF", outline="#C9A24B", width=7)

B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
R = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

def center(text, y, font, fill):
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)

def wrap(text, font, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

maxw = W - 200
top, bottom = 55, area_bottom - 25
sizes = [(50, 42), (46, 38), (42, 35), (38, 32), (34, 29), (30, 26)]
for ts, bs in sizes:
    ft, fb = ImageFont.truetype(B, ts), ImageFont.truetype(R, bs)
    tl, bl = wrap(title, ft, maxw), wrap(body, fb, maxw)
    h = len(tl) * int(ts * 1.3) + 45 + len(bl) * int(bs * 1.4) + 25 + 62
    if h <= bottom - top:
        break

y = top + max(0, (bottom - top - h) // 2)
for l in tl:
    center(l, y, ft, "#0B4F5C"); y += int(ts * 1.3)
y += 12
d.line([(300, y), (W - 300, y)], fill="#C9A24B", width=5); y += 33
for l in bl:
    center(l, y, fb, "#33413F"); y += int(bs * 1.4)
y += 22
fs = ImageFont.truetype(B, 28)
sw = d.textlength(source, font=fs) + 60
d.rounded_rectangle([(W - sw) / 2, y, (W + sw) / 2, y + 56], 28, fill="#E8C66A")
center(source, y + 12, fs, "#0B4F5C")
img.save(out)
print("saved", out)
