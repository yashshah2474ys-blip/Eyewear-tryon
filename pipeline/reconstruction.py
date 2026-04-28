"""COLMAP SfM + OpenMVS MVS orchestration for eyewear reconstruction."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .config import Config


class ReconstructionError(Exception):
    pass


@dataclass
class SparseResult:
    sparse_dir: Path
    camera_count: int
    point_count: int
    registered_images: int


@dataclass
class DenseResult:
    textured_glb: Path
    dense_ply: Optional[Path] = None


def _run(cmd: list[str], label: str, cwd: Optional[Path] = None) -> None:
    """Run a subprocess command, raise ReconstructionError on failure."""
    print(f"  [{label}] {' '.join(str(c) for c in cmd[:3])} ...")
    result = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        capture_output=False,
        text=True,
    )
    if result.returncode != 0:
        raise ReconstructionError(
            f"{label} failed with exit code {result.returncode}.\n"
            f"Command: {' '.join(str(c) for c in cmd)}"
        )


def run_colmap_sfm(
    images_dir: Path,
    workspace_dir: Path,
    config: Config,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> SparseResult:
    """Run full COLMAP SfM pipeline: feature extraction → matching → mapping.

    Returns SparseResult with paths to sparse reconstruction.
    """
    db_path = workspace_dir / "database.db"
    sparse_dir = workspace_dir / "sparse"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    gpu_flag = "1" if config.USE_GPU else "0"

    # Step 1: Feature extraction
    if progress_cb:
        progress_cb("COLMAP: Feature extraction", 0.05)
    _run([
        config.COLMAP_BIN, "feature_extractor",
        "--database_path", str(db_path),
        "--image_path", str(images_dir),
        "--ImageReader.single_camera", "0",
        "--ImageReader.camera_model", "SIMPLE_RADIAL",
        "--SiftExtraction.use_gpu", gpu_flag,
        "--SiftExtraction.max_num_features", str(config.SIFT_MAX_FEATURES),
        "--SiftExtraction.peak_threshold", str(config.SIFT_PEAK_THRESHOLD),
        "--SiftExtraction.edge_threshold", "10.0",
    ], "feature_extractor")

    # Step 2: Exhaustive matching (best for small image sets)
    if progress_cb:
        progress_cb("COLMAP: Feature matching", 0.15)
    _run([
        config.COLMAP_BIN, "exhaustive_matcher",
        "--database_path", str(db_path),
        "--SiftMatching.use_gpu", gpu_flag,
        "--SiftMatching.guided_matching", "1",
        "--SiftMatching.max_num_matches", "32768",
    ], "exhaustive_matcher")

    # Step 3: Incremental mapper (SfM)
    if progress_cb:
        progress_cb("COLMAP: Sparse mapping (SfM)", 0.30)
    _run([
        config.COLMAP_BIN, "mapper",
        "--database_path", str(db_path),
        "--image_path", str(images_dir),
        "--output_path", str(sparse_dir),
        "--Mapper.abs_pose_min_num_inliers", "10",
        "--Mapper.init_min_num_inliers", "50",
        "--Mapper.multiple_models", "0",
    ], "mapper")

    # Determine model folder (should be sparse/0 after successful mapping)
    model_dirs = sorted(sparse_dir.glob("*"))
    if not model_dirs:
        raise ReconstructionError(
            "COLMAP mapper produced no output model. "
            "Check image quality and verify at least 20 images were used."
        )
    model_dir = model_dirs[0]

    # Step 4: Convert model to TXT for inspection
    _run([
        config.COLMAP_BIN, "model_converter",
        "--input_path", str(model_dir),
        "--output_path", str(model_dir),
        "--output_type", "TXT",
    ], "model_converter")

    # Parse registration stats from cameras.txt / images.txt
    camera_count, point_count, registered_images = _parse_colmap_stats(model_dir)
    if registered_images < config.MIN_CAMERAS_REGISTERED:
        raise ReconstructionError(
            f"Only {registered_images} cameras registered "
            f"(minimum {config.MIN_CAMERAS_REGISTERED}). "
            "Capture quality is insufficient — re-photograph with matte spray applied."
        )

    return SparseResult(
        sparse_dir=model_dir,
        camera_count=camera_count,
        point_count=point_count,
        registered_images=registered_images,
    )


def export_sparse_pointcloud(sparse_result: SparseResult, output_ply: Path, config: Config) -> Path:
    """Export COLMAP sparse model to PLY for scale calibration."""
    output_ply.parent.mkdir(parents=True, exist_ok=True)
    _run([
        config.COLMAP_BIN, "model_converter",
        "--input_path", str(sparse_result.sparse_dir),
        "--output_path", str(output_ply),
        "--output_type", "PLY",
    ], "export_sparse_ply")
    return output_ply


def undistort_images(
    sparse_result: SparseResult,
    images_dir: Path,
    dense_dir: Path,
    config: Config,
) -> Path:
    """Undistort images using COLMAP model for MVS input."""
    dense_dir.mkdir(parents=True, exist_ok=True)
    _run([
        config.COLMAP_BIN, "image_undistorter",
        "--image_path", str(images_dir),
        "--input_path", str(sparse_result.sparse_dir),
        "--output_path", str(dense_dir),
        "--output_type", "COLMAP",
        "--max_image_size", "3200",
    ], "image_undistorter")
    return dense_dir


def run_openmvs_mvs(
    dense_dir: Path,
    mvs_dir: Path,
    images_dir: Path,
    config: Config,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> DenseResult:
    """Run full OpenMVS pipeline: densify → reconstruct → refine → texture.

    Returns DenseResult with path to textured GLB.
    """
    mvs_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = Path(config.OPENMVS_BIN_DIR)

    scene_mvs = mvs_dir / "scene.mvs"
    dense_mvs = mvs_dir / "dense.mvs"
    mesh_mvs = mvs_dir / "mesh.mvs"
    refined_mvs = mvs_dir / "refined.mvs"
    textured_glb = mvs_dir / "textured.glb"

    gpu_flag = "1" if config.USE_GPU else "0"

    # Step 1: Convert COLMAP to OpenMVS scene
    if progress_cb:
        progress_cb("OpenMVS: Scene conversion", 0.40)
    _run([
        str(bin_dir / "InterfaceCOLMAP"),
        "-i", str(dense_dir),
        "-o", str(scene_mvs),
        "--image-folder", str(dense_dir / "images"),
    ], "InterfaceCOLMAP")

    # Step 2: Densify point cloud
    if progress_cb:
        progress_cb("OpenMVS: Dense point cloud", 0.50)
    _run([
        str(bin_dir / "DensifyPointCloud"),
        str(scene_mvs),
        "-o", str(dense_mvs),
        "--resolution-level", "1",
        "--min-resolution", "320",
        "--max-resolution", "3200",
        "--number-views", str(config.MVS_NUMBER_VIEWS),
        "--number-views-fuse", str(config.MVS_NUMBER_VIEWS_FUSE),
        "--cuda-device", "-1" if not config.USE_GPU else "0",
    ], "DensifyPointCloud")

    # Step 3: Reconstruct mesh
    if progress_cb:
        progress_cb("OpenMVS: Mesh reconstruction", 0.65)
    _run([
        str(bin_dir / "ReconstructMesh"),
        str(dense_mvs),
        "-o", str(mesh_mvs),
        "--remove-spurious", str(config.MVS_REMOVE_SPURIOUS),
        "--close-holes", str(config.MVS_CLOSE_HOLES),
        "--smooth", str(config.MVS_SMOOTH),
        "--cuda-device", "-1" if not config.USE_GPU else "0",
    ], "ReconstructMesh")

    # Step 4: Refine mesh
    if progress_cb:
        progress_cb("OpenMVS: Mesh refinement", 0.75)
    _run([
        str(bin_dir / "RefineMesh"),
        str(mesh_mvs),
        "-o", str(refined_mvs),
        "--resolution-level", "0",
        "--max-face-area", "16",
        "--cuda-device", "-1" if not config.USE_GPU else "0",
    ], "RefineMesh")

    # Step 5: Texture mesh
    if progress_cb:
        progress_cb("OpenMVS: Texturing", 0.85)
    _run([
        str(bin_dir / "TextureMesh"),
        str(dense_mvs),
        "--mesh-file", str(refined_mvs).replace(".mvs", ".ply"),
        "-o", str(textured_glb).replace(".glb", ".mvs"),
        "--export-type", "glb",
        "--cuda-device", "-1" if not config.USE_GPU else "0",
    ], "TextureMesh")

    # OpenMVS writes output as <input_name>.glb
    candidate_glb = mvs_dir / "refined.glb"
    if not candidate_glb.exists():
        # Sometimes named differently — find the newest GLB
        glbs = sorted(mvs_dir.glob("*.glb"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not glbs:
            raise ReconstructionError("OpenMVS TextureMesh produced no GLB output.")
        candidate_glb = glbs[0]

    candidate_glb.rename(textured_glb) if candidate_glb != textured_glb else None

    return DenseResult(textured_glb=textured_glb)


def full_colmap_openmvs_pipeline(
    frame_id: str,
    config: Config,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> Path:
    """Orchestrate complete COLMAP + OpenMVS reconstruction for one frame.

    Returns path to raw textured GLB ready for calibration + Blender post-process.
    """
    frame_input = config.INPUT_ROOT / frame_id
    images_dir = frame_input / "images"
    workspace = frame_input / "colmap"
    workspace.mkdir(parents=True, exist_ok=True)

    mvs_dir = frame_input / "mvs"

    # 1. SfM
    sparse = run_colmap_sfm(images_dir, workspace, config, progress_cb)

    # 2. Export sparse PLY for scale calibration (done later)
    export_sparse_pointcloud(sparse, workspace / "sparse_cloud.ply", config)

    # 3. Undistort images for MVS
    if progress_cb:
        progress_cb("COLMAP: Image undistortion", 0.37)
    dense_dir = undistort_images(sparse, images_dir, workspace / "dense", config)

    # 4. OpenMVS dense reconstruction
    dense_result = run_openmvs_mvs(dense_dir, mvs_dir, images_dir, config, progress_cb)

    return dense_result.textured_glb


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_colmap_stats(model_dir: Path) -> tuple[int, int, int]:
    """Parse cameras.txt, images.txt, points3D.txt for basic stats."""
    camera_count = 0
    registered_images = 0
    point_count = 0

    cameras_txt = model_dir / "cameras.txt"
    images_txt = model_dir / "images.txt"
    points_txt = model_dir / "points3D.txt"

    if cameras_txt.exists():
        lines = cameras_txt.read_text().splitlines()
        camera_count = sum(1 for l in lines if l and not l.startswith("#"))

    if images_txt.exists():
        lines = images_txt.read_text().splitlines()
        registered_images = sum(
            1 for l in lines if l and not l.startswith("#") and not l.startswith(" ")
        ) // 2  # Each image uses 2 lines in TXT format

    if points_txt.exists():
        lines = points_txt.read_text().splitlines()
        point_count = sum(1 for l in lines if l and not l.startswith("#"))

    return camera_count, point_count, registered_images
