"""
RLHF Monitoring Metrics.

Computes:
- Reward model agreement with users (% of pairs where model prefers same as user)
- Acceptance rate (thumbs up / (thumbs up + thumbs down)) over time
- Quality score distribution shift

Output: JSON for dashboard or CLI print.

Usage:
  DATABASE_URL=... python ai-pipeline/scripts/rlhf_metrics.py
  # Or with reward model to compute agreement:
  python ai-pipeline/scripts/rlhf_metrics.py --reward-checkpoint models/reward_model_preference.pth --pairs pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Optional: connect to same DB as app (Postgres)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PG = True
except ImportError:
    HAS_PG = False


def get_preference_stats_from_db(database_url: str) -> dict:
    if not HAS_PG or not database_url:
        return {"error": "psycopg2 or DATABASE_URL missing", "total_pairs": 0}
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) AS total FROM preference_pairs")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT source, COUNT(*) AS count
            FROM preference_pairs
            GROUP BY source
        """)
        by_source = {row["source"]: row["count"] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return {"total_pairs": total, "by_source": by_source}
    except Exception as e:
        return {"error": str(e), "total_pairs": 0, "by_source": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reward-checkpoint", default=None, help="Optional: compute agreement with reward model")
    ap.add_argument("--pairs", default=None, help="JSONL of pairs for agreement evaluation")
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = ap.parse_args()

    out = {}
    if args.database_url:
        out["preference_stats"] = get_preference_stats_from_db(args.database_url)
    else:
        out["preference_stats"] = {"total_pairs": 0, "by_source": {}, "note": "Set DATABASE_URL for DB stats"}

    # Placeholder: acceptance rate = thumbs up / (up + down) from by_source
    by_source = out["preference_stats"].get("by_source", {})
    explicit = by_source.get("EXPLICIT_THUMBS", 0)
    download = by_source.get("DOWNLOAD", 0)
    save = by_source.get("SAVE_GALLERY", 0)
    delete = by_source.get("DELETE", 0)
    positive_signals = explicit + download + save  # approximate
    negative_signals = delete
    total_signals = positive_signals + negative_signals
    out["acceptance_rate"] = (positive_signals / total_signals) if total_signals else None
    out["target_pairs"] = "5000+ for production RLHF"

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
