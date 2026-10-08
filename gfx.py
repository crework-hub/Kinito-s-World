# -*- coding: utf-8 -*-
"""Общая графика: текстуры, примитивы (display lists), вспомогательные функции."""
import math

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

TAU = math.pi * 2

WHITE = (1.0, 1.0, 1.0)
RED = (0.92, 0.12, 0.2)
BLUE = (0.16, 0.22, 0.88)
YEL = (1.0, 0.86, 0.16)
PURP = (0.46, 0.16, 0.78)
BLACK = (0.04, 0.04, 0.06)


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def cam_yaw(dx, dz):
    return math.atan2(-dx, -dz)


def model_yaw_deg(dx, dz):
    return math.degrees(math.atan2(-dz, dx))


# ----------------------------------------------------------------------------
# Текстуры
# ----------------------------------------------------------------------------
TEX = {}


def upload(name, data, w, h, mip=True, repeat=True):
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    wrap = GL_REPEAT if repeat else GL_CLAMP_TO_EDGE
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    if mip:
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)
    else:
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    TEX[name] = tid
    return tid


def to_rgba(rgb):
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    a = np.full(rgb.shape[:2] + (1,), 255, np.uint8)
    return np.ascontiguousarray(np.concatenate([rgb, a], axis=2))


def _brick_texture(rng):
    W = H = 64
    img = np.zeros((H, W, 3), int)
    img[:] = (44, 34, 28)                              # раствор
    for row in range(8):
        y0 = row * 8
        off = 0 if row % 2 == 0 else 8
        for b in range(-1, 5):
            x0 = b * 16 + off
            var = (rng.integers(-16, 17, 3) * np.array([1.0, .6, .5])).astype(int)
            col = np.array([122, 66, 48]) + var
            xa, xb = max(x0, 0), min(x0 + 15, W)
            if xb > xa:
                img[y0 + 1:y0 + 8, xa:xb] = col
    img += rng.integers(-12, 13, (H, W, 1))
    return to_rgba(img)


def gen_textures():
    rng = np.random.default_rng(7)
    upload("white", to_rgba(np.full((4, 4, 3), 255)), 4, 4)

    # шахматный пол (клетка 2м, текстура 4м)
    y, x = np.mgrid[0:32, 0:32]
    c = (((x // 16) + (y // 16)) % 2 == 0)
    base = np.where(c, 248, 14)[..., None].repeat(3, 2).astype(int)
    base += rng.integers(-7, 8, (32, 32, 1))
    upload("checker", to_rgba(base), 32, 32)

    # жёлто-фиолетовые полосы (16 полос по окружности)
    y, x = np.mgrid[0:8, 0:64]
    s = ((x // 4) % 2 == 0)[..., None]
    yel = np.array([252, 214, 36])
    pur = np.array([92, 40, 176])
    arr = np.where(s, yel, pur).astype(int) + rng.integers(-5, 6, (8, 64, 1))
    upload("stripes", to_rgba(arr), 64, 8)

    # мраморный серый - для лошадок
    g = 218 + rng.integers(-34, 35, (16, 16, 1))
    arr = np.concatenate([g, g, g + 4], axis=2)
    upload("noise", to_rgba(arr), 16, 16)

    # Hide and Seek: кирпич, штукатурка, земля
    upload("brick", _brick_texture(rng), 64, 64)
    g = 205 + rng.integers(-12, 13, (32, 32, 1))
    pl = np.concatenate([g, g - 18, g - 62], axis=2)
    blot = rng.random((32, 32, 1)) < .08
    pl = np.where(blot, pl - 35, pl)
    upload("plaster", to_rgba(pl), 32, 32)
    g = rng.integers(-14, 15, (32, 32, 1))
    dirt = np.concatenate([62 + g, 44 + g, 34 + g], axis=2)
    spec = rng.random((32, 32, 1)) < .07
    dirt = np.where(spec, dirt + 40, dirt)
    upload("dirt", to_rgba(dirt), 32, 32)


# ----------------------------------------------------------------------------
# Примитивы (display lists)
# ----------------------------------------------------------------------------
LISTS = {}

_BOX_FACES = [
    ((0, 0, 1), [(-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)]),
    ((0, 0, -1), [(.5, -.5, -.5), (-.5, -.5, -.5), (-.5, .5, -.5), (.5, .5, -.5)]),
    ((1, 0, 0), [(.5, -.5, .5), (.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5)]),
    ((-1, 0, 0), [(-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5), (-.5, .5, -.5)]),
    ((0, 1, 0), [(-.5, .5, .5), (.5, .5, .5), (.5, .5, -.5), (-.5, .5, -.5)]),
    ((0, -1, 0), [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5)]),
]
_UV = [(0, 0), (1, 0), (1, 1), (0, 1)]


def _geom_box():
    glBegin(GL_QUADS)
    for n, vs in _BOX_FACES:
        glNormal3f(*n)
        for uv, p in zip(_UV, vs):
            glTexCoord2f(*uv)
            glVertex3f(*p)
    glEnd()


def _geom_cyl(n=16):
    glBegin(GL_QUADS)
    for i in range(n):
        a0 = TAU * i / n
        a1 = TAU * (i + 1) / n
        am = (a0 + a1) / 2
        glNormal3f(math.cos(am), 0, math.sin(am))
        glTexCoord2f(i / n, 0)
        glVertex3f(math.cos(a0), 0, math.sin(a0))
        glTexCoord2f((i + 1) / n, 0)
        glVertex3f(math.cos(a1), 0, math.sin(a1))
        glTexCoord2f((i + 1) / n, 1)
        glVertex3f(math.cos(a1), 1, math.sin(a1))
        glTexCoord2f(i / n, 1)
        glVertex3f(math.cos(a0), 1, math.sin(a0))
    glEnd()
    for yv, ny in ((1, 1), (0, -1)):
        glBegin(GL_TRIANGLE_FAN)
        glNormal3f(0, ny, 0)
        glTexCoord2f(.5, .5)
        glVertex3f(0, yv, 0)
        for i in range(n + 1):
            a = TAU * i / n
            glTexCoord2f(.5 + .5 * math.cos(a), .5 + .5 * math.sin(a))
            glVertex3f(math.cos(a), yv, math.sin(a))
        glEnd()


def _geom_cone(n=16):
    glBegin(GL_TRIANGLES)
    for i in range(n):
        a0 = TAU * i / n
        a1 = TAU * (i + 1) / n
        am = (a0 + a1) / 2
        glNormal3f(math.cos(am), 1, math.sin(am))
        glTexCoord2f(i / n, 0)
        glVertex3f(math.cos(a0), 0, math.sin(a0))
        glTexCoord2f((i + 1) / n, 0)
        glVertex3f(math.cos(a1), 0, math.sin(a1))
        glTexCoord2f((i + .5) / n, 1)
        glVertex3f(0, 1, 0)
    glEnd()
    glBegin(GL_TRIANGLE_FAN)
    glNormal3f(0, -1, 0)
    glTexCoord2f(.5, .5)
    glVertex3f(0, 0, 0)
    for i in range(n + 1):
        a = TAU * i / n
        glTexCoord2f(.5 + .5 * math.cos(a), .5 + .5 * math.sin(a))
        glVertex3f(math.cos(a), 0, math.sin(a))
    glEnd()


def _geom_sphere(nlat=8, nlon=12):
    for i in range(nlat):
        la0 = math.pi * (i / nlat - .5)
        la1 = math.pi * ((i + 1) / nlat - .5)
        glBegin(GL_QUAD_STRIP)
        for j in range(nlon + 1):
            lo = TAU * j / nlon
            for la, v in ((la0, i / nlat), (la1, (i + 1) / nlat)):
                x = math.cos(la) * math.cos(lo)
                y = math.sin(la)
                z = math.cos(la) * math.sin(lo)
                glNormal3f(x, y, z)
                glTexCoord2f(j / nlon, v)
                glVertex3f(x, y, z)
        glEnd()


def build_primitives():
    for name, fn in (("box", _geom_box), ("cyl", _geom_cyl),
                     ("cone", _geom_cone), ("sphere", _geom_sphere)):
        l = glGenLists(1)
        glNewList(l, GL_COMPILE)
        fn()
        glEndList()
        LISTS[name] = l


RESTORE = [True]       # включать ли освещение обратно после lit=False (нужно выключать в проходе фонаря)


def obj(kind, x, y, z, sx, sy, sz, col=WHITE, tex="white",
        ry=0.0, rx=0.0, rz=0.0, lit=True):
    glPushMatrix()
    glTranslatef(x, y, z)
    if ry:
        glRotatef(ry, 0, 1, 0)
    if rx:
        glRotatef(rx, 1, 0, 0)
    if rz:
        glRotatef(rz, 0, 0, 1)
    glScalef(sx, sy, sz)
    if not lit:
        glDisable(GL_LIGHTING)
    glColor3f(*col)
    glBindTexture(GL_TEXTURE_2D, TEX[tex])
    glCallList(LISTS[kind])
    if not lit and RESTORE[0]:
        glEnable(GL_LIGHTING)
    glPopMatrix()


def beam(a, b, t, col=WHITE, tex="white"):
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    if L < 1e-6:
        return
    dx /= L
    dy /= L
    dz /= L
    glPushMatrix()
    glTranslatef((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    ax, ay = -dy, dx                       # cross((0,0,1), d)
    s = math.sqrt(ax * ax + ay * ay)
    if s > 1e-6:
        glRotatef(math.degrees(math.atan2(s, dz)), ax / s, ay / s, 0)
    elif dz < 0:
        glRotatef(180, 0, 1, 0)
    glScalef(t, t, L)
    glColor3f(*col)
    glBindTexture(GL_TEXTURE_2D, TEX[tex])
    glCallList(LISTS["box"])
    glPopMatrix()


def push(x, y, z, ry=0.0, rz=0.0, rx=0.0):
    glPushMatrix()
    glTranslatef(x, y, z)
    if ry:
        glRotatef(ry, 0, 1, 0)
    if rx:
        glRotatef(rx, 1, 0, 0)
    if rz:
        glRotatef(rz, 0, 0, 1)


pop = glPopMatrix


def face(o, du, dv, lu, lv, n, uv0=(0.0, 0.0), uvs=(0.5, 0.5), tile=1.0):
    """Плоская грань, нарезанная на плитки (освещение/туман считаются по вершинам)."""
    nu = max(1, int(math.ceil(lu / tile - 1e-6)))
    nv = max(1, int(math.ceil(lv / tile - 1e-6)))
    glNormal3f(*n)
    glBegin(GL_QUADS)
    for i in range(nu):
        u0, u1 = lu * i / nu, lu * (i + 1) / nu
        for j in range(nv):
            v0, v1 = lv * j / nv, lv * (j + 1) / nv
            for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
                glTexCoord2f((uv0[0] + u) * uvs[0], (uv0[1] + v) * uvs[1])
                glVertex3f(o[0] + du[0] * u + dv[0] * v,
                           o[1] + du[1] * u + dv[1] * v,
                           o[2] + du[2] * u + dv[2] * v)
    glEnd()
