"""Blender headless final GLB export (with optional thumbnail rendering).

Run via:
  blender --background --python export_glb.py -- input.glb output.glb
  blender --background --python export_glb.py -- input.glb thumb.png --thumbnail 512 512
"""
import sys
import math
import os
import bpy


def parse_args():
    argv = sys.argv
    try:
        sep = argv.index("--")
        args = argv[sep + 1:]
    except ValueError:
        args = []

    input_path = args[0] if len(args) > 0 else ""
    output_path = args[1] if len(args) > 1 else ""
    is_thumbnail = "--thumbnail" in args
    thumb_w = int(args[args.index("--thumbnail") + 1]) if is_thumbnail and len(args) > args.index("--thumbnail") + 1 else 512
    thumb_h = int(args[args.index("--thumbnail") + 2]) if is_thumbnail and len(args) > args.index("--thumbnail") + 2 else 512
    return input_path, output_path, is_thumbnail, thumb_w, thumb_h


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
    elif ext == "blend":
        bpy.ops.wm.open_mainfile(filepath=filepath)
    else:
        bpy.ops.wm.obj_import(filepath=filepath)


def export_glb_optimized(output_path: str):
    """Export final production GLB with Draco compression if available."""
    export_kwargs = dict(
        filepath=output_path,
        export_format="GLB",
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_colors=True,
        export_image_format="JPEG",
        export_jpeg_quality=85,
        export_apply=True,
        export_yup=True,
        use_active_scene=True,
    )

    # Try Draco compression (reduces file size ~60%)
    try:
        bpy.ops.export_scene.gltf(
            **export_kwargs,
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
        )
    except TypeError:
        # Blender version without Draco support
        bpy.ops.export_scene.gltf(**export_kwargs)


def setup_thumbnail_scene(bg_grey: float = 0.467):
    """Configure scene for front-view thumbnail render."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("ThumbnailWorld")
    scene.world.use_nodes = True
    bg_node = scene.world.node_tree.nodes["Background"]
    bg_node.inputs["Color"].default_value = (bg_grey, bg_grey, bg_grey, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0


def add_thumbnail_lighting():
    """Three-point studio lighting for thumbnail render."""
    # Key light
    bpy.ops.object.light_add(type="AREA", location=(0.3, -0.3, 0.5))
    key = bpy.context.active_object
    key.data.energy = 200
    key.data.size = 0.5
    key.rotation_euler = (math.radians(45), 0, math.radians(45))

    # Fill light
    bpy.ops.object.light_add(type="AREA", location=(-0.3, -0.2, 0.3))
    fill = bpy.context.active_object
    fill.data.energy = 80
    fill.data.size = 0.8

    # Rim light (back)
    bpy.ops.object.light_add(type="AREA", location=(0, 0.4, 0.2))
    rim = bpy.context.active_object
    rim.data.energy = 60
    rim.rotation_euler = (math.radians(-90), 0, 0)


def add_thumbnail_camera(mesh_objs, width_px: int, height_px: int):
    """Position orthographic camera to frame the model from the front."""
    if not mesh_objs:
        return

    # Compute bounding box
    all_verts = []
    for obj in mesh_objs:
        all_verts += [obj.matrix_world @ v.co for v in obj.data.vertices]

    if not all_verts:
        return

    xs = [v.x for v in all_verts]
    ys = [v.y for v in all_verts]
    zs = [v.z for v in all_verts]

    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2

    frame_w = max(xs) - min(xs)
    frame_h = max(ys) - min(ys)

    # Camera distance: far enough to frame the object with 10% margin
    margin = 1.15
    ortho_scale = max(frame_w, frame_h) * margin

    bpy.ops.object.camera_add(location=(cx, cy - 0.5, cz))
    cam_obj = bpy.context.active_object
    cam_obj.rotation_euler = (math.radians(90), 0, 0)  # Look toward +Y
    cam = cam_obj.data
    cam.type = "ORTHO"
    cam.ortho_scale = ortho_scale

    bpy.context.scene.camera = cam_obj
    bpy.context.scene.render.resolution_x = width_px
    bpy.context.scene.render.resolution_y = height_px
    bpy.context.scene.render.resolution_percentage = 100


def render_thumbnail(output_path: str, width: int, height: int):
    """Render and save the thumbnail PNG."""
    setup_thumbnail_scene()
    add_thumbnail_lighting()

    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    add_thumbnail_camera(mesh_objs, width, height)

    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)


def main():
    input_path, output_path, is_thumbnail, thumb_w, thumb_h = parse_args()
    if not input_path or not output_path:
        print("Usage: blender --background --python export_glb.py -- input.glb output.glb")
        sys.exit(1)

    clear_scene()
    import_mesh(input_path)

    if is_thumbnail:
        print(f"[export_glb] Rendering thumbnail {thumb_w}×{thumb_h} → {output_path}")
        render_thumbnail(output_path, thumb_w, thumb_h)
    else:
        print(f"[export_glb] Exporting optimized GLB → {output_path}")
        export_glb_optimized(output_path)

    print("[export_glb] Done.")


if __name__ == "__main__":
    main()
