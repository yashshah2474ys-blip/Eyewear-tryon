"""Global configuration for the LENSFIT 3D pipeline."""
import os
import shutil
from pathlib import Path


def _find_blender() -> str:
    """Auto-detect Blender binary across platforms."""
    candidates = [
        "blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",
        "C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe",
    ]
    for c in candidates:
        if shutil.which(c) or Path(c).exists():
            return c
    return "blender"


class Config:
    # ── Paths ────────────────────────────────────────────────────────────────
    PIPELINE_ROOT: Path = Path(__file__).parent.parent
    INPUT_ROOT: Path = PIPELINE_ROOT / "frames_input"
    OUTPUT_ROOT: Path = PIPELINE_ROOT / "frames_output"
    BLENDER_SCRIPTS: Path = PIPELINE_ROOT / "blender_scripts"

    # ── External tool binaries (override via environment variables) ───────────
    COLMAP_BIN: str = os.environ.get("COLMAP_BIN", "colmap")
    OPENMVS_BIN_DIR: str = os.environ.get("OPENMVS_BIN_DIR", "/usr/local/bin/OpenMVS")
    BLENDER_BIN: str = os.environ.get("BLENDER_BIN") or _find_blender()

    # ── Tripo3D API (optional fast-track) ─────────────────────────────────────
    TRIPO3D_API_KEY: str = os.environ.get("TRIPO3D_API_KEY", "")
    TRIPO3D_ENDPOINT: str = "https://api.tripo3d.ai/v2/openapi/task"
    TRIPO3D_UPLOAD_ENDPOINT: str = "https://api.tripo3d.ai/v2/openapi/upload"

    # ── Processing settings ───────────────────────────────────────────────────
    USE_GPU: bool = False
    TARGET_POLY_COUNT: int = 12_000
    MAX_INPUT_DIM: int = 3200         # Max image edge for reconstruction
    TEXTURE_RESOLUTION: int = 1024
    SCALE_TOLERANCE_MM: float = 1.0
    MIN_IMAGES_REQUIRED: int = 20
    BRIDGE_REPAIR_THICKNESS_MM: float = 0.8  # Min temple/bridge thickness

    # ── COLMAP tuning ─────────────────────────────────────────────────────────
    SIFT_PEAK_THRESHOLD: float = 0.004   # Lower than default for low-texture frames
    SIFT_MAX_FEATURES: int = 8192
    MIN_CAMERAS_REGISTERED: int = 15    # Fail if fewer cameras register

    # ── OpenMVS tuning ────────────────────────────────────────────────────────
    MVS_NUMBER_VIEWS: int = 5
    MVS_NUMBER_VIEWS_FUSE: int = 3      # Fewer required for thin geometry
    MVS_CLOSE_HOLES: int = 30
    MVS_REMOVE_SPURIOUS: int = 20
    MVS_SMOOTH: int = 2

    # ── QC thresholds ─────────────────────────────────────────────────────────
    QC_MAX_POLY_COUNT: int = 15_000
    QC_MIN_POLY_COUNT: int = 5_000
    QC_MAX_SCALE_ERROR_MM: float = 2.0
    QC_MIN_SILHOUETTE_SCORE: float = 0.75
    QC_MAX_ORIGIN_OFFSET_MM: float = 3.0

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    THUMBNAIL_SIZE: tuple = (512, 512)
    THUMBNAIL_BG_COLOR: tuple = (119, 119, 119)  # 18% grey
