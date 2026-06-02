#!/usr/bin/env python3
"""
walkthrough.py — Lucknow Smart Home · FPS Walkthrough (Production)
═══════════════════════════════════════════════════════════════════
Single-file walkthrough of the Lucknow Smart Self-Sufficient Residence
(G+1+Terrace, 27.4 × 13.7 m plot, east-facing).

INSTALL:  pip install ursina pillow numpy
RUN:      python walkthrough.py

CONTROLS
  WASD / Arrow keys   Move
  Mouse               Look
  Space               Jump
  E  (near stair)     Go up one floor
  Shift+E             Go down one floor
  1                   Toggle cooling airflow overlay
  2                   Toggle security camera FOV cones
  3                   Toggle solar / PV info overlay
  Tab                 Design info panel (pause)
  F                   Toggle fullscreen
  Esc / Q             Quit
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import os, sys, math, tempfile, random, importlib.util
from pathlib import Path

# ── third-party ───────────────────────────────────────────────────────────────
try:
    from ursina import *
    from ursina.prefabs.first_person_controller import FirstPersonController
except ImportError:
    sys.exit("ERROR: ursina not found.  Run:  pip install ursina pillow numpy")

try:
    from PIL import Image as PILImage, ImageDraw, ImageFilter
    import numpy as np
except ImportError:
    sys.exit("ERROR: pillow / numpy not found.  Run:  pip install ursina pillow numpy")


# ══════════════════════════════════════════════════════════════════════════════
# 1.  CONSTANTS  (mirrors lucknow_smart_home.py)
# ══════════════════════════════════════════════════════════════════════════════
HX, HY       = 13.9, 10.0
GF_Z         = 0.0
GF_H         = 3.30
F1_Z         = 3.30
F1_H         = 3.65
T_Z          = 6.95
PARAPET_H    = 0.90
CANT_W       = 3.0
DRIVEWAY_W   = 7.5
LAWN_W       = 6.0
PLOT_Y0      = -1.85
PLOT_Y1      = HY + 1.85

TW   = 0.22
TI   = 0.14
TS   = 0.22

CX1, CX2    = 5.9, 9.9
CY1         = 5.0
STAIR_X     = (CX1 + CX2) / 2
STAIR_Y     = 5.0

DOOR_H      = 2.44
WIN_SILL    = 0.90
WIN_HEAD    = 2.40


# ══════════════════════════════════════════════════════════════════════════════
# 2.  TEXTURE FACTORY
# ══════════════════════════════════════════════════════════════════════════════
_TEX_DIR  = Path(tempfile.mkdtemp(prefix="lsh_tex_"))
_TEX_CACHE: dict[str, object] = {}

def _pil_to_ursina(img: PILImage.Image, key: str):
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]
    p = _TEX_DIR / f"{key}.png"
    img.save(str(p), icc_profile=None)   # strip embedded profile → no iCCP warning
    tex = load_texture(str(p))
    _TEX_CACHE[key] = tex
    return tex

def _noise(size=256, scale=24, seed=0) -> np.ndarray:
    """Vectorised bilinear value noise — ~200× faster than loop version."""
    rng   = np.random.default_rng(seed)
    cells = max(2, size // max(scale, 1))
    g     = rng.random((cells + 1, cells + 1)).astype(np.float32)

    xs = np.linspace(0, cells, size, endpoint=False)
    ys = np.linspace(0, cells, size, endpoint=False)
    ix = np.floor(xs).astype(int).clip(0, cells - 1)
    iy = np.floor(ys).astype(int).clip(0, cells - 1)
    fx = (xs - ix).astype(np.float32)
    fy = (ys - iy).astype(np.float32)

    fx2d = fx[np.newaxis, :]
    fy2d = fy[:, np.newaxis]

    g00 = g[iy[:, np.newaxis], ix[np.newaxis, :]]
    g10 = g[iy[:, np.newaxis], (ix + 1)[np.newaxis, :]]
    g01 = g[(iy + 1)[:, np.newaxis], ix[np.newaxis, :]]
    g11 = g[(iy + 1)[:, np.newaxis], (ix + 1)[np.newaxis, :]]

    return (g00 * (1 - fx2d) * (1 - fy2d) +
            g10 *      fx2d  * (1 - fy2d) +
            g01 * (1 - fx2d) *      fy2d  +
            g11 *      fx2d  *      fy2d)

def make_lime_plaster(size=256):
    key = "lime_plaster"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=20, seed=1)
    n2 = _noise(size, scale=6,  seed=2) * 0.3
    n  = np.clip(n + n2, 0, 1)
    r  = (240 + n * 12).astype(np.uint8)
    g  = (235 + n * 10).astype(np.uint8)
    b  = (222 + n *  8).astype(np.uint8)
    arr = np.stack([r, g, b], axis=-1)
    img = PILImage.fromarray(arr, 'RGB')
    img = img.filter(ImageFilter.SMOOTH)
    return _pil_to_ursina(img, key)

def make_terracotta(size=256):
    key = "terracotta"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=16, seed=3)
    n2 = _noise(size, scale=5,  seed=4) * 0.4
    n  = np.clip(n + n2, 0, 1)
    r  = (185 + n * 30).astype(np.uint8)
    g  = ( 82 + n * 20).astype(np.uint8)
    b  = ( 55 + n * 15).astype(np.uint8)
    arr = np.stack([r, g, b], axis=-1)
    img = PILImage.fromarray(arr, 'RGB')
    return _pil_to_ursina(img, key)

def make_sandstone(size=256):
    key = "sandstone"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=32, seed=5)
    n2 = _noise(size, scale=8,  seed=6) * 0.5
    n  = np.clip(n + n2, 0, 1)
    r  = (188 + n * 30).astype(np.uint8)
    g  = (155 + n * 25).astype(np.uint8)
    b  = ( 98 + n * 20).astype(np.uint8)
    arr = np.stack([r, g, b], axis=-1)
    img = PILImage.fromarray(arr, 'RGB')
    return _pil_to_ursina(img, key)

def make_timber(size=256):
    key = "timber"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=256, seed=7)
    n2 = _noise(size, scale=8,   seed=8) * 0.12
    n  = np.clip(n + n2, 0, 1)
    grain = np.zeros((size, size), np.float32)
    for i in range(0, size, 18):
        grain[:, max(0, i-1):i+2] += 0.15
    n = np.clip(n + grain, 0, 1)
    r = (168 + n * 30).astype(np.uint8)
    g = (118 + n * 22).astype(np.uint8)
    b = ( 60 + n * 15).astype(np.uint8)
    arr = np.stack([r, g, b], axis=-1)
    img = PILImage.fromarray(arr, 'RGB')
    return _pil_to_ursina(img, key)

def make_pv_panel(size=256):
    key = "pv_panel"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    img = PILImage.new('RGB', (size, size), (22, 42, 110))
    draw = ImageDraw.Draw(img)
    cell = size // 6
    for cx in range(0, size, cell):
        draw.line([(cx, 0), (cx, size)], fill=(35, 60, 145), width=2)
    for cy in range(0, size, cell):
        draw.line([(0, cy), (size, cy)], fill=(35, 60, 145), width=2)
    draw.line([(0,0),(size,0),(size,size),(0,size),(0,0)], fill=(60,80,160), width=3)
    n = _noise(size, scale=32, seed=9) * 18
    arr = np.array(img, np.float32)
    arr[:,:,0] = np.clip(arr[:,:,0] + n, 0, 255)
    arr[:,:,2] = np.clip(arr[:,:,2] + n * 2, 0, 255)
    img = PILImage.fromarray(arr.astype(np.uint8), 'RGB')
    return _pil_to_ursina(img, key)

def make_concrete_floor(size=256):
    key = "concrete_floor"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=48, seed=10)
    n2 = _noise(size, scale=12, seed=11) * 0.25
    n  = np.clip(n + n2, 0, 1)
    v  = (205 + n * 20).astype(np.uint8)
    arr = np.stack([v, v-3, v-6], axis=-1)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = PILImage.fromarray(arr, 'RGB')
    # tile joint lines (4 tiles across)
    draw = ImageDraw.Draw(img)
    tile = size // 4
    for i in range(0, size, tile):
        draw.line([(i, 0), (i, size)], fill=(190, 185, 175), width=1)
        draw.line([(0, i), (size, i)], fill=(190, 185, 175), width=1)
    return _pil_to_ursina(img, key)

def make_grass(size=256):
    key = "grass"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=12, seed=12)
    n2 = _noise(size, scale=4,  seed=13) * 0.4
    n  = np.clip(n + n2, 0, 1)
    r  = ( 72 + n * 30).astype(np.uint8)
    g  = (145 + n * 40).astype(np.uint8)
    b  = ( 58 + n * 15).astype(np.uint8)
    arr = np.stack([r, g, b], axis=-1)
    img = PILImage.fromarray(arr, 'RGB')
    return _pil_to_ursina(img, key)

def make_glass(size=64):
    key = "glass"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    img = PILImage.new('RGBA', (size, size), (155, 210, 255, 55))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size-1, size-1], outline=(200, 230, 255, 120), width=2)
    # specular highlight stripes
    draw.line([(size//6, 0), (size//4, size)], fill=(240, 248, 255, 180), width=3)
    draw.line([(size//3, 0), (size//3+5, size)], fill=(220, 238, 255, 100), width=2)
    n = _noise(size, scale=16, seed=14) * 30
    arr = np.array(img, np.float32)
    arr[:,:,3] = np.clip(arr[:,:,3] + n, 0, 100)
    img = PILImage.fromarray(arr.astype(np.uint8), 'RGBA')
    return _pil_to_ursina(img, key)

def make_beehive_tex(size=256):
    """Hexagonal honeycomb in terracotta — supersampled to reduce aliasing."""
    key = "beehive_tex"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    hi = 512
    img_hi = PILImage.new('RGB', (hi, hi), (185, 82, 55))
    draw = ImageDraw.Draw(img_hi)
    hex_r = hi // 8
    dx = hex_r * math.sqrt(3)
    dy = hex_r * 1.5
    for row in range(-1, hi // int(dy) + 2):
        for col in range(-1, hi // int(dx) + 2):
            cx = col * dx + (row % 2) * dx / 2
            cy = row * dy
            pts = []
            for a in range(6):
                angle = math.radians(60 * a - 30)
                pts.append((cx + (hex_r-2) * math.cos(angle),
                             cy + (hex_r-2) * math.sin(angle)))
            draw.polygon(pts, outline=(130, 55, 30), fill=(175, 78, 52))
            draw.polygon(pts, outline=(220, 110, 80))
    n = _noise(hi, scale=32, seed=15) * 20
    arr = np.array(img_hi, np.float32)
    arr[:,:,0] = np.clip(arr[:,:,0] + n, 0, 255)
    arr[:,:,1] = np.clip(arr[:,:,1] + n*0.4, 0, 255)
    img_hi = PILImage.fromarray(arr.astype(np.uint8), 'RGB')
    img = img_hi.resize((size, size), PILImage.LANCZOS)
    return _pil_to_ursina(img, key)

def make_garden_soil(size=128):
    key = "garden_soil"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=16, seed=16)
    r  = ( 90 + n * 30).astype(np.uint8)
    g  = ( 60 + n * 20).astype(np.uint8)
    b  = ( 30 + n * 10).astype(np.uint8)
    arr = np.stack([r, g, b], axis=-1)
    img = PILImage.fromarray(arr, 'RGB')
    return _pil_to_ursina(img, key)

def make_driveway_tex(size=256):
    key = "driveway"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    n  = _noise(size, scale=40, seed=17)
    n2 = _noise(size, scale=8,  seed=18) * 0.2
    n  = np.clip(n + n2, 0, 1)
    v  = (175 + n * 25).astype(np.uint8)
    arr = np.stack([v-5, v-5, v-8], axis=-1)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = PILImage.fromarray(arr, 'RGB')
    return _pil_to_ursina(img, key)

def make_roller_door_tex(size=256):
    key = "roller_door"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    img = PILImage.new('RGB', (size, size), (148, 152, 158))
    draw = ImageDraw.Draw(img)
    panel_h = size // 8
    for i in range(1, 8):
        y = i * panel_h
        draw.line([(0, y), (size, y)], fill=(110, 115, 122), width=3)
        draw.line([(0, y+2), (size, y+2)], fill=(175, 178, 183), width=1)
    cx = size // 2
    draw.rectangle([cx-20, size//2-4, cx+20, size//2+4], fill=(90, 95, 100))
    return _pil_to_ursina(img, key)

def make_solar_info_tex(size_w=512, size_h=256):
    key = "solar_info"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    img = PILImage.new('RGBA', (size_w, size_h), (8, 18, 42, 210))
    draw = ImageDraw.Draw(img)
    lines = [
        "  SOLAR + STORAGE",
        "15 x 400 W = 6 kWp  |  25 deg S tilt",
        "Est. yield: ~22-25 kWh/day",
        "Battery: 12 kWh LFP  |  5 kW inverter",
        "Critical loads on isolated microgrid",
    ]
    draw.rectangle([4, 4, size_w-4, size_h-4], outline=(255, 210, 0, 200), width=2)
    y = 18
    for i, line in enumerate(lines):
        col = (255, 215, 0, 255) if i == 0 else (220, 220, 220, 230)
        draw.text((18, y), line, fill=col)
        y += 40
    return _pil_to_ursina(img, key)

def _make_sun_tex(size=64):
    key = "sun_disc"
    if key in _TEX_CACHE: return _TEX_CACHE[key]
    img = PILImage.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy, r = size//2, size//2, size//2 - 2
    for dr in range(r, 0, -1):
        t = dr / r
        alpha = int(220 * (1 - t**2))
        col = (255, 245, int(200 + 55*t), alpha)
        draw.ellipse([cx-dr, cy-dr, cx+dr, cy+dr], fill=col)
    return _pil_to_ursina(img, key)


# ══════════════════════════════════════════════════════════════════════════════
# 3.  COORDINATE MAPPING
#     Blender: east=+X, north=+Y, up=+Z
#     Ursina:  east=+X, up=+Y,   south=+Z
# ══════════════════════════════════════════════════════════════════════════════
def B(bx: float, by: float, bz: float = 0.0) -> Vec3:
    return Vec3(bx - HX / 2, bz, -(by - HY / 2))


# ══════════════════════════════════════════════════════════════════════════════
# 4.  LOW-LEVEL GEOMETRY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _ent(name, pos, scale, tex=None, col=None, alpha=1.0,
         coll='box', model='cube', rot=(0,0,0)):
    kw = dict(name=name, model=model, position=pos, scale=scale,
              rotation=rot, collider=coll)
    if tex is not None:
        kw['texture'] = tex
    if col is not None:
        kw['color'] = col
    if alpha < 1.0:
        kw['alpha'] = alpha
    return Entity(**kw)

def EW(name, x0, x1, y, z0, z1, t=TW, tex=None, col=None, coll='box'):
    cx = (x0 + x1) / 2
    sx = max(abs(x1 - x0), 0.02)
    cz = (z0 + z1) / 2
    sz = max(abs(z1 - z0), 0.02)
    return _ent(name, B(cx, y, cz), (sx, sz, t), tex=tex, col=col, coll=coll)

def NS(name, y0, y1, x, z0, z1, t=TW, tex=None, col=None, coll='box'):
    cy = (y0 + y1) / 2
    sy = max(abs(y1 - y0), 0.02)
    cz = (z0 + z1) / 2
    sz = max(abs(z1 - z0), 0.02)
    return _ent(name, B(x, cy, cz), (t, sz, sy), tex=tex, col=col, coll=coll)

def SLAB(name, x0, x1, y0, y1, z, t=TS, tex=None, col=None, coll='box'):
    cx = (x0 + x1) / 2
    sx = abs(x1 - x0)
    cy = (y0 + y1) / 2
    sy = abs(y1 - y0)
    return _ent(name, B(cx, cy, z + t/2), (sx, t, sy), tex=tex, col=col, coll=coll)

def BOX(name, bx, by, bz, sx, sy, sz, tex=None, col=None, coll=None, rot=(0,0,0)):
    return _ent(name, B(bx, by, bz + sz/2), (sx, sz, sy),
                tex=tex, col=col, coll=coll, rot=rot)

# Octagonal column mesh (lazy-init after app starts)
_OCTA_MESH = None

def _make_octagon_mesh():
    verts, tris, uvs = [], [], []
    n = 8
    for i in range(n):
        a0 = math.tau * i / n
        a1 = math.tau * (i + 1) / n
        x0, z0 = math.cos(a0), math.sin(a0)
        x1, z1 = math.cos(a1), math.sin(a1)
        base = len(verts)
        verts += [(x0, 0, z0), (x1, 0, z1), (x1, 1, z1), (x0, 1, z0)]
        uvs   += [(i/n, 0), ((i+1)/n, 0), ((i+1)/n, 1), (i/n, 1)]
        tris  += [(base, base+1, base+2), (base, base+2, base+3)]
    return Mesh(vertices=verts, triangles=tris, uvs=uvs, mode='triangle')

def COLUMN(name, bx, by, bz, sz, r=0.15, tex=None, col=None):
    global _OCTA_MESH
    if _OCTA_MESH is None:
        _OCTA_MESH = _make_octagon_mesh()
    return Entity(name=name, model=_OCTA_MESH,
                  position=B(bx, by, bz + sz/2) - Vec3(0, sz/2, 0),
                  scale=(r*2, sz, r*2),
                  texture=tex, color=col or C_SAND,
                  collider='box')

def STAIR_RAMP(name, x0, x1, y, z_bot, z_top, depth=1.2):
    """Invisible slope collider spanning a staircase."""
    length  = math.hypot(x1 - x0, z_top - z_bot)
    cx      = (x0 + x1) / 2
    cz      = (z_bot + z_top) / 2
    angle_x = math.degrees(math.atan2(z_top - z_bot, x1 - x0))
    return Entity(name=name, model='cube',
                  position=B(cx, y, cz),
                  scale=(length, 0.12, depth),
                  rotation=(0, 0, -angle_x),
                  color=color.rgba(0, 0, 0, 0),
                  collider='box',
                  visible=False)

def _shadow(name, bx, by, bz, sx, sy, opacity=60):
    Entity(name=f'Shad_{name}',
           model='quad',
           position=B(bx, by, bz + 0.005),
           rotation=(90, 0, 0),
           scale=(sx * 0.92, sy * 0.92, 1),
           color=color.rgba(30, 25, 20, opacity),
           collider=None)

def _orient_arrow(entity, p0: Vec3, p1: Vec3):
    diff = (p1 - p0).normalized()
    if abs(diff.y) > 0.7:
        entity.rotation_x = -90 if diff.y > 0 else 90
    else:
        angle = math.degrees(math.atan2(diff.x, diff.z))
        entity.rotation_y = angle


# ══════════════════════════════════════════════════════════════════════════════
# 5.  TEXTURE REFS
# ══════════════════════════════════════════════════════════════════════════════
print("  Generating procedural textures…")
T_PLASTER  = make_lime_plaster()
T_TERRA    = make_terracotta()
T_SAND     = make_sandstone()
T_TIMBER   = make_timber()
T_PV       = make_pv_panel()
T_FLOOR    = make_concrete_floor()
T_GLASS    = make_glass()
T_BEEHIVE  = make_beehive_tex()
T_SOIL     = make_garden_soil()
T_GRASS    = make_grass()
T_DRIVE    = make_driveway_tex()
T_ROLLER   = make_roller_door_tex()
T_SOL_INFO = make_solar_info_tex()
print("  Textures ready.")


# ══════════════════════════════════════════════════════════════════════════════
# 6.  COLOUR FALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
C_PLASTER  = color.rgb(242, 238, 226)
C_CEIL     = color.rgb(250, 248, 244)
C_FLOOR    = color.rgb(220, 214, 200)
C_SAND     = color.rgb(196, 165, 110)
C_TERRA    = color.rgb(182,  88,  58)
C_TIMBER   = color.rgb(172, 128,  70)
C_GLASS    = color.rgba(155, 210, 255, 60)
C_STEEL    = color.rgb(140, 148, 158)
C_PV       = color.rgb( 28,  55, 118)
C_GREEN    = color.rgb( 88, 150,  62)
C_SOIL     = color.rgb( 88,  58,  28)
C_DRIVE    = color.rgb(180, 176, 165)
C_GRASS    = color.rgb(112, 165,  80)
C_WALL_EXT = color.rgb(235, 230, 218)
C_RAILING  = color.rgb(196, 168, 118)
C_FOG      = color.rgb(184, 210, 235)

C_COOL_FLOW   = color.rgba(  0, 215, 255, 140)
C_SEC_CONE    = color.rgba(255,  45,  45, 100)
C_SOL_GLOW    = color.rgba(255, 215,   0, 110)


# ══════════════════════════════════════════════════════════════════════════════
# 7.  SCENE BUILDER — SITE
# ══════════════════════════════════════════════════════════════════════════════
def build_site():
    Entity(name='Ground', model='plane',
           scale=(200, 1, 200), position=(0, -0.01, 0),
           texture=T_DRIVE, texture_scale=(40, 40), color=C_DRIVE,
           collider='box')

    Entity(name='Lawn_E', model='plane',
           scale=(LAWN_W*2, 1, HY + 4),
           position=B(HX + LAWN_W, HY/2, 0),
           texture=T_GRASS, texture_scale=(8, 8), color=C_GRASS)

    Entity(name='Driveway', model='plane',
           scale=(DRIVEWAY_W, 1, HY + 4),
           position=B(-DRIVEWAY_W/2, HY/2, 0),
           texture=T_DRIVE, texture_scale=(5, 5), color=C_DRIVE)

    wc = color.rgb(228, 222, 210)
    xw0, xw1 = -DRIVEWAY_W - 0.1, HX + LAWN_W + 0.1
    yw0, yw1 = -2.0, HY + 2.0
    for n, (a, b, c, d) in [
        ('BW_S', (xw0, xw1, yw0, 'EW')),
        ('BW_N', (xw0, xw1, yw1, 'EW')),
    ]:
        EW(n, a, b, c, 0, 1.8, t=0.18, tex=T_PLASTER, col=wc)
    for n, (a, b, c, d) in [
        ('BW_W', (yw0, yw1, xw0, 'NS')),
        ('BW_E', (yw0, yw1, xw1, 'NS')),
    ]:
        NS(n, a, b, c, 0, 1.8, t=0.18, tex=T_PLASTER, col=wc)

    for gy, gn in [(4.0, 'GateL'), (6.0, 'GateR')]:
        COLUMN(gn, xw0, gy, 0, 2.0, r=0.2, tex=T_SAND, col=C_SAND)

    BOX('RWH_Tank', -3.5, HY/2, -1.5, 4.0, 3.0, 1.5,
        col=color.rgba(80, 120, 200, 35), coll=None)

    _ent('RechargePit', B(HX + 4.5, HY + 1.5, 0),
         (1.0, 0.08, 1.0), col=color.rgb(155, 135, 108),
         model='cube', coll=None)

    # Stepping-stone path (east approach) + compass rose on ground
    for i in range(5):
        px = HX + 0.4 + i * 1.0
        BOX(f'Step_{i}', px, 5.0, 0, 0.5, 0.5, 0.04, tex=T_SAND, col=C_SAND)


# ══════════════════════════════════════════════════════════════════════════════
# 8.  SCENE BUILDER — GROUND FLOOR
# ══════════════════════════════════════════════════════════════════════════════
def build_gf():
    z0, z1 = GF_Z, GF_Z + GF_H

    SLAB('GF_Floor', 0, HX, 0, HY, z0 - TS, tex=T_FLOOR, col=C_FLOOR)
    SLAB('GF_Ceil',  0, HX, 0, HY, z1, tex=None, col=C_CEIL, coll=None)

    pt = T_PLASTER; pc = C_WALL_EXT

    # East facade
    NS('EF_S1',      0.0, 3.2,  HX, z0, z1, tex=pt, col=pc)
    NS('EF_GDH',    3.2, 4.2,  HX, z0+DOOR_H, z1, tex=pt, col=pc)
    NS('EF_Sill1',  4.2, 5.5,  HX, z0, z0+WIN_SILL, tex=pt, col=pc)
    NS('EF_Head1',  4.2, 5.5,  HX, z0+WIN_HEAD, z1, tex=pt, col=pc)
    Entity(name='EF_FoyerGl', model='cube',
           position=B(HX, 4.85, z0+1.65),
           scale=(TW, WIN_HEAD-WIN_SILL, 1.3),
           texture=T_GLASS, color=C_GLASS, alpha=0.4, collider=None)
    NS('EF_EntH',   5.5, 6.5,  HX, z0+DOOR_H, z1, tex=pt, col=pc)
    NS('EF_N1',     6.5, 8.0,  HX, z0, z1, tex=pt, col=pc)
    NS('EF_KitSill',8.0, 10.0, HX, z0, z0+WIN_SILL, tex=pt, col=pc)
    NS('EF_KitHead',8.0, 10.0, HX, z0+WIN_HEAD, z1, tex=pt, col=pc)
    Entity(name='EF_KitGl', model='cube',
           position=B(HX, 9.0, z0+1.65),
           scale=(TW, WIN_HEAD-WIN_SILL, 2.0),
           texture=T_GLASS, color=C_GLASS, alpha=0.4, collider=None)
    NS('EF_N2',     10.0, HY,  HX, z0, z1, tex=pt, col=pc)

    # West facade
    NS('WF_S', 0.0, 0.5, 0, z0, z1, tex=pt, col=pc)
    NS('WF_DH', 0.5, 4.5, 0, z0+2.5, z1, tex=pt, col=pc)
    BOX('RollerDoor', 0, 2.5, z0, TW, 2.5, 2.5,
        tex=T_ROLLER, col=color.rgb(148, 152, 158), coll='box')
    NS('WF_N', 4.5, HY, 0, z0, z1, tex=pt, col=pc)

    # South facade
    EW('SF_W',   0,    CX1,  0, z0, z1, tex=pt, col=pc)
    EW('SF_Mid', CX1, 10.0, 0, z0, z1, tex=pt, col=pc)
    EW('SF_E',  12.5,  HX,  0, z0, z1, tex=pt, col=pc)
    EW('SF_BhH', 10.0, 12.5, 0, z0+2.5+0.05, z1, tex=pt, col=pc)

    # North facade
    EW('NF', 0, HX, HY, z0, z1, tex=pt, col=pc)

    # Interior walls
    NS('Int_CX1_S',  0.0, 4.4,  CX1, z0, z1, TI, tex=pt, col=pc)
    NS('Int_CX1_DH', 4.4, 5.4,  CX1, z0+DOOR_H, z1, TI, tex=pt, col=pc)
    NS('Int_CX1_N',  5.4, HY,   CX1, z0, z1, TI, tex=pt, col=pc)
    EW('Int_CY1_W',  CX1, 7.2,  CY1, z0, z1, TI, tex=pt, col=pc)
    EW('Int_CY1_DH', 7.2, 8.3,  CY1, z0+DOOR_H, z1, TI, tex=pt, col=pc)
    EW('Int_CY1_E',  8.3, HX,   CY1, z0, z1, TI, tex=pt, col=pc)
    EW('Int_GN', CX2, HX,  3.5, z0, z1, TI, tex=pt, col=pc)
    NS('Int_GW', 0.0, 3.5, CX2, z0, z1, TI, tex=pt, col=pc)
    EW('Core_S', CX1, CX2, 3.2, z0, z1, TI, tex=pt, col=pc)
    EW('Core_N', CX1, CX2, 6.8, z0, z1, TI, tex=pt, col=pc)
    EW('PB_N', CX2, HX, 4.0, z0, z1, TI, tex=pt, col=pc)
    NS('PB_W', 3.5, 4.0, CX2+1.5, z0, z1, TI, tex=pt, col=pc)

    # Elevator shaft
    for nm, (y0e, y1e, xe) in [
        ('ElW', (3.2, 4.8, CX2-0.1)),
        ('ElE', (3.2, 4.8, CX2+1.5)),
    ]:
        NS(nm, y0e, y1e, xe, z0, z1, 0.10, col=C_STEEL)
    for nm, (x0e, x1e, ye) in [
        ('ElS', (CX2-0.1, CX2+1.5, 3.2)),
        ('ElN', (CX2-0.1, CX2+1.5, 4.8)),
    ]:
        EW(nm, x0e, x1e, ye, z0, z1, 0.10, col=C_STEEL)

    # Verandah
    SLAB('Verandah_Slab', HX, HX+1.5, 3.0, 7.0, z1-TS, tex=T_SAND, col=C_SAND, coll=None)
    COLUMN('Verandah_CN', HX+0.75, 3.2, z0, z1, r=0.15, tex=T_SAND, col=C_SAND)
    COLUMN('Verandah_CS', HX+0.75, 6.8, z0, z1, r=0.15, tex=T_SAND, col=C_SAND)
    EW('Verandah_Fascia',  HX, HX+1.5, 3.0, z1-0.1, z1, 0.1, tex=T_SAND, col=C_SAND, coll=None)
    EW('Verandah_FasciaN', HX, HX+1.5, 7.0, z1-0.1, z1, 0.1, tex=T_SAND, col=C_SAND, coll=None)

    # Guest balcony
    SLAB('GuestBalc', HX, HX+1.0, 0.5, 3.2, z0, tex=T_FLOOR, col=C_FLOOR)
    for nm, (x0r, x1r, yr) in [
        ('GB_RS', (HX, HX+1.0, 0.5)),
        ('GB_RN', (HX, HX+1.0, 3.2)),
    ]:
        EW(nm, x0r, x1r, yr, z0, z0+1.0, 0.07, tex=T_SAND, col=C_RAILING, coll=None)
    NS('GB_RE', 0.5, 3.2, HX+1.0, z0, z0+1.0, 0.07, tex=T_SAND, col=C_RAILING, coll=None)

    # Staircase — visual steps (no collider) + single ramp collider
    rh, rd = 0.183, 0.25
    for i in range(18):
        BOX(f'StGF_{i}', CX1+0.5+i*rd, 4.0, z0+i*rh,
            rd, 1.1, rh, tex=T_SAND, col=C_SAND, coll=None)
    STAIR_RAMP('RampGF', CX1+0.5, CX1+0.5+18*rd, 4.0, z0, z0+18*rh, depth=1.1)

    # Beehive panels (E + S faces)
    BOX('Beehive_E', HX-0.2, 5.1, z0+0.7, 0.25, 2.5, 2.5,
        tex=T_BEEHIVE, col=C_TERRA, coll=None)
    BOX('Beehive_S', 11.25, 0.06, z0+0.7, 2.5, 0.25, 2.5,
        tex=T_BEEHIVE, col=C_TERRA, coll=None)
    BOX('Drip_E', HX-0.22, 5.1, z0+3.0, 0.04, 0.1, 0.1,
        col=color.rgb(100, 140, 200), coll=None)
    BOX('Drip_S', 11.25, 0.0, z0+3.0, 0.1, 0.04, 0.1,
        col=color.rgb(100, 140, 200), coll=None)
    # 3D cone relief on beehive faces
    _build_beehive_relief('BhE', HX-0.2, 5.1, z0+0.7, face_axis='E')
    _build_beehive_relief('BhS', 11.25, 0.06, z0+0.7, face_axis='S')

    # Furniture
    BOX('Island', 11.5, 7.5, z0, 3.0, 1.2, 0.9, tex=T_TIMBER, col=C_TIMBER, coll='box')
    _shadow('Island', 11.5, 7.5, z0, 3.0, 1.2)
    for dy in [8.0, 9.2, 10.2, 10.8]:
        BOX(f'DCh_{dy:.0f}', 11.0, dy, z0, 0.5, 0.5, 0.45, col=C_TIMBER)
    BOX('DiningTbl', 12.0, 9.0, z0, 2.4, 1.0, 0.75, tex=T_TIMBER, col=C_TIMBER, coll='box')
    _shadow('DiningTbl', 12.0, 9.0, z0, 2.4, 1.0)
    BOX('SofaMain', 10.5, 2.8, z0, 3.2, 0.9, 0.45, tex=T_TIMBER, col=C_TIMBER, coll='box')
    BOX('SofaArm',  10.5, 1.9, z0, 0.9, 0.9, 0.45, tex=T_TIMBER, col=C_TIMBER, coll='box')
    _shadow('Sofa', 10.5, 2.6, z0, 3.6, 1.0)
    BOX('CoffeeT',  11.0, 1.5, z0, 1.2, 0.6, 0.40, tex=T_TIMBER, col=C_TIMBER)
    BOX('GuestBed', 12.0, 1.8, z0, 2.0, 1.6, 0.55, tex=T_TIMBER, col=C_TIMBER)
    _shadow('GuestBed', 12.0, 1.8, z0, 2.0, 1.6)
    BOX('GBedHB',   12.0, 0.7, z0+0.55, 2.0, 0.15, 0.55, tex=T_TIMBER, col=C_TIMBER)
    BOX('BatteryCab', 1.2, 9.0, z0, 0.8, 0.5, 1.8, col=C_STEEL, coll='box')
    BOX('Inverter',   2.2, 9.0, z0, 0.6, 0.4, 1.2, col=C_STEEL, coll='box')
    BOX('NVR_Cab',   CX1+0.3, 3.5, z0, 0.5, 0.4, 1.6, col=C_STEEL, coll='box')

def _build_beehive_relief(name_prefix, bx, by, bz, face_axis='E'):
    cone_w, cone_h, cone_d = 0.38, 0.38, 0.22
    cols, rows = 4, 6
    for ci in range(cols):
        for ri in range(rows):
            offset_x = -1.25 + (ci + 0.5) * (2.5 / cols)
            offset_z =  0.70 + (ri + 0.5) * (2.5 / rows)
            if ri % 2 == 1:
                offset_x += (2.5 / cols) / 2
            if face_axis == 'E':
                pos = B(bx + cone_d/2, by + offset_x, bz + offset_z)
                sc  = (cone_d, cone_w, cone_h)
            else:
                pos = B(bx + offset_x, by - cone_d/2, bz + offset_z)
                sc  = (cone_h, cone_w, cone_d)
            Entity(name=f'{name_prefix}_cone_{ci}_{ri}',
                   model='cube', position=pos, scale=sc,
                   color=C_TERRA, texture=T_TERRA, collider=None)


# ══════════════════════════════════════════════════════════════════════════════
# 9.  SCENE BUILDER — FIRST FLOOR
# ══════════════════════════════════════════════════════════════════════════════
def build_f1():
    z0, z1 = F1_Z, F1_Z + F1_H
    pt = T_PLASTER; pc = C_WALL_EXT

    SLAB('F1_Floor',      0, HX,     0,  HY, z0-TS, tex=T_FLOOR, col=C_FLOOR)
    SLAB('F1_CantFloor', -CANT_W, 0, 0,  HY, z0-TS, tex=T_FLOOR, col=C_FLOOR)
    SLAB('F1_Ceil',       0, HX,     0,  HY, z1, col=C_CEIL, coll=None)

    NS('F1_EF_S',     0.0, 3.0, HX, z0, z1, tex=pt, col=pc)
    NS('F1_EF_Sill1', 3.0, 5.0, HX, z0, z0+WIN_SILL, tex=pt, col=pc)
    NS('F1_EF_Head1', 3.0, 5.0, HX, z0+WIN_HEAD, z1, tex=pt, col=pc)
    Entity(name='F1_EF_Gl1', model='cube',
           position=B(HX, 4.0, z0+1.65), scale=(TW, WIN_HEAD-WIN_SILL, 2.0),
           texture=T_GLASS, color=C_GLASS, alpha=0.4, collider=None)
    NS('F1_EF_Sill2', 5.0, 7.0, HX, z0, z0+WIN_SILL, tex=pt, col=pc)
    NS('F1_EF_Head2', 5.0, 7.0, HX, z0+WIN_HEAD, z1, tex=pt, col=pc)
    Entity(name='F1_EF_Gl2', model='cube',
           position=B(HX, 6.0, z0+1.65), scale=(TW, WIN_HEAD-WIN_SILL, 2.0),
           texture=T_GLASS, color=C_GLASS, alpha=0.4, collider=None)
    NS('F1_EF_N',     7.0, HY,  HX, z0, z1, tex=pt, col=pc)

    EW('F1_SF', 0, HX, 0,  z0, z1, tex=pt, col=pc)
    EW('F1_NF', 0, HX, HY, z0, z1, tex=pt, col=pc)
    NS('F1_WF_S', 0, HY/2-0.6, 0, z0, z1, tex=pt, col=pc)
    NS('F1_WF_N', HY/2+0.6, HY, 0, z0, z1, tex=pt, col=pc)
    NS('F1_WF_Sill', HY/2-0.6, HY/2+0.6, 0, z0, z0+WIN_SILL, tex=pt, col=pc)
    NS('F1_WF_Head', HY/2-0.6, HY/2+0.6, 0, z0+WIN_HEAD, z1, tex=pt, col=pc)

    EW('Cant_S', -CANT_W, 0, 0,  z0, z1, tex=pt, col=pc)
    EW('Cant_N', -CANT_W, 0, HY, z0, z1, tex=pt, col=pc)
    NS('Cant_W', 0, HY, -CANT_W, z0, z1, tex=pt, col=pc)
    Entity(name='Clerestory_Gl', model='cube',
           position=B(-CANT_W/2, HY+0.05, z1+0.6),
           scale=(CANT_W-0.2, 1.2, 0.08),
           texture=T_GLASS, color=C_GLASS, alpha=0.5, collider=None)

    NS('F1_CX1_S',    0, 4.5,   CX1, z0, z1, TI, tex=pt, col=pc)
    NS('F1_CX1_N',    5.5, HY,  CX1, z0, z1, TI, tex=pt, col=pc)
    EW('F1_MasterS',  CX2, HX,  3.0, z0, z1, TI, tex=pt, col=pc)
    NS('F1_MasterW',  3.0, HY,  CX2, z0, z1, TI, tex=pt, col=pc)
    EW('F1_BR2S',     0, CX1,   CY1, z0, z1, TI, tex=pt, col=pc)
    EW('F1_BR3S',     CX1, CX2, CY1, z0, z1, TI, tex=pt, col=pc)
    EW('F1_LoungeS',  CX2, HX,  5.5, z0, z1, TI, tex=pt, col=pc)

    for sn, (x0b, x1b, y0b, y1b) in [
        ('Balc_E',  (HX, HX+1.5, 0, HY)),
        ('Balc_N',  (0, HX+1.5, HY, HY+1.5)),
        ('Balc_S',  (0, HX+1.5, -1.5, 0)),
    ]:
        SLAB(sn, x0b, x1b, y0b, y1b, z0-TS, tex=T_FLOOR, col=C_FLOOR)
    NS('BPar_E',  0, HY, HX+1.5, z0, z0+1.0, 0.12, tex=T_PLASTER, col=C_RAILING, coll=None)
    EW('BPar_N',  0, HX+1.5, HY+1.5, z0, z0+1.0, 0.12, tex=T_PLASTER, col=C_RAILING, coll=None)
    EW('BPar_S',  0, HX+1.5, -1.5, z0, z0+1.0, 0.12, tex=T_PLASTER, col=C_RAILING, coll=None)

    # Visual steps (no collider) + ramp
    rh, rd = 0.183, 0.25
    for i in range(18):
        BOX(f'StF1_{i}', CX1+0.5+i*rd, 4.0, z0+i*rh,
            rd, 1.1, rh, tex=T_SAND, col=C_SAND, coll=None)
    STAIR_RAMP('RampF1', CX1+0.5, CX1+0.5+18*rd, 4.0, z0, z0+18*rh, depth=1.1)

    BOX('MasterBed',  12.0, 8.0, z0, 2.1, 1.8, 0.55, tex=T_TIMBER, col=C_TIMBER)
    _shadow('MasterBed', 12.0, 8.0, z0, 2.1, 1.8)
    BOX('MBedHB',     12.0, 6.3, z0+0.55, 2.1, 0.15, 0.6, tex=T_TIMBER, col=C_TIMBER)
    BOX('WIW_Shelf',  HX-0.3, 3.8, z0, 0.5, 2.5, 2.1, tex=T_TIMBER, col=C_TIMBER)
    BOX('BR2_Bed',    2.5, 7.5, z0, 1.8, 1.5, 0.55, tex=T_TIMBER, col=C_TIMBER)
    _shadow('BR2_Bed', 2.5, 7.5, z0, 1.8, 1.5)
    BOX('BR3_Bed',    7.5, 7.5, z0, 1.8, 1.5, 0.55, tex=T_TIMBER, col=C_TIMBER)
    _shadow('BR3_Bed', 7.5, 7.5, z0, 1.8, 1.5)
    BOX('F1_Lounge',  11.2, 4.5, z0, 2.5, 0.9, 0.45, tex=T_TIMBER, col=C_TIMBER)
    BOX('WS_Table1',  -1.5, 5.0, z0, 2.5, 0.8, 0.9, tex=T_TIMBER, col=C_TIMBER)
    _shadow('WS_Table1', -1.5, 5.0, z0, 2.5, 0.8)
    BOX('WS_Table2',  -1.5, 2.0, z0, 2.5, 0.8, 0.9, tex=T_TIMBER, col=C_TIMBER)
    _shadow('WS_Table2', -1.5, 2.0, z0, 2.5, 0.8)
    BOX('WS_Sink',    -0.3, 9.2, z0, 0.6, 0.4, 0.9, col=C_STEEL)
    BOX('WS_DryRack', -2.5, 8.0, z0, 0.12, 1.8, 1.8, col=C_STEEL, coll='box')
    BOX('WS_DryRack2',-2.5, 6.0, z0, 0.12, 1.8, 1.8, col=C_STEEL, coll='box')
    for si in range(6):
        BOX(f'SilkBolt_{si}', -0.2, 1.0+si*1.3, z0+0.9+si*0.12, 0.12, 0.8, 0.12,
            col=color.rgb(random.randint(120,220),
                          random.randint(60,180),
                          random.randint(80,200)))


# ══════════════════════════════════════════════════════════════════════════════
# 10.  SCENE BUILDER — TERRACE
# ══════════════════════════════════════════════════════════════════════════════
def build_terrace():
    z0 = T_Z
    pt = T_PLASTER; pc = C_WALL_EXT

    SLAB('T_Slab', 0, HX, 0, HY, z0-TS, tex=T_FLOOR, col=C_FLOOR)

    EW('T_ParS', 0, HX, 0,  z0, z0+PARAPET_H, 0.15, tex=pt, col=pc)
    EW('T_ParN', 0, HX, HY, z0, z0+PARAPET_H, 0.15, tex=pt, col=pc)
    NS('T_ParW', 0, HY, 0,  z0, z0+PARAPET_H, 0.15, tex=pt, col=pc)
    NS('T_ParE', 0, HY, HX, z0, z0+PARAPET_H, 0.15, tex=pt, col=pc)

    # Viewing room NE corner
    vz1 = z0 + 3.35
    vx0, vx1 = HX-6.1, HX
    vy0, vy1 = HY-6.1, HY
    EW('VR_S',    vx0, vx1, vy0, z0, vz1, tex=pt, col=pc)
    NS('VR_W',    vy0, vy1, vx0, z0, vz1, tex=pt, col=pc)
    SLAB('VR_Ceil', vx0, vx1, vy0, vy1, vz1, col=C_CEIL, coll=None)
    SLAB('VR_Floor', vx0, vx1, vy0, vy1, z0-TS, tex=T_FLOOR, col=C_FLOOR)
    NS('VR_EGl', vy0, vy1, HX, z0, vz1, 0.05, tex=T_GLASS, col=C_GLASS, coll=None)
    EW('VR_NGl', vx0, vx1, HY, z0, vz1, 0.05, tex=T_GLASS, col=C_GLASS, coll=None)
    SLAB('VR_Shade', vx0-0.3, vx1, vy0, vy0-1.5, vz1-0.05, col=C_SAND, coll=None)

    # Stair enclosure
    se_x0, se_x1 = CX1+0.3, CX1+3.7
    se_y0, se_y1 = CY1-1.7, CY1+1.7
    se_h = 2.6
    EW('SE_S', se_x0, se_x1, se_y0, z0, z0+se_h, tex=pt, col=pc)
    EW('SE_N', se_x0, se_x1, se_y1, z0, z0+se_h, tex=pt, col=pc)
    NS('SE_W', se_y0, se_y1, se_x0, z0, z0+se_h, tex=pt, col=pc)
    NS('SE_E', se_y0, se_y1, se_x1, z0, z0+se_h, tex=pt, col=pc)
    SLAB('SE_Roof', se_x0, se_x1, se_y0, se_y1, z0+se_h, col=C_WALL_EXT)

    # Burjeel wind-catcher
    bx = (se_x0+se_x1)/2
    by = (se_y0+se_y1)/2
    bz = z0 + se_h
    for sign, cx in [(-1, bx-1), (1, bx+1)]:
        NS(f'BJ_NS_{sign}', by-1, by+1, cx, bz, bz+4.0, 0.09, tex=T_TERRA, col=C_TERRA, coll='box')
    for sign, cy in [(-1, by-1), (1, by+1)]:
        EW(f'BJ_EW_{sign}', bx-1, bx+1, cy, bz, bz+4.0, 0.09, tex=T_TERRA, col=C_TERRA, coll='box')
    for i in range(10):
        frac = (i + 0.5) / 10
        BOX(f'BJ_Lou_{i}', bx, by-1, bz + frac*4.0, 2.0, 0.04, 0.04, col=C_SAND)

    # Workshop clerestory monitor
    cz = z0 + 0.1
    BOX('ClerBox',   -CANT_W/2, HY+0.6, cz, CANT_W-0.1, 0.08, 1.2, tex=pt, col=pc)
    Entity(name='ClerGl', model='cube',
           position=B(-CANT_W/2, HY+0.05, z0+0.7),
           scale=(CANT_W-0.2, 1.0, 0.07),
           texture=T_GLASS, color=C_GLASS, alpha=0.5, collider=None)

    # PV pergola
    px0, px1 = 0.4, 6.4
    py0, py1 = 0.4, 5.4
    ph = 2.4
    for ppx in [px0+0.2, (px0+px1)/2, px1-0.2]:
        for ppy in [py0+0.2, py1-0.2]:
            BOX(f'PVPost_{ppx:.0f}_{ppy:.0f}', ppx, ppy, z0, 0.1, 0.1, ph, col=C_STEEL, coll='box')
    EW('PV_BeamS', px0, px1, py0, z0+ph, z0+ph+0.12, 0.10, col=C_STEEL)
    EW('PV_BeamN', px0, px1, py1, z0+ph, z0+ph+0.12, 0.10, col=C_STEEL)
    NS('PV_BeamE', py0, py1, px1, z0+ph, z0+ph+0.12, 0.10, col=C_STEEL)
    NS('PV_BeamW', py0, py1, px0, z0+ph, z0+ph+0.12, 0.10, col=C_STEEL)
    for ci in range(3):
        for ri in range(5):
            ppx = px0 + 0.7 + ci * 1.8
            ppy = py0 + 0.5 + ri * 0.9
            Entity(name=f'PV_{ci}_{ri}', model='cube',
                   position=B(ppx, ppy, z0+ph+0.15),
                   scale=(1.0, 0.03, 2.0),
                   rotation=(25, 0, 0),
                   texture=T_PV, color=C_PV)

    # Raised garden beds
    for gi, (gx, gy) in enumerate([(2.5,5.8),(2.5,7.8),(4.5,5.8),(4.5,7.8)]):
        BOX(f'Bed_{gi}',  gx, gy, z0, 1.2, 3.0, 0.5, tex=T_TERRA, col=C_TERRA, coll='box')
        BOX(f'Soil_{gi}', gx, gy, z0+0.48, 1.2, 3.0, 0.06, tex=T_SOIL, col=C_SOIL)
        for sx_off, sy_off in [(-0.3,0),(0.3,0),(0,-0.8),(0,0.8)]:
            h = random.uniform(0.3, 0.7)
            _ent(f'Plant_{gi}_{sx_off}', B(gx+sx_off, gy+sy_off, z0+0.55+h/2),
                 (0.35+random.uniform(-0.1,0.1), h, 0.35+random.uniform(-0.1,0.1)),
                 col=color.rgb(random.randint(70,110),
                               random.randint(135,175),
                               random.randint(50,85)),
                 model='sphere', coll=None)
    for gi, (gx, gy) in enumerate([(2.5,5.8),(2.5,7.8),(4.5,5.8),(4.5,7.8)]):
        BOX(f'Drip_T_{gi}', gx, gy, z0+0.52, 1.1, 0.03, 0.02,
            col=color.rgb(80, 110, 160), coll=None)


# ══════════════════════════════════════════════════════════════════════════════
# 11.  OVERLAY SYSTEMS
# ══════════════════════════════════════════════════════════════════════════════
_overlay_ents: dict[str, list] = {'cooling': [], 'security': [], 'solar': [], 'scenario': []}

def build_systems():
    # Cooling airflow arrows with correct orientation
    flow_pts = [
        B(HX-0.4, 5.1, GF_Z+1.5),
        B(CX2+0.5, 5.0, GF_Z+1.5),
        B(STAIR_X,  5.0, GF_Z+1.5),
        B(STAIR_X,  5.0, F1_Z+1.8),
        B(STAIR_X,  5.0, T_Z+3.0),
    ]
    for i in range(len(flow_pts)-1):
        p0, p1 = flow_pts[i], flow_pts[i+1]
        mid  = (p0+p1)/2
        diff = p1-p0
        length = diff.length()
        is_vert = abs(diff.y) > abs(diff.z)
        scale = (0.28, length, 0.28) if is_vert else (0.28, 0.28, length)
        e = Entity(name=f'Flow_{i}', model='cube',
                   position=mid, scale=scale,
                   color=C_COOL_FLOW, alpha=0.55, enabled=False, collider=None)
        _orient_arrow(e, p0, p1)
        _overlay_ents['cooling'].append(e)
        cone = Entity(name=f'FlowHead_{i}', model='sphere',
                      position=p1, scale=(0.38, 0.38, 0.38),
                      color=C_COOL_FLOW, alpha=0.7, enabled=False, collider=None)
        _overlay_ents['cooling'].append(cone)

    # Security cameras
    cam_xw0 = -DRIVEWAY_W - 0.2
    cam_positions = [
        B(cam_xw0, 5.0, 1.7),
        B(-DRIVEWAY_W+1.0, 2.0, 1.7),
        B(HX+0.2, 5.0, GF_Z+2.8),
        B(HX+LAWN_W-0.5, HY+1.5, 1.7),
        B(cam_xw0, 0.5, 1.7),
        B(STAIR_X, HY/2, T_Z+2.5),
        B(CX1/2, HY/2, GF_Z+2.8),
    ]
    for i, p in enumerate(cam_positions):
        body = Entity(name=f'Cam_{i}', model='cube',
                      position=p, scale=(0.18, 0.14, 0.28),
                      color=color.rgb(25, 25, 25), enabled=False, collider=None)
        cone = Entity(name=f'CamFOV_{i}', model='sphere',
                      position=p, scale=(3.5, 0.12, 3.5),
                      color=C_SEC_CONE, alpha=0.3, enabled=False, collider=None)
        _overlay_ents['security'].extend([body, cone])

    sensor_pts = [
        B(cam_xw0, 3.0, 1.4), B(cam_xw0, 7.0, 1.4),
        B(HX+LAWN_W+0.1, 3.0, 1.4), B(HX+LAWN_W+0.1, 7.0, 1.4),
        B(3.0, PLOT_Y0, 1.4), B(10.0, PLOT_Y0, 1.4),
        B(3.0, PLOT_Y1, 1.4), B(10.0, PLOT_Y1, 1.4),
    ]
    for i, p in enumerate(sensor_pts):
        s = Entity(name=f'PIR_{i}', model='sphere',
                   position=p, scale=(0.18, 0.18, 0.18),
                   color=color.rgb(255, 100, 30), enabled=False, collider=None)
        _overlay_ents['security'].append(s)

    # Solar glow on PV panels
    for ci in range(3):
        for ri in range(5):
            ppx = 0.4 + 0.7 + ci * 1.8
            ppy = 0.4 + 0.5 + ri * 0.9
            glow = Entity(name=f'SolGlow_{ci}_{ri}', model='cube',
                          position=B(ppx, ppy, T_Z+2.4+0.2),
                          scale=(1.1, 0.06, 2.1),
                          rotation=(25, 0, 0),
                          color=C_SOL_GLOW, alpha=0.45, enabled=False, collider=None)
            _overlay_ents['solar'].append(glow)

    # Solar info panel with data texture
    sol_info = Entity(name='SolInfoPlane', model='quad',
                      position=B(3.5, 3.0, T_Z+3.0),
                      scale=(3.5, 1.4, 1.0),
                      texture=T_SOL_INFO,
                      billboard=True,
                      enabled=False, collider=None)
    _overlay_ents['solar'].append(sol_info)

    # ── Scenario overlay: Security degraded (2 cameras offline) ──────────
    # Failed camera positions: GateN (0) and NE (3)
    _FAIL_CAM_POS = [
        B(-DRIVEWAY_W-0.2, 5.0, 1.7),    # GateN
        B(HX+LAWN_W-0.5, HY+1.5, 1.7),   # NE
    ]
    for i, p in enumerate(_FAIL_CAM_POS):
        # Grey-out marker with red X stripe
        dead = Entity(name=f'DeadCam_{i}', model='cube',
                      position=p, scale=(0.22, 0.22, 0.22),
                      color=color.rgb(100, 40, 40), enabled=False, collider=None)
        x_bar1 = Entity(name=f'CamX1_{i}', model='cube',
                        position=p + Vec3(0, 0.15, 0),
                        scale=(0.04, 0.30, 0.04),
                        rotation=(0, 0, 45),
                        color=color.rgb(255, 40, 40), enabled=False, collider=None)
        x_bar2 = Entity(name=f'CamX2_{i}', model='cube',
                        position=p + Vec3(0, 0.15, 0),
                        scale=(0.04, 0.30, 0.04),
                        rotation=(0, 0, -45),
                        color=color.rgb(255, 40, 40), enabled=False, collider=None)
        _overlay_ents['scenario'].extend([dead, x_bar1, x_bar2])

    # Elevated PIR indicators at compensating positions
    _ELEV_PIR_POS = [
        B(-DRIVEWAY_W-0.2, 5.0, 1.4),    # gate
        B(HX+LAWN_W+0.1, HY+0.8, 1.4),   # NE area
        B(-DRIVEWAY_W-0.2, 0.5, 1.4),    # SW
        B(HX+0.2, 5.0, GF_Z+2.6),        # front door
    ]
    for i, p in enumerate(_ELEV_PIR_POS):
        pir_glow = Entity(name=f'ElevPIR_{i}', model='sphere',
                          position=p, scale=(0.5, 0.5, 0.5),
                          color=color.rgba(255, 130, 20, 180),
                          enabled=False, collider=None)
        _overlay_ents['scenario'].append(pir_glow)

    # RWH scenario: blue pipe reroute from mains → beehive
    _PIPE_PTS = [
        B(-DRIVEWAY_W, 5.0, 0.5),
        B(-CANT_W-0.1, 5.0, 0.5),
        B(-2.5, 5.0, 0.5),
        B(0.1, 5.0, 0.5),
    ]
    for i in range(len(_PIPE_PTS)-1):
        p0, p1 = _PIPE_PTS[i], _PIPE_PTS[i+1]
        mid  = (p0 + p1) / 2
        diff = p1 - p0
        length = diff.length()
        pipe = Entity(name=f'MainsPipe_{i}', model='cube',
                      position=mid,
                      scale=(length, 0.12, 0.12),
                      color=color.rgba(50, 140, 220, 200),
                      enabled=False, collider=None)
        _overlay_ents['scenario'].append(pipe)

    # RWH tank EMPTY label sphere
    rwh_empty = Entity(name='RWH_Empty', model='sphere',
                       position=B(-3.5, HY/2, -0.5),
                       scale=(0.6, 0.6, 0.6),
                       color=color.rgb(220, 50, 50),
                       enabled=False, collider=None)
    _overlay_ents['scenario'].append(rwh_empty)

    # Beehive duty reduction indicator (dim sphere in front of E panel)
    bh_dim = Entity(name='BhDuty_Indicator', model='sphere',
                    position=B(HX-0.3, 5.1, GF_Z+1.5),
                    scale=(0.5, 0.5, 0.5),
                    color=color.rgba(255, 160, 30, 180),
                    enabled=False, collider=None)
    _overlay_ents['scenario'].append(bh_dim)


# ══════════════════════════════════════════════════════════════════════════════
# 12.  ROOM LOOKUP TABLE
# ══════════════════════════════════════════════════════════════════════════════
ROOMS = [
    (0,    CX1,  0,   HY,  GF_Z, 'GARAGE  28 m²'),
    (CX1,  HX,   CY1, HY,  GF_Z, 'KITCHEN + DINING  32 m²'),
    (CX1,  CX2,  3.2, 6.8, GF_Z, 'STAIR + LIFT CORE'),
    (CX2,  HX,   0,   3.5, GF_Z, 'GUEST BEDROOM  16 m²'),
    (CX1,  HX,   3.5, CY1, GF_Z, 'LIVING ROOM  36 m²'),
    (HX,   HX+1.5, 0, 3.2, GF_Z, 'GUEST BALCONY'),
    (HX,   HX+1.5, 3.0, 7.0, GF_Z, 'VERANDAH'),
    (-CANT_W, 0, 0,   HY,  F1_Z, 'ART WORKSHOP  30 m²  (N-clerestory)'),
    (CX2,  HX,   3.0, HY,  F1_Z, 'MASTER BEDROOM  36 m²  (3.35 m ceiling)'),
    (0,    CX1,  CY1, HY,  F1_Z, 'BEDROOM 2  22 m²'),
    (CX1,  CX2,  CY1, HY,  F1_Z, 'BEDROOM 3  22 m²'),
    (CX2,  HX,   3.0, 5.5, F1_Z, 'LOUNGE  8 m²'),
    (0,    HX,   0,   HY,  F1_Z, 'FIRST FLOOR HALLWAY'),
    (HX,   HX+1.5, 0, HY,  F1_Z, 'WRAP BALCONY (E)'),
    (HX-6.1, HX, HY-6.1, HY, T_Z, 'VIEWING ROOM  37 m²  (3.35 m ceiling)'),
    (0,    6.5,  0.4, 5.5, T_Z,  'PV PERGOLA  6 kWp'),
    (0,    HX,   0,   HY,  T_Z,  'TERRACE'),
]

def get_room_label(px: float, py: float, pz: float) -> str:
    bx = px + HX/2
    by = -(pz) + HY/2
    bz = py - 1.85
    if bz < F1_Z - 0.4:
        fz = GF_Z
    elif bz < T_Z - 0.4:
        fz = F1_Z
    else:
        fz = T_Z
    for (x0, x1, y0, y1, floor_z, lbl) in ROOMS:
        if floor_z == fz and x0 <= bx <= x1 and y0 <= by <= y1:
            return lbl
    return ''


# ══════════════════════════════════════════════════════════════════════════════
# 13.  URSINA APP INIT
# ══════════════════════════════════════════════════════════════════════════════
app = Ursina(
    title='Lucknow Smart Home  ·  FPS Walkthrough',
    fullscreen=False,
    vsync=True,
    development_mode=False,
)
window.color = color.rgb(168, 210, 245)

# Two-sided rendering — fixes see-through walls from interior
from panda3d.core import Fog as PandaFog
render.setTwoSided(True)   # type: ignore[name-defined]  # injected by `from ursina import *`

# Distance fog for depth cue
_fog = PandaFog('scene_fog')
_fog.setColor(0.72, 0.82, 0.92)
_fog.setExpDensity(0.018)
render.setFog(_fog)        # type: ignore[name-defined]

# Build scene
print("Building scene…")
random.seed(42)
build_site()
print("  Site done.")
build_gf()
print("  Ground floor done.")
build_f1()
print("  First floor done.")
build_terrace()
print("  Terrace done.")
build_systems()
print("  Systems done.")

# Sky — solid colour avoids UV-mapping artefacts; sun disc billboard
Sky(color=color.rgb(168, 210, 245))

sun_disc = Entity(
    model='quad',
    texture=_make_sun_tex(),
    position=B(HX + 40, -5, GF_Z + 25),
    scale=(8, 8, 8),
    billboard=True,
    collider=None,
)

# Lighting
AmbientLight(color=color.rgba(195, 192, 185, 210))
sun = DirectionalLight()
sun.look_at(Vec3(-0.6, -0.8, -0.4))

# Point lights — correct Ursina 8.x constructor (no color kwarg)
for lpos, lcol in [
    (B(11.5, 7.0, GF_Z+2.2),  color.rgba(255, 245, 215, 140)),
    (B(12.0, 7.5, F1_Z+2.2),  color.rgba(255, 240, 210, 130)),
    (B(3.5,  5.0, T_Z+1.5),   color.rgba(210, 240, 255, 110)),
]:
    pl = PointLight()
    pl.color = lcol
    pl.position = lpos

# Player — spawned in living room centre, clear of east wall
# FPC adds its own eye-height pivot (height=2) above the base position,
# so pass only the feet position (Y=0 = floor level).
_SPAWN = B(10.5, 3.0, GF_Z)
player = FirstPersonController(
    position=_SPAWN,
    speed=5,
    jump_height=1.0,
    gravity=0.9,
)
player.rotation_y = -90   # face east (+X in Ursina)
mouse.locked = True

_SP = [
    B(STAIR_X, 4.6, GF_Z),
    B(STAIR_X, 4.6, F1_Z),
    B(STAIR_X, 4.6, T_Z),
]
_FLOOR_ZS   = [GF_Z, F1_Z, T_Z]
_FLOOR_NAMES = ['Ground Floor', 'First Floor', 'Terrace']


# ══════════════════════════════════════════════════════════════════════════════
# 14.  HUD
# ══════════════════════════════════════════════════════════════════════════════

xhair = Text('+', origin=(0,0), scale=1.5, color=color.white)

floor_lbl = Text('', origin=(0.5, 0.5), position=(0.85, 0.46),
                 scale=0.9, color=color.white)
room_lbl  = Text('', origin=(0.5, 0.5), position=(0.85, 0.41),
                 scale=0.72, color=color.rgba(230, 222, 200, 220))

hint_lbl = Text('', origin=(-0.5, 0.5), position=(-0.85, 0.30),
                scale=0.82, color=color.yellow)

sys_lbl = Text(
    '[1] Cooling  OFF\n[2] Solar  OFF\n[3] Security  OFF\n[4] Scenario OFF',
    origin=(-0.5, -0.5), position=(-0.85, -0.36),
    scale=0.72, color=color.rgba(200, 200, 200, 200),
)

# Scenario alert panel (bottom-centre, appears when [4] active)
scenario_bg = Entity(parent=camera.ui, model='quad',
                     scale=(0.70, 0.20), position=(0, -0.35),
                     color=color.rgba(8, 20, 45, 220), enabled=False)
scenario_txt = Text(
    parent=scenario_bg,
    text=(
        '⚠  SCENARIO: SECURITY + DRY DAY\n'
        'GateN + NE cameras OFFLINE → PIR compensation ACTIVE\n'
        'RWH tank EMPTY → Mains supply ON  |  Beehive drip: 40 % duty\n'
        'Adjacent cams (Drive, Front, SW) FOV expanded  |  IR beams ARMED'
    ),
    scale=0.42, origin=(0, 0), color=color.white, line_height=1.3,
)

ctrl_lbl = Text(
    'WASD move · Mouse look · Space jump · E=up · Shift+E=down · 1=cooling · 2=solar · 3=security · 4=scenario · Tab=info · F=fullscreen · Q=quit',
    origin=(0, -0.5), position=(0, -0.46),
    scale=0.50, color=color.rgba(180, 180, 180, 160),
)

# Compass rose (top-right)
compass_bg = Entity(parent=camera.ui, model='quad',
                    scale=(0.07, 0.07), position=(0.82, 0.38),
                    color=color.rgba(10, 15, 25, 160), z=-1)
compass_N = Text('N', parent=camera.ui, scale=0.6,
                 position=(0.82, 0.44), origin=(0, 0),
                 color=color.rgba(255, 80, 80, 220))
compass_E = Text('E', parent=camera.ui, scale=0.6,
                 position=(0.88, 0.38), origin=(0, 0),
                 color=color.rgba(200, 200, 200, 200))

def _update_compass():
    yaw = player.rotation_y
    compass_N.rotation_z = yaw
    compass_E.rotation_z = yaw

# Info panel — dynamically scaled for any aspect ratio
_panel_w = min(0.78, 0.78 * window.aspect_ratio / 1.78)
INFO_TEXT = """\
 LUCKNOW SMART HOME — DESIGN BRIEF
 4-BHK G+1+Terrace  ·  Plot 27.4 × 13.7 m  ·  East-facing
 ─────────────────────────────────────────────────────────
 PASSIVE COOLING                              ~14 °C delta
   Beehive terracotta evap wall (E + S faces)
   Each panel: 2.5 × 2.5 m, ~144 hollow cones in hex frame
   Monsoon bypass when RH > 65%
   Central stair void → Burjeel wind-catcher exhaust
   EC fan assist: 50–80 W per panel
 ─────────────────────────────────────────────────────────
 SOLAR + STORAGE
   15 × 400 W panels on terrace pergola = 6 kWp, 25° S tilt
   12 kWh LFP battery (2 × 6 kWh, garage)
   5 kW hybrid inverter · ~10% export net metering
   Critical loads on isolated solar microgrid
 ─────────────────────────────────────────────────────────
 RAINWATER HARVEST
   18 000 L underground RCC tank under driveway
   First-flush diverters + leaf filters
   UV+sediment filtered domestic supply
   Unfiltered drip to beehive panels
   Overflow to NE corner recharge pit
 ─────────────────────────────────────────────────────────
 TALL OCCUPANT SPEC
   All doors ≥ 2.44 m · Corridors ≥ 2.44 m
   Master + Viewing Room ceilings ≥ 3.35 m
 ─────────────────────────────────────────────────────────
 SECURITY
   7 IP cameras · PIR + IR beam-break perimeter
   30-day local NVR · all on solar microgrid
 ─────────────────────────────────────────────────────────
 SMART HOME
   Local KNX bus + Zigbee fallback
   No cloud dependency for core functions
 ─────────────────────────────────────────────────────────
 ART WORKSHOP (First Floor West)
   30 m² · North-facing clerestory monitor for diffuse light
   Drying racks · utility sink · dye/silk storage
 ─────────────────────────────────────────────────────────
               Press  Tab  to close"""

info_bg = Entity(
    parent=camera.ui, model='quad',
    scale=(_panel_w, 0.88), position=(0, 0.02),
    color=color.rgba(8, 12, 22, 220), enabled=False
)
info_txt = Text(
    parent=info_bg, text=INFO_TEXT,
    scale=0.40, origin=(0, 0), color=color.white,
    line_height=1.35,
)


# ══════════════════════════════════════════════════════════════════════════════
# 15.  OVERLAY TOGGLE HELPERS
# ══════════════════════════════════════════════════════════════════════════════
_overlay_state = {'cooling': False, 'solar': False, 'security': False, 'scenario': False}

def _toggle_overlay(key: str):
    _overlay_state[key] = not _overlay_state[key]
    for e in _overlay_ents[key]:
        e.enabled = _overlay_state[key]
    if key == 'scenario':
        scenario_bg.enabled = _overlay_state['scenario']
        # Auto-enable security overlay so cameras are visible alongside scenario
        if _overlay_state['scenario'] and not _overlay_state['security']:
            _toggle_overlay('security')
    _refresh_sys_lbl()

def _refresh_sys_lbl():
    def _s(k): return 'ON ' if _overlay_state[k] else 'OFF'
    sys_lbl.text = (f'[1] Cooling  {_s("cooling")}\n'
                    f'[2] Solar    {_s("solar")}\n'
                    f'[3] Security {_s("security")}\n'
                    f'[4] Scenario {_s("scenario")}')


# ══════════════════════════════════════════════════════════════════════════════
# 16.  UPDATE + INPUT
# ══════════════════════════════════════════════════════════════════════════════
_e_held   = False
_info_open = False

def update():
    global _e_held
    pp  = player.position
    pfy = pp.y - 1.85

    if pfy < F1_Z - 0.5:
        fz_idx = 0
    elif pfy < T_Z - 0.5:
        fz_idx = 1
    else:
        fz_idx = 2
    floor_lbl.text = _FLOOR_NAMES[fz_idx]
    room_lbl.text  = get_room_label(pp.x, pp.y, pp.z)

    _update_compass()

    stair_pos = Vec3(B(STAIR_X, STAIR_Y).x, 0, B(STAIR_X, STAIR_Y).z)
    near_stair = (Vec3(pp.x, 0, pp.z) - stair_pos).length() < 3.0

    if near_stair:
        if fz_idx == 0:
            hint_lbl.text = '[E] Go up → First Floor'
        elif fz_idx == 1:
            hint_lbl.text = '[E] Go up → Terrace   [Shift+E] Go down → Ground'
        else:
            hint_lbl.text = '[Shift+E] Go down → First Floor'

        e_now = held_keys['e']
        if e_now and not _e_held:
            if held_keys['shift']:
                target = max(0, fz_idx - 1)
            else:
                target = min(2, fz_idx + 1)
            player.position = _SP[target]
        _e_held = e_now
    else:
        hint_lbl.text = ''
        _e_held = False


def input(key):
    global _info_open
    if key == '1':
        _toggle_overlay('cooling')
    elif key == '2':
        _toggle_overlay('solar')
    elif key == '3':
        _toggle_overlay('security')
    elif key == '4':
        _toggle_overlay('scenario')
    elif key == 'tab':
        _info_open = not _info_open
        info_bg.enabled = _info_open
        mouse.locked = not _info_open
    elif key == 'f':
        window.fullscreen = not window.fullscreen
    elif key in ('escape', 'q'):
        application.quit()


# ══════════════════════════════════════════════════════════════════════════════
# 17.  RUN
# ══════════════════════════════════════════════════════════════════════════════
print("Scene ready.  Launching window…")
print()
print("  Controls:")
print("    WASD / Arrow keys  — Move")
print("    Mouse              — Look")
print("    Space              — Jump")
print("    E                  — Go up stairs")
print("    Shift + E          — Go down stairs")
print("    1                  — Toggle cooling airflow overlay")
print("    2                  — Toggle solar PV overlay")
print("    3                  — Toggle security camera cones")
print("    Tab                — Design info panel")
print("    F                  — Fullscreen")
print("    Q / Esc            — Quit")
print()

app.run()
