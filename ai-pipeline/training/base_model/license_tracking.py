"""
Base model dataset curation: license tracking.
- Each image source has a license type (user_consent, commercial_license, public_domain).
- Manifest rows can include license and source; we produce a single license_manifest.json for the dataset version.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LICENSE_TYPES = ("user_consent", "commercial_license", "public_domain", "unknown")


def build_license_manifest(
    manifest_path: Path | str,
    source_to_license: dict[str, str] | None = None,
    output_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Read JSONL manifest; assume each row may have "source" or infer from path;
    build license_manifest with counts per license and list of paths per license.
    """
    path = Path(manifest_path)
    source_to_license = source_to_license or {}
    # Default: infer source from path segments
    def infer_source(row: dict) -> str:
        p = row.get("path", "")
        if "user-optin" in p or "user_optin" in p:
            return "user_optin"
        if "licensed_stock" in p or "stock" in p:
            return "licensed_stock"
        if "public_domain" in p or "public_domain" in p:
            return "public_domain"
        return row.get("source", "unknown")

    by_license: dict[str, list[str]] = {k: [] for k in LICENSE_TYPES}
    by_license.setdefault("unknown", [])

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            p = row.get("path")
            if not p:
                continue
            source = infer_source(row)
            license_type = source_to_license.get(source, source_to_license.get("default", "unknown"))
            if license_type not in by_license:
                by_license[license_type] = []
            by_license[license_type].append(p)

    manifest = {
        "version": "1.0",
        "manifest_path": str(path),
        "total_images": sum(len(v) for v in by_license.values()),
        "by_license": {k: len(v) for k, v in by_license.items()},
        "paths_by_license": {k: v for k, v in by_license.items() if v},
    }
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Build license manifest for base model dataset")
    p.add_argument("manifest", type=Path)
    p.add_argument("--output", "-o", type=Path, required=True)
    p.add_argument("--source-license", nargs=2, action="append", metavar=("SOURCE", "LICENSE"),
                   help="e.g. user_optin user_consent")
    args = p.parse_args()
    mapping = dict(args.source_license) if getattr(args, "source_license", None) else None
    build_license_manifest(args.manifest, mapping, args.output)
    print(f"Wrote {args.output}")
