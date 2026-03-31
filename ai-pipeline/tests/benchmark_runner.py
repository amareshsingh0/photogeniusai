"""
Benchmark Runner for PhotoGenius AI Comprehensive Testing Suite.

P0: Run 1000-image benchmark across all categories.
Uses comprehensive_test_suite for prompts and scoring.
Target thresholds: first-try ≥95%, person count ≥99%, hand anatomy ≥95%,
text ≥98%, math ≥98%. Writes JSON results and exits 1 if any metric fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run."""

    total_max: int = 1000
    max_per_category: Optional[int] = None
    categories: Optional[List[str]] = None
    dry_run: bool = False  # If True, no generator; use None image and mock scores
    verbose: int = 0  # 0=quiet, 1=progress, 2=per-case
    config_name: str = "production"  # e.g. production, staging
    output_path: Optional[Path] = None  # JSON output path
    baseline_path: Optional[Path] = None  # Optional baseline JSON to compare


@dataclass
class BenchmarkResult:
    """Result of benchmark run."""

    total_run: int
    total_planned: int
    first_try_success: float
    person_count_accuracy: float
    hand_anatomy: float
    physics_realism: float
    fantasy_coherence: float
    text_accuracy: float
    math_diagram_accuracy: float
    avg_refinement_loops: float
    metrics_passed: Dict[str, bool] = field(default_factory=dict)
    metrics_threshold: Dict[str, float] = field(default_factory=dict)
    per_category_counts: Dict[str, int] = field(default_factory=dict)
    first_try_success_by_category: Dict[str, float] = field(default_factory=dict)
    generation_time_avg_ms: Optional[float] = None
    generation_time_per_category_ms: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    config_name: str = "production"
    baseline_comparison: Optional[Dict[str, Any]] = None

    @property
    def all_metrics_passed(self) -> bool:
        return all(self.metrics_passed.values()) if self.metrics_passed else False

    def summary(self) -> str:
        lines = [
            f"Benchmark: {self.total_run} / {self.total_planned} images (config={self.config_name})",
            f"  first_try_success:      {self.first_try_success:.2%} (target {SUCCESS_METRICS.get('first_try_success', 0.95):.0%}) {'PASS' if self.metrics_passed.get('first_try_success') else 'FAIL'}",
            f"  person_count_accuracy:  {self.person_count_accuracy:.2%} (target {SUCCESS_METRICS['person_count_accuracy']:.0%}) {'PASS' if self.metrics_passed.get('person_count_accuracy') else 'FAIL'}",
            f"  hand_anatomy:           {self.hand_anatomy:.2%} (target {SUCCESS_METRICS['hand_anatomy']:.0%}) {'PASS' if self.metrics_passed.get('hand_anatomy') else 'FAIL'}",
            f"  physics_realism:        {self.physics_realism:.2%} (target {SUCCESS_METRICS['physics_realism']:.0%}) {'PASS' if self.metrics_passed.get('physics_realism') else 'FAIL'}",
            f"  fantasy_coherence:      {self.fantasy_coherence:.2%} (target {SUCCESS_METRICS['fantasy_coherence']:.0%}) {'PASS' if self.metrics_passed.get('fantasy_coherence') else 'FAIL'}",
            f"  text_accuracy:          {self.text_accuracy:.2%} (target {SUCCESS_METRICS.get('text_accuracy', 0.98):.0%}) {'PASS' if self.metrics_passed.get('text_accuracy') else 'FAIL'}",
            f"  math_diagram_accuracy:  {self.math_diagram_accuracy:.2%} (target {SUCCESS_METRICS.get('math_diagram_accuracy', 0.98):.0%}) {'PASS' if self.metrics_passed.get('math_diagram_accuracy') else 'FAIL'}",
            f"  avg_refinement_loops:   {self.avg_refinement_loops:.2f}",
            f"Overall: {'PASS' if self.all_metrics_passed else 'FAIL'}",
        ]
        if self.generation_time_avg_ms is not None:
            lines.insert(
                -1, f"  generation_time_avg_ms:  {self.generation_time_avg_ms:.0f}"
            )
        if self.first_try_success_by_category:
            lines.insert(
                -1,
                "  First-try by category: "
                + ", ".join(
                    f"{c}={v:.0%}"
                    for c, v in sorted(self.first_try_success_by_category.items())
                ),
            )
        if self.errors:
            lines.append("Errors: " + "; ".join(self.errors[:5]))
        return "\n".join(lines)

    def to_json_serializable(self) -> Dict[str, Any]:
        """For --output JSON; exclude non-serializable fields."""
        d: Dict[str, Any] = {
            "total_run": self.total_run,
            "total_planned": self.total_planned,
            "first_try_success": self.first_try_success,
            "person_count_accuracy": self.person_count_accuracy,
            "hand_anatomy": self.hand_anatomy,
            "physics_realism": self.physics_realism,
            "fantasy_coherence": self.fantasy_coherence,
            "text_accuracy": self.text_accuracy,
            "math_diagram_accuracy": self.math_diagram_accuracy,
            "avg_refinement_loops": self.avg_refinement_loops,
            "metrics_passed": self.metrics_passed,
            "metrics_threshold": self.metrics_threshold,
            "per_category_counts": self.per_category_counts,
            "first_try_success_by_category": self.first_try_success_by_category,
            "generation_time_avg_ms": self.generation_time_avg_ms,
            "generation_time_per_category_ms": self.generation_time_per_category_ms,
            "errors": self.errors,
            "config_name": self.config_name,
            "baseline_comparison": self.baseline_comparison,
            "all_metrics_passed": self.all_metrics_passed,
        }
        return d


def run_benchmark(
    generator_fn: Optional[Callable[[str, str], Any]] = None,
    config: Optional[BenchmarkConfig] = None,
    *,
    validator: Optional[Any] = None,
    scene_compiler: Optional[Any] = None,
) -> BenchmarkResult:
    """
    Run benchmark over test cases from comprehensive_test_suite.

    generator_fn: (prompt, negative_prompt) -> image or (image, metadata).
    metadata may include first_try_success, refinement_loops_used, generation_time_ms.
    If None and not dry_run, no images generated.
    config: BenchmarkConfig; if None, uses default.
    validator: TriModelValidator instance for person count / hand anatomy (optional).
    scene_compiler: SceneGraphCompiler for expected counts (optional).

    Returns BenchmarkResult with aggregated scores and pass/fail vs SUCCESS_METRICS.
    """
    config = config or BenchmarkConfig()
    if generator_fn is None and not config.dry_run:
        config = BenchmarkConfig(
            total_max=config.total_max,
            max_per_category=config.max_per_category,
            categories=config.categories,
            dry_run=True,
            verbose=config.verbose,
            config_name=config.config_name,
            output_path=config.output_path,
            baseline_path=config.baseline_path,
        )

    cases = get_prompts_for_benchmark(
        total=config.total_max,
        max_per_category=config.max_per_category,
        categories=config.categories or list(TEST_CATEGORIES),
    )
    total_planned = len(cases)
    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    per_category: Dict[str, int] = {
        c: 0 for c in (config.categories or TEST_CATEGORIES)
    }

    for i, test_case in enumerate(cases):
        if config.verbose >= 2:
            print(
                f"  [{i+1}/{total_planned}] {test_case.category}: {test_case.prompt[:50]}..."
            )
        image = None
        run_metadata: Dict[str, Any] = {}
        if not config.dry_run and generator_fn is not None:
            try:
                out = generator_fn(test_case.prompt, "")
                if isinstance(out, (list, tuple)) and len(out) >= 2:
                    image, run_metadata = out[0], (
                        out[1] if isinstance(out[1], dict) else {}
                    )
                else:
                    image = out
            except Exception as e:
                errors.append(f"case {i+1}: {e}")
        score = score_image(
            test_case.category,
            image,
            test_case,
            validator=validator,
            scene_compiler=scene_compiler,
            run_metadata=run_metadata,
        )
        score["category"] = test_case.category
        results.append(score)
        per_category[test_case.category] = per_category.get(test_case.category, 0) + 1

    agg = aggregate_scores(results)
    metrics_passed = {
        k: (agg.get(k, 0) >= SUCCESS_METRICS.get(k, 0)) for k in SUCCESS_METRICS
    }
    metrics_threshold = dict(SUCCESS_METRICS)

    # Optional baseline comparison
    baseline_comparison: Optional[Dict[str, Any]] = None
    if config.baseline_path and config.baseline_path.exists():
        try:
            baseline_data = json.loads(config.baseline_path.read_text(encoding="utf-8"))
            baseline_comparison = {
                "baseline_file": str(config.baseline_path),
                "first_try_success_delta": agg.get("first_try_success", 0)
                - baseline_data.get("first_try_success", 0),
                "person_count_accuracy_delta": agg.get("person_count_accuracy", 0)
                - baseline_data.get("person_count_accuracy", 0),
                "hand_anatomy_delta": agg.get("hand_anatomy", 0)
                - baseline_data.get("hand_anatomy", 0),
                "text_accuracy_delta": agg.get("text_accuracy", 0)
                - baseline_data.get("text_accuracy", 0),
                "math_diagram_accuracy_delta": agg.get("math_diagram_accuracy", 0)
                - baseline_data.get("math_diagram_accuracy", 0),
            }
        except Exception:
            pass

    return BenchmarkResult(
        total_run=len(results),
        total_planned=total_planned,
        first_try_success=agg.get("first_try_success", 0),
        person_count_accuracy=agg.get("person_count_accuracy", 0),
        hand_anatomy=agg.get("hand_anatomy", 0),
        physics_realism=agg.get("physics_realism", 0),
        fantasy_coherence=agg.get("fantasy_coherence", 0),
        text_accuracy=agg.get("text_accuracy", 0),
        math_diagram_accuracy=agg.get("math_diagram_accuracy", 0),
        avg_refinement_loops=agg.get("avg_refinement_loops", 0),
        metrics_passed=metrics_passed,
        metrics_threshold=metrics_threshold,
        per_category_counts=per_category,
        first_try_success_by_category=agg.get("first_try_success_by_category", {}),
        generation_time_avg_ms=agg.get("generation_time_avg_ms"),
        generation_time_per_category_ms=agg.get("generation_time_per_category_ms", {}),
        errors=errors,
        config_name=config.config_name,
        baseline_comparison=baseline_comparison,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PhotoGenius comprehensive benchmark (1000-image target)."
    )
    parser.add_argument(
        "--total",
        type=int,
        default=1000,
        help="Max total images (default 1000)",
    )
    parser.add_argument(
        "--per-category",
        type=int,
        default=None,
        help="Max per category (default total/7)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="production",
        help="Config name, e.g. production (default production)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write results JSON to this path (e.g. results/benchmark_YYYYMMDD.json)",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Optional baseline JSON to compare against",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No generator; score with placeholder (for CI)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        choices=list(TEST_CATEGORIES),
        help="Categories to run (default all)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbose (e.g. -vv for per-case)",
    )
    args = parser.parse_args()

    output_path = None
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_path = Path(args.baseline) if args.baseline else None

    config = BenchmarkConfig(
        total_max=args.total,
        max_per_category=args.per_category,
        categories=args.categories,
        dry_run=args.dry_run,
        verbose=args.verbose,
        config_name=args.config,
        output_path=output_path,
        baseline_path=baseline_path,
    )
    result = run_benchmark(None, config)

    # Analysis: first-try by category, avg refinement loops, text/math accuracy, time per tier
    print(result.summary())
    if result.first_try_success_by_category and args.verbose >= 1:
        print("\nFirst-try success by category:")
        for c, v in sorted(result.first_try_success_by_category.items()):
            print(f"  {c}: {v:.1%}")
    if result.generation_time_per_category_ms and args.verbose >= 1:
        print("\nAvg generation time (ms) by category:")
        for c, t in sorted(result.generation_time_per_category_ms.items()):
            print(f"  {c}: {t:.0f} ms")

    # Write JSON
    if output_path:
        payload = result.to_json_serializable()
        payload["timestamp"] = datetime.utcnow().isoformat() + "Z"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nResults written to {output_path}")

    # Exit 1 if any metric fails (do not deploy to production)
    return 0 if result.all_metrics_passed else 1


if __name__ == "__main__":
    sys.exit(main())
