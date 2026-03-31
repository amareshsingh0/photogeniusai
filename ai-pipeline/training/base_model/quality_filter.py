"""
Base model dataset curation: image quality filter.
- Resolution and aspect ratio
- Blur detection (Laplacian variance)
- Min file size (avoid corrupt/tiny)
- Optional NSFW filter (placeholder; integrate with safety classifier if available)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generator

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None


def _load_image(path: Path) -> Image.Image | None:
    if Image is None:
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _laplacian_variance(image: "Image.Image") -> float:
    """Blur detection: lower variance = more blur."""
    if np is None:
        return 0.0
    try:
        arr = np.array(image)
        if arr.ndim == 3:
            arr = arr.mean(axis=2)
        # Simple Laplacian
        lap = np.abs(np.diff(arr.astype(float), axis=0)).sum() + np.abs(np.diff(arr.astype(float), axis=1)).sum()
        return float(lap / (arr.size or 1))
    except Exception:
        return 0.0


def check_quality(
    image_path: Path | str,
    *,
    min_resolution: tuple[int, int] = (512, 512),
    max_aspect_ratio: float = 2.5,
    min_file_size_kb: float = 20,
    blur_threshold: float = 100,
) -> dict[str, Any]:
    """
    Returns a dict with keys: ok (bool), reason (str), width, height, aspect_ratio,
    file_size_kb, laplacian_variance.
    """
    path = Path(image_path)
    out: dict[str, Any] = {
        "ok": False,
        "reason": "",
        "path": str(path),
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "file_size_kb": None,
        "laplacian_variance": None,
    }

    if not path.exists():
        out["reason"] = "file_not_found"
        return out

    try:
        size_kb = path.stat().st_size / 1024
        out["file_size_kb"] = round(size_kb, 2)
        if size_kb < min_file_size_kb:
            out["reason"] = f"file_too_small_{size_kb}kb"
            return out
    except OSError:
        out["reason"] = "stat_failed"
        return out

    img = _load_image(path)
    if img is None:
        out["reason"] = "load_failed"
        return out

    w, h = img.size
    out["width"], out["height"] = w, h
    if w < min_resolution[0] or h < min_resolution[1]:
        out["reason"] = f"resolution_too_low_{w}x{h}"
        return out

    aspect = max(w, h) / (min(w, h) or 1)
    out["aspect_ratio"] = round(aspect, 2)
    if aspect > max_aspect_ratio:
        out["reason"] = f"aspect_ratio_too_high_{aspect}"
        return out

    var = _laplacian_variance(img)
    out["laplacian_variance"] = round(var, 2)
    if var < blur_threshold:
        out["reason"] = f"too_blurry_{var}"
        return out

    out["ok"] = True
    out["reason"] = "ok"
    return out


def filter_directory(
    dir_path: Path | str,
    extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp"),
    **quality_kwargs: Any,
) -> Generator[dict[str, Any], None, None]:
    """Yield quality-check results for each image in directory (recursive)."""
    root = Path(dir_path)
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.suffix.lower() in extensions:
            yield check_quality(path, **quality_kwargs)


def run_quality_filter(
    input_dir: Path | str,
    output_manifest_path: Path | str | None = None,
    **quality_kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Run quality filter on all images under input_dir.
    If output_manifest_path is set, write a JSONL of passed items (path, width, height, etc.).
    """
    passed = []
    for result in filter_directory(input_dir, **quality_kwargs):
        if result.get("ok"):
            passed.append({
                "path": result["path"],
                "width": result["width"],
                "height": result["height"],
                "aspect_ratio": result["aspect_ratio"],
                "file_size_kb": result["file_size_kb"],
                "laplacian_variance": result["laplacian_variance"],
            })
    out_path = Path(output_manifest_path) if output_manifest_path else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for item in passed:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return passed


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Quality filter for base model dataset")
    p.add_argument("input_dir", type=Path, help="Root directory of images")
    p.add_argument("--output", type=Path, default=None, help="Output JSONL manifest of passed images")
    p.add_argument("--min-size", type=int, default=512)
    p.add_argument("--min-file-kb", type=float, default=20)
    p.add_argument("--blur-threshold", type=float, default=100)
    args = p.parse_args()
    passed = run_quality_filter(
        args.input_dir,
        output_manifest_path=args.output,
        min_resolution=(args.min_size, args.min_size),
        min_file_size_kb=args.min_file_kb,
        blur_threshold=args.blur_threshold,
    )
    print(f"Passed: {len(passed)}")
    if args.output:
        print(f"Wrote {args.output}")
