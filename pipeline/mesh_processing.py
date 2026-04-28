"""Mesh processing utilities using trimesh, PyMeshLab, and Blender subprocess calls."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh


@dataclass
class MeshStats:
    vertex_count: int
    face_count: int
    tri_count: int
    is_watertight: bool
    has_nan: bool
    component_count: int
    bounding_box_mm: dict


def analyze_mesh(mesh_path: Path) -> MeshStats:
    """Compute geometric statistics for a mesh file."""
    mesh = _load_mesh(mesh_path)

    bounds = mesh.bounds
    bb = {
        "width_mm": round(float(bounds[1][0] - bounds[0][0]), 2),
        "height_mm": round(float(bounds[1][1] - bounds[0][1]), 2),
        "depth_mm": round(float(bounds[1][2] - bounds[0][2]), 2),
    }

    # Count connected components
    try:
        components = trimesh.graph.connected_components(mesh.face_adjacency, min_len=3)
        component_count = len(components)
    except Exception:
        component_count = 1

    return MeshStats(
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        tri_count=len(mesh.triangles),
        is_watertight=mesh.is_watertight,
        has_nan=bool(np.any(np.isnan(mesh.vertices))),
        component_count=component_count,
        bounding_box_mm=bb,
    )


def run_pymeshlab_cleanup(mesh_path: Path, output_path: Path) -> Path:
    """Run PyMeshLab filter chain to clean the raw reconstruction mesh.

    Operations: remove duplicate vertices/faces, fill small holes,
    remove isolated fragments, gentle Laplacian smoothing.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pymeshlab
    except ImportError:
        raise ImportError("pymeshlab is required: pip install pymeshlab")

    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(mesh_path))

    # Remove duplicate vertices and faces
    ms.meshing_remove_duplicate_vertices()
    ms.meshing_remove_duplicate_faces()

    # Remove zero-area faces
    ms.meshing_remove_null_faces()

    # Remove isolated small pieces (noise from MVS)
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=100)

    # Close holes ≤ 500 edges (fills lens openings and gaps in temples)
    try:
        ms.meshing_close_holes(maxholesize=500, newfaceselected=False)
    except Exception:
        pass

    # Gentle Laplacian smoothing (2 iterations)
    ms.apply_coord_laplacian_smoothing(stepsmoothnum=2, boundary=True, cotangentweight=True)

    # Recompute normals consistently
    ms.meshing_re_orient_faces_coherently()

    ms.save_current_mesh(str(output_path), save_vertex_normal=True)
    return output_path


def run_blender_cleanup(
    input_glb: Path,
    output_glb: Path,
    measurements_json: dict,
    blender_bin: str,
    blender_scripts_dir: Path,
) -> bool:
    """Invoke Blender headless to run symmetry, origin, decimate operations."""
    script = blender_scripts_dir / "cleanup_mesh.py"
    if not script.exists():
        raise FileNotFoundError(f"Blender script not found: {script}")

    measurements_str = json.dumps(measurements_json)

    result = subprocess.run(
        [
            blender_bin,
            "--background",
            "--python", str(script),
            "--",
            str(input_glb),
            str(output_glb),
            measurements_str,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Blender cleanup stderr:\n{result.stderr[-2000:]}")
        return False
    return True


def run_blender_retopology(
    input_glb: Path,
    output_glb: Path,
    target_faces: int,
    blender_bin: str,
    blender_scripts_dir: Path,
) -> bool:
    """Invoke Blender headless to run voxel remesh + decimate."""
    script = blender_scripts_dir / "retopology.py"
    if not script.exists():
        raise FileNotFoundError(f"Blender script not found: {script}")

    result = subprocess.run(
        [
            blender_bin,
            "--background",
            "--python", str(script),
            "--",
            str(input_glb),
            str(output_glb),
            str(target_faces),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Blender retopology stderr:\n{result.stderr[-2000:]}")
        return False
    return True


def run_blender_materials(
    input_glb: Path,
    output_glb: Path,
    material_type: str,
    texture_path: Optional[Path],
    blender_bin: str,
    blender_scripts_dir: Path,
) -> bool:
    """Invoke Blender headless to assign PBR materials."""
    script = blender_scripts_dir / "setup_materials.py"
    if not script.exists():
        raise FileNotFoundError(f"Blender script not found: {script}")

    tex_arg = str(texture_path) if texture_path and texture_path.exists() else ""

    result = subprocess.run(
        [
            blender_bin,
            "--background",
            "--python", str(script),
            "--",
            str(input_glb),
            str(output_glb),
            material_type,
            tex_arg,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Blender materials stderr:\n{result.stderr[-2000:]}")
        return False
    return True


def run_blender_export(
    input_blend_or_glb: Path,
    output_glb: Path,
    blender_bin: str,
    blender_scripts_dir: Path,
) -> bool:
    """Invoke Blender headless to export final optimized GLB."""
    script = blender_scripts_dir / "export_glb.py"
    if not script.exists():
        raise FileNotFoundError(f"Blender script not found: {script}")

    result = subprocess.run(
        [
            blender_bin,
            "--background",
            "--python", str(script),
            "--",
            str(input_blend_or_glb),
            str(output_glb),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Blender export stderr:\n{result.stderr[-2000:]}")
        return False
    return True


# ── Private helpers ───────────────────────────────────────────────────────────

def _load_mesh(mesh_path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(mesh_path), force="mesh")
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"No mesh geometry found in {mesh_path}")
        loaded = trimesh.util.concatenate(meshes)
    return loaded
