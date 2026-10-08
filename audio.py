# -*- coding: utf-8 -*-
"""Звуки KINITO PARK: фоновый трек (song/my_world.ogg) + синтезированные эффекты."""
import math
import os

import numpy as np
import pygame

SR = 22050
TAU = 2 * np.pi


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _norm(x):
    return x / (np.abs(x).max() + 1e-9)


def fft_filter(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X * ((f >= lo) & (f <= hi)), len(x))


def noise(dur, lo, hi, rng):
    return _norm(fft_filter(rng.standard_normal(int(dur * SR)), lo, hi))


def crush(x, hold=3, levels=12):
    y = np.repeat(x[::hold], hold)[:len(x)]
    return np.round(y * levels) / levels


# ----------------------------------------------------------------- синтез
def s_step(rng, kind):
    dur = .18
    t = _t(dur)
    n = noise(dur, 200, 2800 if kind == 0 else 900, rng)
    env = np.exp(-t * (38 if kind == 0 else 20))
    th = np.sin(TAU * (75 + rng.uniform(-9, 9)) * t) * np.exp(-t * 30)
    return n * .7 * env + th * .8


def s_blip(rng):
    """Робот-голос в стиле Microsoft Sam: короткий хриплый звук на букву."""
    dur = .075
    t = _t(dur)
    f0 = rng.uniform(92, 150)
    f = f0 * (1 + rng.uniform(-.2, .25) * t / dur)
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1) - 1
    v = fft_filter(saw, 450, 1000) + .7 * fft_filter(saw, 1100, 1900)
    v = _norm(v)
    env = np.minimum(1, t * 220) * np.exp(-(t / dur) ** 2 * 3)
    return crush(v) * env


def s_creak(rng, dur=1.7):
    t = _t(dur)
    f = 140 + 90 * np.sin(TAU * .9 * t) + 40 * np.sin(TAU * 3.1 * t)
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    v = fft_filter(saw, 300, 1400)
    am = .55 + .45 * np.sin(TAU * 13 * t + 2 * np.sin(TAU * 1.7 * t))
    env = np.sin(np.pi * t / dur) ** 1.4
    return _norm(v * am * env)


def s_door_open(rng):
    dur = .8
    t = _t(dur)
    n = noise(dur, 60, 700, rng) * np.exp(-t * 4)
    th = np.sin(TAU * 52 * t) * np.exp(-t * 7)
    return _norm(n * .8 + th)


def s_whistle(rng):
    dur = 1.5
    t = _t(dur)
    f = 760 + 18 * np.sin(TAU * 6 * t)
    ph = np.cumsum(f) / SR
    v = np.sin(TAU * ph) + .45 * np.sin(TAU * 2.01 * ph) + .08 * noise(dur, 2000, 6000, rng)
    env = np.minimum(1, t * 12) * np.minimum(1, (dur - t) * 4)
    return _norm(v * env)


def s_bell(rng):
    t = _t(1.3)
    v = np.zeros_like(t)
    for f, d, a in ((1318, 3.2, 1), (1975, 4.5, .6), (2637, 6, .4), (3300, 9, .2)):
        v += a * np.sin(TAU * f * t) * np.exp(-t * d)
    return _norm(v)


def s_ratchet(rng):
    """Цепной подъём американских горок: щелчки, петля 0.5 c."""
    n = int(.5 * SR)
    out = np.zeros(n)
    for k, a in ((0, 1.0), (int(.25 * SR), .6)):
        t = _t(.03)
        c = fft_filter(rng.standard_normal(len(t)), 700, 5000) * np.exp(-t * 130)
        out[k:k + len(c)] += _norm(c) * a
    return out


def s_clack(rng):
    n = int(.24 * SR)
    out = np.zeros(n)
    for k, a in ((0, 1.0), (int(.085 * SR), .7)):
        t = _t(.1)
        c = fft_filter(rng.standard_normal(len(t)), 400, 3200) * np.exp(-t * 55)
        c = _norm(c) + .7 * np.sin(TAU * 150 * t) * np.exp(-t * 40)
        out[k:k + len(c)] += c * a
    return _norm(out)


def s_wind(rng):
    return noise(3.0, 150, 1700, rng)


def s_ferris_creak(rng):
    t = _t(4.0)
    v = noise(4.0, 300, 750, rng) * (.45 + .55 * np.sin(TAU * .5 * t)) \
        + .25 * np.sin(TAU * 90 * t)
    return _norm(v)


def s_water(rng):
    t = _t(3.0)
    return _norm(noise(3.0, 1800, 7000, rng) * (.75 + .25 * np.sin(TAU * t / 3 * 2)))


def s_train(rng):
    n = int(1.0 * SR)
    out = np.zeros(n)
    for k in range(4):
        t = _t(.14)
        c = fft_filter(rng.standard_normal(len(t)), 150, 1300) * np.exp(-t * 22)
        out[int(k * .25 * SR):int(k * .25 * SR) + len(t)] += _norm(c)
    out += .35 * np.sin(TAU * 55 * (np.arange(n) / SR))
    return _norm(out)


def s_musicbox():
    seq = [(76, .5), (75, .5), (76, .5), (75, .5), (76, .5), (71, .5), (74, .5), (72, .5), (69, 1.5),
           (60, .5), (64, .5), (69, .5), (71, 1.5), (64, .5), (68, .5), (71, .5), (72, 1.5),
           (64, .5), (76, .5), (75, .5), (76, .5), (75, .5), (76, .5), (71, .5), (74, .5), (72, .5), (69, 1.5),
           (60, .5), (64, .5), (69, .5), (71, 1.5), (64, .5), (72, .5), (71, .5), (69, 3.0)]
    beat = .34
    total = sum(b for _, b in seq) * beat + 1.6
    buf = np.zeros(int(total * SR))
    pos = 0.0
    for m, b in seq:
        f = 440.0 * 2 ** ((m + 12 - 69) / 12)
        t = _t(1.4)
        w = (np.sin(TAU * f * t) + .4 * np.sin(TAU * 2 * f * t) * np.exp(-t * 7) +
             .15 * np.sin(TAU * 3.01 * f * t) * np.exp(-t * 12) + .5 * np.sin(TAU * f * 1.006 * t))
        w *= np.exp(-t * 3.3) * (1 - np.exp(-t * 400))
        i0 = int(pos * SR)
        n = min(len(w), len(buf) - i0)
        buf[i0:i0 + n] += w[:n]
        pos += b * beat
    return _norm(buf)


def s_drone(rng):
    """Жуткий гул для Hide and Seek (8 секунд, частоты кратны 1/8 Гц -> бесшовная петля)."""
    t = _t(8.0)
    d = (.5 * np.sin(TAU * 55 * t) + .4 * np.sin(TAU * 55.25 * t) +
         .28 * np.sin(TAU * 82.5 * t + 2 * np.sin(TAU * .125 * t)) +
         .10 * np.sin(TAU * 1760 * t) * (.5 + .5 * np.sin(TAU * .25 * t)) +
         .07 * np.sin(TAU * 2349.5 * t) * (.5 + .5 * np.sin(TAU * .375 * t + 1)))
    d += .3 * noise(8.0, 80, 420, rng)
    return _norm(d)


def s_heartbeat():
    t = _t(1.0)
    v = np.sin(TAU * 58 * t) * np.exp(-t * 24)
    t2 = np.clip(t - .22, 0, None)
    v += .7 * np.sin(TAU * 50 * t2) * np.exp(-t2 * 26) * (t >= .22)
    return _norm(v)


def s_scream(rng):
    """Грубый, хриплый скример: низкий рычащий тон, жёсткая амплитудная модуляция, шум и перегруз."""
    dur = 1.9
    t = _t(dur)
    f = 140 + 430 * np.minimum(1, t / .3) + 80 * np.sin(TAU * 23 * t) + 35 * np.sin(TAU * 57 * t)
    ph = np.cumsum(f) / SR
    v = (2 * (ph % 1) - 1) + .8 * np.sign(np.sin(TAU * ph * 2)) + .5 * np.sign(np.sin(TAU * ph * .5))
    v *= .5 + .5 * np.sign(np.sin(TAU * 71 * t + 1.5 * np.sin(TAU * 9 * t)))     # хрип
    v = _norm(v) + 1.2 * noise(dur, 250, 5500, rng) * (.6 + .4 * np.sin(TAU * 38 * t))
    v += .7 * np.sin(TAU * 52 * t) * np.exp(-t * 1.5)                           # низкий гул
    v = np.tanh(8 * _norm(v))
    v = crush(v, hold=2, levels=20)
    env = np.minimum(1, t * 70) * np.exp(-np.clip(t - .6, 0, None) * 1.3)
    return _norm(v * env)


def s_glitch(rng):
    out = []
    n = 0
    total = int(1.5 * SR)
    while n < total:
        L = int(rng.uniform(.02, .2) * SR)
        k = rng.integers(0, 4)
        if k == 0:
            seg = rng.standard_normal(L) * .8
        elif k == 1:
            f = rng.uniform(80, 1800)
            seg = np.sign(np.sin(TAU * f * np.arange(L) / SR))
        elif k == 2:
            seg = np.zeros(L)
        else:
            seg = np.sin(TAU * rng.uniform(300, 3000) * np.arange(L) / SR) * 1.0
        out.append(seg)
        n += L
    v = crush(np.concatenate(out)[:total], hold=int(rng.integers(2, 6)), levels=6)
    return _norm(v)


def s_alarm():
    seg = []
    for _ in range(8):
        t = _t(.1)
        seg.append(np.sign(np.sin(TAU * 1800 * t)) * .6 + .3 * np.sign(np.sin(TAU * 2700 * t)))
        seg.append(np.zeros(int(.07 * SR)))
    return _norm(np.concatenate(seg))


def s_thud(rng):
    t = _t(.26)
    v = np.sin(TAU * 62 * t) * np.exp(-t * 17) + .6 * fft_filter(rng.standard_normal(len(t)), 40, 300) * np.exp(-t * 20)
    return _norm(v)


def s_swish(rng, dur=.3):
    """Короткий рывок камеры: шорох ткани со свистом, нарастающий и затухающий."""
    t = _t(dur)
    n = rng.standard_normal(len(t))
    lo = fft_filter(n, 220, 1100)
    hi = fft_filter(n, 1400, 5200)
    k = t / dur
    v = _norm(lo * (1 - k) + hi * k)
    env = np.sin(np.pi * np.minimum(1, k * 1.15)) ** 1.6 * (1 - k * .3)
    v = v * env + .45 * np.sin(TAU * 88 * t) * np.exp(-t * 45)
    return _norm(v)


def s_shot(rng):
    """Хлопок игрушечного ружья из тира."""
    t = _t(.28)
    v = fft_filter(rng.standard_normal(len(t)), 250, 7000) * np.exp(-t * 26)
    v += .9 * np.sin(TAU * (130 - 70 * np.minimum(1, t / .12)) * t) * np.exp(-t * 22)
    return _norm(np.tanh(2.2 * _norm(v)))


def s_ding(rng=None):
    """Звон попадания по жестяной мишени."""
    t = _t(.5)
    v = (np.sin(TAU * 1320 * t) + .6 * np.sin(TAU * 1980 * t) + .35 * np.sin(TAU * 2640 * t)) * np.exp(-t * 9)
    return _norm(v * np.minimum(1, t * 400))


def s_whack(rng):
    """Удар молотка по кроту: глухой стук и писк."""
    t = _t(.25)
    v = np.sin(TAU * 110 * t) * np.exp(-t * 28) + .6 * fft_filter(rng.standard_normal(len(t)), 500, 3500) * np.exp(-t * 70)
    v += .35 * np.sin(TAU * (900 + 700 * t / .25) * t) * np.exp(-t * 14)
    return _norm(v)


def s_pop():
    t = _t(.1)
    return np.sin(TAU * (260 + 900 * t / .1) * t) * np.exp(-t * 20) * np.minimum(1, t * 300)


def s_buzz():
    """Штраф: низкий неприятный гудок."""
    t = _t(.32)
    v = np.sign(np.sin(TAU * 98 * t)) * .7 + .4 * np.sign(np.sin(TAU * 147 * t))
    return _norm(v * np.exp(-t * 6) * np.minimum(1, t * 200))


def s_fanfare():
    seg = []
    for f, d in ((523, .1), (659, .1), (784, .1), (1047, .35)):
        t = _t(d)
        seg.append((np.sin(TAU * f * t) + .4 * np.sin(TAU * 2 * f * t)) * np.exp(-t * 4) * np.minimum(1, t * 200))
    return _norm(np.concatenate(seg))


def s_build(rng):
    """«Твой мир» строится: нарастающий шорох, переливающиеся ноты и тёплый аккорд."""
    dur = 3.0
    t = _t(dur)
    sweep = noise(dur, 300, 5000, rng) * (t / dur) ** 1.5 * np.exp(-((t - 1.9) / .9) ** 2 * .0)
    v = sweep * .5
    for k, f in enumerate((392, 494, 587, 740, 988, 1175)):
        t0 = .25 + k * .22
        m = t >= t0
        tt = np.where(m, t - t0, 0)
        v += (np.sin(TAU * f * tt) + .3 * np.sin(TAU * 2 * f * tt)) * np.exp(-tt * 2.2) * m * .35
    chord = sum(np.sin(TAU * f * t) for f in (262, 330, 392, 523)) * np.clip((t - 1.6) / .5, 0, 1) * np.exp(-(t - 1.6) * .9)
    v += chord * .18 * (t > 1.6)
    return _norm(v * np.minimum(1, t * 30) * np.minimum(1, (dur - t) * 6))


def s_chime():
    t = _t(.9)
    v = (np.sin(TAU * 880 * t) + .5 * np.sin(TAU * 1320 * t)) * np.exp(-t * 4.5) * np.minimum(1, t * 300)
    return _norm(v)


def s_tick():
    t = _t(.05)
    return np.sin(TAU * 1400 * t) * np.exp(-t * 110)


def s_pencil(rng):
    """Короткий скрип грифеля по бумаге."""
    dur = .065
    t = _t(dur)
    n = noise(dur, 1600, 7200, rng)
    f = rng.uniform(1900, 3600)
    grit = np.sin(TAU * f * t) * (.55 + .45 * np.sin(TAU * rng.uniform(70, 130) * t))
    env = np.minimum(1.0, t * 600) * np.exp(-t * 32)
    return crush(_norm(n * .82 + grit * .4) * env, hold=2, levels=16)


def s_erase(rng):
    """Мягкое шуршание ластика."""
    dur = .09
    t = _t(dur)
    n = noise(dur, 250, 1600, rng)
    rub = noise(dur, 700, 2200, rng) * np.sin(TAU * rng.uniform(28, 48) * t)
    env = np.minimum(1.0, t * 280) * np.exp(-t * 16)
    return _norm((n * .75 + rub * .45) * env)


def s_clunk(rng):
    t = _t(.3)
    v = np.sin(TAU * 110 * t) * np.exp(-t * 18) + .5 * fft_filter(rng.standard_normal(len(t)), 600, 4000) * np.exp(-t * 35)
    return _norm(v)


# ----------------------------------------------------------------- движок
class Audio:
    LOOPS = ["fountain", "musicbox", "train", "ferris", "wind", "ratchet", "drone", "misc"]

    def __init__(self, song_path):
        self.ok = False
        self.song_path = song_path
        self.listener = (0.0, 0.0, 0.0)
        self.music_vol = .5
        self.muted = False
        try:
            pygame.mixer.init(SR, -16, 2, 512)
            pygame.mixer.set_num_channels(30)
            pygame.mixer.set_reserved(len(self.LOOPS))
        except Exception as e:                       # звук не критичен
            print("audio disabled:", e)
            return
        rng = np.random.default_rng(11)
        S = {}
        S["step0"] = [self._snd(s_step(rng, 0), .55) for _ in range(5)]
        S["step1"] = [self._snd(s_step(rng, 1), .6) for _ in range(5)]
        S["blip"] = [self._snd(s_blip(rng), .6) for _ in range(10)]
        S["creak"] = [self._snd(s_creak(rng), .6)]
        S["door_open"] = [self._snd(s_door_open(rng), .8)]
        S["whistle"] = [self._snd(s_whistle(rng), .55)]
        S["bell"] = [self._snd(s_bell(rng), .5)]
        S["clack"] = [self._snd(s_clack(rng), .5) for _ in range(3)]
        S["heartbeat"] = [self._snd(s_heartbeat(), .9)]
        S["scream"] = [self._snd(s_scream(rng), .9)]
        S["glitch"] = [self._snd(s_glitch(rng), .7)]
        S["alarm"] = [self._snd(s_alarm(), .45)]
        S["thud"] = [self._snd(s_thud(rng), .8)]
        S["tick"] = [self._snd(s_tick(), .5)]
        S["shot"] = [self._snd(s_shot(rng), .7) for _ in range(3)]
        S["ding"] = [self._snd(s_ding(), .5)]
        S["whack"] = [self._snd(s_whack(rng), .8) for _ in range(3)]
        S["pop"] = [self._snd(s_pop(), .45)]
        S["buzz"] = [self._snd(s_buzz(), .5)]
        S["fanfare"] = [self._snd(s_fanfare(), .55)]
        S["swish"] = [self._snd(s_swish(rng, d), .5) for d in (.26, .3, .34, .28)]
        S["clunk"] = [self._snd(s_clunk(rng), .7)]
        S["build"] = [self._snd(s_build(rng), .7)]
        S["chime"] = [self._snd(s_chime(), .5)]
        S["pencil"] = [self._snd(s_pencil(rng), .7) for _ in range(5)]
        S["erase"] = [self._snd(s_erase(rng), .65) for _ in range(4)]
        L = {}
        L["fountain"] = self._snd(s_water(rng), 1.0)
        L["musicbox"] = self._snd(s_musicbox(), 1.0)
        L["train"] = self._snd(s_train(rng), 1.0)
        L["ferris"] = self._snd(s_ferris_creak(rng), 1.0)
        L["wind"] = self._snd(s_wind(rng), 1.0)
        L["ratchet"] = self._snd(s_ratchet(rng), 1.0)
        L["drone"] = self._snd(s_drone(rng), 1.0)
        self.S, self.L = S, L
        self.rng = np.random.default_rng(5)
        self.ch = {}
        self.ok = True

    @staticmethod
    def _snd(x, vol=1.0):
        st = np.stack([x, x], axis=1) * vol
        return pygame.mixer.Sound(buffer=np.ascontiguousarray((np.clip(st, -1, 1) * 32767).astype(np.int16)).tobytes())

    # --- музыка
    def music_start(self):
        if not self.ok or not os.path.exists(self.song_path):
            return
        try:
            pygame.mixer.music.load(self.song_path)
            pygame.mixer.music.set_volume(self.music_vol)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print("music error:", e)

    def music_set(self, v):
        self.music_vol = v
        if self.ok:
            pygame.mixer.music.set_volume(0 if self.muted else v)

    def toggle_mute(self):
        self.muted = not self.muted
        if self.ok:
            pygame.mixer.music.set_volume(0 if self.muted else self.music_vol)
            for c in self.ch.values():
                if self.muted:
                    c.set_volume(0, 0)

    # --- эффекты
    def set_listener(self, x, z, yaw):
        self.listener = (x, z, yaw)

    def pan_for(self, x, z):
        lx, lz, yaw = self.listener
        dx, dz = x - lx, z - lz
        d = math.hypot(dx, dz) + 1e-6
        rx, rz = math.cos(yaw), -math.sin(yaw)
        return (dx * rx + dz * rz) / d, d

    def play(self, name, vol=1.0, pan=0.0, pitch_var=None):
        if not self.ok or self.muted:
            return
        lst = self.S[name]
        snd = lst[int(self.rng.integers(0, len(lst)))]
        ch = None
        for i in range(len(self.LOOPS), pygame.mixer.get_num_channels()):   # только нерезервные каналы
            c = pygame.mixer.Channel(i)
            if not c.get_busy():
                ch = c
                break
        if ch is None:
            return
        ch.play(snd)
        ch.set_volume(min(1, vol * (1 - max(0, pan))), min(1, vol * (1 + min(0, pan))))

    def play_at(self, name, x, z, vol=1.0, falloff=30.0):
        pan, d = self.pan_for(x, z)
        v = vol * max(0.0, 1 - d / falloff) ** 2
        if v > .01:
            self.play(name, v, pan * .8)

    def loop(self, name, vol, pan=0.0):
        if not self.ok:
            return
        ch = self.ch.get(name)
        if ch is None:
            ch = pygame.mixer.Channel(self.LOOPS.index(name))
            self.ch[name] = ch
        if not ch.get_busy():
            ch.play(self.L[name], loops=-1)
        if self.muted:
            vol = 0
        ch.set_volume(min(1, vol * (1 - max(0, pan))), min(1, vol * (1 + min(0, pan))))

    def loop_at(self, name, x, z, vol=1.0, falloff=40.0):
        pan, d = self.pan_for(x, z)
        v = vol * max(0.0, 1 - d / falloff) ** 2
        self.loop(name, v, pan * .8)

    def stop_loop(self, name):
        ch = self.ch.get(name)
        if ch is not None:
            ch.stop()

    def stop_all_loops(self):
        for n in list(self.ch):
            self.stop_loop(n)
