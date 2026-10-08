# -*- coding: utf-8 -*-
"""
«ТВОЙ МИР» (Your World) - домик игрока из финала KinitoPET.

В начале игры Кинито задаёт вопросы (любимое время года и любимая еда). Когда американские горки
доезжают до шестиугольной «дырки» в шахматной стене, игрок попадает в мир, который зависит от
выбранного сезона: сначала горки летят над лесом, потом приезжают к двухэтажному дому
(синяя обшивка, красная крыша, солнышко на фронтоне). Цвета, свет, погода и настроение комнат
зависят от времени года, на столе стоит любимая еда, на стенах висят «рисунки игрока».
"""
import math
import os
import random

import numpy as np
import pygame
from OpenGL.GL import *

from gfx import *

NOROOF = bool(os.environ.get("YW_NOROOF"))      # отладка: без крыши (вид сверху)
WX, WZ = 800.0, 0.0                    # центр мира игрока (далеко от парка)
HW, HD = 9.0, 7.5                      # полуразмеры дома по x и z (фасад смотрит в +z)
F1 = 4.0                               # уровень пола 2-го этажа
H0 = 3.8                               # потолок 1-го этажа
H1 = 7.95                              # потолок 2-го этажа
SX0 = 6.55                             # лестница занимает x от SX0 до HW
SZ0, SZ1 = 5.9, -1.9                   # низ и верх лестницы по z
DOOR_X = -1.8                          # входная дверь на фасаде (к ней ведут горки)
AX = 0.9                               # перегородка: гостиная | кухня
BZ = -4.15                             # перегородка: комнаты | холл (холл ближе к -z)
RX = -0.35                             # перегородка: спальня | ванная и прачечная
LZ = 1.7                               # перегородка: ванная | прачечная
BED_DX, BATH_DX, LAUN_DZ = -5.4, 2.9, 4.6
DOOR_Z = HD
LAND_Z = 26.0                          # конец путей (посадка)

SEASONS = ["Весна", "Лето", "Осень", "Зима"]
SEASON_ACC = ["весну", "лето", "осень", "зиму"]
SEASON_NOM = ["весна", "лето", "осень", "зима"]
FOODS = ["Пицца", "Бургер", "Суши", "Торт"]
FOOD_LOW = ["пицца", "бургер", "суши", "торт"]

ENV = [   # туман/небо/земля/свет по сезонам
    dict(fog=(.93, .95, .96), sky=(.70, .84, 1.0), ground=(.50, .76, .42), amb=(.54, .54, .57), dif=(.50, .47, .46), dens=.0075),
    dict(fog=(1.0, .97, .86), sky=(.50, .78, 1.0), ground=(.42, .72, .30), amb=(.58, .57, .50), dif=(.66, .60, .44), dens=.0065),
    dict(fog=(.93, .80, .58), sky=(.96, .80, .52), ground=(.50, .44, .16), amb=(.62, .50, .38), dif=(.78, .56, .30), dens=.0100),
    dict(fog=(.80, .86, .95), sky=(.66, .74, .92), ground=(.80, .86, .96), amb=(.54, .60, .76), dif=(.56, .62, .84), dens=.0095),
]
PAL = [   # цвета дома и комнат по сезонам
    dict(wall=(.58, .76, .98), roof=(.86, .46, .58), inner=(.92, .78, .86), floor=(.78, .56, .44), carpet=(.70, .64, .86),
         sofa=(.50, .52, .88), rug=(.95, .6, .7), bed=(1.0, .86, .5)),
    dict(wall=(.36, .64, .96), roof=(.90, .30, .22), inner=(.96, .88, .60), floor=(.80, .58, .36), carpet=(.56, .78, .92),
         sofa=(.20, .42, .88), rug=(.98, .76, .3), bed=(1.0, .92, .1)),
    dict(wall=(.22, .46, .76), roof=(.80, .12, .12), inner=(.96, .82, .66), floor=(.52, .35, .26), carpet=(.70, .78, .92),
         sofa=(.20, .36, .78), rug=(.78, .36, .2), bed=(.90, .90, .1)),
    dict(wall=(.58, .68, .84), roof=(.58, .42, .36), inner=(.87, .91, .98), floor=(.60, .46, .38), carpet=(.82, .90, .98),
         sofa=(.36, .46, .72), rug=(.42, .56, .84), bed=(.82, .9, 1.0)),
]
WOOD = (.62, .42, .28)
DWOOD = (.34, .24, .17)
K_HEAD = (.86, .60, .93)
K_GILL = (.92, .22, .74)

# маршрут горок над лесом до дома (относительно центра мира)
WTRACK_REL = [(-70, 38, -250), (-30, 34, -210), (20, 30, -165), (62, 26, -120), (80, 28, -72), (86, 22, -26),
              (74, 14, 12), (52, 9, 36), (30, 6, 58), (8, 3.6, 68), (DOOR_X, 2.2, 56), (DOOR_X, 1.25, 42), (DOOR_X, 1.25, 30)]


# ----------------------------------------------------------------------------
# Трек (общий для парковых горок и горок над лесом)
# ----------------------------------------------------------------------------
def make_track(pts, sigma_m=3.0, ds=.25, min_y=1.0):
    """Открытый гладкий трек по контрольным точкам (Catmull-Rom + сглаживание)."""
    P = np.array(pts, float)
    n = len(P)
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, n):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        k = max(4, int(np.linalg.norm(p2 - p1) / ds))
        for j in range(k):
            t = j / k
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    S = np.array(out)
    S[:, 1] = np.maximum(S[:, 1], min_y)

    def smooth(a, sig):
        half = int(sig * 3)
        k = np.exp(-0.5 * (np.arange(-half, half + 1) / sig) ** 2)
        k /= k.sum()
        pad = np.pad(a, ((half, half), (0, 0)), mode="edge")
        return np.stack([np.convolve(pad[:, d], k, "valid") for d in range(a.shape[1])], axis=1)

    S = smooth(S, max(2.0, sigma_m / ds))
    seg = np.linalg.norm(np.diff(S, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = float(cum[-1])
    N = int(L / ds)
    ss = np.linspace(0, L, N + 1)
    R = np.stack([np.interp(ss, cum, S[:, d]) for d in range(3)], axis=1)
    T = np.gradient(R, axis=0)
    T = smooth(T, 14)
    T /= (np.linalg.norm(T, axis=1, keepdims=True) + 1e-9)
    return dict(P=R, TAN=T, L=L, N=N, ds=L / N, peak=float(ss[int(np.argmax(R[:, 1]))]), ymax=float(R[:, 1].max()))


def track_at(T, s):
    P, TAN, N, ds = T["P"], T["TAN"], T["N"], T["ds"]
    if s <= 0:
        p = P[0] + TAN[0] * s
        return (float(p[0]), float(p[1]), float(p[2])), (float(TAN[0][0]), float(TAN[0][1]), float(TAN[0][2]))
    if s >= T["L"]:
        p = P[-1] + TAN[-1] * (s - T["L"])
        return (float(p[0]), float(p[1]), float(p[2])), (float(TAN[-1][0]), float(TAN[-1][1]), float(TAN[-1][2]))
    f = s / ds
    i = min(int(f), N - 1)
    fr = f - i
    pos = P[i] + (P[i + 1] - P[i]) * fr
    t = TAN[i] + (TAN[i + 1] - TAN[i]) * fr
    t = t / (np.linalg.norm(t) + 1e-9)
    return (float(pos[0]), float(pos[1]), float(pos[2])), (float(t[0]), float(t[1]), float(t[2]))


def build_track_geom(T, supports=True, skip=None, coll=None):
    """Рельсы, шпалы и опоры вдоль трека (вызывать внутри display list)."""
    P, N = T["P"], T["N"]
    step = 4
    for i in range(0, N - step + 1, step):
        a, b = P[i], P[i + step]
        t = b - a
        ln = math.hypot(t[0], t[2]) + 1e-9
        sx, sz = -t[2] / ln * .65, t[0] / ln * .65
        for k in (-1, 1):
            beam((a[0] + sx * k, a[1], a[2] + sz * k), (b[0] + sx * k, b[1], b[2] + sz * k), .2, (.95, .95, .98))
        beam((a[0], a[1] - .55, a[2]), (b[0], b[1] - .55, b[2]), .38, RED)
        if (i // step) % 2 == 0:
            beam((a[0] + sx * 1.3, a[1] - .1, a[2] + sz * 1.3), (a[0] - sx * 1.3, a[1] - .1, a[2] - sz * 1.3), .14, BLUE)
        if supports and (i // step) % 7 == 0 and a[1] > 2.6 and not (skip and skip(a)):
            h = a[1] - .75
            obj("box", a[0], h / 2, a[2], .5, h, .5, WHITE if (i // step // 7) % 2 else BLUE)
            if coll is not None:
                coll.append((float(a[0]), float(a[2]), .45))
            if (i // step // 7) % 3 == 0 and h > 5:
                beam((a[0], h * .15, a[2]), (a[0], h * .85, a[2] + 2.2), .2, WHITE)


# ----------------------------------------------------------------------------
# Портал: шестиугольная «дырка» в шахматной стене в конце парковых горок
# ----------------------------------------------------------------------------
def _hex(r, k):
    a = math.radians(30 + 60 * k)
    return r * math.cos(a), r * math.sin(a)


def build_portal(center, fwd, coll=None):
    """Огромная шахматная стена с шестиугольным отверстием и тоннелем из красно-синих колец.
    center - точка трека (x,y,z) в отверстии, fwd - горизонтальное направление движения."""
    cx, cy, cz = center
    fx, fz = fwd
    n = math.hypot(fx, fz)
    fx, fz = fx / n, fz / n
    sx, sz = -fz, fx                                   # вбок

    def W(a, b, d):
        return (cx + sx * a + fx * d, cy + 1.1 + b, cz + sz * a + fz * d)
    R_IN, R_OUT, DEPTH, NR = 3.6, 12.7, 18.0, 12
    glColor3f(1, 1, 1)
    glBindTexture(GL_TEXTURE_2D, TEX["checker"])
    glNormal3f(-fx, 0, -fz)
    glBegin(GL_QUADS)
    for k in range(6):
        a0, b0 = _hex(R_IN, k)
        a1, b1 = _hex(R_IN, k + 1)
        c0, d0 = _hex(R_OUT, k)
        c1, d1 = _hex(R_OUT, k + 1)
        # разбиваем кольцо на мелкие четырёхугольники (туман по вершинам)
        m = 6
        for i in range(m):
            for j in range(3):
                def pt(u, v):
                    ia, ib = a0 + (a1 - a0) * u, b0 + (b1 - b0) * u
                    oa, ob = c0 + (c1 - c0) * u, d0 + (d1 - d0) * u
                    return ia + (oa - ia) * v, ib + (ob - ib) * v
                for u, v in ((i / m, j / 3), ((i + 1) / m, j / 3), ((i + 1) / m, (j + 1) / 3), (i / m, (j + 1) / 3)):
                    a, b = pt(u, v)
                    glTexCoord2f(a / 3.0, b / 3.0)
                    glVertex3f(*W(a, b, 0))
    glEnd()
    # тоннель
    glBindTexture(GL_TEXTURE_2D, TEX["white"])
    for r in range(NR):
        d0, d1 = DEPTH * r / NR, DEPTH * (r + 1) / NR
        r0, r1 = R_IN * (1 - .035 * r), R_IN * (1 - .035 * (r + 1))
        col = (.9, .1, .16) if r % 2 == 0 else (.12, .16, .9)
        glColor3f(*col)
        glBegin(GL_QUADS)
        for k in range(6):
            a0, b0 = _hex(r0, k)
            a1, b1 = _hex(r0, k + 1)
            c0, d_0 = _hex(r1, k)
            c1, d_1 = _hex(r1, k + 1)
            am = a0 + a1
            bm = b0 + b1
            ln = math.hypot(am, bm) + 1e-9
            nx, nz = -am / ln, -bm / ln
            glNormal3f(sx * nx, nz, sz * nx)
            glVertex3f(*W(a0, b0, d0))
            glVertex3f(*W(a1, b1, d0))
            glVertex3f(*W(c1, d_1, d1))
            glVertex3f(*W(c0, d_0, d1))
        glEnd()
    # светящийся конец тоннеля
    glDisable(GL_LIGHTING)
    glColor3f(1, 1, 1)
    glBegin(GL_POLYGON)
    for k in range(6):
        a, b = _hex(R_IN * (1 - .035 * NR) * 1.02, k)
        glVertex3f(*W(a, b, DEPTH))
    glEnd()
    glEnable(GL_LIGHTING)
    if coll is not None:
        for a in np.arange(-R_OUT * .87, R_OUT * .87 + .1, 1.8):
            if abs(a) > R_IN + 1.2:
                coll.append((cx + sx * float(a), cz + sz * float(a), 1.3))


# ----------------------------------------------------------------------------
# Текстуры
# ----------------------------------------------------------------------------
PAPER = (250, 243, 222)


def _wob(p, rng, j=1.1):
    return p[0] + rng.uniform(-j, j), p[1] + rng.uniform(-j, j)


def _line(s, rng, a, b, col, w=3):
    n = max(2, int(math.dist(a, b) / 6))
    pts = [_wob((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n), rng) for i in range(n + 1)]
    pygame.draw.lines(s, col, False, pts, w)


def _circ(s, rng, c, r, col, w=3, fill=None):
    pts = [(c[0] + math.cos(a) * r * (1 + rng.uniform(-.05, .05)),
            c[1] + math.sin(a) * r * (1 + rng.uniform(-.05, .05))) for a in np.linspace(0, TAU, 18)]
    if fill:
        pygame.draw.polygon(s, fill, pts)
    pygame.draw.lines(s, col, True, pts, w)


def _kinito_doodle(s, rng, cx, cy, r, big=False):
    _circ(s, rng, (cx, cy), r, (150, 60, 150), 3, (222, 153, 238))
    for sg in (-1, 1):
        for k in range(3):
            _line(s, rng, (cx + sg * r * .9, cy + (k - 1) * r * .35),
                  (cx + sg * r * (1.55 + k * .08), cy - r * .8 + k * r * .75), (235, 56, 190), 3)
        ex = cx + sg * r * .42
        pygame.draw.ellipse(s, (255, 255, 255), (ex - r * .28, cy - r * .1, r * .56, r * .4))
        pygame.draw.circle(s, (0, 0, 0), (int(ex), int(cy + r * .12)), max(2, int(r * .11)))
        pygame.draw.line(s, (120, 40, 120), (ex - r * .3, cy - r * .08), (ex + r * .3, cy - r * .08), 2)
    if big:
        pygame.draw.ellipse(s, (20, 0, 20), (cx - r * .35, cy + r * .45, r * .7, r * .45))


def make_textures():
    rng = np.random.default_rng(5)
    # деревянный пол (нейтральный, красится цветом сезона)
    H = W = 64
    img = np.zeros((H, W, 3), int)
    for row in range(8):
        y0 = row * 8
        v = 215 + int(rng.integers(-25, 25))
        img[y0:y0 + 7, :] = (v, v - 12, v - 28)
        img[y0 + 7, :] = (120, 100, 84)
        sx = int(rng.integers(0, W))
        img[y0:y0 + 8, sx] = (120, 100, 84)
    img += rng.integers(-8, 9, (H, W, 1))
    upload("hfloor", to_rgba(img), W, H)

    # дверь как в KinitoPET: деревянные панели
    d = pygame.Surface((64, 128))
    d.fill((120, 72, 42))
    for _ in range(260):
        x = int(rng.integers(0, 64))
        y = int(rng.integers(0, 128))
        c = int(rng.integers(-18, 18))
        d.set_at((x, y), (120 + c, 72 + c, 42 + c))
    for (x, y, w, h) in ((8, 8, 20, 44), (36, 8, 20, 44), (8, 62, 20, 58), (36, 62, 20, 58)):
        pygame.draw.rect(d, (86, 50, 28), (x, y, w, h))
        pygame.draw.rect(d, (150, 96, 60), (x + 2, y + 2, w - 4, h - 4), 1)
        pygame.draw.rect(d, (104, 62, 36), (x + 3, y + 3, w - 6, h - 6))
    pygame.draw.rect(d, (70, 40, 22), (0, 0, 64, 128), 2)
    upload("hdoor", pygame.image.tobytes(d, "RGBA", True), 64, 128, mip=False, repeat=False)

    # солнышко на фронтоне
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.circle(s, (240, 170, 20), (32, 32), 31)
    pygame.draw.circle(s, (255, 228, 40), (32, 32), 28)
    for sg in (-1, 1):
        pygame.draw.ellipse(s, (60, 40, 10), (32 + sg * 11 - 3, 18, 6, 12))
        pygame.draw.circle(s, (255, 150, 90), (32 + sg * 18, 36), 4)
    pygame.draw.arc(s, (60, 40, 10), (16, 20, 32, 28), math.pi * 1.1, math.pi * 1.9, 3)
    upload("sun", pygame.image.tobytes(s, "RGBA", True), 64, 64, mip=False, repeat=False)

    # курсор-«рука» (белый контур, как в KinitoPET при наведении на интерактивное)
    h = pygame.Surface((24, 24), pygame.SRCALPHA)
    poly = [(8, 3), (10, 1), (12, 3), (12, 10), (14, 9), (16, 11), (18, 11), (20, 13), (20, 18), (17, 22), (9, 22),
            (6, 18), (3, 13), (5, 12), (8, 15)]
    pygame.draw.polygon(h, (20, 10, 40, 255), [(x + 1, y + 1) for x, y in poly], 2)
    pygame.draw.polygon(h, (255, 255, 255, 255), poly, 2)
    upload("hand", pygame.image.tobytes(h, "RGBA", True), 24, 24, mip=False, repeat=False)

    # «рисунки игрока» (детские рисунки цветными карандашами)
    r = random.Random(21)

    def new():
        s = pygame.Surface((128, 96))
        s.fill(PAPER)
        for _ in range(70):
            s.set_at((r.randrange(128), r.randrange(96)), (234, 226, 204))
        return s

    def fin(i, s):
        pygame.draw.rect(s, (130, 108, 84), (0, 0, 128, 96), 1)
        upload("draw%d" % i, pygame.image.tobytes(s, "RGBA", True), 128, 96, mip=False, repeat=False)

    s = new()                                                    # 0: солнце и домик
    _circ(s, r, (24, 22), 11, (240, 170, 20), 3, (255, 224, 60))
    for a in range(8):
        ang = a * TAU / 8
        _line(s, r, (24 + math.cos(ang) * 14, 22 + math.sin(ang) * 14), (24 + math.cos(ang) * 21, 22 + math.sin(ang) * 21),
              (240, 170, 20), 2)
    _line(s, r, (0, 82), (128, 84), (60, 160, 60), 4)
    pygame.draw.rect(s, (210, 60, 50), (58, 48, 44, 34))
    pygame.draw.polygon(s, (130, 50, 40), [(54, 50), (80, 28), (106, 50)])
    pygame.draw.rect(s, (100, 70, 40), (74, 62, 12, 20))
    pygame.draw.rect(s, (120, 200, 240), (90, 56, 8, 8))
    fin(0, s)
    s = new()                                                    # 1: Кинито
    _kinito_doodle(s, r, 64, 34, 24)
    for sg in (-1, 1):
        _line(s, r, (64 + sg * 8, 58), (64 + sg * 10, 90), (40, 20, 60), 3)
        _line(s, r, (64 + sg * 10, 90), (64 + sg * 22, 91), (40, 20, 60), 3)
    fin(1, s)
    s = new()                                                    # 2: мы с Кинито за руки
    _circ(s, r, (108, 16), 8, (240, 170, 20), 2, (255, 224, 60))
    _circ(s, r, (30, 40), 8, (30, 60, 160), 3, (255, 214, 170))
    _line(s, r, (30, 48), (30, 72), (30, 60, 160), 3)
    _line(s, r, (30, 72), (24, 90), (30, 60, 160), 3)
    _line(s, r, (30, 72), (38, 90), (30, 60, 160), 3)
    _line(s, r, (30, 54), (64, 60), (30, 60, 160), 3)
    _kinito_doodle(s, r, 92, 36, 14)
    _line(s, r, (92, 50), (92, 72), (40, 20, 60), 3)
    _line(s, r, (92, 72), (86, 92), (40, 20, 60), 3)
    _line(s, r, (92, 72), (100, 92), (40, 20, 60), 3)
    _line(s, r, (92, 56), (64, 60), (40, 20, 60), 3)
    pygame.draw.polygon(s, (230, 40, 70), [(64, 36), (58, 28), (62, 22), (64, 26), (66, 22), (70, 28)])
    fin(2, s)
    s = new()                                                    # 3: дерево и радуга
    for i, c in enumerate(((230, 40, 40), (250, 150, 30), (250, 220, 40), (60, 180, 70), (60, 120, 230))):
        pygame.draw.arc(s, c, (30 + i * 4, 18 + i * 4, 96 - i * 8, 88 - i * 8), 0, math.pi, 3)
    pygame.draw.rect(s, (110, 74, 40), (24, 58, 9, 32))
    _circ(s, r, (28, 46), 19, (30, 110, 40), 3, (80, 180, 70))
    for ax, ay in ((20, 40), (34, 50), (26, 54), (36, 38)):
        pygame.draw.circle(s, (220, 30, 30), (ax, ay), 3)
    _line(s, r, (0, 90), (128, 90), (60, 160, 60), 3)
    fin(3, s)
    s = new()                                                    # 4: кошка
    _circ(s, r, (64, 52), 22, (200, 110, 30), 3, (250, 170, 70))
    for sg in (-1, 1):
        pygame.draw.polygon(s, (250, 170, 70), [(64 + sg * 10, 36), (64 + sg * 24, 34), (64 + sg * 20, 18)])
        _line(s, r, (64 + sg * 10, 36), (64 + sg * 20, 18), (200, 110, 30), 3)
        pygame.draw.circle(s, (20, 20, 20), (64 + sg * 9, 48), 3)
        for k in range(3):
            _line(s, r, (64 + sg * 8, 58 + k * 2), (64 + sg * 32, 54 + k * 6), (40, 40, 40), 1)
    pygame.draw.polygon(s, (240, 90, 120), [(61, 56), (67, 56), (64, 60)])
    fin(4, s)
    s = new()                                                    # 5: огромный Кинито и крошечный человечек
    _kinito_doodle(s, r, 70, 46, 40, big=True)
    pygame.draw.ellipse(s, (10, 0, 10), (50, 40, 16, 22))
    pygame.draw.ellipse(s, (10, 0, 10), (76, 40, 16, 22))
    _circ(s, r, (13, 74), 5, (30, 60, 160), 2, (255, 214, 170))
    _line(s, r, (13, 79), (13, 90), (30, 60, 160), 2)
    for k in range(5):
        _line(s, r, (6 + k * 3, 6), (8 + k * 3, 20), (200, 20, 30), 1)
    fin(5, s)


# ----------------------------------------------------------------------------
# Вспомогательные примитивы
# ----------------------------------------------------------------------------
def bx(x, y0, z, sx, sh, sz, col, tex="white", **k):
    obj("box", x, y0 + sh / 2, z, sx, sh, sz, col, tex, **k)


def flat(x0, x1, z0, z1, y, ny, col, tex="white", uvs=(1.0, 1.0), tile=2.0, lit=True):
    glColor3f(*col)
    glBindTexture(GL_TEXTURE_2D, TEX[tex])
    if not lit:
        glDisable(GL_LIGHTING)
    face((x0, y, z0), (1, 0, 0), (0, 0, 1), x1 - x0, z1 - z0, (0, ny, 0), uvs=uvs, tile=tile)
    if not lit:
        glEnable(GL_LIGHTING)


def wall(axis, c, a0, a1, th, y0, h, col, holes=()):
    """Стена вдоль axis ('x' - вдоль x на линии z=c, 'z' - вдоль z на линии x=c).

    holes: (центр, ширина, низ, верх). Проёмы можно ставить друг над другом:
    каждый вырезается из уже собранных кусков, поэтому стык этажей не рвётся.
    """
    rects = [(a0, a1, y0, y0 + h)]
    for hc, hw, hb, ht in holes:
        x0, x1 = hc - hw / 2, hc + hw / 2
        nxt = []
        for p0, p1, ya, yb in rects:
            if p1 <= x0 or p0 >= x1 or yb <= hb or ya >= ht:
                nxt.append((p0, p1, ya, yb))
                continue
            if p0 < x0:
                nxt.append((p0, x0, ya, yb))
            if p1 > x1:
                nxt.append((x1, p1, ya, yb))
            ix0, ix1 = max(p0, x0), min(p1, x1)
            if ya < hb:
                nxt.append((ix0, ix1, ya, hb))
            if yb > ht:
                nxt.append((ix0, ix1, ht, yb))
        rects = nxt
    for p0, p1, ya, yb in rects:
        if p1 - p0 < 1e-3 or yb - ya < 1e-3:
            continue
        m, L, my, H = (p0 + p1) / 2, p1 - p0, (ya + yb) / 2, yb - ya
        if axis == "z":
            obj("box", c, my, m, th, H, L, col)
        else:
            obj("box", m, my, c, L, H, th, col)


def wb(axis, c, a, y0, la, h, depth, col):
    if axis == "z":
        bx(c, y0, a, depth, h, la, col)
    else:
        bx(a, y0, c, la, h, depth, col)


def window(axis, c, cen, w, yb, yt, tt=.38):
    fr = .07
    mid = (yb + yt) / 2
    wb(axis, c, cen - w / 2 + fr / 2, yb, fr, yt - yb, tt, WHITE)
    wb(axis, c, cen + w / 2 - fr / 2, yb, fr, yt - yb, tt, WHITE)
    wb(axis, c, cen, yt - fr, w, fr, tt, WHITE)
    wb(axis, c, cen, yb, w, fr, tt, WHITE)
    wb(axis, c, cen, yb, fr * .7, yt - yb, tt * .5, WHITE)
    wb(axis, c, cen, mid - fr * .35, w, fr * .7, tt * .5, WHITE)
    wb(axis, c, cen, yb - .05, w + .3, .05, tt + .22, (.92, .92, .94))


def door_frame(axis, c, cen, w, y0, hgt, tt=.4):
    wb(axis, c, cen - w / 2 - .04, y0, .09, hgt, tt, WHITE)
    wb(axis, c, cen + w / 2 + .04, y0, .09, hgt, tt, WHITE)
    wb(axis, c, cen, y0 + hgt, w + .26, .1, tt, WHITE)


# ----------------------------------------------------------------------------
# Мир игрока
# ----------------------------------------------------------------------------
class World:
    def __init__(self, season, food):
        self.season, self.food = season, food
        self.env, self.pal = ENV[season], PAL[season]
        self.rng = random.Random(season * 31 + food * 7 + 5)
        self.anchors = {}
        self.spots = []          # (x, z, r, уровень, ключ, подпись, реплики) - абсолютные координаты
        self.cols = []           # (x, z, r, уровень 0/1/2) - абсолютные координаты
        self.doors = []
        self.mirror = None
        self.entered = False
        self.track = make_track([(WX + x, y, WZ + z) for x, y, z in WTRACK_REL], sigma_m=3.5)
        self.lst = glGenLists(1)
        glNewList(self.lst, GL_COMPILE)
        glPushMatrix()
        glTranslatef(WX, 0, WZ)
        self._terrain()
        self._forest()
        self._track_geom()
        self._yard()
        self._shell()
        self._interior()
        self._landing()
        glPopMatrix()
        glEndList()
        self._colliders()
        r = random.Random(9)
        self.parts = [(r.random() * 40, r.random() * 20, r.random() * 40, r.uniform(.6, 1.2), r.random()) for _ in range(110)]

    # --- вспомогательное
    def C(self, x, z, r, lvl=2):
        self.cols.append((WX + x, WZ + z, r, lvl))

    def spot(self, x, z, r, lvl, key, label, lines):
        self.spots.append((WX + x, WZ + z, r, lvl, key, label, lines))

    def crun(self, axis, c, a0, a1, lvl, gaps=(), r=.2):
        pts = [float(a) for a in np.arange(a0, a1 + 1e-6, .45)]
        for g, hg in gaps:
            pts = [a for a in pts if abs(a - g) >= hg] + [g - hg, g + hg]
        for a in pts:
            if axis == "z":
                self.C(c, a, r, lvl)
            else:
                self.C(a, c, r, lvl)

    def cline(self, x, z, ry, half, r, lvl, axis="x"):
        th = math.radians(ry)
        vx, vz = (math.cos(th), -math.sin(th)) if axis == "x" else (math.sin(th), math.cos(th))
        k = -half
        while k <= half + 1e-6:
            self.C(x + vx * k, z + vz * k, r, lvl)
            k += r * 1.4

    # --- рельеф и лес
    def _terrain(self):
        e, rng = self.env, self.rng
        glColor3f(*e["ground"])
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        face((-240, 0.0, -300), (1, 0, 0), (0, 0, 1), 480, 560, (0, 1, 0), tile=10.0)
        g = e["ground"]
        for i in range(90):
            a, d = rng.uniform(0, TAU), rng.uniform(15, 200)
            k = rng.uniform(.88, 1.1)
            obj("cyl", math.cos(a) * d, .02, math.sin(a) * d - 40, rng.uniform(4, 12), .02, rng.uniform(4, 12),
                (min(1, g[0] * k), min(1, g[1] * k), min(1, g[2] * k)))

    def _tree(self, x, z, sc):
        s, rng = self.season, self.rng
        if s == 3:
            if rng.random() < .8:
                obj("cyl", x, 0, z, .22 * sc, 1.3 * sc, .22 * sc, (.4, .3, .22))
                obj("cone", x, 1.0 * sc, z, 1.9 * sc, 2.6 * sc, 1.9 * sc, (.2, .42, .34))
                obj("cone", x, 2.3 * sc, z, 1.4 * sc, 2.2 * sc, 1.4 * sc, (.2, .42, .34))
                obj("cone", x, 1.4 * sc, z, 1.6 * sc, .9 * sc, 1.6 * sc, WHITE)
                obj("cone", x, 2.7 * sc, z, 1.15 * sc, .8 * sc, 1.15 * sc, WHITE)
            else:
                obj("cyl", x, 0, z, .2 * sc, 2.6 * sc, .2 * sc, (.34, .26, .2))
                obj("sphere", x, 3.0 * sc, z, .9 * sc, .35 * sc, .9 * sc, WHITE)
            return
        cols = {0: [(1.0, .74, .84), (1.0, .9, .94), (.72, .9, .56)],
                1: [(.26, .62, .22), (.34, .72, .28), (.2, .52, .2)],
                2: [(.78, .76, .16), (.9, .56, .12), (.86, .28, .1), (.7, .72, .2), (.82, .66, .14)]}[s]
        obj("cyl", x, 0, z, .22 * sc, 2.2 * sc, .22 * sc, (.4, .3, .22))
        c1, c2 = rng.choice(cols), rng.choice(cols)
        obj("sphere", x, 3.0 * sc, z, 1.5 * sc, 1.25 * sc, 1.5 * sc, c1)
        obj("sphere", x + .6 * sc, 3.6 * sc, z - .3 * sc, 1.05 * sc, .9 * sc, 1.05 * sc, c2)

    def _forest(self):
        rng = self.rng
        n, tries = 0, 0
        P = self.track["P"][::10]
        while n < 950 and tries < 6000:
            tries += 1
            a = rng.uniform(0, TAU)
            d = rng.uniform(34, 230)
            x, z = math.cos(a) * d, math.sin(a) * d - 30
            if abs(x) < 22 and -16 < z < 62:               # двор и посадка
                continue
            ok = True
            for q in P:
                if q[1] < 12 and abs(q[0] - WX - x) < 7 and abs(q[2] - WZ - z) < 7:
                    ok = False
                    break
            if not ok:
                continue
            n += 1
            self._tree(x, z, rng.uniform(1.1, 2.0))

    def _track_geom(self):
        rel = dict(self.track)
        P = self.track["P"].copy()
        P[:, 0] -= WX
        P[:, 2] -= WZ
        rel["P"] = P
        build_track_geom(rel, supports=True, skip=lambda a: abs(a[0]) < 20 and a[2] < 14)

    # --- двор
    def _yard(self):
        s, rng = self.season, self.rng
        # дорожка от посадки к калитке и крыльцу
        for z in np.arange(HD + 4.2, 24.0, 1.15):
            obj("box", DOOR_X, .03, float(z), 1.7, .06, 1.0, (.78, .76, .72) if int(z) % 2 else (.7, .68, .66))
        # забор (двор шире дома)
        fc = WHITE
        for x in np.arange(-16, 16.01, .6):
            if abs(x - DOOR_X) < 1.7:
                continue
            bx(float(x), 0, 16.0, .14, 1.0, .05, fc)
        for z in np.arange(-12, 16.01, .6):
            for xx in (-16.0, 16.0):
                bx(xx, 0, float(z), .05, 1.0, .14, fc)
        for x in np.arange(-16, 16.01, .6):
            bx(float(x), 0, -12.0, .14, 1.0, .05, fc)
        for y in (.3, .7):
            bx(-9.75, y, 16.0, 12.5, .07, .07, fc)
            bx(7.95, y, 16.0, 16.1, .07, .07, fc)
            bx(0, y, -12.0, 32, .07, .07, fc)
            for xx in (-16.0, 16.0):
                bx(xx, y, 2.0, .07, .07, 28, fc)
        for sg in (-1, 1):
            bx(DOOR_X + sg * 1.8, 0, 16.0, .2, 1.35, .2, (.7, .5, .35))
            self.C(DOOR_X + sg * 1.8, 16.0, .3, 2)
        for x in np.arange(-16, 16.01, 1.2):
            if abs(x - DOOR_X) > 2.2:
                self.C(float(x), 16.0, .3, 2)
            self.C(float(x), -12.0, .3, 2)
        for z in np.arange(-12, 16.01, 1.2):
            self.C(-16.0, float(z), .3, 2)
            self.C(16.0, float(z), .3, 2)
        # деревья во дворе
        for tx, tz, sc in ((13.5, 5.5, 1.5), (-13.5, 5.0, 1.4), (13.5, -5.5, 1.4), (-13.2, -6.0, 1.3)):
            self._tree(tx, tz, sc)
            self.C(tx, tz, .5, 2)
        free = lambda: self._free_spot()
        if s == 0:                                              # весна: цветы
            for i in range(90):
                x, z = free()
                c = rng.choice([(1.0, .5, .7), (1.0, 1.0, 1.0), (1.0, .9, .3), (.7, .6, 1.0)])
                obj("cyl", x, .02, z, .02, .22, .02, (.2, .6, .2))
                obj("sphere", x, .26, z, .1, .07, .1, c)
        elif s == 1:                                            # лето: подсолнухи, бассейн, мяч
            for x in np.arange(-14.5, 15, 2.3):
                obj("cyl", float(x), 0, -10.6, .04, 1.7, .04, (.2, .55, .2))
                obj("cyl", float(x) - .05, 1.72, -10.6, .3, .07, .3, (1.0, .82, .1), rz=90)
                obj("cyl", float(x) - .1, 1.72, -10.6, .15, .08, .15, (.35, .2, .1), rz=90)
            obj("cyl", 13.2, 0, 2.2, 1.7, .35, 1.7, (.95, .95, 1.0))
            obj("cyl", 13.2, .2, 2.2, 1.5, .16, 1.5, (.35, .75, 1.0), lit=False)
            obj("sphere", 12.4, .35, 6.2, .32, .32, .32, RED)
            obj("sphere", 12.4, .35, 6.2, .33, .2, .33, WHITE)
            obj("sphere", 60, 70, -120, 7, 7, 7, (1.0, .92, .3), lit=False)
            for i in range(30):
                x, z = free()
                obj("sphere", x, .08, z, .1, .07, .1, rng.choice([(1.0, .85, .2), (1.0, .55, .2)]))
        elif s == 2:                                            # осень: тыквы, листья, сено
            for tx, tz in ((-4.2, 12.4), (-6.6, 11.6), (3.6, 12.6), (-8.2, 13.2), (6.2, 12.8)):
                obj("sphere", tx, .3, tz, .42, .32, .42, (.98, .5, .1))
                obj("cyl", tx, .55, tz, .05, .15, .05, (.3, .5, .2))
            for i in range(80):
                x, z = free()
                obj("sphere", x, .04, z, rng.uniform(.3, .7), .06, rng.uniform(.3, .7),
                    rng.choice([(.85, .3, .1), (.95, .6, .1), (.6, .25, .1), (.8, .15, .12)]), ry=rng.uniform(0, 180))
            bx(13.0, 0, 12.4, 1.3, .6, .8, (.9, .75, .3))
        else:                                                   # зима: снеговик, сугробы
            for i in range(18):
                x, z = free()
                obj("sphere", x, .05, z, rng.uniform(.6, 1.3), rng.uniform(.25, .45), rng.uniform(.6, 1.3), WHITE)
            sx, sz = 12.6, 12.2
            obj("sphere", sx, .5, sz, .6, .55, .6, WHITE)
            obj("sphere", sx, 1.3, sz, .45, .42, .45, WHITE)
            obj("sphere", sx, 1.9, sz, .32, .32, .32, WHITE)
            obj("cyl", sx, 2.15, sz, .3, .08, .3, BLACK)
            obj("cyl", sx, 2.2, sz, .2, .3, .2, BLACK)
            obj("cone", sx, 1.9, sz + .32, .06, .4, .06, (1.0, .5, .1), rx=90)
            for sg in (-1, 1):
                obj("sphere", sx + sg * .11, 1.98, sz + .27, .04, .04, .04, BLACK)
                beam((sx + sg * .4, 1.4, sz), (sx + sg * .95, 1.8, sz + .1), .05, DWOOD)
            self.C(sx, sz, .6, 2)

    def _free_spot(self):
        rng = self.rng
        for _ in range(40):
            x, z = rng.uniform(-15, 15), rng.uniform(-11, 15)
            if abs(x) < HW + 2.4 and -HD - 1.5 < z < HD + 4.0:
                continue
            if abs(x - DOOR_X) < 1.3 and z > HD:
                continue
            return x, z
        return 12.0, 0.0

    # --- посадочная станция
    def _landing(self):
        x0 = DOOR_X
        bx(x0, 0, LAND_Z + 8, 8.0, .35, 22, (.8, .8, .86))
        flat(x0 - 4.0, x0 + 4.0, LAND_Z - 3.0, LAND_Z + 19.0, .352, 1, (.92, .9, .96), "checker", (.5, .5), 2.0)
        for sg in (-1, 1):
            obj("cyl", x0 + sg * 3.6, .35, LAND_Z + 2, .16, 4.2, .16, PURP)
            obj("cyl", x0 + sg * 3.6, .35, LAND_Z + 14, .16, 4.2, .16, PURP)
        obj("box", x0, 4.6, LAND_Z + 8, 8.4, .3, 15, WHITE, "stripes")
        # вагончик, на котором приехали
        # шестиугольный проход «вернуться в парк»
        px, pz = x0 + 3.7, LAND_Z + 8
        for k in range(6):
            a0, b0 = _hex(1.6, k)
            a1, b1 = _hex(1.6, k + 1)
            beam((px, 2.2 + b0, pz + a0), (px, 2.2 + b1, pz + a1), .22, RED if k % 2 else BLUE)
        obj("cyl", px, 2.2, pz, 1.35, .05, 1.35, (.1, .02, .2), rz=90, lit=False)
        self.C(px, pz - 1.7, .4, 0)
        self.C(px, pz + 1.7, .4, 0)
        self.portal_pos = (WX + px, WZ + pz)
        self.land_pos = (WX - 1.8, WZ + LAND_Z + 2.4)

    # --- оболочка дома
    def _shell(self):
        P = self.pal
        t = .16
        wc, ic = P["wall"], P["inner"]
        # (ось, линия, знак наружу, a0, a1, y0, высота, дыры)
        gh = H0
        uh = H1 - F1
        U = F1
        # Одна стена от пола до крыши: раньше низ кончался на H0, а верх начинался на F1,
        # и между этажами оставалась сквозная щель.
        wy0, wy1 = 1.15, 2.8
        uy0, uy1 = U + 1.05, U + 2.75
        shell = [
            ("x", HD, 1, -HW - t, HW + t, [
                (DOOR_X, 1.3, 0, 2.6), (-6.2, 1.6, wy0, wy1), (4.0, 1.6, wy0, wy1),
                (-6.2, 1.6, uy0, uy1), (4.0, 1.6, uy0, uy1)]),
            ("x", -HD, -1, -HW - t, HW + t, [
                (-5.2, 1.7, wy0, wy1), (3.0, 1.55, wy0, wy1),
                (-5.2, 1.7, uy0, uy1), (3.0, 1.55, uy0, uy1)]),
            ("z", -HW, -1, -HD, HD, [
                (-4.4, 1.6, wy0, wy1), (2.6, 1.6, wy0, wy1),
                (-4.4, 1.6, uy0, uy1), (2.6, 1.6, uy0, uy1)]),
            ("z", HW, 1, -HD, HD, [
                (0.4, 1.55, wy0, wy1), (0.4, 1.55, uy0, uy1)]),
        ]
        for axis, c, sg, a0, a1, holes in shell:
            wall(axis, c + sg * t / 2, a0, a1, t, 0, H1, wc, holes)
            wall(axis, c - sg * t / 2, a0 + (t if axis == "x" else 0), a1 - (t if axis == "x" else 0), t, 0, H1, ic, holes)
            for hc, hw, hb, ht in holes:
                if hb > .05 or axis == "z":
                    window(axis, c, hc, hw, hb, ht)
                else:
                    door_frame(axis, c, hc, hw, 0, ht)
        # межэтажное перекрытие: низ (потолок 1-го этажа) и верх (пол 2-го)
        slab = [(-HW, SX0, -HD, HD), (SX0, HW, -HD, SZ1), (SX0, HW, SZ0, HD)]
        ceil = tuple(min(1.0, c * .93) for c in ic)
        for x0, x1, z0, z1 in slab:
            flat(x0, x1, z0, z1, H0 - .012, -1, ceil, tile=3.5, lit=False)
            bx((x0 + x1) / 2, H0, (z0 + z1) / 2, x1 - x0, F1 - H0, z1 - z0, (.9, .88, .82))
        bx((SX0 + HW) / 2, H0, SZ1 - .01, HW - SX0, F1 - H0, .02, (.9, .88, .82))
        bx(SX0, H0, (SZ0 + SZ1) / 2, .02, F1 - H0, SZ0 - SZ1, (.9, .88, .82))
        if not NOROOF:
            flat(-HW, HW, -HD, HD, H1 - .012, -1, ceil, tile=3.5, lit=False)          # потолок 2-го этажа
        # тёмный чулан под лестничной площадкой
        bx((SX0 + HW) / 2, 0, (SZ1 - HD) / 2, HW - SX0, H0, SZ1 + HD, ic)
        # углы
        for sx in (-1, 1):
            for sz in (-1, 1):
                bx(sx * (HW + t / 2), 0, sz * (HD + t / 2), .3, H1, .3, WHITE)
        # красный навес-«пояс» между этажами и крыльцо
        obj("box", 0, F1 - .12, HD + 1.25, 2 * HW + .8, .18, 2.6, P["roof"], rx=-6)
        for x in (-HW + .15, 1.7, HW - .15):
            obj("cyl", x, 0, HD + 2.3, .1, F1 - .15, .1, WHITE)
        bx(0, 0, HD + 1.25, 2 * HW, .12, 2.5, (.62, .44, .3))
        for x in np.arange(-HW, HW + .01, .55):
            if abs(x - DOOR_X) > 1.05:
                bx(float(x), .12, HD + 2.3, .08, 1.0, .05, WHITE)
        bx(0, .62, HD + 2.3, 2 * HW, .06, .08, WHITE)
        for k in range(3):
            bx(DOOR_X, .0, HD + 2.6 + k * .34, 2.0, .13 - k * .035, .34, (.7, .68, .66))
        # цветочные ящики под окнами фасада
        for x in (-6.2, 4.0):
            bx(x, .7, HD + .32, 1.7, .22, .32, RED)
            for k in range(5):
                obj("sphere", x - .7 + k * .35, 1.0, HD + .32, .13, .13, .11, rng_col(self.rng, self.season))
        # крыша на всю ширину дома
        half, rise = HW + .95, 3.35
        ang = math.degrees(math.atan2(rise, half))
        length = math.hypot(half, rise) + .15
        if not NOROOF:
            bx(0, H1, 0, 2 * HW + .5, .12, 2 * HD + .5, (.85, .85, .85))
            for sg in (-1, 1):
                obj("box", sg * half / 2, H1 + rise / 2, 0, length, .22, 2 * HD + 1.7, P["roof"], rz=-sg * ang)
            bx(0, H1 + rise - .06, 0, .55, .2, 2 * HD + 1.8, tuple(c * .8 for c in P["roof"]))
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        for zz, nz in ((-HD - t - .01, -1), (HD + t + .01, 1)):
            glColor3f(*wc)
            glNormal3f(0, 0, nz)
            glBegin(GL_TRIANGLES)
            glVertex3f(-HW - t, H1, zz)
            glVertex3f(HW + t, H1, zz)
            glVertex3f(0, H1 + rise - .02, zz)
            glEnd()
        # солнышко на фронтоне
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, .5)
        glColor3f(1, 1, 1)
        glBindTexture(GL_TEXTURE_2D, TEX["sun"])
        glDisable(GL_LIGHTING)
        glNormal3f(0, 0, 1)
        z = HD + t + .03
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0)
        glVertex3f(-1.15, H1 + .4, z)
        glTexCoord2f(1, 0)
        glVertex3f(1.15, H1 + .4, z)
        glTexCoord2f(1, 1)
        glVertex3f(1.15, H1 + rise - .55, z)
        glTexCoord2f(0, 1)
        glVertex3f(-1.15, H1 + rise - .55, z)
        glEnd()
        glEnable(GL_LIGHTING)
        glDisable(GL_ALPHA_TEST)
        if self.season == 3:                                    # снег на крыше
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            for sg in (-1, 1):
                obj("box", sg * (half / 2 + .14 * sa), H1 + rise / 2 + .14 * ca, 0,
                    length + .05, .16, 2 * HD + 1.75, WHITE, rz=-sg * ang)
            bx(0, H1 + rise + .08, 0, .7, .14, 2 * HD + 1.85, WHITE)
        # перегородки 1 этажа
        arch = [(0.0, 2.8, 0, 2.75)]
        wall("z", AX, -HD + t, HD - t, .16, 0, gh, ic, arch)
        # перегородки 2 этажа
        dh = 2.5
        d_bed = [(BED_DX, 1.15, U, U + dh)]
        d_bath = [(BATH_DX, 1.15, U, U + dh)]
        d_hall = d_bed + d_bath
        d_laun = [(LAUN_DZ, 1.15, U, U + dh)]
        wall("x", BZ, -HW + t, SX0, .16, U, uh, ic, d_hall)
        wall("z", RX, BZ, HD - t, .16, U, uh, ic, d_laun)
        wall("x", LZ, RX, SX0, .16, U, uh, ic)
        wall("z", SX0, BZ, HD - t, .16, U, uh, ic)
        for hc, hw, hb, ht in d_hall:
            door_frame("x", BZ, hc, hw, U, dh, .24)
        door_frame("z", RX, LAUN_DZ, 1.15, U, dh, .24)
        # двери (динамические)
        self._door(DOOR_X, HD, "x", 1.3, 0.0, -1, +1, 0)
        self._door(BED_DX, BZ, "x", 1.15, U, -1, +1, 1)
        self._door(BATH_DX, BZ, "x", 1.15, U, -1, +1, 1)
        self._door(RX, LAUN_DZ, "z", 1.15, U, -1, +1, 1)

    def _door(self, cx, cz, axis, w, y0, hs, sw, lvl):
        # шарнир на краю проёма (hs=-1: на меньшей координате), створка открывается на угол sw*ang
        if axis == "x":
            hx, hz = cx + hs * w / 2, cz
            ry0 = 0.0 if hs < 0 else 180.0
        else:
            hx, hz = cx, cz + hs * w / 2
            ry0 = -90.0 if hs < 0 else 90.0
        self.doors.append(dict(x=cx, z=cz, hx=hx, hz=hz, axis=axis, w=w, y0=y0, ry0=ry0, sw=sw, lvl=lvl,
                               ang=0.0, open=False, h=2.45))

    # --- мебель и картины
    def _pic(self, x, y, z, ry, w, h, tex):
        push(x, y, z, ry=ry)
        obj("box", 0, 0, 0, w + .12, h + .12, .05, (.5, .34, .2))
        obj("box", 0, 0, .03, w, h, .02, WHITE, tex)
        pop()

    def _hang(self, axis, c, y, a0, a1, holes, ry, n=2, tex0=0):
        """Вешает картины только в сплошной стене, с зазором от окон и дверей."""
        pad = 0.62
        blocked = sorted((hc - hw / 2 - pad, hc + hw / 2 + pad) for hc, hw in holes)
        spans, cursor = [], a0
        for b0, b1 in blocked:
            if b0 - cursor > 1.7:
                spans.append((cursor, b0))
            cursor = max(cursor, b1)
        if a1 - cursor > 1.7:
            spans.append((cursor, a1))
        spans.sort(key=lambda s: s[1] - s[0], reverse=True)
        placed = 0
        for a, b in spans:
            if placed >= n:
                break
            length = b - a
            count = 1 if length < 4.6 else (2 if length < 8.2 else 3)
            count = min(count, n - placed)
            for i in range(count):
                mid = a + (i + 1) / (count + 1) * length
                w = 1.05 if length > 2.6 else .82
                tex = "draw%d" % ((tex0 + placed) % 6)
                if axis == "x":
                    self._pic(mid, y, c, ry, w, w * .72, tex)
                else:
                    self._pic(c, y, mid, ry, w, w * .72, tex)
                placed += 1

    def _sofa(self, x, z, ry, w, col, cush):
        push(x, 0, z, ry=ry)
        bx(0, .07, 0, w, .42, .95, col)
        bx(0, .45, -.38, w, .6, .22, col)
        for sg in (-1, 1):
            bx(sg * (w / 2 - .13), .07, 0, .26, .62, .95, col)
        n = 3 if w > 1.6 else 1
        cw = (w - .5) / n
        for i in range(n):
            bx(-(w - .5) / 2 + cw * (i + .5), .49, .07, cw - .04, .12, .72, cush)
        pop()

    def _table(self, x, y0, z, ry, w, d, h, col):
        push(x, y0, z, ry=ry)
        bx(0, h - .07, 0, w, .07, d, col)
        for sx in (-1, 1):
            for sz in (-1, 1):
                bx(sx * (w / 2 - .08), 0, sz * (d / 2 - .08), .07, h - .07, .07, DWOOD)
        pop()

    def _chair(self, x, z, ry, y0=0.0):
        push(x, y0, z, ry=ry)
        bx(0, .42, 0, .46, .06, .46, WOOD)
        bx(0, .48, -.21, .46, .55, .05, WOOD)
        for sx in (-1, 1):
            for sz in (-1, 1):
                bx(sx * .19, 0, sz * .19, .05, .42, .05, DWOOD)
        pop()

    def _plant(self, x, y0, z, sc=1.0, col=(.2, .55, .25)):
        obj("cyl", x, y0, z, .24 * sc, .38 * sc, .24 * sc, (.75, .4, .3))
        for k in range(5):
            a = k * TAU / 5
            obj("sphere", x + math.cos(a) * .18 * sc, y0 + .65 * sc + .12 * (k % 2), z + math.sin(a) * .18 * sc,
                .22 * sc, .3 * sc, .22 * sc, (col[0], col[1] + .05 * k, col[2]))

    def _lamp(self, x, y0, z, shade=(1.0, .62, .72)):
        obj("cyl", x, y0, z, .18, .06, .18, DWOOD)
        obj("cyl", x, y0, z, .025, 1.5, .025, DWOOD)
        obj("cone", x, y0 + 1.3, z, .34, .38, .34, shade, lit=False)

    def _pendant(self, x, y_top, z):
        obj("cyl", x, y_top - .6, z, .012, .6, .012, DWOOD)
        obj("cone", x, y_top - .9, z, .35, .32, .35, (1.0, .9, .6), lit=False)
        obj("sphere", x, y_top - .9, z, .1, .1, .1, (1.0, 1.0, .85), lit=False)

    def _food(self, x, y, z):
        f = self.food
        obj("cyl", x, y, z, .32, .02, .32, WHITE)
        y += .02
        if f == 0:                                             # пицца
            obj("cyl", x, y, z, .28, .035, .28, (.95, .72, .3))
            obj("cyl", x, y + .03, z, .24, .01, .24, (.85, .2, .12))
            obj("cyl", x, y + .035, z, .22, .008, .22, (1.0, .85, .3))
            for k in range(7):
                a = k * TAU / 7
                obj("cyl", x + math.cos(a) * .13, y + .045, z + math.sin(a) * .13, .045, .012, .045, (.6, .1, .1))
            obj("cyl", x, y + .045, z, .045, .012, .045, (.6, .1, .1))
        elif f == 1:                                           # бургер
            obj("cyl", x, y, z, .17, .06, .17, (.88, .58, .26))
            obj("cyl", x, y + .06, z, .18, .05, .18, (.4, .22, .12))
            obj("box", x, y + .11, z, .34, .014, .34, (1.0, .8, .15), ry=45)
            obj("cyl", x, y + .115, z, .2, .02, .2, (.3, .7, .25))
            obj("cyl", x, y + .135, z, .17, .02, .17, (.9, .2, .15))
            obj("sphere", x, y + .155, z, .17, .1, .17, (.88, .58, .26))
        elif f == 2:                                           # суши
            obj("box", x, y + .015, z, .62, .03, .36, (.55, .38, .22))
            for i in range(3):
                for j in range(2):
                    xx, zz = x - .2 + i * .2, z - .08 + j * .16
                    obj("cyl", xx, y + .03, zz, .065, .07, .065, (.06, .06, .06))
                    obj("cyl", xx, y + .031, zz, .05, .075, .05, WHITE)
                    obj("cyl", xx, y + .032, zz, .02, .078, .02, (1.0, .5, .2))
            obj("box", x + .29, y + .05, z, .06, .02, .1, (.2, .6, .2))
        else:                                                  # торт
            obj("cyl", x, y, z, .24, .1, .24, (1.0, .6, .75))
            obj("cyl", x, y + .1, z, .17, .09, .17, WHITE)
            obj("cyl", x, y + .19, z, .09, .02, .09, (1.0, .6, .75))
            obj("sphere", x, y + .22, z, .04, .04, .04, (.9, .1, .15))
            obj("cyl", x + .05, y + .19, z, .012, .1, .012, WHITE)
            obj("sphere", x + .05, y + .31, z, .018, .028, .018, (1.0, .9, .3), lit=False)

    def _interior(self):
        P, rng = self.pal, self.rng
        U = F1
        ic = P["inner"]
        cush = tuple(min(1.0, c + .22) for c in P["sofa"])
        # -- полы 1 этажа
        flat(-HW, SX0, -HD, HD, .075, 1, P["floor"], "hfloor", (.5, .5), 2.0)
        flat(SX0, HW, SZ0, HD, .075, 1, P["floor"], "hfloor", (.5, .5), 2.0)
        # -- полы 2 этажа
        flat(-HW, RX, BZ, HD, U + .005, 1, P["carpet"], tile=2.0)                         # спальня
        flat(RX, SX0, BZ, LZ, U + .005, 1, WHITE, "checker", (.9, .9), 1.0)               # ванная
        flat(RX, SX0, LZ, HD, U + .005, 1, WHITE, "checker", (.9, .9), 1.0)               # прачечная
        flat(-HW, HW, -HD, BZ, U + .005, 1, P["floor"], "hfloor", (.5, .5), 2.0)          # холл
        flat(SX0, HW, BZ, SZ1, U + .005, 1, P["floor"], "hfloor", (.5, .5), 2.0)          # площадка
        flat(SX0, HW, SZ0, HD, U + .005, 1, P["floor"], "hfloor", (.5, .5), 2.0)
        # плинтус
        for (axis, c, a0, a1, y0) in (("x", -HD + .16, -HW, HW, 0), ("x", HD - .16, -HW, HW, 0), ("z", -HW + .16, -HD, HD, 0),
                                       ("z", HW - .16, -HD, HD, 0)):
            hole = [(DOOR_X, 1.5, 0, 2.6)] if (axis, c) == ("x", HD - .16) else []
            wall(axis, c, a0, a1, .04, y0, .12, (.4, .3, .22), hole)
        # -- лестница (тёмные ступени и перила)
        ns = 22
        rise, run = (F1 - .075) / ns, (SZ0 - SZ1) / ns
        for i in range(ns):
            top = .075 + (i + 1) * rise
            bx((SX0 + HW) / 2, 0, SZ0 - (i + .5) * run, HW - SX0, top, run, (.30, .22, .17))
            bx((SX0 + HW) / 2, top - .02, SZ0 - (i + .5) * run + .02, HW - SX0, .03, run + .02, (.42, .3, .22))
        L = (SZ0 - SZ1)
        for k in range(20):
            zz = SZ0 - .2 - k * (L - .4) / 19
            yy = .075 + (SZ0 - zz) / L * (F1 - .075)
            bx(SX0 + .05, yy, zz, .04, .95, .04, (.12, .12, .14))
        beam((SX0 + .05, 1.05, SZ0 - .2), (SX0 + .05, 1.05 + F1 - .075 - .1, SZ1 + .2), .08, (.2, .15, .12))
        # -- гостиная
        sofa = (-4.2, -5.5)
        bx(sofa[0], .075, -3.4, 4.4, .02, 3.2, P["rug"])
        self._sofa(sofa[0], sofa[1], 0, 3.2, P["sofa"], cush)
        self.cline(sofa[0], sofa[1], 0, 1.4, .4, 0)
        obj("cyl", sofa[0], .075, -3.5, .85, .06, .85, WOOD)
        obj("cyl", sofa[0], .0, -3.5, .1, .45, .1, DWOOD)
        obj("cyl", sofa[0], .43, -3.5, .88, .05, .88, WOOD)
        self.C(sofa[0], -3.5, .75, 0)
        self._sofa(-7.6, 1.0, 90, 1.3, (.12, .12, .14), (.2, .2, .24))
        self.C(-7.6, 1.0, .6, 0)
        bx(-7.5, .075, -3.0, .55, .5, .55, (.55, .05, .06))
        self._lamp(-1.4, .075, -6.2)
        self.C(-1.4, -6.2, .3, 0)
        self._plant(-7.9, .075, -6.5)
        self.C(-7.9, -6.5, .35, 0)
        self._plant(.15, .075, 6.3, 1.3)
        self.C(.15, 6.3, .35, 0)
        # книжный шкаф у перегородки, в стороне от арки
        push(AX - .42, 0, -5.6, ry=-90)
        bx(0, 0, -.15, 1.7, 2.05, .04, DWOOD)
        for sg in (-1, 1):
            bx(sg * .85, 0, 0, .05, 2.05, .38, WOOD)
        for k in range(5):
            bx(0, k * .5, 0, 1.7, .05, .38, WOOD)
        for k in range(4):
            xx = -.75
            while xx < .7:
                bw = rng.uniform(.05, .1)
                bx(xx + bw / 2, k * .5 + .05, 0, bw, rng.uniform(.3, .42), .24,
                   rng.choice([(.8, .2, .2), (.2, .4, .8), (.9, .75, .2), (.3, .6, .35), (.6, .3, .7), (.9, .9, .85)]))
                xx += bw + .01
        pop()
        self.cline(AX - .25, -5.6, 0, .85, .35, 0, "z")
        # -- кухня-столовая: стол стоит в глубине, проход через арку свободен
        kx, kz = 3.7, -6.85
        bx(kx, .075, kz, 4.6, .95, .62, (.82, .84, .88))
        bx(kx, 1.02, kz, 4.7, .06, .68, (.94, .94, .96))
        bx(kx, .075, kz, .02, .95, .64, (.5, .52, .56))
        bx(kx - 1.6, 1.08, kz - .05, .4, .22, .32, (.08, .08, .1))
        bx(kx - .8, 1.08, kz - .05, .32, .18, .32, (.08, .08, .1))
        obj("cyl", kx + 1.3, 1.08, kz, .32, .06, .32, (.6, .62, .66))
        obj("cyl", kx + 1.3, 1.14, kz - .2, .03, .32, .03, (.8, .8, .85))
        self.cline(kx, kz, 0, 2.2, .4, 0)
        self._plant(5.7, .075, -5.5, 1.5, (.55, .62, .2))
        self.C(5.7, -5.5, .35, 0)
        self._table(3.7, 0, 2.3, 0, 2.2, 1.15, .78, WOOD)
        self.cline(3.7, 2.3, 0, .85, .45, 0)
        for cx in (2.9, 4.5):
            self._chair(cx, 1.4, 0)
            self._chair(cx, 3.2, 180)
        for k, (px_, pz_) in enumerate(((3.0, 2.1), (4.4, 2.5), (3.7, 2.3))):
            if k < 2:
                obj("cyl", px_, .8, pz_, .17, .015, .17, WHITE)
                obj("cyl", px_ - .04, .815, pz_ + .03, .03, .02, .03, (.15, .3, .15))
        self._food(3.7, .8, 2.3)
        self._pendant(3.7, H0, 2.3)
        # -- спальня
        push(-7.35, U, 1.5, ry=-90)                                                       # кровать, изголовье к западной стене
        bx(0, .12, 0, 1.7, .32, 2.45, (.1, .1, .12))
        bx(0, .42, 0, 1.58, .22, 2.3, (.96, .96, .98))
        bx(0, .54, .4, 1.6, .1, 1.5, P["bed"])
        bx(0, .64, -.9, .75, .14, .45, WHITE)
        for k in range(8):
            bx(-.75 + k * .21, .12, -1.25, .035, 1.0, .035, (.08, .08, .1))
            bx(-.75 + k * .21, .12, 1.22, .035, .52, .035, (.08, .08, .1))
        bx(0, 1.05, -1.25, 1.7, .05, .05, (.08, .08, .1))
        bx(0, .64, 1.22, 1.7, .05, .05, (.08, .08, .1))
        pop()
        self.cline(-7.35, 1.5, -90, 1.1, .4, 1, "z")
        bx(-8.15, U, .15, .55, .55, .5, WOOD)
        obj("cyl", -8.15, U + .55, .15, .09, .24, .09, (1.0, .95, .75), lit=False)
        push(-1.8, U, -3.15, ry=0)                                                        # шкаф, не перекрывает дверь
        bx(0, 0, 0, 1.6, 2.3, .7, WOOD)
        bx(0, .1, .36, .02, 2.1, .02, DWOOD)
        for sg in (-1, 1):
            obj("sphere", sg * .08, 1.15, .38, .035, .035, .035, (.9, .8, .3))
        pop()
        self.cline(-1.8, -3.15, 0, .7, .4, 1)
        obj("cyl", -4.6, U + .01, 3.2, 1.45, .015, 1.45, P["rug"])
        self._table(-4.4, U, 6.45, 0, 1.7, .65, .78, WOOD)
        self._chair(-4.4, 5.6, 180, U)
        self.cline(-4.4, 6.45, 0, .75, .4, 1)
        bx(-4.8, U + .78, 6.5, .42, .03, .32, (.95, .95, .9))
        obj("cyl", -3.7, U + .78, 6.5, .1, .26, .1, (1.0, .95, .75), lit=False)
        # плюшевый Кинито на подушке
        px, py, pz = -8.05, U + .78, 1.7
        obj("sphere", px, py + .12, pz, .2, .19, .2, K_HEAD)
        for sg in (-1, 1):
            obj("sphere", px + .17, py + .17, pz + sg * .08, .05, .06, .05, WHITE, lit=False)
            obj("sphere", px + .21, py + .16, pz + sg * .08, .02, .03, .02, BLACK, lit=False)
            for k in range(3):
                beam((px, py + .12 + (k - 1) * .04, pz + sg * .18),
                     (px, py + .12 + (k - 1) * .13, pz + sg * (.33 + .02 * k)), .035, K_GILL)
        # -- ванная
        obj("cyl", 4.6, U, .85, .14, .7, .14, WHITE)
        obj("sphere", 4.6, U + .85, .85, .4, .17, .34, WHITE)
        bx(4.6, U + 1.35, LZ - .16, 1.15, 1.15, .03, (.4, .45, .5))
        bx(4.6, U + 1.32, LZ - .12, 1.22, 1.22, .02, (.5, .34, .2))
        self.mirror = (WX + 4.6, WZ + LZ - .22, U + 1.9)
        self.C(4.6, .85, .5, 1)
        bx(1.3, U, -.2, .58, .42, .72, WHITE)
        bx(1.3, U + .42, .1, .58, .55, .26, WHITE)
        self.C(1.3, -.2, .45, 1)
        bx(.55, U, -2.5, .06, 2.15, 1.8, (.4, .8, .66), "noise")
        bx(.85, U, -2.5, .55, .32, .55, (.15, .55, .9))
        self.C(.6, -2.5, .55, 1)
        # -- прачечная
        bx(3.3, U, 6.85, 4.2, .95, .62, (.82, .84, .88))
        bx(3.3, U + .95, 6.85, 4.3, .06, .68, (.94, .94, .96))
        for k in range(4):
            bx(1.6 + k * .7, U + 1.02, 6.9, .28, .32, .16, rng.choice([(.9, .2, .5), (.9, .8, .2), (.3, .3, .8)]))
        self.cline(3.3, 6.85, 0, 2.0, .4, 1)
        bx(5.5, U, 3.7, .8, 1.0, .8, WHITE)
        obj("cyl", 5.05, U + .52, 3.7, .28, .04, .28, (.2, .2, .26), rz=90)
        self.C(5.5, 3.7, .55, 1)
        bx(1.7, U, 3.4, .65, .48, .65, (.15, .55, .9))
        # -- люстры 2 этажа
        self._pendant(-4.8, H1, 1.6)
        self._pendant(1.5, H1, -5.8)
        # -- картины только на сплошных кусках стен
        ins = .22
        wins_f = [(DOOR_X, 1.3), (-6.2, 1.6), (4.0, 1.6)]
        wins_b = [(-5.2, 1.7), (3.0, 1.55)]
        wins_w = [(-4.4, 1.6), (2.6, 1.6)]
        self._hang("x", -HD + ins, 2.05, -HW + .8, HW - .8, wins_b, 0, 3, 0)
        self._hang("x", HD - ins, 2.05, -HW + .8, HW - .8, wins_f, 180, 3, 2)
        self._hang("z", -HW + ins, 2.05, -HD + .8, HD - .8, wins_w, 90, 2, 1)
        self._hang("z", HW - ins, 2.05, -HD + .8, HD - .8, [(0.4, 1.55)], -90, 2, 3)
        self._hang("z", AX - ins, 2.05, -HD + .9, HD - .9, [(0.0, 2.8)], -90, 2, 4)
        self._hang("x", -HD + ins, U + 1.9, -HW + .8, HW - .8, wins_b, 0, 3, 1)
        self._hang("x", HD - ins, U + 1.9, -HW + .8, HW - .8, [(-6.2, 1.6), (4.0, 1.6)], 180, 2, 5)
        self._hang("z", -HW + ins, U + 1.9, -HD + .8, HD - .8, wins_w, 90, 2, 2)
        self._hang("x", BZ + ins, U + 1.9, -HW + .8, RX - .55, [(BED_DX, 1.15)], 0, 2, 4)
        self._hang("x", BZ - ins, U + 1.9, -HW + .8, SX0 - .7, [(BED_DX, 1.15), (BATH_DX, 1.15)], 180, 3, 0)
        self.anchors = {
            "sofa": (-4.2, -3.6), "food": (3.7, 2.3), "shelf": (AX - .9, -5.6),
            "pics": (-6.4, -6.4), "kitchen": (3.7, -5.4), "stairs": (5.3, 6.7),
            "bed": (-5.6, 1.5), "pic5": (-4.2, -3.2), "mirror": (4.6, .2),
            "laundry": (3.3, 5.2), "window": (-7.6, 2.6), "window2": (-5.2, -6.5),
        }
        # -- стены/полы: периметр и перегородки (коллайдеры)

    # --- коллизии
    def _colliders(self):
        t = .0
        g = .0
        # внешние стены
        self.crun("x", HD, -HW, HW, 0, [(DOOR_X, .95)])
        self.crun("x", -HD, -HW, HW, 0)
        self.crun("z", -HW, -HD, HD, 0)
        self.crun("z", HW, -HD, HD, 0)
        self.crun("x", HD, -HW, HW, 1)
        self.crun("x", -HD, -HW, HW, 1)
        self.crun("z", -HW, -HD, HD, 1)
        self.crun("z", HW, -HD, HD, 1)
        # перегородка 1 этажа: арка
        self.crun("z", AX, -HD, HD, 0, [(0.0, 1.65)])
        # лестница и чулан под площадкой
        for z in np.arange(SZ1, SZ0 - 1.0, .4):             # у нижних ступеней лестницу можно обойти сбоку
            self.C(SX0 - .05, float(z), .2, 0)
        for x in np.arange(SX0, HW + .01, .4):
            self.C(float(x), SZ1 - .1, .2, 0)
        # перегородки 2 этажа
        self.crun("x", BZ, -HW, SX0, 1, [(BED_DX, .82), (BATH_DX, .82)])
        self.crun("z", RX, BZ, HD, 1, [(LAUN_DZ, .82)])
        self.crun("x", LZ, RX, SX0, 1)
        self.crun("z", SX0, BZ, HD, 1)
        # забор и пр. добавлены в _yard

    def collide(self, nx, nz, gy, pr=.3):
        lvl = 1 if gy > F1 - .9 else 0
        for _pass in (0, 1):
            for cx, cz, r, l in self.cols:
                if l != 2 and l != lvl:
                    continue
                ddx = nx - cx
                rr = r + pr
                if ddx > rr or ddx < -rr:
                    continue
                ddz = nz - cz
                if ddz > rr or ddz < -rr:
                    continue
                d2 = ddx * ddx + ddz * ddz
                if d2 < rr * rr:
                    d = math.sqrt(d2) or 1e-6
                    nx = cx + ddx / d * rr
                    nz = cz + ddz / d * rr
            for d_ in self.doors:                       # закрытая дверь - сплошная преграда
                if d_["ang"] > 35 or d_["lvl"] != lvl:
                    continue
                ax, az = d_["x"] + WX, d_["z"] + WZ
                for j in range(6):
                    off = (j / 5 - .5) * (d_["w"] - .2)
                    cx = ax + (off if d_["axis"] == "x" else 0)
                    cz = az + (off if d_["axis"] == "z" else 0)
                    ddx, ddz = nx - cx, nz - cz
                    rr = .22 + pr
                    d2 = ddx * ddx + ddz * ddz
                    if d2 < rr * rr:
                        dd = math.sqrt(d2) or 1e-6
                        nx = cx + ddx / dd * rr
                        nz = cz + ddz / dd * rr
        ex, ez = nx - WX, nz - (WZ + 14)
        d = math.hypot(ex, ez)
        if d > 48:
            nx = WX + ex / d * 48
            nz = WZ + 14 + ez / d * 48
        return nx, nz

    def inside(self, px, pz):
        return abs(px - WX) < HW and abs(pz - WZ) < HD

    def floor_y(self, px, pz, gy):
        lx, lz = px - WX, pz - WZ
        if SX0 < lx < HW and SZ1 <= lz <= SZ0:
            return max(0.0, min(F1, F1 * (SZ0 - lz) / (SZ0 - SZ1)))
        if abs(lx) < HW and abs(lz) < HD and gy > F1 - .9:
            return F1
        return 0.0

    # --- двери и динамика
    def update(self, dt):
        for d in self.doors:
            tgt = 95.0 if d["open"] else 0.0
            if d["ang"] < tgt:
                d["ang"] = min(tgt, d["ang"] + 150 * dt)
            elif d["ang"] > tgt:
                d["ang"] = max(tgt, d["ang"] - 150 * dt)

    def toggle_door(self, i):
        d = self.doors[i]
        d["open"] = not d["open"]
        return d["open"]

    def candidates(self, px, pz, gy):
        out = []
        lvl = 1 if gy > F1 - .9 else 0
        for i, d in enumerate(self.doors):
            if d["lvl"] != lvl:
                continue
            dist = math.hypot(px - (WX + d["x"]), pz - (WZ + d["z"]))
            if dist < 2.4:
                out.append((dist - 60, "wdoor%d" % i, "Дверь"))
        for i, (sx, sz, r, l, key, lab, lines) in enumerate(self.spots):
            if l != lvl:
                continue
            dist = math.hypot(px - sx, pz - sz)
            if dist < r:
                out.append((dist - 40, "spot%d" % i, lab))
        dist = math.hypot(px - self.portal_pos[0], pz - self.portal_pos[1])
        if dist < 3.4:
            out.append((dist - 80, "wreturn", "Выход"))
        return out

    def draw(self, t, cam):
        px, py, pz = cam
        glCallList(self.lst)
        glBindTexture(GL_TEXTURE_2D, TEX["hdoor"])
        for d in self.doors:
            glPushMatrix()
            glTranslatef(WX + d["hx"], d["y0"] + .02, WZ + d["hz"])
            glRotatef(d["ry0"] + d["sw"] * d["ang"], 0, 1, 0)
            obj("box", d["w"] / 2, d["h"] / 2, 0, d["w"] - .02, d["h"], .06, WHITE, "hdoor")
            obj("sphere", d["w"] - .12, 1.05, .06, .05, .05, .05, (.9, .8, .3))
            obj("sphere", d["w"] - .12, 1.05, -.06, .05, .05, .05, (.9, .8, .3))
            glPopMatrix()
        # лицо Кинито в зеркале
        if self.mirror and math.hypot(px - self.mirror[0], pz - self.mirror[1]) < 14 and abs(py - self.mirror[2]) < 3:
            mx, mz, my = self.mirror
            dx, dz = px - mx, pz - mz
            n = math.hypot(dx, dz) + 1e-6
            ox = clamp(dx / n, -1, 1) * .03
            push(mx, my, mz - .0)
            obj("sphere", 0, 0, -.01, .26, .3, .01, K_HEAD, lit=False)
            for sg in (-1, 1):
                obj("sphere", sg * .1, .06, -.02, .07, .05, .01, WHITE, lit=False)
                obj("sphere", sg * .1 + ox, .05, -.03, .028, .03, .01, BLACK, lit=False)
                obj("box", sg * .1, .105, -.03, .15, .035, .01, (.6, .25, .65), lit=False)
            obj("box", 0, -.12, -.02, .22, .03, .01, (.1, 0, .1), lit=False)
            pop()
        self._weather(t, cam)

    def _weather(self, t, cam):
        s = self.season
        cx, cy, cz = cam
        S = 40.0
        for i, (a, b, c, sp, ph) in enumerate(self.parts):
            if s == 3:
                x = (a + math.sin(t * .8 + ph * 6) * .6 - cx) % S - S / 2 + cx
                z = (c + math.cos(t * .7 + ph * 5) * .6 - cz) % S - S / 2 + cz
                y = cy + 12 - ((t * sp * 1.4 + b * 3 + ph * 9) % 24)
                obj("box", x, y, z, .1, .1, .1, WHITE, lit=False)
            elif s == 2:
                x = (a + math.sin(t * .9 + ph * 6) * 1.2 - cx) % S - S / 2 + cx
                z = (c + math.cos(t * .6 + ph * 5) * .8 - cz) % S - S / 2 + cz
                y = cy + 10 - ((t * sp * 1.0 + b * 2 + ph * 8) % 20)
                col = ((.95, .5, .1), (.85, .2, .1), (.95, .75, .15))[i % 3]
                obj("box", x, y, z, .26, .03, .18, col, rx=t * 120 * sp + ph * 90, rz=t * 80 + ph * 60, lit=False)
            elif s == 0:
                x = (a + math.sin(t * .7 + ph * 6) * 1.0 - cx) % S - S / 2 + cx
                z = (c + math.cos(t * .5 + ph * 5) * .7 - cz) % S - S / 2 + cz
                y = cy + 10 - ((t * sp * 1.0 + b * 2 + ph * 7) % 20)
                obj("box", x, y, z, .14, .02, .1, (1.0, .78, .86), rx=t * 100 * sp + ph * 90, rz=t * 70, lit=False)
            elif i < 14:                                     # лето: пылинки-светлячки
                x = (a + math.sin(t * .5 + ph * 6) * 2 - cx) % S - S / 2 + cx
                z = (c + math.cos(t * .4 + ph * 5) * 2 - cz) % S - S / 2 + cz
                y = max(1.0, cy - 3 + (b % 8) + math.sin(t * 2 + ph * 9) * .5)
                obj("sphere", x, y, z, .06, .06, .06, (1.0, .95, .5), lit=False)


def rng_col(rng, season):
    return rng.choice([(1.0, .5, .7), (1.0, 1.0, 1.0), (1.0, .9, .3), (.7, .6, 1.0)]) if season in (0, 1) else \
        rng.choice([(.9, .5, .15), (.9, .2, .1), (.95, .8, .2)]) if season == 2 else (.85, .92, 1.0)


def spot_lines(world):
    """Реплики Кинито для осмотра предметов (зависят от выбора игрока)."""
    se, fo = world.season, world.food
    sa, sn, fn = SEASON_ACC[se], SEASON_NOM[se], FOOD_LOW[fo]
    L = {
        "sofa": ["Ты любишь сидеть здесь. Я смотрю, как ты сидишь.", "Диван синий. Ты ведь любишь синий?"],
        "food": ["На столе - твоя любимая еда: %s. Я запомнил." % fn, "Она никогда не остывает. Попробуй. Я подожду."],
        "shelf": ["Книги о тебе. Я прочитал все. Дважды.", "Хочешь, расскажу, что на последней странице?"],
        "pics": ["Это твои рисунки с прошлых уровней. Я сохранил все.", "Вот этот лучший: ты нарисовал меня красивым!"],
        "window": ["Ты любишь %s. Поэтому за окном всегда %s." % (sa, sn), "Всегда. Другой погоды больше не будет."],
        "kitchen": ["Мебель стоит так, как ты расставил её в Ready Repair.", "Я ничего не менял. Почти ничего."],
        "stairs": ["Наверху твоя спальня. Я заправил кровать.", "Поднимайся. Я никуда не тороплюсь."],
        "bed": ["Здесь тебе будет уютно. Оставайся навсегда.", "Плюшевый Кинито уже ждёт тебя. Это я, только маленький."],
        "pic5": ["Здесь мы вдвоём. Я нарисовал себя побольше.", "Ведь я всегда рядом. Всегда."],
        "mirror": ["Ой. Ты увидел меня? Я живу в зеркале.", "Не бойся. Я просто хотел быть ближе."],
        "laundry": ["Я постирал твои вещи. Все, что ты оставил.", "Они пахнут %s. Правда?" % sn],
    }
    return L


def add_spots(world):
    """Точки осмотра (после построения мира, чтобы все координаты были известны)."""
    L = spot_lines(world)
    a = world.anchors
    spec = (("sofa", 2.4, 0, "Диван", "sofa"), ("food", 2.2, 0, "Любимая еда", "food"),
            ("shelf", 1.8, 0, "Книжная полка", "shelf"), ("pics", 2.2, 0, "Твои рисунки", "pics"),
            ("kitchen", 2.2, 0, "Кухня", "kitchen"), ("stairs", 2.0, 0, "Лестница", "stairs"),
            ("bed", 2.4, 1, "Кровать", "bed"), ("pic5", 2.0, 1, "Рисунок", "pic5"),
            ("mirror", 2.0, 1, "Зеркало", "mirror"), ("laundry", 2.0, 1, "Стиральная машина", "laundry"),
            ("window", 2.0, 1, "Окно", "window"), ("window2", 2.0, 0, "Окно", "window"))
    for key, r, lvl, lab, lk in spec:
        x, z = a[key]
        world.spot(x, z, r, lvl, lk, lab, L[lk])
