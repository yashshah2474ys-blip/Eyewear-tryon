"""Blender headless retopology: voxel remesh + decimate for AR polygon budget.

Run via:
  blender --background --python retopology.py -- input.glb output.glb 12000
"""
import sys
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
    target_faces = int(args[2]) if len(args) > 2 else 12000
    return input_path, output_path, target_faces


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def import_mesh(filepath: str):
    ext = filepath.lower().rsplit(".", 1)[-1]
    if ext in ("glb", "gltf"):
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == "ply":
        bpy.ops.import_mesh.ply(filepath=filepath)
    elif ext == "obj":
        bpy.ops.wm.obj_import(filepath=filepath)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def get_mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def merge_all(objs):
    if not objs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    return bpy.context.active_object


def voxel_remesh(obj, voxel_size_m: float = 0.0005):
    """Voxel remesh to achieve clean, uniform topology before decimation.

    voxel_size_m = 0.5mm recommended for eyewear at 5k-15k face budget.
    """
    bpy.context.view_layer.objects.active = obj

    remesh = obj.modifiers.new(name="VoxelRemesh", type="REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = voxel_size_m
    remesh.adaptivity = 0.05
    remesh.use_smooth_shade = True

    bpy.ops.object.modifier_apply(modifier="VoxelRemesh")


def decimate_to_target(obj, target_faces: int):
    """Decimate mesh to approximately target_faces triangles."""
    current = len(obj.data.polygons)
    if current <= target_faces:
        print(f"[retopology] Already at {current} faces — no decimation needed.")
        return

    ratio = max(0.01, target_faces / current)
    decimate = obj.modifiers.new(name="Decimate", type="DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = ratio
    decimate.use_collapse_triangulate = True
    decimate.use_symmetry = True
    decimate.symmetry_axis = "X"

    bpy.ops.object.modifier_apply(modifier="Decimate")
    final_count = len(obj.data.polygons)
    print(f"[retopology] Decimated {current} → {final_count} faces (target: {target_faces})")


def triangulate(obj):
    """Ensure all polygons are triangles for GLB export compatibility."""
    bpy.context.view_layer.objects.active = obj
    tri = obj.modifiers.new(name="Triangulate", type="TRIANGULATE")
    tri.quad_method = "BEAUTY"
    tri.ngon_method = "BEAUTY"
    bpy.ops.object.modifier_apply(modifier="Triangulate")


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
    input_path, output_path, target_faces = parse_args()
    if not input_path or not output_path:
        print("Usage: blender --background --python retopology.py -- input.glb output.glb 12000")
        sys.exit(1)

    print(f"[retopology] Input:        {input_path}")
    print(f"[retopology] Output:       {output_path}")
    print(f"[retopology] Target faces: {target_faces}")

    clear_scene()
    import_mesh(input_path)

    objs = get_mesh_objects()
    if not objs:
        print("ERROR: No mesh objects found in input file.")
        sys.exit(1)

    obj = merge_all(objs)

    current_faces = len(obj.data.polygons)
    print(f"[retopology] Current face count: {current_faces}")

    # Only remesh if the mesh is very high-poly (>100k faces) to clean up topology
    if current_faces > 100_000:
        print("[retopology] Running voxel remesh (0.5mm)...")
        voxel_remesh(obj, voxel_size_m=0.0005)

    print(f"[retopology] Decimating to ~{target_faces} faces...")
    decimate_to_target(obj, target_faces)

    triangulate(obj)
    shade_smooth_auto(obj, angle_deg=30.0)

    print(f"[retopology] Exporting to {output_path}...")
    export_glb(output_path)
    print("[retopology] Done.")


if __name__ == "__main__":
    main()
