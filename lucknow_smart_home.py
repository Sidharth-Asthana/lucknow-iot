"""
=====================================================================
lucknow_smart_home.py
Smart Self-Sufficient Residence -- Lucknow, India
Self-contained Blender bpy script (Blender 3.x / 4.x compatible).

USAGE
-----
1.  Open Blender, switch to the Scripting workspace.
2.  Text > Open this file, then click "Run Script" (Alt+P).
3.  Scene rebuilds (clears existing scene first); .blend is saved to
    C:/BLENDER/cradle/lucknow_smart_home.blend.
4.  To render the seven named cameras, type into the Python console:
        render_all("C:/BLENDER/cradle/renders/")
    Produces seven 1920x1080 PNGs (Cycles, 128 samples + denoise).

COORDINATE SYSTEM
-----------------
+X = East, +Y = North, +Z = Up.  Units = meters.
Main house SW corner is at world origin (0, 0, 0).
House envelope: x in [0, 13.9], y in [0, 10.0].
First-floor cantilever (workshop slab) extends west: x in [-3.0, 0].
Plot:           x in [-7.5, 19.9], y in [-1.85, 11.85].

DESIGN SUMMARY (matches verification.md)
----------------------------------------
- G+1+T, ~1500 sqft per floor (139 m^2), east-facing.
- Tall occupant: door clearances 2.44 m; master + viewing room ceilings
  3.35 m clear (11 ft).
- Beehive terracotta evaporative wall, two panels (E + S), each
  2.5 x 2.5 m, ~144 cones in hex pattern.  Cooling delta ~14 C.
- Burjeel wind catcher: 2 x 2 x 4 m atop central stair-core.
- PV pergola: 15 panels @ 400 W = 6 kWp, 25 deg south tilt.
- Rainwater tank: 18,000 L under driveway.
- Art workshop on first-floor west cantilever; north-light via
  clerestory monitor that pops above terrace level.
=====================================================================
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector, Euler


# =====================================================================
# 0. CONFIGURATION
# =====================================================================

SAVE_PATH  = "C:/BLENDER/cradle/lucknow_smart_home.blend"
RENDER_DIR = "C:/BLENDER/cradle/renders/"

# Plot
PLOT_X = 27.4
PLOT_Y = 13.7
DRIVEWAY_W = 7.5
LAWN_W     = 6.0
SETBACK_Y  = 1.85
PLOT_X0 = -DRIVEWAY_W
PLOT_X1 = 13.9 + LAWN_W
PLOT_Y0 = -SETBACK_Y
PLOT_Y1 = 10.0 + SETBACK_Y

# House dimensions
HX = 13.9    # east-west extent of main rectangle
HY = 10.0    # north-south extent

# Vertical stack
GF_FFL    = 0.0
GF_HEIGHT = 3.30   # floor-to-floor
F1_FFL    = 3.30
F1_HEIGHT = 3.65
T_FFL     = 6.95
PARAPET_H = 0.90
T_PARAPET_TOP = T_FFL + PARAPET_H

# Burjeel
BURJEEL_BASE_Z = T_FFL + 2.60          # sits atop central stair-core enclosure (2.6 m tall)
BURJEEL_H = 4.0
BURJEEL_TOP    = BURJEEL_BASE_Z + BURJEEL_H

# Wall thicknesses + slab
T_WALL_EXT = 0.20
T_WALL_INT = 0.115
T_SLAB     = 0.20
T_PARAPET  = 0.15

# Cantilever
CANT_W = 3.0   # westward
CANT_Y = 10.0  # north-south extent of workshop slab

# Door + window standards
DOOR_W  = 1.0
DOOR_H  = 2.44
WIN_SILL = 0.9
WIN_HEAD = 2.40

# Render
RENDER_W = 1920
RENDER_H = 1080
RENDER_SAMPLES = 128


# =====================================================================
# 1. UTILITIES
# =====================================================================

def clear_scene():
    """Delete everything for a clean rebuild."""
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                  bpy.data.lights, bpy.data.curves, bpy.data.images,
                  bpy.data.worlds):
        for item in list(block):
            block.remove(item)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def make_collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    parent_coll = parent if parent else bpy.context.scene.collection
    parent_coll.children.link(coll)
    return coll


def link_to_collection(obj, coll):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)


def add_box(name, size, location, rotation=(0, 0, 0),
            material=None, collection=None):
    """Box of size (sx, sy, sz) centered at location."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    sx, sy, sz = size
    obj.scale = (max(sx, 0.0001) / 2,
                 max(sy, 0.0001) / 2,
                 max(sz, 0.0001) / 2)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_plane(name, size, location, rotation=(0, 0, 0),
              material=None, collection=None):
    bpy.ops.mesh.primitive_plane_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    sx, sy = size
    obj.scale = (sx / 2, sy / 2, 1)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_cylinder(name, radius, depth, location, rotation=(0, 0, 0),
                 material=None, collection=None, verts=16):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth,
                                         vertices=verts, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


def add_wall(name, start, end, height, thickness, z_base=0.0,
             material=None, collection=None):
    """Wall as a box from start_xy to end_xy, height up from z_base."""
    sx, sy = start
    ex, ey = end
    length = math.hypot(ex - sx, ey - sy)
    if length < 1e-4:
        return None
    cx = (sx + ex) / 2
    cy = (sy + ey) / 2
    cz = z_base + height / 2
    angle = math.atan2(ey - sy, ex - sx)
    return add_box(name, (length, thickness, height), (cx, cy, cz),
                   rotation=(0, 0, angle),
                   material=material, collection=collection)


def add_wall_with_opening(name, start, end, height, thickness,
                           opening_pos, opening_w,
                           opening_bottom, opening_top, z_base=0.0,
                           material=None, collection=None):
    """Wall with a single opening (door if opening_bottom=0, window otherwise).
    opening_pos: distance from `start` to opening's near edge.
    opening_w:   opening width.
    opening_bottom / opening_top: relative to z_base.
    Returns (open_start_xy, open_end_xy) for further use (e.g. inserting glass).
    """
    sx, sy = start
    ex, ey = end
    total = math.hypot(ex - sx, ey - sy)
    angle = math.atan2(ey - sy, ex - sx)
    dx = math.cos(angle); dy = math.sin(angle)
    p_open_s = (sx + dx * opening_pos,           sy + dy * opening_pos)
    p_open_e = (sx + dx * (opening_pos + opening_w),
                sy + dy * (opening_pos + opening_w))
    if opening_pos > 1e-3:
        add_wall(name + "_L", start, p_open_s, height, thickness,
                 z_base, material, collection)
    if opening_pos + opening_w < total - 1e-3:
        add_wall(name + "_R", p_open_e, end, height, thickness,
                 z_base, material, collection)
    if opening_bottom > 1e-3:
        add_wall(name + "_Sill", p_open_s, p_open_e, opening_bottom,
                 thickness, z_base, material, collection)
    if opening_top < height - 1e-3:
        add_wall(name + "_Head", p_open_s, p_open_e, height - opening_top,
                 thickness, z_base + opening_top, material, collection)
    return p_open_s, p_open_e


def add_glass_in_opening(name, p_start, p_end, z_bottom, z_top,
                          glass_mat, collection, thickness=0.03):
    """Insert a thin glass pane in the opening defined by add_wall_with_opening."""
    sx, sy = p_start
    ex, ey = p_end
    length = math.hypot(ex - sx, ey - sy)
    cx = (sx + ex) / 2
    cy = (sy + ey) / 2
    cz = (z_bottom + z_top) / 2
    height = z_top - z_bottom
    angle = math.atan2(ey - sy, ex - sx)
    return add_box(name, (length, thickness, height), (cx, cy, cz),
                   rotation=(0, 0, angle),
                   material=glass_mat, collection=collection)


def add_text(name, body, location, size=0.4, rotation=(0, 0, 0),
             material=None, collection=None):
    """Add a 3D text object (used to label rooms in plan-view renders)."""
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.body = body
    obj.data.size = size
    obj.data.align_x = 'CENTER'
    obj.data.align_y = 'CENTER'
    obj.rotation_euler = rotation
    if material:
        obj.data.materials.append(material)
    if collection:
        link_to_collection(obj, collection)
    return obj


# =====================================================================
# 2. SCENE / RENDER SETUP
# =====================================================================

def setup_scene_units_and_render():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    # Render
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = RENDER_W
    scene.render.resolution_y = RENDER_H
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.cycles.samples = RENDER_SAMPLES
    scene.cycles.use_denoising = True
    try:
        scene.cycles.device = 'GPU'
    except Exception:
        pass
    # Color management — neutral tonemapper, works across Blender 4.x and 5.x
    for vt in ('AgX', 'Filmic', 'Standard'):
        try:
            scene.view_settings.view_transform = vt
            break
        except Exception:
            pass
    # Try common "no contrast boost" look names in order of preference
    for look in ('None', 'Medium Contrast', 'Base Contrast'):
        try:
            scene.view_settings.look = look
            break
        except Exception:
            pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    # Frame
    scene.frame_set(1)


def setup_world_sky():
    """Soft sky-blue background — consistent across all camera types and Blender versions."""
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg.name = "Background"
    # Warm off-white sky: reads as clean background from any camera angle
    bg.inputs[0].default_value = (0.82, 0.88, 0.97, 1.0)
    bg.inputs[1].default_value = 1.8
    nt.links.new(bg.outputs[0], out.inputs[0])


def setup_sun_light(coll):
    """Directional sun (east morning) + large overhead area fill to kill pure-black shadows."""
    # -- Sun --
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 30))
    sun = bpy.context.active_object
    sun.name = "SUN_Morning_East"
    sun.data.energy = 3.0          # reduced: avoids blowing-out lime-plaster surfaces
    sun.data.angle = math.radians(2.5)
    # Ry=+55° → -Z tip points east+down → light travels west+down (comes from east)
    sun.rotation_euler = (0, math.radians(55), 0)
    link_to_collection(sun, coll)

    # -- Overhead area fill --
    # Large soft panel high above fills shadowed walls/interiors so they never go pure black
    cx, cy = HX / 2, HY / 2
    bpy.ops.object.light_add(type='AREA', location=(cx, cy, 35))
    fill = bpy.context.active_object
    fill.name = "FILL_Overhead"
    fill.data.energy = 800.0       # large area → very soft, fills section/plan interiors
    fill.data.size   = 40.0        # covers whole plot
    fill.rotation_euler = (0, 0, 0)   # points straight down
    link_to_collection(fill, coll)


# =====================================================================
# 3. MATERIALS
# =====================================================================

def _principled(name, base_color, roughness=0.7, metallic=0.0,
                 transmission=0.0, ior=1.45, alpha=1.0, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    # Transmission input name varies between Blender versions
    for trans_key in ("Transmission Weight", "Transmission"):
        if trans_key in bsdf.inputs:
            bsdf.inputs[trans_key].default_value = transmission
            break
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    if emission is not None:
        for em_key in ("Emission Color", "Emission"):
            if em_key in bsdf.inputs:
                bsdf.inputs[em_key].default_value = (*emission, 1.0)
                break
        for st_key in ("Emission Strength",):
            if st_key in bsdf.inputs:
                bsdf.inputs[st_key].default_value = 5.0
                break
    if alpha < 1.0 or transmission > 0.0:
        mat.blend_method = 'BLEND'
    return mat


def _add_noise_to_color(mat, scale=8.0, strength=0.05):
    """Mix some Voronoi/Noise into the base color for natural variation."""
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if not bsdf: return
    base_color = bsdf.inputs["Base Color"].default_value[:3]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    color_ramp = nt.nodes.new("ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].color = (
        max(0, base_color[0] - strength),
        max(0, base_color[1] - strength),
        max(0, base_color[2] - strength), 1)
    color_ramp.color_ramp.elements[1].color = (
        min(1, base_color[0] + strength),
        min(1, base_color[1] + strength),
        min(1, base_color[2] + strength), 1)
    nt.links.new(noise.outputs["Fac"], color_ramp.inputs["Fac"])
    nt.links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])


def build_materials():
    M = {}
    M["LimePlaster"]    = _principled("MAT_LimePlaster",     (0.93, 0.91, 0.86), roughness=0.85)
    _add_noise_to_color(M["LimePlaster"], scale=12, strength=0.03)
    M["TerracottaJaali"]= _principled("MAT_TerracottaJaali", (0.62, 0.32, 0.20), roughness=0.75)
    _add_noise_to_color(M["TerracottaJaali"], scale=20, strength=0.04)
    M["Sandstone"]      = _principled("MAT_Sandstone",       (0.78, 0.68, 0.50), roughness=0.70)
    _add_noise_to_color(M["Sandstone"], scale=15, strength=0.05)
    M["Glass"]          = _principled("MAT_Glass",           (0.85, 0.92, 0.95), roughness=0.05,
                                       transmission=1.0, ior=1.45, alpha=0.25)
    M["Membrane"]       = _principled("MAT_Membrane",        (0.55, 0.58, 0.60), roughness=0.85)
    M["TerracottaCone"] = _principled("MAT_TerracottaCone",  (0.70, 0.36, 0.22), roughness=0.60)
    _add_noise_to_color(M["TerracottaCone"], scale=18, strength=0.06)
    M["PVPanel"]        = _principled("MAT_PVPanel",         (0.10, 0.13, 0.20), roughness=0.20, metallic=0.4)
    M["TimberJoinery"]  = _principled("MAT_TimberJoinery",   (0.42, 0.27, 0.16), roughness=0.50)
    M["RCC"]            = _principled("MAT_RCC",             (0.65, 0.65, 0.66), roughness=0.85)
    M["Greenery"]       = _principled("MAT_Greenery",        (0.20, 0.50, 0.18), roughness=0.85)
    M["AirflowArrow"]   = _principled("MAT_AirflowArrow",    (0.10, 0.85, 0.95),
                                       roughness=1.0, emission=(0.10, 0.85, 0.95))
    # Supplementary
    M["Grass"]          = _principled("MAT_Grass",           (0.18, 0.42, 0.16), roughness=0.95)
    _add_noise_to_color(M["Grass"], scale=30, strength=0.05)
    M["Concrete"]       = _principled("MAT_Concrete",        (0.55, 0.55, 0.54), roughness=0.85)
    M["Soil"]           = _principled("MAT_Soil",            (0.32, 0.21, 0.13), roughness=0.95)
    M["Steel"]          = _principled("MAT_Steel",           (0.45, 0.45, 0.48), roughness=0.40, metallic=0.85)
    M["Fabric"]         = _principled("MAT_Fabric",          (0.55, 0.45, 0.40), roughness=0.85)
    M["Marble"]         = _principled("MAT_Marble",          (0.92, 0.90, 0.86), roughness=0.20)
    M["LabelText"]      = _principled("MAT_LabelText",       (0.05, 0.05, 0.05), roughness=1.0)
    M["DriveGravel"]    = _principled("MAT_DriveGravel",     (0.50, 0.48, 0.45), roughness=0.95)
    M["Black"]          = _principled("MAT_Black",           (0.04, 0.04, 0.04), roughness=0.6)
    M["WaterPipe"]      = _principled("MAT_WaterPipe",       (0.20, 0.30, 0.50), roughness=0.4, metallic=0.2)
    return M


# =====================================================================
# 4. SITE
# =====================================================================

def build_site(coll, M):
    # Plot ground
    add_box("Site_Plot", (PLOT_X, PLOT_Y, 0.05),
            ((PLOT_X0 + PLOT_X1) / 2, (PLOT_Y0 + PLOT_Y1) / 2, -0.025),
            material=M["Grass"], collection=coll)
    # Driveway (concrete)
    add_box("Site_Driveway", (DRIVEWAY_W, 4.0, 0.06),
            (-DRIVEWAY_W / 2, 5.0, 0.005),
            material=M["Concrete"], collection=coll)
    # East front lawn -- already covered by plot grass, add a footpath
    # Stepping stone path from gate to foyer
    for i in range(5):
        add_box(f"Site_Path_Step_{i}", (0.6, 0.4, 0.05),
                (HX + 0.5 + i * 1.0, 5.0, 0.025),
                material=M["Sandstone"], collection=coll)
    # Boundary wall (perimeter, 1.8 m, with gap on west for gate)
    bw_h = 1.8; bw_t = 0.2
    # South wall (full)
    add_box("Site_BWall_S", (PLOT_X, bw_t, bw_h),
            ((PLOT_X0 + PLOT_X1) / 2, PLOT_Y0, bw_h / 2),
            material=M["LimePlaster"], collection=coll)
    # North wall (full)
    add_box("Site_BWall_N", (PLOT_X, bw_t, bw_h),
            ((PLOT_X0 + PLOT_X1) / 2, PLOT_Y1, bw_h / 2),
            material=M["LimePlaster"], collection=coll)
    # East wall (full)
    add_box("Site_BWall_E", (bw_t, PLOT_Y, bw_h),
            (PLOT_X1, (PLOT_Y0 + PLOT_Y1) / 2, bw_h / 2),
            material=M["LimePlaster"], collection=coll)
    # West wall (split for 4m gate at y in [3, 7])
    add_box("Site_BWall_W_S", (bw_t, 3.0 - PLOT_Y0, bw_h),
            (PLOT_X0, (PLOT_Y0 + 3.0) / 2, bw_h / 2),
            material=M["LimePlaster"], collection=coll)
    add_box("Site_BWall_W_N", (bw_t, PLOT_Y1 - 7.0, bw_h),
            (PLOT_X0, (7.0 + PLOT_Y1) / 2, bw_h / 2),
            material=M["LimePlaster"], collection=coll)
    # Sliding gate (tall steel slats)
    add_box("Site_Gate", (0.05, 4.0, 1.8),
            (PLOT_X0, 5.0, 0.9),
            material=M["Steel"], collection=coll)
    for i in range(8):
        add_box(f"Site_Gate_Slat_{i}", (0.04, 0.10, 1.7),
                (PLOT_X0 - 0.04, 3.05 + i * 0.5, 0.85),
                material=M["Steel"], collection=coll)
    # Recharge pit (NE corner)
    add_cylinder("Site_RechargePit", radius=0.6, depth=0.05,
                 location=(PLOT_X1 - 1.5, PLOT_Y1 - 1.5, 0.025),
                 material=M["DriveGravel"], collection=coll)
    # Rainwater tank wireframe (under driveway, at z=-2)
    tank = add_box("Site_RainwaterTank", (4.0, 3.0, 1.5),
                   (-4.5, 5.0, -1.0),
                   material=M["RCC"], collection=coll)
    tank.display_type = 'WIRE'
    # Tank label
    add_text("Site_TankLabel", "RWH 18,000 L\n(under driveway)",
              location=(-4.5, 5.0, 0.2), size=0.35,
              rotation=(0, 0, 0),
              material=M["LabelText"], collection=coll)
    # Manhole + first flush
    add_cylinder("Site_Manhole", radius=0.35, depth=0.10,
                 location=(-3.0, 5.0, 0.05),
                 material=M["RCC"], collection=coll)


# =====================================================================
# 5. GROUND FLOOR
# =====================================================================

def build_ground_floor(coll, sys_coll, M):
    # Floor slab (visible under-side of GF)
    add_box("GF_Slab", (HX, HY, T_SLAB), (HX / 2, HY / 2, -T_SLAB / 2),
            material=M["RCC"], collection=coll)
    # Interior floor finish (wood/marble, slightly raised)
    add_plane("GF_Floor_Finish", (HX - 0.02, HY - 0.02),
              (HX / 2, HY / 2, 0.001),
              material=M["Marble"], collection=coll)

    h = GF_HEIGHT
    t = T_WALL_EXT
    pl = M["LimePlaster"]

    # ---- OUTER WALLS (with key openings) ----
    # SOUTH wall: y = 0; openings: BeehiveS aperture (behind jaali) + small window
    # Wall corners: (0, 0) -> (HX, 0)
    # We'll add the south jaali aperture in the systems section by overlaying
    # a jaali screen. Wall gets two punched windows for guest bedroom + living.
    # For simplicity, build south wall in three segments around openings:
    add_wall("GF_W_S_a", (0.0, 0.0), (5.5, 0.0), h, t, material=pl, collection=coll)
    # window into living/dining: at x in [5.5, 7.5], 1.5 x 1.5
    add_wall_with_opening("GF_W_S_LiveWin", (5.5, 0.0), (7.5, 0.0),
                          h, t, opening_pos=0.0, opening_w=2.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          material=pl, collection=coll)
    add_glass_in_opening("GF_W_S_LiveWin_Glass",
                         (5.5, 0.0), (7.5, 0.0), WIN_SILL, WIN_SILL + 1.5,
                         M["Glass"], coll)
    add_wall("GF_W_S_b", (7.5, 0.0), (10.0, 0.0), h, t, material=pl, collection=coll)
    # Beehive S aperture: 2.5 wide at x in [10.0, 12.5], full height behind jaali
    add_wall_with_opening("GF_W_S_Beehive", (10.0, 0.0), (12.5, 0.0),
                          h, t, opening_pos=0.0, opening_w=2.5,
                          opening_bottom=0.5, opening_top=3.0,
                          material=pl, collection=coll)
    add_wall("GF_W_S_c", (12.5, 0.0), (HX, 0.0), h, t, material=pl, collection=coll)

    # EAST wall: x = HX; openings: foyer door, big living window, beehive aperture E,
    # guest bedroom door to balcony, kitchen east window.
    # North end (kitchen) -> south end (guest)
    # Kitchen east window at y in [7.5, 9.0]
    add_wall("GF_W_E_a", (HX, HY), (HX, 9.0), h, t, material=pl, collection=coll)
    add_wall_with_opening("GF_W_E_KitWin", (HX, 9.0), (HX, 7.5),
                          h, t, opening_pos=0.0, opening_w=1.5,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          material=pl, collection=coll)
    add_glass_in_opening("GF_W_E_KitWin_Glass",
                         (HX, 9.0), (HX, 7.5), WIN_SILL, WIN_SILL + 1.5,
                         M["Glass"], coll)
    add_wall("GF_W_E_b", (HX, 7.5), (HX, 6.5), h, t, material=pl, collection=coll)
    # Foyer door at y in [5.5, 6.5]
    add_wall_with_opening("GF_W_E_FoyerDoor", (HX, 6.5), (HX, 5.5),
                          h, t, opening_pos=0.0, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    # Door leaf (timber)
    add_box("GF_FrontDoor", (0.05, 1.0, DOOR_H),
            (HX - 0.025, 6.0, DOOR_H / 2),
            material=M["TimberJoinery"], collection=coll)
    # Beehive E aperture: 2.5 wide at y in [3.0, 5.5]
    add_wall("GF_W_E_c", (HX, 5.5), (HX, 5.5), h, t, material=pl, collection=coll)
    add_wall_with_opening("GF_W_E_Beehive", (HX, 5.5), (HX, 3.0),
                          h, t, opening_pos=0.0, opening_w=2.5,
                          opening_bottom=0.5, opening_top=3.0,
                          material=pl, collection=coll)
    # Living-room east window at y in [1.7, 3.0]
    add_wall_with_opening("GF_W_E_LivWin", (HX, 3.0), (HX, 1.7),
                          h, t, opening_pos=0.0, opening_w=1.3,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          material=pl, collection=coll)
    add_glass_in_opening("GF_W_E_LivWin_Glass",
                         (HX, 3.0), (HX, 1.7), WIN_SILL, WIN_SILL + 1.5,
                         M["Glass"], coll)
    # Guest balcony door at y in [0.5, 1.7]
    add_wall_with_opening("GF_W_E_GuestDoor", (HX, 1.7), (HX, 0.5),
                          h, t, opening_pos=0.0, opening_w=1.2,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    add_glass_in_opening("GF_W_E_GuestDoor_Glass",
                         (HX, 1.7), (HX, 0.5), 0.0, DOOR_H,
                         M["Glass"], coll)
    add_wall("GF_W_E_d", (HX, 0.5), (HX, 0.0), h, t, material=pl, collection=coll)

    # NORTH wall: y = HY; small kitchen window, plus blank wall to BR2 above (this is GF, BR2 is above)
    # GF north has kitchen window + blank
    add_wall_with_opening("GF_W_N_KitchenN", (0.0, HY), (4.0, HY),
                          h, t, opening_pos=1.0, opening_w=1.5,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          material=pl, collection=coll)
    add_glass_in_opening("GF_W_N_KitchenN_Glass",
                         (1.0, HY), (2.5, HY), WIN_SILL, WIN_SILL + 1.5,
                         M["Glass"], coll)
    add_wall("GF_W_N_b", (4.0, HY), (HX, HY), h, t, material=pl, collection=coll)

    # WEST wall: x = 0; garage roller door (4.5 m wide), narrow slits on either side
    add_wall("GF_W_W_a", (0.0, 0.0), (0.0, 2.0), h, t, material=pl, collection=coll)
    add_wall_with_opening("GF_W_W_GarageDoor", (0.0, 2.0), (0.0, 6.5),
                          h, t, opening_pos=0.0, opening_w=4.5,
                          opening_bottom=0.0, opening_top=2.5,
                          material=pl, collection=coll)
    # Garage roller door visual
    add_box("GF_GarageRollerDoor", (0.04, 4.5, 2.5),
            (-0.02, 4.25, 1.25),
            material=M["Steel"], collection=coll)
    add_wall_with_opening("GF_W_W_SideDoor", (0.0, 6.5), (0.0, 8.0),
                          h, t, opening_pos=0.5, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    add_wall("GF_W_W_b", (0.0, 8.0), (0.0, HY), h, t, material=pl, collection=coll)

    # ---- INTERNAL WALLS ----
    # Garage / corridor partition: vertical wall at x = 5.9 between y=0 and y=HY
    # but with stair-core opening between y=2.5 and y=5.0 (door from garage to corridor)
    add_wall_with_opening("GF_I_GarageE", (5.9, 0.0), (5.9, HY),
                          h, T_WALL_INT, opening_pos=2.7, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    # Stair / elevator core: 4 walls around x in [5.9, 8.4], y in [3.0, 7.5]
    # Elevator shaft visualization: short box from (5.9, 5.5) to (7.4, 7.0)
    # Stair-core east wall (separates stair from foyer/living)
    add_wall_with_opening("GF_I_StairE", (8.4, 3.0), (8.4, 7.5),
                          h, T_WALL_INT, opening_pos=1.0, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    # Stair-core south wall
    add_wall("GF_I_StairS", (5.9, 3.0), (8.4, 3.0), h, T_WALL_INT,
             material=pl, collection=coll)
    # Stair-core north wall (with door to corridor / kitchen)
    add_wall_with_opening("GF_I_StairN", (5.9, 7.5), (8.4, 7.5),
                          h, T_WALL_INT, opening_pos=0.5, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    # Internal partition: kitchen/dining vs living (open layout, low partition only)
    # We'll skip this -- open kitchen/dining/living per program.
    # Guest bedroom partition: separates SE quadrant (guest) from living
    # Guest bedroom occupies x in [10.0, HX], y in [0.0, 3.5]
    # Wall at y=3.5 from x=10.0 to x=HX
    add_wall_with_opening("GF_I_GuestN", (10.0, 3.5), (HX, 3.5),
                          h, T_WALL_INT, opening_pos=1.5, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    # Wall at x=10.0 from y=0.0 to y=3.5
    add_wall("GF_I_GuestW", (10.0, 0.0), (10.0, 3.5), h, T_WALL_INT,
             material=pl, collection=coll)
    # Guest bath partition (small): bath occupies x in [10.0, 12.0], y in [0.0, 2.0]
    add_wall_with_opening("GF_I_GuestBathE", (12.0, 0.0), (12.0, 2.0),
                          h, T_WALL_INT, opening_pos=0.7, opening_w=0.8,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    add_wall("GF_I_GuestBathN", (10.0, 2.0), (12.0, 2.0), h, T_WALL_INT,
             material=pl, collection=coll)

    # Powder bath: small enclosure at x in [8.6, 10.0], y in [3.5, 5.0]
    add_wall_with_opening("GF_I_PowderS", (8.6, 5.0), (10.0, 5.0),
                          h, T_WALL_INT, opening_pos=0.4, opening_w=0.8,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          material=pl, collection=coll)
    add_wall("GF_I_PowderE", (10.0, 3.5), (10.0, 5.0), h, T_WALL_INT,
             material=pl, collection=coll)
    add_wall("GF_I_PowderW", (8.6, 3.5), (8.6, 5.0), h, T_WALL_INT,
             material=pl, collection=coll)

    # ---- STAIR ----
    # Dog-leg stair within the central core: rises from z=0 to z=3.30 over 18 risers
    # Located in stair-core at x in [5.9, 8.4], y in [3.0, 5.5] (south half of core)
    # First flight: south, going up east; second flight: north, going up west
    riser_h = GF_HEIGHT / 18
    tread_d = 0.25
    # Flight 1: 9 treads going north along west side of core
    for i in range(9):
        add_box(f"GF_Stair_F1_{i}",
                (1.0, tread_d, riser_h * (i + 1)),
                (6.4, 3.0 + tread_d / 2 + i * tread_d, riser_h * (i + 1) / 2),
                material=M["TimberJoinery"], collection=coll)
    # Mid landing
    add_box("GF_Stair_Landing",
            (1.0, 1.0, 0.05),
            (6.4, 3.0 + 9 * tread_d + 0.5, 9 * riser_h - 0.025 + 0.05),
            material=M["TimberJoinery"], collection=coll)
    # Flight 2: 9 treads going south along east side, rising to F1 FFL
    landing_top_z = 9 * riser_h
    for i in range(9):
        z_top = landing_top_z + riser_h * (i + 1)
        z_center = (landing_top_z + z_top) / 2
        add_box(f"GF_Stair_F2_{i}",
                (1.0, tread_d, z_top - landing_top_z + 0.02),
                (7.4, 3.0 + 9 * tread_d + 1.0 - tread_d / 2 - i * tread_d,
                 z_center),
                material=M["TimberJoinery"], collection=coll)
    # Elevator shaft (open box)
    add_box("GF_Elevator_Shaft", (1.5, 1.6, 0.05),
            (7.65, 6.7, 0.025),
            material=M["RCC"], collection=coll)
    # Elevator walls (3 sides, leave east open as door)
    add_wall("GF_Elev_W", (6.9, 5.9), (6.9, 7.5), h, T_WALL_INT,
             material=pl, collection=coll)
    add_wall("GF_Elev_S", (6.9, 5.9), (8.4, 5.9), h, T_WALL_INT,
             material=pl, collection=coll)
    add_wall("GF_Elev_N", (6.9, 7.5), (8.4, 7.5), h, T_WALL_INT,
             material=pl, collection=coll)

    # ---- VERANDAH (east, deep overhang) ----
    # 1.5 m projection from x = HX east, supported on 2 sandstone columns at y=2.5 and y=7.5
    add_box("GF_Verandah_Slab", (1.5, HY, 0.20),
            (HX + 0.75, HY / 2, GF_HEIGHT - 0.10),
            material=M["RCC"], collection=coll)
    for cy in (2.5, 7.5):
        add_box(f"GF_VerCol_{cy}",
                (0.30, 0.30, GF_HEIGHT - 0.20),
                (HX + 1.4, cy, (GF_HEIGHT - 0.20) / 2),
                material=M["Sandstone"], collection=coll)

    # ---- GUEST BALCONY (E side off guest bedroom) ----
    # 3 m wide x 2 m deep, x in [HX, HX+2], y in [0.5, 3.5]
    add_box("GF_GuestBalcony_Slab", (2.0, 3.0, 0.15),
            (HX + 1.0, 2.0, -0.075),
            material=M["RCC"], collection=coll)
    add_box("GF_GuestBalcony_RailE", (0.05, 3.0, 1.0),
            (HX + 2.0, 2.0, 0.5),
            material=M["TimberJoinery"], collection=coll)
    add_box("GF_GuestBalcony_RailN", (2.0, 0.05, 1.0),
            (HX + 1.0, 3.5, 0.5),
            material=M["TimberJoinery"], collection=coll)
    add_box("GF_GuestBalcony_RailS", (2.0, 0.05, 1.0),
            (HX + 1.0, 0.5, 0.5),
            material=M["TimberJoinery"], collection=coll)

    # ---- FURNITURE (low-poly) ----
    # Garage parking pads
    for i, x in enumerate((1.0, 4.0)):
        add_plane(f"GF_GaragePad_{i}", (1.8, 4.5),
                  (x + 0.9, 4.0, 0.011),
                  material=M["Black"], collection=coll)
    # Workshop bay (east side of garage)
    add_box("GF_WorkBench", (1.0, 2.0, 0.85),
            (5.3, 2.0, 0.425),
            material=M["TimberJoinery"], collection=coll)
    # Battery cabinets (along W wall of garage)
    add_box("GF_BatteryCab", (0.5, 1.6, 1.4),
            (0.4, 1.0, 0.7),
            material=M["Steel"], collection=coll)
    add_text("GF_BatteryLabel", "12 kWh LFP",
              location=(0.4, 1.0, 1.55), size=0.18,
              material=M["LabelText"], collection=coll)
    add_box("GF_Inverter", (0.45, 0.6, 0.9),
            (0.4, 8.5, 0.45),
            material=M["Steel"], collection=coll)
    add_text("GF_InverterLabel", "5 kW Hybrid Inverter",
              location=(0.4, 8.5, 1.0), size=0.15,
              material=M["LabelText"], collection=coll)
    # Smart-home / NVR cabinet (in stair-core utility cupboard, north end)
    add_box("GF_NVRCabinet", (0.4, 0.6, 1.6),
            (8.0, 7.2, 0.8),
            material=M["Black"], collection=coll)
    add_text("GF_NVRLabel", "NVR + KNX + Server",
              location=(8.0, 7.2, 1.7), size=0.13,
              material=M["LabelText"], collection=coll)

    # Kitchen island
    add_box("GF_KitchenIsland", (3.0, 1.2, 0.92),
            (8.5, 8.5, 0.46),
            material=M["Marble"], collection=coll)
    add_box("GF_KitchenCounter", (3.0, 0.6, 0.92),
            (HX - 0.3 - 1.5, 9.4, 0.46),
            material=M["TimberJoinery"], collection=coll)
    # Dining table
    add_box("GF_DiningTable", (2.4, 1.0, 0.78),
            (11.5, 7.5, 0.39),
            material=M["TimberJoinery"], collection=coll)
    for i in range(8):
        col = i % 4; row = i // 4
        cx = 11.5 - 0.9 + col * 0.6
        cy = 7.5 + (-0.7 if row == 0 else 0.7)
        add_box(f"GF_DiningChair_{i}", (0.4, 0.4, 0.85),
                (cx, cy, 0.425),
                material=M["TimberJoinery"], collection=coll)
    # Living room sectional sofa (L-shape)
    add_box("GF_Sofa_S", (3.0, 0.8, 0.4),
            (10.5, 4.4, 0.2),
            material=M["Fabric"], collection=coll)
    add_box("GF_Sofa_E", (0.8, 2.0, 0.4),
            (12.0, 5.4, 0.2),
            material=M["Fabric"], collection=coll)
    add_box("GF_CoffeeTable", (1.2, 0.6, 0.35),
            (10.5, 5.5, 0.175),
            material=M["TimberJoinery"], collection=coll)
    # Guest bedroom bed (queen 5x6.5 ft = 1.5x2.0 m)
    add_box("GF_GuestBed", (1.5, 2.0, 0.5),
            (12.5, 2.5, 0.25),
            material=M["Fabric"], collection=coll)
    add_box("GF_GuestNightstand", (0.4, 0.4, 0.55),
            (11.5, 1.7, 0.275),
            material=M["TimberJoinery"], collection=coll)

    # Foyer bench
    add_box("GF_FoyerBench", (1.2, 0.4, 0.45),
            (HX - 0.7, 6.0, 0.225),
            material=M["TimberJoinery"], collection=coll)


# =====================================================================
# 6. FIRST FLOOR
# =====================================================================

def build_first_floor(coll, M):
    z0 = F1_FFL
    h = F1_HEIGHT
    t = T_WALL_EXT
    pl = M["LimePlaster"]

    # Slab (over GF) including 3m W cantilever
    add_box("F1_Slab_Main", (HX, HY, T_SLAB),
            (HX / 2, HY / 2, z0 - T_SLAB / 2),
            material=M["RCC"], collection=coll)
    add_box("F1_Slab_Cantilever", (CANT_W, CANT_Y, T_SLAB),
            (-CANT_W / 2, CANT_Y / 2, z0 - T_SLAB / 2),
            material=M["RCC"], collection=coll)
    # Floor finish
    add_plane("F1_Floor_Finish_Main", (HX - 0.02, HY - 0.02),
              (HX / 2, HY / 2, z0 + 0.001),
              material=M["TimberJoinery"], collection=coll)
    add_plane("F1_Floor_Finish_Workshop", (CANT_W - 0.02, CANT_Y - 0.02),
              (-CANT_W / 2, CANT_Y / 2, z0 + 0.001),
              material=M["Concrete"], collection=coll)

    # ---- OUTER WALLS (main rectangle) ----
    # SOUTH wall y=0: master suite + lounge view
    add_wall("F1_W_S_a", (0.0, 0.0), (3.0, 0.0), h, t, z0, material=pl, collection=coll)
    add_wall_with_opening("F1_W_S_LoungeWin", (3.0, 0.0), (5.0, 0.0),
                          h, t, opening_pos=0.0, opening_w=2.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.7,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_S_LoungeWin_Glass",
                         (3.0, 0.0), (5.0, 0.0),
                         z0 + WIN_SILL, z0 + WIN_SILL + 1.7,
                         M["Glass"], coll)
    add_wall("F1_W_S_b", (5.0, 0.0), (8.5, 0.0), h, t, z0, material=pl, collection=coll)
    # Master south window (large)
    add_wall_with_opening("F1_W_S_MasterWin", (8.5, 0.0), (12.5, 0.0),
                          h, t, opening_pos=0.0, opening_w=4.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 2.0,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_S_MasterWin_Glass",
                         (8.5, 0.0), (12.5, 0.0),
                         z0 + WIN_SILL, z0 + WIN_SILL + 2.0,
                         M["Glass"], coll)
    add_wall("F1_W_S_c", (12.5, 0.0), (HX, 0.0), h, t, z0, material=pl, collection=coll)

    # EAST wall x=HX: master east window + balcony door, BR2 east window + balcony door
    add_wall("F1_W_E_a", (HX, 0.0), (HX, 1.0), h, t, z0, material=pl, collection=coll)
    add_wall_with_opening("F1_W_E_MasterDoor", (HX, 1.0), (HX, 2.5),
                          h, t, opening_pos=0.0, opening_w=1.5,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_E_MasterDoor_Glass",
                         (HX, 1.0), (HX, 2.5),
                         z0, z0 + DOOR_H, M["Glass"], coll)
    add_wall_with_opening("F1_W_E_MasterWin", (HX, 2.5), (HX, 4.5),
                          h, t, opening_pos=0.0, opening_w=2.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 2.0,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_E_MasterWin_Glass",
                         (HX, 2.5), (HX, 4.5),
                         z0 + WIN_SILL, z0 + WIN_SILL + 2.0, M["Glass"], coll)
    add_wall("F1_W_E_mid", (HX, 4.5), (HX, 6.0), h, t, z0, material=pl, collection=coll)
    add_wall_with_opening("F1_W_E_BR2Door", (HX, 6.0), (HX, 7.5),
                          h, t, opening_pos=0.0, opening_w=1.5,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_E_BR2Door_Glass",
                         (HX, 6.0), (HX, 7.5),
                         z0, z0 + DOOR_H, M["Glass"], coll)
    add_wall_with_opening("F1_W_E_BR2Win", (HX, 7.5), (HX, 9.5),
                          h, t, opening_pos=0.0, opening_w=2.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 2.0,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_E_BR2Win_Glass",
                         (HX, 7.5), (HX, 9.5),
                         z0 + WIN_SILL, z0 + WIN_SILL + 2.0, M["Glass"], coll)
    add_wall("F1_W_E_b", (HX, 9.5), (HX, HY), h, t, z0, material=pl, collection=coll)

    # NORTH wall y=HY: BR2 + BR3 north windows
    add_wall("F1_W_N_a", (HX, HY), (12.0, HY), h, t, z0, material=pl, collection=coll)
    add_wall_with_opening("F1_W_N_BR2Win", (12.0, HY), (10.0, HY),
                          h, t, opening_pos=0.0, opening_w=2.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_N_BR2Win_Glass",
                         (12.0, HY), (10.0, HY),
                         z0 + WIN_SILL, z0 + WIN_SILL + 1.5, M["Glass"], coll)
    add_wall("F1_W_N_b", (10.0, HY), (5.0, HY), h, t, z0, material=pl, collection=coll)
    add_wall_with_opening("F1_W_N_BR3Win", (5.0, HY), (3.0, HY),
                          h, t, opening_pos=0.0, opening_w=2.0,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_N_BR3Win_Glass",
                         (5.0, HY), (3.0, HY),
                         z0 + WIN_SILL, z0 + WIN_SILL + 1.5, M["Glass"], coll)
    add_wall("F1_W_N_c", (3.0, HY), (0.0, HY), h, t, z0, material=pl, collection=coll)

    # WEST wall x=0: now interior wall to workshop (open with one door)
    add_wall("F1_W_W_a", (0.0, 0.0), (0.0, 4.0), h, t, z0, material=pl, collection=coll)
    add_wall_with_opening("F1_W_W_WorkshopDoor", (0.0, 4.0), (0.0, 6.0),
                          h, t, opening_pos=0.5, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_wall("F1_W_W_b", (0.0, 6.0), (0.0, HY), h, t, z0, material=pl, collection=coll)

    # ---- WORKSHOP CANTILEVER -- outer walls ----
    # North wall of workshop
    add_wall("F1_W_W_WorkshopN", (-CANT_W, CANT_Y), (0.0, CANT_Y), h, t, z0,
             material=pl, collection=coll)
    # South wall of workshop
    add_wall_with_opening("F1_W_W_WorkshopS", (-CANT_W, 0.0), (0.0, 0.0),
                          h, t, opening_pos=0.5, opening_w=1.5,
                          opening_bottom=WIN_SILL, opening_top=WIN_SILL + 1.5,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_W_WorkshopS_Glass",
                         (-CANT_W, 0.0), (0.0, 0.0),
                         z0 + WIN_SILL, z0 + WIN_SILL + 1.5, M["Glass"], coll)
    # West wall of workshop (overlooks driveway, mostly solid)
    add_wall_with_opening("F1_W_W_WorkshopW", (-CANT_W, 0.0), (-CANT_W, CANT_Y),
                          h, t, opening_pos=4.0, opening_w=1.5,
                          opening_bottom=WIN_SILL + 0.4, opening_top=WIN_SILL + 1.6,
                          z_base=z0, material=pl, collection=coll)
    add_glass_in_opening("F1_W_W_WorkshopW_Glass",
                         (-CANT_W, 4.0), (-CANT_W, 5.5),
                         z0 + WIN_SILL + 0.4, z0 + WIN_SILL + 1.6, M["Glass"], coll)

    # ---- INTERNAL WALLS (main rectangle) ----
    # Master suite occupies SE quadrant: x in [8.5, HX], y in [0.5, 5.0]
    # Master partition (north wall): x=8.5 to HX at y=5.0
    add_wall_with_opening("F1_I_MasterN", (8.5, 5.0), (HX, 5.0),
                          h, T_WALL_INT, opening_pos=0.5, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    # Master partition (west wall): x=8.5 from y=0.5 to y=5.0
    add_wall("F1_I_MasterW", (8.5, 0.5), (8.5, 5.0), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    # Master ensuite: x in [8.5, 11.5], y in [0.5, 2.5]
    add_wall_with_opening("F1_I_MasterBathN", (8.5, 2.5), (11.5, 2.5),
                          h, T_WALL_INT, opening_pos=2.0, opening_w=0.8,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_wall("F1_I_MasterBathE", (11.5, 0.5), (11.5, 2.5), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    # Walk-in wardrobe inside master (small room)
    add_wall("F1_I_MasterWIWS", (11.5, 3.0), (HX - 0.5, 3.0), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall_with_opening("F1_I_MasterWIWW", (11.5, 3.0), (11.5, 5.0),
                          h, T_WALL_INT, opening_pos=0.6, opening_w=0.9,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)

    # Bedroom 2 occupies NE quadrant: x in [8.5, HX], y in [5.5, HY]
    # BR2 west wall x=8.5 from y=5.5 to y=HY
    add_wall("F1_I_BR2W", (8.5, 5.5), (8.5, HY), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    # BR2 ensuite (NE corner): x in [8.5, 10.5], y in [HY - 2.5, HY]
    add_wall_with_opening("F1_I_BR2BathS", (8.5, HY - 2.5), (10.5, HY - 2.5),
                          h, T_WALL_INT, opening_pos=1.0, opening_w=0.8,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_wall("F1_I_BR2BathE", (10.5, HY - 2.5), (10.5, HY), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    # BR2 corridor partition (between BR2 and central hallway)
    add_wall_with_opening("F1_I_BR2DoorWall", (8.5, 5.5), (HX, 5.5),
                          h, T_WALL_INT, opening_pos=0.5, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)

    # Bedroom 3 occupies NW interior: x in [3.0, 5.5], y in [5.5, HY]
    # BR3 east wall x=5.5
    add_wall_with_opening("F1_I_BR3E", (5.5, 5.5), (5.5, HY),
                          h, T_WALL_INT, opening_pos=2.0, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    # BR3 south wall (corridor side) y=5.5 from x=0 to x=5.5
    add_wall("F1_I_BR3S", (0.0, 5.5), (5.5, 5.5), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    # BR3 ensuite at x in [3.0, 5.5], y in [HY - 2.5, HY]
    add_wall("F1_I_BR3BathS", (3.0, HY - 2.5), (5.5, HY - 2.5), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall("F1_I_BR3BathW", (3.0, HY - 2.5), (3.0, HY), h, T_WALL_INT, z0,
             material=pl, collection=coll)

    # Lounge at x in [3.0, 5.5], y in [0.5, 5.0]
    add_wall("F1_I_LoungeS", (3.0, 0.0), (3.0, 5.0), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall_with_opening("F1_I_LoungeN", (3.0, 5.0), (5.5, 5.0),
                          h, T_WALL_INT, opening_pos=0.7, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_wall("F1_I_LoungeE", (5.5, 0.5), (5.5, 5.0), h, T_WALL_INT, z0,
             material=pl, collection=coll)

    # Stair-core walls (continue from GF)
    add_wall("F1_I_StairS", (5.9, 3.0), (8.4, 3.0), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall("F1_I_StairE", (8.4, 3.0), (8.4, 5.5), h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall_with_opening("F1_I_StairN", (5.9, 5.5), (8.4, 5.5),
                          h, T_WALL_INT, opening_pos=0.7, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    add_wall("F1_I_StairW", (5.9, 3.0), (5.9, 5.5), h, T_WALL_INT, z0,
             material=pl, collection=coll)

    # ---- STAIR FROM F1 TO TERRACE ----
    riser_h = F1_HEIGHT / 18
    tread_d = 0.25
    for i in range(9):
        add_box(f"F1_Stair_F1_{i}",
                (1.0, tread_d, riser_h * (i + 1)),
                (6.4, 3.0 + tread_d / 2 + i * tread_d, z0 + riser_h * (i + 1) / 2),
                material=M["TimberJoinery"], collection=coll)
    add_box("F1_Stair_Landing",
            (1.0, 1.0, 0.05),
            (6.4, 3.0 + 9 * tread_d + 0.5, z0 + 9 * riser_h - 0.025 + 0.05),
            material=M["TimberJoinery"], collection=coll)
    landing_top_z = z0 + 9 * riser_h
    for i in range(9):
        z_top = landing_top_z + riser_h * (i + 1)
        z_center = (landing_top_z + z_top) / 2
        add_box(f"F1_Stair_F2_{i}",
                (1.0, tread_d, z_top - landing_top_z + 0.02),
                (7.4, 3.0 + 9 * tread_d + 1.0 - tread_d / 2 - i * tread_d, z_center),
                material=M["TimberJoinery"], collection=coll)

    # ---- WRAP BALCONY (E + N + S) ----
    # E balcony: x in [HX, HX+1.5], y in [0, HY]
    add_box("F1_BalconyE_Slab", (1.5, HY, 0.15),
            (HX + 0.75, HY / 2, z0 - 0.075),
            material=M["RCC"], collection=coll)
    add_box("F1_BalconyE_RailE", (0.05, HY, 1.0),
            (HX + 1.5, HY / 2, z0 + 0.5),
            material=M["TimberJoinery"], collection=coll)
    # N balcony: x in [0, HX], y in [HY, HY+1.5]
    add_box("F1_BalconyN_Slab", (HX, 1.5, 0.15),
            (HX / 2, HY + 0.75, z0 - 0.075),
            material=M["RCC"], collection=coll)
    add_box("F1_BalconyN_RailN", (HX, 0.05, 1.0),
            (HX / 2, HY + 1.5, z0 + 0.5),
            material=M["TimberJoinery"], collection=coll)
    # S balcony: x in [3.0, HX], y in [-1.5, 0]    (W cantilever-shadowed; stops at x=3 because W extension is at 0)
    # Actually balcony stops where extension starts. Extension is on W (x<0) so balcony can be full HX wide.
    add_box("F1_BalconyS_Slab", (HX, 1.5, 0.15),
            (HX / 2, -0.75, z0 - 0.075),
            material=M["RCC"], collection=coll)
    add_box("F1_BalconyS_RailS", (HX, 0.05, 1.0),
            (HX / 2, -1.5, z0 + 0.5),
            material=M["TimberJoinery"], collection=coll)
    # Corner balcony: NE
    add_box("F1_BalconyNE_Slab", (1.5, 1.5, 0.15),
            (HX + 0.75, HY + 0.75, z0 - 0.075),
            material=M["RCC"], collection=coll)
    # SE corner
    add_box("F1_BalconySE_Slab", (1.5, 1.5, 0.15),
            (HX + 0.75, -0.75, z0 - 0.075),
            material=M["RCC"], collection=coll)

    # ---- FURNITURE ----
    # Master bed (queen 6x7 ft = 1.83 x 2.13 m)
    add_box("F1_MasterBed", (1.83, 2.13, 0.55),
            (12.5, 4.0, z0 + 0.275),
            material=M["Fabric"], collection=coll)
    add_box("F1_MasterNS_L", (0.5, 0.5, 0.55),
            (11.4, 3.5, z0 + 0.275),
            material=M["TimberJoinery"], collection=coll)
    add_box("F1_MasterNS_R", (0.5, 0.5, 0.55),
            (11.4, 4.5, z0 + 0.275),
            material=M["TimberJoinery"], collection=coll)
    # WIW shelving
    add_box("F1_WIW_Shelf", (1.5, 0.5, 2.0),
            (12.5, 3.5, z0 + 1.0),
            material=M["TimberJoinery"], collection=coll)

    # BR2 bed
    add_box("F1_BR2Bed", (1.5, 2.0, 0.5),
            (12.5, 7.5, z0 + 0.25),
            material=M["Fabric"], collection=coll)
    # BR3 bed
    add_box("F1_BR3Bed", (1.5, 2.0, 0.5),
            (4.0, 7.5, z0 + 0.25),
            material=M["Fabric"], collection=coll)
    # Lounge sofa
    add_box("F1_LoungeSofa", (2.0, 0.8, 0.4),
            (4.5, 1.5, z0 + 0.2),
            material=M["Fabric"], collection=coll)

    # Workshop furnishings (in cantilever, x in [-3, 0], y in [0, 10])
    # Two long worktables
    add_box("F1_Workshop_Table_S", (2.0, 1.0, 0.85),
            (-1.5, 2.5, z0 + 0.425),
            material=M["TimberJoinery"], collection=coll)
    add_box("F1_Workshop_Table_N", (2.0, 1.0, 0.85),
            (-1.5, 7.0, z0 + 0.425),
            material=M["TimberJoinery"], collection=coll)
    # Utility sink (north end)
    add_box("F1_Workshop_Sink", (1.2, 0.6, 0.92),
            (-1.5, 9.4, z0 + 0.46),
            material=M["Steel"], collection=coll)
    # Drying rack frames (south end)
    for i in range(3):
        add_box(f"F1_Workshop_DryRack_{i}", (0.05, 1.5, 1.6),
                (-2.5 + i * 0.3, 0.8, z0 + 0.8),
                material=M["Steel"], collection=coll)
    # Dye / silk storage shelving along W wall
    add_box("F1_Workshop_Storage", (0.5, 6.0, 2.0),
            (-2.7, 5.0, z0 + 1.0),
            material=M["TimberJoinery"], collection=coll)


# =====================================================================
# 7. TERRACE
# =====================================================================

def build_terrace(coll, M):
    z0 = T_FFL
    pl = M["LimePlaster"]

    # Slab over F1
    add_box("T_Slab_Main", (HX, HY, T_SLAB),
            (HX / 2, HY / 2, z0 - T_SLAB / 2),
            material=M["RCC"], collection=coll)
    # Cantilever slab IS the workshop ceiling -- workshop has its own roof,
    # so we add a separate flat-roof slab over the cantilever:
    add_box("T_Slab_Cantilever", (CANT_W, CANT_Y, T_SLAB),
            (-CANT_W / 2, CANT_Y / 2, z0 - T_SLAB / 2),
            material=M["RCC"], collection=coll)
    # Membrane finish over main terrace (excluding viewing-room footprint and burjeel base)
    add_plane("T_Membrane", (HX, HY), (HX / 2, HY / 2, z0 + 0.005),
              material=M["Membrane"], collection=coll)

    # ---- PARAPET (around main terrace) ----
    add_wall("T_ParapetS", (0.0, 0.0), (HX, 0.0), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)
    add_wall("T_ParapetN", (0.0, HY), (HX, HY), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)
    add_wall("T_ParapetE", (HX, 0.0), (HX, HY), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)
    add_wall("T_ParapetW", (0.0, 0.0), (0.0, HY), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)
    # Cantilever parapet
    add_wall("T_ParapetCantS", (-CANT_W, 0.0), (0.0, 0.0), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)
    add_wall("T_ParapetCantN", (-CANT_W, CANT_Y), (0.0, CANT_Y), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)
    add_wall("T_ParapetCantW", (-CANT_W, 0.0), (-CANT_W, CANT_Y), PARAPET_H, T_PARAPET, z0,
             material=pl, collection=coll)

    # ---- VIEWING ROOM (NE corner of terrace, 6.1 x 6.1, ceiling 3.35 m) ----
    vrx0, vry0 = HX - 6.1, HY - 6.1
    vrx1, vry1 = HX, HY
    vh = 3.35
    # Solid south wall (AAC)
    add_wall("T_VR_S", (vrx0, vry0), (vrx1, vry0), vh, T_WALL_EXT, z0,
             material=pl, collection=coll)
    # Solid west wall (AAC)
    add_wall("T_VR_W", (vrx0, vry0), (vrx0, vry1), vh, T_WALL_EXT, z0,
             material=pl, collection=coll)
    # Glazed north wall (full height)
    add_box("T_VR_N_Glass", (6.1, 0.06, vh - 0.05),
            ((vrx0 + vrx1) / 2, vry1, z0 + vh / 2),
            material=M["Glass"], collection=coll)
    # Glazed east wall (full height)
    add_box("T_VR_E_Glass", (0.06, 6.1, vh - 0.05),
            (vrx1, (vry0 + vry1) / 2, z0 + vh / 2),
            material=M["Glass"], collection=coll)
    # Roof slab
    add_box("T_VR_Roof", (6.1, 6.1, T_SLAB),
            ((vrx0 + vrx1) / 2, (vry0 + vry1) / 2, z0 + vh + T_SLAB / 2),
            material=M["RCC"], collection=coll)
    # Deep south overhang (1.5 m projection south)
    add_box("T_VR_Overhang_S", (6.1, 1.5, 0.15),
            ((vrx0 + vrx1) / 2, vry0 - 0.75, z0 + vh + T_SLAB),
            material=M["RCC"], collection=coll)
    # Floor finish
    add_plane("T_VR_Floor", (6.0, 6.0),
              ((vrx0 + vrx1) / 2, (vry0 + vry1) / 2, z0 + 0.012),
              material=M["Marble"], collection=coll)
    # Loungers inside
    for i in range(3):
        add_box(f"T_VR_Lounger_{i}", (1.8, 0.7, 0.4),
                (vrx0 + 1.0, vry0 + 1.5 + i * 1.7, z0 + 0.2),
                material=M["Fabric"], collection=coll)
    # Coffee table
    add_box("T_VR_CoffeeTable", (0.9, 0.9, 0.4),
            (vrx0 + 3.0, vry0 + 3.0, z0 + 0.2),
            material=M["TimberJoinery"], collection=coll)

    # ---- STAIR / ELEVATOR WEATHERPROOF LANDING ----
    # 3 x 3 m enclosure around the stair head (centered on stair core x in [5.9, 8.4], y in [3.0, 7.5])
    # We'll place it at x in [5.9, 8.9], y in [4.5, 7.5]
    se_h = 2.6
    add_wall("T_SE_S", (5.9, 4.5), (8.9, 4.5), se_h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall("T_SE_N", (5.9, 7.5), (8.9, 7.5), se_h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall("T_SE_W", (5.9, 4.5), (5.9, 7.5), se_h, T_WALL_INT, z0,
             material=pl, collection=coll)
    add_wall_with_opening("T_SE_E", (8.9, 4.5), (8.9, 7.5),
                          se_h, T_WALL_INT, opening_pos=1.0, opening_w=1.0,
                          opening_bottom=0.0, opening_top=DOOR_H,
                          z_base=z0, material=pl, collection=coll)
    # Stair-enclosure roof
    add_box("T_SE_Roof", (3.0, 3.0, T_SLAB),
            (7.4, 6.0, z0 + se_h + T_SLAB / 2),
            material=M["RCC"], collection=coll)

    # ---- ROOFTOP GARDEN BEDS ----
    bed_specs = [
        ("Bed_NW",  (1.5, 4.0, 0.5), (3.0, HY - 2.5, z0 + 0.25)),
        ("Bed_W",   (1.5, 4.0, 0.5), (1.0, 4.5, z0 + 0.25)),
        ("Bed_S",   (4.0, 1.2, 0.5), (3.5, 1.0, z0 + 0.25)),
        ("Bed_NE",  (1.2, 1.5, 0.5), (HX - 0.8, vry0 - 1.0, z0 + 0.25)),
    ]
    for nm, sz, loc in bed_specs:
        add_box(f"T_GardenBed_{nm}", sz, loc,
                material=M["Soil"], collection=coll)
        # Add a few low-poly plants
        for i in range(int(sz[0] * sz[1] * 1.5)):
            px = loc[0] + (i % 3 - 1) * sz[0] / 4
            py = loc[1] + (i // 3 % 3 - 1) * sz[1] / 4
            add_box(f"T_Plant_{nm}_{i}", (0.18, 0.18, 0.35),
                    (px, py, z0 + 0.5 + 0.175),
                    material=M["Greenery"], collection=coll)

    # ---- WORKSHOP NORTH-CLERESTORY MONITOR (popping above terrace W) ----
    # On the cantilever roof, a small box that rises above terrace level for north light
    mon_x, mon_y = -1.5, CANT_Y - 0.5
    mon_h = 1.2
    # South wall (solid)
    add_box("T_WorkshopMon_S", (3.0, T_WALL_INT, mon_h),
            (mon_x, mon_y - 0.5, z0 + mon_h / 2),
            material=pl, collection=coll)
    # East + west walls (solid)
    add_box("T_WorkshopMon_W", (T_WALL_INT, 1.0, mon_h),
            (mon_x - 1.5, mon_y, z0 + mon_h / 2),
            material=pl, collection=coll)
    add_box("T_WorkshopMon_E", (T_WALL_INT, 1.0, mon_h),
            (mon_x + 1.5, mon_y, z0 + mon_h / 2),
            material=pl, collection=coll)
    # NORTH face: glass (this is the north-light source)
    add_box("T_WorkshopMon_N_Glass", (3.0, 0.04, mon_h),
            (mon_x, mon_y + 0.5, z0 + mon_h / 2),
            material=M["Glass"], collection=coll)
    # Roof (slight slope south to drain)
    add_box("T_WorkshopMon_Roof", (3.2, 1.2, 0.10),
            (mon_x, mon_y, z0 + mon_h + 0.05),
            rotation=(math.radians(-5), 0, 0),
            material=M["Membrane"], collection=coll)


# =====================================================================
# 8. ENGINEERING SYSTEMS
# =====================================================================

def build_beehive_panel_east(coll, M):
    """Beehive panel on east face GF. Centered at y=4.25, z in [0.6, 3.1]. Faces +X.
    Hex grid 12 cols x 12 rows of cones, projecting ~0.25 m east."""
    cone_dia = 0.20
    cone_depth = 0.25
    spacing_y = cone_dia
    spacing_z = cone_dia * math.sqrt(3) / 2
    n_cols, n_rows = 12, 12
    panel_x = HX
    grid_w = (n_cols - 1) * spacing_y
    grid_h = (n_rows - 1) * spacing_z
    # Center the grid in y in [3.0, 5.5] (panel width 2.5)
    panel_yc = 4.25
    panel_zb = 0.7
    y0 = panel_yc - grid_w / 2
    z0 = panel_zb + spacing_z

    # Even-row cones (rows 0, 2, 4, ...)
    bpy.ops.mesh.primitive_cone_add(
        radius1=cone_dia / 2, radius2=0.02, depth=cone_depth, vertices=8,
        location=(panel_x + 0.10 + cone_depth / 2, y0, z0))
    cone_e = bpy.context.active_object
    cone_e.name = "BeehiveE_Cone_Even"
    cone_e.rotation_euler = (0, math.radians(-90), 0)
    bpy.ops.object.transform_apply(rotation=True)
    cone_e.data.materials.append(M["TerracottaCone"])
    arr1 = cone_e.modifiers.new(name="ArrayY", type='ARRAY')
    arr1.use_relative_offset = False
    arr1.use_constant_offset = True
    arr1.constant_offset_displace = (0, spacing_y, 0)
    arr1.count = n_cols
    arr2 = cone_e.modifiers.new(name="ArrayZ", type='ARRAY')
    arr2.use_relative_offset = False
    arr2.use_constant_offset = True
    arr2.constant_offset_displace = (0, 0, 2 * spacing_z)
    arr2.count = (n_rows + 1) // 2
    link_to_collection(cone_e, coll)

    # Odd-row cones (rows 1, 3, 5, ...) offset
    bpy.ops.mesh.primitive_cone_add(
        radius1=cone_dia / 2, radius2=0.02, depth=cone_depth, vertices=8,
        location=(panel_x + 0.10 + cone_depth / 2,
                  y0 + spacing_y / 2, z0 + spacing_z))
    cone_o = bpy.context.active_object
    cone_o.name = "BeehiveE_Cone_Odd"
    cone_o.rotation_euler = (0, math.radians(-90), 0)
    bpy.ops.object.transform_apply(rotation=True)
    cone_o.data.materials.append(M["TerracottaCone"])
    arr3 = cone_o.modifiers.new(name="ArrayY", type='ARRAY')
    arr3.use_relative_offset = False
    arr3.use_constant_offset = True
    arr3.constant_offset_displace = (0, spacing_y, 0)
    arr3.count = n_cols
    arr4 = cone_o.modifiers.new(name="ArrayZ", type='ARRAY')
    arr4.use_relative_offset = False
    arr4.use_constant_offset = True
    arr4.constant_offset_displace = (0, 0, 2 * spacing_z)
    arr4.count = n_rows // 2
    link_to_collection(cone_o, coll)

    # Steel/timber frame around panel
    panel_h_total = grid_h + 2 * spacing_z + 0.2
    panel_w_total = grid_w + 2 * spacing_y + 0.2
    fx = panel_x + 0.10 + cone_depth / 2
    add_box("BeehiveE_Frame_Bot", (0.30, panel_w_total, 0.06),
            (fx, panel_yc, panel_zb - 0.03),
            material=M["Steel"], collection=coll)
    add_box("BeehiveE_Frame_Top", (0.30, panel_w_total, 0.06),
            (fx, panel_yc, panel_zb + panel_h_total),
            material=M["Steel"], collection=coll)
    add_box("BeehiveE_Frame_L", (0.30, 0.06, panel_h_total + 0.06),
            (fx, panel_yc - panel_w_total / 2, panel_zb + panel_h_total / 2),
            material=M["Steel"], collection=coll)
    add_box("BeehiveE_Frame_R", (0.30, 0.06, panel_h_total + 0.06),
            (fx, panel_yc + panel_w_total / 2, panel_zb + panel_h_total / 2),
            material=M["Steel"], collection=coll)

    # Drip line along top of panel
    add_cylinder("BeehiveE_DripLine", radius=0.012, depth=panel_w_total + 0.4,
                 location=(fx + 0.18, panel_yc, panel_zb + panel_h_total + 0.15),
                 rotation=(math.radians(90), 0, 0),
                 material=M["WaterPipe"], collection=coll)

    # Jaali screen in front of beehive panel (decorative perforated terracotta)
    # Modeled as a single thin perforated plane via plane + emissive holes (skip detail)
    # Visualized as a textured panel offset 0.4 m east
    add_box("BeehiveE_Jaali_Screen", (0.05, 2.6, 2.6),
            (panel_x + 0.55, panel_yc, panel_zb + panel_h_total / 2 - 0.05),
            material=M["TerracottaJaali"], collection=coll)
    # Add cut-out pattern: 8 x 8 small holes (modeled as small black boxes overlaid)
    for i in range(7):
        for j in range(7):
            add_box(f"BeehiveE_Jaali_Hole_{i}_{j}",
                    (0.06, 0.18, 0.18),
                    (panel_x + 0.55,
                     panel_yc - 1.05 + i * 0.30,
                     panel_zb - 0.05 + (j + 1) * 0.30),
                    material=M["Black"], collection=coll)

    # Small EC fan box (assist) at the inside (west face) of the panel
    add_box("BeehiveE_ECFan", (0.30, 0.30, 0.30),
            (panel_x - 0.20, panel_yc, panel_zb + 1.0),
            material=M["Steel"], collection=coll)


def build_beehive_panel_south(coll, M):
    """Beehive panel on south face GF. Same geometry, mirrored to face -Y."""
    cone_dia = 0.20
    cone_depth = 0.25
    spacing_x = cone_dia
    spacing_z = cone_dia * math.sqrt(3) / 2
    n_cols, n_rows = 12, 12
    panel_y = 0.0
    grid_w = (n_cols - 1) * spacing_x
    grid_h = (n_rows - 1) * spacing_z
    # Center grid in x in [10.0, 12.5]
    panel_xc = 11.25
    panel_zb = 0.7
    x0 = panel_xc - grid_w / 2
    z0 = panel_zb + spacing_z

    # Even rows
    bpy.ops.mesh.primitive_cone_add(
        radius1=cone_dia / 2, radius2=0.02, depth=cone_depth, vertices=8,
        location=(x0, panel_y - 0.10 - cone_depth / 2, z0))
    cone_e = bpy.context.active_object
    cone_e.name = "BeehiveS_Cone_Even"
    cone_e.rotation_euler = (math.radians(-90), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    cone_e.data.materials.append(M["TerracottaCone"])
    arr1 = cone_e.modifiers.new(name="ArrayX", type='ARRAY')
    arr1.use_relative_offset = False
    arr1.use_constant_offset = True
    arr1.constant_offset_displace = (spacing_x, 0, 0)
    arr1.count = n_cols
    arr2 = cone_e.modifiers.new(name="ArrayZ", type='ARRAY')
    arr2.use_relative_offset = False
    arr2.use_constant_offset = True
    arr2.constant_offset_displace = (0, 0, 2 * spacing_z)
    arr2.count = (n_rows + 1) // 2
    link_to_collection(cone_e, coll)

    # Odd rows
    bpy.ops.mesh.primitive_cone_add(
        radius1=cone_dia / 2, radius2=0.02, depth=cone_depth, vertices=8,
        location=(x0 + spacing_x / 2,
                  panel_y - 0.10 - cone_depth / 2, z0 + spacing_z))
    cone_o = bpy.context.active_object
    cone_o.name = "BeehiveS_Cone_Odd"
    cone_o.rotation_euler = (math.radians(-90), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    cone_o.data.materials.append(M["TerracottaCone"])
    arr3 = cone_o.modifiers.new(name="ArrayX", type='ARRAY')
    arr3.use_relative_offset = False
    arr3.use_constant_offset = True
    arr3.constant_offset_displace = (spacing_x, 0, 0)
    arr3.count = n_cols
    arr4 = cone_o.modifiers.new(name="ArrayZ", type='ARRAY')
    arr4.use_relative_offset = False
    arr4.use_constant_offset = True
    arr4.constant_offset_displace = (0, 0, 2 * spacing_z)
    arr4.count = n_rows // 2
    link_to_collection(cone_o, coll)

    panel_h_total = grid_h + 2 * spacing_z + 0.2
    panel_w_total = grid_w + 2 * spacing_x + 0.2
    fy = panel_y - 0.10 - cone_depth / 2
    add_box("BeehiveS_Frame_Bot", (panel_w_total, 0.30, 0.06),
            (panel_xc, fy, panel_zb - 0.03),
            material=M["Steel"], collection=coll)
    add_box("BeehiveS_Frame_Top", (panel_w_total, 0.30, 0.06),
            (panel_xc, fy, panel_zb + panel_h_total),
            material=M["Steel"], collection=coll)
    add_box("BeehiveS_Frame_L", (0.06, 0.30, panel_h_total + 0.06),
            (panel_xc - panel_w_total / 2, fy, panel_zb + panel_h_total / 2),
            material=M["Steel"], collection=coll)
    add_box("BeehiveS_Frame_R", (0.06, 0.30, panel_h_total + 0.06),
            (panel_xc + panel_w_total / 2, fy, panel_zb + panel_h_total / 2),
            material=M["Steel"], collection=coll)

    add_cylinder("BeehiveS_DripLine", radius=0.012, depth=panel_w_total + 0.4,
                 location=(panel_xc, fy - 0.18, panel_zb + panel_h_total + 0.15),
                 rotation=(0, math.radians(90), 0),
                 material=M["WaterPipe"], collection=coll)

    # Jaali screen in front
    add_box("BeehiveS_Jaali_Screen", (2.6, 0.05, 2.6),
            (panel_xc, panel_y - 0.55, panel_zb + panel_h_total / 2 - 0.05),
            material=M["TerracottaJaali"], collection=coll)
    for i in range(7):
        for j in range(7):
            add_box(f"BeehiveS_Jaali_Hole_{i}_{j}",
                    (0.18, 0.06, 0.18),
                    (panel_xc - 1.05 + i * 0.30,
                     panel_y - 0.55,
                     panel_zb - 0.05 + (j + 1) * 0.30),
                    material=M["Black"], collection=coll)

    add_box("BeehiveS_ECFan", (0.30, 0.30, 0.30),
            (panel_xc, panel_y + 0.20, panel_zb + 1.0),
            material=M["Steel"], collection=coll)


def build_burjeel(coll, M):
    """Burjeel wind catcher: 2x2 m square hollow tower, 4 m tall, atop stair-enclosure roof.
    Located at the central stair core x in [6.4, 8.4], y in [5.0, 7.0]."""
    base_x = 6.9 + 0.5
    base_y = 6.0
    bx0, by0 = base_x - 1.0, base_y - 1.0
    bx1, by1 = base_x + 1.0, base_y + 1.0
    bz = BURJEEL_BASE_Z
    bh = BURJEEL_H
    bt = 0.10  # wall thickness

    # 4 vertical walls (with louver openings on each face: 1 louver of 1.5 x 1.0 m near top)
    # For simplicity we'll model the louvers as stacked horizontal slats inside an opening
    # in each face.
    # Solid bottom 2 m of each face, then louvers in top 2 m
    # SOUTH face
    add_wall("Burjeel_S_Bot", (bx0, by0), (bx1, by0), 2.0, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_S_TopFrameL", (bx0, by0), (bx0 + 0.2, by0), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_S_TopFrameR", (bx1 - 0.2, by0), (bx1, by0), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_S_TopFrameTop", (bx0 + 0.2, by0), (bx1 - 0.2, by0),
             bh - 3.5, bt, bz + 3.5,
             material=M["LimePlaster"], collection=coll)
    # Louver slats (south face)
    for i in range(6):
        sz = 0.10
        add_box(f"Burjeel_S_Slat_{i}", (1.6, bt + 0.05, sz),
                ((bx0 + bx1) / 2, by0, bz + 2.1 + i * 0.22),
                rotation=(math.radians(20), 0, 0),
                material=M["TimberJoinery"], collection=coll)
    # NORTH face
    add_wall("Burjeel_N_Bot", (bx0, by1), (bx1, by1), 2.0, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_N_TopFrameL", (bx0, by1), (bx0 + 0.2, by1), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_N_TopFrameR", (bx1 - 0.2, by1), (bx1, by1), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_N_TopFrameTop", (bx0 + 0.2, by1), (bx1 - 0.2, by1),
             bh - 3.5, bt, bz + 3.5,
             material=M["LimePlaster"], collection=coll)
    for i in range(6):
        sz = 0.10
        add_box(f"Burjeel_N_Slat_{i}", (1.6, bt + 0.05, sz),
                ((bx0 + bx1) / 2, by1, bz + 2.1 + i * 0.22),
                rotation=(math.radians(-20), 0, 0),
                material=M["TimberJoinery"], collection=coll)
    # EAST face
    add_wall("Burjeel_E_Bot", (bx1, by0), (bx1, by1), 2.0, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_E_TopFrameL", (bx1, by0), (bx1, by0 + 0.2), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_E_TopFrameR", (bx1, by1 - 0.2), (bx1, by1), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_E_TopFrameTop", (bx1, by0 + 0.2), (bx1, by1 - 0.2),
             bh - 3.5, bt, bz + 3.5,
             material=M["LimePlaster"], collection=coll)
    for i in range(6):
        sz = 0.10
        add_box(f"Burjeel_E_Slat_{i}", (bt + 0.05, 1.6, sz),
                (bx1, (by0 + by1) / 2, bz + 2.1 + i * 0.22),
                rotation=(0, math.radians(-20), 0),
                material=M["TimberJoinery"], collection=coll)
    # WEST face
    add_wall("Burjeel_W_Bot", (bx0, by0), (bx0, by1), 2.0, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_W_TopFrameL", (bx0, by0), (bx0, by0 + 0.2), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_W_TopFrameR", (bx0, by1 - 0.2), (bx0, by1), bh, bt, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_W_TopFrameTop", (bx0, by0 + 0.2), (bx0, by1 - 0.2),
             bh - 3.5, bt, bz + 3.5,
             material=M["LimePlaster"], collection=coll)
    for i in range(6):
        sz = 0.10
        add_box(f"Burjeel_W_Slat_{i}", (bt + 0.05, 1.6, sz),
                (bx0, (by0 + by1) / 2, bz + 2.1 + i * 0.22),
                rotation=(0, math.radians(20), 0),
                material=M["TimberJoinery"], collection=coll)
    # Cap (slight pyramid)
    add_box("Burjeel_Cap", (2.4, 2.4, 0.20),
            (base_x, base_y, bz + bh + 0.10),
            material=M["Sandstone"], collection=coll)
    # Internal cross-divider (X-shape) -- just for visual indicator
    add_wall("Burjeel_Div_NS", (base_x, by0), (base_x, by1), bh - 0.1, 0.05, bz,
             material=M["LimePlaster"], collection=coll)
    add_wall("Burjeel_Div_EW", (bx0, base_y), (bx1, base_y), bh - 0.1, 0.05, bz,
             material=M["LimePlaster"], collection=coll)


def build_pv_pergola(coll, M):
    """PV pergola: 6 x 5 m platform raised 2.4 m over terrace; 15 panels (3 x 5) at 25 deg S tilt.
    Positioned to NOT block burjeel. Place at x in [0.5, 6.5], y in [0.8, 5.8], offset W of viewing room."""
    px0, py0 = 0.5, 0.8
    px1, py1 = 6.5, 5.8
    pz_top = T_FFL + 2.4
    # Posts at corners
    for cx, cy in [(px0, py0), (px1, py0), (px0, py1), (px1, py1)]:
        add_box(f"T_PV_Post_{cx}_{cy}", (0.12, 0.12, 2.4),
                (cx, cy, T_FFL + 1.2),
                material=M["Steel"], collection=coll)
    # Beams (E-W along long axis)
    add_box("T_PV_Beam_S", (px1 - px0, 0.10, 0.10),
            ((px0 + px1) / 2, py0, pz_top - 0.05),
            material=M["Steel"], collection=coll)
    add_box("T_PV_Beam_N", (px1 - px0, 0.10, 0.10),
            ((px0 + px1) / 2, py1, pz_top - 0.05),
            material=M["Steel"], collection=coll)
    add_box("T_PV_Beam_W", (0.10, py1 - py0, 0.10),
            (px0, (py0 + py1) / 2, pz_top - 0.05),
            material=M["Steel"], collection=coll)
    add_box("T_PV_Beam_E", (0.10, py1 - py0, 0.10),
            (px1, (py0 + py1) / 2, pz_top - 0.05),
            material=M["Steel"], collection=coll)
    # 15 panels: 3 rows (N-S) x 5 cols (E-W). Each panel ~1.0 (N-S) x 1.2 (E-W) m at 25 deg S tilt
    # The S edge of each panel is lower; N edge is higher. Tilt about E-W axis.
    panel_w = 1.2  # E-W
    panel_d = 1.0  # N-S
    tilt = math.radians(25)
    for col in range(5):
        for row in range(3):
            pcx = px0 + 0.3 + col * (panel_w + 0.05)
            pcy = py0 + 0.5 + row * (panel_d + 0.20)
            pcz = pz_top + 0.05
            # Tilt around X axis: rotate so the +Y (N) side goes UP, -Y (S) side goes DOWN
            add_box(f"T_PV_Panel_{col}_{row}",
                    (panel_w, panel_d, 0.04),
                    (pcx, pcy, pcz),
                    rotation=(tilt, 0, 0),
                    material=M["PVPanel"], collection=coll)


def build_systems(coll_sys, coll_terrace, M):
    """All engineering systems live in 04_Systems collection."""
    build_beehive_panel_east(coll_sys, M)
    build_beehive_panel_south(coll_sys, M)
    build_burjeel(coll_sys, M)
    build_pv_pergola(coll_sys, M)
    # Cameras (security CCTVs as small pyramid markers)
    cctv_positions = [
        ("CCTV_Gate",       (PLOT_X0 + 0.3, 5.0, 2.2)),
        ("CCTV_Driveway",   (-2.0, 5.0, 2.4)),
        ("CCTV_FrontDoor",  (HX + 0.3, 6.0, 2.2)),
        ("CCTV_NEPerim",    (PLOT_X1 - 0.3, PLOT_Y1 - 0.3, 2.2)),
        ("CCTV_SWPerim",    (PLOT_X0 + 0.3, PLOT_Y0 + 0.3, 2.2)),
        ("CCTV_Terrace",    (HX / 2, HY / 2, T_PARAPET_TOP + 0.5)),
        ("CCTV_GarageInt",  (3.0, 4.0, GF_HEIGHT - 0.3)),
    ]
    for nm, loc in cctv_positions:
        bpy.ops.mesh.primitive_cone_add(radius1=0.10, radius2=0.0, depth=0.25,
                                         vertices=8, location=loc)
        obj = bpy.context.active_object
        obj.name = nm
        obj.rotation_euler = (math.radians(90), 0, 0)
        bpy.ops.object.transform_apply(rotation=True)
        obj.data.materials.append(M["Black"])
        link_to_collection(obj, coll_sys)
    # PIR / IR beam-break sensors along boundary wall (small spheres)
    sensor_positions = [
        (PLOT_X0 + 0.3, 1.0, 1.6),
        (PLOT_X0 + 0.3, 9.0, 1.6),
        (PLOT_X1 - 0.3, 1.0, 1.6),
        (PLOT_X1 - 0.3, 9.0, 1.6),
        (4.0, PLOT_Y0 + 0.3, 1.6),
        (10.0, PLOT_Y0 + 0.3, 1.6),
        (4.0, PLOT_Y1 - 0.3, 1.6),
        (10.0, PLOT_Y1 - 0.3, 1.6),
    ]
    for i, loc in enumerate(sensor_positions):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=loc, segments=10, ring_count=8)
        obj = bpy.context.active_object
        obj.name = f"PIR_IRBeam_{i}"
        obj.data.materials.append(M["Black"])
        link_to_collection(obj, coll_sys)

    # ---- AIRFLOW ARROWS (visible only in CAM_Section_Cooling) ----
    # 5 arrows tracing path: outside east -> beehive -> living -> stair void -> burjeel
    arrow_pts = [
        ((HX + 1.5, 4.5, 1.5), (HX - 0.5, 4.5, 1.5),  "Arrow_BeehiveIn"),     # east intake
        ((HX - 0.5, 4.5, 1.5), (8.5, 4.5, 1.5),       "Arrow_Living"),         # through living
        ((8.5, 4.5, 1.5),     (7.5, 4.5, 3.0),        "Arrow_StairBase"),      # to stair core
        ((7.5, 4.5, 3.0),     (7.5, 6.0, 6.0),        "Arrow_StairUp"),        # rise through stack
        ((7.5, 6.0, 7.0),     (7.5, 6.0, BURJEEL_TOP - 0.3), "Arrow_BurjeelOut"),  # out burjeel
    ]
    for start, end, nm in arrow_pts:
        sx, sy, sz = start; ex, ey, ez = end
        cx, cy, cz = (sx+ex)/2, (sy+ey)/2, (sz+ez)/2
        length = math.sqrt((ex-sx)**2 + (ey-sy)**2 + (ez-sz)**2)
        # Cylinder shaft
        bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=length * 0.85,
                                             vertices=10,
                                             location=(cx, cy, cz))
        obj = bpy.context.active_object
        obj.name = nm + "_Shaft"
        # Orient cylinder along the direction from start to end (default cylinder axis is +Z)
        direction = Vector((ex-sx, ey-sy, ez-sz))
        obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        obj.data.materials.append(M["AirflowArrow"])
        link_to_collection(obj, coll_sys)
        # Cone tip at end
        bpy.ops.mesh.primitive_cone_add(radius1=0.20, radius2=0, depth=0.3,
                                         vertices=10,
                                         location=(ex, ey, ez))
        tip = bpy.context.active_object
        tip.name = nm + "_Tip"
        tip.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        tip.data.materials.append(M["AirflowArrow"])
        link_to_collection(tip, coll_sys)
        # Mark these as section-only (we'll hide them in render_all for non-section cams)
        for o in (obj, tip):
            o["section_only"] = True


# =====================================================================
# 9. CAMERAS
# =====================================================================

def make_camera(name, location, look_at, lens=35.0, ortho=False, ortho_scale=20.0,
                clip_start=0.1, clip_end=200.0, collection=None):
    cam_data = bpy.data.cameras.new(name)
    cam_obj = bpy.data.objects.new(name, cam_data)
    cam_obj.location = location
    direction = Vector(look_at) - Vector(location)
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = lens
    cam_data.clip_start = clip_start
    cam_data.clip_end = clip_end
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.type = 'PERSP'
    if collection:
        collection.objects.link(cam_obj)
    else:
        bpy.context.scene.collection.objects.link(cam_obj)
    return cam_obj


def build_cameras(coll):
    cams = {}
    # Hero: outside plot east + slightly south, eye-level, sees full east facade + lawn
    cams["CAM_East_Hero"] = make_camera(
        "CAM_East_Hero",
        location=(HX + 10, -3, 7),
        look_at=(HX / 2, HY / 2, 4),
        lens=28, collection=coll)
    # West service: outside plot west, sees garage + gate + driveway
    cams["CAM_West_Service"] = make_camera(
        "CAM_West_Service",
        location=(-DRIVEWAY_W - 3, HY / 2, 5),
        look_at=(3, HY / 2, 3),
        lens=35, collection=coll)
    # Aerial NE: high above NE corner, 45° down, full massing
    cams["CAM_Aerial_NE"] = make_camera(
        "CAM_Aerial_NE",
        location=(HX + 10, HY + 10, 20),
        look_at=(HX / 2, HY / 2, 4),
        lens=28, collection=coll)
    # Section: ortho looking +Y; clip_start = 30 → cut just inside south face (Y=0)
    cams["CAM_Section_Cooling"] = make_camera(
        "CAM_Section_Cooling",
        location=(HX / 2, -30, 4),
        look_at=(HX / 2, 5, 4),
        ortho=True, ortho_scale=22,
        clip_start=31, clip_end=75,
        collection=coll)
    # Plan cameras: centred on extended footprint incl. cantilever
    plan_cx = (HX - CANT_W) / 2   # x-centre including west cantilever
    cams["CAM_GroundPlan_Top"] = make_camera(
        "CAM_GroundPlan_Top",
        location=(HX / 2, HY / 2, 20),
        look_at=(HX / 2, HY / 2, 0),
        ortho=True, ortho_scale=24, collection=coll)
    cams["CAM_FirstPlan_Top"] = make_camera(
        "CAM_FirstPlan_Top",
        location=(plan_cx, HY / 2, 20),
        look_at=(plan_cx, HY / 2, 0),
        ortho=True, ortho_scale=24, collection=coll)
    cams["CAM_TerracePlan_Top"] = make_camera(
        "CAM_TerracePlan_Top",
        location=(HX / 2, HY / 2, 22),
        look_at=(HX / 2, HY / 2, 0),
        ortho=True, ortho_scale=24, collection=coll)
    return cams


# =====================================================================
# 10. PLAN-VIEW LABELS (text objects for top-down cameras)
# =====================================================================

def build_plan_labels(coll, M):
    """3D text labels for room identification in plan-view renders.
    Placed at appropriate Z heights so they only show in their matching plan camera.
    Uses three sub-collections so render_all can toggle them."""
    label_mat = M["LabelText"]
    # Ground floor labels at z = 1.5 (inside GF rooms)
    gf_labels = [
        ("L_GF_Garage",   "GARAGE",            (3.0, 4.0, 1.5)),
        ("L_GF_Foyer",    "FOYER",             (HX - 0.8, 6.0, 1.5)),
        ("L_GF_Kitchen",  "KITCHEN+DINING",    (10.0, 8.5, 1.5)),
        ("L_GF_Living",   "LIVING",            (10.5, 5.0, 1.5)),
        ("L_GF_Guest",    "GUEST + BATH",      (12.5, 1.5, 1.5)),
        ("L_GF_Stair",    "STAIR/LIFT",        (7.2, 6.5, 1.5)),
        ("L_GF_Powder",   "PWD",               (9.3, 4.2, 1.5)),
    ]
    gf_coll = make_collection("Labels_GF", parent=coll)
    for nm, body, loc in gf_labels:
        add_text(nm, body, loc, size=0.35, rotation=(0, 0, 0),
                 material=label_mat, collection=gf_coll)

    # First floor labels at z = F1_FFL + 1.5
    f1_labels = [
        ("L_F1_Master",   "MASTER + WIW (3.35m)", (12.0, 3.5, F1_FFL + 1.5)),
        ("L_F1_MBath",    "M.BATH",            (10.0, 1.5, F1_FFL + 1.5)),
        ("L_F1_BR2",      "BEDROOM 2",         (12.5, 7.5, F1_FFL + 1.5)),
        ("L_F1_BR3",      "BEDROOM 3",         (4.5, 7.5, F1_FFL + 1.5)),
        ("L_F1_Lounge",   "LOUNGE",            (4.5, 2.5, F1_FFL + 1.5)),
        ("L_F1_Stair",    "STAIR/LIFT",        (7.2, 4.5, F1_FFL + 1.5)),
        ("L_F1_Workshop", "ART WORKSHOP\n(N-clerestory)", (-1.5, 5.0, F1_FFL + 1.5)),
        ("L_F1_BalcE",    "WRAP BALCONY",      (HX + 0.8, 5.0, F1_FFL + 1.5)),
    ]
    f1_coll = make_collection("Labels_F1", parent=coll)
    for nm, body, loc in f1_labels:
        add_text(nm, body, loc, size=0.32, rotation=(0, 0, 0),
                 material=label_mat, collection=f1_coll)

    # Terrace labels at z = T_FFL + 1.5
    t_labels = [
        ("L_T_Viewing",   "VIEWING ROOM\n(3.35m, low-e glass)",
                          (HX - 3.0, HY - 3.0, T_FFL + 1.5)),
        ("L_T_Stair",     "STAIR/LIFT\nLANDING", (7.4, 6.0, T_FFL + 1.5)),
        ("L_T_Burjeel",   "BURJEEL",           (7.4, 6.0, BURJEEL_TOP + 0.3)),
        ("L_T_PV",        "PV PERGOLA\n6 kWp", (3.5, 3.0, T_FFL + 3.5)),
        ("L_T_Garden",    "ROOF GARDEN",       (3.5, HY - 2.5, T_FFL + 1.5)),
        ("L_T_Monitor",   "WORKSHOP N-CLERESTORY",
                          (-1.5, CANT_Y - 1.0, T_FFL + 2.0)),
    ]
    t_coll = make_collection("Labels_T", parent=coll)
    for nm, body, loc in t_labels:
        add_text(nm, body, loc, size=0.32, rotation=(0, 0, 0),
                 material=label_mat, collection=t_coll)

    return gf_coll, f1_coll, t_coll


# =====================================================================
# 11. RENDER HELPER
# =====================================================================

def _set_collection_visible(coll_name, visible):
    """Toggle viewport + render visibility of a collection by name."""
    coll = bpy.data.collections.get(coll_name)
    if coll is None:
        return
    # Render visibility via collection
    for vlayer in bpy.context.scene.view_layers:
        lc = _find_layer_collection(vlayer.layer_collection, coll_name)
        if lc:
            lc.exclude = not visible
            lc.hide_viewport = not visible


def _find_layer_collection(layer_coll, name):
    if layer_coll.name == name:
        return layer_coll
    for c in layer_coll.children:
        r = _find_layer_collection(c, name)
        if r:
            return r
    return None


def _set_section_only_visible(visible):
    """Show/hide all objects flagged with section_only=True."""
    for obj in bpy.data.objects:
        if obj.get("section_only"):
            obj.hide_render = not visible
            obj.hide_viewport = not visible


def render_all(out_dir=RENDER_DIR):
    """Render all 7 named cameras to PNG in out_dir.
    Toggles per-camera collection visibility as needed."""
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    cameras_in_order = [
        "CAM_East_Hero",
        "CAM_West_Service",
        "CAM_Aerial_NE",
        "CAM_Section_Cooling",
        "CAM_GroundPlan_Top",
        "CAM_FirstPlan_Top",
        "CAM_TerracePlan_Top",
    ]

    # Visibility plan per camera:
    #   floors: 01_Ground / 02_First / 03_Terrace
    #   labels: Labels_GF / Labels_F1 / Labels_T
    #   systems: 04_Systems
    #   site:   00_Site
    # Hero, Service, Aerial: all floors visible, no labels, systems visible, site visible.
    # Section_Cooling: all floors, NO labels, systems visible (incl airflow arrows).
    # GroundPlan_Top: only GF + GF labels + GF-relevant systems (beehive panels visible since they're at GF height) + site OFF.
    # FirstPlan_Top: only F1 + F1 labels.
    # TerracePlan_Top: only Terrace + T labels.

    plan = {
        "CAM_East_Hero":      dict(gf=True, f1=True, t=True, site=True, sys=True,
                                    lab_gf=False, lab_f1=False, lab_t=False, section=False),
        "CAM_West_Service":   dict(gf=True, f1=True, t=True, site=True, sys=True,
                                    lab_gf=False, lab_f1=False, lab_t=False, section=False),
        "CAM_Aerial_NE":      dict(gf=True, f1=True, t=True, site=True, sys=True,
                                    lab_gf=False, lab_f1=False, lab_t=False, section=False),
        "CAM_Section_Cooling":dict(gf=True, f1=True, t=True, site=False, sys=True,
                                    lab_gf=False, lab_f1=False, lab_t=False, section=True),
        "CAM_GroundPlan_Top": dict(gf=True, f1=False, t=False, site=False, sys=True,
                                    lab_gf=True, lab_f1=False, lab_t=False, section=False),
        "CAM_FirstPlan_Top":  dict(gf=False, f1=True, t=False, site=False, sys=False,
                                    lab_gf=False, lab_f1=True, lab_t=False, section=False),
        "CAM_TerracePlan_Top":dict(gf=False, f1=False, t=True, site=False, sys=True,
                                    lab_gf=False, lab_f1=False, lab_t=True, section=False),
    }

    scene = bpy.context.scene
    for i, cam_name in enumerate(cameras_in_order):
        cam = bpy.data.objects.get(cam_name)
        if cam is None:
            print(f"  [skip] camera not found: {cam_name}")
            continue
        scene.camera = cam
        cfg = plan[cam_name]
        _set_collection_visible("00_Site",  cfg["site"])
        _set_collection_visible("01_Ground", cfg["gf"])
        _set_collection_visible("02_First",  cfg["f1"])
        _set_collection_visible("03_Terrace", cfg["t"])
        _set_collection_visible("04_Systems", cfg["sys"])
        _set_collection_visible("Labels_GF", cfg["lab_gf"])
        _set_collection_visible("Labels_F1", cfg["lab_f1"])
        _set_collection_visible("Labels_T",  cfg["lab_t"])
        _set_section_only_visible(cfg["section"])

        # Per-camera world strength: plan/section views need brighter background
        is_plan = cam_name in ("CAM_GroundPlan_Top", "CAM_FirstPlan_Top", "CAM_TerracePlan_Top")
        is_section = cam_name == "CAM_Section_Cooling"
        world = scene.world
        bg_node = (world.node_tree.nodes.get("Background")
                   if world and world.use_nodes else None)
        if bg_node:
            if is_plan:
                bg_node.inputs[1].default_value = 4.0
            elif is_section:
                bg_node.inputs[1].default_value = 2.5
            else:
                bg_node.inputs[1].default_value = 1.8

        out_path = os.path.join(out_dir, f"{i + 1:02d}_{cam_name}.png")
        scene.render.filepath = out_path
        print(f"  Rendering -> {out_path}")
        bpy.ops.render.render(write_still=True)

    # Restore world strength and visibility after batch
    if bg_node:
        bg_node.inputs[1].default_value = 1.8
    for nm in ["00_Site", "01_Ground", "02_First", "03_Terrace", "04_Systems",
               "Labels_GF", "Labels_F1", "Labels_T"]:
        _set_collection_visible(nm, True)
    _set_section_only_visible(False)
    print("Render batch complete.")


# =====================================================================
# 12. BUILD ENTRY POINT
# =====================================================================

def build_all():
    print("Lucknow smart-home build starting...")
    clear_scene()
    setup_scene_units_and_render()
    setup_world_sky()

    # Top-level collections
    coll_site    = make_collection("00_Site")
    coll_ground  = make_collection("01_Ground")
    coll_first   = make_collection("02_First")
    coll_terrace = make_collection("03_Terrace")
    coll_systems = make_collection("04_Systems")
    coll_cameras = make_collection("05_Cameras")
    coll_lights  = make_collection("06_Lighting")

    M = build_materials()
    setup_sun_light(coll_lights)

    build_site(coll_site, M)
    build_ground_floor(coll_ground, coll_systems, M)
    build_first_floor(coll_first, M)
    build_terrace(coll_terrace, M)
    build_systems(coll_systems, coll_terrace, M)
    build_cameras(coll_cameras)
    build_plan_labels(coll_cameras, M)

    # Set Hero camera as active by default
    hero = bpy.data.objects.get("CAM_East_Hero")
    if hero:
        bpy.context.scene.camera = hero

    # Save .blend
    save_dir = os.path.dirname(SAVE_PATH)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir)
    bpy.ops.wm.save_as_mainfile(filepath=SAVE_PATH)
    print(f"Scene saved: {SAVE_PATH}")
    print("Call render_all() to produce the 7 renders.")


if __name__ == "__main__":
    build_all()
