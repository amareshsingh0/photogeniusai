"""
Base model dataset curation: deduplication.
- Perceptual hash (pHash) or file hash to detect near-duplicates and exact duplicates.
- Output: manifest with duplicate groups or a deduped list.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from PIL import Image
    import imagehash
    _HASH_AVAILABLE = True
except ImportError:
    _HASH_AVAILABLE = False


def file_hash(path: Path | str) -> str:
    """SHA-256 of file contents (exact duplicate detection)."""
    path = Path(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def perceptual_hash(path: Path | str) -> str | None:
    """Perceptual hash (pHash) for near-duplicate detection. Returns hex string or None."""
    if not _HASH_AVAILABLE:
        return None
    try:
        img = Image.open(path).convert("RGB")
        ph = imagehash.phash(img)
        return str(ph)
    except Exception:
        return None


def dedup_by_file_hash(manifest_path: Path | str) -> list[dict[str, Any]]:
    """
    Read JSONL manifest; keep first occurrence of each file hash; return deduped list.
    Each row should have "path" key.
    """
    seen: set[str] = set()
    deduped = []
    path = Path(manifest_path)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            p = row.get("path")
            if not p or not Path(p).exists():
                continue
            h = file_hash(p)
            if h in seen:
                continue
            seen.add(h)
            row["file_hash"] = h
            deduped.append(row)
    return deduped


def dedup_by_phash(
    manifest_path: Path | str,
    threshold: int = 2,
) -> list[dict[str, Any]]:
    """
    Deduplicate by perceptual hash. Keep first of each group within Hamming distance threshold.
    """
    if not _HASH_AVAILABLE:
        return dedup_by_file_hash(manifest_path)

    path = Path(manifest_path)
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            p = row.get("path")
            if not p or not Path(p).exists():
                continue
            ph = perceptual_hash(p)
            row["phash"] = ph
            rows.append(row)

    kept = []
    for row in rows:
        ph = row.get("phash")
        if not ph:
            kept.append(row)
            continue
        try:
            h = imagehash.hex_to_hash(ph)
        except Exception:
            kept.append(row)
            continue
        is_dup = False
        for other in kept:
            op = other.get("phash")
            if not op:
                continue
            try:
                if imagehash.hex_to_hash(op) - h <= threshold:
                    is_dup = True
                    break
            except Exception:
                pass
        if not is_dup:
            kept.append(row)
    return kept


def run_dedup(
    manifest_path: Path | str,
    output_path: Path | str | None = None,
    use_phash: bool = True,
) -> list[dict[str, Any]]:
    """Run dedup; write JSONL if output_path given. Returns deduped list."""
    deduped = dedup_by_phash(manifest_path) if use_phash else dedup_by_file_hash(manifest_path)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for row in deduped:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return deduped


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Deduplicate base model manifest")
    p.add_argument("manifest", type=Path)
    p.add_argument("--output", "-o", type=Path, default=None)
    p.add_argument("--file-hash-only", action="store_true", help="Use file hash only (no phash)")
    args = p.parse_args()
    out = run_dedup(args.manifest, args.output, use_phash=not args.file_hash_only)
    print(f"Deduped: {len(out)} rows")
    if args.output:
        print(f"Wrote {args.output}")
