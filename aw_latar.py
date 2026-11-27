"""
Variasi latar format kisah (2026-11-22). Latar "peran" (kitab / musholla) tetap menentukan figuran & properti depan
(meja ngaji, santri, jamaah, sajadah); modul ini hanya mengganti DINDING/PEMANDANGAN di belakangnya + kehidupan bergeraknya.

  kitab    -> kitab | serambi | majelis | pendopo | pesantren | ruang_tamu
  musholla -> musholla | masjid

assign(script) memilih variasi per adegan: tiap video urutan berbeda (seed dari judul), adegan kajian berturut-turut
berganti latar. Paksa manual: shot["wajah"] = "<nama>".  Matikan: style["latar_variasi"] = false.
"""
import functools
import math
import zlib

import cv2
import numpy as np

W, H = 1080, 1920
POOL = {"kitab": ["kitab", "serambi", "majelis", "pendopo", "pesantren", "ruang_tamu"],
        "musholla": ["musholla", "masjid"]}
VARIAN = {v for p in POOL.values() for v in p}
OUT = (46, 40, 38)


def _i(v):
    return int(round(v))


def _KS():
    import aw_kisah as KS
    return KS


def assign(script, st=None):
    """Daftar nama latar tampilan per adegan (None = pakai latar asli)."""
    adegan = script.get("adegan") or []
    if not (st or {}).get("latar_variasi", True):
        return [None] * len(adegan)
    seed = zlib.crc32((script.get("judul") or script.get("judul_pendek") or "x").encode("utf-8"))
    r = np.random.RandomState(seed % (2 ** 31))
    pick = {}
    for role, pool in POOL.items():
        p = list(pool)
        r.shuffle(p)
        pick[role] = p
    n_k = 0
    out = []
    mus = pick["musholla"][0]                                          # satu cerita = satu tempat sholat (kontinuitas)
    kaj = pick["kitab"][:3]                                            # tiap video 3 latar kajian, bergilir
    for sc in adegan:
        shot = sc.get("shot") or {}
        lat = shot.get("latar")
        if shot.get("wajah"):
            out.append(shot["wajah"])
        elif lat == "kitab":
            out.append(kaj[n_k % len(kaj)])
            n_k += 1
        elif lat == "musholla":
            out.append(mus)
        else:
            out.append(None)
    return out


# ================================================================ latar statis (cache)
@functools.lru_cache(maxsize=16)
def base(var, malam=False):
    KS = _KS()
    img = np.zeros((H, W, 3), np.uint8)
    fn = {"serambi": _serambi, "majelis": _majelis, "pendopo": _pendopo, "pesantren": _pesantren,
          "ruang_tamu": _ruang_tamu, "masjid": _masjid}.get(var)
    if fn is None:
        return None
    fn(img, KS, malam)
    return img


def _floor_tiles(img, KS, y0, c0, c1, line):
    KS._gradient(img, y0, H, c0, c1)
    for k in range(9):                                                 # garis ubin perspektif
        y = y0 + int((k / 8.0) ** 1.6 * (H - y0))
        cv2.line(img, (0, y), (W, y), line, 2, cv2.LINE_AA)
    for k in range(-6, 7):
        cv2.line(img, (540 + k * 90, y0), (540 + k * 300, H), line, 2, cv2.LINE_AA)


def _dome_masjid(img, KS, cx, base_y, s, col=(64, 140, 110), wall=(244, 238, 222)):
    cv2.rectangle(img, (_i(cx - 190 * s), _i(base_y - 160 * s)), (_i(cx + 190 * s), base_y), wall, -1)
    for k in range(5):                                                 # jendela lengkung kecil
        x = cx - 150 * s + k * 75 * s
        cv2.rectangle(img, (_i(x), _i(base_y - 120 * s)), (_i(x + 34 * s), _i(base_y - 40 * s)), (120, 150, 160), -1)
        cv2.ellipse(img, (_i(x + 17 * s), _i(base_y - 120 * s)), (_i(17 * s), _i(17 * s)), 0, 180, 360, (120, 150, 160), -1, cv2.LINE_AA)
    cv2.rectangle(img, (_i(cx - 120 * s), _i(base_y - 200 * s)), (_i(cx + 120 * s), _i(base_y - 160 * s)), wall, -1)
    cv2.ellipse(img, (cx, _i(base_y - 200 * s)), (_i(130 * s), _i(150 * s)), 0, 180, 360, col, -1, cv2.LINE_AA)
    cv2.line(img, (cx, _i(base_y - 350 * s)), (cx, _i(base_y - 400 * s)), (214, 180, 96), _i(5 * s) + 1, cv2.LINE_AA)
    cv2.circle(img, (cx, _i(base_y - 410 * s)), _i(12 * s), (214, 180, 96), -1, cv2.LINE_AA)
    for side in (-1, 1):                                               # menara
        mx = cx + side * 260 * s
        cv2.rectangle(img, (_i(mx - 22 * s), _i(base_y - 480 * s)), (_i(mx + 22 * s), base_y), wall, -1)
        cv2.rectangle(img, (_i(mx - 32 * s), _i(base_y - 380 * s)), (_i(mx + 32 * s), _i(base_y - 366 * s)), (214, 180, 96), -1)
        cv2.ellipse(img, (_i(mx), _i(base_y - 480 * s)), (_i(26 * s), _i(40 * s)), 0, 180, 360, col, -1, cv2.LINE_AA)


def _serambi(img, KS, malam):
    """Serambi masjid: pemandangan halaman + kubah dari balik deretan lengkung."""
    KS._gradient(img, 0, 1240, (150, 196, 226), (238, 228, 204))
    KS._gradient(img, 980, 1240, (150, 186, 120), (120, 160, 98))      # rumput halaman
    _dome_masjid(img, KS, 720, 1000, 1.25)
    for x, s in ((120, 1.4), (980, 1.2)):
        KS.tree(img, x, 1010, s, 1.0, 1)
    wall = (240, 232, 212)
    cv2.rectangle(img, (0, 0), (W, 230), wall, -1)                     # balok atas + lengkung
    for k in range(3):
        cx = 180 + k * 360
        cv2.ellipse(img, (cx, 330), (150, 140), 0, 180, 360, (0, 0, 0), -1, cv2.LINE_AA)
    mask = np.all(img[:470] == 0, axis=2)
    sky = np.zeros_like(img[:470])
    KS._gradient(sky, 0, 470, (150, 196, 226), (186, 214, 230))
    img[:470][mask] = sky[mask]
    for k in range(3):
        cx = 180 + k * 360
        cv2.rectangle(img, (cx - 150, 230), (cx + 150, 330), wall, -1)
        cv2.ellipse(img, (cx, 330), (150, 140), 0, 180, 360, wall, -1, cv2.LINE_AA)
        cv2.ellipse(img, (cx, 330), (130, 120), 0, 180, 360, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.rectangle(img, (cx - 130, 330), (cx + 130, 360), (0, 0, 0), -1)
    m2 = np.all(img[:400] == 0, axis=2)
    img[:400][m2] = sky[:400][m2]
    for k in range(3):
        cx = 180 + k * 360
        cv2.ellipse(img, (cx, 330), (140, 130), 0, 180, 360, (214, 180, 96), 5, cv2.LINE_AA)
    for x in (0, 360, 720, 1080):                                      # tiang
        cv2.rectangle(img, (x - 34, 220), (x + 34, 1240), (232, 222, 198), -1)
        cv2.rectangle(img, (x - 34, 220), (x + 34, 1240), (196, 182, 150), 3)
        cv2.rectangle(img, (x - 44, 1180), (x + 44, 1240), (206, 192, 160), -1)
        cv2.rectangle(img, (x - 44, 210), (x + 44, 240), (206, 192, 160), -1)
    for k in range(18):                                                # pola geometris di balok
        KS._star8(img, 30 + k * 60, 110, 18, (214, 180, 96))
    _floor_tiles(img, KS, 1240, (236, 228, 212), (208, 196, 176), (196, 184, 160))


def _majelis(img, KS, malam):
    """Majelis taklim: dinding hijau, jendela kisi geometris, tirai, karpet merah."""
    KS._gradient(img, 0, 1240, (232, 226, 206), (220, 212, 190))
    cv2.rectangle(img, (0, 880), (W, 1240), (44, 104, 80), -1)
    cv2.rectangle(img, (0, 870), (W, 890), (214, 180, 96), -1)
    x0, y0, x1, y1 = 300, 330, 780, 830                                # jendela kisi (masyrabiyah)
    cv2.rectangle(img, (x0, y0), (x1, y1), (250, 232, 190) if not malam else (60, 70, 110), -1)
    cv2.ellipse(img, ((x0 + x1) // 2, y0), ((x1 - x0) // 2, 140), 0, 180, 360, (250, 232, 190) if not malam else (60, 70, 110), -1, cv2.LINE_AA)
    for yy in range(y0 - 100, y1 + 1, 80):
        for xx in range(x0 + 40, x1, 80):
            KS._star8(img, xx, yy, 34, (120, 80, 50))
            KS._star8(img, xx, yy, 16, (250, 232, 190) if not malam else (60, 70, 110))
    cv2.rectangle(img, (x0, y0), (x1, y1), (110, 74, 46), 16)
    cv2.ellipse(img, ((x0 + x1) // 2, y0), ((x1 - x0) // 2, 140), 0, 180, 360, (110, 74, 46), 16, cv2.LINE_AA)
    mask = np.zeros(img.shape[:2], np.uint8)                           # rapikan pola keluar bingkai
    cv2.rectangle(mask, (x0, y0), (x1, y1), 255, -1)
    cv2.ellipse(mask, ((x0 + x1) // 2, y0), ((x1 - x0) // 2, 140), 0, 180, 360, 255, -1)
    wallc = np.zeros_like(img)
    KS._gradient(wallc, 0, 1240, (232, 226, 206), (220, 212, 190))
    outside = (mask == 0) & (np.arange(H)[:, None] < 870)
    img[outside] = wallc[outside]
    cv2.rectangle(img, (x0, y0), (x1, y1), (110, 74, 46), 16)
    cv2.ellipse(img, ((x0 + x1) // 2, y0), ((x1 - x0) // 2, 140), 0, 180, 360, (110, 74, 46), 16, cv2.LINE_AA)
    KS._clock(img, 930, 300, 44)
    for k, x in enumerate((90, 990)):                                  # bingkai kaligrafi geometris (tanpa tulisan)
        cv2.rectangle(img, (x - 60, 480), (x + 60, 680), (150, 112, 60), -1)
        cv2.rectangle(img, (x - 48, 492), (x + 48, 668), (36, 86, 64), -1)
        KS._star8(img, x, 580, 36, (222, 186, 96))
    _floor_tiles(img, KS, 1240, (168, 52, 58), (130, 36, 44), (150, 44, 50))
    cv2.rectangle(img, (0, 1240), (W, 1262), (214, 180, 96), -1)


def _pendopo(img, KS, malam):
    """Pendopo kayu terbuka: tiang, atap joglo, kebun & sawah di belakang."""
    KS._gradient(img, 0, 900, (160, 204, 230), (236, 232, 212))
    pts = [(0, 900)] + [(x, 760 + 60 * math.sin(x / 170.0) + 30 * math.sin(x / 61.0)) for x in range(0, W + 20, 20)] + [(W, 900)]
    KS._poly(img, pts, (150, 176, 150))
    KS._gradient(img, 900, 1240, (128, 180, 96), (104, 156, 80))
    for k in range(6):                                                 # petak sawah
        y = 930 + k * k * 9 + k * 20
        cv2.line(img, (0, y), (W, y), (150, 196, 110), 3, cv2.LINE_AA)
    for x, s, kd in ((150, 1.3, 0), (420, 1.0, 1), (900, 1.5, 0)):
        KS.tree(img, x, 960, s, 1.0, kd)
    KS._poly(img, [(-40, 0), (W + 40, 0), (W + 40, 220), (-40, 220)], (110, 70, 44))   # atap / blandar
    for k in range(9):
        cv2.line(img, (k * 135, 0), (k * 135 - 60, 220), (90, 56, 36), 8, cv2.LINE_AA)
    cv2.rectangle(img, (0, 220), (W, 262), (140, 92, 58), -1)
    for k in range(20):
        cv2.rectangle(img, (k * 56 + 8, 262), (k * 56 + 40, 300), (140, 92, 58), -1)    # ukiran gigi balang
    for x in (60, 1020):                                               # saka (tiang)
        cv2.rectangle(img, (x - 30, 262), (x + 30, 1240), (132, 86, 54), -1)
        cv2.rectangle(img, (x - 30, 262), (x + 30, 1240), (100, 64, 40), 3)
        cv2.rectangle(img, (x - 44, 1200), (x + 44, 1240), (180, 170, 150), -1)
    KS._gradient(img, 1240, H, (176, 124, 80), (146, 100, 64))         # lantai papan
    for k in range(12):
        y = 1240 + int((k / 11.0) ** 1.5 * (H - 1240))
        cv2.line(img, (0, y), (W, y), (128, 86, 54), 3, cv2.LINE_AA)


def _pesantren(img, KS, malam=True):
    """Halaman pesantren malam: asrama berlampu, bulan, pohon kelapa; tikar di halaman."""
    KS._gradient(img, 0, 1000, (22, 30, 64), (64, 70, 112))
    cv2.circle(img, (820, 260), 62, (250, 238, 190), -1, cv2.LINE_AA)
    cv2.circle(img, (846, 244), 56, (24, 32, 66), -1, cv2.LINE_AA)
    r = np.random.RandomState(5)
    for _ in range(70):
        cv2.circle(img, (_i(r.uniform(0, W)), _i(r.uniform(0, 700))), int(r.uniform(1, 3)), (240, 240, 220), -1, cv2.LINE_AA)
    cv2.rectangle(img, (120, 640), (960, 1000), (196, 190, 176), -1)   # asrama 2 lantai
    KS._poly(img, [(80, 650), (1000, 650), (900, 540), (180, 540)], (38, 96, 70))
    cv2.rectangle(img, (120, 810), (960, 830), (38, 96, 70), -1)
    for row, y in enumerate((680, 860)):
        for k in range(7):
            x = 160 + k * 116
            cv2.rectangle(img, (x, y), (x + 60, y + 90), (250, 214, 120) if (k + row) % 3 else (90, 96, 110), -1)
            cv2.rectangle(img, (x, y), (x + 60, y + 90), (110, 90, 70), 4)
    _dome_masjid(img, KS, 540, 640, 0.55, col=(40, 110, 84), wall=(200, 196, 186))
    for x, lean in ((50, 1), (1040, -1)):                              # pohon kelapa siluet
        pts = [(x + lean * k * 6 + 6 * math.sin(k), 1000 - k * 40) for k in range(12)]
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, (_i(a[0]), _i(a[1])), (_i(b[0]), _i(b[1])), (30, 34, 40), 22, cv2.LINE_AA)
        tx, ty = pts[-1]
        for k in range(7):
            ang = math.radians(200 + k * 24)
            cv2.ellipse(img, (_i(tx + 90 * math.cos(ang)), _i(ty + 50 * math.sin(ang) + 30)), (110, 22), math.degrees(ang), 0, 360,
                        (30, 40, 40), -1, cv2.LINE_AA)
    KS._gradient(img, 1000, 1240, (50, 56, 70), (70, 72, 80))         # pagar rendah + halaman
    cv2.rectangle(img, (0, 1100), (W, 1130), (120, 116, 110), -1)
    for x in range(0, W, 90):
        cv2.rectangle(img, (x, 1060), (x + 20, 1130), (120, 116, 110), -1)
    KS._gradient(img, 1240, H, (96, 92, 84), (70, 66, 60))
    cv2.rectangle(img, (0, 1430), (800, 1760), (176, 150, 96), -1)     # tikar pandan
    for x in range(0, 800, 40):
        cv2.line(img, (x, 1430), (x, 1760), (150, 124, 76), 2)


def _ruang_tamu(img, KS, malam):
    """Ruang tamu rumah: jendela bertirai, sofa, tanaman, lemari, bingkai."""
    KS._gradient(img, 0, 1240, (240, 226, 200), (228, 212, 184))
    cv2.rectangle(img, (0, 960), (W, 1240), (196, 160, 120), -1)       # lambris kayu
    for x in range(0, W, 70):
        cv2.line(img, (x, 960), (x, 1240), (176, 140, 100), 3)
    cv2.rectangle(img, (0, 950), (W, 966), (150, 110, 74), -1)
    x0, y0, x1, y1 = 420, 300, 900, 760                                # jendela
    cv2.rectangle(img, (x0, y0), (x1, y1), (150, 200, 226) if not malam else (30, 42, 78), -1)
    KS._gradient(img[y0:y1, x0:x1], 0, y1 - y0, (150, 200, 226), (226, 232, 220)) if not malam else None
    KS._poly(img, [(x0, 700), (x0 + 120, 620), (x0 + 260, 680), (x0 + 380, 600), (x1, 660), (x1, y1), (x0, y1)], (120, 176, 110))
    cv2.rectangle(img, (x0, y0), (x1, y1), (250, 248, 240), 16)
    cv2.line(img, ((x0 + x1) // 2, y0), ((x0 + x1) // 2, y1), (250, 248, 240), 10)
    cv2.rectangle(img, (x0 - 60, y1), (x1 + 60, y1 + 20), (250, 248, 240), -1)
    cv2.rectangle(img, (x0 - 80, y0 - 50), (x1 + 80, y0 - 36), (120, 90, 60), -1)   # rel tirai
    KS._clock(img, 200, 330, 46)
    cv2.rectangle(img, (110, 470), (290, 640), (150, 112, 60), -1)     # bingkai geometris
    cv2.rectangle(img, (124, 484), (276, 626), (230, 220, 196), -1)
    KS._star8(img, 200, 555, 48, (46, 120, 80))
    KS._star8(img, 200, 555, 22, (230, 220, 196))
    cv2.rectangle(img, (930, 800), (1060, 1240), (150, 104, 68), -1)   # lemari kecil + tanaman
    cv2.rectangle(img, (944, 820), (1046, 1000), (170, 122, 82), -1)
    cv2.rectangle(img, (944, 1020), (1046, 1220), (170, 122, 82), -1)
    KS._gradient(img, 1240, H, (196, 150, 104), (170, 126, 84))        # parket
    for k in range(14):
        y = 1240 + int((k / 13.0) ** 1.5 * (H - 1240))
        cv2.line(img, (0, y), (W, y), (160, 116, 76), 2, cv2.LINE_AA)
    cv2.ellipse(img, (420, 1620), (420, 150), 0, 0, 360, (150, 70, 70), -1, cv2.LINE_AA)   # karpet bulat
    cv2.ellipse(img, (420, 1620), (380, 126), 0, 0, 360, (214, 180, 96), 4, cv2.LINE_AA)


def _masjid(img, KS, malam):
    """Masjid besar: deretan tiang & lengkung, mihrab bermotif, karpet merah ber-shaf."""
    KS._gradient(img, 0, 1180, (246, 240, 226), (232, 222, 202))
    cv2.rectangle(img, (330, 300), (750, 1180), (226, 214, 190), -1)   # mihrab
    cv2.ellipse(img, (540, 300), (210, 210), 0, 180, 360, (226, 214, 190), -1, cv2.LINE_AA)
    cv2.rectangle(img, (380, 360), (700, 1180), (40, 100, 80), -1)
    cv2.ellipse(img, (540, 360), (160, 170), 0, 180, 360, (40, 100, 80), -1, cv2.LINE_AA)
    for yy in range(260, 1180, 92):
        for xx in range(420, 700, 92):
            KS._star8(img, xx, yy, 30, (214, 180, 96))
            KS._star8(img, xx, yy, 13, (40, 100, 80))
    m = np.zeros(img.shape[:2], np.uint8)
    cv2.rectangle(m, (380, 360), (700, 1180), 255, -1)
    cv2.ellipse(m, (540, 360), (160, 170), 0, 180, 360, 255, -1)
    bg = np.zeros_like(img)
    KS._gradient(bg, 0, 1180, (246, 240, 226), (232, 222, 202))
    cv2.rectangle(bg, (330, 300), (750, 1180), (226, 214, 190), -1)
    cv2.ellipse(bg, (540, 300), (210, 210), 0, 180, 360, (226, 214, 190), -1, cv2.LINE_AA)
    outside = (m == 0) & (np.arange(H)[:, None] < 1180)
    img[outside] = bg[outside]
    cv2.ellipse(img, (540, 360), (160, 170), 0, 180, 360, (214, 180, 96), 8, cv2.LINE_AA)
    cv2.rectangle(img, (380, 360), (700, 1180), (214, 180, 96), 8)
    for side in (-1, 1):                                               # tiang & lengkung samping
        for k, x in enumerate((150, 0)):
            xx = 540 + side * (540 - x) if side > 0 else x
            cv2.rectangle(img, (xx - 36, 200), (xx + 36, 1180), (236, 228, 210), -1)
            cv2.rectangle(img, (xx - 36, 200), (xx + 36, 1180), (200, 186, 156), 3)
            cv2.rectangle(img, (xx - 46, 190), (xx + 46, 220), (214, 180, 96), -1)
        cx = 75 if side < 0 else W - 75
        cv2.ellipse(img, (cx, 200), (75, 90), 0, 180, 360, (214, 180, 96), 6, cv2.LINE_AA)
    cv2.rectangle(img, (0, 0), (W, 70), (40, 100, 80), -1)
    for k in range(18):
        KS._star8(img, 30 + k * 60, 36, 18, (214, 180, 96))
    KS._gradient(img, 1180, H, (160, 46, 54), (128, 34, 42))           # karpet merah ber-shaf
    for k in range(8):
        y = 1180 + k * k * 8 + k * 30
        cv2.line(img, (0, y), (W, y), (214, 180, 96), 4, cv2.LINE_AA)
    cv2.rectangle(img, (0, 1166), (W, 1186), (140, 110, 74), -1)


# ================================================================ kehidupan bergerak per latar
def life(var, c, t, tg, fx=True):
    KS = _KS()
    if var == "serambi":
        for k in range(2):                                             # awan & burung di balik lengkung
            cx = (k * 520 + tg * 16) % (W + 400) - 200
            cy = 560 + k * 120
            for j in range(4):
                cv2.ellipse(c, (_i(cx + j * 50 - 80), _i(cy - (j % 2) * 16)), (60, 28), 0, 0, 360, (250, 250, 246), -1, cv2.LINE_AA)
        for k in range(4):
            ph = (tg * 0.07 + 0.5) % 1.0
            KS.bird(c, -100 + ph * (W + 200) - (k % 2) * 50, 500 + k * 24 + 8 * math.sin(tg * 1.3 + k), 1.3, tg + k * 0.3)
    elif var == "majelis":
        cx, cy = 540, 130                                              # kipas angin langit-langit berputar
        cv2.line(c, (cx, 0), (cx, cy), (90, 80, 70), 6, cv2.LINE_AA)
        for k in range(3):
            a = tg * 7.0 + k * 2 * math.pi / 3
            ex, ey = cx + 230 * math.cos(a), cy + 34 * math.sin(a)
            cv2.line(c, (cx, cy), (_i(ex), _i(ey)), (120, 90, 60), 18, cv2.LINE_AA)
        cv2.circle(c, (cx, cy), 22, (90, 70, 50), -1, cv2.LINE_AA)
        for x0, x1, side in ((230, 335, -1), (745, 850, 1)):               # tirai bergoyang
            sw = 14 * math.sin(tg * 1.1 + side)
            KS._poly(c, [(x0, 250), (x1, 250), (x1 + sw * 0.6 - side * 20, 880), (x0 + sw - side * 20, 880)], (150, 40, 50), OUT, 2)
            for k in range(3):
                xx = x0 + (k + 1) * (x1 - x0) / 4
                cv2.line(c, (_i(xx), 260), (_i(xx + sw * 0.8 - side * 20), 870), (120, 30, 40), 3, cv2.LINE_AA)
    elif var == "pendopo":
        a = math.radians(6 * math.sin(tg * 1.3))                       # lampion bergoyang
        lx, ly = 540 + math.sin(a) * 120, 262 + math.cos(a) * 120
        cv2.line(c, (540, 262), (_i(lx), _i(ly)), (60, 50, 40), 3, cv2.LINE_AA)
        cv2.ellipse(c, (_i(lx), _i(ly + 40)), (34, 44), 0, 0, 360, (220, 70, 60), -1, cv2.LINE_AA)
        cv2.ellipse(c, (_i(lx), _i(ly + 40)), (34, 44), 0, 0, 360, OUT, 2, cv2.LINE_AA)
        for k in range(3):
            ph = (tg * 0.05 + k * 0.33) % 1.0
            KS.bird(c, -100 + ph * (W + 200), 420 + k * 40 + 10 * math.sin(tg + k), 1.2, tg + k)
        for k in range(2):
            KS.butterfly(c, 300 + k * 400 + 80 * math.sin(tg * 0.7 + k * 2), 1050 + 50 * math.sin(tg * 1.4 + k), 1.8, tg + k,
                         [(250, 180, 60), (240, 120, 150)][k])
    elif var == "pesantren":
        r = np.random.RandomState(9)                                   # bintang berkelip + kunang-kunang
        for k in range(18):
            x, y = r.uniform(0, W), r.uniform(0, 600)
            tw = max(0.0, math.sin(tg * 2.2 + k * 1.7)) ** 2
            if tw > 0.05:
                KS._sparkle(c, x, y, 1.0 + 2.2 * tw, (255, 246, 210))
        for k in range(10):
            x = (r.uniform(0, W) + 40 * math.sin(tg * 0.6 + k)) % W
            y = 1000 + 180 * math.sin(tg * 0.4 + k * 1.3) + r.uniform(0, 200)
            b = 0.5 + 0.5 * math.sin(tg * 3.0 + k)
            cv2.circle(c, (_i(x), _i(y)), _i(3 + 3 * b), (210, 250, 140), -1, cv2.LINE_AA)
    elif var == "ruang_tamu":
        for side, x0, x1 in ((-1, 340, 470), (1, 850, 980)):            # tirai bergoyang
            sw = 12 * math.sin(tg * 1.0 + side)
            KS._poly(c, [(x0, 250), (x1, 250), (x1 + sw * 0.6, 860), (x0 + sw, 880)], (110, 150, 120), OUT, 2)
            for k in range(3):
                xx = x0 + (k + 1) * (x1 - x0) / 4
                cv2.line(c, (_i(xx), 260), (_i(xx + sw * 0.8), 860), (90, 130, 100), 3, cv2.LINE_AA)
        a = math.radians(3 * math.sin(tg * 1.2))                       # tanaman pot bergoyang di atas lemari
        cv2.rectangle(c, (960, 730), (1030, 800), (190, 110, 70), -1)
        for k in range(6):
            ang = math.radians(-150 + k * 24) + a
            cv2.ellipse(c, (_i(995 + 60 * math.cos(ang)), _i(720 + 60 * math.sin(ang))), (46, 14), math.degrees(ang), 0, 360,
                        (70, 140, 80), -1, cv2.LINE_AA)
