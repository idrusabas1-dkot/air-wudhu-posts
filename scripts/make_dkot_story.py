"""Generate DKOT Coffee promo stories (1080x1920 JPEG).

Usage: python3 scripts/make_dkot_story.py OUT_DIR
Creates OUT_DIR/{slot}-{variant}.jpg for 6 slots x 3 variants.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FD = "/usr/share/fonts/truetype/google-fonts/"
BOLD = FD + "Poppins-Bold.ttf"
MED = FD + "Poppins-Medium.ttf"
REG = FD + "Poppins-Regular.ttf"
ITAL = FD + "Poppins-MediumItalic.ttf"

SHOPEE = "spf.shopee.co.id/70Lq8Yydya"
GRAB = "app.grab.com/s/EmDgJRkg"

# palettes: (top, bottom, accent, text, cup)
PALETTES = [
    ((58, 34, 22), (20, 11, 7), (232, 168, 84), (250, 238, 220), (245, 232, 212)),
    ((24, 52, 46), (9, 22, 19), (240, 190, 110), (246, 240, 226), (240, 226, 204)),
    ((92, 30, 30), (34, 10, 12), (255, 196, 120), (252, 240, 228), (248, 234, 214)),
]

SLOTS = {
    "07": [
        ("SELAMAT PAGI", "Awali hari\npenuh semangat\nbareng kopi!", "Diantar hangat ke depan pintu"),
        ("GOOD MORNING", "Belum ngopi,\nbelum mulai\nhari.", "Pesan sekarang, langsung diantar"),
        ("PAGI CERAH", "Bangun pagi\njadi ringan\nbareng DKOT.", "Kopi segar tiap pagi"),
    ],
    "10": [
        ("JAM 10 PAGI", "Fokus kerja\nbutuh kopi\nyang pas.", "Pesan tanpa ninggalin meja"),
        ("COFFEE BREAK", "Rehat sejenak,\nbiar ide\nmengalir lagi.", "Satu klik, kopi datang"),
        ("SEMANGAT KERJA", "Meeting lancar\nkalau kopinya\nDKOT.", "Pesan buat satu tim juga bisa"),
    ],
    "12": [
        ("MAKAN SIANG", "Makan siang\nbelum lengkap\ntanpa kopi.", "Pesan bareng menu siangmu"),
        ("ISTIRAHAT SIANG", "Panas di luar?\nYang dingin-\ndingin aja.", "Es kopi segar diantar"),
        ("LUNCH TIME", "Kenyang sudah,\nsekarang\nwaktunya ngopi.", "Biar gak ngantuk habis makan"),
    ],
    "15": [
        ("JAM 3 SORE", "Ngantuk\nmenyerang?\nButuh booster!", "DKOT siap jadi penyelamat"),
        ("SORE ASYIK", "Kopi sore,\nmood naik\nlagi.", "Pesan sekarang, santai nunggu"),
        ("AFTERNOON", "Tenaga habis?\nIsi ulang\npakai kopi.", "Diantar ke kantor atau rumah"),
    ],
    "18": [
        ("PULANG KERJA", "Capek seharian?\nSaatnya santai\ndulu.", "Kopi sudah nunggu di rumah"),
        ("SENJA", "Senja paling\nenak ditemani\nkopi DKOT.", "Pesan sekarang, nikmati sore"),
        ("ME TIME", "Hari ini\nkamu hebat.\nTraktir diri!", "Kamu layak dapat kopi enak"),
    ],
    "20": [
        ("NGOPI MALAM", "Teman lembur\n& begadang\nterbaik.", "Masih buka, siap diantar"),
        ("MALAM SANTAI", "Nongkrong di\nrumah tetap\nseru.", "Pesan buat rame-rame"),
        ("NIGHT MODE", "Malam panjang,\nkopi jangan\nsampai kosong.", "Pesan sekarang sebelum tutup"),
    ],
}


def gradient(top, bottom):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


def beans(img, accent, seed):
    rnd = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(22):
        x, y = rnd.randint(-40, W + 40), rnd.randint(-40, H + 40)
        s = rnd.randint(26, 60)
        a = rnd.randint(18, 45)
        bean = Image.new("RGBA", (s * 2, s * 3), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bean)
        bd.ellipse([0, 0, s * 2 - 1, s * 3 - 1], fill=accent + (a,))
        bd.arc([s * 0.6, s * 0.2, s * 1.4, s * 2.8], 100, 260, fill=(0, 0, 0, a + 30), width=max(3, s // 8))
        bean = bean.rotate(rnd.randint(0, 360), expand=True)
        layer.alpha_composite(bean, (x, y))
    img.paste(layer, (0, 0), layer)


def cup(img, cx, cy, cupc, accent):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 330, cy - 300, cx + 330, cy + 300], fill=accent + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    layer.alpha_composite(glow)
    # saucer
    d.ellipse([cx - 280, cy + 150, cx + 280, cy + 240], fill=(0, 0, 0, 90))
    d.ellipse([cx - 260, cy + 130, cx + 260, cy + 215], fill=cupc + (255,))
    # body
    d.rounded_rectangle([cx - 190, cy - 120, cx + 190, cy + 170], radius=90, fill=cupc + (255,))
    d.rectangle([cx - 190, cy - 120, cx + 190, cy - 20], fill=cupc + (255,))
    # handle
    d.ellipse([cx + 140, cy - 70, cx + 290, cy + 90], outline=cupc + (255,), width=34)
    # coffee surface
    d.ellipse([cx - 190, cy - 160, cx + 190, cy - 80], fill=cupc + (255,))
    d.ellipse([cx - 168, cy - 150, cx + 168, cy - 92], fill=(92, 52, 30, 255))
    # latte art heart
    hx, hy = cx, cy - 121
    d.ellipse([hx - 44, hy - 22, hx + 2, hy + 12], fill=(238, 214, 182, 255))
    d.ellipse([hx - 2, hy - 22, hx + 44, hy + 12], fill=(238, 214, 182, 255))
    d.polygon([(hx - 42, hy - 2), (hx + 42, hy - 2), (hx, hy + 24)], fill=(238, 214, 182, 255))
    # band with brand
    d.rectangle([cx - 190, cy - 10, cx + 190, cy + 50], fill=accent + (255,))
    f = ImageFont.truetype(BOLD, 40)
    d.text((cx, cy + 20), "DKOT", font=f, fill=(40, 22, 14, 255), anchor="mm")
    # steam
    for k, off in enumerate((-70, 0, 70)):
        pts = []
        for i in range(40):
            t = i / 39
            pts.append((cx + off + 22 * math.sin(t * 2 * math.pi + k), cy - 190 - t * 120))
        d.line(pts, fill=(255, 255, 255, 120), width=12, joint="curve")
    img.paste(layer, (0, 0), layer)


def pill(d, box, fill, text, font, tcol=(255, 255, 255)):
    d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, font=font, fill=tcol, anchor="mm")


def make(slot, v, out):
    top, bot, accent, text, cupc = PALETTES[v]
    tag, headline, sub = SLOTS[slot][v]
    img = gradient(top, bot)
    beans(img, accent, hash((slot, v)) & 0xFFFF)
    d = ImageDraw.Draw(img)

    # header brand
    d.text((W / 2, 120), "DKOT COFFEE", font=ImageFont.truetype(BOLD, 64), fill=text, anchor="mm")
    d.line([(W / 2 - 150, 170), (W / 2 + 150, 170)], fill=accent, width=4)
    # tag chip
    ft = ImageFont.truetype(BOLD, 38)
    tw = d.textlength(tag, font=ft)
    pill(d, (W / 2 - tw / 2 - 40, 215, W / 2 + tw / 2 + 40, 285), accent, tag, ft, (40, 22, 14))

    # headline
    fh = ImageFont.truetype(BOLD, 96)
    lines = headline.split("\n")
    y = 360
    for ln in lines:
        d.text((W / 2, y), ln, font=fh, fill=text, anchor="mt")
        y += 112
    # sub
    d.text((W / 2, y + 20), sub, font=ImageFont.truetype(ITAL, 42), fill=accent, anchor="mt")

    cup(img, W // 2, 1130, cupc, accent)
    d = ImageDraw.Draw(img)

    # CTA area
    d.text((W / 2, 1390), "ORDER SEKARANG DI", font=ImageFont.truetype(BOLD, 46), fill=text, anchor="mm")
    fb = ImageFont.truetype(BOLD, 50)
    pill(d, (90, 1440, 520, 1540), (238, 77, 45), "ShopeeFood", fb)
    pill(d, (560, 1440, 990, 1540), (0, 177, 79), "GrabFood", fb)
    fu = ImageFont.truetype(REG, 28)
    d.text((305, 1570), SHOPEE, font=fu, fill=text, anchor="mm")
    d.text((775, 1570), GRAB, font=fu, fill=text, anchor="mm")
    # tap hint
    pill(d, (210, 1630, 870, 1720), text, "KLIK LINK DI BIO", ImageFont.truetype(BOLD, 44), top)

    img.save(out, "JPEG", quality=88, optimize=True)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for slot in SLOTS:
        for v in range(3):
            make(slot, v, out / f"{slot}-{v}.jpg")
    print("done", len(list(out.glob("*.jpg"))))
