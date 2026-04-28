"""Blender headless PBR material setup for eyewear GLB assets.

Run via:
  blender --background --python setup_materials.py -- input.glb output.glb acetate_gloss /path/to/texture.png

Supports all material presets defined in pipeline/materials.py.
Outputs a GLB with embedded PBR materials and textures.
"""
import sys
import math
import bpy


MATERIAL_PRESETS = {
    "acetate_gloss": {
        "base_color": None, "metallic": 0.0, "roughness": 0.15,
        "ior": 1.49, "clearcoat": 0.8, "clearcoat_roughness": 0.05,
        "transmission": 0.0, "specular": 0.5,
    },
    "acetate_matte": {
        "base_color": None, "metallic": 0.0, "roughness": 0.65,
        "ior": 1.49, "clearcoat": 0.0, "transmission": 0.0,
    },
    "metal_polished": {
        "base_color": (0.85, 0.85, 0.88, 1.0), "metallic": 1.0,
        "roughness": 0.05, "anisotropic": 0.3,
    },
    "metal_brushed": {
        "base_color": (0.78, 0.78, 0.80, 1.0), "metallic": 1.0,
        "roughness": 0.30, "anisotropic": 0.8,
    },
    "titanium": {
        "base_color": (0.72, 0.70, 0.68, 1.0), "metallic": 1.0,
        "roughness": 0.20, "anisotropic": 0.5,
    },
    "plastic_matte": {
        "base_color": None, "metallic": 0.0, "roughness": 0.70, "specular": 0.3,
    },
    "wood": {
        "base_color": None, "metallic": 0.0, "roughness": 0.60, "specular": 0.1,
    },
    "lens_transparent": {
        "base_color": (0.95, 0.97, 1.0, 0.08), "metallic": 0.0,
        "roughness": 0.02, "ior": 1.52, "transmission": 0.95, "alpha": 0.08,
    },
    "lens_tinted_grey": {
        "base_color": (0.18, 0.20, 0.22, 0.35), "metallic": 0.0,
        "roughness": 0.03, "ior": 1.52, "transmission": 0.60, "alpha": 0.35,
    },
}


def parse_args():
    argv = sys.argv
    try:
        sep = argv.index("--")
        args = argv[sep + 1:]
    except ValueError:
        args = []
    input_path = args[0] if len(args) > 0 else ""
    output_path = args[1] if len(args) > 1 else ""
    material_type = args[2] if len(args) > 2 else "acetate_gloss"
    texture_path = args[3] if len(args) > 3 else ""
    return input_path, output_path, material_type, texture_path


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
    else:
        bpy.ops.wm.obj_import(filepath=filepath)


def get_mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def load_texture(texture_path: str):
    if not texture_path:
        return None
    try:
        img = bpy.data.images.load(texture_path, check_existing=True)
        img.colorspace_settings.name = "sRGB"
        return img
    except Exception as e:
        print(f"[setup_materials] Could not load texture {texture_path}: {e}")
        return None


def build_principled_material(name: str, preset: dict, texture_image=None):
    """Create a new Blender material with Principled BSDF from a preset dict."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (600, 0)

    # Principled BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    # Base color — from texture or solid
    if texture_image and preset.get("base_color") is None:
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.location = (-300, 100)
        tex_node.image = texture_image
        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
        links.new(tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])
    elif preset.get("base_color") is not None:
        bsdf.inputs["Base Color"].default_value = preset["base_color"]
    else:
        # Default mid-grey
        bsdf.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1.0)

    # Scalar inputs mapping
    scalar_map = {
        "metallic": "Metallic",
        "roughness": "Roughness",
        "ior": "IOR",
        "specular": "Specular",
        "clearcoat": "Clearcoat",
        "clearcoat_roughness": "Clearcoat Roughness",
        "transmission": "Transmission",
        "alpha": "Alpha",
        "anisotropic": "Anisotropic",
        "anisotropic_rotation": "Anisotropic Rotation",
        "subsurface": "Subsurface",
    }
    for key, bsdf_input in scalar_map.items():
        if key in preset and bsdf_input in bsdf.inputs:
            bsdf.inputs[bsdf_input].default_value = float(preset[key])

    # Transmission materials need special blend mode
    if preset.get("transmission", 0) > 0.3:
        mat.blend_method = "BLEND"
        mat.shadow_method = "NONE"
        mat.show_transparent_back = False

    return mat


def assign_material_to_all(objs, mat):
    """Assign material to all mesh objects (replace slot 0)."""
    for obj in objs:
        if obj.type != "MESH":
            continue
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)


def auto_uv_unwrap(obj):
    """Smart UV unwrap if object has no UVs (needed for texture mapping)."""
    bpy.context.view_layer.objects.active = obj
    if not obj.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")


def export_glb(output_path: str):
    bpy.ops.export_scene.gltf(
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


def main():
    input_path, output_path, material_type, texture_path = parse_args()
    if not input_path or not output_path:
        print("Usage: blender --background --python setup_materials.py "
              "-- input.glb output.glb acetate_gloss [/path/to/texture.png]")
        sys.exit(1)

    preset = MATERIAL_PRESETS.get(material_type, MATERIAL_PRESETS["acetate_gloss"])
    print(f"[setup_materials] Material: {material_type}")
    print(f"[setup_materials] Texture:  {texture_path or '(none)'}")

    clear_scene()
    import_mesh(input_path)
    objs = get_mesh_objects()
    if not objs:
        print("ERROR: No mesh objects found.")
        sys.exit(1)

    texture_image = load_texture(texture_path)

    # Auto UV-unwrap objects that need it
    if texture_image:
        for obj in objs:
            auto_uv_unwrap(obj)

    mat = build_principled_material(material_type, preset, texture_image)
    assign_material_to_all(objs, mat)

    print(f"[setup_materials] Exporting to {output_path}...")
    export_glb(output_path)
    print("[setup_materials] Done.")


if __name__ == "__main__":
    main()
