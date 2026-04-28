"""Image preprocessing for photogrammetry reconstruction."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from .config import Config


@dataclass
class ValidationResult:
    passed: bool
    image_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"Validation {'PASSED' if self.passed else 'FAILED'} ({self.image_count} images)"]
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        for w in self.warnings:
            lines.append(f"  WARN:  {w}")
        return "\n".join(lines)


REQUIRED_SHOTS = [f"shot_{i:02d}.jpg" for i in range(1, 22)]   # shots 01–21
OPTIONAL_SHOTS = [f"shot_{i:02d}.jpg" for i in range(22, 26)]  # shots 22–25


def validate_image_set(images_dir: Path) -> ValidationResult:
    """Validate that the 25-shot capture protocol was followed."""
    errors: list[str] = []
    warnings: list[str] = []

    if not images_dir.exists():
        return ValidationResult(False, 0, errors=[f"images/ directory not found: {images_dir}"])

    present = {f.name.lower() for f in images_dir.glob("*.jpg")} | \
              {f.name.lower() for f in images_dir.glob("*.jpeg")} | \
              {f.name.lower() for f in images_dir.glob("*.png")}

    image_count = len(present)
    if image_count < Config.MIN_IMAGES_REQUIRED:
        errors.append(f"Only {image_count} images found; minimum {Config.MIN_IMAGES_REQUIRED} required")

    missing_required = [s for s in REQUIRED_SHOTS if s not in present]
    if missing_required:
        errors.append(f"Missing required shots: {missing_required}")

    # Check resolution and blur for each image
    for name in sorted(present)[:25]:  # check at most 25
        path = images_dir / name
        if not path.exists():
            # Try case-insensitive
            matches = list(images_dir.glob(f"*{name}"))
            if not matches:
                continue
            path = matches[0]

        try:
            with Image.open(path) as img:
                w, h = img.size
            if min(w, h) < 1500:
                warnings.append(f"{name}: low resolution {w}×{h} (target ≥1500px short side)")

            img_cv = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img_cv is not None:
                lap_var = cv2.Laplacian(img_cv, cv2.CV_64F).var()
                if lap_var < 80:
                    warnings.append(f"{name}: possibly blurry (Laplacian var={lap_var:.1f})")
        except Exception as exc:
            warnings.append(f"{name}: could not read ({exc})")

    return ValidationResult(
        passed=len(errors) == 0,
        image_count=image_count,
        errors=errors,
        warnings=warnings,
    )


def remove_background(
    image_path: Path,
    output_path: Path,
    method: str = "rembg",
    bg_grey: int = 119,
) -> Path:
    """Remove background and replace with neutral grey for COLMAP masking.

    Returns path to processed JPEG.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if method == "rembg":
        try:
            from rembg import remove
            from PIL import Image as PILImage
            import io

            with open(image_path, "rb") as f:
                input_bytes = f.read()
            rgba_bytes = remove(input_bytes)
            img_rgba = PILImage.open(io.BytesIO(rgba_bytes)).convert("RGBA")

            # Composite on grey background
            bg = PILImage.new("RGBA", img_rgba.size, (bg_grey, bg_grey, bg_grey, 255))
            bg.paste(img_rgba, mask=img_rgba.split()[3])
            bg.convert("RGB").save(output_path, "JPEG", quality=95)
            return output_path
        except ImportError:
            pass  # fall through to OpenCV GrabCut

    # GrabCut fallback
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    h, w = img.shape[:2]
    margin = int(min(w, h) * 0.02)
    rect = (margin, margin, w - 2 * margin, h - 2 * margin)

    mask = np.zeros((h, w), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)

    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg_mask = cv2.GaussianBlur(fg_mask, (5, 5), 0)

    result = img.copy()
    result[fg_mask == 0] = bg_grey

    cv2.imwrite(str(output_path), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path


def attenuate_specular_highlights(image_path: Path, output_path: Path) -> Path:
    """Inpaint bright specular hotspots to aid photogrammetry feature matching."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(str(image_path))

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Specular highlights: very high value channel AND very low saturation
    _, s, v = cv2.split(hsv)
    highlight_mask = np.logical_and(v > 240, s < 30).astype(np.uint8) * 255

    # Dilate slightly so inpainting covers the full highlight edge
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    highlight_mask = cv2.dilate(highlight_mask, kernel, iterations=2)

    result = cv2.inpaint(img, highlight_mask, 5, cv2.INPAINT_NS)
    cv2.imwrite(str(output_path), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path


def enhance_contrast(image_path: Path, output_path: Path) -> Path:
    """Apply CLAHE for contrast enhancement, helpful on dark acetate frames."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(str(image_path))

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    enhanced = cv2.merge([l_ch, a_ch, b_ch])
    result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    cv2.imwrite(str(output_path), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path


def resize_for_reconstruction(image_path: Path, output_path: Path, max_dim: int = 3200) -> Path:
    """Resize image so its longest edge ≤ max_dim. Preserves aspect ratio."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(str(image_path))

    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        cv2.imwrite(str(output_path), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return output_path

    scale = max_dim / longest
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(output_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path


def preprocess_image_set(
    images_dir: Path,
    output_dir: Path,
    config: Config,
    remove_bg: bool = True,
    fix_speculars: bool = True,
    enhance: bool = True,
) -> Path:
    """Run the full preprocessing chain on all images in images_dir.

    Returns output_dir containing processed images ready for COLMAP.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_images = sorted(
        list(images_dir.glob("*.jpg"))
        + list(images_dir.glob("*.jpeg"))
        + list(images_dir.glob("*.png"))
    )

    if not all_images:
        raise FileNotFoundError(f"No images found in {images_dir}")

    for src in all_images:
        dest = output_dir / src.with_suffix(".jpg").name
        tmp = src

        if fix_speculars:
            _tmp = output_dir / f"_spec_{src.name}"
            attenuate_specular_highlights(tmp, _tmp)
            tmp = _tmp

        if remove_bg:
            _tmp2 = output_dir / f"_bg_{src.name}"
            remove_background(tmp, _tmp2)
            tmp = _tmp2

        if enhance:
            _tmp3 = output_dir / f"_enh_{src.name}"
            enhance_contrast(tmp, _tmp3)
            tmp = _tmp3

        resize_for_reconstruction(tmp, dest, max_dim=config.MAX_INPUT_DIM)

        # Clean up intermediate temp files
        for prefix in ("_spec_", "_bg_", "_enh_"):
            t = output_dir / f"{prefix}{src.name}"
            if t.exists():
                t.unlink()

    return output_dir
