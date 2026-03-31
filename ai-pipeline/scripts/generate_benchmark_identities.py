#!/usr/bin/env python3
"""
Generate benchmark_identities.json with 50 identities for train_lora vs train_lora_advanced.

Use this to create a 50-identity file so the benchmark uses the same 50 identities.
Replace placeholder image_urls with your real identity image URLs (at least 5 per identity)
before running the benchmark.

Usage:
  python ai-pipeline/scripts/generate_benchmark_identities.py
  python ai-pipeline/scripts/generate_benchmark_identities.py --count 10 --out my_identities.json
  python ai-pipeline/scripts/generate_benchmark_identities.py --urls-file path/to/urls_per_identity.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Placeholder URLs (picsum) so the file is valid; replace with real identity image URLs.
DEFAULT_IMAGE_URLS = [
    "https://picsum.photos/id/100/1024/1024",
    "https://picsum.photos/id/101/1024/1024",
    "https://picsum.photos/id/102/1024/1024",
    "https://picsum.photos/id/103/1024/1024",
    "https://picsum.photos/id/104/1024/1024",
    "https://picsum.photos/id/105/1024/1024",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate benchmark_identities.json for LoRA benchmark (50 identities by default)."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of identities to generate (default 50).",
    )
    parser.add_argument(
        "--out",
        default="ai-pipeline/scripts/benchmark_identities.json",
        help="Output JSON path (default ai-pipeline/scripts/benchmark_identities.json).",
    )
    parser.add_argument(
        "--urls-file",
        help="Optional JSON file: list of lists of image URLs, one list per identity (length must be >= count).",
    )
    args = parser.parse_args()

    if args.urls_file:
        path = Path(args.urls_file)
        if not path.exists():
            print(f"[ERROR] URLs file not found: {path}")
            return 1
        with open(path, encoding="utf-8") as f:
            urls_per_identity = json.load(f)
        if len(urls_per_identity) < args.count:
            print(f"[WARN] urls-file has {len(urls_per_identity)} entries; using first {args.count}.")
        urls_per_identity = urls_per_identity[: args.count]
    else:
        urls_per_identity = [DEFAULT_IMAGE_URLS] * args.count

    identities = []
    for i in range(args.count):
        urls = urls_per_identity[i] if i < len(urls_per_identity) else DEFAULT_IMAGE_URLS
        if len(urls) < 5:
            urls = urls + DEFAULT_IMAGE_URLS[: 5 - len(urls)]
        identities.append({
            "user_id": "benchmark",
            "identity_id": f"identity_{i + 1:03d}",
            "image_urls": urls[: max(5, len(urls))],
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(identities, f, indent=2)
    print(f"[OK] Wrote {len(identities)} identities to {out_path}")
    if not args.urls_file:
        print("[INFO] Replace image_urls with your real identity image URLs (≥5 per identity) before running the benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
