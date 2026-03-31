"""
Dashboard and Reporting System
Generates reports and dashboard data for visualization.
Uses local/EFS storage (DATA_DIR); no Modal. AWS-compatible.
"""

from datetime import datetime, timedelta
from typing import Dict, List
import json
import os

try:
    import numpy as np  # type: ignore[reportMissingImports]
except ImportError:
    np = None  # type: ignore[assignment]

try:
    import httpx  # type: ignore[reportMissingImports]
except ImportError:
    httpx = None  # type: ignore[assignment]

from .storage import metrics_volume


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    if np is not None:
        return float(np.mean(values))
    return sum(values) / len(values)


def get_metrics(start: datetime, end: datetime) -> List[Dict]:
    """Get metrics for time range."""
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


def calculate_trend(values: List[float]) -> str:
    """Calculate trend direction."""
    if len(values) < 2:
        return "insufficient_data"
    recent = values[-10:] if len(values) >= 10 else values
    older = values[-20:-10] if len(values) >= 20 else values[: len(recent)]
    if not older:
        return "insufficient_data"
    recent_avg = _mean(recent)
    older_avg = _mean(older)
    change = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
    if abs(change) < 0.05:
        return "stable"
    if change > 0:
        return f"increasing_{abs(change):.1%}"
    return f"decreasing_{abs(change):.1%}"


def get_top_errors(start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
    """Get top error types in time range."""
    metrics = get_metrics(start, end)
    error_counts = {}
    for metric in metrics:
        for error_type, count in metric.get("error_types", {}).items():
            error_counts[error_type] = error_counts.get(error_type, 0) + count
    top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {"error_type": error_type, "count": count} for error_type, count in top_errors
    ]


def get_mode_distribution(start: datetime, end: datetime) -> Dict[str, float]:
    """Get mode distribution for time range."""
    metrics = get_metrics(start, end)
    if not metrics:
        return {}
    total_generations = sum(m.get("total_generations", 0) for m in metrics)
    if total_generations == 0:
        return {}
    mode_totals = {}
    for metric in metrics:
        mode_dist = metric.get("mode_distribution", {})
        generations = metric.get("total_generations", 0)
        for mode, rate in mode_dist.items():
            mode_totals[mode] = mode_totals.get(mode, 0) + (rate * generations)
    return {mode: total / total_generations for mode, total in mode_totals.items()}


def generate_dashboard_report() -> Dict:
    """
    Generate 6-hour summary report.
    Sends report to Slack/Email and stores for dashboard.
    """
    now = datetime.utcnow()
    start = now - timedelta(hours=6)
    print(f"\n📊 Generating dashboard report: {start.isoformat()} to {now.isoformat()}")

    metrics = get_metrics(start, now)
    if not metrics:
        print("  No metrics found for this period")
        return {"error": "No metrics available"}

    total_generations = sum(m.get("total_generations", 0) for m in metrics)
    similarities = [
        m["face_similarity_mean"] for m in metrics if m.get("face_similarity_mean")
    ]
    times = [
        m["generation_time_mean"] for m in metrics if m.get("generation_time_mean")
    ]
    costs = [m.get("total_cost", 0) for m in metrics]
    error_rates = [m.get("error_rate", 0) for m in metrics]

    report = {
        "period": {
            "start": start.isoformat(),
            "end": now.isoformat(),
            "duration_hours": 6,
        },
        "summary": {
            "total_generations": total_generations,
            "unique_users": len(set(m.get("unique_users", 0) for m in metrics)),
            "avg_face_similarity": float(_mean(similarities)) if similarities else None,
            "avg_generation_time": float(_mean(times)) if times else None,
            "total_cost": float(sum(costs)),
            "avg_cost_per_image": (
                float(sum(costs) / total_generations) if total_generations > 0 else 0.0
            ),
            "avg_error_rate": float(_mean(error_rates)) if error_rates else 0.0,
            "total_errors": sum(m.get("error_count", 0) for m in metrics),
        },
        "trends": {
            "face_similarity_trend": (
                calculate_trend(similarities) if similarities else "insufficient_data"
            ),
            "latency_trend": calculate_trend(times) if times else "insufficient_data",
            "cost_trend": calculate_trend(
                [m.get("cost_per_image", 0) for m in metrics if m.get("cost_per_image")]
            ),
        },
        "top_errors": get_top_errors(start, now),
        "mode_popularity": get_mode_distribution(start, now),
        "user_satisfaction": {
            "thumbs_up_rate": (
                _mean(
                    [
                        m.get("thumbs_up_rate", 0)
                        for m in metrics
                        if m.get("thumbs_up_rate") is not None
                    ]
                )
                if any(m.get("thumbs_up_rate") is not None for m in metrics)
                else None
            ),
            "thumbs_down_rate": (
                _mean(
                    [
                        m.get("thumbs_down_rate", 0)
                        for m in metrics
                        if m.get("thumbs_down_rate") is not None
                    ]
                )
                if any(m.get("thumbs_down_rate") is not None for m in metrics)
                else None
            ),
        },
    }

    try:
        reports_file = "/data/reports.jsonl"
        with metrics_volume.open(reports_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(report) + "\n")
    except Exception as e:
        print(f"⚠️ Failed to store report: {e}")

    send_report(report)
    print(f"  ✅ Report generated: {total_generations} generations")
    return report


def send_report(report: Dict) -> None:
    """Send report to configured channels (Slack webhook)."""
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not slack_webhook:
        return

    summary = report["summary"]
    avg_sim = summary.get("avg_face_similarity")
    avg_sim_str = f"{avg_sim:.2%}" if avg_sim is not None else "N/A"

    top_errors = report.get("top_errors", [])[:5]
    top_errors_lines = "\n".join(
        f"• {e['error_type']}: {e['count']}" for e in top_errors
    )

    report_message = f"""
📊 **PhotoGenius 6-Hour Report**

**Period:** {report['period']['start']} to {report['period']['end']}

**Summary:**
• Total Generations: {summary['total_generations']:,}
• Avg Face Similarity: {avg_sim_str}
• Avg Generation Time: {summary.get('avg_generation_time') or 0:.1f}s
• Total Cost: ${summary['total_cost']:.2f}
• Avg Cost/Image: ${summary.get('avg_cost_per_image', 0):.4f}
• Error Rate: {summary.get('avg_error_rate', 0):.1%}

**Trends:**
• Face Similarity: {report['trends']['face_similarity_trend']}
• Latency: {report['trends']['latency_trend']}
• Cost: {report['trends']['cost_trend']}

**Top Errors:**
{top_errors_lines}
"""

    if httpx is not None:
        try:
            httpx.post(
                slack_webhook,
                json={"text": report_message, "username": "PhotoGenius Dashboard"},
                timeout=10.0,
            )
            print("✅ Report sent to Slack")
        except Exception as e:
            print(f"⚠️ Failed to send report: {e}")


def detect_quality_regression() -> Dict:
    """
    Compare today's quality vs last week.
    Runs daily to detect quality regressions.
    """
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_week_end = last_week + timedelta(days=1)

    print("\n🔍 Detecting quality regression...")
    print(f"  Today: {yesterday.isoformat()} to {today.isoformat()}")
    print(f"  Last week: {last_week.isoformat()} to {last_week_end.isoformat()}")

    today_metrics = get_metrics(yesterday, today)
    last_week_metrics = get_metrics(last_week, last_week_end)

    if not today_metrics or not last_week_metrics:
        print("  ⚠️ Insufficient data for comparison")
        return {"error": "Insufficient data"}

    today_similarities = [
        m["face_similarity_mean"]
        for m in today_metrics
        if m.get("face_similarity_mean")
    ]
    last_week_similarities = [
        m["face_similarity_mean"]
        for m in last_week_metrics
        if m.get("face_similarity_mean")
    ]

    if not today_similarities or not last_week_similarities:
        print("  ⚠️ No similarity data available")
        return {"error": "No similarity data"}

    today_similarity = float(_mean(today_similarities))
    last_week_similarity = float(_mean(last_week_similarities))
    regression = last_week_similarity - today_similarity

    print(f"  Today: {today_similarity:.3f}")
    print(f"  Last week: {last_week_similarity:.3f}")
    print(f"  Regression: {regression:.3f}")

    result = {
        "today_similarity": today_similarity,
        "last_week_similarity": last_week_similarity,
        "regression": regression,
        "regression_percent": (
            (regression / last_week_similarity * 100) if last_week_similarity > 0 else 0
        ),
        "passed": regression < 0.05,
        "timestamp": today.isoformat(),
    }

    if regression > 0.05:
        from .alerts import send_alert

        alert = {
            "severity": "high",
            "type": "quality_regression",
            "message": f"Face similarity regressed by {regression:.1%} compared to last week",
            "metric": "face_similarity_mean",
            "today_value": today_similarity,
            "last_week_value": last_week_similarity,
            "regression": regression,
            "regression_percent": result["regression_percent"],
        }
        send_alert(alert)
        print(f"  🚨 Quality regression detected: {regression:.1%}")
    else:
        print("  ✅ No significant regression detected")

    try:
        regression_file = "/data/regressions.jsonl"
        with metrics_volume.open(regression_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
    except Exception as e:
        print(f"⚠️ Failed to store regression data: {e}")

    return result


def get_dashboard_data(hours: int = 24) -> Dict:
    """Get dashboard data for visualization."""
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    metrics = get_metrics(start, end)

    face_means = [
        m["face_similarity_mean"] for m in metrics if m.get("face_similarity_mean")
    ]
    time_means = [
        m["generation_time_mean"] for m in metrics if m.get("generation_time_mean")
    ]

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "hours": hours},
        "metrics": metrics,
        "summary": {
            "total_generations": sum(m.get("total_generations", 0) for m in metrics),
            "avg_face_similarity": float(_mean(face_means)) if face_means else None,
            "avg_generation_time": float(_mean(time_means)) if time_means else None,
            "total_cost": sum(m.get("total_cost", 0) for m in metrics),
            "avg_error_rate": (
                float(_mean([m.get("error_rate", 0) for m in metrics]))
                if metrics
                else 0.0
            ),
        },
    }
