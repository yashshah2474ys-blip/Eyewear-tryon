#!/usr/bin/env python3
"""Batch-process all eyewear frames in the frames_input/ directory.

Scans frames_input/ for folders with images/ + measurements.json and processes
each one sequentially. Already-processed frames (existing model.glb) are skipped.

Usage examples:
  python scripts/batch_process.py
  python scripts/batch_process.py --use-api
  python scripts/batch_process.py --gpu --only frame_001 frame_002
  python scripts/batch_process.py --reprocess-all
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from pipeline.config import Config
from pipeline.batch import BatchProcessor, JobStatus


def main():
    parser = argparse.ArgumentParser(
        description="LENSFIT 3D Pipeline — batch processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--use-api", action="store_true",
        help="Use Tripo3D API for all frames (requires TRIPO3D_API_KEY env var)",
    )
    parser.add_argument(
        "--gpu", action="store_true",
        help="Enable GPU acceleration",
    )
    parser.add_argument(
        "--only", nargs="+", metavar="FRAME_ID",
        help="Process only specific frame IDs",
    )
    parser.add_argument(
        "--reprocess-all", action="store_true",
        help="Re-process frames even if model.glb already exists",
    )
    parser.add_argument(
        "--input-root", metavar="PATH", default="frames_input",
        help="Root folder for inputs (default: frames_input/)",
    )
    parser.add_argument(
        "--output-root", metavar="PATH", default="frames_output",
        help="Root folder for outputs (default: frames_output/)",
    )
    parser.add_argument(
        "--blender", metavar="PATH",
        help="Override Blender binary path",
    )
    parser.add_argument(
        "--colmap", metavar="PATH",
        help="Override COLMAP binary path",
    )

    args = parser.parse_args()

    config = Config()
    config.USE_GPU = args.gpu
    config.INPUT_ROOT = Path(args.input_root).resolve()
    config.OUTPUT_ROOT = Path(args.output_root).resolve()

    if args.blender:
        config.BLENDER_BIN = args.blender
    if args.colmap:
        config.COLMAP_BIN = args.colmap

    if not config.INPUT_ROOT.exists():
        print(f"ERROR: Input root not found: {config.INPUT_ROOT}")
        sys.exit(1)

    processor = BatchProcessor(config)

    if args.only:
        # Enqueue specific frames
        for fid in args.only:
            try:
                processor.enqueue(fid, use_api=args.use_api)
            except FileNotFoundError as exc:
                print(f"WARNING: Skipping {fid}: {exc}")
    else:
        # Auto-discover all frames
        if args.reprocess_all:
            # Temporarily clear output to force reprocessing
            for candidate in sorted(config.INPUT_ROOT.iterdir()):
                if not candidate.is_dir():
                    continue
                if (candidate / "images").exists() and (candidate / "measurements.json").exists():
                    out_glb = config.OUTPUT_ROOT / candidate.name / "model.glb"
                    if out_glb.exists():
                        out_glb.unlink()

        jobs = processor.enqueue_all(use_api=args.use_api)
        if not jobs:
            print("No frames to process. All frames already have model.glb output.")
            print("Use --reprocess-all to force reprocessing.")
            sys.exit(0)

    if not processor._jobs:
        print("No frames queued for processing.")
        sys.exit(0)

    total = len(processor._jobs)
    print(f"\n{'='*60}")
    print(f"  LENSFIT 3D Batch Pipeline")
    print(f"{'='*60}")
    print(f"  Frames to process: {total}")
    print(f"  Track:  {'Tripo3D API' if args.use_api else 'COLMAP + OpenMVS (free)'}")
    print(f"  GPU:    {'Enabled' if args.gpu else 'Disabled (CPU)'}")
    print(f"  Input:  {config.INPUT_ROOT}")
    print(f"  Output: {config.OUTPUT_ROOT}")
    print(f"{'='*60}\n")

    processor.run()
    print(processor.summary())

    failed_count = len(processor.failed)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
