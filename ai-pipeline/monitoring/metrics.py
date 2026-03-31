"""
Metrics Collection System
Collects and aggregates production metrics every 5 minutes.
Uses local/EFS storage (DATA_DIR); no Modal. AWS-compatible.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

try:
    import numpy as np  # type: ignore[reportMissingImports]

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None

from .storage import metrics_volume


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    if _HAS_NUMPY and np is not None:
        return float(np.median(values))
    s = sorted(values)
    n = len(s)
    return float(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    if _HAS_NUMPY and np is not None:
        return float(np.mean(values))
    return sum(values) / len(values)


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if _HAS_NUMPY and np is not None:
        return float(np.percentile(values, p))
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    return float(s[f]) if f == c else s[f] + (k - f) * (s[c] - s[f])


def get_generations(start: datetime, end: datetime) -> List[Dict]:
    """
    Fetch generation logs from storage.
    In production, this would query from database (Postgres/Supabase).
    Uses local/EFS path (DATA_DIR) for AWS compatibility.
    """
    generations = []
    try:
        logs_file = "/data/generation_logs.json"
        if metrics_volume.exists(logs_file):
            with metrics_volume.open(logs_file, "r") as f:
                all_logs = json.load(f)
                for log in all_logs:
                    log_time = datetime.fromisoformat(log.get("timestamp", ""))
                    if start <= log_time <= end:
                        generations.append(log)
    except Exception as e:
        print(f"Warning: Failed to load generation logs: {e}")
    return generations


def store_metrics(metrics: Dict) -> None:
    """Store metrics to storage (JSONL)."""
    try:
        metrics_file = "/data/metrics.jsonl"
        with metrics_volume.open(metrics_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics) + "\n")
    except Exception as e:
        print(f"Warning: Failed to store metrics: {e}")


def count_error_types(generations: List[Dict]) -> Dict[str, int]:
    """Count error types from generations."""
    error_types = {}
    for gen in generations:
        if gen.get("status") == "failed":
            error_type = gen.get("error_type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
    return error_types


def get_baseline_latency() -> float:
    """Get baseline P95 latency (from historical data)."""
    try:
        metrics_file = "/data/metrics.jsonl"
        if metrics_volume.exists(metrics_file):
            latencies = []
            with metrics_volume.open(metrics_file, "r") as f:
                for line in f:
                    metric = json.loads(line)
                    if "generation_time_p95" in metric:
                        latencies.append(metric["generation_time_p95"])
            if latencies:
                return _median(latencies[-100:])
    except Exception:
        pass
    return 50.0


def get_baseline_cost() -> float:
    """Get baseline cost per image."""
    try:
        metrics_file = "/data/metrics.jsonl"
        if metrics_volume.exists(metrics_file):
            costs = []
            with metrics_volume.open(metrics_file, "r") as f:
                for line in f:
                    metric = json.loads(line)
                    if "cost_per_image" in metric:
                        costs.append(metric["cost_per_image"])
            if costs:
                return _median(costs[-100:])
    except Exception:
        pass
    return 0.05


class MetricsCollector:
    """
    Collect and aggregate metrics from production.
    Runs locally or on AWS (Lambda/ECS); no Modal. Calls are direct (no .remote()).
    """

    def collect_metrics(self) -> Dict:
        """
        Collect metrics from past 5 minutes.
        Returns dictionary with all collected metrics.
        """
        now = datetime.utcnow()
        start = now - timedelta(minutes=5)
        print(f"\n📊 Collecting metrics: {start.isoformat()} to {now.isoformat()}")

        generations = get_generations(start, now)
        if not generations:
            print("  No generations found in this period")
            return {
                "timestamp": now.isoformat(),
                "period_minutes": 5,
                "total_generations": 0,
            }

        similarities = [g["similarity"] for g in generations if g.get("similarity")]
        times = [g["time_seconds"] for g in generations if g.get("time_seconds")]
        costs = [g.get("cost", 0.0) for g in generations]
        ratings = [g.get("rating") for g in generations if g.get("rating")]

        metrics = {
            "timestamp": now.isoformat(),
            "period_minutes": 5,
            "total_generations": len(generations),
            "unique_users": len(
                set(g["user_id"] for g in generations if g.get("user_id"))
            ),
            "face_similarity_mean": (
                float(_mean(similarities)) if similarities else None
            ),
            "face_similarity_p50": (
                float(_percentile(similarities, 50)) if similarities else None
            ),
            "face_similarity_p95": (
                float(_percentile(similarities, 95)) if similarities else None
            ),
            "face_similarity_p99": (
                float(_percentile(similarities, 99)) if similarities else None
            ),
            "face_similarity_min": float(min(similarities)) if similarities else None,
            "face_similarity_max": float(max(similarities)) if similarities else None,
            "generation_time_mean": float(_mean(times)) if times else None,
            "generation_time_p50": float(_percentile(times, 50)) if times else None,
            "generation_time_p95": float(_percentile(times, 95)) if times else None,
            "generation_time_p99": float(_percentile(times, 99)) if times else None,
            "generation_time_min": float(min(times)) if times else None,
            "generation_time_max": float(max(times)) if times else None,
            "error_rate": (
                len([g for g in generations if g.get("status") == "failed"])
                / len(generations)
                if generations
                else 0.0
            ),
            "error_count": len([g for g in generations if g.get("status") == "failed"]),
            "error_types": count_error_types(generations),
            "total_cost": float(sum(costs)),
            "cost_per_image": (
                float(sum(costs) / len(generations)) if generations else 0.0
            ),
            "cost_per_user": (
                float(
                    sum(costs)
                    / len(set(g["user_id"] for g in generations if g.get("user_id")))
                )
                if generations
                else 0.0
            ),
            "thumbs_up_count": len([r for r in ratings if r == "up"]),
            "thumbs_down_count": len([r for r in ratings if r == "down"]),
            "thumbs_up_rate": (
                len([r for r in ratings if r == "up"]) / len(ratings)
                if ratings
                else None
            ),
            "thumbs_down_rate": (
                len([r for r in ratings if r == "down"]) / len(ratings)
                if ratings
                else None
            ),
            "mode_distribution": {
                mode: len([g for g in generations if g.get("mode") == mode])
                / len(generations)
                for mode in ["REALISM", "CREATIVE", "FASHION", "CINEMATIC", "ROMANTIC"]
            },
            "identity_usage_rate": (
                len([g for g in generations if g.get("identity_id")]) / len(generations)
                if generations
                else 0.0
            ),
            "avg_quality_score": (
                float(
                    _mean(
                        [
                            g["quality_score"]
                            for g in generations
                            if g.get("quality_score")
                        ]
                    )
                )
                if any(g.get("quality_score") for g in generations)
                else None
            ),
        }

        store_metrics(metrics)
        print(f"  ✅ Collected metrics: {metrics['total_generations']} generations")
        if metrics.get("face_similarity_mean") is not None:
            print(f"     Face similarity: {metrics['face_similarity_mean']:.3f}")
        else:
            print("     Face similarity: N/A")
        print(f"     Error rate: {metrics['error_rate']:.1%}")
        print(f"     Cost per image: ${metrics['cost_per_image']:.4f}")

        self.check_alerts(metrics)
        return metrics

    def check_alerts(self, metrics: Dict) -> List[Dict]:
        """Check if any metrics trigger alerts. Called after collection."""
        try:
            from .alerts import check_alerts as check_alerts_func

            return check_alerts_func(metrics)
        except Exception as e:
            print(f"  ⚠️ Alert check failed: {e}")
            return []

    def get_metrics(self, start: datetime, end: datetime) -> List[Dict]:
        """Get metrics for a time range."""
        metrics_file = "/data/metrics.jsonl"
        metrics = []
        try:
            if metrics_volume.exists(metrics_file):
                with metrics_volume.open(metrics_file, "r") as f:
                    for line in f:
                        metric = json.loads(line)
                        metric_time = datetime.fromisoformat(metric["timestamp"])
                        if start <= metric_time <= end:
                            metrics.append(metric)
        except Exception as e:
            print(f"Error loading metrics: {e}")
        return metrics


def collect_metrics_scheduled() -> Dict:
    """Scheduled metrics collection (call from cron/Lambda/ECS). No Modal .remote()."""
    collector = MetricsCollector()
    return collector.collect_metrics()


metrics_collector = MetricsCollector()
