"""Queue-based batch processor for running the pipeline on many frames."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .config import Config


class JobStatus(Enum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    COLMAP_SFM = "colmap_sfm"
    OPENMVS_DENSE = "openmvs_dense"
    CALIBRATING = "calibrating"
    BLENDER_REPAIR = "blender_repair"
    MATERIALS = "materials"
    EXPORTING = "exporting"
    QC = "qc"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class FrameJob:
    frame_id: str
    input_dir: Path
    output_dir: Path
    measurements_path: Path
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    use_api_fallback: bool = False
    track_used: str = "colmap_openmvs"

    @property
    def elapsed(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0

    @property
    def images_dir(self) -> Path:
        return self.input_dir / "images"

    @property
    def workspace_dir(self) -> Path:
        return self.input_dir / "colmap"

    @property
    def mvs_dir(self) -> Path:
        return self.input_dir / "mvs"


class BatchProcessor:
    def __init__(
        self,
        config: Config,
        progress_callback: Optional[Callable[[FrameJob], None]] = None,
    ):
        self.config = config
        self.progress_callback = progress_callback
        self._jobs: list[FrameJob] = []
        self.completed: list[FrameJob] = []
        self.failed: list[FrameJob] = []

    def enqueue(self, frame_id: str, use_api: bool = False) -> FrameJob:
        """Add a frame to the processing queue after validating its input folder."""
        input_dir = self.config.INPUT_ROOT / frame_id
        output_dir = self.config.OUTPUT_ROOT / frame_id
        measurements_path = input_dir / "measurements.json"

        if not measurements_path.exists():
            raise FileNotFoundError(
                f"measurements.json not found for '{frame_id}'. "
                f"Expected at: {measurements_path}"
            )
        if not (input_dir / "images").exists():
            raise FileNotFoundError(
                f"images/ folder not found for '{frame_id}'. "
                f"Expected at: {input_dir / 'images'}"
            )

        job = FrameJob(
            frame_id=frame_id,
            input_dir=input_dir,
            output_dir=output_dir,
            measurements_path=measurements_path,
            use_api_fallback=use_api,
        )
        self._jobs.append(job)
        return job

    def enqueue_all(self, use_api: bool = False) -> list[FrameJob]:
        """Scan INPUT_ROOT and enqueue every folder that has images/ + measurements.json."""
        jobs = []
        for candidate in sorted(self.config.INPUT_ROOT.iterdir()):
            if not candidate.is_dir():
                continue
            if (candidate / "images").exists() and (candidate / "measurements.json").exists():
                # Skip already completed
                output_glb = self.config.OUTPUT_ROOT / candidate.name / "model.glb"
                if output_glb.exists():
                    print(f"  Skipping {candidate.name} (already processed)")
                    continue
                jobs.append(self.enqueue(candidate.name, use_api=use_api))
        return jobs

    def run(self) -> None:
        """Process all queued jobs sequentially. Reports progress live."""
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
            self._run_rich()
        except ImportError:
            self._run_plain()

    def _run_plain(self) -> None:
        total = len(self._jobs)
        for i, job in enumerate(self._jobs):
            print(f"\n{'='*60}")
            print(f"[{i+1}/{total}] Processing frame: {job.frame_id}")
            print(f"{'='*60}")
            self._process_job(job)

    def _run_rich(self) -> None:
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
        from rich.console import Console

        console = Console()
        total = len(self._jobs)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            overall = progress.add_task("Overall progress", total=total)

            for job in self._jobs:
                task = progress.add_task(f"  {job.frame_id}", total=100)

                def cb(j: FrameJob) -> None:
                    progress.update(task, completed=int(j.progress * 100))
                    if self.progress_callback:
                        self.progress_callback(j)

                self._process_job(job, cb)
                progress.update(task, completed=100)
                progress.update(overall, advance=1)

    def _process_job(
        self,
        job: FrameJob,
        progress_cb: Optional[Callable[[FrameJob], None]] = None,
    ) -> None:
        """Run the full pipeline for a single frame job."""
        from .preprocess import validate_image_set, preprocess_image_set
        from .reconstruction import full_colmap_openmvs_pipeline, ReconstructionError
        from .ai_reconstruction import reconstruct_with_tripo3d
        from .calibration import (
            load_measurements,
            compute_scale_factor_from_mesh,
            apply_scale_and_recenter,
        )
        from .mesh_processing import (
            run_pymeshlab_cleanup,
            run_blender_cleanup,
            run_blender_retopology,
            run_blender_materials,
            run_blender_export,
        )
        from .materials import resolve_material_preset, inject_gltf_extensions, MATERIAL_PRESETS
        from .qc import run_full_qc, qc_report_to_dict
        from .export import write_metadata_json, generate_thumbnail_blender, get_glb_file_stats

        job.start_time = time.time()
        job.output_dir.mkdir(parents=True, exist_ok=True)

        def update(status: JobStatus, pct: float) -> None:
            job.status = status
            job.progress = pct
            self._write_status(job)
            if progress_cb:
                progress_cb(job)

        timing: dict[str, float] = {}

        try:
            # ── Step 1: Validate input ────────────────────────────────────────
            update(JobStatus.PREPROCESSING, 0.02)
            validation = validate_image_set(job.images_dir)
            if not validation.passed:
                raise ValueError(f"Image validation failed:\n{validation}")
            for w in validation.warnings:
                print(f"  WARN: {w}")

            # ── Step 2: Load measurements ─────────────────────────────────────
            measurements = load_measurements(job.measurements_path)

            # ── Step 3: Preprocess images ─────────────────────────────────────
            t0 = time.time()
            preprocessed_dir = job.input_dir / "images_preprocessed"
            preprocess_image_set(job.images_dir, preprocessed_dir, self.config)
            timing["preprocessing_min"] = round((time.time() - t0) / 60, 2)

            # ── Step 4: Reconstruction ────────────────────────────────────────
            raw_glb: Optional[Path] = None

            if not job.use_api_fallback:
                update(JobStatus.COLMAP_SFM, 0.10)
                t0 = time.time()

                def recon_cb(label: str, pct: float) -> None:
                    update(
                        JobStatus.COLMAP_SFM if pct < 0.40 else JobStatus.OPENMVS_DENSE,
                        pct,
                    )

                try:
                    raw_glb = full_colmap_openmvs_pipeline(
                        job.frame_id, self.config, recon_cb
                    )
                    timing["reconstruction_min"] = round((time.time() - t0) / 60, 2)
                    job.track_used = "colmap_openmvs"
                except ReconstructionError as exc:
                    print(f"  COLMAP failed: {exc}")
                    print("  Attempting Tripo3D API fallback...")
                    job.use_api_fallback = True

            if job.use_api_fallback or raw_glb is None:
                update(JobStatus.COLMAP_SFM, 0.10)
                t0 = time.time()
                raw_glb = reconstruct_with_tripo3d(
                    job.images_dir,
                    job.output_dir / "raw_tripo.glb",
                    self.config,
                )
                timing["reconstruction_min"] = round((time.time() - t0) / 60, 2)
                job.track_used = "tripo3d_api"

            # ── Step 5: Scale calibration ─────────────────────────────────────
            update(JobStatus.CALIBRATING, 0.87)
            t0 = time.time()
            scale_factor, confidence = compute_scale_factor_from_mesh(raw_glb, measurements)
            print(f"  Scale factor: {scale_factor:.4f} mm/unit (confidence: {confidence:.2f})")

            scaled_glb = job.output_dir / "scaled.glb"
            scale_result = apply_scale_and_recenter(
                raw_glb, scale_factor, measurements, scaled_glb,
                tolerance_mm=self.config.SCALE_TOLERANCE_MM,
            )
            print(f"  Scale result: width={scale_result.actual_width_mm:.1f}mm "
                  f"error=±{scale_result.width_error_mm:.2f}mm")
            timing["calibration_min"] = round((time.time() - t0) / 60, 2)

            # ── Step 6: PyMeshLab cleanup ─────────────────────────────────────
            update(JobStatus.BLENDER_REPAIR, 0.89)
            t0 = time.time()
            cleaned_ply = job.output_dir / "cleaned.ply"
            try:
                run_pymeshlab_cleanup(scaled_glb, cleaned_ply)
                cleanup_input = cleaned_ply
            except Exception as exc:
                print(f"  PyMeshLab cleanup skipped: {exc}")
                cleanup_input = scaled_glb

            # ── Step 7: Blender cleanup ───────────────────────────────────────
            blender_repaired = job.output_dir / "repaired.glb"
            measurements_dict = {
                "frame_id": measurements.frame_id,
                "lens_width_mm": measurements.lens_width_mm,
                "bridge_width_mm": measurements.bridge_width_mm,
                "temple_length_mm": measurements.temple_length_mm,
                "total_front_width_mm": measurements.best_reference_width,
            }

            if run_blender_cleanup(
                cleanup_input, blender_repaired, measurements_dict,
                self.config.BLENDER_BIN, self.config.BLENDER_SCRIPTS,
            ):
                retopo_input = blender_repaired
            else:
                print("  Blender cleanup skipped (Blender not available)")
                retopo_input = cleanup_input

            # ── Step 8: Retopology ────────────────────────────────────────────
            retopoed = job.output_dir / "retopoed.glb"
            if run_blender_retopology(
                retopo_input, retopoed,
                self.config.TARGET_POLY_COUNT,
                self.config.BLENDER_BIN, self.config.BLENDER_SCRIPTS,
            ):
                material_input = retopoed
            else:
                material_input = retopo_input

            timing["blender_repair_min"] = round((time.time() - t0) / 60, 2)

            # ── Step 9: Materials ─────────────────────────────────────────────
            update(JobStatus.MATERIALS, 0.93)
            t0 = time.time()
            material_preset = resolve_material_preset(measurements.material)
            textured_glb = job.output_dir / "textured.glb"
            run_blender_materials(
                material_input, textured_glb,
                material_preset, None,
                self.config.BLENDER_BIN, self.config.BLENDER_SCRIPTS,
            )
            if not textured_glb.exists():
                textured_glb = material_input
            timing["materials_min"] = round((time.time() - t0) / 60, 2)

            # ── Step 10: Final GLB export ─────────────────────────────────────
            update(JobStatus.EXPORTING, 0.95)
            t0 = time.time()
            final_glb = job.output_dir / "model.glb"
            if not run_blender_export(
                textured_glb, final_glb,
                self.config.BLENDER_BIN, self.config.BLENDER_SCRIPTS,
            ):
                # Blender not available — copy textured GLB as final
                import shutil
                shutil.copy2(str(textured_glb), str(final_glb))

            # Inject GLTF material extensions
            preset_data = MATERIAL_PRESETS.get(material_preset, {})
            inject_gltf_extensions(final_glb, {"Material": preset_data})
            timing["export_min"] = round((time.time() - t0) / 60, 2)

            # ── Step 11: Thumbnail ────────────────────────────────────────────
            thumbnail_png = job.output_dir / "thumbnail.png"
            generate_thumbnail_blender(
                final_glb, thumbnail_png,
                self.config.BLENDER_BIN, self.config.BLENDER_SCRIPTS,
                size=self.config.THUMBNAIL_SIZE,
            )

            # ── Step 12: QC ───────────────────────────────────────────────────
            update(JobStatus.QC, 0.97)
            reference_images = sorted(job.images_dir.glob("shot_0[123].jpg"))[:3]
            qc_report = run_full_qc(
                final_glb, measurements_dict, self.config,
                frame_id=job.frame_id,
                reference_images=reference_images or None,
            )
            print(f"\n{qc_report.summary()}")

            # Write QC report
            qc_path = job.output_dir / "qc_report.json"
            with open(qc_path, "w") as f:
                json.dump(qc_report_to_dict(qc_report), f, indent=2)

            # ── Step 13: Metadata ─────────────────────────────────────────────
            job.end_time = time.time()
            timing["total_min"] = round(job.elapsed / 60, 2)

            from .mesh_processing import analyze_mesh
            stats = analyze_mesh(final_glb)
            glb_info = get_glb_file_stats(final_glb)

            write_metadata_json(
                frame_id=job.frame_id,
                measurements=measurements_dict,
                model_stats={
                    **stats.bounding_box_mm,
                    "triangle_count": stats.tri_count,
                    "vertex_count": stats.vertex_count,
                    "file_size_bytes": glb_info["file_size_bytes"],
                    "origin_at_bridge_center": qc_report.origin_placement_ok,
                },
                qc_results=qc_report_to_dict(qc_report),
                timing=timing,
                output_path=job.output_dir / "metadata.json",
                track=job.track_used,
            )

            job.status = JobStatus.COMPLETE
            job.progress = 1.0
            self._write_status(job)
            self.completed.append(job)

            print(f"\n  Done in {timing['total_min']:.1f} min → {final_glb}")

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.end_time = time.time()
            self._write_status(job)
            self.failed.append(job)
            print(f"\n  FAILED: {exc}")
            raise

    def _write_status(self, job: FrameJob) -> None:
        status_path = job.output_dir / "status.json"
        job.output_dir.mkdir(parents=True, exist_ok=True)
        with open(status_path, "w") as f:
            json.dump({
                "frame_id": job.frame_id,
                "status": job.status.value,
                "progress": round(job.progress, 3),
                "elapsed_sec": round(job.elapsed, 1),
                "track": job.track_used,
                "error": job.error,
            }, f, indent=2)

    def summary(self) -> str:
        total = len(self._jobs)
        done = len(self.completed)
        fail = len(self.failed)
        lines = [
            f"\nBatch summary: {done}/{total} succeeded, {fail} failed",
        ]
        for j in self.completed:
            lines.append(f"  ✓ {j.frame_id} ({j.elapsed/60:.1f} min)")
        for j in self.failed:
            lines.append(f"  ✗ {j.frame_id}: {j.error}")
        return "\n".join(lines)
