#!/usr/bin/env python3
"""
Benchmark train_lora vs train_lora_advanced on the same identities.

Compares validation_score (and downstream face consistency) between baseline and
advanced training. Use REGULARIZATION_URLS or REGULARIZATION_DATASET so the
20% regularization branch is used in advanced training.

Usage:
  # From repo root, run via Modal (recommended):
  modal run ai-pipeline/services/lora_trainer.py::benchmark_lora --identities-path ai-pipeline/scripts/benchmark_identities.json

  # Or use this script to invoke the same entrypoint:
  python ai-pipeline/scripts/benchmark_lora_training.py --identities-path ai-pipeline/scripts/benchmark_identities.json --limit 5

  # Full 50 identities (ensure benchmark_identities.json has 50 entries):
  python ai-pipeline/scripts/benchmark_lora_training.py --identities-path ai-pipeline/scripts/benchmark_identities.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark train_lora vs train_lora_advanced")
    parser.add_argument(
        "--identities-path",
        default="ai-pipeline/scripts/benchmark_identities.json",
        help="JSON file with list of { user_id, identity_id, image_urls }",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max identities to run (0 = all)",
    )
    parser.add_argument(
        "--training-steps-baseline",
        type=int,
        default=1000,
        help="Training steps for baseline train_lora",
    )
    parser.add_argument(
        "--training-steps-advanced",
        type=int,
        default=3000,
        help="Training steps for train_lora_advanced",
    )
    args = parser.parse_args()

    path = Path(args.identities_path)
    if not path.exists():
        # Try relative to script dir
        path = Path(__file__).resolve().parent / Path(args.identities_path).name
    if not path.exists():
        print(f"[ERROR] Identities file not found: {args.identities_path}")
        return 1

    # Validate JSON
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    identities = data if isinstance(data, list) else data.get("identities", [])
    if not identities:
        print("[ERROR] No identities in file")
        return 1
    n = len(identities) if args.limit <= 0 else min(args.limit, len(identities))
    print(f"[*] Will benchmark {n} identities")

    # Invoke Modal entrypoint
    cmd = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "ai-pipeline/services/lora_trainer.py::benchmark_lora",
        "--identities-path",
        str(path.resolve()),
        "--training-steps-baseline",
        str(args.training_steps_baseline),
        "--training-steps-advanced",
        str(args.training_steps_advanced),
    ]
    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    # Repo root: ai-pipeline/scripts -> parent.parent
    repo_root = Path(__file__).resolve().parent.parent.parent
    return subprocess.run(cmd, cwd=repo_root).returncode


if __name__ == "__main__":
    sys.exit(main())
