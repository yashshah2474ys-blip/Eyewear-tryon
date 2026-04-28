"""Measurement-based scale calibration for reconstructed meshes.

Eyewear model dimensions must match real-world measurements within ±1mm.
COLMAP reconstructions are in arbitrary units; this module applies the
correct metric scale derived from user-supplied measurements.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh


@dataclass
class Measurements:
    frame_id: str
    lens_width_mm: float
    bridge_width_mm: float
    temple_length_mm: float
    lens_height_mm: Optional[float] = None
    total_front_width_mm: Optional[float] = None
    total_height_mm: Optional[float] = None
    material: str = "acetate_gloss"
    color: str = ""
    name: str = ""
    gender: str = "unisex"
    shape: str = ""

    @property
    def best_reference_width(self) -> float:
        """Return the most reliable width measurement for scale calibration."""
        if self.total_front_width_mm:
            return self.total_front_width_mm
        # Derive: left lens + bridge + right lens
        return self.lens_width_mm * 2 + self.bridge_width_mm


@dataclass
class ScaleResult:
    scale_factor: float
    actual_width_mm: float
    actual_height_mm: float
    width_error_mm: float
    height_error_mm: Optional[float]
    within_tolerance: bool


def load_measurements(measurements_path: Path) -> Measurements:
    """Load and validate measurements.json."""
    with open(measurements_path) as f:
        data = json.load(f)

    required = ["frame_id", "lens_width_mm", "bridge_width_mm", "temple_length_mm"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"measurements.json is missing required fields: {missing}")

    return Measurements(
        frame_id=data["frame_id"],
        lens_width_mm=float(data["lens_width_mm"]),
        bridge_width_mm=float(data["bridge_width_mm"]),
        temple_length_mm=float(data["temple_length_mm"]),
        lens_height_mm=float(data["lens_height_mm"]) if "lens_height_mm" in data else None,
        total_front_width_mm=float(data["total_front_width_mm"]) if "total_front_width_mm" in data else None,
        total_height_mm=float(data["total_height_mm"]) if "total_height_mm" in data else None,
        material=data.get("material", "acetate_gloss"),
        color=data.get("color", ""),
        name=data.get("name", ""),
        gender=data.get("gender", "unisex"),
        shape=data.get("shape", ""),
    )


def compute_scale_factor_from_mesh(
    mesh_path: Path,
    measurements: Measurements,
) -> tuple[float, float]:
    """Compute scale factor (mm per mesh unit) from mesh bounding box vs. measurements.

    Returns (scale_factor, confidence) where confidence ∈ [0, 1].
    Uses total_front_width as ground truth because it spans the full X axis of the frame.
    """
    mesh = _load_mesh(mesh_path)

    bounds = mesh.bounds  # [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    mesh_width = float(bounds[1][0] - bounds[0][0])

    if mesh_width < 1e-6:
        raise ValueError(
            "Mesh has zero or near-zero X extent. "
            "The reconstruction may have failed to capture the front face."
        )

    reference_mm = measurements.best_reference_width
    scale_factor = reference_mm / mesh_width

    # Confidence: high if mesh_width is clearly > noise floor
    confidence = min(1.0, mesh_width / 0.01)  # 0.01 = 1cm in mesh units
    return scale_factor, confidence


def compute_scale_factor_from_sparse_cloud(
    sparse_ply: Path,
    measurements: Measurements,
) -> tuple[float, float]:
    """Alternative: derive scale from COLMAP sparse point cloud X-extent.

    More accurate than mesh-based when the mesh has been trimmed or deformed.
    """
    try:
        pcd = trimesh.load(str(sparse_ply))
        pts = np.asarray(pcd.vertices)
    except Exception:
        raise ValueError(f"Could not load sparse point cloud from {sparse_ply}")

    if len(pts) < 10:
        raise ValueError("Sparse point cloud has too few points for scale estimation")

    # Use the widest X extent as proxy for total_front_width
    x_span = float(pts[:, 0].max() - pts[:, 0].min())
    reference_mm = measurements.best_reference_width
    scale_factor = reference_mm / x_span
    confidence = 0.8  # Slightly less confident than mesh-based
    return scale_factor, confidence


def apply_scale_and_recenter(
    mesh_path: Path,
    scale_factor: float,
    measurements: Measurements,
    output_path: Path,
    tolerance_mm: float = 1.0,
) -> ScaleResult:
    """Apply scale to mesh and set origin to bridge center.

    Exports scaled mesh to output_path and returns validation result.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mesh = _load_mesh(mesh_path)

    # Apply uniform scale
    mesh.apply_scale(scale_factor)

    # Recenter: origin at bridge center (X=0, Y and Z at frame front-center)
    bounds = mesh.bounds
    center_x = (bounds[1][0] + bounds[0][0]) / 2.0
    center_y = (bounds[1][1] + bounds[0][1]) / 2.0
    z_front = bounds[1][2]  # Frontmost Z = frame facing viewer

    # Translate so origin = bridge center
    translation = np.array([-center_x, -center_y, -z_front])
    mesh.apply_translation(translation)

    # Compute validation
    bounds_after = mesh.bounds
    actual_width = float(bounds_after[1][0] - bounds_after[0][0])
    actual_height = float(bounds_after[1][1] - bounds_after[0][1])

    reference_width = measurements.best_reference_width
    width_error = abs(actual_width - reference_width)

    height_error = None
    if measurements.total_height_mm:
        height_error = abs(actual_height - measurements.total_height_mm)

    within_tolerance = width_error <= tolerance_mm

    # Export
    mesh.export(str(output_path))

    return ScaleResult(
        scale_factor=scale_factor,
        actual_width_mm=actual_width,
        actual_height_mm=actual_height,
        width_error_mm=width_error,
        height_error_mm=height_error,
        within_tolerance=within_tolerance,
    )


def verify_scale_accuracy(mesh_path: Path, measurements: Measurements) -> dict:
    """Measure actual mesh bounding box and report errors vs measurements."""
    mesh = _load_mesh(mesh_path)
    bounds = mesh.bounds
    width = float(bounds[1][0] - bounds[0][0])
    height = float(bounds[1][1] - bounds[0][1])
    depth = float(bounds[1][2] - bounds[0][2])

    report: dict = {
        "mesh_width_mm": round(width, 2),
        "mesh_height_mm": round(height, 2),
        "mesh_depth_mm": round(depth, 2),
        "reference_width_mm": measurements.best_reference_width,
        "width_error_mm": round(abs(width - measurements.best_reference_width), 2),
    }

    if measurements.total_height_mm:
        report["reference_height_mm"] = measurements.total_height_mm
        report["height_error_mm"] = round(abs(height - measurements.total_height_mm), 2)

    if measurements.temple_length_mm:
        report["reference_depth_mm"] = measurements.temple_length_mm
        report["depth_error_mm"] = round(abs(depth - measurements.temple_length_mm), 2)

    return report


# ── Private helpers ───────────────────────────────────────────────────────────

def _load_mesh(mesh_path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(mesh_path), force="mesh")
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"No mesh geometry found in {mesh_path}")
        loaded = trimesh.util.concatenate(meshes)
    return loaded
