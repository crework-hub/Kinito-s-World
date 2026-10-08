# -*- coding: utf-8 -*-
"""
KINITO PARK  -  3D-парк развлечений в стиле KinitoPET (pygame + OpenGL)

Управление:
  WASD - ходьба      Shift - бег       Мышь - обзор
  ПКМ  - зум         E     - действие (аттракцион / белая дверь / тир / «Твой мир»)
  F2   - размер "пикселей" (PS1-стиль)   M - музыка вкл/выкл   F1 - скрыть интерфейс
  Esc  - выход
"""
import json
import math
import os
import random
import sys
import textwrap

import numpy as np
import pygame

from gfx import *
from audio import Audio
from hideseek import HideSeek, CELL as HS_CELL
import yourworld as YW

# ----------------------------------------------------------------------------
# Настройки
# ----------------------------------------------------------------------------
WIN_W, WIN_H = 640, 480          # окно как в KinitoPET, 4:3
PIX_SCALES = [4, 3, 2]            # внутреннее разрешение = окно / scale
FOG_COL = (0.95, 0.975, 1.0)
SKY_TOP = (0.84, 0.94, 1.0)
C0 = (0.0, -30.0)                 # центр парка
RR = 95.0                         # радиус кольцевой железной дороги
WALK_SPEED, RUN_SPEED = 4.0, 6.8
HS_WALK, HS_RUN = 3.3, 5.2
HERE = os.path.dirname(os.path.abspath(__file__))
SONG = os.path.join(HERE, "song", "my_world.ogg")
FONT_PATH = os.path.join(HERE, "font", "EpilepsySansBold.ttf")

# Рисовалка в начале игры, как MS Paint в KinitoPET. Пять рисунков вешаются дома вместо заготовок.
DRAW_PROMPTS = [
    ("Нарисуй то, что делает тебя счастливым.", "Я запомнил. Это будет висеть у тебя дома."),
    ("А теперь то, от чего тебе грустно.", "Грустную картинку я тоже оставлю. Чтобы не забыть."),
    ("Нарисуй своего лучшего друга.", "Хм. Совсем на меня не похоже. Но я сохраню."),
    ("Нарисуй себя. Я хочу знать, как ты выглядишь.", "Так вот ты какой. Я буду смотреть на это каждый день."),
    ("Последний рисунок: тот, кто стоит у тебя за спиной.", "Я так и думал. Он всегда рядом."),
]
PAINT_COLORS = [
    (0, 0, 0), (128, 128, 128), (128, 0, 0), (128, 128, 0), (0, 128, 0), (0, 128, 128), (0, 0, 128), (128, 0, 128),
    (255, 255, 255), (192, 192, 192), (255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255), (255, 0, 255),
    (255, 128, 64), (255, 128, 128), (128, 64, 0), (0, 64, 128), (64, 64, 64), (255, 128, 0),
]


def player_name():
    """Имя игрока — пользователь Windows, чтобы сохранение было его собственным."""
    raw = os.environ.get("KINITO_USER") or os.environ.get("USERNAME") or os.environ.get("USER") or "player"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw).strip("_")[:40]
    return raw, (safe or "player")


def profile_dir():
    _, safe = player_name()
    return os.path.join(HERE, "saves", safe)


def load_font(size):
    """Единый шрифт игры (папка font); если файла нет - системный."""
    try:
        return pygame.font.Font(FONT_PATH, size)
    except Exception:
        return pygame.font.SysFont("arial,segoeui", size, bold=True)

# цвета Кинито (по референсу: светло-розовая голова, тёмно-розовые жабры, чёрные ноги)
K_HEAD = (0.86, 0.60, 0.93)
K_GILL = (0.92, 0.22, 0.74)


def make_sign_texture():
    surf = pygame.Surface((512, 128), pygame.SRCALPHA)
    surf.fill((86, 30, 158))
    pygame.draw.rect(surf, (255, 214, 40), (0, 0, 512, 128), 8)
    pygame.draw.rect(surf, (230, 40, 70), (12, 12, 488, 104), 4)
    size = 70
    f = load_font(size)
    while f.size("KINITO PARK")[0] > 440 and size > 20:
        size -= 4
        f = load_font(size)
    t1 = f.render("KINITO PARK", True, (0, 0, 0))
    t2 = f.render("KINITO PARK", True, (255, 226, 60))
    r = t2.get_rect(center=(256, 66))
    surf.blit(t1, r.move(4, 4))
    surf.blit(t2, r)
    upload("sign", pygame.image.tobytes(surf, "RGBA", True), 512, 128, mip=False, repeat=False)


def make_label_texture(name, text, bg, fg, border=(255, 214, 40)):
    """Вывеска с текстом (шрифт игры)."""
    surf = pygame.Surface((512, 128), pygame.SRCALPHA)
    surf.fill(bg)
    pygame.draw.rect(surf, border, (0, 0, 512, 128), 8)
    pygame.draw.rect(surf, (255, 255, 255), (14, 14, 484, 100), 3)
    size = 84
    f = load_font(size)
    while f.size(text)[0] > 440 and size > 16:
        size -= 4
        f = load_font(size)
    shadow = f.render(text, True, (0, 0, 0))
    main = f.render(text, True, fg)
    r = main.get_rect(center=(256, 66))
    surf.blit(shadow, r.move(4, 4))
    surf.blit(main, r)
    upload(name, pygame.image.tobytes(surf, "RGBA", True), 512, 128, mip=False, repeat=False)


def make_scare_texture():
    """Скример Кинито из Hide and Seek (пиксельная морда, 177x131 как в оригинале)."""
    s = pygame.Surface((177, 131))
    s.fill((4, 0, 0))
    for side in (-1, 1):
        cx = 88 + side * 62
        for k in range(4):
            pygame.draw.line(s, (130, 6, 24), (cx - side * 8, 50 + k * 14),
                             (cx + side * (30 - k * 2), 6 + k * 20), 3)
            pygame.draw.line(s, (130, 6, 24), (cx + side * (30 - k * 2), 6 + k * 20),
                             (cx + side * (40 - k * 4), 24 + k * 20), 2)
    pygame.draw.ellipse(s, (166, 140, 176), (28, -6, 121, 138))          # бледная вытянутая голова
    pygame.draw.ellipse(s, (0, 0, 0), (38, 24, 34, 54))                  # пустые чёрные глазницы
    pygame.draw.ellipse(s, (0, 0, 0), (105, 20, 34, 54))
    pygame.draw.ellipse(s, (0, 0, 0), (62, 74, 54, 90))                  # огромный рот до низа лица
    for i in range(9):                                                   # мелкие зубы по верхней дуге
        u = -.8 + i * .2
        x = 89 + u * 27
        yt = 119 - 45 * math.sqrt(max(0.0, 1 - u * u))
        pygame.draw.polygon(s, (214, 204, 176), [(x - 3, yt), (x + 3, yt), (x + 2, yt + 7 + (i * 5) % 3 * 2),
                                                 (x - 2, yt + 7 + (i * 5) % 3 * 2)])
    upload("scare", pygame.image.tobytes(s, "RGBA", True), 177, 131, mip=False, repeat=False)


# ----------------------------------------------------------------------------
# Геометрия мира
# ----------------------------------------------------------------------------
COLL = []   # круглые коллайдеры (x, z, r)

FER = dict(x=-38.0, z=0.0, hub=14.0, R=12.5)
CAR = dict(x=34.0, z=2.0, r=8.4, h=0.5)
SWG = dict(x=32.0, z=36.0, H=12.0, L=6.5)
TENT = dict(x=-34.0, z=36.0)
FOUNT = dict(x=0.0, z=22.0)
DOOR = dict(x=-60.0, z=14.0)
SHT = dict(x=-21.0, z=18.0, sx=-13.4)        # тир (стойка игрока sx, стреляем в сторону -x)
MOLE = dict(x=21.0, z=18.0, sx=13.4)         # "Попади по кроту" (бьём в сторону +x)
SHT_ROWS = [(-19.5, 1.55, .42), (-22.0, 2.15, .38), (-24.5, 1.75, .34)]   # плоскость мишеней X, высота, радиус
MOLE_HOLES = [(15.9 + 1.3 * i, 16.6 + 1.4 * j) for j in range(3) for i in range(3)]
GATE_Z = 42.0
CS_STATION = (0.0, -44.0)

HORSES = []   # (radius, alpha0, index)
for _i in range(10):
    HORSES.append((6.4, _i * TAU / 10, len(HORSES)))
for _i in range(6):
    HORSES.append((3.6, _i * TAU / 6 + TAU / 12, len(HORSES)))
SW_N = 12

COASTER = {}


# Длинная открытая трасса: подъём по цепи, спуски, повороты и финальная прямая в шестиугольный тоннель
COASTER_PTS = [(-28, 1.2, -44), (-12, 1.2, -44), (8, 1.2, -44), (28, 1.8, -46), (42, 7, -56), (50, 16, -72),
               (48, 29, -92), (34, 31, -108),                                       # подъём по цепи
               (18, 24, -110), (2, 11, -108), (-12, 6, -108), (-28, 15, -108), (-44, 22, -108), (-56, 16, -108),
               (-60, 13, -106), (-62, 12, -102), (-60, 10, -98), (-56, 9, -96),     # первый разворот
               (-44, 8, -96), (-28, 14, -96), (-12, 18, -96), (4, 10, -96), (14, 6, -96),
               (18, 5.5, -94), (20, 5, -90), (18, 5, -86), (14, 5, -84),            # второй разворот
               (2, 9, -84), (-12, 13, -84), (-28, 9, -84), (-44, 5, -84), (-56, 4, -84),
               (-62, 3.8, -81), (-65, 3.6, -75), (-62, 3.4, -69), (-56, 3.2, -66),  # третий разворот
               (-42, 3.2, -66), (-20, 3.2, -66), (10, 3.2, -66), (36, 3.2, -66)]
CS_START = 14.0                  # положение поезда у платформы (s вдоль трассы)
PORTAL_BACK = 24.0               # стена с шестиугольной дырой стоит за столько метров до конца трассы
TUNNEL_LEN = 18.0


def build_coaster_data():
    COASTER.update(YW.make_track(COASTER_PTS, sigma_m=3.0))
    COASTER["s_wall"] = COASTER["L"] - PORTAL_BACK


def coaster_at(s):
    return YW.track_at(COASTER, s)


def build_floor():
    # пол режем на плитки: туман считается по вершинам, большие квады дают белую кашу
    S, T = 240.0, 8.0
    n = int(2 * S / T)
    glBindTexture(GL_TEXTURE_2D, TEX["checker"])
    glColor3f(1, 1, 1)
    glNormal3f(0, 1, 0)
    glBegin(GL_QUADS)
    for i in range(n):
        for j in range(n):
            x0, z0 = -S + i * T, -S + j * T
            x1, z1 = x0 + T, z0 + T
            glTexCoord2f(x0 / 4, z0 / 4)
            glVertex3f(x0, 0, z0)
            glTexCoord2f(x0 / 4, z1 / 4)
            glVertex3f(x0, 0, z1)
            glTexCoord2f(x1 / 4, z1 / 4)
            glVertex3f(x1, 0, z1)
            glTexCoord2f(x1 / 4, z0 / 4)
            glVertex3f(x1, 0, z0)
    glEnd()


def tree(x, z, s, shade):
    obj("cyl", x, 0, z, .28 * s, 1.6 * s, .28 * s, (.42, .3, .22))
    g = (.30 * shade, .52 * shade, .42 * shade)
    obj("cone", x, 1.2 * s, z, 2.1 * s, 3.0 * s, 2.1 * s, g)
    obj("cone", x, 2.7 * s, z, 1.7 * s, 2.7 * s, 1.7 * s, g)
    obj("cone", x, 4.1 * s, z, 1.15 * s, 2.5 * s, 1.15 * s, g)


def tree_ok(x, z):
    if math.hypot(x - FOUNT["x"], z - FOUNT["z"]) < 9:
        return False
    if math.hypot(x - FER["x"], z - FER["z"]) < 20:
        return False
    if math.hypot(x - CAR["x"], z - CAR["z"]) < 14:
        return False
    if math.hypot(x - SWG["x"], z - SWG["z"]) < 15:
        return False
    if math.hypot(x - TENT["x"], z - TENT["z"]) < 14:
        return False
    if math.hypot(x - DOOR["x"], z - DOOR["z"]) < 8:
        return False
    if math.hypot(x - SHT["x"], z - SHT["z"]) < 14 or math.hypot(x - MOLE["x"], z - MOLE["z"]) < 14:
        return False
    if abs(x) < 10 and -12 < z < 72:
        return False
    if abs(x) < 34 and z > 48:
        return False
    if abs(x) < 20 and 30 < z < 48:
        return False
    for q in COASTER["P"][::16]:
        if abs(x - q[0]) < 5 and abs(z - q[2]) < 5:
            return False
    if abs(x) < 34 and -50 < z < -38:
        return False
    if -72 < x < 46 and -78 < z < -54:           # финальная прямая и стена с шестиугольной дырой
        return False
    return True


def build_trees():
    rng = random.Random(3)
    pts = []
    tries = 0
    while len(pts) < 150 and tries < 3000:
        tries += 1
        a = rng.uniform(0, TAU)
        r = rng.uniform(78, 91)
        x, z = C0[0] + r * math.sin(a), C0[1] + r * math.cos(a)
        if tree_ok(x, z):
            pts.append((x, z))
    tries = 0
    inner = 0
    while inner < 80 and tries < 3000:
        tries += 1
        a = rng.uniform(0, TAU)
        r = rng.uniform(25, 76)
        x, z = C0[0] + r * math.sin(a), C0[1] + r * math.cos(a)
        if tree_ok(x, z):
            pts.append((x, z))
            inner += 1
    for x, z in pts:
        s = rng.uniform(.85, 1.5)
        tree(x, z, s, rng.uniform(.85, 1.15))
        COLL.append((x, z, .55 * s))


def build_gate():
    gz = GATE_Z
    for sx in (-7, 7):
        obj("cyl", sx, 0, gz, 1.1, 7, 1.1, WHITE, "stripes")
        obj("sphere", sx, 7.6, gz, .95, .95, .95, YEL, lit=False)
        COLL.append((sx, gz, 1.3))
    obj("box", 0, 6.9, gz, 16, 2.6, 1.0, WHITE, "sign")
    obj("box", 0, 5.4, gz, 14, .4, .7, PURP)
    for bx in (-14.5, 14.5):
        obj("box", bx, 1.5, gz, 3.4, 3, 3.4, (.97, .93, .85))
        obj("cone", bx, 3.0, gz, 3.2, 2.2, 3.2, WHITE, "stripes")
        obj("box", bx, 1.0, gz + 1.8, 3.4, .3, .3, RED)
        COLL.append((bx, gz, 2.5))


def build_lamps():
    for z in range(58, 8, -10):
        for sx in (-6.5, 6.5):
            obj("cyl", sx, 0, z, .13, 4.2, .13, (.25, .22, .35))
            obj("sphere", sx, 4.55, z, .42, .42, .42, (1, .97, .8), lit=False)
            COLL.append((sx, z, .3))


def build_fountain():
    fx, fz = FOUNT["x"], FOUNT["z"]
    obj("cyl", fx, 0, fz, 3.7, .7, 3.7, WHITE, "stripes")
    obj("cyl", fx, .45, fz, 3.3, .25, 3.3, (.55, .85, 1.0), lit=False)
    obj("cyl", fx, .4, fz, 1.0, 1.9, 1.0, (.95, .9, 1.0), "noise")
    obj("cyl", fx, 1.5, fz, 1.7, .35, 1.7, (.95, .9, 1.0), "noise")
    obj("cyl", fx, 1.8, fz, .5, 1.1, .5, (.95, .9, 1.0), "noise")
    COLL.append((fx, fz, 3.9))


def build_tent():
    x, z = TENT["x"], TENT["z"]
    obj("cyl", x, 0, z, 9, 4.4, 9, WHITE, "stripes")
    obj("cone", x, 4.4, z, 9.8, 5.8, 9.8, WHITE, "stripes")
    obj("cyl", x, 10.0, z, .1, 2.4, .1, (.9, .9, .9))
    obj("cone", x, 11.6, z, .8, 1.0, .1, RED)
    obj("box", x + 4.2, 1.6, z + 7.9, 3.2, 3.2, .4, (.12, .06, .22), ry=-28)
    COLL.append((x, z, 9.4))


def build_station():
    obj("box", -9, .25, 60, 24, .5, 4, (.9, .86, .95), "checker")
    for px in (-19, -9.5, 0):
        obj("cyl", px, 0, 58.8, .16, 3.8, .16, (.3, .25, .45))
        COLL.append((px, 58.8, .3))
    obj("box", -9.5, 3.9, 60, 24, .35, 5, WHITE, "stripes")
    obj("box", 8, 1.8, 56, 6, 3.6, 4.4, (.97, .93, .85))
    obj("cone", 8, 3.6, 56, 4.6, 2.0, 4.6, WHITE, "stripes", ry=45)
    COLL.append((8, 56, 3.6))
    for bx in (-16, 1.5):
        obj("box", bx, .45, 58.7, 2.6, .12, .6, (.55, .38, .25))
        obj("box", bx, .75, 58.45, 2.6, .5, .1, (.55, .38, .25))
    obj("box", -21.5, 2.0, 61.3, 5.0, 1.4, .15, WHITE, "sign")


def build_rails():
    n = 120
    for k in (-.75, .75):
        for i in range(n):
            a0 = TAU * i / n
            a1 = TAU * (i + 1) / n
            p0 = (C0[0] + (RR + k) * math.sin(a0), .32, C0[1] + (RR + k) * math.cos(a0))
            p1 = (C0[0] + (RR + k) * math.sin(a1), .32, C0[1] + (RR + k) * math.cos(a1))
            beam(p0, p1, .16, (.35, .35, .42))
    for i in range(300):
        a = TAU * i / 300
        obj("box", C0[0] + RR * math.sin(a), .1, C0[1] + RR * math.cos(a),
            .5, .18, 2.8, (.4, .28, .2), ry=math.degrees(a))


def build_ferris_static():
    fx, fz, H = FER["x"], FER["z"], FER["hub"]
    for sz in (-2.5, 2.5):
        for sx in (-8.5, 8.5):
            beam((fx + sx, .5, fz + sz), (fx, H, fz + sz), .75, RED)
        yb = 4.5
        k = 1 - yb / H
        beam((fx - 8.5 * k, yb, fz + sz), (fx + 8.5 * k, yb, fz + sz), .45, WHITE)
        yb = 9
        k = 1 - yb / H
        beam((fx - 8.5 * k, yb, fz + sz), (fx + 8.5 * k, yb, fz + sz), .4, BLUE)
    for sx in (-8.5, 8.5):
        beam((fx + sx, .6, fz - 2.5), (fx + sx, .6, fz + 2.5), .7, WHITE)
    obj("box", fx, .5, fz, 21, 1.0, 6.6, BLUE)
    for i in range(11):
        obj("cone", fx - 10 + i * 2, 1.0, fz + 3.4, 1.0, 1.4, 1.0, RED)
        obj("cone", fx - 10 + i * 2, 1.0, fz - 3.4, 1.0, 1.4, 1.0, RED)
    for k in range(-3, 4):
        COLL.append((fx + k * 3, fz, 3.6))
    obj("box", fx, .08, fz + 8.2, 7, .16, 4.5, (.95, .9, .5))


def build_carousel_static():
    cx, cz = CAR["x"], CAR["z"]
    obj("cyl", cx, 0, cz, 8.4, .5, 8.4, WHITE, "stripes")
    obj("cyl", cx, .5, cz, 8.0, .03, 8.0, (1, .92, .6))
    COLL.append((cx, cz, 1.9))


def build_swing_static():
    x, z, H = SWG["x"], SWG["z"], SWG["H"]
    obj("cyl", x, 0, z, 3.2, .6, 3.2, WHITE, "stripes")
    obj("cyl", x, .6, z, .9, H - .6, .9, (.95, .95, 1.0))
    obj("cyl", x, 2, z, 1.05, .6, 1.05, RED)
    obj("cyl", x, 5, z, 1.05, .6, 1.05, BLUE)
    obj("cyl", x, 8, z, 1.05, .6, 1.05, RED)
    COLL.append((x, z, 1.5))
    obj("box", x, .08, z + 13, 6, .16, 3, (.95, .9, .5))


def build_coaster_static():
    sw = COASTER["s_wall"]
    wp, wt = coaster_at(sw)
    # опоры не ставим внутри тоннеля (там рельсы идут на уровне дырки)
    YW.build_track_geom(COASTER, supports=True, coll=COLL,
                        skip=lambda a: wp[0] - 4 < a[0] and abs(a[2] - wp[2]) < 5)
    YW.build_portal(wp, (wt[0], wt[2]), COLL)
    sx, sz = CS_STATION
    obj("box", sx, .3, sz, 26, .6, 6, (.92, .88, .96), "checker")
    for px in (-12, 12):
        for pz in (-2.6, 2.6):
            obj("cyl", sx + px, 0, sz + pz, .2, 4.6, .2, PURP)
    obj("box", sx, 4.8, sz, 27, .4, 7, WHITE, "stripes")
    obj("box", sx, 5.7, sz + 3.3, 16, 1.4, .3, WHITE, "sign")


def build_door():
    """Одинокая белая дверь на краю парка - вход в Hide and Seek."""
    x, z = DOOR["x"], DOOR["z"]
    push(x, 0, z, ry=90)
    df = (.8, .83, .93)
    obj("box", -1.0, 1.75, 0, .26, 3.5, .45, df)
    obj("box", 1.0, 1.75, 0, .26, 3.5, .45, df)
    obj("box", 0, 3.6, 0, 2.52, .28, .45, df)
    obj("box", 0, 1.7, -.15, 1.8, 3.4, .04, (0, 0, 0), lit=False)       # чёрная пустота за дверью
    obj("box", 0, .04, 0, 2.5, .08, .9, WHITE)
    pop()
    COLL.append((x, z, 1.25))


def _bulbs(x0, z0, y, dz, n):
    for i in range(n):
        obj("sphere", x0, y, z0 + i * dz, .1, .1, .1, (1.0, .95, .6), lit=False)


def build_shoot_static():
    """Тир: прилавок, три ряда рельсов с мишенями за ним, полосатая крыша и вывеска."""
    bz = SHT["z"]
    obj("box", -21.0, .06, bz, 13.2, .12, 10.4, (.9, .86, .95), "checker")
    obj("box", -27.2, 2.0, bz, .4, 4.0, 10.2, (.2, .12, .35))
    for s in (-1, 1):
        obj("box", -21.0, 1.95, bz + s * 5.0, 12.4, 3.9, .3, WHITE, "stripes")
    obj("box", -15.2, .55, bz, .9, 1.1, 10.0, RED, "stripes")
    obj("box", -15.2, 1.15, bz, 1.3, .12, 10.4, PURP)
    obj("box", -21.0, 4.0, bz, 13.2, .3, 10.8, WHITE, "stripes")
    obj("box", -14.5, 3.6, bz, .3, .8, 10.8, RED)
    obj("box", -14.3, 4.95, bz, .4, 1.3, 5.6, WHITE, "sign_tir")
    for s in (-1, 1):
        obj("cyl", -14.6, 0, bz + s * 5.0, .14, 4.0, .14, PURP)
    _bulbs(-14.2, bz - 4.8, 3.55, .96, 11)
    for z in np.arange(bz - 4.8, bz + 4.81, 1.0):
        COLL.append((-15.2, float(z), .65))
    for x in np.arange(-16.0, -27.1, -1.5):
        for s in (-1, 1):
            COLL.append((float(x), bz + s * 5.0, .5))
    for z in np.arange(bz - 4.8, bz + 4.81, 1.5):
        COLL.append((-27.0, float(z), .5))


def build_mole_static():
    """Попади по кроту: стол с девятью норками, крыша, вывеска."""
    bz = MOLE["z"]
    obj("box", 20.8, .06, bz, 15.0, .12, 10.4, (.9, .86, .95), "checker")
    obj("box", 27.6, 2.0, bz, .4, 4.0, 10.2, (.2, .12, .35))
    for s in (-1, 1):
        obj("box", 21.0, 1.9, bz + s * 5.0, 13.4, 3.8, .3, WHITE, "stripes")
    obj("box", 17.2, .5, bz, 5.4, 1.0, 4.8, RED, "stripes")
    obj("box", 17.2, .95, bz, 5.8, .1, 5.2, (.62, .38, .2))
    for hx, hz in MOLE_HOLES:
        obj("cyl", hx, .995, hz, .5, .02, .5, PURP)
        obj("cyl", hx, 1.0, hz, .4, .012, .4, (0, 0, 0), lit=False)
    obj("box", 20.5, 4.0, bz, 14.6, .3, 10.8, WHITE, "stripes")
    obj("box", 13.5, 3.6, bz, .3, .8, 10.8, PURP)
    obj("box", 13.3, 4.95, bz, .4, 1.3, 8.0, WHITE, "sign_mole")
    for s in (-1, 1):
        obj("cyl", 13.8, 0, bz + s * 5.0, .14, 4.0, .14, RED)
    _bulbs(13.2, bz - 4.8, 3.55, .96, 11)
    for z in np.arange(bz - 2.6, bz + 2.61, 1.0):
        COLL.append((14.7, float(z), .6))
    for x in np.arange(14.5, 27.6, 1.5):
        for s in (-1, 1):
            COLL.append((float(x), bz + s * 5.0, .5))
    for z in np.arange(bz - 4.8, bz + 4.81, 1.5):
        COLL.append((27.4, float(z), .5))


STATIC = [0]


def build_static():
    l = glGenLists(1)
    glNewList(l, GL_COMPILE)
    build_floor()
    build_trees()
    build_gate()
    build_lamps()
    build_fountain()
    build_tent()
    build_station()
    build_rails()
    build_ferris_static()
    build_carousel_static()
    build_swing_static()
    build_coaster_static()
    build_door()
    build_shoot_static()
    build_mole_static()
    glEndList()
    STATIC[0] = l


# ----------------------------------------------------------------------------
# Динамические объекты
# ----------------------------------------------------------------------------
GONDOLA_COLS = [RED, BLUE, WHITE, YEL, RED, BLUE, WHITE, PURP]


def ferris_vert(ang, i):
    a = ang + i * TAU / 8
    return FER["x"] + FER["R"] * math.cos(a), FER["hub"] + FER["R"] * math.sin(a)


def draw_ferris(ang, ridden):
    fx, fz, H, R = FER["x"], FER["z"], FER["hub"], FER["R"]
    n = 8
    outer = [ferris_vert(ang, i) for i in range(n)]
    ri = R * .5
    inner = [(fx + ri * math.cos(ang + i * TAU / n + TAU / 16),
              H + ri * math.sin(ang + i * TAU / n + TAU / 16)) for i in range(n)]
    for zo in (-1.35, 1.35):
        if ridden >= 0 and zo > 0:      # передний обод не закрывает обзор пассажиру
            continue
        z = fz + zo
        for i in range(n):
            a, b = outer[i], outer[(i + 1) % n]
            beam((a[0], a[1], z), (b[0], b[1], z), .5, RED if i % 2 == 0 else BLUE)
            c, d = inner[i], inner[(i + 1) % n]
            beam((c[0], c[1], z), (d[0], d[1], z), .32, WHITE if i % 2 == 0 else BLUE)
            beam((fx, H, z), (a[0], a[1], z), .24, WHITE)
            beam((c[0], c[1], z), (a[0], a[1], z), .2, RED)
            beam((c[0], c[1], z), (b[0], b[1], z), .2, RED)
    for i in range(n):
        a = outer[i]
        if ridden == i:
            continue
        beam((a[0], a[1], fz - 1.35), (a[0], a[1], fz + 1.35), .34, WHITE)
    obj("cyl", fx, H, fz - 2.9, 1.1, 5.8, 1.1, RED, rx=90)
    for zo in (-1.5, 1.5):
        obj("sphere", fx, H, fz + zo, 1.5, 1.5, 1.5, BLUE)
    obj("sphere", fx, H, fz - 2.9, .9, .9, .9, YEL)
    obj("sphere", fx, H, fz + 2.9, .9, .9, .9, YEL)
    for i in range(n):
        vx, vy = outer[i]
        col = GONDOLA_COLS[i]
        beam((vx, vy, fz - 1.35), (vx - .7, vy - .75, fz - .95), .14, WHITE)
        beam((vx, vy, fz - 1.35), (vx + .7, vy - .75, fz - .95), .14, WHITE)
        if ridden != i:
            beam((vx, vy, fz + 1.35), (vx - .7, vy - .75, fz + .95), .14, WHITE)
            beam((vx, vy, fz + 1.35), (vx + .7, vy - .75, fz + .95), .14, WHITE)
        if ridden == i:
            obj("box", vx, vy - 1.95, fz, 2.0, .12, 2.1, col)
            continue
        obj("box", vx, vy - 1.4, fz, 2.0, 1.2, 2.1, col)
        obj("box", vx, vy - 1.35, fz, 2.05, .5, 2.15, (.7, .88, 1.0), lit=False)
        obj("box", vx, vy - .7, fz, 2.3, .16, 2.4, WHITE)
        obj("cone", vx, vy - .56, fz, 1.1, .5, 1.1, col)


def horse(col):
    obj("box", 0, 1.35, 0, 1.5, .66, .5, col, "noise")
    obj("box", .78, 1.9, 0, .34, .9, .36, col, "noise", rz=-25)
    obj("box", 1.2, 2.3, 0, .66, .3, .3, col, "noise", rz=-22)
    obj("box", .62, 2.0, 0, .12, .95, .22, PURP, rz=-25)
    obj("box", -.85, 1.3, 0, .12, .8, .16, PURP, rz=22)
    obj("box", .08, 1.72, 0, .55, .08, .54, RED)
    for lx, lz, rz in ((.6, .17, -14), (.6, -.17, -14), (-.6, .17, 14), (-.6, -.17, 14)):
        obj("box", lx, .6, lz, .15, 1.15, .15, col, "noise", rz=rz)


def draw_carousel(phi, t):
    cx, cz, h = CAR["x"], CAR["z"], CAR["h"]
    push(cx, 0, cz, ry=-math.degrees(phi))
    obj("cyl", 0, h, 0, 1.8, 6.0, 1.8, (.78, .6, .92), "stripes")
    obj("cyl", 0, h + .1, 0, 2.1, .5, 2.1, YEL)
    obj("cyl", 0, 6.0, 0, 9.8, .7, 9.8, WHITE, "stripes")
    obj("cone", 0, 6.7, 0, 9.8, 3.4, 9.8, WHITE, "stripes")
    obj("cyl", 0, 10.0, 0, .12, 1.4, .12, YEL)
    obj("sphere", 0, 11.5, 0, .4, .4, .4, YEL, lit=False)
    for i in range(16):
        a = i * TAU / 16
        x, z = 9.6 * math.cos(a), 9.6 * math.sin(a)
        obj("cone", x, 6.7, z, .55, 1.5, .55, YEL if i % 2 == 0 else PURP)
        obj("sphere", x, 5.8, z, .22, .22, .22, (1, .95, .6), lit=False)
    for r, a0, j in HORSES:
        x, z = r * math.cos(a0), r * math.sin(a0)
        bob = .38 * math.sin(t * 1.8 + j * math.pi)
        obj("cyl", x, h, z, .07, 5.5, .07, (.95, .8, .3))
        push(x, h + .45 + bob, z, ry=model_yaw_deg(-math.sin(a0), math.cos(a0)))
        horse((.97, .97, 1.0))
        pop()
    pop()


def draw_swings(ang, tilt, ridden=-1):
    x, z, H, L = SWG["x"], SWG["z"], SWG["H"], SWG["L"]
    push(x, H, z, ry=-math.degrees(ang))
    obj("cyl", 0, -.8, 0, 5.6, .8, 5.6, WHITE, "stripes")
    obj("cone", 0, 0, 0, 5.6, 2.4, 5.6, WHITE, "stripes")
    obj("sphere", 0, 2.4, 0, .35, .35, .35, YEL, lit=False)
    for i in range(SW_N):
        a = i * TAU / SW_N
        ca, sa = math.cos(a), math.sin(a)
        r = 5.0 + L * math.sin(tilt)
        sy = -.8 - L * math.cos(tilt)
        for k in ((-.4, .4) if ridden != i else ()):
            ox, oz = -sa * k, ca * k
            beam((5.0 * ca + ox, -.8, 5.0 * sa + oz), (r * ca + ox, sy + .9, r * sa + oz), .06, (.8, .8, .9))
        push(r * ca, sy, r * sa, ry=model_yaw_deg(-sa, ca))
        obj("box", 0, .0, 0, .9, .14, .9, RED if i % 2 else BLUE)
        obj("box", -.4, .5, 0, .1, .8, .9, RED if i % 2 else BLUE)
        pop()
    pop()


def draw_balloons(t):
    spots = [(-5, 48), (5, 48), (-10, 40), (10, 40), (-3, 30), (3, 30), (26, 10), (42, 12),
             (-28, 14), (-46, 20), (20, 44), (-20, 46)]
    cols = [RED, BLUE, YEL, WHITE, PURP, (1.0, .45, .75)]
    for i, (x, z) in enumerate(spots):
        h = 3.5 + .5 * math.sin(t * .9 + i)
        beam((x, .1, z), (x + .15 * math.sin(t + i), h, z), .02, (.8, .8, .8))
        obj("sphere", x + .15 * math.sin(t + i), h + .55, z, .5, .62, .5, cols[i % 6], lit=False)


def draw_fountain_water(t):
    fx, fz = FOUNT["x"], FOUNT["z"]
    for k in range(20):
        a = k * TAU / 20
        tt = (t * .75 + k / 20) % 1
        r = 2.6 * tt
        y = 2.3 + 2.2 * 4 * tt * (1 - tt) - 1.7 * tt
        obj("box", fx + r * math.cos(a), y, fz + r * math.sin(a), .15, .15, .15, (.7, .92, 1), lit=False)
    for k in range(8):
        tt = (t * 1.1 + k / 8) % 1
        y = 2.6 + 3.2 * 4 * tt * (1 - tt)
        obj("box", fx + .1 * math.sin(k * 3), y, fz + .1 * math.cos(k * 3), .2, .2, .2, WHITE, lit=False)


def draw_door(open_t):
    """Створка белой двери: открывается внутрь, в темноту."""
    x, z = DOOR["x"], DOOR["z"]
    push(x, 0, z, ry=90)
    push(-.9, 0, 0, ry=open_t * 108)
    obj("box", .9, 1.7, 0, 1.8, 3.4, .1, WHITE)
    obj("box", .9, 2.55, .06, 1.35, 1.1, .03, (.9, .93, 1.0))
    obj("box", .9, 1.0, .06, 1.35, 1.2, .03, (.9, .93, 1.0))
    obj("sphere", 1.55, 1.65, .12, .08, .08, .08, (.92, .82, .4))
    obj("sphere", 1.55, 1.65, -.12, .08, .08, .08, (.92, .82, .4))
    pop()
    pop()


def train_pos(th):
    return C0[0] + RR * math.sin(th), C0[1] + RR * math.cos(th)


def train_unit(k, ridden):
    if ridden:
        obj("box", 0, .7, 0, 5, .15, 2.2, (.4, .4, .5))
        obj("box", 0, 2.75, 0, 5.1, .2, 2.3, WHITE)
        for px in (-2.4, 2.4):
            for pz in (-1.05, 1.05):
                obj("box", px, 1.7, pz, .12, 2.1, .12, RED)
        obj("box", -1.0, 1.0, .7, 1.8, .25, .5, (.5, .3, .2))
        obj("box", -1.0, 1.0, -.7, 1.8, .25, .5, (.5, .3, .2))
        return
    obj("box", 0, .55, 0, 4.6, .45, 1.6, (.18, .18, .22))
    for wx in (-1.6, 1.6):
        obj("cyl", wx, .12, 1.0, .35, .1, .35, (.15, .15, .15), rx=90)
        obj("cyl", wx, .12, -1.1, .35, .1, .35, (.15, .15, .15), rx=90)
    if k == 0:
        obj("box", -.6, 1.75, 0, 3.4, 1.8, 2.2, BLUE)
        obj("box", 1.5, 1.45, 0, 2.2, 1.2, 2.0, BLUE)
        obj("box", 1.5, 2.1, 0, 2.3, .12, 2.1, YEL)
        obj("cyl", 1.8, 2.1, 0, .35, 1.3, .35, YEL)
        obj("cone", 1.8, 3.4, 0, .6, .5, .6, (.2, .2, .25))
        obj("sphere", 2.6, 1.5, 0, .3, .3, .3, (1, 1, .8), lit=False)
        obj("box", -.9, 2.8, 0, 2.6, .2, 2.4, WHITE)
        obj("box", -.9, 2.1, 0, 1.8, .7, 2.25, (.7, .88, 1), lit=False)
        return
    obj("box", 0, 1.75, 0, 5.0, 1.8, 2.2, RED)
    obj("box", 0, 1.1, 0, 5.05, .3, 2.25, WHITE)
    obj("box", 0, 2.85, 0, 5.1, .22, 2.3, WHITE)
    for wx in (-1.6, 0, 1.6):
        obj("box", wx, 2.1, 0, .9, .7, 2.28, (.7, .88, 1), lit=False)


def draw_cart_train(s, ridden=False, T=None):
    cols = [RED, YEL, PURP]
    for k in range(3):
        pos, t = YW.track_at(T or COASTER, s - k * 3.1)
        push(pos[0], pos[1], pos[2], ry=model_yaw_deg(t[0], t[2]), rz=math.degrees(math.asin(clamp(t[1], -1, 1))))
        if ridden and k == 0:
            obj("box", 0, .25, 0, 2.6, .3, 1.7, cols[k])
            obj("box", -1.2, .8, 0, .3, 1.0, 1.7, WHITE)
            pop()
            continue
        obj("box", 0, .5, 0, 2.6, .7, 1.7, cols[k])
        obj("box", -.9, .95, 0, .3, .8, 1.7, WHITE)
        obj("box", 1.25, .6, 0, .3, .4, 1.7, WHITE)
        obj("box", 0, .1, 0, 1.9, .2, 1.3, (.2, .2, .25))
        pop()


def draw_hand(x, y, z, side, t):
    """Белая парящая перчатка Кинито с пятью пальцами."""
    push(x, y + .05 * math.sin(t * 2 + side), z)
    obj("box", 0, 0, 0, .14, .17, .12, WHITE)
    for i in range(4):
        obj("box", .0, .13, (i - 1.5) * .032, .04, .1, .03, WHITE)
    obj("box", 0, .0, side * -.1, .04, .1, .04, WHITE, rx=side * 40)
    pop()


def spike(a, b, r, col):
    """Заострённый шип (конус) от точки a к точке b - жабры Кинито."""
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    if L < 1e-6:
        return
    glPushMatrix()
    glTranslatef(a[0], a[1], a[2])
    s = math.hypot(dx, dz)
    if s > 1e-6:
        glRotatef(math.degrees(math.atan2(s, dy)), dz / s, 0, -dx / s)
    elif dy < 0:
        glRotatef(180, 1, 0, 0)
    glScalef(r, L, r)
    glColor3f(*col)
    glBindTexture(GL_TEXTURE_2D, TEX["white"])
    glCallList(LISTS["cone"])
    glPopMatrix()


def draw_kinito(x, z, yaw_deg, t, moving, scale=1.0):
    """Кинито по референсу: сиреневая круглая голова с огромными сонными глазами (веки до половины),
    по три острых розовых жабры с каждой стороны, очень длинные тонкие чёрные ноги и
    большие плоские чёрные ступни, развёрнутые наружу. Рук нет."""
    ph = t * 6.5 if moving else 0.0
    sw = math.sin(ph) * 24 if moving else 0.0
    bob = abs(math.sin(ph)) * .045 if moving else .012 * math.sin(t * 1.6)
    LEG = (.1, .06, .16)
    LID = (K_HEAD[0] * .93, K_HEAD[1] * .86, K_HEAD[2] * .96)
    glPushMatrix()
    glTranslatef(x, 0, z)
    glRotatef(yaw_deg, 0, 1, 0)
    glScalef(scale, scale, scale)
    hip = 1.34 + bob
    for side in (-1, 1):                                  # длинные тонкие ноги с лёгким изгибом
        k = sw * side
        push(0, hip, side * .11, rz=k, rx=-5 * side)
        obj("box", 0, -.34, 0, .105, .68, .095, LEG)
        push(0, -.68, 0, rz=-abs(k) * .8 - 3, rx=10 * side)
        obj("box", 0, -.33, 0, .095, .68, .09, LEG)
        push(0, -.66, 0, rz=-(k - abs(k) * .8 - 3) * 1.0, rx=-5 * side)   # ступня остаётся горизонтальной
        push(.12, .03, side * .03, ry=-side * 24)
        obj("box", 0, 0, 0, .46, .055, .21, LEG)            # большая плоская ступня
        obj("box", .26, 0, 0, .1, .05, .12, LEG)            # носок-клин
        pop()
        pop()
        pop()
        pop()
    hy = hip + .39
    push(0, hy, 0, rz=1.8 * math.sin(t * 1.3))
    obj("sphere", 0, 0, 0, .46, .43, .5, K_HEAD)            # голова
    ph_b = t % 4.3
    blink = 1.0 if ph_b < .12 else 0.0
    for side in (-1, 1):
        ez = side * .27
        obj("sphere", .35, .05, ez, .075, .085, .105, WHITE, lit=False)                 # белок
        obj("sphere", .41, .04 - .01 * blink, ez - side * .012, .022, .04, .036, (0, 0, 0), lit=False)   # зрачок
        obj("sphere", .43, .06, ez - side * .02, .01, .014, .014, WHITE, lit=False)    # блик
        obj("sphere", .365, .05 + .08 - .075 * blink, ez, .085, .045 + .045 * blink, .12, LID, rx=side * 7)   # тяжёлое веко
        for k, (ang, ln, yy) in enumerate(((66, .62, .2), (10, .6, .02), (-22, .5, -.13))):
            a = math.radians(ang + 5 * math.sin(t * 2.2 + k * 1.7 + side))
            b = (.0, yy, side * .43)
            tip = (-.12, yy + math.sin(a) * ln, side * (.43 + math.cos(a) * ln))
            spike(b, tip, .05, K_GILL)
    pop()
    glPopMatrix()


def draw_monster(x, z, yaw_deg, t, moving, jaw=0.0):
    """Кинито из Hide and Seek: крупная бледная голова на ходулях, пустые чёрные глазницы,
    длинный чёрный рот без зубов, рваные жабры и длинные руки, свисающие вниз.
    Движется рывками, как покадровая анимация."""
    tq = math.floor(t * 11) / 11.0                      # покадровая «дёрганая» анимация
    ph = tq * 6.0 if moving else 0.0
    sw = math.sin(ph) * 40 if moving else 0.0
    bob = abs(math.sin(ph)) * .09 if moving else .025 * math.sin(tq * 2)
    tw = 9 * math.sin(tq * 31) if math.sin(tq * 2.3) > .55 else 0.0
    jw = clamp(jaw * .8 + (.12 if math.sin(tq * 7) > .3 else 0.0), 0.0, 1.0)
    SKIN = (.66, .56, .7)
    BLOOD = (.42, .03, .1)
    CLAW = (.82, .8, .84)
    glPushMatrix()
    glTranslatef(x, 0, z)
    glRotatef(yaw_deg + tw, 0, 1, 0)
    glScalef(1.12, 1.12, 1.12)
    for side in (-1, 1):                                  # паучьи ходули
        k = sw * side
        push(-.1, 1.78 + bob, side * .38, rz=k)
        obj("cyl", 0, -.95, 0, .035, .95, .035, BLACK)
        push(0, -.95, 0, rz=-abs(k) * .9 - 18)
        obj("cyl", 0, -.85, 0, .028, .85, .028, BLACK)
        obj("box", .2, -.85, 0, .5, .035, .09, BLACK)
        for i in (-1, 0, 1):
            obj("box", .45, -.85, i * .05, .16, .025, .02, CLAW, ry=i * 20)
        pop()
        pop()
    hy = 2.2 + bob
    shake = .018 * math.sin(t * 70) * jw
    push(0, hy, shake, rz=-9 + 7 * math.sin(tq * 1.7))
    obj("sphere", 0, 0, 0, .5, .58, .47, SKIN)             # вытянутая голова
    obj("sphere", -.12, .2, 0, .4, .5, .4, (.5, .4, .56))  # затылок темнее
    for side in (-1, 1):
        big = 1.2 if side < 0 else 1.0
        obj("sphere", .35, .12, side * .2, .13 * big, .24 * big, .15 * big, (0, 0, 0), lit=False)   # пустая глазница
        for k in range(4):                                # рваные жабры
            a = math.radians(70 - k * 24 + 7 * math.sin(tq * 8 + k * 1.7 + side))
            b = (-.04, .22 - k * .1, side * .42)
            p1 = (b[0] - .08, b[1] + math.sin(a) * .36, b[2] + side * math.cos(a) * .36)
            a2 = a + math.radians(20 + 12 * math.sin(tq * 5 + k))
            p2 = (p1[0] - .1, p1[1] + math.sin(a2) * .4, p1[2] + side * math.cos(a2) * .4)
            beam(b, p1, .06, BLOOD)
            beam(p1, p2, .035, BLOOD)
    # вытянутая вниз челюсть и огромный раззявленный рот (как на референсе): чёрная пасть
    # до самого низа лица, сверху - ряд мелких тупых зубов
    obj("sphere", .02, -.42, 0, .34, .44, .32, SKIN)
    cy, sy, sz = -.55, .36 + .14 * jw, .25 + .03 * jw
    obj("sphere", .27, cy, 0, .13, sy, sz, (0, 0, 0), lit=False)
    for i in range(9):
        u = -.8 + i * .2
        zz = u * sz
        yt = cy + sy * math.sqrt(max(0.0, 1 - u * u)) - .02
        tx = .27 + .13 * math.sqrt(max(0.0, 1 - u * u * .64)) * .9
        th = .06 + .035 * ((i * 5) % 3)
        obj("box", tx, yt - th / 2, zz, .03, th, .036, (.84, .8, .7))
    pop()
    for side in (-1, 1):                                  # длинные руки свисают вниз
        a = math.sin(ph + (0 if side > 0 else math.pi)) * .2 if moving else .03 * math.sin(tq * 2 + side)
        sh = (0, 1.62 + bob, side * .3)
        el = (.04 + a * .6, 1.08, side * .52)
        hw = (.08 + a, .56 + bob * .5, side * .54)
        beam(sh, el, .05, BLACK)
        beam(el, hw, .04, BLACK)
        obj("box", hw[0], hw[1], hw[2], .09, .12, .14, CLAW)
        for i in range(4):                                # длинные пальцы-когти вниз
            curl = 5 * math.sin(tq * 5 + i + side)
            obj("box", hw[0] + .02 * math.sin(tq * 3 + i), hw[1] - .27, hw[2] + (i - 1.5) * .036,
                .022, .46, .022, CLAW, rz=curl)
    glPopMatrix()


# ----------------------------------------------------------------------------
# Игра
# ----------------------------------------------------------------------------
KINITO_LINES = [
    "Привет! Добро пожаловать в Парк Кинито!",
    "Давай покатаемся на всём! Только горки оставим напоследок.",
    "Колесо обозрения - моё любимое!",
    "Видел карусель? Лошадки такие милые!",
    "Я так рад, что ты здесь... Не уходи, ладно?",
    "Всё здесь сделано специально для тебя.",
]

PROJ_BIAS = np.array([[.5, 0, 0, .5], [0, .5, 0, .5], [0, 0, .5, .5], [0, 0, 0, 1]], float)


def look_m(eye, f, up=(0.0, 1.0, 0.0)):
    f = np.asarray(f, float)
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    M = np.eye(4)
    M[0, :3], M[1, :3], M[2, :3] = s, u, -f
    T = np.eye(4)
    T[:3, 3] = -np.asarray(eye, float)
    return M @ T


def persp_m(fovy, aspect, n, f):
    t = 1.0 / math.tan(math.radians(fovy) / 2)
    P = np.zeros((4, 4))
    P[0, 0], P[1, 1] = t / aspect, t
    P[2, 2], P[2, 3] = (f + n) / (n - f), 2 * f * n / (n - f)
    P[3, 2] = -1.0
    return P


KINITO_TALK = [
    "Привет! Я Кинито. Давай дружить!",
    "Ты уже катался на колесе обозрения?",
    "Горки - самое весёлое! Но оставь их напоследок.",
    "Не уходи далеко, ладно?",
    "Мне нравится, когда ты рядом.",
    "Видел белую дверь? За ней ждёт игра...",
    "Хочешь секрет? Я люблю карусель.",
    "Погода сегодня просто чудесная!",
    "Ты ведь будешь со мной играть?",
    "Этот парк только для нас двоих.",
]

HELP_FONTS = "segoeui,arial,tahoma,dejavusans"
MONO_FONTS = "couriernew,consolas,dejavusansmono,lucidaconsole,monospace"


class Game:
    def __init__(self, args):
        pygame.init()
        self.shot = None
        self.shot_frames = 40
        self.start = None
        if "--shot" in args:
            self.shot = args[args.index("--shot") + 1]
        if "--frames" in args:
            self.shot_frames = int(args[args.index("--frames") + 1])
        if "--at" in args:
            self.start = [float(v) for v in args[args.index("--at") + 1].split(",")]
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        flags = pygame.DOUBLEBUF | pygame.OPENGL
        try:
            self.screen = pygame.display.set_mode((WIN_W, WIN_H), flags, vsync=1)
        except Exception:
            self.screen = pygame.display.set_mode((WIN_W, WIN_H), flags)
        pygame.display.set_caption("KINITO PARK")
        self.clock = pygame.time.Clock()
        self.scale_i = 1
        self.RW, self.RH = WIN_W // PIX_SCALES[1], WIN_H // PIX_SCALES[1]

        self.setup_gl()
        gen_textures()
        make_sign_texture()
        make_label_texture("sign_tir", "ТИР", (200, 30, 70), (255, 240, 120))
        make_label_texture("sign_mole", "ПОПАДИ ПО КРОТУ!", (86, 30, 158), (255, 226, 60))
        YW.make_textures()
        make_scare_texture()
        build_primitives()
        build_coaster_data()
        build_static()
        self.make_fb_texture()
        self.make_overlay_textures()
        self.fonts = {}
        self.text_cache = {}
        self.audio = Audio(SONG)

        # состояние
        self.mode = "park"           # park | hs_intro | hs | hs_scare | hs_glitch
        self.t = 0.0
        self.fov = 72.0
        self.fov_t = 72.0
        self.px, self.pz = -6.0, 61.0
        self.yaw, self.pitch = 0.0, -0.02
        self.roll = 0.0
        self.vx = self.vz = 0.0
        self.gy = 0.0
        self.walk_ph = 0.0
        self.step_idx = 0
        if self.start:
            self.px, self.pz = self.start[0], self.start[1]
            self.yaw = math.radians(self.start[2])
            self.pitch = math.radians(self.start[3]) if len(self.start) > 3 else 0.0
        self.fer_ang = 0.3
        self.car_phi = 0.0
        self.sw_ang = 0.0
        self.sw_tilt = .6
        self.train_th = 0.0
        self.train_wait = 16.0
        self.cs = CS_START
        self.cs_yaw = self.cs_pitch = self.cs_roll = 0.0
        self.last_clack = 0
        self.ride = None
        self.visited = set()
        if self.start:
            self.kx, self.kz = self.px + 2.0, self.pz + 2.0
            if "--nok" in args:                       # тест: Кинито не мешает в кадре
                self.kx, self.kz = 0.0, 55.0
        else:
            self.kx, self.kz = -2.0, 50.0                 # ждёт у входа в парк
        self.kyaw = 0.0
        self.kmoving = False
        self.k_met = False          # уже поздоровался с игроком
        self.k_talk = 0.0           # >0: стоит и разговаривает
        self.k_target = None        # куда сейчас идёт (бродит по парку)
        self.k_timer = 0.0
        self.k_stuck = 0.0
        self.talk_i = 0
        self.talk_order = list(range(len(KINITO_TALK)))
        random.shuffle(self.talk_order)
        # мини-игры: тир и "Попади по кроту"
        self.mg = None
        self.best = {"shoot": 0, "mole": 0}
        self.init_targets()
        self.moles = [dict(s=0, t=0.0, h=0.0, h0=0.0, kind="n", life=1.0) for _ in MOLE_HOLES]
        self.mole_next = 2.0
        # «Твой мир»: пространство за шестиугольной дырой; зависит от ответов на вопросы Кинито в начале игры
        self.world = None
        self.inw = False            # игрок сейчас в «Твоём мире»
        self.quiz = None            # опрос и рисовалка в начале: dict(phase, step, season, food)
        self.paint = None
        self.answers = None         # (сезон, еда)
        self.wflash = 0.0           # белая вспышка
        self.wtrans = None          # возврат в парк: dict(t, to, done)
        self.flash_hold = False
        self.park_t0 = 0.0
        self.spot_n = {}
        self.bub = None
        self.bub_dims = None
        self.next_line = 7.0
        self.line_i = 1
        self.door_open = 0.0
        self.seq = None
        self.door_hint = False
        self.fade = 0.0
        self.show_hud = True
        self.mv = self.pj = self.vp = None
        self.cam_yaw_val = 0.0
        # hide and seek
        self.hs = None
        self.view_yaw = self.view_pitch = 0.0      # инерционная камера (Hide and Seek)
        self.turn_w = self.turn_p = 0.0            # скорость поворота (для размытия)
        self.bob_amp = 0.0                         # амплитуда head bobbing в прятках
        self.swish_cd = 0.0
        self.fl_yaw = self.fl_pitch = 0.0          # направление фонаря (отстаёт от взгляда)
        self.hs_t = 0.0
        self.hs_light = 1.0
        self.fl_state = 0
        self.fl_timer = 9.0
        self.fl_dur = 0.0
        self.fl_black = False
        self.intro_t = 0.0
        self.scare_t = 0.0
        self.glitch_t = 0.0
        self.beat_t = 0.0
        self.kstep_t = 0.0
        self.glitching = False

        self.audio.music_start()
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()
        if self.shot:
            self.t = 100.0
            self.bub = None
        if "--ride" in args:
            self.board(args[args.index("--ride") + 1])
        if "--hs" in args or "--scare" in args or "--glitch" in args:
            self.start_hs()
            self.mode = "hs"
            self.fade = 0.0
            if "--monster" in args:                # тест: монстр замер перед игроком
                self.mon_test = float(args[args.index("--monster") + 1])
            if "--scare" in args:
                self.mode = "hs_scare"
            if "--glitch" in args:
                self.mode = "hs_glitch"
        if "--say" in args:
            self.say(args[args.index("--say") + 1])
            self.bub["shown"] = 999.0
        if "--mg" in args:                                 # тест: сразу начать мини-игру (shoot | mole)
            self.start_mg(args[args.index("--mg") + 1])
            self.bub = None
        self.apply_saved_drawings()                        # чужие текстуры не трогаем, если сохранения нет
        if "--world" in args:                              # тест: --world сезон,еда (0-3,0-3)
            v = [int(q) for q in args[args.index("--world") + 1].split(",")]
            self.set_answers(v[0], v[1])
        elif self.shot and "--paint" not in args and "--quiz" not in args:
            self.set_answers(1, 0)
        if "--inw" in args:                                # тест: сразу в мире (--at: координаты относительно мира)
            self.enter_world(ride=False)
            if self.start:
                self.px, self.pz = YW.WX + self.start[0], YW.WZ + self.start[1]
            if "--gy" in args:
                self.gy = float(args[args.index("--gy") + 1])
        if "--wride" in args:                              # тест: сразу в поездку над лесом
            self.enter_world(ride=True)
        if "--paint" in args:
            self.quiz = dict(phase="paint", step=2, season=1, food=0)
            self.begin_drawing(0)
        elif "--quiz" in args:
            st = int(args[args.index("--quiz") + 1])
            self.quiz = dict(phase="ask", step=min(st, 1), season=1 if st else None, food=None)
        elif not self.shot:
            self.try_resume()                              # опрос и рисунки, либо сразу парк, если уже сохранено
        if "--door" in args:
            self.door_open = 0.7

    # ------------------------------------------------------------------ GL
    def setup_gl(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_NORMALIZE)
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0, 0, 0, 1))
        glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
        glEnable(GL_FOG)
        glFogi(GL_FOG_MODE, GL_EXP2)
        glHint(GL_FOG_HINT, GL_NICEST)

    def make_fb_texture(self):
        self.fb = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.fb)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 1024, 1024, 0, GL_RGB, GL_UNSIGNED_BYTE, None)

    def make_overlay_textures(self):
        # прицел: крошечный полый круг (кольцо 4x4)
        n = 4
        arr = np.zeros((n, n, 4), np.uint8)
        for x, y in ((1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (1, 3), (2, 3)):
            arr[y, x] = (58, 36, 104, 255)
        upload("cross", np.ascontiguousarray(arr), n, n, mip=False, repeat=False)
        # маска света фонаря (проецируется на геометрию): яркая середина, видимый край и тонкий ободок
        N = 128
        yy, xx = np.mgrid[0:N, 0:N]
        r = np.hypot((xx + .5) / N * 2 - 1, (yy + .5) / N * 2 - 1)
        edge = np.clip((.82 - r) / .10, 0, 1)
        edge = edge * edge * (3 - 2 * edge)
        core = .58 + .42 * np.exp(-(r / .5) ** 2)
        rim = .22 * np.exp(-((r - .735) / .035) ** 2)
        inten = np.clip((core + rim) * edge, 0, 1)
        g = (inten * 255).astype(np.uint8)
        spot = np.stack([g, g, g, np.full_like(g, 255)], axis=2)
        upload("spot", np.ascontiguousarray(spot), N, N, mip=False, repeat=False)
        glBindTexture(GL_TEXTURE_2D, TEX["spot"])
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        # виньетка
        N = 64
        yy, xx = np.mgrid[0:N, 0:N]
        r = np.hypot((xx - N / 2) / (N / 2), (yy - N / 2) / (N / 2))
        a = np.clip((r - .35) / .75, 0, 1) ** 1.6
        vig = np.zeros((N, N, 4), np.uint8)
        vig[..., 3] = (a * 255).astype(np.uint8)
        tid = upload("vignette", np.ascontiguousarray(vig), N, N, mip=False, repeat=False)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        # зерно (обновляется каждый кадр)
        g = np.random.randint(0, 255, (96, 96, 1), dtype=np.uint8)
        grain = np.concatenate([g, g, g, np.full_like(g, 255)], axis=2)
        upload("grain", np.ascontiguousarray(grain), 96, 96, mip=False, repeat=True)
        # пузырь диалога
        self.bub_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.bub_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    # --------------------------------------------------------------- речь
    def say(self, text, hold=3.2):
        self.bub = dict(text=text, shown=0.0, hold=hold, last=-1, tail=None)

    def update_bubble(self, dt):
        b = self.bub
        if not b:
            return
        n = len(b["text"])
        if b["shown"] < n:
            b["shown"] = min(n, b["shown"] + 30 * dt)
            k = int(b["shown"])
            if k != b["last"]:
                b["last"] = k
                ch = b["text"][k - 1] if k > 0 else " "
                if ch not in " .,!?-" and k % 2 == 0:
                    self.audio.play("blip", .5)
        else:
            b["hold"] -= dt
            if b["hold"] <= 0:
                self.bub = None

    def build_bubble(self, b):
        """Пузырь диалога как в KinitoPET: кремовый, курсив, пиксельный, с хвостиком вниз."""
        key = (b["text"], int(b["shown"]))
        if self.bub_dims and self.bub_dims[0] == key:
            return self.bub_dims[1]
        font = self.mono(17)
        lines = textwrap.wrap(b["text"], 17) or [""]
        lh = font.get_linesize()
        pad = 8
        W = max(font.size(ln)[0] for ln in lines) + pad * 2 + 6
        H = lh * len(lines) + pad * 2
        tail = 11
        surf = pygame.Surface((W, H + tail), pygame.SRCALPHA)
        edge, cream = (40, 32, 28), (250, 241, 214)
        pygame.draw.rect(surf, edge, (0, 0, W, H), border_radius=6)
        pygame.draw.rect(surf, cream, (2, 2, W - 4, H - 4), border_radius=5)
        cx = W // 2
        pygame.draw.polygon(surf, edge, [(cx - 8, H - 3), (cx + 8, H - 3), (cx, H + tail)])
        pygame.draw.polygon(surf, cream, [(cx - 6, H - 4), (cx + 6, H - 4), (cx, H + tail - 4)])
        left = int(b["shown"])
        for i, ln in enumerate(lines):
            part = ln[:max(0, min(len(ln), left))]
            left -= len(ln) + 1
            if part:
                surf.blit(font.render(part, False, (16, 12, 10)), (pad, pad + i * lh))
        big = pygame.transform.scale(surf, (W * 2, (H + tail) * 2))
        data = pygame.image.tobytes(big, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self.bub_tex)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W * 2, (H + tail) * 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        dims = (W * 2, (H + tail) * 2)
        self.bub_dims = (key, dims)
        return dims

    def project(self, x, y, z):
        if self.mv is None:
            return None
        try:
            sx, sy, sz = gluProject(x, y, z, self.mv, self.pj, self.vp)
        except Exception:
            return None
        if sz >= 1.0 or sz <= 0:
            return None
        return sx * WIN_W / self.RW, WIN_H - sy * WIN_H / self.RH

    # --------------------------------------------------------------- логика
    def ride_pose(self):
        r = self.ride
        k = r["kind"]
        if k == "ferris":
            vx, vy = ferris_vert(self.fer_ang, r["i"])
            return (vx, vy - .5, FER["z"]), cam_yaw(.45, .9), 0.0
        if k == "carousel":
            rad, a0, j = HORSES[r["j"]]
            a = self.car_phi + a0
            bob = .38 * math.sin(self.t * 1.8 + j * math.pi)
            pos = (CAR["x"] + rad * math.cos(a), CAR["h"] + .45 + bob + 2.55, CAR["z"] + rad * math.sin(a))
            return pos, cam_yaw(-math.sin(a), math.cos(a)), -.05
        if k == "swing":
            a = self.sw_ang + r["i"] * TAU / SW_N
            rad = 5.0 + SWG["L"] * math.sin(self.sw_tilt)
            y = SWG["H"] - .8 - SWG["L"] * math.cos(self.sw_tilt) + 1.0
            return (SWG["x"] + rad * math.cos(a), y, SWG["z"] + rad * math.sin(a)), \
                cam_yaw(-math.sin(a), math.cos(a)), -.04
        if k in ("coaster", "wride"):
            pos, _ = YW.track_at(self.ride_track(), r["s"])
            return (pos[0], pos[1] + 1.15, pos[2]), self.cs_yaw, self.cs_pitch
        if k == "train":
            th = self.train_th - 2 * 5.8 / RR
            x, z = train_pos(th)
            return (x, 1.9, z), cam_yaw(C0[0] - x, C0[1] - z), 0.0
        raise ValueError(k)

    def ride_track(self):
        return self.world.track if self.ride and self.ride["kind"] == "wride" else COASTER

    def candidates(self):
        p = (self.px, self.pz)
        out = []
        if self.inw:
            return self.world.candidates(p[0], p[1], self.gy)
        d = math.hypot(p[0] - FER["x"], p[1] - (FER["z"] + 8.2))
        if d < 6:
            out.append((d, "ferris", "Колесо обозрения"))
        d = math.hypot(p[0] - CAR["x"], p[1] - CAR["z"])
        if d < 9.6:
            out.append((d, "carousel", "Карусель"))
        d = math.hypot(p[0] - SWG["x"], p[1] - SWG["z"])
        if 2.0 < d < 14.5:
            out.append((d + 3, "swing", "Цепочная карусель"))
        d = math.hypot(p[0] - CS_STATION[0], p[1] - CS_STATION[1])
        if d < 11:
            out.append((d, "coaster", "Американские горки"))
        tx, tz = train_pos(self.train_th - 2 * 5.8 / RR)
        d = math.hypot(p[0] - tx, p[1] - tz)
        if self.train_wait > 0 and d < 10:
            out.append((d, "train", "Поезд"))
        d = math.hypot(p[0] - (DOOR["x"] + 2.4), p[1] - DOOR["z"])
        if d < 3.4:
            out.append((d - 1, "door", "Белая дверь"))
        for key, S, lab in (("shoot", SHT, "Тир"), ("mole", MOLE, "Попади по кроту")):
            d = math.hypot(p[0] - S["sx"], p[1] - S["z"])
            if d < 2.8:
                out.append((d - 50, key, lab))
        d = math.hypot(p[0] - self.kx, p[1] - self.kz)
        if d < 3.4 and self.k_met:
            out.append((d - 100, "kinito", "Кинито"))
        out.sort()
        return out

    def board(self, kind):
        if kind in ("shoot", "mole"):
            self.start_mg(kind)
            return
        if kind.startswith("wdoor"):
            i = int(kind[5:])
            op = self.world.toggle_door(i)
            d = self.world.doors[i]
            self.audio.play_at("creak" if op else "clunk", YW.WX + d["x"], YW.WZ + d["z"], .9, 30)
            return
        if kind == "wreturn":
            self.start_trans("park")
            return
        if kind.startswith("spot"):
            i = int(kind[4:])
            lines = self.world.spots[i][6]
            n = self.spot_n.get(i, 0)
            self.spot_n[i] = n + 1
            self.say(lines[n % len(lines)], 3.8)
            self.audio.play("chime", .5)
            return
        if kind == "kinito":
            i = self.talk_order[self.talk_i % len(self.talk_order)]
            self.talk_i += 1
            self.say(KINITO_TALK[i], 3.4)
            self.k_talk = 5.0
            self.k_target = None
            return
        if kind == "door":
            self.seq = dict(t=0.0, snd=False)
            self.say("Кинито хочет сыграть с тобой в весёлую игру...", 2.5)
            return
        self.visited.add(kind)
        self.audio.play("clunk", .8)
        if kind == "ferris":
            ys = [ferris_vert(self.fer_ang, i)[1] for i in range(8)]
            self.ride = dict(kind=kind, t=0.0, i=int(np.argmin(ys)))
        elif kind == "carousel":
            best, bj = 1e9, 0
            for rad, a0, j in HORSES:
                a = self.car_phi + a0
                d = math.hypot(CAR["x"] + rad * math.cos(a) - self.px, CAR["z"] + rad * math.sin(a) - self.pz)
                if d < best:
                    best, bj = d, j
            self.ride = dict(kind=kind, t=0.0, j=bj)
        elif kind == "swing":
            a = math.atan2(self.pz - SWG["z"], self.px - SWG["x"])
            i = int(round(((a - self.sw_ang) % TAU) / (TAU / SW_N))) % SW_N
            self.ride = dict(kind=kind, t=0.0, i=i)
        elif kind == "coaster":
            self.cs = CS_START
            self.ride = dict(kind=kind, t=0.0, s=CS_START, v=2.5)
            _, t = coaster_at(CS_START + 2.0)
            self.cs_yaw = cam_yaw(t[0], t[2])
            self.cs_pitch = math.asin(clamp(t[1], -1, 1))
            self.cs_roll = 0.0
            self.last_clack = 0
        elif kind == "train":
            self.ride = dict(kind=kind, t=0.0, moved=False)
        self.yaw = 0.0
        self.pitch = 0.0
        self.vx = self.vz = 0.0
        lines = {"ferris": "Смотри, как высоко! Видно весь парк!",
                 "carousel": "Держись крепче, наездник!",
                 "swing": "Вжжжух! Выше, выше!",
                 "coaster": "Ты готов? Пристегнись... Поехали!",
                 "train": "Поезд идёт вокруг всего парка!"}
        self.say(lines[kind])
        others = {"ferris", "carousel", "swing", "train"}
        if others <= self.visited and "coaster" not in self.visited and kind != "coaster":
            self.say("Осталась только самая главная горка! Давай?")

    def leave(self, msg=None):
        r = self.ride
        base_yaw = self.ride_pose()[1]
        self.yaw = base_yaw + self.yaw
        self.pitch = 0.0
        k = r["kind"]
        if k == "ferris":
            self.px, self.pz = FER["x"], FER["z"] + 8.2
        elif k == "carousel":
            rad, a0, j = HORSES[r["j"]]
            a = self.car_phi + a0
            self.px, self.pz = CAR["x"] + 10.2 * math.cos(a), CAR["z"] + 10.2 * math.sin(a)
        elif k == "swing":
            a = self.sw_ang + r["i"] * TAU / SW_N
            self.px, self.pz = SWG["x"] + 12.5 * math.cos(a), SWG["z"] + 12.5 * math.sin(a)
        elif k == "coaster":
            self.px, self.pz = CS_STATION[0] + 3, CS_STATION[1] + 6
            self.cs = CS_START
        elif k == "wride":
            self.inw = True
            self.px, self.pz = self.world.land_pos
            self.yaw = 0.0                                   # дом прямо перед тобой
            self.cs = CS_START
            self.vx = self.vz = 0.0
            self.say("Это твой мир. Ты любишь %s, поэтому здесь всегда %s." % (
                YW.SEASON_ACC[self.world.season], YW.SEASON_NOM[self.world.season]), 5.0)
        elif k == "train":
            self.px, self.pz = -8.0, 60.0
            self.yaw = math.pi
        self.ride = None
        self.gy = 0.0
        if msg:
            self.say(msg)

    # --- «Твой мир»: опрос Кинито в начале игры, переход через шестиугольную дыру и возврат
    def set_answers(self, season, food):
        self.answers = (season, food)
        self.world = YW.World(season, food)
        YW.add_spots(self.world)

    def quiz_pick(self, n):
        qz = self.quiz
        if not qz or qz.get("phase") != "ask" or not (0 <= n < 4):
            return
        self.audio.play("tick", .8)
        if qz["step"] == 0:
            qz["season"], qz["step"] = n, 1
            self.save_profile()
            self.audio.play("chime", .7)
            return
        qz["food"] = n
        self.save_profile()
        self.audio.play("chime", .7)
        self.begin_drawing(self.count_drawings())

    def read_profile(self):
        path = os.path.join(profile_dir(), "profile.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_profile(self):
        qz = self.quiz
        folder = profile_dir()
        os.makedirs(folder, exist_ok=True)
        data = self.read_profile() or {}
        name, _ = player_name()
        data["name"] = name
        if qz:
            if qz.get("season") is not None:
                data["season"] = int(qz["season"])
            if qz.get("food") is not None:
                data["food"] = int(qz["food"])
        path = os.path.join(folder, "profile.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def count_drawings(self):
        folder = profile_dir()
        return sum(os.path.exists(os.path.join(folder, "draw%d.png" % i)) for i in range(len(DRAW_PROMPTS)))

    def replace_draw(self, index, surf):
        """Подменяет уже загруженную текстуру картины, не создавая новый id (его держит список дома)."""
        name = "draw%d" % index
        if name not in TEX:
            return
        img = surf.convert_alpha()
        w, h = img.get_size()
        data = pygame.image.tobytes(img, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, TEX[name])
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)

    def apply_saved_drawings(self):
        folder = profile_dir()
        loaded = []
        for i in range(len(DRAW_PROMPTS)):
            path = os.path.join(folder, "draw%d.png" % i)
            if not os.path.exists(path):
                continue
            try:
                loaded.append((i, pygame.image.load(path)))
            except Exception:
                continue
        for i, img in loaded:
            self.replace_draw(i, img)
        if len(loaded) == len(DRAW_PROMPTS):
            self.replace_draw(5, loaded[0][1])

    def try_resume(self):
        """Продолжить с места, где игрок вышел, либо сразу в парк, если всё уже нарисовано."""
        data = self.read_profile() or {}
        season, food = data.get("season"), data.get("food")
        done = self.count_drawings()
        if season is None:
            self.quiz = dict(phase="ask", step=0, season=None, food=None)
            return
        if food is None:
            self.quiz = dict(phase="ask", step=1, season=int(season), food=None)
            return
        if done < len(DRAW_PROMPTS):
            self.quiz = dict(phase="paint", step=2, season=int(season), food=int(food))
            self.begin_drawing(done)
            return
        self.set_answers(int(season), int(food))
        self.quiz = None
        self.park_t0 = self.t

    def begin_drawing(self, index):
        if index >= len(DRAW_PROMPTS):
            self.finish_intro()
            return
        surf = pygame.Surface((192, 120))
        surf.fill((255, 255, 255))
        name, _ = player_name()
        prompt = DRAW_PROMPTS[index][0]
        if index == 0:
            prompt = "%s, давай порисуем. %s" % (name, prompt)
        self.paint = dict(surf=surf, tool="pencil", color=(0, 0, 0), last=None, down=False,
                          line_a=None, dirty=True, snd_t=0.0, warn="", prompt=prompt, react="")
        self.quiz["phase"] = "paint"
        self.quiz["draw_i"] = index
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()

    def finish_intro(self):
        qz = self.quiz
        season = qz["season"] if qz and qz.get("season") is not None else 1
        food = qz["food"] if qz and qz.get("food") is not None else 0
        self.apply_saved_drawings()
        self.set_answers(int(season), int(food))
        self.quiz = None
        self.paint = None
        self.park_t0 = self.t
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()
        self.audio.play("chime", .9)

    def paint_geom(self):
        W, H = WIN_W, WIN_H
        bar = 40
        wx, wy, ww, wh = 8, bar + 4, W - 16, H - bar - 10
        title, tools, pal = 22, 56, 50
        canvas = (wx + tools + 6, wy + title + 4, ww - tools - 12, wh - title - pal - 8)
        return dict(bar=(0, 0, W, bar), win=(wx, wy, ww, wh), title=(wx, wy, ww, title),
                    tools=(wx + 4, wy + title + 4, tools - 8, wh - title - pal - 8),
                    canvas=canvas, pal=(wx + 4, wy + wh - pal + 4, ww - 8, pal - 8))

    def paint_upload(self):
        p = self.paint
        if not p or not p["dirty"]:
            return
        surf = p["surf"]
        w, h = surf.get_size()
        data = pygame.image.tobytes(surf, "RGBA", True)
        if "canvas" not in TEX:
            upload("canvas", data, w, h, mip=False, repeat=False)
        else:
            glBindTexture(GL_TEXTURE_2D, TEX["canvas"])
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)
        p["dirty"] = False

    def paint_ink(self):
        arr = pygame.surfarray.array3d(self.paint["surf"])
        white = (arr[:, :, 0] > 248) & (arr[:, :, 1] > 248) & (arr[:, :, 2] > 248)
        return int((~white).sum())

    def paint_stamp(self, a, b):
        p = self.paint
        tool = p["tool"]
        if tool == "erase":
            col, width = (255, 255, 255), 12
        elif tool == "brush":
            col, width = p["color"], 8
        else:
            col, width = p["color"], 3
        surf = p["surf"]
        pygame.draw.line(surf, col, a, b, width)
        pygame.draw.circle(surf, col, (int(b[0]), int(b[1])), max(1, width // 2))
        p["dirty"] = True
        p["react"] = ""
        p["warn"] = ""
        kind = "erase" if tool == "erase" else "pencil"
        if self.t - p["snd_t"] > 0.055:
            self.audio.play(kind, .6)
            p["snd_t"] = self.t

    def paint_to_canvas(self, pos):
        """Экранные координаты -> пиксели холста (он мельче окна, поэтому штрих на стене жирный)."""
        x, y, w, h = self.paint_geom()["canvas"]
        sw, sh = self.paint["surf"].get_size()
        return (pos[0] - x) / max(1, w) * sw, (pos[1] - y) / max(1, h) * sh, sw, sh

    def paint_fill(self, x, y):
        surf = self.paint["surf"]
        w, h = surf.get_size()
        if not (0 <= x < w and 0 <= y < h):
            return
        px = pygame.surfarray.pixels3d(surf)
        target = px[int(x), int(y)].copy()
        repl = np.array(self.paint["color"], np.uint8)
        if (target == repl).all():
            del px
            return
        stack = [(int(x), int(y))]
        while stack:
            cx, cy = stack.pop()
            if cx < 0 or cy < 0 or cx >= w or cy >= h or (px[cx, cy] != target).any():
                continue
            x0 = cx
            while x0 > 0 and (px[x0 - 1, cy] == target).all():
                x0 -= 1
            x1 = cx
            while x1 + 1 < w and (px[x1 + 1, cy] == target).all():
                x1 += 1
            px[x0:x1 + 1, cy] = repl
            if cy > 0:
                row = px[x0:x1 + 1, cy - 1]
                hits = np.where((row == target).all(axis=1))[0]
                stack.extend((x0 + int(i), cy - 1) for i in hits)
            if cy + 1 < h:
                row = px[x0:x1 + 1, cy + 1]
                hits = np.where((row == target).all(axis=1))[0]
                stack.extend((x0 + int(i), cy + 1) for i in hits)
        del px
        self.paint["dirty"] = True
        self.paint["react"] = ""
        self.paint["warn"] = ""
        self.audio.play("pencil", .45)

    def paint_pointer(self, pos, kind):
        p = self.paint
        if not p:
            return
        g = self.paint_geom()
        if kind == "down":
            if self._hit_done(pos, g):
                self.paint_finish()
                return
            tool = self._hit_tool(pos, g)
            if tool:
                p["tool"] = tool
                self.audio.play("tick", .5)
                return
            col = self._hit_color(pos, g)
            if col is not None:
                p["color"] = col
                self.audio.play("tick", .4)
                return
            lx, ly, w, h = self.paint_to_canvas(pos)
            if not (0 <= lx < w and 0 <= ly < h):
                return
            p["down"] = True
            if p["tool"] == "fill":
                self.paint_fill(lx, ly)
                p["down"] = False
                return
            if p["tool"] == "line":
                p["line_a"] = (lx, ly)
                p["last"] = (lx, ly)
                return
            self.paint_stamp((lx, ly), (lx, ly))
            p["last"] = (lx, ly)
        elif kind == "move" and p["down"]:
            lx, ly, w, h = self.paint_to_canvas(pos)
            lx = clamp(lx, 0, w - 1)
            ly = clamp(ly, 0, h - 1)
            if p["tool"] == "line":
                p["last"] = (lx, ly)
                return
            if p["last"] is not None:
                self.paint_stamp(p["last"], (lx, ly))
            p["last"] = (lx, ly)
        elif kind == "up":
            if p["down"] and p["tool"] == "line" and p["line_a"] and p["last"]:
                pygame.draw.line(p["surf"], p["color"], p["line_a"], p["last"], 3)
                p["dirty"] = True
                p["react"] = ""
                p["warn"] = ""
                self.audio.play("pencil", .6)
            p["down"] = False
            p["last"] = None
            p["line_a"] = None

    def _hit_done(self, pos, g):
        W = WIN_W
        return pygame.Rect(W - 118, 8, 100, 24).collidepoint(pos)

    def _hit_tool(self, pos, g):
        x, y, w, _ = g["tools"]
        names = ("pencil", "brush", "fill", "line", "erase")
        for i, name in enumerate(names):
            if pygame.Rect(x + 4, y + 4 + i * 34, 32, 30).collidepoint(pos):
                return name
        return None

    def _hit_color(self, pos, g):
        x, y, _, _ = g["pal"]
        for i, col in enumerate(PAINT_COLORS):
            colx = x + 46 + (i % 11) * 22
            coly = y + 4 + (i // 11) * 20
            if pygame.Rect(colx, coly, 20, 18).collidepoint(pos):
                return col
        return None

    def paint_finish(self):
        p = self.paint
        qz = self.quiz
        if not p or not qz:
            return
        if self.paint_ink() < 30:
            p["warn"] = "Тут пока пусто. Нарисуй хоть немного."
            self.audio.play("tick", .6)
            return
        i = qz["draw_i"]
        folder = profile_dir()
        os.makedirs(folder, exist_ok=True)
        pygame.image.save(p["surf"], os.path.join(folder, "draw%d.png" % i))
        self.save_profile()
        self.audio.play("chime", .65)
        p["warn"] = ""
        self.begin_drawing(i + 1)
        if self.paint and i + 1 < len(DRAW_PROMPTS):
            self.paint["react"] = DRAW_PROMPTS[i][1]

    def enter_world(self, ride):
        """Тест/переход: оказаться в «Твоём мире» (ride=True - на горках над лесом, иначе - у посадки)."""
        if ride:
            self.board_wride(9.0)
        else:
            self.inw = True
            self.px, self.pz = self.world.land_pos
            if not self.start:
                self.yaw = 0.0

    def board_wride(self, v):
        w = self.world
        self.inw = True
        self.ride = dict(kind="wride", t=0.0, s=0.0, v=v)
        _, t = YW.track_at(w.track, 2.0)
        self.cs_yaw = cam_yaw(t[0], t[2])
        self.cs_pitch = math.asin(clamp(t[1], -1, 1))
        self.cs_roll = 0.0
        self.last_clack = 0
        self.yaw = self.pitch = 0.0
        self.vx = self.vz = 0.0

    def start_trans(self, to):
        self.wtrans = dict(t=0.0, to=to, done=False)
        self.vx = self.vz = 0.0
        self.audio.play("chime", .8)

    def update_trans(self, dt):
        """Возврат в парк через шестиугольный проход: белая вспышка -> парк."""
        s = self.wtrans
        s["t"] += dt
        self.mouse_look(dt, .3)
        self.vx = self.vz = 0.0
        if s["t"] < 1.0:
            self.wflash = s["t"] ** 2
            self.flash_hold = True
        else:
            if not s["done"]:
                s["done"] = True
                self.inw = False
                self.px, self.pz = CS_STATION[0] + 3, CS_STATION[1] + 6
                self.yaw = math.pi
                self.gy = 0.0
                self.wflash = 1.0
                self.say("С возвращением в парк!", 3.0)
            self.wtrans = None

    def hud_quiz(self):
        W, H = WIN_W, WIN_H
        qz = self.quiz
        self.rect(0, 0, W, H, (.07, .03, .16, 1))
        # декоративные «шахматные» ленты как на вывеске парка
        band = 12
        for i in range(16):
            c = (.9, .1, .2, .9) if i % 2 == 0 else (.12, .16, .9, .9)
            self.rect(i * W / 16, 0, W / 16 + 1, band, c)
            self.rect(i * W / 16, H - band, W / 16 + 1, band, c)
        pw, ph = min(560, W - 48), min(400, H - 48)
        x0, y0 = (W - pw) / 2, (H - ph) / 2
        self.rect(x0, y0, pw, ph, (.1, .06, .22, .96))
        self.rect(x0 + 4, y0 + 4, pw - 8, ph - 8, (.34, .2, .6, .35))
        cx = W / 2
        self.text("KINITO PARK", 28, cx, y0 + 14, (255, 226, 60), (90, 30, 140))
        self.text("Прежде чем ты войдёшь в парк, давай познакомимся.", 16, cx, y0 + 52, (230, 200, 255), (40, 20, 80))
        self.text("Вопрос %d из 2" % (qz["step"] + 1), 16, cx, y0 + 78, (200, 200, 220), None)
        if qz["step"] == 0:
            q, opts = "Какое твоё любимое время года?", YW.SEASONS
        else:
            q, opts = "Какая твоя любимая еда?", YW.FOODS
        self.text(q, 22, cx, y0 + 112, (255, 255, 255), (60, 30, 120))
        for i, o in enumerate(opts):
            self.text("[%d]  %s" % (i + 1, o), 24, cx - 100, y0 + 156 + i * 38, (255, 226, 120), (60, 30, 120), "left")
        note = "Я всё запомню..." if qz["step"] == 0 else "Спасибо. Теперь нарисуй для меня."
        self.text(note, 16, cx, y0 + ph - 64, (230, 200, 255), (40, 20, 80))
        self.text("Нажми 1-4", 16, cx, y0 + ph - 36, (200, 200, 220), None)

    def ensure_paint_icons(self):
        if getattr(self, "_paint_icons", False):
            return
        def up(name, draw):
            s = pygame.Surface((24, 24), pygame.SRCALPHA)
            draw(s)
            upload(name, pygame.image.tobytes(s, "RGBA", True), 24, 24, mip=False, repeat=False)
        up("icon_pencil", lambda s: (pygame.draw.line(s, (40, 40, 40), (5, 19), (15, 7), 2),
                                      pygame.draw.polygon(s, (240, 210, 70), [(14, 5), (19, 10), (16, 11), (13, 7)])))
        up("icon_brush", lambda s: (pygame.draw.line(s, (50, 50, 50), (5, 19), (13, 9), 4),
                                     pygame.draw.circle(s, (30, 30, 30), (16, 7), 4)))
        up("icon_fill", lambda s: pygame.draw.polygon(s, (40, 90, 200), [(6, 16), (10, 6), (16, 8), (18, 16), (8, 20)]))
        up("icon_line", lambda s: pygame.draw.line(s, (20, 20, 20), (4, 18), (19, 5), 2))
        up("icon_erase", lambda s: (pygame.draw.rect(s, (250, 170, 190), (5, 7, 14, 12)),
                                     pygame.draw.rect(s, (80, 40, 50), (5, 7, 14, 12), 1)))
        self._paint_icons = True

    def hud_paint(self):
        self.ensure_paint_icons()
        self.paint_upload()
        W, H = WIN_W, WIN_H
        g = self.paint_geom()
        p = self.paint
        qz = self.quiz
        self.rect(0, 0, W, H, (.07, .03, .16, 1))
        self.rect(0, 0, W, g["bar"][3], (.14, .07, .26, 1))
        self.text(p["prompt"], 14, 10, 3, (255, 236, 180), (40, 20, 70), "left")
        sub = p["warn"] or p["react"] or ("Рисунок %d из %d" % (qz["draw_i"] + 1, len(DRAW_PROMPTS)))
        self.text(sub, 13, 10, 20, (255, 150, 150) if p["warn"] else (220, 200, 235), None, "left")
        self.rect(W - 112, 8, 96, 24, (.55, .32, .78, 1))
        self.text("Готово", 16, W - 64, 10, (255, 255, 255), (40, 20, 70))
        wx, wy, ww, wh = g["win"]
        self.rect(wx, wy, ww, wh, (.80, .80, .76, 1))
        self.rect(wx + 3, wy + 3, ww - 6, 18, (.70, .70, .66, 1))
        self.text("untitled - Paint", 14, wx + 8, wy + 4, (30, 30, 30), None, "left")
        self.rect(wx + ww - 22, wy + 4, 16, 14, (.86, .86, .82, 1))
        self.text("x", 12, wx + ww - 14, wy + 4, (40, 40, 40), None)
        tx, ty, _, _ = g["tools"]
        icons = ("icon_pencil", "icon_brush", "icon_fill", "icon_line", "icon_erase")
        names = ("pencil", "brush", "fill", "line", "erase")
        for i, (icon, name) in enumerate(zip(icons, names)):
            bx, by = tx + 4, ty + 4 + i * 34
            sel = p["tool"] == name
            self.rect(bx, by, 32, 30, ((.55, .55, .70, 1) if sel else (.88, .88, .84, 1)))
            self.tex_quad(TEX[icon], bx + 4, by + 3, 24, 24)
        # текущий цвет, как зелёный квадрат в Paint
        px0, py0, _, _ = g["pal"]
        self.rect(px0 + 4, py0 + 6, 28, 28, (.55, .55, .55, 1))
        cr, cg, cb = [c / 255 for c in p["color"]]
        self.rect(px0 + 8, py0 + 10, 20, 20, (cr, cg, cb, 1))
        for i, col in enumerate(PAINT_COLORS):
            colx = px0 + 46 + (i % 11) * 22
            coly = py0 + 6 + (i // 11) * 20
            self.rect(colx, coly, 20, 18, (col[0] / 255, col[1] / 255, col[2] / 255, 1))
            if col == p["color"]:
                self.rect(colx - 1, coly - 1, 22, 20, (1, 1, 1, .0))
                glBindTexture(GL_TEXTURE_2D, TEX["white"])
                glColor3f(0, 0, 0)
                glBegin(GL_LINE_LOOP)
                glVertex2f(colx - 1, coly - 1)
                glVertex2f(colx + 21, coly - 1)
                glVertex2f(colx + 21, coly + 19)
                glVertex2f(colx - 1, coly + 19)
                glEnd()
        cx, cy, cw, ch = g["canvas"]
        self.rect(cx - 2, cy - 2, cw + 4, ch + 4, (.45, .45, .45, 1))
        if "canvas" in TEX:
            self.tex_quad(TEX["canvas"], cx, cy, cw, ch)
        if p["down"] and p["tool"] == "line" and p["line_a"] and p["last"]:
            sw, sh = p["surf"].get_size()
            cr, cg, cb = [c / 255 for c in p["color"]]
            glBindTexture(GL_TEXTURE_2D, TEX["white"])
            glColor3f(cr, cg, cb)
            glBegin(GL_LINES)
            glVertex2f(cx + p["line_a"][0] / sw * cw, cy + p["line_a"][1] / sh * ch)
            glVertex2f(cx + p["last"][0] / sw * cw, cy + p["last"][1] / sh * ch)
            glEnd()
        mx, my = pygame.mouse.get_pos()
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        glColor3f(0, 0, 0)
        glBegin(GL_LINE_LOOP)
        glVertex2f(mx, my)
        glVertex2f(mx + 4, my + 14)
        glVertex2f(mx + 8, my + 11)
        glEnd()

    def interact(self):
        if self.mode != "park" or self.seq or self.quiz or self.wtrans:
            return
        if self.mg:                              # выход из мини-игры
            self.mg = None
            return
        if self.ride:
            k = self.ride["kind"]
            if k == "wride":
                self.say("Мы почти приехали. Подожди...", 1.4)
                return
            if k == "ferris":
                vy = ferris_vert(self.fer_ang, self.ride["i"])[1]
                if vy < 4.2:
                    self.leave()
                else:
                    self.say("Подожди, пока кабинка опустится!", 1.5)
            elif k in ("carousel", "swing"):
                self.leave()
            elif k == "coaster":
                self.say("На ходу вылезать нельзя!", 1.2)
            elif k == "train":
                self.say("Дождись остановки поезда.", 1.2)
        else:
            c = self.candidates()
            if c:
                self.board(c[0][1])

    def update_ride(self, dt):
        r = self.ride
        r["t"] += dt
        k = r["kind"]
        if k == "ferris":
            vy = ferris_vert(self.fer_ang, r["i"])[1]
            if r["t"] > 75 and vy < 4.2:
                self.leave("Было здорово!")
        elif k == "carousel":
            if r["t"] > 50:
                self.leave()
        elif k == "swing":
            if r["t"] > 45:
                self.leave()
        elif k in ("coaster", "wride"):
            P = self.ride_track()
            s = r["s"]
            pos, tan = YW.track_at(P, s)
            if s < P["peak"]:
                r["v"] += (7.5 - r["v"]) * min(1.0, dt * 1.8)       # плавный подъём по цепи
            else:
                a = -9.81 * tan[1] * .92 - .0009 * r["v"] ** 2 - .35   # гравитация + трение
                r["v"] = clamp(r["v"] + a * dt, 5.5, 27.0)
            rest = P["L"] - s
            if k == "coaster" and rest < 80:                        # перед шестиугольной дырой едем ровно и не медленно
                r["v"] += (min(r["v"], 8.0 + rest * .12) - r["v"]) * min(1.0, dt * 3)
            elif k == "wride" and rest < 50:                        # торможение у дома
                r["v"] += (min(r["v"], 1.4 + rest * .45) - r["v"]) * min(1.0, dt * 3)
            r["s"] += r["v"] * dt
            if k == "coaster":
                self.cs = r["s"]
            # плавная камера: смотрим по касательной чуть вперёд + сглаживание + крен в поворотах
            _, t1 = YW.track_at(P, r["s"] + 2.5)
            _, t2 = YW.track_at(P, r["s"] + 8.0)
            ty = cam_yaw(t1[0], t1[2])
            tp = math.asin(clamp(t1[1], -1, 1)) * .9
            k_s = min(1.0, dt * 7)
            self.cs_yaw += (((ty - self.cs_yaw + math.pi) % TAU) - math.pi) * k_s
            self.cs_pitch += (tp - self.cs_pitch) * k_s
            dyaw = ((cam_yaw(t2[0], t2[2]) - ty + math.pi) % TAU - math.pi) / 5.5
            roll_t = clamp(math.atan(r["v"] ** 2 * dyaw / 9.81) * .7, -.5, .5)
            self.cs_roll += (roll_t - self.cs_roll) * min(1.0, dt * 3)
            # звук рельсов
            seg = int(r["s"] / 7.0)
            if seg != self.last_clack and r["s"] > P["peak"]:
                self.last_clack = seg
                self.audio.play("clack", clamp(r["v"] / 28, .25, .8))
            if k == "coaster":
                # конец тоннеля: белый свет, и мы уже над лесом в «Твоём мире»
                ramp = (r["s"] - (P["L"] - 11.0)) / 6.0
                if ramp > 0:
                    self.wflash = max(self.wflash, clamp(ramp, 0, 1) ** 1.5)
                    self.flash_hold = True
                if ramp >= 1.0:
                    self.cs = CS_START
                    v = r["v"]
                    self.ride = None
                    self.board_wride(v)
                    self.audio.play("chime", .8)
                    self.say("Добро пожаловать в твой мир...", 4.0)
                    return
            elif r["s"] >= P["L"] - .6:
                self.leave()
        elif k == "train":
            if self.train_th > .3:
                r["moved"] = True
            if r["moved"] and self.train_wait > 0:
                self.leave("Конечная! Выходим.")
        if self.ride:
            self.yaw = clamp(self.yaw, -2.6, 2.6) if k != "ferris" else self.yaw
            self.pitch = clamp(self.pitch, -1.2, 1.2)

    # --- ходьба
    def collide_park(self, nx, nz):
        pr = .45
        for cx, cz, r in COLL:
            ddx = nx - cx
            if ddx > r + pr or ddx < -r - pr:
                continue
            ddz = nz - cz
            if ddz > r + pr or ddz < -r - pr:
                continue
            d2 = ddx * ddx + ddz * ddz
            rr = r + pr
            if d2 < rr * rr:
                d = math.sqrt(d2) or 1e-6
                nx = cx + ddx / d * rr
                nz = cz + ddz / d * rr
        ex, ez = nx - C0[0], nz - C0[1]
        d = math.hypot(ex, ez)
        if d > 93.4:
            nx = C0[0] + ex / d * 93.4
            nz = C0[1] + ez / d * 93.4
        return nx, nz

    def walk_world(self, dt):
        w = self.world
        indoor = w.inside(self.px, self.pz)
        self.walk(dt, WALK_SPEED, RUN_SPEED, lambda nx, nz: w.collide(nx, nz, self.gy),
                  "step1" if indoor else "step0")
        if os.environ.get("YW_FLY"):                      # отладка: свободная высота камеры
            return
        ty = w.floor_y(self.px, self.pz, self.gy)
        self.gy += (ty - self.gy) * min(1.0, dt * 12)
        if abs(ty - self.gy) < .002:
            self.gy = ty

    def walk(self, dt, walk_spd, run_spd, collide, step_kind, yaw=None):
        keys = pygame.key.get_pressed()
        mx = (keys[pygame.K_d] - keys[pygame.K_a])
        mz = (keys[pygame.K_w] - keys[pygame.K_s])
        sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        spd = run_spd if sprint else walk_spd
        yw = self.yaw if yaw is None else yaw
        fx, fz = -math.sin(yw), -math.cos(yw)
        rx, rz = math.cos(yw), -math.sin(yw)
        dx = fx * mz + rx * mx
        dz = fz * mz + rz * mx
        n = math.hypot(dx, dz)
        if n > 0:
            dx, dz = dx / n * spd, dz / n * spd
        k = min(1.0, dt * 9)
        self.vx = lerp(self.vx, dx, k)
        self.vz = lerp(self.vz, dz, k)
        nx, nz = collide(self.px + self.vx * dt, self.pz + self.vz * dt)
        moved = math.hypot(nx - self.px, nz - self.pz)
        self.walk_ph += moved * 2.1
        self.px, self.pz = nx, nz
        si = int(self.walk_ph / math.pi)
        if si != self.step_idx:
            self.step_idx = si
            if moved > .01:
                self.audio.play(step_kind, .5 if not sprint else .65)

    def _turn_k(self, tgt, dt, rate=7.0):
        dd = (tgt - self.kyaw + 180.0) % 360.0 - 180.0
        self.kyaw += dd * min(1.0, dt * rate)

    def update_kinito(self, dt):
        """Кинито встречает игрока у входа, потом бродит по парку сам по себе."""
        dx, dz = self.px - self.kx, self.pz - self.kz
        d = math.hypot(dx, dz)
        to_player = model_yaw_deg(dx, dz) if d > .1 else self.kyaw
        self.kmoving = False
        if not self.k_met:
            self._turn_k(to_player, dt)
            if d < 12 and self.t > 3.5 and not self.ride and not self.seq and not self.quiz:
                self.k_met = True
                self.k_talk = 5.0
                self.say("Привет! Добро пожаловать в Парк Кинито!", 3.4)
            return
        if self.k_talk > 0:                     # разговор: стоит и смотрит на игрока
            self.k_talk -= dt
            self._turn_k(to_player, dt)
            return
        if d < 2.4:                             # игрок рядом - останавливается, можно нажать E
            self._turn_k(to_player, dt)
            self.k_target = None
            self.k_timer = max(self.k_timer, 1.5)
            return
        if self.k_target is None:
            self.k_timer -= dt
            if d < 9:
                self._turn_k(to_player, dt, 2.0)
            if self.k_timer <= 0:
                for _ in range(12):             # случайная точка поблизости, не внутри препятствий
                    a = random.uniform(0, TAU)
                    r = random.uniform(7, 22)
                    tx, tz = self.kx + math.cos(a) * r, self.kz + math.sin(a) * r
                    if abs(tx) > 62 or not (-34 < tz < 64):
                        continue
                    cx, cz = self.collide_park(tx, tz)
                    if math.hypot(cx - tx, cz - tz) < .05:
                        self.k_target = (tx, tz)
                        self.k_stuck = 0.0
                        break
                else:
                    self.k_timer = 1.0
            return
        tx, tz = self.k_target
        ex, ez = tx - self.kx, tz - self.kz
        de = math.hypot(ex, ez)
        if de < .5:
            self.k_target = None
            self.k_timer = random.uniform(2.5, 7.0)
            return
        self._turn_k(model_yaw_deg(ex, ez), dt, 6.0)
        sp = 2.0 * dt
        nx, nz = self.collide_park(self.kx + ex / de * sp, self.kz + ez / de * sp)
        moved = math.hypot(nx - self.kx, nz - self.kz)
        self.kx, self.kz = nx, nz
        self.kmoving = True
        if moved < sp * .4:                     # упёрся в препятствие
            self.k_stuck += dt
            if self.k_stuck > .6:
                self.k_target = None
                self.k_timer = random.uniform(.5, 2.0)
        else:
            self.k_stuck = 0.0

    def mouse_look(self, dt, k=1.0):
        mdx, mdy = pygame.mouse.get_rel()
        sens = .0022 * k * (self.fov / 72.0 if self.fov < 72 else 1.0)
        self.yaw -= mdx * sens
        self.pitch = clamp(self.pitch - mdy * sens, -1.5, 1.5)
        return mdx, mdy

    # --- Hide and Seek
    def start_hs(self):
        if self.hs:
            self.hs.free()
        self.hs = HideSeek()
        self.hs.build()
        c = self.hs.center(self.hs.start_cell)
        self.px, self.pz = c
        self.yaw = self.hs.start_yaw()
        self.pitch = 0.0
        self.view_yaw = self.fl_yaw = self.yaw
        self.view_pitch = self.fl_pitch = 0.0
        self.vx = self.vz = 0.0
        self.hs_t = 0.0
        self.hs_light = 1.0
        self.fl_state = 0
        self.fl_timer = 9.0
        self.beat_t = 0.0
        self.kstep_t = 0.0
        self.ride = None
        self.gy = 0.0
        self.roll = 0.0

    def begin_hs_intro(self):
        self.mode = "hs_intro"
        self.intro_t = 0.0
        self.fade = 1.0
        self.seq = None
        self.bub = None
        if self.audio.ok:
            pygame.mixer.music.pause()
            self.audio.stop_all_loops()
        self.start_hs()

    def begin_hs(self):
        self.mode = "hs"
        self.fade = 1.0
        if self.audio.ok:
            pygame.mixer.music.pause()                 # в Hide and Seek фоновой музыки нет (один раз)
            for n in self.audio.LOOPS:                 # и никаких парковых петель (карусель, фонтан, ветер...)
                self.audio.stop_loop(n)
            pygame.mixer.stop()
    def return_to_park(self):
        self.mode = "park"
        self.fade = 1.0
        self.px, self.pz = DOOR["x"] + 4.0, DOOR["z"]
        self.yaw = math.pi / 2
        self.pitch = 0.0
        self.door_open = 0.0
        self.kx, self.kz = self.px + 2.5, self.pz + 2.5
        self.k_met, self.k_talk, self.k_target, self.k_timer = True, 0.0, None, 3.0
        self.vx = self.vz = 0.0
        self.glitching = False
        self.audio.stop_all_loops()
        if self.audio.ok:
            pygame.mixer.music.unpause()
        self.say("Кинито так рад, что ты вернулся...", 3)

    def update_hs(self, dt):
        self.hs_t += dt
        hs = self.hs
        mdx, mdy = self.mouse_look(dt, .55)            # в подвале камера тяжелее и медленнее
        # инерция камеры: реальный взгляд догоняет цель от мыши, фонарь отстаёт ещё сильнее
        kv = 1 - math.exp(-dt * 4.2)
        oy, op = self.view_yaw, self.view_pitch
        self.view_yaw += (self.yaw - self.view_yaw) * kv
        self.view_pitch += (self.pitch - self.view_pitch) * kv
        if dt > 0:
            self.turn_w = lerp(self.turn_w, abs(self.view_yaw - oy) / dt, min(1.0, dt * 12))
            self.turn_p = lerp(self.turn_p, abs(self.view_pitch - op) / dt, min(1.0, dt * 12))
        # звук рывка камеры при резком повороте
        self.swish_cd -= dt
        flick = math.hypot(mdx, mdy)
        if flick > 28 and self.swish_cd <= 0:
            self.audio.play("swish", clamp(.25 + flick / 260, .3, .9), clamp(-mdx / 300, -.5, .5))
            self.swish_cd = .45
        # фонарь опережает камеру: смотрит туда, куда камера только поворачивается
        kf = 1 - math.exp(-dt * 12.0)
        ty = self.view_yaw + clamp((self.yaw - self.view_yaw) * 1.4, -.55, .55)
        tp = self.view_pitch + clamp((self.pitch - self.view_pitch) * 1.4, -.4, .4)
        self.fl_yaw += (ty - self.fl_yaw) * kf
        self.fl_pitch += (clamp(tp, -1.45, 1.45) - self.fl_pitch) * kf
        self.walk(dt, HS_WALK, HS_RUN, lambda x, z: hs.collide(x, z, .35), "step1", self.view_yaw)
        sp = math.hypot(self.vx, self.vz)
        tgt = clamp(sp / HS_WALK, 0.0, 1.0) * (1.0 + .55 * clamp((sp - HS_WALK) / (HS_RUN - HS_WALK), 0.0, 1.0))
        self.bob_amp += (tgt - self.bob_amp) * (1 - math.exp(-dt * (8 if tgt > self.bob_amp else 5)))
        if getattr(self, "mon_test", 0):
            d = self.mon_test
            hs.kx = self.px - math.sin(self.view_yaw) * d
            hs.kz = self.pz - math.cos(self.view_yaw) * d
            hs.kyaw = model_yaw_deg(self.px - hs.kx, self.pz - hs.kz)
            hs.kmoving = False
            self.hs_t = min(self.hs_t, 5.0)
        else:
            hs.update_seeker(self.px, self.pz, dt, self.hs_t)
        # мигание лампочки / отключение света
        self.fl_timer -= dt
        if self.fl_state == 0:
            self.hs_light = 1.0
            if self.fl_timer <= 0:
                self.fl_state = 1
                self.fl_black = random.random() < .55
                self.fl_dur = random.uniform(.7, 1.3) if not self.fl_black else random.uniform(1.4, 2.2)
                self.fl_timer = self.fl_dur
        else:
            if self.fl_black:
                self.hs_light = 0.0
            else:
                self.hs_light = 1.0 if math.sin(self.hs_t * 55) > .1 else .12
            if self.fl_timer <= 0:
                if self.fl_black:
                    hs.advance_seeker(5.0, self.px, self.pz)
                    self.audio.play("thud", .9)
                self.fl_state = 0
                self.fl_timer = random.uniform(7, 14)
        dist = math.hypot(self.px - hs.kx, self.pz - hs.kz)
        # звуки: шаги Кинито и сердцебиение
        if hs.kmoving:
            self.kstep_t -= dt
            if self.kstep_t <= 0:
                self.kstep_t = .62
                self.audio.play_at("thud", hs.kx, hs.kz, 1.0, 22)
        self.beat_t -= dt
        if self.beat_t <= 0:
            self.audio.play("heartbeat", clamp(1.2 - dist / 14, .15, 1.0))
            self.beat_t = clamp(.5 + dist / 16, .5, 1.3)
        self.audio.set_listener(self.px, self.pz, self.view_yaw)
        if dist < 1.3:
            self.mode = "hs_scare"
            self.scare_t = 0.0
            self.audio.stop_loop("drone")
            self.audio.play("scream", 1.0)
        elif self.hs_t > 110:
            self.begin_glitch()

    def begin_glitch(self):
        self.mode = "hs_glitch"
        self.glitch_t = 0.0
        self.audio.stop_loop("drone")
        self.audio.play("glitch", 1.0)

    def update_modes(self, dt):
        """Состояния вне обычной ходьбы по парку. Возвращает True, если парковая логика не нужна."""
        if self.mode == "hs_intro":
            t0 = self.intro_t
            self.intro_t += dt
            t = self.intro_t
            for sec in (0.0, 1.0):
                if t0 < sec <= t or (t0 == 0 and sec == 0):
                    self.audio.play("tick", .7)
            if t0 < 1.6 <= t:
                self.audio.play("alarm", .8)
            pygame.mouse.get_rel()
            if t > 8.3:
                self.begin_hs()
            return True
        if self.mode == "hs":
            self.update_hs(dt)
            return True
        if self.mode == "hs_scare":
            self.scare_t += dt
            pygame.mouse.get_rel()
            if self.scare_t > 1.8:
                self.begin_glitch()
            return True
        if self.mode == "hs_glitch":
            self.glitch_t += dt
            pygame.mouse.get_rel()
            self.glitching = True
            if self.glitch_t > 2.8:
                self.return_to_park()
            return True
        return False

    def update(self, dt):
        self.t += dt
        if self.fade > 0 and self.mode != "hs_intro":
            self.fade = max(0.0, self.fade - dt * .9)
        if self.update_modes(dt):
            return
        self.fer_ang += .13 * dt
        self.car_phi += .55 * dt
        self.sw_ang += 1.05 * dt
        self.sw_tilt = .58 + .08 * math.sin(self.t * .45)
        # поезд
        if self.train_wait > 0:
            self.train_wait -= dt
            if self.train_wait <= 0:
                tx, tz = train_pos(0.0)
                self.audio.play_at("whistle", tx, tz, 1.0, 120)
        else:
            self.train_th += (10.0 / RR) * dt
            if self.train_th >= TAU:
                self.train_th = 0.0
                self.train_wait = 18.0
                tx, tz = train_pos(0.0)
                self.audio.play_at("bell", tx, tz, 1.0, 120)
        self.fov_t = 30.0 if pygame.mouse.get_pressed()[2] else 72.0
        self.fov = lerp(self.fov, self.fov_t, min(1, dt * 10))
        self.flash_hold = False
        if self.seq:
            self.update_door_seq(dt)
        elif self.quiz:
            pygame.mouse.get_rel()
            self.vx = self.vz = 0.0
        elif self.wtrans:
            self.update_trans(dt)
        else:
            self.mouse_look(dt)
            if self.ride:
                self.update_ride(dt)
            elif self.mg:
                self.update_mg(dt)
            elif self.inw:
                self.walk_world(dt)
            else:
                self.walk(dt, WALK_SPEED, RUN_SPEED, self.collide_park, "step0")
        if self.wflash > 0 and not self.flash_hold:
            self.wflash = max(0.0, self.wflash - dt * .7)
        self.update_games(dt)
        if self.mode != "park":                 # дверь открыта -> уже в Hide and Seek, парковые звуки не трогаем
            return
        self.update_kinito(dt)
        self.update_bubble(dt)
        w = self.world
        if w and self.inw:
            w.update(dt)
            if not w.entered and w.inside(self.px, self.pz) and not self.ride:
                w.entered = True
                if not self.shot:
                    self.say("Добро пожаловать домой.", 3.4)
                    self.audio.play("chime", .7)
        if not self.bub and self.k_met and not self.ride and not self.seq and not self.inw and not self.quiz:
            if not self.door_hint and math.hypot(self.px - DOOR["x"], self.pz - DOOR["z"]) < 16:
                self.door_hint = True
                self.say("Кинито хочет сыграть с тобой в весёлую игру...", 4)
            elif self.t > self.next_line and math.hypot(self.px - self.kx, self.pz - self.kz) < 7:
                self.say(KINITO_LINES[self.line_i % len(KINITO_LINES)])   # изредка бормочет, если рядом
                self.line_i += 1
                self.next_line = self.t + 40
        self.update_audio(dt)

    # ------------------------------------------------------------ мини-игры
    def init_targets(self):
        """Мишени тира: три ряда на рельсах, движутся навстречу друг другу."""
        self.tg = []
        plan = [(0, 4, 1.5, ("b", "b", "b", "b")),
                (1, 3, -2.1, ("b", "b", "b")),
                (2, 3, 2.7, ("g", "k", "g"))]
        for row, n, v, kinds in plan:
            X, y, r = SHT_ROWS[row]
            for i in range(n):
                kind = kinds[i]
                self.tg.append(dict(X=X, y=y, r=r * (.7 if kind == "g" else 1.0), z=-3.6 + 7.2 * i / n,
                                    v=v * (1.25 if kind == "g" else 1.0), kind=kind, hit=None))

    def start_mg(self, kind):
        base = math.pi / 2 if kind == "shoot" else -math.pi / 2
        S = SHT if kind == "shoot" else MOLE
        self.px, self.pz = S["sx"], S["z"]
        self.yaw, self.pitch = base, (-.03 if kind == "shoot" else -.32)
        self.vx = self.vz = 0.0
        self.mg = dict(kind=kind, t=0.0, dur=45.0 if kind == "shoot" else 40.0, score=0, cd=0.0,
                       flash=0.0, swing=0.0, end=None, pop=None, base=base, hits=0, shots=0)
        if kind == "shoot":
            self.init_targets()
            self.say("Целься и стреляй! Золотые мишени дороже. Меня не трогай!", 3.6)
        else:
            self.say("Бей кротов молотком! Золотые - дороже. Меня не бей!", 3.6)
        self.audio.play("tick", .7)

    def end_mg(self):
        mg = self.mg
        mg["end"] = 0.0
        sc = mg["score"]
        newrec = sc > self.best[mg["kind"]]
        if newrec:
            self.best[mg["kind"]] = sc
        mg["newrec"] = newrec
        lo, hi = (150, 350) if mg["kind"] == "shoot" else (100, 250)
        self.audio.play("fanfare", .8)
        if sc >= hi:
            self.say("Невероятно! Ты лучший игрок в моём парке!", 3.6)
        elif sc >= lo:
            self.say("Здорово получилось! Хочешь ещё раз?", 3.6)
        else:
            self.say("Неплохо! Давай попробуем ещё?", 3.6)

    def mg_pop(self, text, col):
        self.mg["pop"] = [text, col, 1.1]

    def update_mg(self, dt):
        mg = self.mg
        self.yaw = clamp(self.yaw, mg["base"] - 1.0, mg["base"] + 1.0)
        self.pitch = clamp(self.pitch, -.8, .5)
        mg["cd"] = max(0.0, mg["cd"] - dt)
        mg["flash"] = max(0.0, mg["flash"] - dt)
        mg["swing"] = max(0.0, mg["swing"] - dt)
        if mg["pop"]:
            mg["pop"][2] -= dt
            if mg["pop"][2] <= 0:
                mg["pop"] = None
        if mg["end"] is not None:
            mg["end"] += dt
            if mg["end"] > 4.0:
                self.mg = None
            return
        mg["t"] += dt
        if mg["t"] >= mg["dur"]:
            self.end_mg()

    def click(self):
        mg = self.mg
        if self.mode != "park" or not mg or mg["end"] is not None or mg["cd"] > 0:
            return
        pos, f = self.camera()
        o = np.array(pos, float)
        d = np.array(f, float)
        mg["shots"] += 1
        if mg["kind"] == "shoot":
            mg["cd"], mg["flash"] = .26, .07
            self.audio.play("shot", .8)
            best, bt = None, 1e9
            for tg in self.tg:
                if tg["hit"] is not None or d[0] > -1e-3:
                    continue
                t = (tg["X"] - o[0]) / d[0]
                if t <= 0 or t >= bt:
                    continue
                zc = SHT["z"] + tg["z"]
                dist = math.hypot(o[2] + d[2] * t - zc, o[1] + d[1] * t - tg["y"])
                if dist < tg["r"]:
                    best, bt = (tg, dist), t
            if best:
                tg, dist = best
                tg["hit"] = 0.0
                mg["hits"] += 1
                if tg["kind"] == "k":
                    mg["score"] = max(0, mg["score"] - 20)
                    self.audio.play("buzz", .8)
                    self.mg_pop("Ай! Не стреляй в меня! -20", (255, 120, 150))
                elif tg["kind"] == "g":
                    mg["score"] += 40
                    self.audio.play("ding", .9)
                    self.mg_pop("Золото! +40", (255, 224, 70))
                else:
                    pts = 10 + int(15 * (1 - dist / tg["r"]))
                    mg["score"] += pts
                    self.audio.play("ding", .8)
                    self.mg_pop("+%d" % pts, (255, 255, 255))
        else:
            mg["cd"], mg["swing"] = .32, .3
            self.audio.play("swish", .5)
            best, bt = None, 1e9
            for i, (hx, hz) in enumerate(MOLE_HOLES):
                m = self.moles[i]
                if m["s"] not in (1, 2) or m["h"] < .25:
                    continue
                c = np.array([hx, 1.0 - .4 + .62 * m["h"], hz])
                Lv = c - o
                tca = float(Lv @ d)
                d2 = float(Lv @ Lv) - tca * tca
                if tca > 0 and d2 < .36 ** 2 and tca < bt:
                    best, bt = i, tca
            if best is not None:
                m = self.moles[best]
                m["s"], m["t"], m["h0"] = 4, 0.0, m["h"]
                mg["hits"] += 1
                self.audio.play("whack", .9)
                if m["kind"] == "k":
                    mg["score"] = max(0, mg["score"] - 20)
                    self.audio.play("buzz", .7)
                    self.mg_pop("Не бей Кинито! -20", (255, 120, 150))
                elif m["kind"] == "g":
                    mg["score"] += 30
                    self.mg_pop("Золотой крот! +30", (255, 224, 70))
                else:
                    mg["score"] += 10
                    self.mg_pop("+10", (255, 255, 255))

    def update_games(self, dt):
        """Мишени и кроты живут всегда (стенд оживлён), но очки считаются только во время игры."""
        for tg in self.tg:
            if tg["hit"] is not None:
                tg["hit"] += dt
                if tg["hit"] > 1.5:
                    tg["hit"] = None
                    tg["z"] = random.uniform(-3.4, 3.4)
                continue
            tg["z"] += tg["v"] * dt
            if tg["z"] > 3.9:
                tg["z"] = -3.9
            elif tg["z"] < -3.9:
                tg["z"] = 3.9
        mg = self.mg
        active = bool(mg and mg["kind"] == "mole" and mg["end"] is None)
        prog = mg["t"] / mg["dur"] if active else 0.0
        up = 0
        for i, m in enumerate(self.moles):
            s = m["s"]
            if s == 0:
                m["h"] = 0.0
                continue
            m["t"] += dt
            if s == 1:
                m["h"] = min(1.0, m["t"] / .16)
                if m["t"] >= .16:
                    m["s"], m["t"] = 2, 0.0
            elif s == 2:
                m["h"] = 1.0
                if m["t"] >= m["life"]:
                    m["s"], m["t"] = 3, 0.0
            elif s == 3:
                m["h"] = max(0.0, 1 - m["t"] / .2)
                if m["t"] >= .2:
                    m["s"] = 0
            elif s == 4:
                m["h"] = m["h0"] * (1 - clamp((m["t"] - .22) / .25, 0, 1))
                if m["t"] > .47:
                    m["s"] = 0
            if m["s"] in (1, 2):
                up += 1
        self.mole_next -= dt
        if self.mole_next <= 0:
            if active:
                self.mole_next = random.uniform(.4, .85) * (1 - .45 * prog)
                maxup = 3
            else:
                self.mole_next = random.uniform(2.0, 4.0)
                maxup = 1 if math.hypot(self.px - MOLE["x"], self.pz - MOLE["z"]) < 40 else 0
            free = [m for m in self.moles if m["s"] == 0]
            if free and up < maxup:
                m = random.choice(free)
                r = random.random()
                m["kind"] = "n" if (not active or r < .7) else ("g" if r < .85 else "k")
                m["life"] = (1.2 - .6 * prog) * (.7 if m["kind"] == "g" else 1.0) if active else 1.4
                m["s"], m["t"], m["h"] = 1, 0.0, 0.0
                hx, hz = MOLE_HOLES[self.moles.index(m)]
                self.audio.play_at("pop", hx, hz, .8, 30)

    def draw_games(self):
        bz = SHT["z"]
        for X, y, r in SHT_ROWS:                                   # рельсы
            beam((X - .15, y + r + .45, bz - 4.3), (X - .15, y + r + .45, bz + 4.3), .08, (.55, .55, .62))
        for tg in self.tg:
            X, y, r = tg["X"], tg["y"], tg["r"]
            yr = y + r + .45
            ang = 92 * min(1.0, tg["hit"] / .18) if tg["hit"] is not None else 0.0
            push(X, yr, bz + tg["z"], rz=-ang)
            obj("box", 0, -.22, 0, .05, .44, .05, (.5, .5, .55))
            push(0, y - yr, 0)
            if tg["kind"] == "b":
                for k, (rr, c) in enumerate(((1.0, WHITE), (.76, RED), (.52, WHITE), (.28, RED))):
                    obj("cyl", .03 + .018 * k, 0, 0, r * rr, .04, r * rr, c, rz=90)
            elif tg["kind"] == "g":
                obj("cyl", .03, 0, 0, r, .04, r, (1.0, .84, .2), rz=90)
                obj("cyl", .05, 0, 0, r * .62, .04, r * .62, (1.0, .55, .1), rz=90)
                obj("cyl", .07, 0, 0, r * .25, .04, r * .25, WHITE, rz=90)
            else:                                                  # картонный Кинито - не стрелять
                obj("cyl", .03, 0, 0, r, .04, r, K_HEAD, rz=90)
                for s in (-1, 1):
                    obj("cyl", .05, r * .14, s * r * .38, r * .27, .04, r * .27, WHITE, rz=90)
                    obj("cyl", .07, r * .1, s * r * .38, r * .11, .04, r * .11, (0, 0, 0), rz=90)
                    spike((0, r * .1, s * r * .9), (.0, r * .55, s * r * 1.6), r * .1, K_GILL)
                    spike((0, -r * .15, s * r * .92), (.0, -r * .3, s * r * 1.5), r * .09, K_GILL)
            pop()
            pop()
        for i, (hx, hz) in enumerate(MOLE_HOLES):                   # кроты
            m = self.moles[i]
            h = m["h"]
            if h <= .01:
                continue
            col = {"n": (.5, .34, .22), "g": (1.0, .82, .25), "k": K_HEAD}[m["kind"]]
            sq = 1.0 if m["s"] != 4 else max(.55, 1 - m["t"] * 3)
            push(hx, 1.0 - .4 + .62 * h, hz)
            obj("sphere", 0, 0, 0, .3, .34 * sq, .3, col)
            if m["kind"] == "k":
                for s in (-1, 1):
                    obj("sphere", -.24, .1, s * .13, .08, .1, .1, WHITE, lit=False)
                    obj("sphere", -.31, .08, s * .13, .03, .045, .04, (0, 0, 0), lit=False)
                    obj("sphere", -.27, .15, s * .13, .09, .045, .11, K_HEAD)
                    spike((-.02, .08, s * .27), (-.1, .26, s * .5), .035, K_GILL)
            else:
                obj("sphere", -.12, -.06, 0, .2, .24 * sq, .2, (.82, .68, .52) if m["kind"] == "n" else (1.0, .95, .6))
                for s in (-1, 1):
                    obj("sphere", -.25, .12, s * .11, .07, .08, .07, WHITE, lit=False)
                    obj("sphere", -.31, .12, s * .11, .028, .035, .03, (0, 0, 0), lit=False)
                    obj("sphere", 0, .33 * sq, s * .19, .08, .08, .06, col)
                    obj("sphere", -.2, -.16, s * .28, .09, .08, .08, (.3, .2, .14))
                    obj("box", -.31, -.1, s * .03, .02, .07, .03, WHITE)
                obj("sphere", -.32, .0, 0, .07, .055, .07, (1.0, .55, .65))
            if m["s"] == 4:
                for k in range(3):
                    a = self.t * 9 + k * TAU / 3
                    obj("sphere", math.cos(a) * .3, .5, math.sin(a) * .3, .05, .05, .05, (1.0, .9, .2), lit=False)
            pop()

    def draw_viewmodel(self):
        """Оружие / молоток перед камерой (рисуем в координатах глаза поверх сцены)."""
        mg = self.mg
        if not mg or mg["end"] is not None:
            return
        glClear(GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_FOG)
        sway = math.sin(self.t * 1.3) * .004
        if mg["kind"] == "shoot":
            rec = mg["flash"] / .07 * .05 if mg["flash"] > 0 else 0.0
            push(.26, -.27 + sway, -.62 + rec)
            obj("box", 0, 0, 0, .075, .11, .5, (.28, .16, .42), lit=False)           # корпус
            obj("box", 0, .06, -.02, .05, .02, .4, (.55, .4, .75), lit=False)        # блик сверху
            obj("box", 0, .01, -.4, .035, .035, .42, (.75, .75, .82), lit=False)     # ствол
            obj("box", 0, .05, -.55, .012, .035, .012, (.15, .15, .2), lit=False)    # мушка
            obj("box", 0, -.09, .22, .07, .17, .1, (.5, .3, .18), lit=False, rx=-18)  # приклад
            obj("box", 0, -.1, -.05, .05, .13, .05, (.22, .12, .34), lit=False, rx=14)  # рукоять
            if mg["flash"] > .02:
                obj("sphere", 0, .01, -.68, .09, .09, .09, (1.0, .9, .4), lit=False)
                obj("sphere", 0, .01, -.68, .05, .05, .05, WHITE, lit=False)
            pop()
        else:
            s = 1 - mg["swing"] / .3 if mg["swing"] > 0 else 0.0
            if mg["swing"] > 0:
                k = math.sin(min(1.0, s * 1.15) * math.pi * .5) if s < .55 else 1 - (s - .55) / .45 * .85
                ang = 18 - 125 * clamp(k, 0, 1)
            else:
                ang = 18 + 3 * math.sin(self.t * 1.7)
            push(.30, -.62 + sway, -.62, rx=ang)
            obj("box", 0, .25, 0, .04, .5, .04, (.62, .4, .22), lit=False)            # рукоять
            obj("box", 0, .54, 0, .26, .17, .16, (.9, .2, .3), lit=False)             # боёк
            obj("box", 0, .54, .0, .27, .06, .17, (1.0, .85, .25), lit=False)         # полоса
            pop()
        glEnable(GL_FOG)
        glPopMatrix()

    def hud_mg(self):
        mg = self.mg
        W, H = WIN_W, WIN_H
        name = "ТИР" if mg["kind"] == "shoot" else "ПОПАДИ ПО КРОТУ"
        left = max(0.0, mg["dur"] - mg["t"])
        self.rect(W / 2 - 250, 10, 500, 76, (0, 0, 0, .5))
        self.text(name, 22, W / 2, 12, (255, 214, 40), (60, 20, 100))
        self.text("Счёт: %d" % mg["score"], 30, W / 2 - 120, 40, (255, 255, 255), (60, 30, 120))
        self.text("Время: %d" % math.ceil(left), 30, W / 2 + 120, 40, (255, 120, 140) if left < 8 else (255, 255, 255),
                  (60, 30, 120))
        self.text("Рекорд: %d" % self.best[mg["kind"]], 18, W - 20, 16, (255, 255, 255), (60, 30, 120), "right")
        hint = "[ЛКМ] стрелять   [ПКМ] прицел   [E] выйти" if mg["kind"] == "shoot" else \
            "[ЛКМ] ударить   [E] выйти"
        self.rect(W / 2 - 280, H - 70, 560, 42, (0, 0, 0, .45))
        self.text(hint, 24, W / 2, H - 66, outline=None)
        if mg["pop"]:
            tx, col, tl = mg["pop"]
            self.text(tx, 36, W / 2, H / 2 - 110 - (1.1 - tl) * 40, col, (40, 20, 80), alpha=clamp(tl * 3, 0, 1))
        if mg["end"] is not None:
            self.rect(0, H / 2 - 110, W, 220, (0, 0, 0, .55))
            self.text("ВРЕМЯ ВЫШЛО!", 64, W / 2, H / 2 - 100, (255, 214, 40), (86, 30, 158))
            self.text("Счёт: %d" % mg["score"], 48, W / 2, H / 2 - 10, (255, 255, 255), (60, 30, 120))
            if mg.get("newrec"):
                self.text("Новый рекорд!", 30, W / 2, H / 2 + 50, (255, 140, 200), (60, 30, 120))

    def update_door_seq(self, dt):
        s = self.seq
        s["t"] += dt
        t = s["t"]
        pygame.mouse.get_rel()
        if not s["snd"]:
            s["snd"] = True
            self.audio.play("creak", .9)
            self.audio.play("door_open", .7)
        self.door_open = clamp(t / 1.4, 0, 1)
        dyaw = ((math.pi / 2 - self.yaw + math.pi) % TAU) - math.pi
        self.yaw += dyaw * min(1, dt * 4)
        self.pitch += (0 - self.pitch) * min(1, dt * 4)
        if t > 1.0:
            self.px = max(DOOR["x"] + .3, self.px - 1.5 * dt)
            self.pz += (DOOR["z"] - self.pz) * min(1, dt * 3)
        if t > 1.7:
            self.fade = clamp((t - 1.7) / .9, 0, 1)
        if t > 2.7:
            self.begin_hs_intro()

    def update_audio(self, dt):
        a = self.audio
        if not a.ok or self.mode != "park":
            return
        pos, f = self.camera()
        a.set_listener(pos[0], pos[2], self.cam_yaw_val)
        a.loop_at("fountain", FOUNT["x"], FOUNT["z"], .45, 30)
        a.loop_at("musicbox", CAR["x"], CAR["z"], .5, 40)
        a.loop_at("ferris", FER["x"], FER["z"], .3, 32)
        if self.train_wait <= 0:
            tx, tz = train_pos(self.train_th)
            a.loop_at("train", tx, tz, .55, 55)
        else:
            a.loop("train", 0)
        r = self.ride
        wind = 0.0
        ratchet = 0.0
        if r:
            k = r["kind"]
            if k == "coaster":
                wind = clamp(r["v"] / 28, 0, 1) * .65
                ratchet = .55 if r["s"] < COASTER["peak"] else 0.0
            elif k == "wride":
                wind = clamp(r["v"] / 28, 0, 1) * .55
            elif k == "swing":
                wind = .4
            elif k == "ferris":
                wind = clamp(ferris_vert(self.fer_ang, r["i"])[1] / 30, 0, .3)
            elif k == "carousel":
                wind = .12
        a.loop("wind", wind)
        a.loop("ratchet", ratchet)

    # ----------------------------------------------------------------- вид
    def camera(self):
        if self.ride:
            pos, byaw, bp = self.ride_pose()
            yaw = byaw + self.yaw
            pitch = clamp(bp + self.pitch, -1.5, 1.5)
            self.roll = self.cs_roll if self.ride["kind"] in ("coaster", "wride") else 0.0
        else:
            if self.mode in ("hs", "hs_scare", "hs_glitch"):
                yaw, pitch = self.view_yaw, self.view_pitch
                # head bobbing (как в Backrooms): ныряющий шаг, боковое покачивание, крен и кивок
                a = self.bob_amp if self.mode == "hs" else 0.0
                ph = self.walk_ph
                s = abs(math.sin(ph))
                br = math.sin(self.t * 1.25) * .006                   # дыхание в покое
                vy = a * .065 * (s ** .8 - .62) + br
                side = a * .04 * math.cos(ph)
                rgt = (math.cos(yaw), -math.sin(yaw))
                pos = (self.px + rgt[0] * side, self.gy + 1.65 + vy, self.pz + rgt[1] * side)
                pitch += a * (-.014 * (1 - s) + .004 * math.sin(2 * ph)) + br * .25
                self.roll = a * .016 * math.cos(ph) + math.sin(self.t * .7) * .0025
            else:
                bob = math.sin(self.walk_ph) * .045 if math.hypot(self.vx, self.vz) > .5 else 0
                pos = (self.px, self.gy + 1.65 + bob, self.pz)
                yaw, pitch = self.yaw, self.pitch
                self.roll = 0.0
        self.cam_yaw_val = yaw
        f = (-math.cos(pitch) * math.sin(yaw), math.sin(pitch), -math.cos(pitch) * math.cos(yaw))
        return pos, f

    def setup_view(self):
        RW, RH = self.RW, self.RH
        glViewport(0, 0, RW, RH)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, RW / RH, .15, 500)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        pos, f = self.camera()
        r = self.roll
        lx, lz = -math.cos(self.cam_yaw_val), math.sin(self.cam_yaw_val)
        up = (math.sin(r) * lx, math.cos(r), math.sin(r) * lz)
        gluLookAt(pos[0], pos[1], pos[2], pos[0] + f[0], pos[1] + f[1], pos[2] + f[2], *up)
        self.mv = glGetDoublev(GL_MODELVIEW_MATRIX)
        self.pj = glGetDoublev(GL_PROJECTION_MATRIX)
        self.vp = glGetIntegerv(GL_VIEWPORT)
        return pos

    def draw_sky(self, fog=FOG_COL, sky=SKY_TOP):
        # бледно-голубое небо над белой дымкой на горизонте (как на референсе)
        t = math.tan(math.radians(self.fov / 2))
        hy = clamp(.5 - .5 * math.tan(self.pitch if not self.ride else 0) / t, 0.0, 1.0)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, 1, 0, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_FOG)
        glDisable(GL_TEXTURE_2D)
        top = min(1.0, hy + .75)
        glBegin(GL_QUADS)
        glColor3f(*fog)
        glVertex2f(0, hy)
        glVertex2f(1, hy)
        glColor3f(*sky)
        glVertex2f(1, top)
        glVertex2f(0, top)
        glEnd()
        if top < 1.0:
            glBegin(GL_QUADS)
            glColor3f(*sky)
            glVertex2f(0, top)
            glVertex2f(1, top)
            glVertex2f(1, 1)
            glVertex2f(0, 1)
            glEnd()
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def render_park(self):
        glClearColor(*FOG_COL, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.draw_sky()
        glClear(GL_DEPTH_BUFFER_BIT)
        self.setup_view()
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (.62, .64, .70, 1))
        glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 1.0)
        glLightf(GL_LIGHT0, GL_LINEAR_ATTENUATION, 0.0)
        glLightf(GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 0.0)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (.62, .6, .55, 1))
        glLightfv(GL_LIGHT0, GL_POSITION, (.5, 1.0, .35, 0))
        glFogfv(GL_FOG_COLOR, FOG_COL + (1,))
        glFogf(GL_FOG_DENSITY, 0.0145)
        glEnable(GL_LIGHTING)
        glEnable(GL_FOG)
        glEnable(GL_DEPTH_TEST)
        glCallList(STATIC[0])
        r = self.ride
        draw_ferris(self.fer_ang, r["i"] if r and r["kind"] == "ferris" else -1)
        draw_carousel(self.car_phi, self.t)
        draw_swings(self.sw_ang, self.sw_tilt, r["i"] if r and r["kind"] == "swing" else -1)
        draw_balloons(self.t)
        draw_fountain_water(self.t)
        draw_door(self.door_open)
        draw_cart_train(self.cs, bool(r and r["kind"] == "coaster"))
        for k in range(4):
            th = self.train_th - k * 5.8 / RR
            x, z = train_pos(th)
            push(x, 0, z, ry=math.degrees(th))
            train_unit(k, bool(r and r["kind"] == "train" and k == 2))
            pop()
        draw_kinito(self.kx, self.kz, self.kyaw, self.t, self.kmoving)
        self.draw_games()
        if self.mg:
            self.draw_viewmodel()

    def render_world(self):
        """«Твой мир»: небо, свет и туман зависят от выбранного времени года."""
        w = self.world
        e = w.env
        glClearColor(*e["fog"], 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.draw_sky(e["fog"], e["sky"])
        glClear(GL_DEPTH_BUFFER_BIT)
        pos = self.setup_view()
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, tuple(e["amb"]) + (1,))
        glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 1.0)
        glLightf(GL_LIGHT0, GL_LINEAR_ATTENUATION, 0.0)
        glLightf(GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 0.0)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, tuple(e["dif"]) + (1,))
        glLightfv(GL_LIGHT0, GL_POSITION, (.5, 1.0, .35, 0))
        glFogfv(GL_FOG_COLOR, tuple(e["fog"]) + (1,))
        glFogf(GL_FOG_DENSITY, e["dens"])
        glEnable(GL_LIGHTING)
        glEnable(GL_FOG)
        glEnable(GL_DEPTH_TEST)
        w.draw(self.t, pos)
        r = self.ride
        if r and r["kind"] == "wride":
            draw_cart_train(r["s"], True, w.track)
        else:
            draw_cart_train(w.track["L"] - .8, False, w.track)          # вагончик, на котором мы приехали

    def render_hs(self):
        L = self.hs_light
        glClearColor(.01, .008, .006, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        pos = self.setup_view()
        hs = self.hs
        # общий свет: тусклый, слабое тёплое свечение вокруг игрока
        # всё вне луча фонаря - почти чёрное: видно только то, что освещено фонарём
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (.006, .005, .004, 1))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0, 0, 0, 1))
        glLightfv(GL_LIGHT0, GL_POSITION, (pos[0], pos[1] + .1, pos[2], 1))
        glFogfv(GL_FOG_COLOR, (.008, .006, .005, 1))
        glFogf(GL_FOG_DENSITY, .058)
        glEnable(GL_LIGHTING)
        glEnable(GL_FOG)
        glEnable(GL_DEPTH_TEST)
        glCallList(hs.list)
        jaw = clamp(1.15 - math.hypot(self.px - hs.kx, self.pz - hs.kz) / 6.0, 0.0, 1.0)
        draw_monster(hs.kx, hs.kz, hs.kyaw, self.t, hs.kmoving, jaw)
        self.flash_pass(pos, jaw)

    def flash_pass(self, pos, jaw):
        """Направленный свет фонаря: второй проход, где маска-конус проецируется на геометрию
        (попиксельно), поэтому граница светового круга чётко видна на стенах и полу."""
        hs = self.hs
        fy, fp = self.fl_yaw, self.fl_pitch
        fdir = np.array([-math.cos(fp) * math.sin(fy), math.sin(fp), -math.cos(fp) * math.cos(fy)])
        rgt = np.array([math.cos(fy), 0.0, -math.sin(fy)])
        fpos = np.array(pos, float) + rgt * .28 + np.array([0.0, -.22, 0.0])
        F = .3 + .7 * self.hs_light
        TM = PROJ_BIAS @ persp_m(62.0, 1.0, .1, 60.0) @ look_m(fpos, fdir) @ np.linalg.inv(np.array(self.mv, float).T)
        RESTORE[0] = False
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_CONSTANT_COLOR, GL_ONE)
        glBlendColor(.8 * F, .7 * F, .5 * F, 1)
        glDepthFunc(GL_LEQUAL)
        glDepthMask(GL_FALSE)
        glFogfv(GL_FOG_COLOR, (0, 0, 0, 1))
        glFogf(GL_FOG_DENSITY, .1)
        glClipPlane(GL_CLIP_PLANE0, (fdir[0], fdir[1], fdir[2], -float(fdir @ fpos) - .05))
        glEnable(GL_CLIP_PLANE0)
        glActiveTexture(GL_TEXTURE1)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, TEX["spot"])
        glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_COMBINE)
        glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_RGB, GL_MODULATE)
        glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_RGB, GL_PREVIOUS)
        glTexEnvi(GL_TEXTURE_ENV, GL_OPERAND0_RGB, GL_SRC_COLOR)
        glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE1_RGB, GL_TEXTURE)
        glTexEnvi(GL_TEXTURE_ENV, GL_OPERAND1_RGB, GL_SRC_COLOR)
        glTexEnvi(GL_TEXTURE_ENV, GL_COMBINE_ALPHA, GL_REPLACE)
        glTexEnvi(GL_TEXTURE_ENV, GL_SOURCE0_ALPHA, GL_PREVIOUS)
        glTexEnvi(GL_TEXTURE_ENV, GL_OPERAND0_ALPHA, GL_SRC_ALPHA)
        glTexEnvf(GL_TEXTURE_ENV, GL_RGB_SCALE, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()                                   # плоскости texgen - в координатах глаза
        for coord, plane in ((GL_S, (1, 0, 0, 0)), (GL_T, (0, 1, 0, 0)), (GL_R, (0, 0, 1, 0)), (GL_Q, (0, 0, 0, 1))):
            glTexGeni(coord, GL_TEXTURE_GEN_MODE, GL_EYE_LINEAR)
            glTexGenfv(coord, GL_EYE_PLANE, plane)
        glPopMatrix()
        for g in (GL_TEXTURE_GEN_S, GL_TEXTURE_GEN_T, GL_TEXTURE_GEN_R, GL_TEXTURE_GEN_Q):
            glEnable(g)
        glMatrixMode(GL_TEXTURE)
        glLoadMatrixd(np.ascontiguousarray(TM.T))
        glMatrixMode(GL_MODELVIEW)
        glActiveTexture(GL_TEXTURE0)
        glCallList(hs.list)
        draw_monster(hs.kx, hs.kz, hs.kyaw, self.t, hs.kmoving, jaw)
        # возврат состояния
        glActiveTexture(GL_TEXTURE1)
        for g in (GL_TEXTURE_GEN_S, GL_TEXTURE_GEN_T, GL_TEXTURE_GEN_R, GL_TEXTURE_GEN_Q):
            glDisable(g)
        glMatrixMode(GL_TEXTURE)
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glDisable(GL_TEXTURE_2D)
        glActiveTexture(GL_TEXTURE0)
        glDisable(GL_CLIP_PLANE0)
        glDepthMask(GL_TRUE)
        glDepthFunc(GL_LESS)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)
        RESTORE[0] = True

    def render_scene(self):
        glViewport(0, 0, self.RW, self.RH)
        if self.mode == "hs_intro":
            glClearColor(0, 0, 0, 1)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        elif self.mode in ("hs", "hs_scare", "hs_glitch"):
            self.render_hs()
        elif self.quiz:
            glClearColor(.07, .03, .16, 1)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        elif self.inw:
            self.render_world()
        else:
            self.render_park()

    # ------------------------------------------------------------- 2D / HUD
    def begin2d(self, w, h):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, w, h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_FOG)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def present(self):
        RW, RH = self.RW, self.RH
        glBindTexture(GL_TEXTURE_2D, self.fb)
        glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 0, 0, RW, RH)
        glViewport(0, 0, WIN_W, WIN_H)
        self.begin2d(WIN_W, WIN_H)
        u1, v1 = RW / 1024, RH / 1024

        def quad(ox, oy):
            glBegin(GL_QUADS)
            glTexCoord2f(0, v1)
            glVertex2f(ox, oy)
            glTexCoord2f(u1, v1)
            glVertex2f(WIN_W + ox, oy)
            glTexCoord2f(u1, 0)
            glVertex2f(WIN_W + ox, WIN_H + oy)
            glTexCoord2f(0, 0)
            glVertex2f(ox, WIN_H + oy)
            glEnd()

        def band(y0, y1, ox):
            va, vb = v1 * (1 - y0 / WIN_H), v1 * (1 - y1 / WIN_H)
            glBegin(GL_QUADS)
            glTexCoord2f(0, va)
            glVertex2f(ox, y0)
            glTexCoord2f(u1, va)
            glVertex2f(WIN_W + ox, y0)
            glTexCoord2f(u1, vb)
            glVertex2f(WIN_W + ox, y1)
            glTexCoord2f(0, vb)
            glVertex2f(ox, y1)
            glEnd()

        glDisable(GL_BLEND)
        glColor4f(1, 1, 1, 1)
        ca = 3 if self.mode != "hs" else 2
        if self.mode == "hs":
            # размытие кадра (сильнее при быстром повороте камеры) + хроматические каймы
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            bx = 3.0 + clamp(self.turn_w * 2.4, 0, 16)
            by = 2.5 + clamp(self.turn_p * 2.4, 0, 12)
            for i, (ox, oy, a) in enumerate(((0, 0, 1.0), (bx, 0, .5), (-bx, 0, .34), (0, by, .26), (0, -by, .2))):
                if i == 1:
                    glEnable(GL_BLEND)
                    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glColor4f(1, 1, 1, a)
                for mask, off in (((1, 0, 0, 1), -ca), ((0, 1, 0, 1), 0), ((0, 0, 1, 1), ca)):
                    glColorMask(*mask)
                    quad(ox + off, oy)
            glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
            glDisable(GL_BLEND)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        else:
            quad(0, 0)
            # хроматическая аберрация: красно-синие каймы, как на колесе обозрения на референсе
            glColorMask(GL_TRUE, GL_FALSE, GL_FALSE, GL_TRUE)
            quad(-ca, 0)
            glColorMask(GL_FALSE, GL_FALSE, GL_TRUE, GL_TRUE)
            quad(ca, 0)
            glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        if self.glitching or self.mode == "hs_scare":
            k = 14 if self.glitching else 4
            for _ in range(k):
                y0 = random.uniform(0, WIN_H)
                band(y0, y0 + random.uniform(6, 60), random.uniform(-90, 90))
        # лёгкое "размазывание" / пересвет
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        bloom = .20 if self.mode in ("park", "hs_intro") else .10
        glColor4f(1, 1, 1, bloom)
        quad(4, 0)
        glColor4f(1, 1, 1, bloom * .5)
        quad(-5, 2)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = load_font(size)
        return self.fonts[size]

    def mono(self, size, bold=False):
        return self.font(size)

    def text_tex(self, text, size, color, outline, mono=False):
        key = (text, size, color, outline, mono)
        if key in self.text_cache:
            return self.text_cache[key]
        f = self.mono(size, True) if mono else self.font(size)
        base = f.render(text, True, color)
        w, h = base.get_size()
        surf = pygame.Surface((w + 6, h + 6), pygame.SRCALPHA)
        if outline:
            o = f.render(text, True, outline)
            for ox in (0, 3, 6):
                for oy in (0, 3, 6):
                    surf.blit(o, (ox, oy))
        surf.blit(base, (3, 3))
        data = pygame.image.tobytes(surf, "RGBA", True)
        tid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w + 6, h + 6, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        self.text_cache[key] = (tid, w + 6, h + 6)
        return self.text_cache[key]

    def rect(self, x, y, w, h, rgba):
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        glColor4f(*rgba)
        glBegin(GL_QUADS)
        glVertex2f(x, y)
        glVertex2f(x + w, y)
        glVertex2f(x + w, y + h)
        glVertex2f(x, y + h)
        glEnd()

    def text(self, s, size, x, y, color=(255, 255, 255), outline=(40, 20, 80), align="center",
             alpha=1.0, mono=False):
        tid, w, h = self.text_tex(s, size, color, outline, mono)
        if align == "center":
            x -= w / 2
        elif align == "right":
            x -= w
        glBindTexture(GL_TEXTURE_2D, tid)
        glColor4f(1, 1, 1, alpha)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1)
        glVertex2f(x, y)
        glTexCoord2f(1, 1)
        glVertex2f(x + w, y)
        glTexCoord2f(1, 0)
        glVertex2f(x + w, y + h)
        glTexCoord2f(0, 0)
        glVertex2f(x, y + h)
        glEnd()
        return w, h

    def tex_quad(self, tid, x, y, w, h, rgba=(1, 1, 1, 1), uv=(0, 0, 1, 1)):
        glBindTexture(GL_TEXTURE_2D, tid)
        glColor4f(*rgba)
        u0, v0, u1, v1 = uv
        glBegin(GL_QUADS)
        glTexCoord2f(u0, v1)
        glVertex2f(x, y)
        glTexCoord2f(u1, v1)
        glVertex2f(x + w, y)
        glTexCoord2f(u1, v0)
        glVertex2f(x + w, y + h)
        glTexCoord2f(u0, v0)
        glVertex2f(x, y + h)
        glEnd()

    def draw_bubble(self):
        b = self.bub
        if not b or self.mode != "park":
            return
        w, h = self.build_bubble(b)
        pt = None
        if not self.ride:
            pt = self.project(self.kx, 2.05, self.kz)
        ax, ay = pt if pt else (WIN_W / 2, h + 30)
        x = clamp(ax - w / 2, 10, WIN_W - w - 10)
        y = clamp(ay - h, 10, WIN_H - h - 80)
        self.tex_quad(self.bub_tex, int(x), int(y), w, h)

    def draw_overlay_hs(self):
        W, H = WIN_W, WIN_H
        # зерно + виньетка
        g = np.random.randint(0, 255, (96, 96, 1), dtype=np.uint8)
        grain = np.concatenate([g, g, g, np.full_like(g, 255)], axis=2)
        glBindTexture(GL_TEXTURE_2D, TEX["grain"])
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 96, 96, GL_RGBA, GL_UNSIGNED_BYTE, np.ascontiguousarray(grain))
        ox, oy = random.random(), random.random()
        glBindTexture(GL_TEXTURE_2D, TEX["grain"])
        glColor4f(1, 1, 1, .10)
        glBegin(GL_QUADS)
        for (vx, vy), (u, v) in zip(((0, 0), (W, 0), (W, H), (0, H)),
                                     ((ox, oy), (ox + W / 288, oy), (ox + W / 288, oy + H / 288), (ox, oy + H / 288))):
            glTexCoord2f(u, v)
            glVertex2f(vx, vy)
        glEnd()
        self.tex_quad(TEX["vignette"], 0, 0, W, H, (1, 1, 1, .95), (0, 0, 1, 1))

    def draw_scare(self):
        W, H = WIN_W, WIN_H
        t = self.scare_t
        sh = (random.uniform(-14, 14), random.uniform(-10, 10))
        sc = 1.0 + min(t, .5) * .5
        h = H * sc
        w = h * 177 / 131
        red = (1, .55, .55, 1) if int(t * 24) % 2 == 0 else (1, 1, 1, 1)
        self.rect(0, 0, W, H, (0, 0, 0, 1))
        self.tex_quad(TEX["scare"], W / 2 - w / 2 + sh[0], H / 2 - h / 2 + sh[1], w, h, red)
        # красные вспышки
        if random.random() < .5:
            self.rect(0, 0, W, H, (1, 0, 0, random.uniform(.05, .3)))

    def draw_glitch(self):
        W, H = WIN_W, WIN_H
        t = self.glitch_t
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        for _ in range(45):
            x = random.uniform(-50, W)
            y = random.uniform(0, H)
            w = random.uniform(30, 420)
            h = random.uniform(2, 30)
            c = random.choice(((1, 0, 0), (0, 1, 1), (0, 0, 0), (1, 1, 1), (1, 0, 1)))
            glColor4f(*c, random.uniform(.25, .8))
            glBegin(GL_QUADS)
            glVertex2f(x, y)
            glVertex2f(x + w, y)
            glVertex2f(x + w, y + h)
            glVertex2f(x, y + h)
            glEnd()
        glColor4f(0, 0, 0, .35)
        glBegin(GL_LINES)
        for y in range(0, H, 4):
            glVertex2f(0, y)
            glVertex2f(W, y)
        glEnd()
        glEnable(GL_TEXTURE_2D)
        if random.random() < .6:
            self.rect(0, 0, W, H, (random.choice((1, 0)), 0, 0, random.uniform(.05, .35)))
        if t > .3:
            self.rect(W / 2 - 260, H / 2 - 38, 520, 76, (0, 0, 0, .8))
            self.text("KinitoPET.exe: connection lost", 26, W / 2, H / 2 - 22, (255, 60, 60), None,
                      mono=True, alpha=.7 + .3 * random.random())
        k = clamp((t - 2.0) / .8, 0, 1)
        if k > 0:
            self.rect(0, 0, W, H, (0, 0, 0, k))

    def draw_intro(self):
        W, H = WIN_W, WIN_H
        self.rect(0, 0, W, H, (0, 0, 0, 1))
        t = self.intro_t
        if t < 3.6:
            on = int(t * 2) % 2 == 0 or t < 1.5
            clock = "10:59" if t < 1.6 else "11:00"
            col = (210, 30, 30)
            if t >= 1.6 and int(t * 8) % 2:
                col = (255, 120, 120)
            if on or t >= 1.6:
                self.text(clock, 120, W / 2, H / 2 - 90, col, None, mono=True)
        if t > 3.9:
            msg1 = "something is seeking you."
            msg2 = "DONT GET CAUGHT"
            n1 = int((t - 3.9) * 22)
            n2 = int((t - 5.4) * 16)
            self.text(msg1[:n1], 34, W / 2, H / 2 - 40, (230, 230, 230), None, mono=True)
            if n2 > 0:
                flick = .6 + .4 * random.random()
                self.text(msg2[:n2], 40, W / 2, H / 2 + 20, (220, 20, 20), None, mono=True, alpha=flick)

    def hud(self):
        W, H = WIN_W, WIN_H
        self.begin2d(W, H)
        mode = self.mode
        if mode == "hs_intro":
            self.draw_intro()
            return
        if mode in ("hs", "hs_scare", "hs_glitch"):
            self.draw_overlay_hs()
        if mode == "hs_scare":
            self.draw_scare()
        elif mode == "hs_glitch":
            self.draw_glitch()
        elif mode == "park" and self.quiz:
            if self.quiz.get("phase") == "paint":
                self.hud_paint()
            else:
                self.hud_quiz()
        elif self.show_hud and mode == "park":
            # прицел - маленький полый круг (в Hide and Seek прицела нет)
            px = PIX_SCALES[self.scale_i]
            s = 8
            self.tex_quad(TEX["cross"], round(W / 2 - s / 2), round(H / 2 - s / 2), s, s)
            self.hud_park()
        if self.wflash > 0:
            self.rect(0, 0, W, H, (1, 1, 1, clamp(self.wflash, 0, 1)))
        if self.fade > 0:
            self.rect(0, 0, W, H, (0, 0, 0, clamp(self.fade, 0, 1)))

    def hud_park(self):
        W, H = WIN_W, WIN_H
        if self.ride:
            k = self.ride["kind"]
            hint = {"ferris": "[E] Выйти (когда кабинка внизу)",
                    "carousel": "[E] Слезть с лошадки",
                    "swing": "[E] Слезть",
                    "coaster": "Держись! Мышь - осмотреться",
                    "wride": "Мышь - осмотреться",
                    "train": "Поезд едет по кругу. Мышь - осмотреться"}[k]
            self.rect(W / 2 - 280, H - 70, 560, 42, (0, 0, 0, .45))
            self.text(hint, 24, W / 2, H - 66, outline=None)
        elif self.mg:
            self.hud_mg()
            self.draw_bubble()
            return
        elif not self.seq and not self.wtrans:
            c = self.candidates()
            if c:
                kind = c[0][1]
                s = {"train": "[E] Сесть в поезд", "door": "[E] Открыть белую дверь",
                     "kinito": "[E] Поговорить с Кинито", "shoot": "[E] Играть в тир",
                     "mole": "[E] Играть: Попади по кроту",
                     "wreturn": "[E] Вернуться в парк"}.get(kind, "[E] Прокатиться: " + c[0][2])
                if kind.startswith("spot"):
                    s = "[E] Осмотреть: " + c[0][2]
                elif kind.startswith("wdoor"):
                    d = self.world.doors[int(kind[5:])]
                    s = "[E] Закрыть дверь" if d["open"] else "[E] Открыть дверь"
                self.rect(W / 2 - 280, H - 70, 560, 42, (0, 0, 0, .5))
                self.text(s, 24, W / 2, H - 66, outline=None)
                if self.inw or kind in ("door", "kinito"):         # курсор-«рука» над интерактивным
                    hs = 40
                    self.tex_quad(TEX["hand"], W // 2 + 4, H // 2 + 2, hs, hs)
        self.draw_bubble()
        tt = self.t - self.park_t0
        if tt < 28 and not self.shot and not self.inw:
            a = clamp((28 - tt) / 4, 0, 1)
            self.text("WASD - ходить   Shift - бежать   ПКМ - зум   E - действие   F2 - пиксели   Esc - выход",
                      14, 12, H - 28, (255, 255, 255), (60, 30, 120), "left", a)
        if tt < 7 and not self.shot:
            fade = clamp(1 - tt / 3.0, 0, 1)
            self.rect(0, 0, W, H, (1, 1, 1, fade))
            ta = clamp((7 - tt) / 2, 0, 1) * clamp(tt / 1.0, 0, 1)
            self.text("KINITO PARK", 84, W / 2, H / 2 - 90, (255, 214, 40), (86, 30, 158), alpha=ta)
            self.text("Добро пожаловать!", 34, W / 2, H / 2 + 20, (255, 255, 255), (150, 30, 90), alpha=ta)

    # ------------------------------------------------------------- главный цикл
    def run(self):
        running = True
        frame = 0
        while running:
            dt = min(self.clock.tick(120) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif self.quiz and self.quiz.get("phase") == "paint" and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.paint_finish()
                    elif self.quiz and self.quiz.get("phase") != "paint" and pygame.K_1 <= e.key <= pygame.K_4:
                        self.quiz_pick(e.key - pygame.K_1)
                    elif self.quiz and self.quiz.get("phase") != "paint" and pygame.K_KP1 <= e.key <= pygame.K_KP4:
                        self.quiz_pick(e.key - pygame.K_KP1)
                    elif e.key == pygame.K_e:
                        self.interact()
                    elif e.key == pygame.K_F2:
                        self.scale_i = (self.scale_i + 1) % len(PIX_SCALES)
                        s = PIX_SCALES[self.scale_i]
                        self.RW, self.RH = WIN_W // s, WIN_H // s
                    elif e.key == pygame.K_F1:
                        self.show_hud = not self.show_hud
                    elif e.key == pygame.K_m:
                        self.audio.toggle_mute()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.quiz and self.quiz.get("phase") == "paint":
                        self.paint_pointer(e.pos, "down")
                    else:
                        self.click()
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.quiz and self.quiz.get("phase") == "paint":
                    self.paint_pointer(e.pos, "up")
                elif e.type == pygame.MOUSEMOTION and self.quiz and self.quiz.get("phase") == "paint":
                    self.paint_pointer(e.pos, "move")
            if self.shot:
                dt = 1 / 60
            self.update(dt)
            self.render_scene()
            self.present()
            self.hud()
            frame += 1
            if self.shot and frame >= self.shot_frames:
                data = glReadPixels(0, 0, WIN_W, WIN_H, GL_RGB, GL_UNSIGNED_BYTE)
                surf = pygame.image.frombuffer(data, (WIN_W, WIN_H), "RGB")
                pygame.image.save(pygame.transform.flip(surf, False, True), self.shot)
                running = False
            pygame.display.flip()
            if frame % 30 == 0:
                pygame.display.set_caption("KINITO PARK  -  %d fps" % self.clock.get_fps())
        pygame.quit()


if __name__ == "__main__":
    Game(sys.argv[1:]).run()
