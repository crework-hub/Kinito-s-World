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
SEASON_SONG = [os.path.join(HERE, "song", name + ".ogg") for name in ("spring", "summer", "autumn", "winter")]
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


QUIZ_BOARD = (36, 58, 568, 376)     # лист бумаги опроса внутри деревянного фона
FURN_MARGIN, FURN_BAR, FURN_TRAY = 16, 36, 118


def _upload_surf(name, surf, repeat=False):
    surf = surf.convert_alpha()
    upload(name, pygame.image.tobytes(surf, "RGBA", True), surf.get_width(), surf.get_height(),
           mip=False, repeat=repeat)


def _blit_leaf(dst, x, y, ang, length, width, col):
    leaf = pygame.Surface((width, length), pygame.SRCALPHA)
    pygame.draw.ellipse(leaf, col, (0, 1, width - 1, length - 2))
    vein = tuple(max(0, c - 55) for c in col)
    pygame.draw.line(leaf, vein, (width // 2, 3), (width // 2, length - 4), 1)
    rot = pygame.transform.rotate(leaf, ang)
    dst.blit(rot, rot.get_rect(center=(int(x), int(y))))


def _leaf_ring(w, h, rect):
    """Плотная лиственная рамка вокруг прямоугольника, остальное прозрачное."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rng = random.Random(11)
    greens = ((18, 108, 28), (34, 148, 40), (12, 82, 22), (56, 166, 46),
              (24, 126, 32), (8, 68, 18), (74, 176, 52), (28, 96, 30))
    x, y, rw, rh = rect
    for grow, step, llen in ((0, 7, (16, 26)), (7, 9, (12, 20))):
        edges = (
            (x - grow, y, x + rw + grow, y, -90, max(8, int((rw + 16) / step))),
            (x - grow, y + rh, x + rw + grow, y + rh, 90, max(8, int((rw + 16) / step))),
            (x, y - grow, x, y + rh + grow, 180, max(8, int((rh + 16) / step))),
            (x + rw, y - grow, x + rw, y + rh + grow, 0, max(8, int((rh + 16) / step))),
        )
        for x0, y0, x1, y1, ang, n in edges:
            for i in range(n):
                t = (i + rng.random() * 0.35) / n
                px = x0 + (x1 - x0) * t + rng.randint(-2, 2)
                py = y0 + (y1 - y0) * t + rng.randint(-2, 2)
                col = greens[rng.randrange(len(greens))]
                _blit_leaf(surf, px, py, ang + rng.randint(-32, 32),
                           rng.randint(*llen), rng.randint(7, 12), col)
    return surf


SW, SH = 64, 64


def _scene(col):
    surf = pygame.Surface((SW, SH))
    surf.fill(col)
    return surf


def _dot(surf, x, y, col):
    if 0 <= x < SW and 0 <= y < SH:
        surf.set_at((int(x), int(y)), col)


def _blob(surf, cx, cy, rx, ry, col):
    for y in range(int(cy - ry), int(cy + ry) + 1):
        for x in range(int(cx - rx), int(cx + rx) + 1):
            if ry and rx and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                _dot(surf, x, y, col)


def _tri(surf, x, top, bottom, half, col):
    span = max(1, bottom - top)
    for y in range(int(top), int(bottom)):
        w = max(1, int(half * (y - top) / span))
        pygame.draw.line(surf, col, (x - w, y), (x + w, y))


def _up(surf):
    return pygame.transform.scale(surf, (160, 160)).convert_alpha()


def _season_spring():
    """Небо, луг и три цветущих дерева."""
    s = _scene((112, 188, 232))
    _blob(s, 16, 10, 9, 4, (246, 250, 255))
    _blob(s, 44, 8, 11, 4, (236, 246, 255))
    pygame.draw.rect(s, (86, 178, 64), (0, 36, SW, 28))
    pygame.draw.rect(s, (64, 156, 48), (0, 48, SW, 16))
    for cx, top in ((14, 28), (33, 24), (50, 30)):
        pygame.draw.rect(s, (118, 74, 44), (cx, top + 6, 3, 16))
        _blob(s, cx + 1, top + 2, 8, 7, (244, 126, 168))
        _blob(s, cx - 4, top, 4, 4, (255, 176, 198))
        _blob(s, cx + 5, top + 4, 4, 3, (214, 86, 132))
    return _up(s)


def _season_summer():
    """Синее небо, птицы, зелёный холм и тёмная кромка леса."""
    s = _scene((62, 166, 228))
    ink = (28, 36, 48)
    for bx, by in ((18, 12), (30, 9), (44, 14)):
        _dot(s, bx, by, ink)
        _dot(s, bx - 1, by - 1, ink)
        _dot(s, bx + 1, by - 1, ink)
        _dot(s, bx - 2, by, ink)
        _dot(s, bx + 2, by, ink)
    for x in range(SW):
        crest = 26 + int(6 * math.sin(x / 7.0)) - x // 16
        pygame.draw.line(s, (168, 206, 62), (x, crest), (x, 46))
        pygame.draw.line(s, (186, 214, 78), (x, crest), (x, crest + 6))
    pygame.draw.rect(s, (24, 92, 32), (0, 46, SW, 18))
    for x in range(0, SW, 4):
        h = 6 + (x * 3) % 5
        pygame.draw.rect(s, (16, 72, 26), (x, 46 - h, 3, h + 4))
    return _up(s)


def _season_autumn():
    """Осенние кроны и домик посреди них."""
    s = _scene((214, 108, 28))
    rng = random.Random(4)
    for _ in range(90):
        _blob(s, rng.randint(2, 61), rng.randint(2, 60), rng.randint(3, 7), rng.randint(3, 6),
              rng.choice(((196, 72, 18), (232, 132, 28), (168, 48, 16), (240, 160, 40))))
    pygame.draw.rect(s, (150, 196, 220), (22, 4, 20, 10))
    pygame.draw.polygon(s, (92, 58, 32), [(18, 36), (32, 22), (46, 36)])
    pygame.draw.rect(s, (118, 72, 40), (20, 36, 24, 16))
    pygame.draw.rect(s, (70, 42, 24), (29, 42, 6, 10))
    pygame.draw.rect(s, (186, 214, 230), (22, 40, 5, 5))
    pygame.draw.rect(s, (186, 214, 230), (37, 40, 5, 5))
    pygame.draw.rect(s, (150, 150, 154), (40, 24, 3, 8))
    pygame.draw.rect(s, (120, 78, 36), (28, 52, 8, 6))
    return _up(s)


def _season_winter():
    """Снежные ели и дорожка между ними."""
    s = _scene((176, 196, 214))
    pygame.draw.rect(s, (232, 238, 244), (0, 40, SW, 24))
    pygame.draw.polygon(s, (214, 224, 232), [(24, 64), (32, 40), (40, 64)])
    for x, top, h in ((10, 16, 30), (22, 22, 26), (34, 12, 34), (46, 20, 28), (56, 14, 32)):
        _tri(s, x, top, top + h, 7, (36, 78, 62))
        _tri(s, x, top - 1, top + 6, 4, (244, 248, 252))
        pygame.draw.rect(s, (92, 64, 44), (x - 1, top + h - 4, 2, 6))
    return _up(s)


def _food_picture(kind):
    s = pygame.Surface((48, 48))
    s.fill((255, 244, 220))
    if kind == "pizza":
        pygame.draw.circle(s, (196, 120, 48), (24, 24), 20)
        pygame.draw.circle(s, (186, 40, 36), (24, 24), 15)
        for p in ((16, 16), (30, 18), (22, 30), (32, 28)):
            pygame.draw.circle(s, (250, 210, 70), p, 3)
    elif kind == "burger":
        pygame.draw.ellipse(s, (150, 78, 32), (8, 8, 32, 12))
        pygame.draw.rect(s, (70, 150, 40), (8, 18, 32, 6))
        pygame.draw.rect(s, (120, 40, 28), (8, 24, 32, 8))
        pygame.draw.ellipse(s, (214, 160, 64), (8, 30, 32, 10))
    elif kind == "sushi":
        s.fill((236, 228, 208))
        for cx in (12, 24, 36):
            pygame.draw.ellipse(s, (36, 36, 40), (cx - 8, 12, 16, 24))
            pygame.draw.ellipse(s, (250, 250, 246), (cx - 6, 15, 12, 18))
            pygame.draw.ellipse(s, (214, 64, 54), (cx - 4, 20, 8, 8))
    else:
        pygame.draw.rect(s, (236, 150, 170), (10, 22, 28, 16))
        pygame.draw.polygon(s, (250, 190, 200), [(10, 22), (24, 8), (38, 22)])
        pygame.draw.circle(s, (220, 50, 70), (24, 16), 2)
    return pygame.transform.scale(s, (144, 144)).convert_alpha()


def make_web_ui():
    """Дерево, бумага и листья для опроса и меню мебели. Персонажей тут нет."""
    wood = pygame.Surface((64, 128))
    for i, x in enumerate(range(0, 64, 16)):
        shade = 10 if i % 2 == 0 else -8
        col = (78 + shade, 50 + shade, 28 + shade)
        pygame.draw.rect(wood, col, (x, 0, 16, 128))
        pygame.draw.line(wood, (46, 28, 16), (x, 0), (x, 127))
    _upload_surf("ui_wood", wood, repeat=True)

    paper = pygame.Surface((32, 32))
    for y in range(2):
        for x in range(2):
            col = (244, 236, 214) if (x + y) % 2 == 0 else (232, 220, 192)
            pygame.draw.rect(paper, col, (x * 16, y * 16, 16, 16))
    _upload_surf("ui_paper", paper, repeat=True)

    _upload_surf("ui_leaves", _leaf_ring(WIN_W, WIN_H, QUIZ_BOARD))
    _upload_surf("ui_leaves_furn", _leaf_ring(WIN_W, WIN_H, (6, 6, WIN_W - 12, WIN_H - 12)))

    tag = pygame.Surface((156, 34), pygame.SRCALPHA)
    pygame.draw.rect(tag, (118, 72, 34), (0, 2, 156, 30))
    pygame.draw.rect(tag, (62, 36, 16), (0, 2, 156, 30), 2)
    pygame.draw.circle(tag, (48, 28, 14), (12, 17), 3)
    pygame.draw.circle(tag, (48, 28, 14), (144, 17), 3)
    _upload_surf("ui_tag", tag)

    cur = pygame.Surface((18, 22), pygame.SRCALPHA)
    arrow = [(1, 1), (1, 18), (5, 14), (8, 20), (11, 18), (8, 12), (15, 12)]
    pygame.draw.polygon(cur, (20, 16, 12), arrow)
    inner = [(3, 4), (3, 15), (6, 12), (8, 16), (10, 15), (7, 11), (13, 11)]
    pygame.draw.polygon(cur, (255, 255, 255), inner)
    _upload_surf("ui_cursor", cur)

    for name, draw in (("spring", _season_spring), ("summer", _season_summer),
                       ("autumn", _season_autumn), ("winter", _season_winter)):
        _upload_surf("season_" + name, draw())
    for i, kind in enumerate(("pizza", "burger", "sushi", "cake")):
        _upload_surf("food_%d" % i, _food_picture(kind))
    make_furn_icons()


INK = (32, 20, 12)
FW, FH = 64, 48


def _ficon():
    return pygame.Surface((FW, FH), pygame.SRCALPHA)


def _r(s, x, y, w, h, col):
    pygame.draw.rect(s, INK, (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.rect(s, col, (x, y, w, h))


def _o(s, x, y, w, h, col):
    pygame.draw.ellipse(s, INK, (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.ellipse(s, col, (x, y, w, h))


def _poly(s, pts, col):
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, 1)


def _icon_sofa():
    s = _ficon()
    _r(s, 6, 30, 8, 8, (96, 62, 36))
    _r(s, 50, 30, 8, 8, (96, 62, 36))
    _r(s, 8, 10, 48, 24, (186, 78, 124))
    _r(s, 10, 12, 44, 8, (140, 48, 90))
    _r(s, 8, 14, 8, 18, (160, 58, 104))
    _r(s, 48, 14, 8, 18, (160, 58, 104))
    for x in (16, 28, 40):
        _r(s, x, 20, 10, 12, (230, 150, 180))
    return s


def _icon_chair():
    s = _ficon()
    _r(s, 14, 32, 6, 8, (40, 40, 44))
    _r(s, 44, 32, 6, 8, (40, 40, 44))
    _r(s, 16, 6, 32, 28, (48, 48, 54))
    _r(s, 18, 8, 28, 10, (24, 24, 28))
    _r(s, 14, 16, 8, 16, (36, 36, 40))
    _r(s, 42, 16, 8, 16, (36, 36, 40))
    _r(s, 20, 20, 24, 12, (90, 90, 98))
    return s


def _icon_table():
    s = _ficon()
    _r(s, 10, 28, 5, 12, (70, 44, 24))
    _r(s, 49, 28, 5, 12, (70, 44, 24))
    _o(s, 8, 8, 48, 26, (168, 112, 62))
    _o(s, 16, 12, 32, 16, (206, 156, 96))
    return s


def _icon_lamp():
    s = _ficon()
    _o(s, 22, 34, 20, 8, (90, 64, 40))
    _r(s, 30, 18, 4, 16, (70, 50, 32))
    _poly(s, [(14, 18), (50, 18), (44, 8), (20, 8)], (236, 150, 176))
    _o(s, 28, 12, 8, 6, (255, 230, 120))
    return s


def _icon_plant(big=False):
    s = _ficon()
    _poly(s, [(22, 28), (42, 28), (46, 42), (18, 42)], (176, 96, 52))
    _r(s, 20, 26, 24, 4, (140, 74, 40))
    leaves = ((32, 16, 16, 14), (18, 14, 14, 12), (36, 10, 14, 12), (24, 8, 12, 10))
    if big:
        leaves = ((32, 14, 20, 16), (14, 16, 16, 14), (38, 8, 16, 14), (22, 4, 14, 12), (30, 18, 8, 8))
    for x, y, w, h in leaves:
        _o(s, x, y, w, h, (40, 150, 58) if not big else (36, 140, 48))
    if big:
        _o(s, 28, 14, 8, 8, (230, 90, 120))
    return s


def _icon_shelf():
    s = _ficon()
    _r(s, 8, 6, 48, 36, (150, 102, 58))
    _r(s, 12, 10, 40, 28, (92, 60, 34))
    colors = ((190, 48, 42), (48, 90, 180), (230, 190, 50), (48, 140, 70), (140, 60, 160))
    x = 14
    for i, col in enumerate(colors):
        h = 16 + (i % 3) * 4
        _r(s, x, 12 + (24 - h), 6, h, col)
        x += 8
    return s


def _icon_chest():
    s = _ficon()
    _r(s, 10, 16, 44, 24, (168, 36, 40))
    _r(s, 10, 10, 44, 12, (140, 24, 30))
    _r(s, 12, 20, 40, 4, (210, 170, 50))
    _r(s, 28, 18, 8, 8, (230, 196, 70))
    return s


def _icon_bush():
    s = _ficon()
    for x, y, w, h, col in ((8, 16, 22, 20, (30, 120, 40)), (34, 14, 22, 22, (48, 150, 52)),
                            (20, 8, 24, 20, (70, 170, 60)), (18, 22, 28, 16, (24, 100, 36))):
        _o(s, x, y, w, h, col)
    return s


def _icon_counter():
    s = _ficon()
    _r(s, 4, 20, 56, 20, (210, 214, 220))
    _r(s, 4, 28, 56, 12, (150, 156, 164))
    _r(s, 8, 8, 18, 14, (36, 36, 40))
    for dx, dy in ((2, 2), (10, 2), (2, 8), (10, 8)):
        _o(s, 8 + dx, 8 + dy, 5, 4, (180, 180, 186))
    _o(s, 36, 12, 16, 12, (120, 170, 190))
    _r(s, 42, 8, 3, 6, (170, 176, 182))
    return s


def _icon_dine():
    s = _ficon()
    for x in (8, 50):
        _r(s, x, 16, 5, 24, (90, 58, 32))
    _r(s, 6, 14, 52, 16, (176, 122, 70))
    _o(s, 26, 16, 12, 10, (245, 245, 248))
    _o(s, 29, 18, 6, 5, (220, 70, 60))
    return s


def _icon_seat():
    s = _ficon()
    _r(s, 18, 34, 5, 8, (90, 58, 32))
    _r(s, 41, 34, 5, 8, (90, 58, 32))
    _r(s, 16, 22, 32, 12, (186, 132, 74))
    _r(s, 20, 6, 5, 20, (120, 78, 42))
    _r(s, 39, 6, 5, 20, (120, 78, 42))
    _r(s, 20, 8, 24, 6, (150, 100, 56))
    return s


def _icon_bed():
    s = _ficon()
    _r(s, 8, 8, 48, 32, (70, 48, 32))
    _r(s, 12, 14, 40, 22, (245, 245, 248))
    _r(s, 14, 16, 16, 10, (255, 255, 255))
    _r(s, 14, 26, 36, 8, (255, 214, 70))
    _o(s, 40, 28, 8, 6, (210, 90, 140))
    return s


def _icon_night():
    s = _ficon()
    _r(s, 16, 16, 32, 24, (168, 114, 64))
    _r(s, 20, 22, 24, 12, (140, 92, 50))
    _o(s, 28, 26, 6, 6, (230, 190, 80))
    _r(s, 30, 6, 4, 10, (80, 56, 36))
    _poly(s, [(24, 8), (40, 8), (36, 2), (28, 2)], (255, 220, 120))
    return s


def _icon_wardrobe():
    s = _ficon()
    _r(s, 10, 4, 44, 40, (150, 102, 56))
    _r(s, 14, 8, 16, 32, (176, 126, 74))
    _r(s, 34, 8, 16, 32, (176, 126, 74))
    _o(s, 26, 22, 4, 4, (230, 196, 70))
    _o(s, 34, 22, 4, 4, (230, 196, 70))
    return s


def _icon_desk():
    s = _ficon()
    _r(s, 8, 28, 6, 12, (90, 58, 32))
    _r(s, 50, 28, 6, 12, (90, 58, 32))
    _r(s, 6, 18, 52, 12, (176, 122, 70))
    _r(s, 12, 20, 16, 8, (248, 248, 250))
    _r(s, 40, 8, 4, 12, (80, 56, 36))
    _poly(s, [(34, 10), (50, 10), (46, 4), (38, 4)], (255, 220, 110))
    return s


def _icon_bath():
    s = _ficon()
    _r(s, 8, 34, 6, 6, (180, 184, 190))
    _r(s, 50, 34, 6, 6, (180, 184, 190))
    _r(s, 6, 12, 52, 24, (170, 220, 210))
    _r(s, 12, 16, 40, 16, (70, 160, 200))
    _r(s, 28, 6, 4, 8, (190, 196, 202))
    _o(s, 24, 4, 12, 6, (200, 206, 212))
    return s


def _icon_toilet():
    s = _ficon()
    _r(s, 18, 4, 28, 14, (236, 238, 242))
    _o(s, 14, 16, 36, 26, (248, 248, 250))
    _o(s, 20, 22, 24, 14, (190, 210, 220))
    return s


def _icon_sink():
    s = _ficon()
    _r(s, 8, 18, 48, 22, (230, 232, 236))
    _o(s, 18, 22, 28, 14, (120, 176, 198))
    _r(s, 30, 8, 4, 12, (180, 186, 192))
    _r(s, 26, 6, 12, 4, (200, 206, 212))
    return s


def _icon_lcounter():
    s = _ficon()
    _r(s, 4, 22, 56, 18, (214, 216, 220))
    _r(s, 4, 32, 56, 8, (160, 164, 170))
    for x, col in ((8, (230, 90, 120)), (22, (240, 200, 60)), (36, (60, 120, 200)), (48, (60, 160, 80))):
        _r(s, x, 12, 10, 12, col)
    return s


def _icon_washer():
    s = _ficon()
    _r(s, 12, 4, 40, 40, (240, 242, 246))
    _o(s, 20, 12, 24, 24, (50, 56, 64))
    _o(s, 26, 18, 12, 12, (150, 190, 210))
    for i, x in enumerate((18, 28, 38)):
        _o(s, x, 6, 4, 4, (80, 180, 90) if i == 0 else (180, 60, 60))
    return s


def make_furn_icons():
    """Иконки панели: каждая собрана из нескольких фигур, чтобы читаться в клетке."""
    icons = {
        "sofa": _icon_sofa, "chair": _icon_chair, "table": _icon_table, "lamp": _icon_lamp,
        "plant": _icon_plant, "shelf": _icon_shelf, "chest": _icon_chest, "bush": _icon_bush,
        "counter": _icon_counter, "kplant": lambda: _icon_plant(True), "dine": _icon_dine,
        "seat": _icon_seat, "bed": _icon_bed, "night": _icon_night, "wardrobe": _icon_wardrobe,
        "desk": _icon_desk, "bath": _icon_bath, "toilet": _icon_toilet, "sink": _icon_sink,
        "lcounter": _icon_lcounter, "washer": _icon_washer,
    }
    for name, draw in icons.items():
        _upload_surf("fi_" + name, draw())


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
               (-42, 3.2, -66), (-20, 3.2, -66), (10, 3.2, -66), (36, 3.2, -66), (96, 3.2, -66)]
CS_START = 14.0                  # положение поезда у платформы (s вдоль трассы)
PORTAL_BACK = 24.0               # пересчитывается после удлинения прямой, чтобы дырка осталась на месте
RING_LEN = 18.0                  # красно-синие кольца
WHITE_LEN = 52.0                 # белый проход за кольцами: его надо проезжать, а не проскакивать


def build_coaster_data():
    COASTER.update(YW.make_track(COASTER_PTS, sigma_m=3.0))
    # стена с дыркой на прежнем месте: лишние метры прямой уходят в белый проход
    COASTER["s_wall"] = COASTER["L"] - (PORTAL_BACK + WHITE_LEN)


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
    if -72 < x < 180 and -78 < z < -54:          # финальная прямая, дырка и длинный белый проход
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
    fx, fz = wt[0], wt[2]
    ln = math.hypot(fx, fz) or 1.0
    fx, fz = fx / ln, fz / ln
    span = RING_LEN + WHITE_LEN + 6.0

    def in_tunnel(a):
        dx, dz = a[0] - wp[0], a[2] - wp[2]
        return -3.0 < dx * fx + dz * fz < span and abs(dx * fz - dz * fx) < 6.0

    YW.build_track_geom(COASTER, supports=True, coll=COLL, skip=in_tunnel)
    YW.build_portal(wp, (wt[0], wt[2]), COLL, white=WHITE_LEN)
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
        make_web_ui()
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
        self.quiz = None            # опрос, рисовалка и расстановка мебели: dict(phase, step, season, food)
        self.paint = None
        self.furnish = None
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
        if "--furnish" in args:
            self.quiz = dict(phase="furnish", step=2, season=1, food=0)
            self.begin_furnish()
        elif "--paint" in args:
            self.quiz = dict(phase="paint", step=2, season=1, food=0)
            self.begin_drawing(0)
        elif "--quiz" in args:
            st = int(args[args.index("--quiz") + 1])
            self.quiz = dict(phase="ask", step=min(st, 1), season=1 if st else None, food=None)
        elif not self.shot:
            self.try_resume()                              # опрос и рисунки, либо сразу парк, если уже сохранено
        if "--door" in args:
            self.door_open = 0.7
        self.sync_music()

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
            arr[y, x] = (255, 255, 255, 255)
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
    def set_answers(self, season, food, layout=None):
        self.answers = (season, food)
        self.world = YW.World(season, food, layout)
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
        if not data.get("furniture_done"):
            self.quiz = dict(phase="furnish", step=2, season=int(season), food=int(food))
            self.begin_furnish()
            return
        self.set_answers(int(season), int(food), data.get("furniture"))
        self.quiz = None
        self.park_t0 = self.t

    def begin_drawing(self, index):
        if index >= len(DRAW_PROMPTS):
            self.begin_furnish()
            return
        surf = pygame.Surface((192, 120))
        surf.fill((255, 255, 255))
        name, _ = player_name()
        prompt = DRAW_PROMPTS[index][0]
        if index == 0:
            prompt = "%s, давай порисуем. %s" % (name, prompt)
        self.paint = dict(surf=surf, tool="pencil", color=(0, 0, 0), last=None, down=False,
                          line_a=None, dirty=True, snd_t=0.0, warn="", prompt=prompt, react="", live=0.0)
        self.quiz["phase"] = "paint"
        self.quiz["draw_i"] = index
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()

    def begin_furnish(self):
        items = [dict(it) for it in YW.empty_layout()]
        self.furnish = dict(items=items, drag=None, sel=None, warn="", floor=0,
                            zoom=1.0, pan_x=0.0, pan_y=0.0, pan_drag=None)
        if self.quiz is None:
            self.quiz = dict(phase="furnish", step=2, season=1, food=0)
        self.quiz["phase"] = "furnish"
        self.paint = None
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()

    def finish_intro(self):
        qz = self.quiz
        season = qz["season"] if qz and qz.get("season") is not None else 1
        food = qz["food"] if qz and qz.get("food") is not None else 0
        layout = [dict(it) for it in self.furnish["items"]] if self.furnish else None
        self.apply_saved_drawings()
        self.set_answers(int(season), int(food), layout)
        self.quiz = None
        self.paint = None
        self.furnish = None
        self.park_t0 = self.t
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()
        self.audio.play("chime", .9)

    def paint_geom(self):
        W, H = WIN_W, WIN_H
        m, bar, pal_h, tool_w = 16, 48, 78, 64
        top = m + bar
        board = pygame.Rect(m, top, W - m * 2, H - top - m)
        tools = pygame.Rect(board.x + 8, board.y + 8, tool_w, board.h - pal_h - 12)
        canvas = (tools.right + 8, board.y + 8, board.right - 8 - (tools.right + 8), tools.h)
        pal = pygame.Rect(board.x + 8, board.bottom - pal_h + 4, board.w - 16, pal_h - 12)
        bw, bh, gap = 52, 48, 6
        ox = tools.x + (tools.w - bw) / 2
        oy = tools.y + max(0, (tools.h - (5 * bh + 4 * gap)) / 2)
        names = ("pencil", "brush", "fill", "line", "erase")
        slots = [(name, pygame.Rect(ox, oy + i * (bh + gap), bw, bh)) for i, name in enumerate(names)]
        sw, sh, gy = 34, 24, 6
        span = pal.w - 56
        gx = (span - 11 * sw) / 10
        colors = []
        for i, col in enumerate(PAINT_COLORS):
            c, r = i % 11, i // 11
            colors.append((col, pygame.Rect(pal.x + 48 + c * (sw + gx), pal.y + 6 + r * (sh + gy), sw, sh)))
        done = pygame.Rect(W - m - 100, m + 11, 92, 26)
        cur = pygame.Rect(pal.x + 6, pal.y + (pal.h - 36) / 2, 36, 36)
        return dict(board=board, tools=tools, canvas=canvas, pal=pal, slots=slots,
                    colors=colors, done=done, current=cur)

    def _line_boil(self, surf, phase):
        """Кадр line boil: куски линий сдвигаются на пиксель, заливка почти стоит."""
        w, h = surf.get_size()
        src = pygame.surfarray.array3d(surf)
        xs = np.arange(w, dtype=np.int32)[:, None]
        ys = np.arange(h, dtype=np.int32)[None, :]
        cell = 7
        hsh = ((xs // cell) * 17 + (ys // cell) * 31 + int(phase) * 13) % 5
        table = np.array([[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]], np.int32)
        sx = np.clip(xs - table[hsh, 0], 0, w - 1)
        sy = np.clip(ys - table[hsh, 1], 0, h - 1)
        out = pygame.Surface((w, h))
        pygame.surfarray.blit_array(out, src[sx, sy])
        return out

    def paint_upload(self):
        p = self.paint
        if not p:
            return
        phase = int(p.get("live", 0.0) * 8) % 4
        if not p["dirty"] and p.get("_boil") == phase and "canvas" in TEX:
            return
        surf = self._line_boil(p["surf"], phase)
        w, h = surf.get_size()
        data = pygame.image.tobytes(surf, "RGBA", True)
        if "canvas" not in TEX:
            upload("canvas", data, w, h, mip=False, repeat=False)
        else:
            glBindTexture(GL_TEXTURE_2D, TEX["canvas"])
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)
        p["dirty"] = False
        p["_boil"] = phase

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
        return g["done"].collidepoint(pos)

    def _hit_tool(self, pos, g):
        for name, rect in g["slots"]:
            if rect.collidepoint(pos):
                return name
        return None

    def _hit_color(self, pos, g):
        for col, rect in g["colors"]:
            if rect.collidepoint(pos):
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

    def furnish_geom(self):
        f = self.furnish
        m, bar, tray_h = FURN_MARGIN, FURN_BAR, FURN_TRAY
        top = m + bar
        x0, z0, x1, z1 = -9.2, -7.85, 9.2, 7.85
        rw, rh = x1 - x0, z1 - z0
        area_w = WIN_W - m * 2
        area_h = WIN_H - top - tray_h - m
        base = min((area_w - 8) / rw, (area_h - 6) / rh)
        scale = base * f["zoom"]
        dw, dh = rw * scale, rh * scale
        ox = m + (area_w - dw) / 2 + f["pan_x"]
        oy = top + (area_h - dh) / 2 + f["pan_y"]
        fl = dict(lvl=f["floor"], ox=ox, oy=oy, scale=scale, dw=dw, dh=dh, x0=x0, z0=z0,
                  view=(m, top, area_w, area_h))
        btns = dict(
            f0=pygame.Rect(m + 8, m + 5, 84, 26),
            f1=pygame.Rect(m + 100, m + 5, 84, 26),
            default=pygame.Rect(WIN_W - m - 246, m + 5, 140, 26),
            done=pygame.Rect(WIN_W - m - 100, m + 5, 92, 26),
        )
        return dict(floor=fl, tray=(m, WIN_H - m - tray_h, area_w, tray_h), top=top, tray_h=tray_h,
                    margin=m, area_w=area_w, area_h=area_h, btns=btns)

    def furnish_w2s(self, x, z, fl):
        return fl["ox"] + (x - fl["x0"]) * fl["scale"], fl["oy"] + (z - fl["z0"]) * fl["scale"]

    def furnish_s2w(self, sx, sy, fl):
        return fl["x0"] + (sx - fl["ox"]) / fl["scale"], fl["z0"] + (sy - fl["oy"]) / fl["scale"]

    def _floor_at(self, pos, g):
        x, y, w, h = g["floor"]["view"]
        if x <= pos[0] <= x + w and y <= pos[1] <= y + h:
            return g["floor"]
        return None

    def _tray_slots(self, g):
        dragging = self.furnish["drag"]["id"] if self.furnish.get("drag") else None
        items = [it for it in self.furnish["items"] if not it.get("placed") and it["id"] != dragging]
        cols = 13
        tx, ty, tw, _ = g["tray"]
        cw = tw / cols
        th = 44
        ox, oy = tx, ty + 24
        slots = []
        for i, it in enumerate(items):
            c, r = i % cols, i // cols
            slots.append((it, pygame.Rect(ox + c * cw + 2, oy + r * th, cw - 4, th - 4)))
        return slots

    def _tray_hit(self, pos, g):
        for it, rect in self._tray_slots(g):
            if rect.collidepoint(pos):
                return it
        return None

    def _hit_floor_btn(self, pos, g):
        if g["btns"]["f0"].collidepoint(pos):
            return 0
        if g["btns"]["f1"].collidepoint(pos):
            return 1
        return None

    def _hit_default(self, pos, g):
        return g["btns"]["default"].collidepoint(pos)

    def _furnish_hit(self, pos, g):
        fl = self._floor_at(pos, g)
        if not fl:
            return None
        x, z = self.furnish_s2w(pos[0], pos[1], fl)
        best, best_d = None, 1e9
        for it in self.furnish["items"]:
            if not it.get("placed") or it["lvl"] != fl["lvl"]:
                continue
            spec = YW.piece_of(it["id"])
            th = math.radians(it["ry"])
            co, si = math.cos(th), math.sin(th)
            dx, dz = x - it["x"], z - it["z"]
            lx, lz = co * dx - si * dz, si * dx + co * dz
            inside = abs(lx) <= spec["w"] / 2 and abs(lz) <= spec["d"] / 2
            dist = math.hypot(dx, dz) * fl["scale"]
            if (inside or dist < 16) and dist < best_d:
                best, best_d = it, dist
        return best

    def furnish_zoom(self, direction, pos):
        f = self.furnish
        if not f or not direction:
            return
        g = self.furnish_geom()
        over = self._floor_at(pos, g)
        wx = wz = None
        if over:
            wx, wz = self.furnish_s2w(pos[0], pos[1], g["floor"])
        f["zoom"] = clamp(f["zoom"] * (1.12 if direction > 0 else 1 / 1.12), 1.0, 3.4)
        if f["zoom"] <= 1.02:
            f["zoom"], f["pan_x"], f["pan_y"] = 1.0, 0.0, 0.0
            return
        if wx is None:
            return
        met = self.furnish_geom()
        fl = met["floor"]
        f["pan_x"] = pos[0] - (wx - fl["x0"]) * fl["scale"] - (met["margin"] + (met["area_w"] - fl["dw"]) / 2)
        f["pan_y"] = pos[1] - (wz - fl["z0"]) * fl["scale"] - (met["top"] + (met["area_h"] - fl["dh"]) / 2)

    def _set_furn_floor(self, lvl):
        f = self.furnish
        f["floor"] = lvl
        f["zoom"], f["pan_x"], f["pan_y"] = 1.0, 0.0, 0.0

    def furnish_pointer(self, pos, kind):
        f = self.furnish
        if not f:
            return
        g = self.furnish_geom()
        if kind == "down":
            if g["btns"]["done"].collidepoint(pos):
                self.furnish_finish()
                return
            if self._hit_default(pos, g):
                f["items"] = [dict(it) for it in YW.default_layout()]
                f["drag"] = None
                f["sel"] = None
                f["warn"] = ""
                self._set_furn_floor(0)
                self.audio.play("chime", .6)
                return
            floor = self._hit_floor_btn(pos, g)
            if floor is not None:
                self._set_furn_floor(floor)
                self.audio.play("tick", .45)
                return
            tray = self._tray_hit(pos, g)
            if tray:
                f["sel"] = tray["id"]
                f["drag"] = dict(id=tray["id"], x0=tray["x"], z0=tray["z"], lvl0=tray["lvl"],
                                 placed0=False, gx=0.0, gz=0.0)
                f["pan_drag"] = None
                self.audio.play("tick", .35)
                return
            hit = self._furnish_hit(pos, g)
            fl = self._floor_at(pos, g)
            if fl and f.get("sel") and not hit:
                chosen = next((i for i in f["items"] if i["id"] == f["sel"]), None)
                if chosen and not chosen.get("placed"):
                    wx, wz = self.furnish_s2w(pos[0], pos[1], fl)
                    chosen["placed"] = True
                    chosen["lvl"] = fl["lvl"]
                    chosen["x"], chosen["z"] = wx, wz
                    f["drag"] = dict(id=chosen["id"], x0=0.0, z0=0.0, lvl0=0, placed0=False, gx=0.0, gz=0.0)
                    return
            if hit and fl:
                wx, wz = self.furnish_s2w(pos[0], pos[1], fl)
                f["sel"] = hit["id"]
                f["drag"] = dict(id=hit["id"], x0=hit["x"], z0=hit["z"], lvl0=hit["lvl"],
                                 placed0=True, gx=hit["x"] - wx, gz=hit["z"] - wz)
                f["pan_drag"] = None
                self.audio.play("tick", .35)
                return
            if fl and f["zoom"] > 1.02:
                f["pan_drag"] = (pos[0], pos[1], f["pan_x"], f["pan_y"])
                f["sel"] = None
        elif kind == "move" and f.get("pan_drag"):
            x0, y0, px, py = f["pan_drag"]
            f["pan_x"] = px + pos[0] - x0
            f["pan_y"] = py + pos[1] - y0
        elif kind == "move" and f["drag"]:
            it = next(i for i in f["items"] if i["id"] == f["drag"]["id"])
            fl = self._floor_at(pos, g)
            over_tray = pygame.Rect(*g["tray"]).collidepoint(pos)
            if fl and not over_tray:
                wx, wz = self.furnish_s2w(pos[0], pos[1], fl)
                it["placed"] = True
                it["lvl"] = fl["lvl"]
                it["x"] = wx + f["drag"]["gx"]
                it["z"] = wz + f["drag"]["gz"]
            else:
                it["placed"] = False
        elif kind == "up":
            f["pan_drag"] = None
            if not f["drag"]:
                return
            it = next(i for i in f["items"] if i["id"] == f["drag"]["id"])
            if not it.get("placed"):
                f["warn"] = ""
            elif YW.layout_ok(f["items"]):
                f["warn"] = ""
            else:
                d = f["drag"]
                it["x"], it["z"], it["lvl"], it["placed"] = d["x0"], d["z0"], d["lvl0"], d["placed0"]
                f["warn"] = "Сюда не встанет: стена, лестница или другая мебель."
                self.audio.play("tick", .7)
            f["drag"] = None

    def furnish_rotate(self, pos=None):
        f = self.furnish
        if not f or f["drag"]:
            return
        it = self._furnish_hit(pos, self.furnish_geom()) if pos is not None else None
        if it is None:
            it = next((i for i in f["items"] if i["id"] == f["sel"]), None)
        if it is None or not it.get("placed") or YW.piece_of(it["id"]).get("round"):
            if it is not None:
                f["sel"] = it["id"]
            return
        old = it["ry"]
        it["ry"] = (int(it["ry"]) + 90) % 360
        if YW.layout_ok(f["items"]):
            f["sel"] = it["id"]
            f["warn"] = ""
            self.audio.play("tick", .55)
        else:
            it["ry"] = old
            f["warn"] = "Так не поворачивается: упирается в стену или мебель."
            self.audio.play("tick", .7)

    def furnish_finish(self):
        f = self.furnish
        qz = self.quiz
        if not f or not qz:
            return
        if not YW.layout_ok(f["items"]):
            f["warn"] = "Сначала освободи двери и лестницу."
            self.audio.play("tick", .7)
            return
        folder = profile_dir()
        os.makedirs(folder, exist_ok=True)
        data = self.read_profile() or {}
        name, _ = player_name()
        data["name"] = name
        data["season"] = int(qz["season"] if qz.get("season") is not None else 1)
        data["food"] = int(qz["food"] if qz.get("food") is not None else 0)
        data["furniture_done"] = True
        data["furniture"] = [dict(id=it["id"], x=round(float(it["x"]), 3), z=round(float(it["z"]), 3),
                                  ry=int(it["ry"]) % 360, lvl=int(it["lvl"]), placed=True)
                             for it in f["items"] if it.get("placed")]
        with open(os.path.join(folder, "profile.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        self.audio.play("chime", .8)
        self.finish_intro()

    def poly(self, pts, rgba):
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        glColor4f(*rgba)
        glBegin(GL_TRIANGLE_FAN)
        for x, y in pts:
            glVertex2f(x, y)
        glEnd()

    def loop(self, pts, rgba):
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        glColor4f(*rgba)
        glLineWidth(2)
        glBegin(GL_LINE_LOOP)
        for x, y in pts:
            glVertex2f(x, y)
        glEnd()
        glLineWidth(1)

    def disk(self, x, y, r, rgba, n=18):
        glBindTexture(GL_TEXTURE_2D, TEX["white"])
        glColor4f(*rgba)
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(x, y)
        for i in range(n + 1):
            a = i * TAU / n
            glVertex2f(x + math.cos(a) * r, y + math.sin(a) * r)
        glEnd()

    def _plan_rect(self, fl, x0, z0, x1, z1, rgba):
        sx, sy = self.furnish_w2s(x0, z0, fl)
        sx2, sy2 = self.furnish_w2s(x1, z1, fl)
        self.rect(min(sx, sx2), min(sy, sy2), abs(sx2 - sx), abs(sy2 - sy), rgba)

    def _draw_icon(self, it, fl, parts):
        th = math.radians(it["ry"])
        co, si = math.cos(th), math.sin(th)
        ink = (0.12, 0.07, 0.04, 1)
        for part in parts:
            if part[0] == "disk":
                _, lx, lz, rad, col = part
                wx = it["x"] + lx * co + lz * si
                wz = it["z"] - lx * si + lz * co
                sx, sy = self.furnish_w2s(wx, wz, fl)
                self.disk(sx, sy, rad * fl["scale"] + 1.2, ink, 14)
                self.disk(sx, sy, rad * fl["scale"], (*col, 1), 14)
                continue
            _, lx, lz, a, b, col = part
            hw, hd = a / 2, b / 2
            pts = []
            for ox, oz in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)):
                wx = it["x"] + (lx + ox) * co + (lz + oz) * si
                wz = it["z"] - (lx + ox) * si + (lz + oz) * co
                pts.append(self.furnish_w2s(wx, wz, fl))
            self.poly(pts, (*col, 1))
            self.loop(pts, ink)

    def _draw_tray_icon(self, kind, rect):
        alias = {"seat_a": "seat", "seat_b": "seat", "seat_c": "seat", "seat_d": "seat", "dchair": "seat"}
        name = "fi_" + alias.get(kind, kind)
        pad = 2
        aw, ah = max(8, rect.w - pad * 2), max(8, rect.h - pad * 2)
        if aw / ah > FW / FH:
            h = ah
            w = h * FW / FH
        else:
            w = aw
            h = w * FH / FW
        self.tex_quad(TEX[name], rect.centerx - w / 2, rect.centery - h / 2, w, h)

    def _draw_floor(self, fl, pal):
        wood, kitchen = (.76, .56, .38, 1), (.84, .66, .44, 1)
        carpet = (*pal["carpet"], 1)
        wall = (.34, .22, .16, 1)
        self.rect(fl["ox"], fl["oy"], fl["dw"], fl["dh"], wall)
        if fl["lvl"] == 0:
            self._plan_rect(fl, -8.75, -7.25, 0.78, 7.2, wood)
            self._plan_rect(fl, 1.08, -7.25, 6.28, 7.2, kitchen)
            self._plan_rect(fl, 6.28, 5.95, 8.55, 7.2, kitchen)
            self._plan_rect(fl, 0.7, -1.5, 1.15, 1.5, wood)
            self._plan_rect(fl, 6.35, -1.9, 8.7, 5.9, (.28, .2, .14, 1))
            for i in range(6):
                self._plan_rect(fl, 6.55, -1.6 + i * 1.15, 8.55, -1.45 + i * 1.15, (.42, .3, .2, 1))
        else:
            self._plan_rect(fl, -8.75, -7.25, 8.55, -4.15, wood)
            self._plan_rect(fl, -8.75, -3.98, -0.35, 7.2, carpet)
            self._plan_rect(fl, -0.15, -3.98, 6.35, 1.55, (.92, .93, .95, 1))
            self._plan_rect(fl, -0.15, 1.85, 6.35, 7.2, (.86, .9, .94, 1))
            self._plan_rect(fl, 6.55, -4.0, 8.55, -2.05, wood)
            self._plan_rect(fl, 6.4, -2.0, 8.7, 6.0, (.22, .16, .14, 1))
        for box in YW.WALLS[fl["lvl"]]:
            if box[2] - box[0] > 2.2 and box[3] - box[1] > 4:
                continue
            self._plan_rect(fl, *box, wall)
        if fl["lvl"] == 0:
            self._plan_rect(fl, YW.DOOR_X - .75, 7.05, YW.DOOR_X + .75, 7.75, wood)

    def ui_button(self, rect, label, kind, on=False):
        if kind == "green":
            fill = (0.42, 0.72, 0.28, 1) if on else (0.28, 0.58, 0.22, 1)
            edge = (0.10, 0.32, 0.10, 1)
            fg, outline = (255, 255, 255), (20, 60, 16)
        else:
            fill = (0.62, 0.42, 0.22, 1)
            edge = (0.28, 0.16, 0.08, 1)
            fg, outline = (255, 236, 190), (50, 28, 12)
        self.rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4, edge)
        self.rect(rect.x, rect.y, rect.w, rect.h, fill)
        self.text(label, 14, rect.centerx, rect.y + 4, fg, outline)

    def hud_furnish(self):
        W = WIN_W
        f = self.furnish
        g = self.furnish_geom()
        fl = g["floor"]
        season = self.quiz.get("season") if self.quiz and self.quiz.get("season") is not None else 1
        pal = YW.PAL[int(season)]
        self.tex_quad(TEX["ui_wood"], 0, 0, W, WIN_H, uv=(0, 0, W / 64, WIN_H / 128))
        self.ui_button(g["btns"]["f0"], "1 этаж", "green", f["floor"] == 0)
        self.ui_button(g["btns"]["f1"], "2 этаж", "green", f["floor"] == 1)
        self.ui_button(g["btns"]["default"], "По умолчанию", "wood")
        self.ui_button(g["btns"]["done"], "Готово", "green")
        vx, vy, vw, vh = fl["view"]
        glEnable(GL_SCISSOR_TEST)
        glScissor(int(vx), int(WIN_H - (vy + vh)), int(vw), int(vh))
        self._draw_floor(fl, pal)
        bad = f["drag"] is not None and not YW.layout_ok(f["items"])
        placed = [it for it in f["items"] if it.get("placed") and it["lvl"] == fl["lvl"] and it["id"] != f.get("sel")]
        placed += [it for it in f["items"] if it.get("placed") and it["lvl"] == fl["lvl"] and it["id"] == f.get("sel")]
        for it in placed:
            self._draw_icon(it, fl, YW.icon_parts(it["id"], pal["sofa"], pal["bed"]))
            if it["id"] == f.get("sel"):
                hot = bad and f["drag"] and f["drag"]["id"] == it["id"]
                pts = [self.furnish_w2s(x, z, fl) for x, z in YW._corners(it)]
                self.loop(pts, ((1, .3, .3, 1) if hot else (1, 1, 1, 1)))
        glDisable(GL_SCISSOR_TEST)
        tx, ty, tw, th = g["tray"]
        self.rect(tx - 2, ty - 2, tw + 4, th + 4, (0.28, 0.16, 0.08, 1))
        self.tex_quad(TEX["ui_wood"], tx, ty, tw, th, uv=(0, 0, tw / 64, th / 128))
        sel = YW.piece_of(f["sel"]) if f.get("sel") else None
        sub = f["warn"] or ("Бери снизу. Колесо — крупнее." if not sel else sel["label"] + ". R — повернуть.")
        self.text(sub, 13, tx + 8, ty + 2, (160, 32, 24) if f["warn"] else (255, 236, 190), (40, 22, 10), "left")
        for it, rect in self._tray_slots(g):
            on = it["id"] == f.get("sel")
            self.rect(rect.x, rect.y, rect.w, rect.h, (0.36, 0.62, 0.28, 1) if on else (0.45, 0.30, 0.16, 1))
            self._draw_tray_icon(it["id"], rect)
        self.tex_quad(TEX["ui_leaves_furn"], 0, 0, W, WIN_H)
        if not self.shot:
            mx, my = pygame.mouse.get_pos()
            self.tex_quad(TEX["ui_cursor"], mx, my, 18, 22)

    def enter_world(self, ride):
        """Тест/переход: оказаться в «Твоём мире» (ride=True - на горках над лесом, иначе - у посадки)."""
        if ride:
            self.board_wride(9.0)
        else:
            self.inw = True
            self.px, self.pz = self.world.land_pos
            if not self.start:
                self.yaw = 0.0
            self.sync_music()

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
        self.sync_music()

    def sync_music(self):
        """В парке играет общая тема, в «Твоём мире» — трек выбранного сезона."""
        if self.inw and self.world is not None:
            self.audio.music_play(SEASON_SONG[self.world.season])
        else:
            self.audio.music_play(SONG)

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
                self.sync_music()
            self.wtrans = None

    def quiz_geom(self):
        board = pygame.Rect(*QUIZ_BOARD)
        tag = pygame.Rect(board.x + 18, board.y - 16, 156, 34)
        n, gap, pad, label_h, top = 4, 12, 16, 22, 78
        avail = board.w - pad * 2
        cw = (avail - gap * (n - 1)) / n
        ch = min(cw, board.h - top - label_h - 14)
        total = cw * n + gap * (n - 1)
        x0 = board.x + (board.w - total) / 2
        y0 = board.y + top + max(0, (board.h - top - label_h - ch) / 2)
        cards = [pygame.Rect(x0 + i * (cw + gap), y0, cw, ch) for i in range(n)]
        return dict(board=board, tag=tag, cards=cards)

    def quiz_click(self, pos):
        if not self.quiz or self.quiz.get("phase") != "ask":
            return
        for i, rect in enumerate(self.quiz_geom()["cards"]):
            if rect.collidepoint(pos):
                self.quiz_pick(i)
                return

    def hud_quiz(self):
        W, H = WIN_W, WIN_H
        qz = self.quiz
        g = self.quiz_geom()
        board = g["board"]
        self.tex_quad(TEX["ui_wood"], 0, 0, W, H, uv=(0, 0, W / 64, H / 128))
        self.tex_quad(TEX["ui_paper"], board.x, board.y, board.w, board.h,
                      uv=(0, 0, board.w / 32, board.h / 32))
        edge = (0.10, 0.42, 0.14, 1)
        t = 8
        self.rect(board.x - t, board.y - t, board.w + t * 2, t, edge)
        self.rect(board.x - t, board.bottom, board.w + t * 2, t, edge)
        self.rect(board.x - t, board.y, t, board.h, edge)
        self.rect(board.right, board.y, t, board.h, edge)
        self.tex_quad(TEX["ui_leaves"], 0, 0, W, H)
        self.tex_quad(TEX["ui_tag"], g["tag"].x, g["tag"].y, g["tag"].w, g["tag"].h)
        self.text("Вопрос %d" % (qz["step"] + 1), 16, g["tag"].centerx, g["tag"].y + 6,
                  (255, 214, 64), (60, 32, 12))
        if qz["step"] == 0:
            question = "Какое твоё любимое время года?"
            names = YW.SEASONS
            texs = ("season_spring", "season_summer", "season_autumn", "season_winter")
        else:
            question = "Какая твоя любимая еда?"
            names = YW.FOODS
            texs = tuple("food_%d" % i for i in range(4))
        self.text(question, 20, W / 2, board.y + 36, (64, 46, 32), None)
        mx, my = pygame.mouse.get_pos()
        for i, rect in enumerate(g["cards"]):
            hot = rect.collidepoint((mx, my))
            border = (1, 0.84, 0.2, 1) if hot else (0.12, 0.08, 0.05, 1)
            self.rect(rect.x - 3, rect.y - 3, rect.w + 6, rect.h + 6, border)
            self.tex_quad(TEX[texs[i]], rect.x, rect.y, rect.w, rect.h)
            self.text(names[i], 15, rect.centerx, rect.bottom + 4, (58, 40, 26), None)
        if not self.shot:
            self.tex_quad(TEX["ui_cursor"], mx, my, 18, 22)

    def ensure_paint_icons(self):
        if getattr(self, "_paint_icons", False):
            return
        def up(name, draw):
            s = pygame.Surface((36, 36), pygame.SRCALPHA)
            draw(s)
            upload(name, pygame.image.tobytes(s, "RGBA", True), 36, 36, mip=False, repeat=False)
        ink = (28, 18, 12)
        up("icon_pencil", lambda s: (pygame.draw.line(s, ink, (6, 30), (24, 8), 4),
                                      pygame.draw.polygon(s, (240, 196, 48), [(22, 4), (32, 14), (26, 16), (18, 6)])))
        up("icon_brush", lambda s: (pygame.draw.line(s, (92, 58, 32), (6, 30), (20, 12), 6),
                                     pygame.draw.circle(s, ink, (26, 8), 7),
                                     pygame.draw.circle(s, (40, 40, 44), (26, 8), 4)))
        up("icon_fill", lambda s: pygame.draw.polygon(s, (36, 110, 210),
                                                      [(8, 28), (14, 6), (24, 10), (30, 26), (16, 32)]))
        up("icon_line", lambda s: pygame.draw.line(s, ink, (6, 30), (30, 6), 4))
        up("icon_erase", lambda s: (pygame.draw.rect(s, ink, (5, 8, 26, 20)),
                                     pygame.draw.rect(s, (255, 214, 220), (7, 10, 22, 16))))
        self._paint_icons = True

    def hud_paint(self):
        self.ensure_paint_icons()
        self.paint_upload()
        W, H = WIN_W, WIN_H
        g = self.paint_geom()
        p = self.paint
        qz = self.quiz
        board = g["board"]
        self.tex_quad(TEX["ui_wood"], 0, 0, W, H, uv=(0, 0, W / 64, H / 128))
        self.text(p["prompt"], 13, 22, 18, (255, 236, 190), (40, 22, 10), "left")
        sub = p["warn"] or p["react"] or ("Рисунок %d из %d" % (qz["draw_i"] + 1, len(DRAW_PROMPTS)))
        self.text(sub, 13, 22, 36, (180, 40, 32) if p["warn"] else (255, 236, 190), (40, 22, 10), "left")
        self.ui_button(g["done"], "Готово", "green")
        self.tex_quad(TEX["ui_paper"], board.x, board.y, board.w, board.h,
                      uv=(0, 0, board.w / 32, board.h / 32))
        icons = {"pencil": "icon_pencil", "brush": "icon_brush", "fill": "icon_fill",
                 "line": "icon_line", "erase": "icon_erase"}
        for name, rect in g["slots"]:
            sel = p["tool"] == name
            self.ui_button(rect, "", "green" if sel else "wood", sel)
            self.tex_quad(TEX[icons[name]], rect.x + 8, rect.y + 6, 36, 36)
        cur = g["current"]
        self.rect(cur.x - 2, cur.y - 2, cur.w + 4, cur.h + 4, (0.12, 0.07, 0.04, 1))
        cr, cg, cb = [c / 255 for c in p["color"]]
        self.rect(cur.x, cur.y, cur.w, cur.h, (cr, cg, cb, 1))
        for col, rect in g["colors"]:
            self.rect(rect.x, rect.y, rect.w, rect.h, (col[0] / 255, col[1] / 255, col[2] / 255, 1))
            if col == p["color"]:
                self.rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4, (1, 0.84, 0.2, 1))
                self.rect(rect.x, rect.y, rect.w, rect.h, (col[0] / 255, col[1] / 255, col[2] / 255, 1))
        cx, cy, cw, ch = g["canvas"]
        self.rect(cx - 4, cy - 4, cw + 8, ch + 8, (0.22, 0.13, 0.07, 1))
        if "canvas" in TEX:
            self.tex_quad(TEX["canvas"], cx, cy, cw, ch)
        if p["down"] and p["tool"] == "line" and p["line_a"] and p["last"]:
            sw, sh = p["surf"].get_size()
            glBindTexture(GL_TEXTURE_2D, TEX["white"])
            glColor3f(cr, cg, cb)
            glBegin(GL_LINES)
            glVertex2f(cx + p["line_a"][0] / sw * cw, cy + p["line_a"][1] / sh * ch)
            glVertex2f(cx + p["last"][0] / sw * cw, cy + p["last"][1] / sh * ch)
            glEnd()
        self.tex_quad(TEX["ui_leaves_furn"], 0, 0, W, H)
        if not self.shot:
            mx, my = pygame.mouse.get_pos()
            glBindTexture(GL_TEXTURE_2D, TEX["white"])
            glLineWidth(2)
            for rad, col in ((9, (0, 0, 0)), (7, (1, 1, 1))):
                glColor3f(*col)
                glBegin(GL_LINE_LOOP)
                for i in range(16):
                    a = i * TAU / 16
                    glVertex2f(mx + math.cos(a) * rad, my + math.sin(a) * rad)
                glEnd()
            glLineWidth(1)

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
                # белый проход длинный: свет нарастает всю дорогу, переключение в самом конце
                white0 = (P["L"] - (PORTAL_BACK + WHITE_LEN)) + RING_LEN
                if r["s"] > white0:
                    r["v"] += (8.5 - r["v"]) * min(1.0, dt * 1.6)
                ramp = (r["s"] - white0) / WHITE_LEN
                if ramp > 0:
                    self.wflash = max(self.wflash, clamp(ramp, 0, 1) ** 1.15)
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
            if self.quiz.get("phase") == "ask":
                pygame.event.set_grab(False)
            elif self.quiz.get("phase") == "paint" and self.paint:
                self.paint["live"] = self.paint.get("live", 0.0) + dt
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
            elif self.quiz.get("phase") == "furnish":
                self.hud_furnish()
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
                    phase = self.quiz.get("phase") if self.quiz else None
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif phase == "paint" and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.paint_finish()
                    elif phase == "furnish" and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.furnish_finish()
                    elif phase == "furnish" and e.key == pygame.K_r:
                        self.furnish_rotate()
                    elif phase == "ask" and pygame.K_1 <= e.key <= pygame.K_4:
                        self.quiz_pick(e.key - pygame.K_1)
                    elif phase == "ask" and pygame.K_KP1 <= e.key <= pygame.K_KP4:
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
                    phase = self.quiz.get("phase") if self.quiz else None
                    if phase == "paint":
                        self.paint_pointer(e.pos, "down")
                    elif phase == "furnish":
                        self.furnish_pointer(e.pos, "down")
                    elif phase == "ask":
                        self.quiz_click(e.pos)
                    else:
                        self.click()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3 and self.quiz and self.quiz.get("phase") == "furnish":
                    self.furnish_rotate(e.pos)
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.quiz:
                    phase = self.quiz.get("phase")
                    if phase == "paint":
                        self.paint_pointer(e.pos, "up")
                    elif phase == "furnish":
                        self.furnish_pointer(e.pos, "up")
                elif e.type == pygame.MOUSEWHEEL and self.quiz and self.quiz.get("phase") == "furnish":
                    self.furnish_zoom(e.y, pygame.mouse.get_pos())
                elif e.type == pygame.MOUSEMOTION and self.quiz:
                    phase = self.quiz.get("phase")
                    if phase == "paint":
                        self.paint_pointer(e.pos, "move")
                    elif phase == "furnish":
                        self.furnish_pointer(e.pos, "move")
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
