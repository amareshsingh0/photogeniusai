"""
HTML Report Generator for Benchmark Executor.

Produces benchmark_report.html with:
- Per-category success rates (table + optional chart)
- Top 10 failure patterns
- Side-by-side comparisons of failed images (thumbnail + prompt)
- Recommended fixes for each failure type
"""

from __future__ import annotations

import html
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


# Recommended fixes per failure type (for report)
RECOMMENDED_FIXES: Dict[str, str] = {
    "Person count mismatch": (
        "Use scene graph compiler to enforce exact person count; add negative prompt "
        "'extra limbs, duplicate person, wrong number of people'; consider constraint solver."
    ),
    "Hand anatomy failed": (
        "Enable hand-specific negative prompts (missing hands, extra fingers, bad anatomy); "
        "consider hand-refinement pass or ControlNet hand pose."
    ),
    "Physics/realism failed": (
        "Add physics-aware negative prompts; use physics micro-simulation for rain/umbrella "
        "consistency; validate against expected scene physics."
    ),
    "Fantasy coherence failed": (
        "Strengthen style LoRA for fantasy; add coherence negative prompts; "
        "validate object relationships in scene."
    ),
    "Text/OCR failed": (
        "Use TypographyEngine or deterministic text overlay; avoid diffusion for critical text; "
        "post-render text with correct font/size."
    ),
    "Math/diagram failed": (
        "Use math diagram renderer for equations; overlay LaTeX/rendered math on image; "
        "avoid free-form diffusion for formulas."
    ),
    "Required refinement (not first-try success)": (
        "Tune guidance scale and steps; improve prompt clarity; use auto-validation pipeline "
        "with refinement loops; consider two-pass (preview then refine)."
    ),
    "Generation/GPU error": (
        "Check GPU memory; reduce batch size or resolution; add retry with backoff; "
        "fallback to CPU or smaller model."
    ),
    "Timeout": (
        "Increase timeout per image; use faster model (e.g. Turbo) for preview; "
        "optimize pipeline or scale horizontally."
    ),
    "Out of memory": (
        "Reduce image size or batch size; clear cache between images; use gradient checkpointing; "
        "consider offloading to cloud GPU."
    ),
}


def _classify_failure(failure_reason: str) -> List[str]:
    """Map free-form failure_reason string to list of known pattern keys."""
    reason = (failure_reason or "").strip()
    if not reason:
        return []
    out = []
    for key, label in [
        ("person_count", "Person count mismatch"),
        ("hand_anatomy", "Hand anatomy failed"),
        ("physics_realism", "Physics/realism failed"),
        ("fantasy_coherence", "Fantasy coherence failed"),
        ("text_accuracy", "Text/OCR failed"),
        ("math_diagram", "Math/diagram failed"),
        ("first_try", "Required refinement (not first-try success)"),
        ("generation_error", "Generation/GPU error"),
        ("timeout", "Timeout"),
        ("oom", "Out of memory"),
    ]:
        if label.lower() in reason.lower() or key in reason.lower():
            out.append(label)
    if not out and reason:
        out.append(reason[:80])
    return out


def _top_failure_patterns(results: List[Dict[str, Any]], top_n: int = 10) -> List[tuple]:
    """Return list of (pattern_label, count) sorted by count descending."""
    c: Counter = Counter()
    for r in results:
        if (r.get("pass") if isinstance(r.get("pass"), bool) else (r.get("pass") == "pass")) and not r.get("failure_reason"):
            continue
        reason = r.get("failure_reason", "")
        for label in _classify_failure(reason):
            c[label] += 1
        if not _classify_failure(reason) and reason:
            c[reason[:80]] += 1
    return c.most_common(top_n)


def _failed_cases_with_image(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return failed cases that have an image_path for side-by-side display."""
    out = []
    for r in results:
        pass_val = r.get("pass")
        passed = pass_val is True if isinstance(pass_val, bool) else (pass_val == "pass")
        if passed:
            continue
        img_path = r.get("image_path")
        if img_path and Path(img_path).exists():
            out.append(r)
    return out[:50]  # cap for report size


def generate_html_report(
    results_dir: Path,
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_path: str,
) -> None:
    results_dir = Path(results_dir).resolve()
    total_run = summary.get("total_run", len(results))
    total_planned = summary.get("total_planned", total_run)
    wall_seconds = summary.get("wall_seconds", 0)
    aggregates = summary.get("aggregates", {})
    metrics_passed = summary.get("metrics_passed", {})
    per_category = aggregates.get("first_try_success_by_category", {})
    per_category_counts: Dict[str, int] = {}
    for r in results:
        c = r.get("category", "unknown")
        per_category_counts[c] = per_category_counts.get(c, 0) + 1
    pass_count = sum(1 for r in results if (r.get("pass") is True or r.get("pass") == "pass"))
    success_rate = (pass_count / total_run * 100) if total_run else 0
    top_failures = _top_failure_patterns(results, 10)
    failed_with_img = _failed_cases_with_image(results)

    html_parts: List[str] = []
    html_parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    html_parts.append("<title>PhotoGenius Benchmark Report</title>")
    html_parts.append(
        "<style>"
        "body{font-family:system-ui,sans-serif;margin:1rem 2rem;background:#0f1219;color:#e2e8f0;}"
        "h1,h2,h3{color:#f8fafc;} table{border-collapse:collapse;margin:1rem 0;} th,td{border:1px solid #334155;padding:0.5rem 0.75rem;text-align:left;}"
        "th{background:#1e293b;} .pass{color:#22c55e;} .fail{color:#ef4444;} .metric-fail{background:#7f1d1d20;} .metric-pass{background:#14532d20;}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;} .card{border:1px solid #334155;border-radius:8px;overflow:hidden;}"
        ".card img{width:100%;height:200px;object-fit:cover;} .card .prompt{padding:0.5rem;font-size:0.85rem;} .fix{font-size:0.9rem;color:#94a3b8;margin-top:0.5rem;}"
        ".summary{display:flex;gap:2rem;flex-wrap:wrap;} .summary div{min-width:140px;}"
        "</style></head><body>"
    )
    html_parts.append("<h1>PhotoGenius Benchmark Report</h1>")
    html_parts.append(f"<p>Generated for {total_run} / {total_planned} images in {wall_seconds:.1f}s</p>")
    html_parts.append(f"<p><strong>Overall pass rate:</strong> <span class='{'pass' if success_rate >= 95 else 'fail'}'>{success_rate:.1f}%</span></p>")

    # Summary metrics
    html_parts.append("<h2>Metrics vs targets</h2><table><tr><th>Metric</th><th>Value</th><th>Target</th><th>Status</th></tr>")
    for k, target in summary.get("metrics_threshold", {}).items():
        val = aggregates.get(k)
        if val is None:
            continue
        passed = metrics_passed.get(k, False)
        cls = "metric-pass" if passed else "metric-fail"
        status = "PASS" if passed else "FAIL"
        html_parts.append(
            f"<tr class='{cls}'><td>{html.escape(k)}</td><td>{val:.2%}</td><td>{target:.0%}</td><td>{status}</td></tr>"
        )
    html_parts.append("</table>")

    # Per-category success rates
    html_parts.append("<h2>Per-category success rates</h2><table><tr><th>Category</th><th>Count</th><th>First-try success</th></tr>")
    for cat in sorted(per_category.keys()):
        rate = per_category[cat]
        count = per_category_counts.get(cat, 0)
        cls = "pass" if rate >= 0.95 else "fail"
        html_parts.append(f"<tr><td>{html.escape(cat)}</td><td>{count}</td><td class='{cls}'>{rate:.1%}</td></tr>")
    html_parts.append("</table>")

    # Top 10 failure patterns
    html_parts.append("<h2>Top 10 failure patterns</h2><table><tr><th>Pattern</th><th>Count</th><th>Recommended fix</th></tr>")
    for label, count in top_failures:
        fix = RECOMMENDED_FIXES.get(label, "Review prompt and model behavior; add targeted negative prompts.")
        html_parts.append(
            f"<tr><td>{html.escape(label)}</td><td>{count}</td><td class='fix'>{html.escape(fix)}</td></tr>"
        )
    html_parts.append("</table>")

    # Side-by-side failed images
    html_parts.append("<h2>Failed images (sample)</h2><div class='grid'>")
    results_dir = Path(results_dir)
    for r in failed_with_img:
        img_path = r.get("image_path", "")
        prompt = r.get("prompt", "")[:120]
        reason = (r.get("failure_reason") or "")[:100]
        try:
            rel_path = Path(img_path).resolve().relative_to(Path(results_dir).resolve())
        except (ValueError, TypeError):
            rel_path = img_path
        html_parts.append(
            f"<div class='card'>"
            f"<img src='{html.escape(str(rel_path))}' alt='' loading='lazy' />"
            f"<div class='prompt'><strong>Prompt:</strong> {html.escape(prompt)}..."
            f"<br/><strong>Failure:</strong> {html.escape(reason)}</div></div>"
        )
    html_parts.append("</div>")
    html_parts.append("</body></html>")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(html_parts), encoding="utf-8")
