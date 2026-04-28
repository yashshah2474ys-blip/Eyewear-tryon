"""Optional Tripo3D API fast-track reconstruction for eyewear.

Use when COLMAP fails (too few matched features) or for high-volume production.
Requires TRIPO3D_API_KEY environment variable.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Optional

import httpx

from .config import Config

# Priority order for selecting images to send to the API
# Chosen to maximize viewpoint coverage with minimal redundancy
API_SHOT_PRIORITY = [
    "shot_01.jpg",  # Front
    "shot_06.jpg",  # 45° right-front
    "shot_09.jpg",  # Right side
    "shot_12.jpg",  # 45° left-front
    "shot_15.jpg",  # Left side
    "shot_18.jpg",  # Top
    "shot_22.jpg",  # Bridge close-up
    "shot_07.jpg",  # 45° right-front elevated
    "shot_13.jpg",  # 45° left-front elevated
    "shot_20.jpg",  # Bottom
]


def select_best_images_for_api(images_dir: Path, max_count: int = 8) -> list[Path]:
    """Select the most informative images from the capture set for API submission."""
    selected = []
    for shot_name in API_SHOT_PRIORITY:
        candidate = images_dir / shot_name
        if candidate.exists():
            selected.append(candidate)
        if len(selected) >= max_count:
            break

    # If named shots not found, fall back to the first max_count images
    if not selected:
        all_imgs = sorted(images_dir.glob("*.jpg"))[:max_count]
        selected = all_imgs

    return selected[:max_count]


def upload_image(image_path: Path, api_key: str, client: httpx.Client) -> str:
    """Upload one image to Tripo3D and return the file token."""
    with open(image_path, "rb") as f:
        data = f.read()

    response = client.post(
        "https://api.tripo3d.ai/v2/openapi/upload",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": (image_path.name, io.BytesIO(data), "image/jpeg")},
        timeout=60.0,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Upload failed: {result}")
    return result["data"]["image_token"]


def create_multiview_task(image_tokens: list[str], api_key: str, client: httpx.Client) -> str:
    """Submit a multi-view reconstruction task. Returns task_id."""
    payload = {
        "type": "multiview_to_model",
        "files": [{"type": "jpg", "file": {"type": "token", "token": t}} for t in image_tokens],
        "model_version": "v2.0-20240919",
        "texture": True,
    }
    response = client.post(
        "https://api.tripo3d.ai/v2/openapi/task",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Task creation failed: {result}")
    return result["data"]["task_id"]


def poll_task(task_id: str, api_key: str, client: httpx.Client, timeout: int = 600) -> dict:
    """Poll Tripo3D task until complete. Returns final task data dict."""
    start = time.time()
    interval = 5

    while time.time() - start < timeout:
        response = client.get(
            f"https://api.tripo3d.ai/v2/openapi/task/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Task poll error: {data}")

        task = data["data"]
        status = task.get("status", "unknown")

        if status == "success":
            return task
        elif status in ("failed", "cancelled"):
            raise RuntimeError(f"Tripo3D task {task_id} {status}: {task.get('message', '')}")

        print(f"  [Tripo3D] Task {task_id}: {status} ({task.get('progress', 0)}%)")
        time.sleep(interval)

    raise TimeoutError(f"Tripo3D task {task_id} timed out after {timeout}s")


def download_glb(download_url: str, output_path: Path, client: httpx.Client) -> Path:
    """Download GLB from Tripo3D CDN."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", download_url, timeout=120.0) as response:
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
    return output_path


def reconstruct_with_tripo3d(
    images_dir: Path,
    output_glb: Path,
    config: Config,
    max_images: int = 8,
) -> Path:
    """Full Tripo3D API pipeline: select images → upload → task → poll → download.

    Returns path to downloaded raw GLB (before scale calibration and Blender cleanup).
    """
    if not config.TRIPO3D_API_KEY:
        raise ValueError(
            "TRIPO3D_API_KEY is not set. "
            "Set it as an environment variable or in config.py to use the API track."
        )

    images = select_best_images_for_api(images_dir, max_count=max_images)
    if not images:
        raise FileNotFoundError(f"No images found in {images_dir}")

    print(f"  [Tripo3D] Uploading {len(images)} images...")
    with httpx.Client() as client:
        tokens = []
        for img_path in images:
            token = upload_image(img_path, config.TRIPO3D_API_KEY, client)
            tokens.append(token)
            print(f"    Uploaded {img_path.name}")

        print(f"  [Tripo3D] Creating reconstruction task...")
        task_id = create_multiview_task(tokens, config.TRIPO3D_API_KEY, client)
        print(f"  [Tripo3D] Task ID: {task_id}")

        print(f"  [Tripo3D] Polling for completion (may take 2-5 minutes)...")
        task_data = poll_task(task_id, config.TRIPO3D_API_KEY, client)

        model_url = task_data.get("output", {}).get("model")
        if not model_url:
            raise RuntimeError(f"No model URL in task output: {task_data}")

        print(f"  [Tripo3D] Downloading GLB...")
        return download_glb(model_url, output_glb, client)
