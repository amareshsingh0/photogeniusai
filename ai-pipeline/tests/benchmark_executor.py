"""
Benchmark Executor — Run the full 1000-image benchmark with real execution.

- Runs the full benchmark (not dry-run); optional mock generator for CI.
- Saves all generated images to benchmark_results/images/
- Generates detailed CSV: category, prompt, pass/fail, failure_reason, metrics
- Checkpoints every 50 images for resumability
- Progress bar with ETA; handles GPU/memory errors
- Outputs JSON summary and triggers HTML report generation.

Usage:
  python -m tests.benchmark_executor --total 1000
  python -m tests.benchmark_executor --total 100 --checkpoint-every 25 --generator mock
  python -m tests.benchmark_executor --resume
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure ai-pipeline root on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from tests.comprehensive_test_suite import (
        TEST_CATEGORIES,
        SUCCESS_METRICS,
        BenchmarkTestCase,
        get_prompts_for_benchmark,
        score_image,
        aggregate_scores,
    )
except ImportError:
    from comprehensive_test_suite import (
        TEST_CATEGORIES,
        SUCCESS_METRICS,
        BenchmarkTestCase,
        get_prompts_for_benchmark,
        score_image,
        aggregate_scores,
    )

# Optional progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"
IMAGES_SUBDIR = "images"
CHECKPOINT_FILENAME = "checkpoint.json"
CSV_FILENAME = "benchmark_results.csv"
SUMMARY_JSON = "benchmark_summary.json"
CHECKPOINT_EVERY = 50

# Failure reason classification
FAILURE_PATTERNS = {
    "person_count": "Person count mismatch",
    "hand_anatomy": "Hand anatomy failed",
    "physics_realism": "Physics/realism failed",
    "fantasy_coherence": "Fantasy coherence failed",
    "text_accuracy": "Text/OCR failed",
    "math_diagram": "Math/diagram failed",
    "first_try": "Required refinement (not first-try success)",
    "generation_error": "Generation/GPU error",
    "timeout": "Timeout",
    "oom": "Out of memory",
}


def _slug(prompt: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", prompt)[:max_len].strip()
    return re.sub(r"[-\s]+", "_", s) or "prompt"


def _get_failure_reason(score: Dict[str, Any], test_case: BenchmarkTestCase) -> str:
    reasons = []
    if score.get("person_count_ok") is False:
        reasons.append(FAILURE_PATTERNS["person_count"])
    if score.get("hand_anatomy_ok") is False:
        reasons.append(FAILURE_PATTERNS["hand_anatomy"])
    if score.get("physics_realism_ok") is False:
        reasons.append(FAILURE_PATTERNS["physics_realism"])
    if score.get("fantasy_coherence_ok") is False:
        reasons.append(FAILURE_PATTERNS["fantasy_coherence"])
    if score.get("text_ok") is False:
        reasons.append(FAILURE_PATTERNS["text_accuracy"])
    if score.get("math_ok") is False:
        reasons.append(FAILURE_PATTERNS["math_diagram"])
    if not score.get("first_try_success", True):
        reasons.append(FAILURE_PATTERNS["first_try"])
    return "; ".join(reasons) if reasons else ""


def _passed(score: Dict[str, Any], category: str) -> bool:
    """Single case pass: all relevant metrics for category pass."""
    if score.get("person_count_ok") is False:
        return False
    if score.get("hand_anatomy_ok") is False:
        return False
    if score.get("physics_realism_ok") is False:
        return False
    if score.get("fantasy_coherence_ok") is False:
        return False
    if score.get("text_ok") is False:
        return False
    if score.get("math_ok") is False:
        return False
    return True


@dataclass
class ExecutorConfig:
    total: int = 1000
    max_per_category: Optional[int] = None
    categories: Optional[List[str]] = None
    results_dir: Path = field(default_factory=lambda: DEFAULT_RESULTS_DIR)
    checkpoint_every: int = CHECKPOINT_EVERY
    generator: str = "mock"  # mock | aws | local
    verbose: int = 1
    timeout_per_image: float = 120.0


def _mock_generator(prompt: str, negative_prompt: str) -> Tuple[Any, Dict[str, Any]]:
    """Generate a small placeholder image (PIL) for CI/dry-run style execution."""
    try:
        from PIL import Image
        img = Image.new("RGB", (256, 256), color=(128, 128, 128))
        return img, {"first_try_success": True, "refinement_loops_used": 0, "generation_time_ms": 0}
    except Exception as e:
        return None, {"first_try_success": False, "refinement_loops_used": 0, "generation_time_ms": 0, "error": str(e)}


def _load_aws_generator() -> Optional[Callable[[str, str], Any]]:
    """Optional: load AWS/orchestrator generator if env and deps available."""
    try:
        from services.orchestrator_aws import generate_professional
    except ImportError:
        try:
            from ai_pipeline.services.orchestrator_aws import generate_professional
        except ImportError:
            return None
    if not os.environ.get("AWS_API_GATEWAY_URL") and not os.environ.get("AWS_LAMBDA_GENERATION_URL"):
        return None

    def _gen(prompt: str, negative_prompt: str) -> Tuple[Any, Dict[str, Any]]:
        import base64
        import io
        start = time.perf_counter()
        try:
            out = generate_professional(
                user_prompt=prompt,
                identity_id=None,
                user_id="benchmark",
                quality_tier="STANDARD",
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            if out.get("status") != "success":
                return None, {"first_try_success": False, "generation_time_ms": elapsed_ms, "error": out.get("message", "unknown")}
            b64 = (out.get("images") or {}).get("final")
            if not b64:
                return None, {"first_try_success": False, "generation_time_ms": elapsed_ms}
            raw = base64.b64decode(b64)
            from PIL import Image
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            meta = out.get("metadata") or {}
            return img, {
                "first_try_success": meta.get("first_try_success", True),
                "refinement_loops_used": meta.get("refinement_loops_used", 0),
                "generation_time_ms": elapsed_ms,
            }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return None, {"first_try_success": False, "generation_time_ms": elapsed_ms, "error": str(e)}

    return _gen


def _get_generator(config: ExecutorConfig) -> Callable[[str, str], Any]:
    if config.generator == "mock":
        return _mock_generator
    if config.generator == "aws":
        fn = _load_aws_generator()
        if fn is None:
            print("Warning: AWS generator not available; falling back to mock.", file=sys.stderr)
            return _mock_generator
        return fn
    return _mock_generator


def _image_to_save_path(image: Any, results_dir: Path, category: str, index: int, prompt: str) -> Optional[Path]:
    """Save image to results_dir/images/category/index_slug.png; return path."""
    if image is None:
        return None
    try:
        from PIL import Image
        if not isinstance(image, Image.Image):
            return None
    except ImportError:
        return None
    sub = results_dir / IMAGES_SUBDIR / category
    sub.mkdir(parents=True, exist_ok=True)
    slug = _slug(prompt)[:50]
    path = sub / f"{index:05d}_{slug}.png"
    try:
        image.save(path)
        return path
    except Exception:
        return None


def load_checkpoint(results_dir: Path) -> Tuple[int, List[Dict[str, Any]]]:
    path = results_dir / CHECKPOINT_FILENAME
    if not path.exists():
        return 0, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("last_index", 0)), data.get("results", [])
    except Exception:
        return 0, []


def save_checkpoint(results_dir: Path, last_index: int, results: List[Dict[str, Any]]) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / CHECKPOINT_FILENAME
    path.write_text(
        json.dumps({"last_index": last_index, "results": results}, indent=2),
        encoding="utf-8",
    )


def run_executor(config: ExecutorConfig, resume: bool = False) -> Dict[str, Any]:
    results_dir = config.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / IMAGES_SUBDIR).mkdir(parents=True, exist_ok=True)

    cases = get_prompts_for_benchmark(
        total=config.total,
        max_per_category=config.max_per_category,
        categories=config.categories or list(TEST_CATEGORIES),
    )
    total_planned = len(cases)
    generator_fn = _get_generator(config)

    start_index = 0
    results: List[Dict[str, Any]] = []
    if resume:
        start_index, results = load_checkpoint(results_dir)
        if config.verbose:
            print(f"Resuming from index {start_index} ({len(results)} results in checkpoint)")

    csv_path = results_dir / CSV_FILENAME
    write_header = not csv_path.exists() or start_index == 0
    csv_file = open(csv_path, "a", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    if write_header:
        writer.writerow([
            "index", "category", "prompt", "pass", "failure_reason",
            "person_count_ok", "hand_anatomy_ok", "physics_realism_ok",
            "fantasy_coherence_ok", "text_ok", "math_ok", "first_try_success",
            "refinement_loops", "generation_time_ms", "image_path",
        ])

    errors: List[str] = []
    start_wall = time.perf_counter()
    iterator = range(start_index, total_planned)
    if HAS_TQDM:
        iterator = tqdm(iterator, total=total_planned, initial=start_index, unit="img", desc="Benchmark")

    for i in iterator:
        test_case = cases[i]
        image = None
        run_metadata: Dict[str, Any] = {}
        image_path: Optional[str] = None

        try:
            t0 = time.perf_counter()
            out = generator_fn(test_case.prompt, "")
            if isinstance(out, (list, tuple)) and len(out) >= 2:
                image, run_metadata = out[0], (out[1] if isinstance(out[1], dict) else {})
            else:
                image = out
            if image is not None:
                saved = _image_to_save_path(
                    image, results_dir, test_case.category, i, test_case.prompt
                )
                if saved:
                    image_path = str(saved)
        except MemoryError as e:
            errors.append(f"case {i}: OOM")
            run_metadata = {"error": "OOM", "generation_time_ms": 0}
            gc.collect()
        except Exception as e:
            err_msg = str(e)
            if "out of memory" in err_msg.lower() or "cuda" in err_msg.lower():
                errors.append(f"case {i}: GPU/OOM")
                run_metadata = {"error": err_msg, "generation_time_ms": 0}
                gc.collect()
            else:
                errors.append(f"case {i}: {err_msg}")
                run_metadata = {"error": err_msg, "generation_time_ms": 0}

        score = score_image(
            test_case.category,
            image,
            test_case,
            run_metadata=run_metadata,
        )
        score["category"] = test_case.category
        score["prompt"] = test_case.prompt
        score["index"] = i
        score["image_path"] = image_path
        failure_reason = _get_failure_reason(score, test_case)
        if run_metadata.get("error") and not failure_reason:
            failure_reason = run_metadata.get("error", "Generation error")[:200]
        passed = _passed(score, test_case.category) and not run_metadata.get("error")
        score["pass"] = passed
        score["failure_reason"] = failure_reason

        results.append(score)
        writer.writerow([
            i,
            test_case.category,
            test_case.prompt[:200],
            "pass" if passed else "fail",
            failure_reason[:500] if failure_reason else "",
            score.get("person_count_ok"),
            score.get("hand_anatomy_ok"),
            score.get("physics_realism_ok"),
            score.get("fantasy_coherence_ok"),
            score.get("text_ok"),
            score.get("math_ok"),
            score.get("first_try_success"),
            score.get("refinement_loops", 0),
            score.get("generation_time_ms"),
            image_path or "",
        ])
        csv_file.flush()

        if (i + 1) % config.checkpoint_every == 0:
            save_checkpoint(results_dir, i + 1, results)

    csv_file.close()
    total_wall = time.perf_counter() - start_wall

    agg = aggregate_scores(results)
    metrics_passed = {
        k: (agg.get(k, 0) >= SUCCESS_METRICS.get(k, 0)) for k in SUCCESS_METRICS
    }
    summary = {
        "total_run": len(results),
        "total_planned": total_planned,
        "wall_seconds": round(total_wall, 2),
        "aggregates": agg,
        "metrics_passed": metrics_passed,
        "metrics_threshold": dict(SUCCESS_METRICS),
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "results_dir": str(results_dir),
        "csv_path": str(csv_path),
    }
    summary_path = results_dir / SUMMARY_JSON
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Trigger HTML report
    try:
        from tests.benchmark_html_report import generate_html_report
        html_path = results_dir / "benchmark_report.html"
        generate_html_report(results_dir, results, summary, str(html_path))
        summary["html_report"] = str(html_path)
    except Exception as e:
        summary["html_report_error"] = str(e)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full 1000-image benchmark with checkpointing and CSV/HTML report."
    )
    parser.add_argument("--total", type=int, default=1000, help="Max total images")
    parser.add_argument("--per-category", type=int, default=None, help="Max per category")
    parser.add_argument("--categories", nargs="+", default=None, choices=list(TEST_CATEGORIES), help="Categories to run")
    parser.add_argument("--results-dir", type=str, default=None, help="Output directory (default: ai-pipeline/benchmark_results)")
    parser.add_argument("--checkpoint-every", type=int, default=CHECKPOINT_EVERY, help="Checkpoint every N images")
    parser.add_argument("--generator", choices=("mock", "aws"), default="mock", help="Generator: mock or aws")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args()

    results_dir = Path(args.results_dir) if args.results_dir else DEFAULT_RESULTS_DIR
    config = ExecutorConfig(
        total=args.total,
        max_per_category=args.per_category,
        categories=args.categories,
        results_dir=results_dir,
        checkpoint_every=args.checkpoint_every,
        generator=args.generator,
        verbose=args.verbose,
    )
    summary = run_executor(config, resume=args.resume)
    print(f"\nResults: {summary['results_dir']}")
    print(f"  CSV: {summary['csv_path']}")
    print(f"  Summary JSON: {results_dir / SUMMARY_JSON}")
    if summary.get("html_report"):
        print(f"  HTML report: {summary['html_report']}")
    print(f"  Total: {summary['total_run']}/{summary['total_planned']} in {summary['wall_seconds']}s")
    passed = all(summary.get("metrics_passed", {}).values())
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
