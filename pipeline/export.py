"""Thumbnail generation, metadata writing, and final export utilities."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from .config import Config


def generate_thumbnail_blender(
    glb_path: Path,
    output_png: Path,
    blender_bin: str,
    blender_scripts_dir: Path,
    size: tuple[int, int] = (512, 512),
) -> Path:
    """Render a front-view thumbnail using Blender headless rendering."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    script = blender_scripts_dir / "export_glb.py"

    result = subprocess.run(
        [
            blender_bin, "--background",
            "--python", str(script),
            "--",
            str(glb_path),
            str(output_png),
            "--thumbnail",
            str(size[0]), str(size[1]),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not output_png.exists():
        # Fallback: generate a simple PIL thumbnail
        _generate_thumbnail_pil(glb_path, output_png, size)
    return output_png


def _generate_thumbnail_pil(
    glb_path: Path,
    output_png: Path,
    size: tuple[int, int] = (512, 512),
) -> Path:
    """Minimal PIL fallback thumbnail (grey square with frame label)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        bg_color = (119, 119, 119)
        img = Image.new("RGBA", size, bg_color + (255,))
        draw = ImageDraw.Draw(img)
        label = glb_path.stem
        draw.text((size[0] // 2 - len(label) * 4, size[1] // 2 - 8), label,
                  fill=(255, 255, 255), align="center")
        img.save(str(output_png), "PNG")
    except ImportError:
        pass
    return output_png


def write_metadata_json(
    frame_id: str,
    measurements: dict,
    model_stats: dict,
    qc_results: dict,
    timing: dict,
    output_path: Path,
    pipeline_version: str = "1.0.0",
    track: str = "colmap_openmvs",
) -> None:
    """Write complete metadata.json for admin.html consumption."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "frame_id": frame_id,
        "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pipeline_version": pipeline_version,
        "track": track,
        "measurements_input": measurements,
        "model_stats": model_stats,
        "qc": qc_results,
        "timing": timing,
    }
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)


def get_glb_file_stats(glb_path: Path) -> dict:
    """Return file size and basic stats for metadata."""
    if not glb_path.exists():
        return {"file_size_bytes": 0, "exists": False}
    return {
        "file_size_bytes": glb_path.stat().st_size,
        "exists": True,
        "path": str(glb_path),
    }
