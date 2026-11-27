"""Buat SFX hologram sintetis (tanpa lisensi pihak ketiga) ke assets/sfx: holo_boot, holo_on, holo_glitch."""
import os
import wave

import numpy as np

SR = 48000
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")


def save(name, x):
    x = x / (np.max(np.abs(x)) or 1) * 0.8
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def t_(d):
    return np.arange(int(d * SR)) / SR


def env(t, a, r):
    return np.minimum(1, t / a) * np.exp(-t / r)


rng = np.random.RandomState(7)

# boot: sapuan naik + dengung + kilau
t = t_(0.7)
f = 180 + 900 * (t / 0.7) ** 2
boot = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(t, 0.02, 0.3) * 0.6
boot += np.sin(2 * np.pi * 2400 * t) * np.sin(2 * np.pi * 31 * t) * env(np.maximum(t - 0.25, 1e-4), 0.01, 0.12) * (t > 0.25) * 0.25
boot += np.sin(2 * np.pi * 90 * t) * env(t, 0.05, 0.25) * 0.4
save("holo_boot", boot)

# on: dua nada blip digital + kilau
t = t_(0.32)
on = np.sin(2 * np.pi * 1320 * t) * env(t, 0.003, 0.05) * (t < 0.09)
t2 = np.maximum(t - 0.07, 0)
on += np.sin(2 * np.pi * 1980 * t2) * env(t2 + 1e-4, 0.003, 0.08) * (t > 0.07)
on += np.sin(2 * np.pi * 3600 * t) * np.sin(2 * np.pi * 45 * t) * env(t, 0.01, 0.1) * 0.25
save("holo_on", on)

# glitch: potongan derau + nada terputus
t = t_(0.3)
gate = (np.sin(2 * np.pi * 37 * t) > 0.2).astype(float)
gl = (rng.randn(len(t)) * 0.5 + np.sign(np.sin(2 * np.pi * 220 * t)) * 0.4) * gate * env(t, 0.002, 0.12)
gl = np.round(gl * 6) / 6                                  # efek bitcrush
save("holo_glitch", gl)
print("ok", OUT)
