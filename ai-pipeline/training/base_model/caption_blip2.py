"""
Base model dataset curation: caption generation with BLIP-2.
Produces detailed captions for training. Optional human-review step is external.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

# Optional: transformers + PIL
try:
    from transformers import Blip2Processor, Blip2ForConditionalGeneration
    import torch
    from PIL import Image
    _BLIP_AVAILABLE = True
except ImportError:
    _BLIP_AVAILABLE = False


def get_blip2_model():
    if not _BLIP_AVAILABLE:
        raise RuntimeError("Install transformers, torch, Pillow for BLIP-2 captioning")
    processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = Blip2ForConditionalGeneration.from_pretrained("Salesforce/blip2-opt-2.7b")
    if torch.cuda.is_available():
        model = model.cuda()
    return processor, model


def caption_image(
    image_path: Path | str,
    processor: Any,
    model: Any,
    max_length: int = 77,
    num_beams: int = 4,
) -> str:
    """Generate one caption for an image."""
    if not _BLIP_AVAILABLE:
        return ""
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception:
        return ""
    inputs = processor(images=image, return_tensors="pt")
    if next(model.parameters()).is_cuda:
        inputs = {k: v.cuda() for k, v in inputs.items()}
    out = model.generate(**inputs, max_length=max_length, num_beams=num_beams)
    return processor.decode(out[0], skip_special_tokens=True).strip()


def caption_manifest(
    manifest_path: Path | str,
    output_path: Path | str | None = None,
    batch_size: int = 1,
) -> Iterator[dict[str, Any]]:
    """
    Read a JSONL manifest (each line: {"path": "...", ...}), add "caption" via BLIP-2, yield rows.
    If output_path is set, write JSONL with path, caption, and original fields.
    """
    if not _BLIP_AVAILABLE:
        raise RuntimeError("BLIP-2 not available; install transformers, torch, Pillow")
    processor, model = get_blip2_model()
    manifest_path = Path(manifest_path)
    out_path = Path(output_path) if output_path else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_file = open(out_path, "w", encoding="utf-8")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                path = row.get("path") or row.get("image_path")
                if not path or not Path(path).exists():
                    row["caption"] = ""
                    row["caption_error"] = "path_missing"
                else:
                    row["caption"] = caption_image(path, processor, model)
                if out_path:
                    out_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                yield row
    finally:
        if out_path and "out_file" in dir():
            out_file.close()


def run_caption_pipeline(
    manifest_path: Path | str,
    output_path: Path | str,
) -> int:
    """Run captioning on manifest; return count of captioned rows."""
    count = 0
    for _ in caption_manifest(manifest_path, output_path):
        count += 1
    return count


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="BLIP-2 captioning for base model dataset")
    p.add_argument("manifest", type=Path, help="Input JSONL manifest (path per line)")
    p.add_argument("--output", "-o", type=Path, required=True, help="Output JSONL with captions")
    args = p.parse_args()
    n = run_caption_pipeline(args.manifest, args.output)
    print(f"Captioned {n} images -> {args.output}")
