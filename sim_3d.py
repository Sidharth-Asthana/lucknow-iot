#!/usr/bin/env python3
"""
sim_3d.py — Lucknow Smart Home · Ursina FPS Walkthrough
─────────────────────────────────────────────────────────
Install : pip install ursina
Run     : python sim_3d.py

Controls
  WASD / Arrow keys   Move
  Mouse               Look
  Space               Jump
  E (near staircase)  Cycle floor  (GF → F1 → Terrace → GF)
  1                   Toggle cooling-airflow overlay
  2                   Toggle solar overlay
  3                   Toggle security-camera overlay
  Tab                 Building info panel
  Esc / Q             Quit
"""

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import math

# ═══════════════════════════════════════════════════════════════════════════
# 1.  CONSTANTS  (match lucknow_smart_home.py exactly)
# ═══════════════════════════════════════════════════════════════════════════
HX, HY      = 13.9, 10.0
GF_Z        = 0.0
GF_H        = 3.30
F1_Z        = 3.30
F1_H        = 3.65
T_Z         = 6.95
CANT_W      = 3.0          # westward cantilever
DRIVEWAY_W  = 7.5

TW   = 0.22   # exterior wall
TI   = 0.14   # interior wall
TS   = 0.22   # slab

CX1, CX2 = 5.9, 9.9       # E-W column lines (west→east)
CY1       = 5.0            # N-S midline

STAIR_X, STAIR_Y = (CX1 + CX2) / 2, 5.0   # stair-core centre

# ═══════════════════════════════════════════════════════════════════════════
# 2.  COLOUR PALETTE
# ═══════════════════════════════════════════════════════════════════════════
CP   = color.rgb(245, 240, 230)   # lime plaster
CF   = color.rgb(228, 216, 195)   # floor finish
CC   = color.rgb(252, 250, 246)   # ceiling
CSL  = color.rgb(195, 190, 182)   # concrete edge
CS   = color.rgb(196, 172, 128)   # Dholpur sandstone
CT   = color.rgb(182,  92,  62)   # terracotta
CTM  = color.rgb(164, 124,  68)   # timber
CGL  = color.rgba(155, 210, 255, 50)   # glazing
CGR  = color.rgb( 90, 150,  65)   # greenery
CPV  = color.rgb( 28,  58, 120)   # PV panel
CST  = color.rgb(138, 143, 150)   # steel
CGD  = color.rgb(210, 205, 190)   # driveway
CLN  = color.rgb(118, 168,  82)   # lawn
C_COOL = color.rgba(  0, 220, 255, 120)
C_SOL  = color.rgba(255, 200,   0, 120)
C_SEC  = color.rgba(255,  50,  50, 120)

# ═══════════════════════════════════════════════════════════════════════════
# 3.  COORDINATE MAPPING
#     Blender: east=+X, north=+Y, up=+Z
#     Ursina:  east=+X, up=+Y,   south=+Z
# ═══════════════════════════════════════════════════════════════════════════
def B(bx, by, bz=0.0):
    return Vec3(bx - HX / 2, bz, -(by - HY / 2))

# ═══════════════════════════════════════════════════════════════════════════
# 4.  GEOMETRY HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _box(name, pos, scale, col, coll='box'):
    return Entity(name=name, model='cube', position=pos,
                  scale=scale, color=col, collider=coll)

def EW(name, x0, x1, y, z0, z1, t=TW, col=CP, coll='box'):
    """East-West wall at constant Y."""
    cx = (x0 + x1) / 2;  sx = max(abs(x1 - x0), 0.02)
    cz = (z0 + z1) / 2;  sz = max(abs(z1 - z0), 0.02)
    return _box(name, B(cx, y, cz), (sx, sz, t), col, coll)

def NS(name, y0, y1, x, z0, z1, t=TW, col=CP, coll='box'):
    """North-South wall at constant X."""
    cy = (y0 + y1) / 2;  sy = max(abs(y1 - y0), 0.02)
    cz = (z0 + z1) / 2;  sz = max(abs(z1 - z0), 0.02)
    return _box(name, B(x, cy, cz), (t, sz, sy), col, coll)

def SLAB(name, x0, x1, y0, y1, z, t=TS, col=CSL, coll='box'):
    cx = (x0 + x1) / 2;  sx = abs(x1 - x0)
    cy = (y0 + y1) / 2;  sy = abs(y1 - y0)
    return _box(name, B(cx, cy, z + t / 2), (sx, t, sy), col, coll)

def BOX(name, bx, by, bz, sx, sy, sz, col=CP, coll=None):
    return _box(name, B(bx, by, bz + sz / 2), (sx, sz, sy), col, coll)

# ═══════════════════════════════════════════════════════════════════════════
# 5.  SCENE BUILDERS
# ═══════════════════════════════════════════════════════════════════════════
def build_site():
    # Ground
    Entity(model='plane', scale=(120, 1, 120), position=(0, -0.01, 0),
           color=CGD, collider='box')
    # Lawn (east)
    Entity(model='plane',
           scale=(DRIVEWAY_W * 2, 1, HY + 4),
           position=B(HX + DRIVEWAY_W, HY / 2, 0),
           color=CLN)
    # Driveway (west)
    Entity(model='plane',
           scale=(DRIVEWAY_W, 1, HY + 4),
           position=B(-DRIVEWAY_W / 2, HY / 2, 0),
           color=color.rgb(185, 182, 172))
    # Boundary walls (4 sides)
    wall_col = color.rgb(220, 215, 205)
    xw0, xw1 = -DRIVEWAY_W - 0.1, HX + DRIVEWAY_W + 0.1
    yw0, yw1 = -2.0, HY + 2.0
    EW('BW_S', xw0, xw1, yw0, 0, 1.8, col=wall_col)
    EW('BW_N', xw0, xw1, yw1, 0, 1.8, col=wall_col)
    NS('BW_W', yw0, yw1, xw0, 0, 1.8, col=wall_col)
    NS('BW_E', yw0, yw1, xw1, 0, 1.8, col=wall_col)
    # Gate posts
    BOX('GateL', xw0, 4.0, 0, 0.3, 0.3, 1.8, CS, 'box')
    BOX('GateR', xw0, 6.0, 0, 0.3, 0.3, 1.8, CS, 'box')
    # RWH tank wireframe (underground, visible as outline)
    BOX('RWH_Tank', -3.5, HY / 2, -1.5, 4.0, 3.0, 1.5,
        color.rgba(100, 140, 200, 40))
    # Recharge pit (NE corner)
    Entity(model='cylinder', scale=(1, 0.1, 1),
           position=B(HX + 5, HY + 1.5, 0),
           color=color.rgb(160, 140, 110))


def build_gf():
    z0, z1 = GF_Z, GF_Z + GF_H
    # Floor + ceiling (ceiling has no collider so player can reach F1)
    SLAB('GF_Floor', 0, HX, 0, HY, z0 - TS, col=CF)
    SLAB('GF_Ceil',  0, HX, 0, HY, z1,       col=CC, coll=None)

    # East face: main facade with entry door gap (Y=5.5..6.6) + foyer window
    NS('EF_S',      0.0, 3.2, HX, z0, z1)
    NS('EF_GuestD', 3.2, 3.5, HX, z0 + 2.44, z1)   # header above guest door
    # guest door gap 3.5..4.55 (no wall)
    NS('EF_Sill1',  4.55, 5.5, HX, z0, z0 + 0.9)
    NS('EF_Head1',  4.55, 5.5, HX, z0 + 2.4, z1)
    Entity(model='cube', name='EF_FoyerGl',
           position=B(HX, 5.0, z0 + 1.65),
           scale=(TW, 1.5, 0.95), color=CGL)
    # main entry gap 5.5..6.6 (no wall)
    NS('EF_EntH',   5.5, 6.6, HX, z0 + 2.44, z1)   # entry header
    NS('EF_N',      6.6, HY,  HX, z0, z1)
    NS('EF_KitSill',7.5, 9.5, HX, z0, z0 + 0.9)
    NS('EF_KitH',   7.5, 9.5, HX, z0 + 2.4, z1)
    Entity(model='cube', name='EF_KitGl',
           position=B(HX, 8.5, z0 + 1.65),
           scale=(TW, 1.5, 2.0), color=CGL)

    # South face (Y=0) — beehive panel is at X=10..12.5
    EW('SF_W',   0, CX1, 0, z0, z1)
    EW('SF_E1', CX1, 10.0, 0, z0, z1)
    EW('SF_BhH',10.0, 12.5, 0, z0 + 3.2, z1)     # header above beehive
    EW('SF_E2', 12.5, HX,   0, z0, z1)
    # Beehive S panel (orange slab face)
    BOX('Beehive_S', 11.25, 0.06, z0 + 0.7, 2.5, 0.2, 2.5, CT)

    # North face (Y=HY)
    EW('NF', 0, HX, HY, z0, z1)

    # West face (X=0) — garage roller door gap Y=0.5..4.5
    NS('WF_S', 0, 0.5, 0, z0, z1)
    NS('WF_DH',0.5, 4.5, 0, z0 + 2.5, z1)         # roller door header
    NS('WF_N', 4.5, HY, 0, z0, z1)

    # Interior: garage / living divide at X=CX1
    NS('Int_CX1_S',  0.0,  4.4, CX1, z0, z1, TI)
    NS('Int_CX1_DH', 4.4,  5.4, CX1, z0 + 2.44, z1, TI)  # door header
    NS('Int_CX1_N',  5.4, HY,  CX1, z0, z1, TI)

    # Kitchen / living divide at Y=CY1
    EW('Int_CY1_W', CX1, 7.3,  CY1, z0, z1, TI)
    EW('Int_CY1_DH',7.3, 8.5,  CY1, z0 + 2.44, z1, TI)
    EW('Int_CY1_E', 8.5, HX,   CY1, z0, z1, TI)

    # Guest bedroom walls
    EW('Int_GN', CX2, HX, 3.5, z0, z1, TI)
    NS('Int_GW', 0.0, 3.5, CX2, z0, z1, TI)

    # Stair core bounding walls
    EW('Core_S', CX1, CX2, 3.2, z0, z1, TI)
    EW('Core_N', CX1, CX2, 6.8, z0, z1, TI)

    # Verandah overhang slab (east, 1.5 m deep)
    SLAB('Verandah', HX, HX + 1.5, 3.0, 7.0, z1 - TS, col=CS, coll=None)
    BOX('Verandah_ColN', HX + 0.75, 3.2, z0, 0.25, 0.25, z1, CS, 'box')
    BOX('Verandah_ColS', HX + 0.75, 6.8, z0, 0.25, 0.25, z1, CS, 'box')

    # Guest balcony slab + railings
    SLAB('GuestBalc', HX, HX + 1.0, 0.5, 3.2, z0, col=CF)
    EW('GBalc_RS', HX, HX + 1.0, 0.5, z0, z0 + 1.0, 0.08, CS, None)
    EW('GBalc_RN', HX, HX + 1.0, 3.2, z0, z0 + 1.0, 0.08, CS, None)
    NS('GBalc_RE', 0.5, 3.2, HX + 1.0, z0, z0 + 1.0, 0.08, CS, None)

    # Staircase steps (18 risers, dog-leg in core, going north)
    rh, rd = 0.183, 0.25
    for i in range(18):
        BOX(f'StairGF_{i}',
            CX1 + 0.5 + i * rd, 4.0,
            z0 + i * rh,
            rd, 1.1, rh,
            color.rgb(215, 205, 185), 'box')

    # Elevator shaft (open box)
    NS('ElevW', 3.2, 4.8, CX2 - 0.1, z0, z1, 0.1, CST, 'box')
    NS('ElevE', 3.2, 4.8, CX2 + 1.5, z0, z1, 0.1, CST, 'box')
    EW('ElevS', CX2 - 0.1, CX2 + 1.5, 3.2, z0, z1, 0.1, CST, 'box')
    EW('ElevN', CX2 - 0.1, CX2 + 1.5, 4.8, z0, z1, 0.1, CST, 'box')

    # Beehive E panel (on inside of east face below verandah)
    BOX('Beehive_E', HX - 0.2, 5.1, z0 + 0.7, 0.2, 2.5, 2.5, CT)

    # Furniture
    BOX('Island',     11.5, 7.5, z0, 3.0, 1.2, 0.9, CTM)
    BOX('DiningTbl',  12.0, 9.0, z0, 2.4, 1.0, 0.75, CTM)
    BOX('Sofa',       11.0, 2.5, z0, 3.2, 0.9, 0.45, CTM)
    BOX('CoffeeT',    11.0, 1.5, z0, 1.2, 0.6, 0.38, CTM)
    BOX('GuestBed',   12.0, 1.8, z0, 2.0, 1.6, 0.55, CTM)
    BOX('BatteryCab',  1.2, 9.0, z0, 0.8, 0.5, 1.8, CST, 'box')
    BOX('Inverter',    2.2, 9.0, z0, 0.6, 0.4, 1.2, CST, 'box')
    BOX('NVR_Cab',    CX1 + 0.3, 3.5, z0, 0.5, 0.4, 1.6, CST, 'box')


def build_f1():
    z0, z1 = F1_Z, F1_Z + F1_H
    # Floor slabs
    SLAB('F1_Floor',      0, HX,     0, HY, z0 - TS, col=CF)
    SLAB('F1_Cant_Floor', -CANT_W, 0, 0, HY, z0 - TS, col=CF)
    SLAB('F1_Ceil',       0, HX,     0, HY, z1,       col=CC, coll=None)

    # East face
    NS('F1_EF_S',    0.0, 3.0, HX, z0, z1)
    NS('F1_EF_MidS', 3.0, 5.0, HX, z0, z0 + 0.9)
    NS('F1_EF_MidH', 3.0, 5.0, HX, z0 + 2.4, z1)
    Entity(model='cube', name='F1_EF_Gl1',
           position=B(HX, 4.0, z0 + 1.65),
           scale=(TW, 1.5, 2.0), color=CGL)
    NS('F1_EF_MidN', 5.0, 7.0, HX, z0, z0 + 0.9)
    NS('F1_EF_MidNH',5.0, 7.0, HX, z0 + 2.4, z1)
    Entity(model='cube', name='F1_EF_Gl2',
           position=B(HX, 6.0, z0 + 1.65),
           scale=(TW, 1.5, 2.0), color=CGL)
    NS('F1_EF_N',    7.0, HY,  HX, z0, z1)

    # South, north, west faces (solid with window gaps)
    EW('F1_SF', 0, HX, 0,  z0, z1)
    EW('F1_NF', 0, HX, HY, z0, z1)
    NS('F1_WF_S', 0, HY / 2 - 0.6, 0, z0, z1)
    NS('F1_WF_N', HY / 2 + 0.6, HY, 0, z0, z1)

    # Cantilever (workshop) walls
    EW('Cant_S', -CANT_W, 0, 0,  z0, z1)
    EW('Cant_N', -CANT_W, 0, HY, z0, z1)
    NS('Cant_W', 0, HY, -CANT_W, z0, z1)
    # North clerestory glazing (pops above terrace in terrace build)
    Entity(model='cube', name='Clerestory_Gl',
           position=B(-CANT_W / 2, HY + 0.05, z1 + 0.6),
           scale=(CANT_W - 0.2, 1.2, 0.08), color=CGL)

    # Interior walls F1
    NS('F1_CX1_S',  0, 4.5,  CX1, z0, z1, TI)
    NS('F1_CX1_N',  5.5, HY, CX1, z0, z1, TI)
    EW('F1_MasterS', CX2, HX, 3.0, z0, z1, TI)
    NS('F1_MasterW', 3.0, HY, CX2, z0, z1, TI)
    EW('F1_BR2_S',   0, CX1,  CY1, z0, z1, TI)
    EW('F1_BR3_S',   CX1, CX2, CY1, z0, z1, TI)
    EW('F1_LoungeS', CX2, HX,  5.5, z0, z1, TI)

    # Wrap balcony E+N+S (1.5 m wide)
    SLAB('Balc_E',  HX, HX + 1.5,  0, HY,        z0 - TS, col=CF)
    SLAB('Balc_N',  0,  HX + 1.5,  HY, HY + 1.5, z0 - TS, col=CF)
    SLAB('Balc_S',  0,  HX + 1.5, -1.5, 0,        z0 - TS, col=CF)
    NS('BalcPar_E',  0, HY, HX + 1.5, z0, z0 + 1.0, 0.12, CS, None)
    EW('BalcPar_N',  0, HX + 1.5, HY + 1.5, z0, z0 + 1.0, 0.12, CS, None)
    EW('BalcPar_S',  0, HX + 1.5, -1.5,     z0, z0 + 1.0, 0.12, CS, None)

    # Staircase steps (F1 continuation)
    rh, rd = 0.183, 0.25
    for i in range(18):
        BOX(f'StairF1_{i}',
            CX1 + 0.5 + i * rd, 4.0,
            z0 + i * rh,
            rd, 1.1, rh,
            color.rgb(215, 205, 185), 'box')

    # Furniture
    BOX('MasterBed',   12.0, 8.0, z0, 2.1, 1.8, 0.55, CTM)
    BOX('WIW_Shelf',   HX - 0.35, 3.8, z0, 0.5, 2.5, 2.2, CTM)
    BOX('BR2_Bed',     2.5, 7.5, z0, 1.8, 1.5, 0.55, CTM)
    BOX('BR3_Bed',     7.5, 7.5, z0, 1.8, 1.5, 0.55, CTM)
    BOX('LoungeS',    11.2, 4.5, z0, 2.5, 0.9, 0.45, CTM)
    BOX('WS_Table1',  -1.5, 5.0, z0, 2.5, 0.8, 0.9, CTM)
    BOX('WS_Table2',  -1.5, 2.0, z0, 2.5, 0.8, 0.9, CTM)
    BOX('WS_Sink',    -0.3, 9.2, z0, 0.6, 0.4, 0.9, CST)
    BOX('WS_DryRack', -2.5, 8.0, z0, 0.15, 1.8, 1.8, CST, 'box')


def build_terrace():
    z0 = T_Z
    SLAB('T_Slab', 0, HX, 0, HY, z0 - TS, col=CF)
    # Parapet (all 4 sides, 0.9 m)
    EW('T_ParS', 0, HX, 0,  z0, z0 + 0.9, 0.15)
    EW('T_ParN', 0, HX, HY, z0, z0 + 0.9, 0.15)
    NS('T_ParW', 0, HY, 0,  z0, z0 + 0.9, 0.15)
    NS('T_ParE', 0, HY, HX, z0, z0 + 0.9, 0.15)

    # Viewing room 6.1×6.1 m NE corner
    vz1 = z0 + 3.35
    vx0, vx1 = HX - 6.1, HX
    vy0, vy1 = HY - 6.1, HY
    EW('VR_S', vx0, vx1, vy0, z0, vz1)
    NS('VR_W', vy0, vy1, vx0, z0, vz1)
    SLAB('VR_Ceil', vx0, vx1, vy0, vy1, vz1, col=CC, coll=None)
    SLAB('VR_Floor', vx0, vx1, vy0, vy1, z0 - TS, col=CF)
    # Glazed N and E walls
    NS('VR_EGl', vy0, vy1, HX,  z0, vz1, 0.06, CGL, None)
    EW('VR_NGl', vx0, vx1, HY,  z0, vz1, 0.06, CGL, None)

    # Stair enclosure (central)
    se_x0, se_x1 = CX1 + 0.3, CX1 + 3.7
    se_y0, se_y1 = CY1 - 1.7, CY1 + 1.7
    se_h = 2.6
    EW('SE_S', se_x0, se_x1, se_y0, z0, z0 + se_h)
    EW('SE_N', se_x0, se_x1, se_y1, z0, z0 + se_h)
    NS('SE_W', se_y0, se_y1, se_x0, z0, z0 + se_h)
    NS('SE_E', se_y0, se_y1, se_x1, z0, z0 + se_h)
    SLAB('SE_Roof', se_x0, se_x1, se_y0, se_y1, z0 + se_h, col=CC)

    # Burjeel 2×2×4 m atop stair core
    bx = (se_x0 + se_x1) / 2
    by = (se_y0 + se_y1) / 2
    bz = z0 + se_h
    for dx, tx in [(-1, bx - 1), (1, bx + 1)]:
        NS(f'BJ_NS_{dx}', by - 1, by + 1, tx, bz, bz + 4.0, 0.1, CT, 'box')
    for dy, ty in [(-1, by - 1), (1, by + 1)]:
        EW(f'BJ_EW_{dy}', bx - 1, bx + 1, ty, bz, bz + 4.0, 0.1, CT, 'box')
    # Louver slats
    for i in range(8):
        frac = (i + 0.5) / 8
        BOX(f'BJ_Lou_{i}', bx, by - 1, bz + frac * 4.0, 2.0, 0.05, 0.04, CST)

    # Workshop clerestory monitor above cantilever (north-glazed box)
    cz = z0 + 0.1
    BOX('Clerestory_Box', -CANT_W / 2, HY + 0.6, cz, CANT_W - 0.1, 0.1, 1.2, CP)

    # PV pergola (SW terrace area, 6×5 m, posts at 2.4 m)
    px0, px1 = 0.4, 6.4
    py0, py1 = 0.4, 5.4
    ph = 2.4
    for ppx in [px0 + 0.2, (px0 + px1) / 2, px1 - 0.2]:
        for ppy in [py0 + 0.2, py1 - 0.2]:
            BOX(f'PVPost_{ppx:.0f}_{ppy:.0f}', ppx, ppy, z0, 0.1, 0.1, ph, CST, 'box')
    EW('PV_BeamS', px0, px1, py0, z0 + ph, z0 + ph + 0.1, 0.1, CST)
    EW('PV_BeamN', px0, px1, py1, z0 + ph, z0 + ph + 0.1, 0.1, CST)
    # 15 panels (3×5), tilted 25° south
    for ci in range(3):
        for ri in range(5):
            ppx = px0 + 0.7 + ci * 1.8
            ppy = py0 + 0.5 + ri * 0.9
            Entity(name=f'PV_{ci}_{ri}', model='cube',
                   position=B(ppx, ppy, z0 + ph + 0.15),
                   scale=(1.0, 0.03, 2.0),
                   rotation=(25, 0, 0),
                   color=CPV)

    # Raised garden beds
    for gi, (gx, gy) in enumerate([(2.5, 5.8), (2.5, 7.8),
                                    (4.5, 5.8), (4.5, 7.8)]):
        BOX(f'Bed_{gi}',  gx, gy, z0, 1.2, 3.0, 0.5,
            color.rgb(120, 80, 45), 'box')
        BOX(f'Soil_{gi}', gx, gy, z0 + 0.48, 1.2, 3.0, 0.06,
            color.rgb(80, 55, 30))
        Entity(name=f'Plant_{gi}', model='sphere',
               position=B(gx, gy, z0 + 0.8),
               scale=(0.85, 0.5, 0.85), color=CGR)


def build_systems():
    """Overlay geometry for cooling, solar, security (disabled by default)."""
    # Airflow path: east beehive → living → stair void → burjeel
    flow_pts = [
        B(HX - 0.4, 5.1, GF_Z + 1.5),
        B(CX2 + 0.5, 5.0, GF_Z + 1.5),
        B(STAIR_X,   5.0, GF_Z + 1.5),
        B(STAIR_X,   5.0, F1_Z + 1.5),
        B(STAIR_X,   5.0, T_Z  + 3.0),
    ]
    for i in range(len(flow_pts) - 1):
        p0, p1 = flow_pts[i], flow_pts[i + 1]
        mid  = (p0 + p1) / 2
        diff = p1 - p0
        length = diff.length()
        arrow = Entity(name=f'Flow_{i}', model='cube',
                       position=mid,
                       scale=(0.3, 0.3, length) if abs(diff.z) > abs(diff.y) else
                              (0.3, length, 0.3),
                       color=C_COOL, enabled=False)
        arrow.look_at(p1)

    # CCTV camera markers
    cam_pts = [
        B(xw0 := -DRIVEWAY_W - 0.2, 5.0, 1.7),
        B(-DRIVEWAY_W + 1.0, 2.0, 1.7),
        B(HX + 0.2, 5.0, GF_Z + 2.8),
        B(HX + DRIVEWAY_W - 0.5, HY + 1.5, 1.7),
        B(-DRIVEWAY_W - 0.2, 0.5, 1.7),
        B(STAIR_X, HY / 2, T_Z + 2.5),
        B(CX1 / 2, HY / 2, GF_Z + 2.8),
    ]
    for i, p in enumerate(cam_pts):
        Entity(name=f'Cam_{i}', model='cube',
               position=p, scale=(0.18, 0.14, 0.28),
               color=color.rgb(25, 25, 25), enabled=False)
        Entity(name=f'CamCone_{i}', model='sphere',
               position=p, scale=(3.0, 0.12, 3.0),
               color=C_SEC, alpha=0.25, enabled=False)


# ═══════════════════════════════════════════════════════════════════════════
# 6.  ROOM DETECTION  (used for HUD label)
# ═══════════════════════════════════════════════════════════════════════════
ROOMS = [
    # (bx0, bx1, by0, by1, floor_z, label)
    (0,    CX1,  0, HY,  GF_Z, 'GARAGE  28 m²'),
    (CX1,  HX,   CY1, HY, GF_Z, 'KITCHEN + DINING  32 m²'),
    (CX1,  CX2,  3.2, 6.8, GF_Z, 'STAIR + LIFT CORE'),
    (CX2,  HX,   0, 3.5, GF_Z, 'GUEST BEDROOM  16 m²'),
    (CX1,  HX,   3.5, CY1, GF_Z, 'LIVING ROOM  36 m²'),
    (CX1,  HX,   4.4, 5.6, GF_Z, 'FOYER'),

    (-CANT_W, 0, 0, HY,  F1_Z, 'ART WORKSHOP  30 m²  (N-clerestory light)'),
    (CX2,  HX,   3.0, HY,  F1_Z, 'MASTER BEDROOM  36 m²  (3.35 m ceiling)'),
    (0,    CX1,  CY1, HY,  F1_Z, 'BEDROOM 2  22 m²'),
    (CX1,  CX2,  CY1, HY,  F1_Z, 'BEDROOM 3  22 m²'),
    (CX2,  HX,   3.0, 5.5,  F1_Z, 'LOUNGE  8 m²'),
    (0,    HX,   0,  HY,  F1_Z, 'FIRST FLOOR HALLWAY'),

    (HX - 6.1, HX, HY - 6.1, HY, T_Z, 'VIEWING ROOM  37 m²  (3.35 m ceiling)'),
    (0, 6.5, 0.4, 5.5,  T_Z, 'PV PERGOLA  6 kWp'),
    (0,    HX,   0,  HY,  T_Z, 'TERRACE'),
]

def get_room_label(px, py, pz):
    """px,py,pz in Ursina world coords → room string."""
    bx = px + HX / 2
    by = -(pz) + HY / 2
    bz = py - 1.85       # approximate feet level
    if bz < F1_Z - 0.4:
        fz = GF_Z
    elif bz < T_Z - 0.4:
        fz = F1_Z
    else:
        fz = T_Z
    for (x0, x1, y0, y1, floor, lbl) in ROOMS:
        if floor == fz and x0 <= bx <= x1 and y0 <= by <= y1:
            return lbl
    return ''


# ═══════════════════════════════════════════════════════════════════════════
# 7.  URSINA APP
# ═══════════════════════════════════════════════════════════════════════════
app = Ursina(title='Lucknow Smart Home  |  FPS Walkthrough',
             fullscreen=False, vsync=True)
window.color = color.rgb(175, 210, 240)

# ── Build ──────────────────────────────────────────────────────────────────
build_site()
build_gf()
build_f1()
build_terrace()
build_systems()

# ── Sky + Lighting ─────────────────────────────────────────────────────────
Sky(color=color.rgb(175, 212, 242))
AmbientLight(color=color.rgba(200, 195, 188, 200))
sun = DirectionalLight()
sun.look_at(Vec3(-0.65, -0.8, -0.35))   # east morning angle

# ── Player ─────────────────────────────────────────────────────────────────
player = FirstPersonController(
    position=B(12.0, 5.2, GF_Z) + Vec3(0, 1.85, 0),
    speed=5,
    jump_height=1.0,
    gravity=0.9,
)
mouse.locked = True

# ── Stair teleport positions (Ursina coords) ───────────────────────────────
_SP = [
    B(STAIR_X, 4.6, GF_Z) + Vec3(0, 1.85, 0),   # 0 = GF landing
    B(STAIR_X, 4.6, F1_Z) + Vec3(0, 1.85, 0),   # 1 = F1 landing
    B(STAIR_X, 4.6, T_Z)  + Vec3(0, 1.85, 0),   # 2 = Terrace landing
]

# ── Overlay groups ─────────────────────────────────────────────────────────
flow_ents = [e for e in scene.entities if e.name.startswith('Flow_')]
cam_ents  = [e for e in scene.entities
             if e.name.startswith('Cam_') or e.name.startswith('CamCone_')]

overlays = dict(cooling=False, security=False)

def _toggle(key):
    overlays[key] = not overlays[key]
    group = flow_ents if key == 'cooling' else cam_ents
    for e in group:
        e.enabled = overlays[key]

# ── HUD ────────────────────────────────────────────────────────────────────
xhair = Text('+', origin=(0, 0), scale=1.6, color=color.white)

floor_lbl = Text('', origin=(0.5, 0.5), position=(0.85, 0.46),
                 scale=0.85, color=color.white)
room_lbl  = Text('', origin=(0.5, 0.5), position=(0.85, 0.41),
                 scale=0.72, color=color.rgba(220, 215, 200, 220))
hint_lbl  = Text('', origin=(-0.5, 0.5), position=(-0.85, 0.28),
                 scale=0.8, color=color.yellow)

sys_lbl = Text(
    '[1] Cooling  OFF\n[2] Solar info\n[3] Security OFF',
    origin=(-0.5, -0.5), position=(-0.85, -0.36),
    scale=0.72, color=color.rgba(200, 200, 200, 200),
)

ctrl_lbl = Text(
    'WASD move · Mouse look · Space jump · E=stairs · Tab=info · Q=quit',
    origin=(0, -0.5), position=(0, -0.46),
    scale=0.6, color=color.rgba(180, 180, 180, 160),
)

# Info panel
info_bg = Entity(parent=camera.ui, model='quad',
                 scale=(0.7, 0.78), position=(0, 0.02),
                 color=color.rgba(8, 12, 22, 215), enabled=False)
info_txt = Text(
    parent=info_bg,
    text=(
        'LUCKNOW SMART HOME — DESIGN BRIEF\n'
        '4-BHK G+1+Terrace  •  Plot 27.4 × 13.7 m\n'
        '────────────────────────────────────────\n'
        'PASSIVE COOLING\n'
        '  Beehive terracotta evap wall (E + S faces)\n'
        '  Each panel: 2.5 × 2.5 m, ~144 hollow cones\n'
        '  Cooling delta: ~14 °C  (45 → ~31 °C inlet)\n'
        '  Monsoon bypass when RH > 65 %\n'
        '  Burjeel wind-catcher on terrace as exhaust\n'
        '────────────────────────────────────────\n'
        'SOLAR + STORAGE\n'
        '  15 × 400 W panels = 6 kWp, 25° S tilt\n'
        '  12 kWh LFP battery  •  5 kW hybrid inverter\n'
        '  Critical loads on isolated solar microgrid\n'
        '────────────────────────────────────────\n'
        'RAINWATER HARVEST\n'
        '  18 000 L underground RCC tank (under driveway)\n'
        '  First-flush diverters + leaf filters\n'
        '  UV+sediment domestic  •  unfiltered beehive drip\n'
        '  Overflow to NE-corner recharge pit\n'
        '────────────────────────────────────────\n'
        'SECURITY\n'
        '  7 IP cameras  •  PIR + IR beam-break perimeter\n'
        '  30-day local NVR  •  on solar microgrid\n'
        '────────────────────────────────────────\n'
        'SMART HOME\n'
        '  Local KNX bus + Zigbee fallback\n'
        '  No cloud dependency for core functions\n'
        '────────────────────────────────────────\n'
        'TALL-OCCUPANT SPEC\n'
        '  All doors ≥ 2.44 m  •  Corridors ≥ 2.44 m\n'
        '  Master + Viewing Room ceilings ≥ 3.35 m\n'
        '────────────────────────────────────────\n'
        '              Press Tab to close'
    ),
    scale=0.5, origin=(0, 0), color=color.white,
)


# ═══════════════════════════════════════════════════════════════════════════
# 8.  UPDATE + INPUT
# ═══════════════════════════════════════════════════════════════════════════
_FLOOR_NAMES = {GF_Z: 'Ground Floor', F1_Z: 'First Floor', T_Z: 'Terrace'}
_e_held = False

def update():
    global _e_held
    pp = player.position
    py_feet = pp.y - 1.85

    # Floor + room labels
    if py_feet < F1_Z - 0.5:
        fz, fl = GF_Z, 'Ground Floor'
    elif py_feet < T_Z - 0.5:
        fz, fl = F1_Z, 'First Floor'
    else:
        fz, fl = T_Z, 'Terrace'
    floor_lbl.text = fl
    room_lbl.text  = get_room_label(pp.x, pp.y, pp.z)

    # Stair proximity
    near_stair = (Vec3(pp.x, 0, pp.z) -
                  Vec3(B(STAIR_X, STAIR_Y).x, 0,
                       B(STAIR_X, STAIR_Y).z)).length() < 2.8

    if near_stair:
        if fz == GF_Z:
            hint_lbl.text = '[E]  Go up  →  First Floor'
            dest = _SP[1]
        elif fz == F1_Z:
            hint_lbl.text = '[E]  Go up  →  Terrace        [Shift+E]  Go down'
            dest = _SP[2]
        else:
            hint_lbl.text = '[E]  Go down  →  First Floor'
            dest = _SP[1]

        e_now = held_keys['e']
        if e_now and not _e_held:
            if fz == T_Z or (fz == F1_Z and held_keys['shift']):
                player.position = _SP[max(0, [GF_Z,F1_Z,T_Z].index(fz)-1)]
            else:
                player.position = dest
        _e_held = e_now
    else:
        hint_lbl.text = ''
        _e_held = False


def input(key):
    if key == '1':
        _toggle('cooling')
        state = 'ON ' if overlays['cooling'] else 'OFF'
        sys_lbl.text = (f'[1] Cooling  {state}\n'
                        '[2] Solar info\n'
                        f'[3] Security {"ON " if overlays["security"] else "OFF"}')
    elif key == '2':
        print('Solar: 6 kWp  |  Est. 22–25 kWh/day  |  Battery: 12 kWh LFP')
    elif key == '3':
        _toggle('security')
        state = 'ON ' if overlays['security'] else 'OFF'
        sys_lbl.text = (f'[1] Cooling  {"ON " if overlays["cooling"] else "OFF"}\n'
                        '[2] Solar info\n'
                        f'[3] Security {state}')
    elif key == 'tab':
        info_bg.enabled = not info_bg.enabled
        mouse.locked = not info_bg.enabled
    elif key in ('escape', 'q'):
        application.quit()


app.run()
