"""PBR material definitions and texture utilities for eyewear GLB assets."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


# ── Material presets (values map to GLTF PBR + Blender Principled BSDF) ────

MATERIAL_PRESETS: dict[str, dict] = {
    "acetate_gloss": {
        "base_color": None,       # Driven by baked photo texture
        "metallic": 0.0,
        "roughness": 0.15,
        "ior": 1.49,
        "subsurface": 0.02,
        "specular": 0.5,
        "clearcoat": 0.8,
        "clearcoat_roughness": 0.05,
        "transmission": 0.0,
    },
    "acetate_matte": {
        "base_color": None,
        "metallic": 0.0,
        "roughness": 0.65,
        "ior": 1.49,
        "clearcoat": 0.0,
        "transmission": 0.0,
    },
    "metal_polished": {
        "base_color": [0.85, 0.85, 0.88, 1.0],
        "metallic": 1.0,
        "roughness": 0.05,
        "specular": 1.0,
        "anisotropic": 0.3,
        "anisotropic_rotation": 0.0,
    },
    "metal_brushed": {
        "base_color": [0.78, 0.78, 0.80, 1.0],
        "metallic": 1.0,
        "roughness": 0.30,
        "anisotropic": 0.8,
        "anisotropic_rotation": 0.0,
    },
    "titanium": {
        "base_color": [0.72, 0.70, 0.68, 1.0],
        "metallic": 1.0,
        "roughness": 0.20,
        "anisotropic": 0.5,
    },
    "plastic_matte": {
        "base_color": None,
        "metallic": 0.0,
        "roughness": 0.70,
        "specular": 0.3,
        "transmission": 0.0,
    },
    "wood": {
        "base_color": None,
        "metallic": 0.0,
        "roughness": 0.60,
        "specular": 0.1,
    },
    "lens_transparent": {
        "base_color": [0.95, 0.97, 1.0, 0.08],
        "metallic": 0.0,
        "roughness": 0.02,
        "ior": 1.52,
        "transmission": 0.95,
        "alpha": 0.08,
        "blend_mode": "BLEND",
    },
    "lens_tinted_grey": {
        "base_color": [0.18, 0.20, 0.22, 0.35],
        "metallic": 0.0,
        "roughness": 0.03,
        "ior": 1.52,
        "transmission": 0.60,
        "alpha": 0.35,
        "blend_mode": "BLEND",
    },
    "lens_tinted_brown": {
        "base_color": [0.25, 0.15, 0.08, 0.35],
        "metallic": 0.0,
        "roughness": 0.03,
        "ior": 1.52,
        "transmission": 0.58,
        "alpha": 0.35,
        "blend_mode": "BLEND",
    },
    "lens_tinted_blue": {
        "base_color": [0.05, 0.15, 0.40, 0.35],
        "metallic": 0.0,
        "roughness": 0.03,
        "ior": 1.52,
        "transmission": 0.58,
        "alpha": 0.35,
        "blend_mode": "BLEND",
    },
    "lens_mirror": {
        "base_color": [0.90, 0.90, 0.92, 1.0],
        "metallic": 0.95,
        "roughness": 0.02,
        "transmission": 0.0,
    },
}

# Map from admin.html 'material' field values to pipeline preset keys
ADMIN_MATERIAL_MAP: dict[str, str] = {
    "acetate": "acetate_gloss",
    "plastic": "plastic_matte",
    "metal": "metal_polished",
    "titanium": "titanium",
    "mixed": "acetate_gloss",
    "wood": "wood",
}


def resolve_material_preset(material_value: str) -> str:
    """Map an admin.html material value to the closest MATERIAL_PRESETS key."""
    key = material_value.lower().strip()
    if key in MATERIAL_PRESETS:
        return key
    if key in ADMIN_MATERIAL_MAP:
        return ADMIN_MATERIAL_MAP[key]
    return "acetate_gloss"  # safe default


def inject_gltf_extensions(glb_path: Path, material_assignments: dict) -> Path:
    """Inject KHR_materials_clearcoat and KHR_materials_transmission into GLB.

    material_assignments: mapping of material name → preset dict from MATERIAL_PRESETS.
    Returns path to the modified GLB (overwrites in-place).
    """
    try:
        import pygltflib
    except ImportError:
        raise ImportError("pygltflib required: pip install pygltflib")

    glb = pygltflib.GLTF2().load(str(glb_path))

    if not glb.materials:
        return glb_path

    used_extensions: list[str] = list(glb.extensionsUsed or [])

    for mat in glb.materials:
        preset = material_assignments.get(mat.name or "", {})
        if not preset:
            continue

        if not hasattr(mat, "extensions") or mat.extensions is None:
            mat.extensions = {}

        if preset.get("clearcoat"):
            ext_name = "KHR_materials_clearcoat"
            mat.extensions[ext_name] = {
                "clearcoatFactor": float(preset["clearcoat"]),
                "clearcoatRoughnessFactor": float(preset.get("clearcoat_roughness", 0.05)),
            }
            if ext_name not in used_extensions:
                used_extensions.append(ext_name)

        if preset.get("transmission") and float(preset["transmission"]) > 0:
            ext_name = "KHR_materials_transmission"
            mat.extensions[ext_name] = {
                "transmissionFactor": float(preset["transmission"]),
            }
            if ext_name not in used_extensions:
                used_extensions.append(ext_name)

        if preset.get("ior"):
            ext_name = "KHR_materials_ior"
            mat.extensions[ext_name] = {"ior": float(preset["ior"])}
            if ext_name not in used_extensions:
                used_extensions.append(ext_name)

    glb.extensionsUsed = used_extensions
    glb.save(str(glb_path))
    return glb_path


def detect_material_type_from_color(color_str: str) -> str:
    """Heuristic: map a color description to a material type hint."""
    color_lower = color_str.lower()
    metal_words = {"silver", "gold", "rose gold", "gunmetal", "chrome", "titanium", "steel"}
    wood_words = {"wood", "walnut", "bamboo", "oak"}
    if any(w in color_lower for w in metal_words):
        return "metal_polished"
    if any(w in color_lower for w in wood_words):
        return "wood"
    return "acetate_gloss"
