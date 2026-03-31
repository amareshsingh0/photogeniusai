"""
Base model dataset curation: full pipeline.
1. Quality filter (resolution, blur, size)
2. Caption generation (BLIP-2)
3. Deduplication (file hash + optional phash)
4. License manifest

Usage:
  python -m ai_pipeline.training.base_model.run_curation_pipeline --input data/sources --output data/curated/v1.0
  # Or from repo root:
  python ai-pipeline/training/base_model/run_curation_pipeline.py --input data/base_model/sources --output data/base_model/curated/v1.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Local imports (run from repo root or with PYTHONPATH)
try:
    from .quality_filter import run_quality_filter
    from .dedup import run_dedup
    from .license_tracking import build_license_manifest
except ImportError:
    from quality_filter import run_quality_filter
    from dedup import run_dedup
    from license_tracking import build_license_manifest


def run_pipeline(
    input_root: Path | str,
    output_dir: Path | str,
    run_captions: bool = False,
    min_resolution: int = 512,
    min_file_kb: float = 20,
    blur_threshold: float = 100,
) -> dict:
    """
    Run quality filter -> (optional) captions -> dedup -> license manifest.
    Returns summary dict with counts and paths.
    """
    input_root = Path(input_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Quality filter
    quality_manifest = output_dir / "quality_passed.jsonl"
    passed = run_quality_filter(
        input_root,
        output_manifest_path=quality_manifest,
        min_resolution=(min_resolution, min_resolution),
        min_file_size_kb=min_file_kb,
        blur_threshold=blur_threshold,
    )
    summary = {"quality_passed": len(passed), "quality_manifest": str(quality_manifest)}

    # Step 2: Captions (optional; requires BLIP-2)
    caption_manifest = output_dir / "captions.jsonl"
    if run_captions:
        try:
            from .caption_blip2 import run_caption_pipeline
        except ImportError:
            from caption_blip2 import run_caption_pipeline
        n_cap = run_caption_pipeline(quality_manifest, caption_manifest)
        summary["captioned"] = n_cap
        next_manifest = caption_manifest
    else:
        next_manifest = quality_manifest

    # Step 3: Dedup
    dedup_manifest = output_dir / "manifest.jsonl"
    deduped = run_dedup(next_manifest, output_path=dedup_manifest, use_phash=True)
    summary["after_dedup"] = len(deduped)
    summary["manifest"] = str(dedup_manifest)

    # Step 4: License manifest
    license_path = output_dir / "license_manifest.json"
    build_license_manifest(dedup_manifest, output_path=license_path)
    summary["license_manifest"] = str(license_path)

    return summary


def main():
    p = argparse.ArgumentParser(description="Base model dataset curation pipeline")
    p.add_argument("--input", "-i", type=Path, required=True, help="Root directory of source images")
    p.add_argument("--output", "-o", type=Path, required=True, help="Output directory (e.g. data/base_model/curated/v1.0)")
    p.add_argument("--captions", action="store_true", help="Run BLIP-2 captioning (slow)")
    p.add_argument("--min-resolution", type=int, default=512)
    p.add_argument("--min-file-kb", type=float, default=20)
    p.add_argument("--blur-threshold", type=float, default=100)
    args = p.parse_args()
    summary = run_pipeline(
        args.input,
        args.output,
        run_captions=args.captions,
        min_resolution=args.min_resolution,
        min_file_kb=args.min_file_kb,
        blur_threshold=args.blur_threshold,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
