# -*- coding: utf-8 -*-
"""Локация HIDE AND SEEK: тёмный кирпичный подвал с арками (как в KinitoPET)."""
import math
import random
from collections import deque

from gfx import *
import gfx as _gfx


def face(*a, **k):
    # мельче плитки: конус фонарика считается по вершинам, нужна более частая сетка
    k.setdefault("tile", .5)
    return _gfx.face(*a, **k)

CELL = 4.0
GW = GH = 8
WALL_T = .4
WALL_H = 3.4
OPEN_R = 1.0                 # радиус арочного проёма
OPEN_BASE = 1.8              # высота прямой части проёма
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class HideSeek:
    def __init__(self, seed=None):
        rng = random.Random(seed)
        self.rng = rng
        self.open = set()
        visited = {(0, 0)}
        stack = [(0, 0)]
        while stack:
            x, z = stack[-1]
            nb = [(x + dx, z + dz) for dx, dz in DIRS
                  if 0 <= x + dx < GW and 0 <= z + dz < GH and (x + dx, z + dz) not in visited]
            if not nb:
                stack.pop()
                continue
            n = rng.choice(nb)
            self.open.add(frozenset(((x, z), n)))
            visited.add(n)
            stack.append(n)
        for _ in range(20):                       # лишние проёмы -> петли
            x, z = rng.randrange(GW), rng.randrange(GH)
            dx, dz = rng.choice(DIRS)
            if 0 <= x + dx < GW and 0 <= z + dz < GH:
                self.open.add(frozenset(((x, z), (x + dx, z + dz))))
        self.rects = []
        self.bulbs = []
        self.list = None
        self.dist = {}
        self._last_pc = None
        # старт игрока / Кинито
        self.start_cell = (GW // 2, GH // 2)
        d = self.bfs(self.start_cell)
        cands = [c for c, v in d.items() if 8 <= v <= 11] or [max(d, key=d.get)]
        self.kcell0 = rng.choice(cands)
        self.kx, self.kz = self.center(self.kcell0)
        self.kyaw = 0.0
        self.kmoving = False
        self.t = 0.0

    # --------------------------------------------------------- граф
    @staticmethod
    def center(c):
        return (c[0] + .5) * CELL, (c[1] + .5) * CELL

    @staticmethod
    def cell_of(x, z):
        return (min(GW - 1, max(0, int(x // CELL))), min(GH - 1, max(0, int(z // CELL))))

    def links(self, c):
        out = []
        for dx, dz in DIRS:
            n = (c[0] + dx, c[1] + dz)
            if frozenset((c, n)) in self.open:
                out.append(n)
        return out

    def bfs(self, src):
        d = {src: 0}
        q = deque([src])
        while q:
            c = q.popleft()
            for n in self.links(c):
                if n not in d:
                    d[n] = d[c] + 1
                    q.append(n)
        return d

    def start_yaw(self):
        c = self.start_cell
        d = self.bfs(self.kcell0)
        best = max(self.links(c), key=lambda n: d.get(n, 0))
        return cam_yaw(best[0] - c[0], best[1] - c[1])

    def free(self):
        """Освободить display list (иначе при каждом входе в подвал память видеокарты утекает)."""
        if self.list:
            glDeleteLists(self.list, 1)
            self.list = None

    # --------------------------------------------------------- геометрия
    def build(self):
        W = GW * CELL
        H = GH * CELL
        T = WALL_T
        walls = []          # (axis, pos, a0, a1, opening)
        for z in range(GH):
            walls.append(("x", 0.0, z * CELL, (z + 1) * CELL, False))
            walls.append(("x", W, z * CELL, (z + 1) * CELL, False))
        for x in range(GW):
            walls.append(("z", 0.0, x * CELL, (x + 1) * CELL, False))
            walls.append(("z", H, x * CELL, (x + 1) * CELL, False))
        for x in range(GW - 1):
            for z in range(GH):
                op = frozenset(((x, z), (x + 1, z))) in self.open
                walls.append(("x", (x + 1) * CELL, z * CELL, (z + 1) * CELL, op))
        for x in range(GW):
            for z in range(GH - 1):
                op = frozenset(((x, z), (x, z + 1))) in self.open
                walls.append(("z", (z + 1) * CELL, x * CELL, (x + 1) * CELL, op))

        def wface(axis, pos, sgn, u0, u1, v0, v1):
            if u1 - u0 < 1e-4 or v1 - v0 < 1e-4:
                return
            d = pos + sgn * T / 2
            if axis == "x":
                face((d, v0, u0), (0, 0, 1), (0, 1, 0), u1 - u0, v1 - v0, (sgn, 0, 0), uv0=(u0, v0))
            else:
                face((u0, v0, d), (1, 0, 0), (0, 1, 0), u1 - u0, v1 - v0, (0, 0, sgn), uv0=(u0, v0))

        def top_of(xc):
            return OPEN_BASE + math.sqrt(max(0.0, OPEN_R * OPEN_R - xc * xc))

        l = glGenLists(1)
        glNewList(l, GL_COMPILE)
        glColor3f(1, 1, 1)
        # пол и потолок
        glBindTexture(GL_TEXTURE_2D, TEX["dirt"])
        face((0, 0, 0), (1, 0, 0), (0, 0, 1), W, H, (0, 1, 0))
        glColor3f(.5, .5, .55)
        glBindTexture(GL_TEXTURE_2D, TEX["brick"])
        face((0, WALL_H, 0), (1, 0, 0), (0, 0, 1), W, H, (0, -1, 0))
        glColor3f(1, 1, 1)
        # кирпичные стены
        for axis, pos, a0, a1, op in walls:
            ac = (a0 + a1) / 2
            for sgn in (-1, 1):
                if not op:
                    wface(axis, pos, sgn, a0 - T / 2, a1 + T / 2, 0, WALL_H)
                else:
                    wface(axis, pos, sgn, a0 - T / 2, ac - OPEN_R, 0, WALL_H)
                    wface(axis, pos, sgn, ac + OPEN_R, a1 + T / 2, 0, WALL_H)
                    n = 8
                    cw = 2 * OPEN_R / n
                    for k in range(n):
                        u0 = ac - OPEN_R + k * cw
                        wface(axis, pos, sgn, u0, u0 + cw, top_of(u0 + cw / 2 - ac), WALL_H)
        # штукатурка: откосы и интрадос арок
        glBindTexture(GL_TEXTURE_2D, TEX["plaster"])
        for axis, pos, a0, a1, op in walls:
            if not op:
                continue
            ac = (a0 + a1) / 2
            n = 8
            cw = 2 * OPEN_R / n
            for k in range(n):
                u0 = ac - OPEN_R + k * cw
                ht = top_of(u0 + cw / 2 - ac)
                if axis == "x":
                    face((pos - T / 2, ht, u0), (0, 0, 1), (1, 0, 0), cw, T, (0, -1, 0))
                else:
                    face((u0, ht, pos - T / 2), (1, 0, 0), (0, 0, 1), cw, T, (0, -1, 0))
            for sj, nj in ((ac - OPEN_R, 1), (ac + OPEN_R, -1)):
                jh = top_of(OPEN_R - cw / 2)
                if axis == "x":
                    face((pos - T / 2, 0, sj), (1, 0, 0), (0, 1, 0), T, jh, (0, 0, nj), uvs=(.5, .5))
                else:
                    face((sj, 0, pos - T / 2), (0, 0, 1), (0, 1, 0), T, jh, (nj, 0, 0), uvs=(.5, .5))
        # декоративные арки и колонны (светлая штукатурка вокруг проёма)
        for axis, pos, a0, a1, op in walls:
            if not op:
                continue
            ac = (a0 + a1) / 2
            for sgn in (-1, 1):
                if axis == "z":
                    push(ac, 0, pos)
                else:
                    push(pos, 0, ac, ry=-90)
                zoff = sgn * (T / 2 + .04)
                for k in range(9):
                    phi = (k + .5) / 9 * math.pi
                    obj("box", 1.12 * math.cos(phi), OPEN_BASE + 1.12 * math.sin(phi), zoff,
                        .26, .52, .1, WHITE, "plaster", rz=math.degrees(phi))
                for sx in (-1.12, 1.12):
                    obj("box", sx, OPEN_BASE / 2, zoff, .26, OPEN_BASE, .1, WHITE, "plaster")
                pop()
        # лампочки (патроны) и ящики
        for x in range(GW):
            for z in range(GH):
                if (x * 2 + z) % 5 == 0:
                    cx, cz = self.center((x, z))
                    self.bulbs.append((cx, WALL_H - .3, cz))
                    obj("cyl", cx, WALL_H - .12, cz, .06, .12, .06, (.12, .1, .1))
                    beam((cx, WALL_H - .12, cz), (cx, WALL_H - .3, cz), .02, (.1, .1, .1))
        rng = random.Random(4)
        for _ in range(9):
            c = (rng.randrange(GW), rng.randrange(GH))
            if c == self.start_cell:
                continue
            cx, cz = self.center(c)
            ox, oz = rng.choice((-1, 1)) * 1.35, rng.choice((-1, 1)) * 1.35
            s = rng.uniform(.8, 1.1)
            obj("box", cx + ox, s / 2, cz + oz, s, s, s, (.62, .42, .24), "plaster", ry=rng.uniform(0, 80))
            self.rects.append((cx + ox - s * .7, cz + oz - s * .7, cx + ox + s * .7, cz + oz + s * .7))
        glEndList()
        self.list = l

        # коллайдеры стен
        for axis, pos, a0, a1, op in walls:
            ac = (a0 + a1) / 2
            segs = [(a0 - T / 2, a1 + T / 2)] if not op else [(a0 - T / 2, ac - OPEN_R), (ac + OPEN_R, a1 + T / 2)]
            for s0, s1 in segs:
                if axis == "x":
                    self.rects.append((pos - T / 2, s0, pos + T / 2, s1))
                else:
                    self.rects.append((s0, pos - T / 2, s1, pos + T / 2))

    # --------------------------------------------------------- коллизии
    def collide(self, x, z, r):
        for _ in range(2):
            for x0, z0, x1, z1 in self.rects:
                if x < x0 - r or x > x1 + r or z < z0 - r or z > z1 + r:
                    continue
                cx = min(max(x, x0), x1)
                cz = min(max(z, z0), z1)
                dx, dz = x - cx, z - cz
                d2 = dx * dx + dz * dz
                if d2 < r * r:
                    if d2 > 1e-9:
                        d = math.sqrt(d2)
                        x = cx + dx / d * r
                        z = cz + dz / d * r
                    else:                       # центр внутри прямоугольника - выталкиваем по короткой оси
                        pushes = ((x - x0, -1, 0), (x1 - x, 1, 0), (z - z0, 0, -1), (z1 - z, 0, 1))
                        m = min(pushes, key=lambda p: p[0])
                        x += m[1] * (m[0] + r)
                        z += m[2] * (m[0] + r)
        return x, z

    # --------------------------------------------------------- Кинито
    def update_seeker(self, px, pz, dt, t):
        pc = self.cell_of(px, pz)
        if pc != self._last_pc:
            self.dist = self.bfs(pc)
            self._last_pc = pc
        kc = self.cell_of(self.kx, self.kz)
        if kc == pc or kc not in self.dist:
            tx, tz = px, pz
        else:
            n = min(self.links(kc), key=lambda c: self.dist.get(c, 999))
            tx, tz = self.center(n)
        dx, dz = tx - self.kx, tz - self.kz
        d = math.hypot(dx, dz)
        speed = min(4.2, 2.1 + .028 * t)
        self.kmoving = d > .05
        if d > .05:
            st = min(d, speed * dt)
            self.kx += dx / d * st
            self.kz += dz / d * st
            self.kyaw = model_yaw_deg(dx, dz)

    def advance_seeker(self, meters, px, pz):
        """Рывок Кинито вперёд по пути (после отключения света)."""
        while meters > 0:
            pc = self.cell_of(px, pz)
            if pc != self._last_pc:
                self.dist = self.bfs(pc)
                self._last_pc = pc
            kc = self.cell_of(self.kx, self.kz)
            if kc == pc or kc not in self.dist:
                tx, tz = px, pz
            else:
                n = min(self.links(kc), key=lambda c: self.dist.get(c, 999))
                tx, tz = self.center(n)
            dx, dz = tx - self.kx, tz - self.kz
            d = math.hypot(dx, dz)
            if d < .01:
                break
            st = min(d, meters)
            self.kx += dx / d * st
            self.kz += dz / d * st
            self.kyaw = model_yaw_deg(dx, dz)
            meters -= st
            if math.hypot(px - self.kx, pz - self.kz) < 5.5:
                break
