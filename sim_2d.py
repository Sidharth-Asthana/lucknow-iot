#!/usr/bin/env python3
"""
sim_2d.py — Lucknow Smart Home  |  Pygame 2D Interactive Floor-Plan Viewer
───────────────────────────────────────────────────────────────────────────
Install : pip install pygame pygame_gui pillow
Run     : python sim_2d.py

Controls
  GF / F1 / T  tabs  Switch floor
  1            Toggle cooling airflow animation
  2            Solar dashboard
  3            Toggle security camera cones
  R            System reset
  Click room   Show room detail card
  Esc          Quit
"""

import sys, math, time, os
import pygame
import pygame_gui

# ── optional: load the rendered plan PNGs as backgrounds ──────────────────
RENDER_DIR  = os.path.join(os.path.dirname(__file__), 'renders')
PLAN_IMGS   = {
    'GF': os.path.join(RENDER_DIR, '05_CAM_GroundPlan_Top.png'),
    'F1': os.path.join(RENDER_DIR, '06_CAM_FirstPlan_Top.png'),
    'T':  os.path.join(RENDER_DIR, '07_CAM_TerracePlan_Top.png'),
}

# ── Window ────────────────────────────────────────────────────────────────
W, H        = 1400, 880
SIDEBAR_W   = 320
CANVAS_W    = W - SIDEBAR_W
CANVAS_H    = H
FPS         = 60

# ── Palette ───────────────────────────────────────────────────────────────
BG          = (245, 242, 236)
SIDEBAR_BG  = (28,  32,  42)
WALL        = (60,  55,  50)
SLAB        = (215, 208, 195)
ROOM_FILL   = (235, 228, 215)
ROOM_HOVER  = (220, 210, 190)
ROOM_SEL    = (200, 185, 160)
LABEL       = (50,  45,  40)
WHITE       = (255, 255, 255)
SAND        = (196, 172, 128)
TERRA       = (182,  92,  62)
TIMBER      = (164, 124,  68)
GLASS_C     = (155, 210, 255)
GREEN       = ( 90, 150,  65)
SOLAR_C     = ( 28,  58, 120)
CYAN        = (  0, 210, 240)
GOLD        = (255, 200,   0)
RED_SEC     = (220,  50,  50)
GREY        = (160, 160, 160)
ACCENT      = ( 80, 130, 200)

# ── Building constants (metres) ───────────────────────────────────────────
HX, HY      = 13.9, 10.0
CX1, CX2    = 5.9,   9.9
CY1         = 5.0
CANT_W      = 3.0
DW_M        = 7.5    # driveway width west

# ── Plan-view scale: metres → pixels ─────────────────────────────────────
# We fit the extended plan (with cantilever west + lawn east) into CANVAS_W
PLOT_W_M    = DW_M + CANT_W + HX + 6.0   # total E-W metres in view
PLOT_H_M    = HY + 4.0                    # total N-S metres
SCALE       = min(CANVAS_W / PLOT_W_M, CANVAS_H / PLOT_H_M) * 0.88
MARGIN_X    = (CANVAS_W - PLOT_W_M * SCALE) / 2
MARGIN_Y    = (CANVAS_H - PLOT_H_M * SCALE) / 2

# Origin: SW corner of the plot in screen coords
# Blender (0,0) = house SW corner; plot goes west by DW_M+CANT_W and south by 2m
OX = MARGIN_X + (DW_M + CANT_W) * SCALE   # screen X for Blender x=0
OY = MARGIN_Y + (PLOT_H_M - 2.0) * SCALE  # screen Y for Blender y=0 (south, Y grows DOWN)

def s(bx, by):
    """Blender metres → screen pixels (Y inverted: north=up)."""
    return (int(OX + bx * SCALE), int(OY - by * SCALE))

def sr(bx, by, w_m, h_m):
    """Rectangle from Blender bottom-left (bx,by) with size w_m×h_m."""
    sx, sy = s(bx, by + h_m)
    return pygame.Rect(sx, sy, int(w_m * SCALE), int(h_m * SCALE))

# ── Room definitions ──────────────────────────────────────────────────────
# Each: (id, floor, bx, by, w, h, label, short_label, detail_text)
ROOMS = [
    # Ground Floor
    ('garage',   'GF', 0,    0,    CX1, HY,
     'Garage + Workshop Bay',  'GARAGE',
     '28 m²  |  2-car + workshop bay\nRoller door (W)  4.5×2.5 m\n'
     'Battery: 2×6 kWh LFP\n5 kW hybrid inverter\nNVR + KNX panel'),
    ('kitchen',  'GF', CX1,  CY1,  HX-CX1, HY-CY1,
     'Kitchen + Dining',       'KITCHEN\n+DINING',
     '32 m²  |  Open plan\nIsland 3.0×1.2 m\nDining 8-seat\nE window 3×1.8 m'),
    ('living',   'GF', CX1,  3.5,  HX-CX1, CY1-3.5,
     'Living Room',            'LIVING',
     '36 m²  |  Sectional sofa\nDouble-height void above stair core\nE verandah access'),
    ('guest',    'GF', CX2,  0,    HX-CX2, 3.5,
     'Guest Bedroom + Ensuite','GUEST\n+BATH',
     '16 m²  |  En-suite\nEast private balcony 3×2 m\nDoor: 2.44 m clearance'),
    ('foyer',    'GF', CX2,  3.5,  HX-CX2, 2.0,
     'Foyer / Entry Vestibule','FOYER',
     '8 m²  |  E main entry\nSecondary door from garage\nShoe niche'),
    ('powder',   'GF', CX1,  0,    1.5, 3.0,
     'Powder Bath',            'PWD',
     '3 m²'),
    ('core_gf',  'GF', CX1,  3.2,  CX2-CX1, 3.6,
     'Stair + Lift Core',      'CORE',
     '12 m²  |  Lift 1.5×1.6 m\n18-riser dog-leg stair\nDouble-height void'),
    # First Floor
    ('master',   'F1', CX2,  3.0,  HX-CX2, HY-3.0,
     'Master Bedroom + WIW',   'MASTER\n+WIW',
     '36 m²  |  3.35 m clear ceiling\nWalk-in wardrobe 6 m²\nEast + wrap balcony'),
    ('mbath',    'F1', CX2,  0,    HX-CX2, 3.0,
     'Master En-suite',        'M.BATH',
     '8 m²  |  Radiant floor heat (winter)'),
    ('br2',      'F1', 0,    CY1,  CX1, HY-CY1,
     'Bedroom 2 + Ensuite',    'BR 2',
     '22 m²  |  En-suite 5 m²\nN view + wrap balcony'),
    ('br3',      'F1', CX1,  CY1,  CX2-CX1, HY-CY1,
     'Bedroom 3 + Ensuite',    'BR 3',
     '22 m²  |  En-suite 5 m²\nNorth balcony'),
    ('lounge',   'F1', CX2,  3.0,  HX-CX2, 2.5,
     'Small Lounge',           'LOUNGE',
     '8 m²  |  S balcony access'),
    ('hall_f1',  'F1', CX1,  3.2,  CX2-CX1, 2.6,
     'Hallway + Lift Core',    'HALL',
     '9 m²  |  2.44 m headroom\nLift landing'),
    ('workshop', 'F1', -CANT_W, 0, CANT_W, HY,
     'Silk Art Workshop',      'ART\nWORKSHOP',
     '30 m²  |  North clerestory glazing\n3×1.2 m skylight above parapet\n'
     'Utility sink (N)  Drying racks (S)\nDye/silk storage (W)'),
    # Terrace
    ('viewing',  'T',  HX-6.1, HY-6.1, 6.1, 6.1,
     'Viewing Room',           'VIEWING\nROOM',
     '37 m²  |  3.35 m clear ceiling\nN + E double-glazed low-e\nDeep S overhang'),
    ('garden',   'T',  1.0,  5.0,  5.0, 4.5,
     'Rooftop Garden',         'ROOF\nGARDEN',
     '50 m²  |  4 raised beds\nDrip-irrigated from RWH tank\nWaterproof membrane'),
    ('pv_area',  'T',  0.4,  0.4,  6.0, 5.0,
     'PV Pergola',             'PV\nPERGOLA',
     '6 kWp  |  15 × 400 W panels\n25° south tilt  |  Garden shade'),
    ('burjeel_a','T',  5.5,  3.3,  4.0, 3.4,
     'Burjeel Wind Catcher',   'BURJEEL',
     '2×2×4 m  |  Atop stair core\nPassive stack exhaust\nLouver intakes all 4 faces'),
    ('stair_t',  'T',  CX1, CY1-1.7, CX2-CX1, 3.4,
     'Stair + Lift Landing',   'STAIR\nLANDING',
     'Weatherproof enclosure\nElevator + dog-leg stair'),
]

# ── Airflow animation path (Blender coords) ────────────────────────────────
FLOW_PATH_GF = [
    (HX, 5.1), (CX2, 5.0), (STAIR_X := (CX1+CX2)/2, 5.0)
]
FLOW_PATH_UP = [(STAIR_X, 5.0)]   # vertical, shown as a pulsing ring in plan

# ── Security camera cone definitions (bx, by, angle_deg, fov_deg, label) ──
CAMS = [
    (-DW_M-0.1,  5.0,   0,  90, 'GateN'),    # 0
    (-DW_M+1.0,  2.0,  45,  80, 'Drive'),    # 1
    (HX+0.1,     5.0, 180,  90, 'Front'),    # 2
    (HX+6,       HY+1, 225, 80, 'NE'),       # 3
    (-DW_M-0.1,  0.5,  45,  80, 'SW'),       # 4
    (STAIR_X,    5.0, 270,  80, 'Terrace'),  # 5
    (CX1/2,      5.0, 180,  90, 'Garage'),   # 6
]

# ── PIR sensor positions (bx, by, label) ──────────────────────────────────
PIRS = [
    (-DW_M-0.1, 5.0,   'Gate'),
    (HX+5.5,    HY+1.0,'NE'),
    (-DW_M-0.1, 0.5,   'SW'),
    (HX+0.1,    5.0,   'FrontDoor'),
    (CX2+1.0,   4.0,   'Living'),
    (10.0,      7.5,   'Dining'),
    (STAIR_X,   5.0,   'Terrace'),
    (CX1/2,     5.0,   'Garage'),
]

# ── Scenario Engine ────────────────────────────────────────────────────────
# Security scenario: cameras 0 (GateN) and 3 (NE) go offline
SEC_FAIL_CAMS    = {0, 3}
# PIRs that compensate: gate area (0), NE corner (1), perimeter (2)
SEC_ELEVATE_PIRS = {0, 1, 2, 3}
# Cameras that expand FOV to compensate: Drive (1), Front (2), SW (4)
SEC_EXPAND_CAMS  = {1, 2, 4}

# RWH / water scenario
RWH_MAINS_PATH = [                   # Blender coords of mains reroute path
    (-DW_M, 5.0), (-CANT_W-0.1, 5.0), (-2.5, 5.0), (0.1, 5.0),
]
BEEHIVE_DUTY_REDUCED = 0.40          # 40 % duty when on mains

_SCENARIO_LOG: list[str] = []        # adaptive response log messages

# ═══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def draw_rect_blender(surf, col, bx, by, bw, bh, border=0):
    r = sr(bx, by, bw, bh)
    if border:
        pygame.draw.rect(surf, col, r, border)
    else:
        pygame.draw.rect(surf, col, r)
    return r

def draw_wall(surf, bx0, by0, bx1, by1, thick=0.20):
    """Draw a wall segment as a thick line."""
    p0 = s(bx0, by0)
    p1 = s(bx1, by1)
    t  = max(2, int(thick * SCALE))
    pygame.draw.line(surf, WALL, p0, p1, t)

def draw_arrow(surf, col, p0, p1, head=10):
    pygame.draw.line(surf, col, p0, p1, 3)
    dx, dy = p1[0]-p0[0], p1[1]-p0[1]
    ln = max(math.hypot(dx, dy), 1)
    dx, dy = dx/ln, dy/ln
    left  = (p1[0] - head*(dx+dy*0.5), p1[1] - head*(dy-dx*0.5))
    right = (p1[0] - head*(dx-dy*0.5), p1[1] - head*(dy+dx*0.5))
    pygame.draw.polygon(surf, col, [p1, left, right])

def draw_cam_cone(surf, bx, by, angle_deg, fov_deg, label='',
                  cone_col=None, failed=False):
    """Draw a camera FOV cone. failed=True draws it grey with an X."""
    cx, cy = s(bx, by)
    rad    = int(80 * SCALE / 10)
    fov    = math.radians(fov_deg / 2)
    base   = math.radians(-angle_deg)
    pts = [(cx, cy)]
    for i in range(12):
        a = base - fov + (2 * fov * i / 11)
        pts.append((cx + int(rad * math.cos(a)),
                    cy + int(rad * math.sin(a))))
    fill_col = cone_col if cone_col else RED_SEC
    s_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    if failed:
        pygame.draw.polygon(s_surf, (120, 120, 120, 35), pts)
        pygame.draw.polygon(s_surf, (120, 120, 120, 100), pts, 2)
    else:
        pygame.draw.polygon(s_surf, (*fill_col, 60), pts)
        pygame.draw.polygon(s_surf, (*fill_col, 160), pts, 2)
    surf.blit(s_surf, (0, 0))
    dot_col = (110, 110, 110) if failed else fill_col
    pygame.draw.circle(surf, dot_col, (cx, cy), 5)
    if failed:
        pygame.draw.line(surf, (200, 40, 40), (cx-7, cy-7), (cx+7, cy+7), 3)
        pygame.draw.line(surf, (200, 40, 40), (cx+7, cy-7), (cx-7, cy+7), 3)


def draw_scenario_security(surf, font_sm, t, floor):
    """Overlay: 2 cameras offline, PIR compensation, expanded adjacent FOVs."""
    global _SCENARIO_LOG

    # Draw all cams — failed ones grey+X, compensating ones with expanded FOV
    for i, (bx, by, ang, fov, lbl) in enumerate(CAMS):
        if i in SEC_FAIL_CAMS:
            draw_cam_cone(surf, bx, by, ang, fov, lbl, failed=True)
            # 'OFFLINE' label
            cx, cy = s(bx, by)
            tsurf = font_sm.render(f'{lbl}: OFFLINE', True, (210, 50, 50))
            surf.blit(tsurf, (cx + 10, cy - 14))
        elif i in SEC_EXPAND_CAMS:
            # Expanded FOV compensation
            draw_cam_cone(surf, bx, by, ang, min(fov + 25, 120), lbl,
                          cone_col=(0, 200, 220))
            cx, cy = s(bx, by)
            tsurf = font_sm.render(f'{lbl}: ↑FOV', True, CYAN)
            surf.blit(tsurf, (cx + 10, cy + 2))

    # PIR elevated-sensitivity pulse rings
    pulse = 0.5 + 0.5 * math.sin(t * 6)
    for pi in SEC_ELEVATE_PIRS:
        if pi < len(PIRS):
            px, py, plbl = PIRS[pi]
            cx, cy = s(px, py)
            r_outer = int((14 + 9 * pulse) * SCALE / 10)
            r_inner = max(5, int(7 * SCALE / 10))
            pygame.draw.circle(surf, (255, 130, 20), (cx, cy), max(3, r_outer), 2)
            pygame.draw.circle(surf, (255, 130, 20), (cx, cy), r_inner)
            tsurf = font_sm.render(f'PIR↑', True, (255, 140, 20))
            surf.blit(tsurf, (cx + r_inner + 2, cy - 7))

    # Blind-zone hatching (only show on GF plan)
    if floor == 'GF':
        for zone_bx, zone_by, zone_r, label in [
            (-DW_M-0.1, 5.0, 1.8, 'BLIND'),
            (HX+5.5,    HY+1.0, 1.8, 'BLIND'),
        ]:
            zx, zy = s(zone_bx, zone_by)
            zr = int(zone_r * SCALE)
            h_surf = pygame.Surface((zr*2, zr*2), pygame.SRCALPHA)
            # Hatch fill
            for hx in range(0, zr*2, 6):
                pygame.draw.line(h_surf, (200, 30, 30, 70), (hx, 0), (0, hx))
                pygame.draw.line(h_surf, (200, 30, 30, 70), (zr*2, hx), (hx, zr*2))
            surf.blit(h_surf, (zx - zr, zy - zr))
            pygame.draw.circle(surf, (200, 30, 30), (zx, zy), zr, 2)
            tsurf = font_sm.render(label, True, (200, 30, 30))
            surf.blit(tsurf, tsurf.get_rect(center=(zx, zy)))

    # Alert banner
    alpha = int(200 + 40 * math.sin(t * 2.5))
    banner = pygame.Surface((CANVAS_W, 28), pygame.SRCALPHA)
    banner.fill((160, 20, 20, alpha))
    surf.blit(banner, (0, 4))
    msg = '⚠  SECURITY ALERT  |  GateN + NE CAMERAS OFFLINE  |  PIR COMPENSATION ACTIVE  |  ALERT THRESHOLD ELEVATED'
    tsurf = font_sm.render(msg, True, WHITE)
    surf.blit(tsurf, tsurf.get_rect(center=(CANVAS_W // 2, 18)))

    # IR beam-break reminder (east + west perimeter)
    for pbx, pby in [(HX+1.0, 2.0), (HX+1.0, 8.0), (-DW_M+0.2, 2.0), (-DW_M+0.2, 8.0)]:
        px_, py_ = s(pbx, pby)
        pygame.draw.rect(surf, (255, 200, 0), pygame.Rect(px_-4, py_-4, 8, 8))


def draw_scenario_rwh(surf, font_sm, t, floor):
    """Overlay: RWH tank empty — mains reroute, reduced beehive duty."""
    if floor != 'GF':
        return

    # Animated mains supply flow path (blue arrows)
    flow_col = (60, 150, 220)
    phase = (t * 0.6) % 1.0
    path = RWH_MAINS_PATH
    for i in range(len(path) - 1):
        p0 = s(*path[i])
        p1 = s(*path[i + 1])
        draw_arrow(surf, flow_col, p0, p1)

    # Animated flow particles along path
    for k in range(5):
        frac = ((phase + k / 5) % 1.0)
        seg = int(frac * (len(path) - 1))
        f2  = (frac * (len(path) - 1)) % 1.0
        if seg < len(path) - 1:
            x_p = path[seg][0] + f2 * (path[seg+1][0] - path[seg][0])
            y_p = path[seg][1] + f2 * (path[seg+1][1] - path[seg][1])
            px_, py_ = s(x_p, y_p)
            pygame.draw.circle(surf, flow_col, (px_, py_), max(3, int(0.2 * SCALE)))

    # RWH tank empty indicator
    tx, ty = s(-3.5, 5.0)
    pygame.draw.circle(surf, (220, 50, 50), (tx, ty), 14, 3)
    tsurf = font_sm.render('RWH EMPTY', True, (220, 50, 50))
    surf.blit(tsurf, (tx + 16, ty - 7))

    # Mains entry marker
    mx_, my_ = s(-DW_M, 5.0)
    pygame.draw.circle(surf, flow_col, (mx_, my_), 8)
    tsurf = font_sm.render('MAINS →', True, flow_col)
    surf.blit(tsurf, (mx_ + 10, my_ - 7))

    # Solenoid valve state labels
    sv_e_x, sv_e_y = s(-2.5, 5.0)
    pygame.draw.circle(surf, flow_col, (sv_e_x, sv_e_y), 6)
    tsurf = font_sm.render('SV: MAINS OPEN', True, flow_col)
    surf.blit(tsurf, (sv_e_x + 8, sv_e_y - 6))

    # Beehive panels — dim overlay showing 40 % duty
    for bx_bh, by_bh, bw, bh_h in [
        (HX-0.25, 3.7, 0.25, 2.5),   # east panel
        (10.0, -0.25, 2.5, 0.25),     # south panel
    ]:
        rect = sr(bx_bh, by_bh, bw, bh_h)
        dim = pygame.Surface((rect.width or 4, rect.height or 4), pygame.SRCALPHA)
        dim.fill((140, 140, 140, 155))
        surf.blit(dim, rect.topleft)
        tsurf = font_sm.render(f'{int(BEEHIVE_DUTY_REDUCED*100)}%', True, WHITE)
        surf.blit(tsurf, tsurf.get_rect(center=rect.center))

    # Water budget bar
    bar_x, bar_y = 16, 38
    bar_w, bar_h = 200, 14
    pygame.draw.rect(surf, (40, 50, 70), pygame.Rect(bar_x, bar_y, bar_w, bar_h))
    fill_w = int(bar_w * BEEHIVE_DUTY_REDUCED)
    pygame.draw.rect(surf, flow_col, pygame.Rect(bar_x, bar_y, fill_w, bar_h))
    tsurf = font_sm.render(f'Beehive duty: {int(BEEHIVE_DUTY_REDUCED*100)} %  (mains conservation)', True, WHITE)
    surf.blit(tsurf, (bar_x, bar_y - 14))

    # Info banner
    banner = pygame.Surface((CANVAS_W, 28), pygame.SRCALPHA)
    banner.fill((20, 60, 130, 200))
    surf.blit(banner, (0, 4))
    msg = '💧  RWH TANK EMPTY  |  MAINS SUPPLY ACTIVE  |  BEEHIVE DRIP REDUCED TO 40 %  |  SOIL SENSORS MONITORING'
    tsurf = font_sm.render(msg, True, WHITE)
    surf.blit(tsurf, tsurf.get_rect(center=(CANVAS_W // 2, 18)))


# ═══════════════════════════════════════════════════════════════════════════
# FLOOR DRAWERS
# ═══════════════════════════════════════════════════════════════════════════
def draw_gf(surf, font_sm, font_md, hover_id, sel_id):
    # Site background
    draw_rect_blender(surf, (210, 205, 190), -DW_M-CANT_W, -2, DW_M+CANT_W, HY+4)
    draw_rect_blender(surf, (118, 168, 82),  HX, -2, 6.0, HY+4)
    draw_rect_blender(surf, (185, 182, 172), -DW_M-CANT_W, -2, DW_M, HY+4)

    # House footprint
    draw_rect_blender(surf, ROOM_FILL, 0, 0, HX, HY)

    # Room fills
    rooms_gf = [(r, sr(r[2], r[3], r[4], r[5]))
                for r in ROOMS if r[1] == 'GF']
    for r, rect in rooms_gf:
        col = ROOM_SEL if r[0] == sel_id else \
              ROOM_HOVER if r[0] == hover_id else ROOM_FILL
        pygame.draw.rect(surf, col, rect)

    # Walls (exterior)
    tw = 0.22
    for (bx0,by0,bx1,by1) in [
        (0,0,HX,0), (0,HY,HX,HY),
        (0,0,0,HY), (HX,0,HX,HY),
    ]:
        draw_wall(surf, bx0,by0,bx1,by1, tw)

    # Interior walls
    draw_wall(surf, CX1, 0, CX1, HY, 0.14)
    draw_wall(surf, CX1, CY1, HX, CY1, 0.14)
    draw_wall(surf, CX2, 0, CX2, 3.5, 0.14)
    draw_wall(surf, CX1, 3.5, HX, 3.5, 0.14)
    draw_wall(surf, CX1, 3.2, CX2, 3.2, 0.12)
    draw_wall(surf, CX1, 6.8, CX2, 6.8, 0.12)

    # Verandah (dashed)
    for i in range(8):
        x0 = HX + i*0.3
        col_v = SAND if i%2==0 else BG
        draw_rect_blender(surf, col_v, x0, 3.0, 0.15, 4.0)
    draw_wall(surf, HX, 3.0, HX+1.5, 3.0, 0.1)
    draw_wall(surf, HX, 7.0, HX+1.5, 7.0, 0.1)

    # Guest balcony
    draw_rect_blender(surf, (205, 198, 185), HX, 0.5, 1.0, 2.7)
    draw_wall(surf, HX, 0.5, HX+1.0, 0.5, 0.1)
    draw_wall(surf, HX, 3.2, HX+1.0, 3.2, 0.1)
    draw_wall(surf, HX+1.0, 0.5, HX+1.0, 3.2, 0.1)

    # Beehive panels
    draw_rect_blender(surf, TERRA, HX-0.2, 0.7+3.7, 0.2, 2.5)   # east
    draw_rect_blender(surf, TERRA, 10.0, -0.2, 2.5, 0.2)          # south

    # Furniture
    draw_rect_blender(surf, TIMBER, 10.0, 7.0, 3.0, 1.2)   # island
    draw_rect_blender(surf, TIMBER, 10.5, 8.5, 2.4, 1.0)   # dining
    draw_rect_blender(surf, TIMBER,  9.5, 2.0, 3.2, 0.9)   # sofa
    draw_rect_blender(surf, TIMBER, 11.0, 1.0, 2.0, 1.6)   # guest bed

    # Labels
    for r, rect in rooms_gf:
        cx_r, cy_r = rect.centerx, rect.centery
        for i, line in enumerate(r[7].split('\n')):
            surf_t = font_sm.render(line, True, LABEL)
            surf.blit(surf_t, surf_t.get_rect(
                center=(cx_r, cy_r - 7 + i*14)))

    return rooms_gf


def draw_f1(surf, font_sm, font_md, hover_id, sel_id):
    # Cantilever background
    draw_rect_blender(surf, SLAB, -CANT_W, 0, CANT_W, HY)
    draw_rect_blender(surf, ROOM_FILL, 0, 0, HX, HY)
    # Wrap balcony
    draw_rect_blender(surf, (205,198,185), HX, 0, 1.5, HY)
    draw_rect_blender(surf, (205,198,185), -1.5, -1.5, HX+3.0, 1.5)
    draw_rect_blender(surf, (205,198,185), -1.5, HY, HX+3.0, 1.5)

    rooms_f1 = [(r, sr(r[2], r[3], r[4], r[5]))
                for r in ROOMS if r[1] == 'F1']
    for r, rect in rooms_f1:
        col = ROOM_SEL if r[0] == sel_id else \
              ROOM_HOVER if r[0] == hover_id else ROOM_FILL
        pygame.draw.rect(surf, col, rect)

    # Exterior walls
    tw = 0.22
    for (bx0,by0,bx1,by1) in [
        (0,0,HX,0),(0,HY,HX,HY),(HX,0,HX,HY),
        (-CANT_W,0,-CANT_W,HY),(-CANT_W,0,0,0),(-CANT_W,HY,0,HY),
    ]:
        draw_wall(surf, bx0,by0,bx1,by1, tw)
    # Interior walls
    draw_wall(surf, CX1, 0,  CX1, HY, 0.14)
    draw_wall(surf, CX2, 3.0,CX2, HY, 0.14)
    draw_wall(surf, CX1, CY1,CX2, CY1, 0.14)
    draw_wall(surf, CX2, 3.0,HX,  3.0, 0.14)
    draw_wall(surf, CX2, 5.5,HX,  5.5, 0.14)
    # Balcony parapets
    draw_wall(surf, HX, -1.5, HX+1.5, -1.5, 0.12)
    draw_wall(surf, HX+1.5, -1.5, HX+1.5, HY+1.5, 0.12)
    draw_wall(surf, HX, HY+1.5, HX+1.5, HY+1.5, 0.12)

    # Workshop fixtures
    draw_rect_blender(surf, TIMBER, -2.5, 4.2, 2.5, 0.8)
    draw_rect_blender(surf, TIMBER, -2.5, 1.2, 2.5, 0.8)
    # Beds
    draw_rect_blender(surf, TIMBER, 11.2, 7.2, 2.1, 1.8)
    draw_rect_blender(surf, TIMBER,  1.5, 6.5, 1.8, 1.5)
    draw_rect_blender(surf, TIMBER,  6.5, 6.5, 1.8, 1.5)

    # Clerestory monitor
    draw_rect_blender(surf, GLASS_C, -CANT_W+0.1, HY, CANT_W-0.2, 0.4)
    draw_wall(surf, -CANT_W+0.1, HY+0.4, -0.1, HY+0.4, 0.08)

    for r, rect in rooms_f1:
        cx_r, cy_r = rect.centerx, rect.centery
        for i, line in enumerate(r[7].split('\n')):
            surf_t = font_sm.render(line, True, LABEL)
            surf.blit(surf_t, surf_t.get_rect(
                center=(cx_r, cy_r - 7 + i*14)))
    return rooms_f1


def draw_terrace(surf, font_sm, font_md, hover_id, sel_id):
    draw_rect_blender(surf, SLAB, 0, 0, HX, HY)

    rooms_t = [(r, sr(r[2], r[3], r[4], r[5]))
               for r in ROOMS if r[1] == 'T']
    for r, rect in rooms_t:
        col = ROOM_SEL if r[0] == sel_id else \
              ROOM_HOVER if r[0] == hover_id else SLAB
        pygame.draw.rect(surf, col, rect)

    # Parapet
    draw_wall(surf, 0,0,HX,0, 0.15)
    draw_wall(surf, 0,HY,HX,HY, 0.15)
    draw_wall(surf, 0,0,0,HY, 0.15)
    draw_wall(surf, HX,0,HX,HY, 0.15)

    # Viewing room glazing
    draw_rect_blender(surf, (*GLASS_C[:3], 80), HX-6.1, HY-6.1, 6.1, 0.1)
    draw_rect_blender(surf, (*GLASS_C[:3], 80), HX-0.1, HY-6.1, 0.1, 6.1)

    # Garden beds
    for gx, gy in [(1.5,5.2),(1.5,7.2),(3.5,5.2),(3.5,7.2)]:
        draw_rect_blender(surf, (80,55,30),  gx, gy, 1.2, 3.0)
        draw_rect_blender(surf, (90,150,65), gx+0.1, gy+0.1, 1.0, 2.8)

    # PV panels (3×5 grid)
    for ci in range(3):
        for ri in range(5):
            draw_rect_blender(surf, SOLAR_C,
                              0.4+0.7+ci*1.8, 0.4+0.5+ri*0.9, 1.0, 0.7)

    # Burjeel outline
    draw_rect_blender(surf, TERRA, 5.5, 3.3, 4.0, 3.4, 3)

    # Workshop clerestory (west)
    draw_rect_blender(surf, GLASS_C, -CANT_W, HY-0.2, CANT_W, 0.2)

    for r, rect in rooms_t:
        cx_r, cy_r = rect.centerx, rect.centery
        for i, line in enumerate(r[7].split('\n')):
            surf_t = font_sm.render(line, True, LABEL)
            surf.blit(surf_t, surf_t.get_rect(
                center=(cx_r, cy_r - 7 + i*14)))
    return rooms_t


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
def draw_sidebar(surf, font_sm, font_md, font_lg, floor, sel_id,
                 t, cooling_on, security_on,
                 sec_scenario=False, rwh_scenario=False):
    sb = pygame.Rect(CANVAS_W, 0, SIDEBAR_W, H)
    pygame.draw.rect(surf, SIDEBAR_BG, sb)

    x0 = CANVAS_W + 18
    y  = 20

    def txt(text, font, col=WHITE, indent=0):
        nonlocal y
        for line in text.split('\n'):
            s_t = font.render(line, True, col)
            surf.blit(s_t, (x0 + indent, y))
            y += s_t.get_height() + 2

    def sep():
        nonlocal y
        pygame.draw.line(surf, (60,65,80),
                         (CANVAS_W+10, y+4), (W-10, y+4), 1)
        y += 12

    txt('LUCKNOW SMART HOME', font_lg, (220, 215, 200))
    txt('4-BHK G+1+Terrace  |  27.4×13.7 m', font_sm, (160,155,145))
    sep()

    # System status
    txt('SYSTEMS', font_md, (200, 195, 185))
    cooling_col = CYAN if cooling_on else (90, 95, 105)
    txt(f'[1] Cooling airflow  {"▶ ON" if cooling_on else "  OFF"}',
        font_sm, cooling_col)
    txt('[2] Solar: 6 kWp  •  ~23 kWh/day', font_sm, GOLD)
    txt('     Battery: 12 kWh LFP charged', font_sm, (160,155,100))
    sec_col = (RED_SEC if security_on else (90,95,105))
    txt(f'[3] Security cameras  {"▶ ON" if security_on else "  OFF"}',
        font_sm, sec_col)
    sep()

    # Selected room detail
    sel = next((r for r in ROOMS if r[0] == sel_id), None)
    if sel:
        txt(sel[6], font_md, (220, 215, 200))
        txt(sel[8], font_sm, (180, 175, 165))
        sep()
    else:
        txt('Click a room for details', font_sm, (100,100,110))
        sep()

    # Scenario engine status
    if sec_scenario or rwh_scenario:
        txt('SCENARIO MODE ACTIVE', font_md, (255, 100, 60))
        sep()
    if sec_scenario:
        txt('🔴 SECURITY INCIDENT', font_md, (220, 60, 60))
        txt('  Cameras OFFLINE: GateN, NE', font_sm, (220, 90, 90))
        txt('  PIR zones elevated: Gate,', font_sm, (255, 140, 40))
        txt('  NE, SW, FrontDoor', font_sm, (255, 140, 40))
        txt('  FOV expanded: Drive, Front,', font_sm, CYAN)
        txt('  SW (coverage compensation)', font_sm, CYAN)
        txt('  IR beam-break: ARMED', font_sm, (255, 200, 0))
        txt('  NVR: all cams recording', font_sm, (180, 175, 165))
        sep()
    if rwh_scenario:
        txt('💧 RWH EMPTY — DRY DAY', font_md, (60, 150, 220))
        txt('  RWH tank: 0 L remaining', font_sm, (220, 60, 60))
        txt('  Mains supply: ACTIVE', font_sm, (60, 150, 220))
        txt('  Solenoid SV-DOM: MAINS', font_sm, (60, 150, 220))
        txt('  Beehive drip duty: 40 %', font_sm, (255, 180, 60))
        txt('  (conservation mode)', font_sm, (180,175,165))
        txt('  Soil sensors: MONITORING', font_sm, (90, 170, 80))
        txt('  Alert threshold: RH < 15%', font_sm, (180,175,165))
        sep()
    if not sec_scenario and not rwh_scenario:
        txt('PERFORMANCE', font_md, (200,195,185))
        txt('Cooling delta: ~14 °C (45→31°C)',   font_sm, (180,175,165))
        txt('Monsoon bypass: RH > 65 %',          font_sm, (180,175,165))
        txt('RWH tank: 18 000 L underground',     font_sm, (180,175,165))
        txt('Cameras: 7 IP + PIR + IR perimeter', font_sm, (180,175,165))
        txt('NVR: 30-day local  •  solar grid',   font_sm, (180,175,165))
        sep()

    # Controls
    txt('CONTROLS', font_md, (200,195,185))
    txt('[GF/F1/T]  Switch floor',    font_sm, (120,120,130))
    txt('[1/2/3]    Toggle systems',  font_sm, (120,120,130))
    txt('[4]        Security scenario', font_sm, (120,120,130))
    txt('[5]        RWH empty scenario', font_sm, (120,120,130))
    txt('[Click]    Room detail',     font_sm, (120,120,130))
    txt('[Esc]      Quit',            font_sm, (120,120,130))
    sep()

    # Animated cooling temp bar
    if cooling_on:
        bar_w = SIDEBAR_W - 36
        cool_frac = 0.5 + 0.5 * math.sin(t * 1.5)
        txt('Indoor temp estimate:', font_sm, CYAN)
        bar_rect = pygame.Rect(x0, y, bar_w, 14)
        pygame.draw.rect(surf, (40,44,55), bar_rect)
        inner = bar_rect.inflate(-2, -2)
        fill  = inner.copy(); fill.width = int(inner.width * (0.55 + 0.05*cool_frac))
        pygame.draw.rect(surf, CYAN, fill)
        temp  = 27.5 + cool_frac * 1.0
        surf.blit(font_sm.render(f'{temp:.1f} °C', True, WHITE), (x0, y+16))
        y += 36


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('Lucknow Smart Home  |  2D Interactive Plan')
    clock  = pygame.time.Clock()

    font_sm = pygame.font.SysFont('Segoe UI', 12)
    font_md = pygame.font.SysFont('Segoe UI', 14, bold=True)
    font_lg = pygame.font.SysFont('Segoe UI', 16, bold=True)
    font_tab= pygame.font.SysFont('Segoe UI', 13, bold=True)

    # Try to load pre-rendered plan PNGs as optional bg layer
    plan_surfs = {}
    for fl, path in PLAN_IMGS.items():
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
                plan_surfs[fl] = pygame.transform.scale(
                    img, (CANVAS_W, CANVAS_H))
            except Exception:
                pass

    floor        = 'GF'
    hover_id     = None
    sel_id       = None
    cooling      = False
    security     = False
    sec_scenario = False    # [4] security degraded scenario
    rwh_scenario = False    # [5] RWH empty / dry-day scenario
    t0           = time.time()

    # Airflow particle positions (0..1 along path)
    particles = [i / 8 for i in range(8)]

    # Floor tab rects
    tabs = {}
    for i, fl in enumerate(['GF', 'F1', 'T']):
        tabs[fl] = pygame.Rect(10 + i * 80, 8, 75, 30)

    running = True
    while running:
        t = time.time() - t0
        dt = clock.tick(FPS) / 1000

        # ── Events ──────────────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_1:
                    cooling = not cooling
                elif ev.key == pygame.K_2:
                    pass   # solar always displayed in sidebar
                elif ev.key == pygame.K_3:
                    security = not security
                elif ev.key == pygame.K_4:
                    sec_scenario = not sec_scenario
                    # auto-enable camera view when scenario starts
                    if sec_scenario:
                        security = True
                elif ev.key == pygame.K_5:
                    rwh_scenario = not rwh_scenario
                    if rwh_scenario:
                        cooling = True   # show beehive flow when scenario on
                elif ev.key == pygame.K_r:
                    cooling = security = False
                    sec_scenario = rwh_scenario = False
                    sel_id = None
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # Tab click
                for fl, tr in tabs.items():
                    if tr.collidepoint(mx, my):
                        floor = fl
                        sel_id = None
                        break
                # Room click (inside canvas)
                if mx < CANVAS_W:
                    for r in ROOMS:
                        if r[1] == floor:
                            rect = sr(r[2], r[3], r[4], r[5])
                            if rect.collidepoint(mx, my):
                                sel_id = r[0] if sel_id != r[0] else None
                                break

        # ── Hover ────────────────────────────────────────────────────────
        mx, my = pygame.mouse.get_pos()
        hover_id = None
        if mx < CANVAS_W:
            for r in ROOMS:
                if r[1] == floor:
                    if sr(r[2], r[3], r[4], r[5]).collidepoint(mx, my):
                        hover_id = r[0]
                        break

        # ── Draw canvas ──────────────────────────────────────────────────
        canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        canvas.fill(BG)

        if floor in plan_surfs:
            canvas.blit(plan_surfs[floor], (0, 0))
            canvas.set_alpha(None)
            overlay = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
            overlay.fill((245, 242, 236, 160))
            canvas.blit(overlay, (0,0))

        # Draw floor
        if floor == 'GF':
            active_rooms = draw_gf(canvas, font_sm, font_md, hover_id, sel_id)
        elif floor == 'F1':
            active_rooms = draw_f1(canvas, font_sm, font_md, hover_id, sel_id)
        else:
            active_rooms = draw_terrace(canvas, font_sm, font_md, hover_id, sel_id)

        # Cooling overlay
        if cooling and floor == 'GF':
            particles = [(p + dt * 0.35) % 1.0 for p in particles]
            path = FLOW_PATH_GF
            for p in particles:
                seg = int(p * (len(path)-1))
                frac = (p * (len(path)-1)) % 1.0
                if seg < len(path)-1:
                    x0r = path[seg][0] + frac*(path[seg+1][0]-path[seg][0])
                    y0r = path[seg][1] + frac*(path[seg+1][1]-path[seg][1])
                    px_s, py_s = s(x0r, y0r)
                    r_p = max(4, int(0.25*SCALE))
                    pygame.draw.circle(canvas, CYAN, (px_s, py_s), r_p)
            # arrows between waypoints
            for i in range(len(FLOW_PATH_GF)-1):
                p0 = s(*FLOW_PATH_GF[i])
                p1 = s(*FLOW_PATH_GF[i+1])
                draw_arrow(canvas, CYAN, p0, p1)
            # pulsing ring at stair (upward flow indicator)
            pulse_r = int((0.4 + 0.2*math.sin(t*4)) * SCALE)
            pygame.draw.circle(canvas, CYAN, s(STAIR_X, 5.0), pulse_r, 3)
            # label
            lab = font_sm.render('← Beehive → Stack → Burjeel', True, CYAN)
            canvas.blit(lab, (s(HX-1, 5.4)[0] - lab.get_width(), s(HX, 5.4)[1]))

        # Security overlay (normal — show all cams if no scenario)
        if security and not sec_scenario:
            for i, (bx, by, ang, fov, lbl) in enumerate(CAMS):
                draw_cam_cone(canvas, bx, by, ang, fov, lbl)

        # Scenario overlays
        if sec_scenario:
            draw_scenario_security(canvas, font_sm, t, floor)
        if rwh_scenario:
            draw_scenario_rwh(canvas, font_sm, t, floor)

        # Solar overlay (terrace)
        if floor == 'T':
            glow = int(40 + 20*math.sin(t*2))
            for ci in range(3):
                for ri in range(5):
                    bx_ = 0.4+0.7+ci*1.8
                    by_ = 0.4+0.5+ri*0.9
                    glow_s = pygame.Surface((int(1.0*SCALE), int(0.7*SCALE)),
                                            pygame.SRCALPHA)
                    glow_s.fill((*GOLD, glow))
                    sx_, sy_ = s(bx_, by_+0.7)
                    canvas.blit(glow_s, (sx_, sy_))

        # Compass rose
        compass_x, compass_y = CANVAS_W - 55, CANVAS_H - 55
        for angle, label, col in [
            (90,  'N', (200,100,100)),
            (270, 'S', GREY),
            (180, 'E', GREY),
            (0,   'W', GREY),
        ]:
            a = math.radians(angle)
            ex = compass_x + int(28*math.cos(a))
            ey = compass_y - int(28*math.sin(a))
            pygame.draw.line(canvas, col, (compass_x,compass_y), (ex,ey), 2)
            t_c = font_sm.render(label, True, col)
            canvas.blit(t_c, t_c.get_rect(center=(
                compass_x + int(38*math.cos(a)),
                compass_y - int(38*math.sin(a)))))

        screen.blit(canvas, (0, 0))

        # ── Sidebar ──────────────────────────────────────────────────────
        draw_sidebar(screen, font_sm, font_md, font_lg, floor, sel_id,
                     t, cooling, security, sec_scenario, rwh_scenario)

        # ── Floor tabs ───────────────────────────────────────────────────
        tab_labels = {'GF': 'Ground Floor', 'F1': 'First Floor', 'T': 'Terrace'}
        for fl, tr in tabs.items():
            active = (fl == floor)
            pygame.draw.rect(screen, SIDEBAR_BG if active else (200,196,188), tr,
                             border_radius=6)
            lbl = font_tab.render(tab_labels[fl], True,
                                  WHITE if active else (60,55,50))
            screen.blit(lbl, lbl.get_rect(center=tr.center))

        # Scale bar
        bar_len = int(5 * SCALE)
        bx_s, by_s = 30, CANVAS_H - 28
        pygame.draw.line(screen, LABEL, (bx_s, by_s), (bx_s+bar_len, by_s), 2)
        pygame.draw.line(screen, LABEL, (bx_s, by_s-4), (bx_s, by_s+4), 2)
        pygame.draw.line(screen, LABEL, (bx_s+bar_len, by_s-4), (bx_s+bar_len, by_s+4), 2)
        sc_t = font_sm.render('5 m', True, LABEL)
        screen.blit(sc_t, sc_t.get_rect(center=(bx_s + bar_len//2, by_s - 10)))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()
