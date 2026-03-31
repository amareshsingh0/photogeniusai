"""
Base model pilot: evaluation benchmark.
Run 1000-image benchmark on base SDXL vs fine-tuned; measure anatomy, composition, style, user preference.
Target: +15% improvement to proceed to scale.

Usage:
  python ai-pipeline/training/base_model/evaluate_benchmark.py \\
    --prompts_file data/base_model/benchmark/prompts_1000.jsonl \\
    --base_model stabilityai/stable-diffusion-xl-base-1.0 \\
    --finetuned_path outputs/base_model_lora \\
    --output_dir results/benchmark_v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_prompts(path: str) -> list[dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def parse_args():
    p = argparse.ArgumentParser(description="Evaluate base vs fine-tuned SDXL on benchmark")
    p.add_argument("--prompts_file", type=str, required=True,
                   help="JSONL: each line {prompt, category, [expected_style]}")
    p.add_argument("--base_model", type=str, default="stabilityai/stable-diffusion-xl-base-1.0")
    p.add_argument("--finetuned_path", type=str, default=None, help="Path to LoRA or full fine-tuned model")
    p.add_argument("--output_dir", type=str, default="results/benchmark")
    p.add_argument("--num_samples", type=int, default=1000, help="Max prompts to evaluate (0 = all)")
    p.add_argument("--batch_size", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def run_inference(prompts: list[dict], model_path: str, is_lora: bool, output_dir: Path, batch_size: int, seed: int) -> list[dict]:
    """Placeholder: call SDXL pipeline for each prompt (or batch), save images and scores."""
    results = []
    for i, item in enumerate(prompts):
        prompt = item.get("prompt", "")
        category = item.get("category", "general")
        # In production: pipe(prompt, num_inference_steps=30, generator=torch.manual_seed(seed+i))
        # Save image to output_dir/images/{i}.png
        # Run anatomy validator, composition scorer, style CLIP score
        results.append({
            "index": i,
            "prompt": prompt[:80],
            "category": category,
            "image_path": str(output_dir / "images" / f"{i}.png"),
            "anatomy_ok": None,
            "composition_score": None,
            "style_score": None,
        })
    return results


def aggregate_metrics(results: list[dict]) -> dict[str, float]:
    """Compute per-category and overall metrics."""
    by_cat: dict[str, list] = {}
    for r in results:
        cat = r.get("category", "general")
        by_cat.setdefault(cat, []).append(r)
    metrics = {}
    for cat, rows in by_cat.items():
        anatomy = [r["anatomy_ok"] for r in rows if r.get("anatomy_ok") is not None]
        composition = [r["composition_score"] for r in rows if r.get("composition_score") is not None]
        style = [r["style_score"] for r in rows if r.get("style_score") is not None]
        metrics[f"{cat}_anatomy_ok_rate"] = sum(anatomy) / len(anatomy) if anatomy else 0.0
        metrics[f"{cat}_composition_avg"] = sum(composition) / len(composition) if composition else 0.0
        metrics[f"{cat}_style_avg"] = sum(style) / len(style) if style else 0.0
    overall_anatomy = [r["anatomy_ok"] for r in results if r.get("anatomy_ok") is not None]
    overall_comp = [r["composition_score"] for r in results if r.get("composition_score") is not None]
    overall_style = [r["style_score"] for r in results if r.get("style_score") is not None]
    metrics["overall_anatomy_ok_rate"] = sum(overall_anatomy) / len(overall_anatomy) if overall_anatomy else 0.0
    metrics["overall_composition_avg"] = sum(overall_comp) / len(overall_comp) if overall_comp else 0.0
    metrics["overall_style_avg"] = sum(overall_style) / len(overall_style) if overall_style else 0.0
    return metrics


def main():
    args = parse_args()
    prompts = load_prompts(args.prompts_file)
    if args.num_samples and args.num_samples < len(prompts):
        prompts = prompts[: args.num_samples]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)

    (output_dir / "base" / "images").mkdir(parents=True, exist_ok=True)
    (output_dir / "finetuned" / "images").mkdir(parents=True, exist_ok=True)

    # Base model run
    base_results = run_inference(
        prompts, args.base_model, is_lora=False,
        output_dir=output_dir / "base", batch_size=args.batch_size, seed=args.seed,
    )
    base_metrics = aggregate_metrics(base_results)
    with open(output_dir / "base_metrics.json", "w") as f:
        json.dump(base_metrics, f, indent=2)

    # Fine-tuned run (if path given)
    if args.finetuned_path:
        ft_results = run_inference(
            prompts, args.finetuned_path, is_lora=True,
            output_dir=output_dir / "finetuned", batch_size=args.batch_size, seed=args.seed,
        )
        ft_metrics = aggregate_metrics(ft_results)
        with open(output_dir / "finetuned_metrics.json", "w") as f:
            json.dump(ft_metrics, f, indent=2)
        # Delta
        delta = {k: ft_metrics.get(k, 0) - base_metrics.get(k, 0) for k in base_metrics}
        with open(output_dir / "delta_metrics.json", "w") as f:
            json.dump(delta, f, indent=2)
        print("Delta (finetuned - base):", json.dumps(delta, indent=2))

    print("Base metrics:", json.dumps(base_metrics, indent=2))
    print(f"Results in {output_dir}")


if __name__ == "__main__":
    main()
