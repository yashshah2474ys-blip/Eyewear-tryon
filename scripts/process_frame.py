#!/usr/bin/env python3
"""Process a single eyewear frame through the full 3D reconstruction pipeline.

Usage examples:
  python scripts/process_frame.py --frame-id ray_ban_wayfarer
  python scripts/process_frame.py --frame-id ray_ban_wayfarer --use-api
  python scripts/process_frame.py --frame-id ray_ban_wayfarer --gpu
  python scripts/process_frame.py --frame-id ray_ban_wayfarer --skip-reconstruction

Input expected at:
  frames_input/{frame-id}/images/       (20-30 JPEGs named shot_01.jpg ... shot_25.jpg)
  frames_input/{frame-id}/measurements.json

Output written to:
  frames_output/{frame-id}/model.glb
  frames_output/{frame-id}/thumbnail.png
  frames_output/{frame-id}/metadata.json
  frames_output/{frame-id}/qc_report.json
"""
import sys
import os
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from pipeline.config import Config
from pipeline.batch import BatchProcessor, JobStatus


def main():
    parser = argparse.ArgumentParser(
        description="LENSFIT 3D Pipeline — single frame processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--frame-id", required=True,
        help="Frame folder name inside frames_input/ (e.g. 'ray_ban_wayfarer')",
    )
    parser.add_argument(
        "--use-api", action="store_true",
        help="Use Tripo3D API instead of COLMAP+OpenMVS (requires TRIPO3D_API_KEY env var)",
    )
    parser.add_argument(
        "--gpu", action="store_true",
        help="Enable CUDA GPU acceleration for COLMAP and OpenMVS",
    )
    parser.add_argument(
        "--skip-reconstruction", action="store_true",
        help="Skip COLMAP/API step; re-use existing raw mesh from a previous run",
    )
    parser.add_argument(
        "--blender", metavar="PATH",
        help="Override path to Blender executable",
    )
    parser.add_argument(
        "--colmap", metavar="PATH",
        help="Override path to COLMAP binary",
    )
    parser.add_argument(
        "--openmvs-dir", metavar="PATH",
        help="Override path to OpenMVS binaries directory",
    )
    parser.add_argument(
        "--input-root", metavar="PATH", default="frames_input",
        help="Root folder for frame inputs (default: frames_input/)",
    )
    parser.add_argument(
        "--output-root", metavar="PATH", default="frames_output",
        help="Root folder for outputs (default: frames_output/)",
    )

    args = parser.parse_args()

    # Build config
    config = Config()
    config.USE_GPU = args.gpu
    config.INPUT_ROOT = Path(args.input_root).resolve()
    config.OUTPUT_ROOT = Path(args.output_root).resolve()

    if args.blender:
        config.BLENDER_BIN = args.blender
    if args.colmap:
        config.COLMAP_BIN = args.colmap
    if args.openmvs_dir:
        config.OPENMVS_BIN_DIR = args.openmvs_dir

    # Validate inputs exist
    input_dir = config.INPUT_ROOT / args.frame_id
    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}")
        print(f"Create it with an images/ subfolder and measurements.json inside.")
        sys.exit(1)

    # Print header
    print(f"\n{'='*60}")
    print(f"  LENSFIT 3D Pipeline v1.0")
    print(f"{'='*60}")
    print(f"  Frame ID:  {args.frame_id}")
    print(f"  Track:     {'Tripo3D API' if args.use_api else 'COLMAP + OpenMVS'}")
    print(f"  GPU:       {'Enabled' if args.gpu else 'Disabled (CPU)'}")
    print(f"  Input:     {input_dir}")
    print(f"  Output:    {config.OUTPUT_ROOT / args.frame_id}")
    print(f"  Blender:   {config.BLENDER_BIN}")
    print(f"{'='*60}\n")

    def progress(job):
        bar_len = 30
        filled = int(bar_len * job.progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        elapsed = f"{job.elapsed:.0f}s"
        print(f"\r  [{bar}] {job.progress*100:.0f}% — {job.status.value:<20} {elapsed}",
              end="", flush=True)

    processor = BatchProcessor(config, progress_callback=progress)
    try:
        job = processor.enqueue(args.frame_id, use_api=args.use_api)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    try:
        processor.run()
        print()  # newline after progress bar
    except Exception:
        print()

    job = processor._jobs[0]
    if job.status == JobStatus.COMPLETE:
        output_glb = config.OUTPUT_ROOT / args.frame_id / "model.glb"
        print(f"\n{'='*60}")
        print(f"  SUCCESS — {args.frame_id}")
        print(f"{'='*60}")
        print(f"  GLB:       {output_glb}")
        print(f"  Size:      {output_glb.stat().st_size / 1024:.1f} KB")
        print(f"  Time:      {job.elapsed/60:.1f} minutes")
        print(f"\n  Next steps:")
        print(f"    1. Open admin.html in your browser")
        print(f"    2. Edit the '{args.frame_id}' frame record")
        print(f"    3. Upload {output_glb.name} in the '3D Model' field")
        print(f"    4. Open index.html — 3D try-on is now active for this frame")
        print(f"{'='*60}\n")
        sys.exit(0)
    else:
        print(f"\nFAILED: {job.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
