"""
Alert System
Monitors metrics and sends alerts for anomalies.
Uses local/EFS storage (DATA_DIR); no Modal. AWS-compatible.
"""

from typing import Dict, List
from datetime import datetime
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


def _median(values: list) -> float:
    if not values:
        return 0.0
    if np is not None:
        return float(np.median(values))
    s = sorted(values)
    n = len(s)
    return float(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def get_baseline_latency() -> float:
    """Get baseline P95 latency."""
    try:
        metrics_file = "/data/metrics.jsonl"
        if metrics_volume.exists(metrics_file):
            latencies = []
            with metrics_volume.open(metrics_file, "r") as f:
                for line in f:
                    metric = json.loads(line)
                    if (
                        "generation_time_p95" in metric
                        and metric["generation_time_p95"]
                    ):
                        latencies.append(metric["generation_time_p95"])
            if latencies:
                return float(_median(latencies[-100:]))
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
                    if "cost_per_image" in metric and metric["cost_per_image"]:
                        costs.append(metric["cost_per_image"])
            if costs:
                return float(_median(costs[-100:]))
    except Exception:
        pass
    return 0.05


def send_alert(alert: Dict) -> None:
    """
    Send alert to configured channels.
    Supports: Slack webhook, PagerDuty (for critical alerts), Email (via SendGrid/SES).
    """
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    pagerduty_key = os.environ.get("PAGERDUTY_INTEGRATION_KEY")

    alert_message = f"""
🚨 **{alert['type'].replace('_', ' ').title()} Alert**

{alert['message']}

**Details:**
- Severity: {alert['severity']}
- Metric: {alert['metric']}
- Current Value: {alert['value']}
- Threshold: {alert.get('threshold', 'N/A')}
- Timestamp: {datetime.utcnow().isoformat()}
"""

    if slack_webhook and httpx is not None:
        try:
            httpx.post(
                slack_webhook,
                json={"text": alert_message, "username": "PhotoGenius Monitoring"},
                timeout=5.0,
            )
            print(f"✅ Alert sent to Slack: {alert['type']}")
        except Exception as e:
            print(f"⚠️ Failed to send Slack alert: {e}")

    if alert.get("severity") == "high" and pagerduty_key and httpx is not None:
        try:
            httpx.post(
                "https://events.pagerduty.com/v2/enqueue",
                json={
                    "routing_key": pagerduty_key,
                    "event_action": "trigger",
                    "payload": {
                        "summary": alert["message"],
                        "severity": alert["severity"],
                        "source": "photogenius-monitoring",
                        "custom_details": alert,
                    },
                },
                timeout=5.0,
            )
            print(f"✅ Alert sent to PagerDuty: {alert['type']}")
        except Exception as e:
            print(f"⚠️ Failed to send PagerDuty alert: {e}")

    try:
        alerts_file = "/data/alerts.jsonl"
        with metrics_volume.open(alerts_file, "a", encoding="utf-8") as f:
            alert_record = {**alert, "timestamp": datetime.utcnow().isoformat()}
            f.write(json.dumps(alert_record) + "\n")
    except Exception as e:
        print(f"⚠️ Failed to store alert: {e}")


def check_alerts(metrics: Dict) -> List[Dict]:
    """
    Check if any metrics trigger alerts.
    Returns list of triggered alerts.
    """
    alerts = []

    if (
        metrics.get("face_similarity_mean") is not None
        and metrics["face_similarity_mean"] < 0.85
    ):
        alerts.append(
            {
                "severity": "high",
                "type": "quality_degradation",
                "message": f"Face similarity dropped to {metrics['face_similarity_mean']:.2%} (threshold: 85%)",
                "metric": "face_similarity_mean",
                "value": metrics["face_similarity_mean"],
                "threshold": 0.85,
            }
        )

    error_rate = metrics.get("error_rate", 0.0)
    if error_rate > 0.05:
        alerts.append(
            {
                "severity": "high",
                "type": "error_rate",
                "message": f"Error rate spiked to {error_rate:.1%} (threshold: 5%)",
                "metric": "error_rate",
                "value": error_rate,
                "threshold": 0.05,
            }
        )

    p95_latency = metrics.get("generation_time_p95")
    if p95_latency:
        baseline_p95 = get_baseline_latency()
        if p95_latency > baseline_p95 * 2:
            alerts.append(
                {
                    "severity": "medium",
                    "type": "latency_spike",
                    "message": f"P95 latency is {p95_latency:.1f}s (2x baseline of {baseline_p95:.1f}s)",
                    "metric": "generation_time_p95",
                    "value": p95_latency,
                    "threshold": baseline_p95 * 2,
                    "baseline": baseline_p95,
                }
            )

    cost_per_image = metrics.get("cost_per_image", 0.0)
    if cost_per_image > 0:
        baseline_cost = get_baseline_cost()
        if cost_per_image > baseline_cost * 1.2:
            alerts.append(
                {
                    "severity": "medium",
                    "type": "cost_spike",
                    "message": f"Cost per image increased 20%: ${cost_per_image:.4f} (baseline: ${baseline_cost:.4f})",
                    "metric": "cost_per_image",
                    "value": cost_per_image,
                    "threshold": baseline_cost * 1.2,
                    "baseline": baseline_cost,
                }
            )

    thumbs_down_rate = metrics.get("thumbs_down_rate")
    if thumbs_down_rate is not None and thumbs_down_rate > 0.15:
        alerts.append(
            {
                "severity": "medium",
                "type": "user_satisfaction",
                "message": f"Thumbs down rate high: {thumbs_down_rate:.1%} (threshold: 15%)",
                "metric": "thumbs_down_rate",
                "value": thumbs_down_rate,
                "threshold": 0.15,
            }
        )

    if metrics.get("total_generations", 0) == 0:
        alerts.append(
            {
                "severity": "low",
                "type": "no_activity",
                "message": "No generations in the last 5 minutes",
                "metric": "total_generations",
                "value": 0,
                "threshold": 1,
            }
        )

    for alert in alerts:
        send_alert(alert)
        print(f"  🚨 Alert triggered: {alert['type']} ({alert['severity']})")

    return alerts


def check_alerts_now() -> List[Dict]:
    """Manually trigger alert check. Uses MetricsCollector directly (no Modal .remote())."""
    from .metrics import MetricsCollector

    collector = MetricsCollector()
    metrics = collector.collect_metrics()
    return check_alerts(metrics)


__all__ = ["check_alerts", "send_alert"]
