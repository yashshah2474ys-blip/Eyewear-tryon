"""Quality control validation for reconstructed eyewear GLB assets."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh

from .config import Config


@dataclass
class QCReport:
    frame_id: str
    passed: bool
    poly_count_ok: bool
    mesh_integrity_ok: bool
    scale_accuracy_ok: bool
    origin_placement_ok: bool
    triangle_count: int
    scale_error_mm: float
    origin_offset_mm: float
    is_watertight: bool
    has_nan_vertices: bool
    silhouette_score: Optional[float] = None
    details: dict = field(default_factory=dict)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"QC {status} — {self.frame_id}",
            f"  Polys:        {self.triangle_count:,} ({'OK' if self.poly_count_ok else 'FAIL'})",
            f"  Scale error:  ±{self.scale_error_mm:.2f} mm ({'OK' if self.scale_accuracy_ok else 'FAIL'})",
            f"  Origin offset:{self.origin_offset_mm:.2f} mm ({'OK' if self.origin_placement_ok else 'FAIL'})",
            f"  Watertight:   {'yes' if self.is_watertight else 'no'}",
            f"  NaN vertices: {'yes' if self.has_nan_vertices else 'no'}",
        ]
        if self.silhouette_score is not None:
            lines.append(f"  Silhouette:   {self.silhouette_score:.3f}")
        return "\n".join(lines)


def check_poly_count(mesh: trimesh.Trimesh, config: Config) -> tuple[bool, int]:
    """Return (passed, triangle_count)."""
    tri_count = len(mesh.triangles)
    ok = config.QC_MIN_POLY_COUNT <= tri_count <= config.QC_MAX_POLY_COUNT
    return ok, tri_count


def check_mesh_integrity(mesh: trimesh.Trimesh) -> tuple[bool, dict]:
    """Check for NaN vertices, degenerate faces, normal consistency."""
    has_nan = bool(np.any(np.isnan(mesh.vertices)))
    is_wt = mesh.is_watertight

    # Zero-area faces
    areas = mesh.area_faces
    degenerate_count = int(np.sum(areas < 1e-12))

    ok = not has_nan and degenerate_count == 0
    return ok, {
        "has_nan": has_nan,
        "is_watertight": is_wt,
        "degenerate_faces": degenerate_count,
    }


def check_scale_accuracy(
    mesh: trimesh.Trimesh,
    measurements: dict,
    config: Config,
) -> tuple[bool, float]:
    """Compare mesh bounding box width vs reference width. Returns (passed, error_mm)."""
    reference_width = measurements.get("total_front_width_mm") or (
        measurements.get("lens_width_mm", 52) * 2 + measurements.get("bridge_width_mm", 18)
    )

    bounds = mesh.bounds
    actual_width = float(bounds[1][0] - bounds[0][0])
    error = abs(actual_width - reference_width)
    ok = error <= config.QC_MAX_SCALE_ERROR_MM
    return ok, round(error, 2)


def check_origin_placement(mesh: trimesh.Trimesh, config: Config) -> tuple[bool, float]:
    """Verify origin is near bridge center (X symmetric, Z at front face).

    Returns (passed, offset_mm) where offset_mm = distance from origin to ideal bridge center.
    """
    bounds = mesh.bounds
    # Ideal bridge center: X=0 (symmetric), Y=center, Z=max_Z (front face)
    ideal_x = 0.0
    ideal_z = bounds[1][2]  # Front of frame

    # The origin IS (0,0,0) in the mesh — we check if the mesh is symmetric around X=0
    x_center_of_mass = float((bounds[1][0] + bounds[0][0]) / 2.0)
    x_symmetry_offset = abs(x_center_of_mass)

    # Also check Z: front face should be near Z=0 after centering
    z_front_offset = abs(bounds[1][2])  # Should be ~0 if origin was set to front

    offset = max(x_symmetry_offset, z_front_offset)
    ok = offset <= config.QC_MAX_ORIGIN_OFFSET_MM
    return ok, round(float(offset), 2)


def compute_silhouette_score_cpu(
    glb_path: Path,
    reference_images: list[Path],
) -> float:
    """Compute silhouette IoU score using pyrender (CPU rasterizer).

    Returns average IoU across provided reference images, or -1 if unavailable.
    """
    try:
        import pyrender
        import cv2
    except ImportError:
        return -1.0

    try:
        mesh = _load_mesh(glb_path)
        scene = pyrender.Scene()
        scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=True))

        iou_scores = []
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0)

        for ref_path in reference_images[:5]:  # cap at 5 views for speed
            # Standard front view
            camera_pose = np.array([
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0.25],
                [0, 0, 0, 1],
            ], dtype=np.float32)

            camera_node = scene.add(camera, pose=camera_pose)

            renderer = pyrender.OffscreenRenderer(320, 240)
            try:
                _, depth = renderer.render(scene)
                rendered_sil = (depth > 0).astype(np.uint8)

                ref_img = cv2.imread(str(ref_path), cv2.IMREAD_GRAYSCALE)
                if ref_img is None:
                    continue
                ref_img = cv2.resize(ref_img, (320, 240))
                _, ref_sil = cv2.threshold(ref_img, 100, 1, cv2.THRESH_BINARY_INV)

                intersection = np.logical_and(rendered_sil, ref_sil).sum()
                union = np.logical_or(rendered_sil, ref_sil).sum()
                if union > 0:
                    iou_scores.append(float(intersection / union))
            finally:
                renderer.delete()
                scene.remove_node(camera_node)

        return float(np.mean(iou_scores)) if iou_scores else -1.0
    except Exception:
        return -1.0


def run_full_qc(
    glb_path: Path,
    measurements: dict,
    config: Config,
    frame_id: str = "",
    reference_images: Optional[list[Path]] = None,
) -> QCReport:
    """Run all QC checks and return a consolidated report."""
    if not glb_path.exists():
        return QCReport(
            frame_id=frame_id,
            passed=False,
            poly_count_ok=False,
            mesh_integrity_ok=False,
            scale_accuracy_ok=False,
            origin_placement_ok=False,
            triangle_count=0,
            scale_error_mm=999.0,
            origin_offset_mm=999.0,
            is_watertight=False,
            has_nan_vertices=True,
            details={"error": f"GLB not found: {glb_path}"},
        )

    mesh = _load_mesh(glb_path)

    poly_ok, tri_count = check_poly_count(mesh, config)
    integrity_ok, integrity_details = check_mesh_integrity(mesh)
    scale_ok, scale_error = check_scale_accuracy(mesh, measurements, config)
    origin_ok, origin_offset = check_origin_placement(mesh, config)

    silhouette = -1.0
    if reference_images:
        silhouette = compute_silhouette_score_cpu(glb_path, reference_images)

    overall_passed = poly_ok and integrity_ok and scale_ok and origin_ok

    return QCReport(
        frame_id=frame_id,
        passed=overall_passed,
        poly_count_ok=poly_ok,
        mesh_integrity_ok=integrity_ok,
        scale_accuracy_ok=scale_ok,
        origin_placement_ok=origin_ok,
        triangle_count=tri_count,
        scale_error_mm=scale_error,
        origin_offset_mm=origin_offset,
        is_watertight=integrity_details["is_watertight"],
        has_nan_vertices=integrity_details["has_nan"],
        silhouette_score=silhouette if silhouette >= 0 else None,
        details=integrity_details,
    )


def qc_report_to_dict(report: QCReport) -> dict:
    return {
        "passed": report.passed,
        "poly_count_ok": report.poly_count_ok,
        "mesh_integrity_ok": report.mesh_integrity_ok,
        "scale_accuracy_ok": report.scale_accuracy_ok,
        "origin_placement_ok": report.origin_placement_ok,
        "triangle_count": report.triangle_count,
        "scale_error_mm": report.scale_error_mm,
        "origin_offset_mm": report.origin_offset_mm,
        "is_watertight": report.is_watertight,
        "has_nan_vertices": report.has_nan_vertices,
        "silhouette_score": report.silhouette_score,
        "details": report.details,
    }


def _load_mesh(mesh_path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(mesh_path), force="mesh")
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"No mesh found in {mesh_path}")
        loaded = trimesh.util.concatenate(meshes)
    return loaded
