"""Original upbeat 128 BPM track (15 s) for DKOT reels. Usage: python3 make_beat.py out.wav [variant]"""
import sys

import numpy as np
from scipy.io import wavfile

SR = 44100
BPM = 128
BEAT = 60 / BPM
LEN = 32 * BEAT
N = int(LEN * SR)
rng = np.random.default_rng(7)


def env(n, decay):
    return np.exp(-np.arange(n) / SR / decay)


def place(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    e = min(len(buf), i + len(sig))
    buf[i:e] += sig[: e - i] * gain


def kick():
    n = int(0.35 * SR)
    tt = np.arange(n) / SR
    f = 45 + 110 * np.exp(-tt * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(n, 0.16) + 0.3 * rng.standard_normal(n) * env(n, 0.004)


def lp(x, a):
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


def clap():
    n = int(0.25 * SR)
    no = rng.standard_normal(n)
    no = no - lp(no, 0.15)
    e = env(n, 0.07)
    for d in (0.0, 0.011, 0.022):
        e[int(d * SR):] += 0.0
    return no * e * 0.8


def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    no = rng.standard_normal(n)
    no = no - lp(no, 0.5)
    return no * env(n, 0.06 if open_ else 0.012) * 0.35


def saw(freq, dur, decay):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    s = 2 * ((tt * freq) % 1) - 1
    s2 = 2 * ((tt * freq * 1.006) % 1) - 1
    return (s + s2) * 0.5 * env(n, decay)


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def build(variant=0):
    mix = np.zeros(N)
    roots = [[57, 53, 48, 55], [52, 48, 55, 50], [50, 46, 53, 48]][variant % 3]  # chord roots per bar
    K, C, Hh = kick(), clap(), hat()
    # intro riser (beats 0-4)
    n = int(4 * BEAT * SR)
    tt = np.arange(n) / SR
    noise = rng.standard_normal(n)
    hp = noise - lp(noise, 0.05)
    riser = hp * (tt / tt[-1]) ** 2 * 0.35
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 900 * (tt / tt[-1]) ** 2) / SR) * (tt / tt[-1]) ** 2 * 0.15
    place(mix, riser + sweep, 0)
    # intro hits on the hook words + snare roll
    place(mix, K, 0, 0.9)
    place(mix, K, 2 * BEAT, 0.9)
    for i in range(16):
        t = 3 * BEAT + i * BEAT / 16 * 1.0
        place(mix, clap(), t, 0.15 + 0.5 * i / 16)
    # drop impact
    n = int(1.5 * SR)
    boom = np.sin(2 * np.pi * np.cumsum(30 + 60 * np.exp(-np.arange(n) / SR * 6)) / SR) * env(n, 0.5)
    crash = rng.standard_normal(n)
    crash = (crash - lp(crash, 0.3)) * env(n, 0.45) * 0.25
    place(mix, boom + crash, 4 * BEAT, 1.0)
    for b in range(4, 32):
        t = b * BEAT
        place(mix, K, t, 1.0)
        if b % 2 == 1:
            place(mix, C, t, 0.9)
        place(mix, Hh, t + BEAT / 2, 1.0)
        place(mix, hat(), t + BEAT / 4, 0.4)
        place(mix, hat(), t + 3 * BEAT / 4, 0.4)
        bar = (b - 4) // 4
        r = roots[bar % 4]
        # bass on offbeat 8ths
        place(mix, lp(saw(note(r - 12), BEAT / 2, 0.12), 0.08), t + BEAT / 2, 0.9)
        place(mix, lp(saw(note(r - 12), BEAT / 4, 0.06), 0.08), t, 0.35)
        # chord stab on offbeats
        stab = sum(saw(note(r + iv + 12), BEAT * 0.45, 0.09) for iv in (0, 3, 7)) / 3
        place(mix, lp(stab, 0.25), t + BEAT / 2, 0.35)
        # lead plucks pattern
        if b >= 8:
            seq = [0, 7, 12, 7, 3, 7, 10, 7]
            for k in range(2):
                m = r + 24 + seq[(b * 2 + k) % len(seq)]
                place(mix, lp(saw(note(m), BEAT * 0.4, 0.07), 0.35), t + k * BEAT / 2, 0.16)
    # sidechain pump
    pump = np.ones(N)
    for b in range(4, 32):
        i = int(b * BEAT * SR)
        n = int(BEAT * SR)
        e = 1 - 0.55 * np.exp(-np.arange(min(n, N - i)) / SR / 0.09)
        pump[i:i + len(e)] *= e
    mix *= pump * 0.85 + 0.15
    # fade last beat
    f = int(BEAT * SR)
    mix[-f:] *= np.linspace(1, 0, f)
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.6) * 0.89
    return mix


if __name__ == "__main__":
    out = sys.argv[1]
    v = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    m = build(v)
    st = np.stack([m, np.roll(m, 120) * 0.97], axis=1)
    wavfile.write(out, SR, (st * 32767).astype(np.int16))
    print(out, len(m) / SR)
