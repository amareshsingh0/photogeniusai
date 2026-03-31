# PhotoGenius 1000-Image Benchmark — Execution Guide

This directory contains the **comprehensive benchmark suite** and **executor** for running a full 1000-image benchmark, saving images and metrics, and generating an HTML report with failure analysis.

## Overview

- **`comprehensive_test_suite.py`** — Defines test categories, prompts (1000+ per category), success metrics, and scoring.
- **`benchmark_runner.py`** — Core runner used by CI (dry-run) or with an injected generator.
- **`benchmark_executor.py`** — **Full executor**: runs real or mock generation, checkpoints every N images, writes CSV + JSON, triggers HTML report.
- **`benchmark_html_report.py`** — Generates `benchmark_report.html` with per-category success rates, top failure patterns, failed image samples, and recommended fixes.

## Quick Start

From the **ai-pipeline** root:

```bash
# Dry-run style with mock generator (no GPU); 100 images, checkpoint every 50
python -m tests.benchmark_executor --total 100 --generator mock

# Full 1000-image benchmark with mock generator (CI / no GPU)
python -m tests.benchmark_executor --total 1000 --checkpoint-every 50 --generator mock

# With AWS generator (requires AWS_API_GATEWAY_URL or AWS_LAMBDA_GENERATION_URL)
python -m tests.benchmark_executor --total 1000 --generator aws

# Resume from last checkpoint after interrupt
python -m tests.benchmark_executor --resume
```

## Output Layout

All outputs go under **`ai-pipeline/benchmark_results/`** (or `--results-dir`):

```
benchmark_results/
├── images/
│   ├── multi_person/
│   │   ├── 00000_2_people_at_a_cafe.png
│   │   └── ...
│   ├── rain_weather/
│   └── ...
├── benchmark_results.csv      # Per-image: category, prompt, pass/fail, failure_reason, metrics
├── benchmark_summary.json    # Aggregates, metrics vs targets, wall time
├── benchmark_report.html     # Visual report (success rates, top failures, failed image grid)
└── checkpoint.json           # Resume state (last index + results so far)
```

## CSV Columns

| Column | Description |
|--------|-------------|
| index | Case index (0-based) |
| category | Test category (e.g. multi_person, hand_anatomy) |
| prompt | Prompt text (truncated) |
| pass | `pass` or `fail` |
| failure_reason | Semicolon-separated reasons (e.g. "Person count mismatch; Hand anatomy failed") |
| person_count_ok | 1/0 or True/False |
| hand_anatomy_ok | 1/0 or True/False |
| physics_realism_ok | ... |
| fantasy_coherence_ok | ... |
| text_ok | ... |
| math_ok | ... |
| first_try_success | Whether no refinement was needed |
| refinement_loops | Number of refinement loops |
| generation_time_ms | Time for this image (ms) |
| image_path | Path to saved image (if any) |

## Resumability

- **Checkpoint every N images**: `--checkpoint-every 50` (default) writes `checkpoint.json` with `last_index` and full `results` list.
- **Resume**: Run with `--resume` to skip cases before `last_index` and append to the same CSV. Existing `benchmark_results.csv` is opened in append mode when resuming.

## Progress and Runtime

- If **tqdm** is installed, a progress bar is shown with ETA.
- **Estimated runtime** (mock): ~0.1–0.5 s per image → 100–500 s for 1000 images.
- **Real GPU/AWS**: depends on backend (e.g. 30–60 s per image → several hours for 1000).

## Error Handling

- **GPU / OOM**: Caught per image; error logged, case marked failed, script continues; `gc.collect()` is called after OOM.
- **Timeouts**: Not enforced inside the executor; configure your generator or backend to respect `timeout_per_image` if needed.
- **Generation errors**: Stored in `failure_reason` and in `errors` in the summary JSON.

## HTML Report Contents

- **Metrics vs targets**: Table of aggregate metrics (e.g. first_try_success, person_count_accuracy) vs SUCCESS_METRICS.
- **Per-category success rates**: First-try success and count per category.
- **Top 10 failure patterns**: Most common failure reasons with **recommended fixes** (e.g. “Person count mismatch” → scene graph compiler, negative prompts).
- **Failed images (sample)**: Grid of up to 50 failed cases with thumbnail and prompt/failure reason (only when image was saved).

## Success Metrics (P0)

From `comprehensive_test_suite.SUCCESS_METRICS`:

- first_try_success ≥ 95%
- person_count_accuracy ≥ 99%
- hand_anatomy ≥ 95%
- physics_realism ≥ 90%
- fantasy_coherence ≥ 85%
- text_accuracy ≥ 98%
- math_diagram_accuracy ≥ 98%

The executor exits with **0** if all metrics pass, **1** otherwise (suitable for CI).

## Optional: Run HTML Report Only

If you already have `benchmark_results.csv` and `benchmark_summary.json`, you can regenerate the HTML report by running the executor in a no-op way or calling the report generator from Python:

```python
from pathlib import Path
from tests.benchmark_html_report import generate_html_report
import json

results_dir = Path("benchmark_results")
summary = json.loads((results_dir / "benchmark_summary.json").read_text())
# Build results list from CSV if needed, or load from checkpoint
results = json.loads((results_dir / "checkpoint.json").read_text()).get("results", [])
generate_html_report(results_dir, results, summary, str(results_dir / "benchmark_report.html"))
```

## Requirements

- Python 3.9+
- Dependencies from `ai-pipeline/requirements.txt` (and optionally `requirements-test.txt`).
- Optional: **tqdm** for progress bar (`pip install tqdm`).
- For **real** generation: GPU and/or AWS credentials + `generator=aws` (or inject your own generator in code).
