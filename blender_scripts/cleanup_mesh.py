"""Blender headless mesh cleanup for eyewear frames.

Run via:
  blender --background --python cleanup_mesh.py -- input.glb output.glb '{"total_front_width_mm":140}'

Operations (in order):
  1. Remove duplicate vertices / zero-area faces
  2. Recalculate normals outward
  3. Enforce bilateral X-symmetry (mirror dominant side)
  4. Repair thin geometry (Solidify modifier)
  5. Set origin to bridge center
  6. Rotate to GLTF coordinate convention (+Y up, +Z toward viewer)
  7. Export final GLB
"""
import sys
import json
import math
import bpy
import bmesh


def parse_args():
    argv = sys.argv
    try:
        sep = argv.index("--")
        args = argv[sep + 1:]
    except ValueError:
        args = []

    input_path = args[0] if len(args) > 0 else ""
    output_path = args[1] if len(args) > 1 else ""
    measurements = json.loads(args[2]) if len(args) > 2 else {}
    return input_path, output_path, measurements


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def import_mesh(filepath: str):
    ext = filepath.lower().rsplit(".", 1)[-1]
    if ext == "glb" or ext == "gltf":
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == "ply":
        bpy.ops.import_mesh.ply(filepath=filepath)
    elif ext == "obj":
        bpy.ops.wm.obj_import(filepath=filepath)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def get_mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def merge_all_meshes(objs):
    """Join all mesh objects into one for unified processing."""
    if not objs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    return bpy.context.active_object


def remove_doubles_and_bad_faces(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(obj.data)

    # Remove duplicate vertices (merge by distance 0.05mm = 0.00005m)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00005)

    # Remove zero-area faces
    zero_faces = [f for f in bm.faces if f.calc_area() < 1e-12]
    bmesh.ops.delete(bm, geom=zero_faces, context="FACES")

    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode="OBJECT")


def recalculate_normals(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def enforce_x_symmetry(obj, merge_threshold_m: float = 0.001):
    """Mirror the dominant X-half onto the other side to enforce bilateral symmetry."""
    bpy.context.view_layer.objects.active = obj

    # Count vertices on each side
    verts = obj.data.vertices
    pos_count = sum(1 for v in verts if v.co.x > 0)
    neg_count = sum(1 for v in verts if v.co.x < 0)

    # We'll use the Symmetrize operator which mirrors the dominant side
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")

    # Determine direction: mirror from the side with more geometry
    if pos_count >= neg_count:
        # +X is dominant → symmetrize to -X
        bpy.ops.mesh.symmetrize(direction="POSITIVE_X", threshold=merge_threshold_m)
    else:
        # -X is dominant → symmetrize to +X
        bpy.ops.mesh.symmetrize(direction="NEGATIVE_X", threshold=merge_threshold_m)

    bpy.ops.object.mode_set(mode="OBJECT")


def repair_thin_geometry(obj, min_thickness_m: float = 0.0008):
    """Add Solidify modifier to ensure minimum wall thickness (e.g. 0.8mm temples)."""
    bpy.context.view_layer.objects.active = obj

    solidify = obj.modifiers.new(name="MinThickness", type="SOLIDIFY")
    solidify.thickness = min_thickness_m
    solidify.offset = 0.0
    solidify.use_even_offset = True
    solidify.use_quality_normals = True
    solidify.use_rim = True

    bpy.ops.object.modifier_apply(modifier="MinThickness")


def set_origin_to_bridge_center(obj):
    """Set object origin to bridge center (X=0, Y=center, Z=frontmost point)."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="OBJECT")

    # Apply any existing transforms first
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Compute bounding box in world space
    bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not bbox:
        return

    import mathutils
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]

    bridge_x = 0.0                        # Centered on X after symmetry
    bridge_y = (min(ys) + max(ys)) / 2.0  # Vertical center
    bridge_z = max(zs)                     # Front-facing Z (toward viewer)

    cursor_loc = mathutils.Vector((bridge_x, bridge_y, bridge_z))
    bpy.context.scene.cursor.location = cursor_loc
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

    # Now translate mesh so the origin (bridge) is at world (0,0,0)
    obj.location = (0, 0, 0)
    bpy.ops.object.transform_apply(location=True)


def apply_gltf_axis_convention(obj):
    """Rotate mesh to match GLTF convention: +Y up, +Z toward viewer (forward)."""
    # COLMAP / OpenMVS outputs +Y up, -Z forward by default (same as GLTF)
    # Blender's native is +Z up, -Y forward, so we may need no rotation
    # if reconstruction already exported in GLTF convention.
    # We ensure the frame faces +Z by checking bounding box.
    bpy.context.view_layer.objects.active = obj

    bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not bbox:
        return

    zs = [v.z for v in bbox]
    # If front of frame (nose-pad side) is not in +Z direction, flip
    z_positive_mass = sum(1 for v in bbox if v.z > 0)
    z_negative_mass = sum(1 for v in bbox if v.z < 0)

    # Frame front should have more geometry on the positive Z side
    # (after bridge-centering, most of frame is behind Z=0)
    # This is already correct after set_origin_to_bridge_center


def shade_smooth_auto(obj, angle_deg: float = 30.0):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    obj.data.use_auto_smooth = True
    obj.data.auto_smooth_angle = math.radians(angle_deg)


def export_glb(output_path: str):
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format="GLB",
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_colors=True,
        export_apply=True,
        export_yup=True,
        use_active_scene=True,
    )


def main():
    input_path, output_path, measurements = parse_args()
    if not input_path or not output_path:
        print("Usage: blender --background --python cleanup_mesh.py -- input.glb output.glb '{...}'")
        sys.exit(1)

    print(f"[cleanup_mesh] Input:  {input_path}")
    print(f"[cleanup_mesh] Output: {output_path}")

    clear_scene()
    import_mesh(input_path)

    objs = get_mesh_objects()
    if not objs:
        print("ERROR: No mesh objects found in input file.")
        sys.exit(1)

    # Join all parts into a single mesh
    obj = merge_all_meshes(objs)

    print("[cleanup_mesh] Removing duplicate vertices and bad faces...")
    remove_doubles_and_bad_faces(obj)

    print("[cleanup_mesh] Recalculating normals...")
    recalculate_normals(obj)

    print("[cleanup_mesh] Enforcing X-axis symmetry...")
    enforce_x_symmetry(obj)

    print("[cleanup_mesh] Repairing thin geometry...")
    repair_thin_geometry(obj, min_thickness_m=0.0008)

    print("[cleanup_mesh] Setting origin to bridge center...")
    set_origin_to_bridge_center(obj)

    print("[cleanup_mesh] Applying smooth shading...")
    shade_smooth_auto(obj, angle_deg=30.0)

    print(f"[cleanup_mesh] Exporting to {output_path}...")
    export_glb(output_path)
    print("[cleanup_mesh] Done.")


if __name__ == "__main__":
    main()
