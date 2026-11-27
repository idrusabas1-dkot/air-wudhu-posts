"""
Tata letak layar (style["tata"]):
  pojok  (default) panggung cerita stickman besar di atas, kata hologram + subtitle di TENGAH, Gus Idrus kecil di pojok kanan bawah
  tengah           tata letak lama: ustad besar di tengah, subtitle di bawah kakinya
apply(st) dipanggil sekali di awal render/preview; modul lain membaca nilai dari sini.
"""
MODE = "pojok"

STAGE_TOP = 330
PANEL_BOTTOM = 1108          # bawah panggung cerita
LANE_Y = 1214                # subtitle hologram (di tengah, antara panggung & ustad)
SUB_TOP = 1238               # subtitle
UX, UY, US = 872, 1708, 0.42  # ustad (x tengah, garis bawah figur, skala)
WM = (300, 1392)             # watermark
TRANS_Y1 = 1360              # batas bawah area transisi


def apply(st):
    global MODE, LANE_Y, SUB_TOP, UX, UY, US, WM, TRANS_Y1
    MODE = (st or {}).get("tata", "pojok")
    if MODE == "tengah":
        LANE_Y, SUB_TOP, UX, UY, US, WM, TRANS_Y1 = 1282, 1436, None, 1392, None, (540, 1600), 1430
    else:
        MODE = "pojok"
        LANE_Y, SUB_TOP, UX, UY, US, WM, TRANS_Y1 = 1214, 1238, 872, 1708, 0.42, (300, 1392), 1360
    return MODE


def pojok():
    return MODE == "pojok"
