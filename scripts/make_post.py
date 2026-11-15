import sys, textwrap
from PIL import Image, ImageDraw, ImageFont

# usage: make_post.py out.png "Judul" "Isi" "Sumber"
out, title, body, source = sys.argv[1:5]
W = H = 1080
img = Image.new("RGB", (W, H), "#F6EFD9")
d = ImageDraw.Draw(img)
d.rectangle([0, 0, W, 150], fill="#0B4F5C")
d.rectangle([0, H - 110, W, H], fill="#0B4F5C")
d.rounded_rectangle([60, 190, W - 60, H - 150], 36, fill="#FFFBEF", outline="#C9A24B", width=8)

B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
R = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

def center(text, y, font, fill):
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)

def wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

center("Air-Wudhu", 45, ImageFont.truetype(B, 54), "#E8C66A")
center("Doodle dakwah fiqih ibadah", H - 80, ImageFont.truetype(R, 32), "#F6EFD9")

maxw = W - 230
top, bottom = 250, H - 190   # usable area inside card
for ts, bs in [(50, 44), (46, 40), (42, 36), (38, 33), (34, 30)]:
    ft, fb = ImageFont.truetype(B, ts), ImageFont.truetype(R, bs)
    tl, bl = wrap(title, ft, maxw), wrap(body, fb, maxw)
    h = len(tl) * int(ts * 1.3) + 50 + len(bl) * int(bs * 1.4) + 30 + 70
    if h <= bottom - top:
        break

y = top + max(0, (bottom - top - h) // 2)
for l in tl:
    center(l, y, ft, "#0B4F5C"); y += int(ts * 1.3)
y += 15
d.line([(300, y), (W - 300, y)], fill="#C9A24B", width=5); y += 35
for l in bl:
    center(l, y, fb, "#33413F"); y += int(bs * 1.4)
y += 25
fs = ImageFont.truetype(B, 32)
sw = d.textlength(source, font=fs) + 70
d.rounded_rectangle([(W - sw) / 2, y, (W + sw) / 2, y + 66], 33, fill="#E8C66A")
center(source, y + 15, fs, "#0B4F5C")
img.save(out)
print("saved", out)
