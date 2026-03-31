"""
Offline Policy Update Pipeline (RLHF pilot).

1. Generate 1000 images from recent prompts (or sample from DB).
2. Score each with reward model.
3. Fine-tune on top 10% (rejection sampling / supervised on high-reward samples).
4. Export checkpoint for A/B test.
5. Safety: ensure no degradation on safety metrics before rollout.

Usage:
  python ai-pipeline/scripts/offline_policy_update.py \\
    --reward-checkpoint models/reward_model_preference.pth \\
    --prompts-jsonl prompts.jsonl \\
    --output-dir models/policy_canary \\
    --top-fraction 0.1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent so we can import from training
_SCRIPT_DIR = Path(__file__).resolve().parent
_TOP = _SCRIPT_DIR.parent.parent
if str(_TOP) not in sys.path:
    sys.path.insert(0, str(_TOP))


def main():
    ap = argparse.ArgumentParser(description="Offline policy update: score -> top-k -> fine-tune")
    ap.add_argument("--reward-checkpoint", required=True, help="Path to reward model .pth")
    ap.add_argument("--prompts-jsonl", default=None, help="JSONL of {prompt, ...} for generation")
    ap.add_argument("--output-dir", default="models/policy_canary")
    ap.add_argument("--top-fraction", type=float, default=0.1, help="Top fraction to use for SFT")
    ap.add_argument("--num-samples", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true", help="Only print steps, do not run")
    args = ap.parse_args()

    if args.dry_run:
        print("Offline policy update (dry run)")
        print("  1. Load reward model from", args.reward_checkpoint)
        print("  2. Generate or load", args.num_samples, "images from prompts")
        print("  3. Score with reward model")
        print("  4. Select top", int(args.top_fraction * 100), "%")
        print("  5. Fine-tune base model on selected (SFT)")
        print("  6. Export to", args.output_dir)
        print("  7. Safety check: no degradation on safety metrics")
        return

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # Placeholder: actual implementation would load reward model, run inference pipeline,
    # call generation API or local pipeline, then run SFT script.
    print("Offline policy update: implement generation + scoring + SFT in your pipeline.")
    print("See docs/RLHF_DEPLOYMENT_RUNBOOK.md for full steps.")
    with open(Path(args.output_dir) / "manifest.json", "w") as f:
        json.dump({
            "reward_checkpoint": args.reward_checkpoint,
            "top_fraction": args.top_fraction,
            "num_samples": args.num_samples,
            "status": "placeholder",
        }, f, indent=2)


if __name__ == "__main__":
    main()
