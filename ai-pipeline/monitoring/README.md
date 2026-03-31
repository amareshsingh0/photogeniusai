# Production Monitoring System

**Track quality, performance, costs, and user satisfaction in production.**

Catch issues before users complain. Ensure 99.9% uptime and consistent quality.

## Features

- ✅ **Real-time Metrics Collection** - Every 5 minutes
- ✅ **Quality Monitoring** - Face similarity, error rates
- ✅ **Performance Tracking** - P50, P95, P99 latencies
- ✅ **Cost Tracking** - Cost per image, cost trends
- ✅ **User Satisfaction** - Thumbs up/down rates
- ✅ **Proactive Alerts** - Slack, PagerDuty integration
- ✅ **Dashboard Reports** - 6-hour summaries
- ✅ **Quality Regression Detection** - Daily comparisons

## Architecture

```
┌──────────────────────────────────────────┐
│         MONITORING SYSTEM                │
│                                          │
│  Metrics Collector (every 5 min)        │
│  ↓                                       │
│  Alert Checker                           │
│  ↓                                       │
│  Dashboard Generator (every 6 hours)   │
│  ↓                                       │
│  Quality Regression (daily)              │
└──────────────────────────────────────────┘
```

## Quick Start

### Deploy Monitoring System

```bash
cd ai-pipeline/monitoring
modal deploy metrics.py
modal deploy alerts.py
modal deploy dashboard.py
```

### Set Up Alert Channels

```bash
# Slack webhook
modal secret create monitoring SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# PagerDuty (optional, for critical alerts)
modal secret create monitoring PAGERDUTY_INTEGRATION_KEY=your_key
```

### Integrate Logging

Add to your services (orchestrator, identity engine):

```python
from ai_pipeline.monitoring.logger import log_generation

# After generation completes
log_generation(
    user_id=user_id,
    generation_id=job_id,
    mode=mode,
    time_seconds=elapsed_time,
    status="completed",
    similarity=result.get("face_similarity", 0.95),
    quality_score=result.get("quality_score", 90),
    cost=estimated_cost,
    identity_id=identity_id,
)
```

## Metrics Collected

### Quality Metrics
- Face similarity (mean, P50, P95, P99, min, max)
- Quality scores
- Error rates
- Error type distribution

### Performance Metrics
- Generation time (mean, P50, P95, P99, min, max)
- Latency trends
- Throughput (generations per period)

### Cost Metrics
- Total cost per period
- Cost per image
- Cost per user
- Cost trends

### User Satisfaction
- Thumbs up rate
- Thumbs down rate
- Rating distribution

### Usage Metrics
- Total generations
- Unique users
- Mode distribution
- Identity usage rate

## Alerts

### High Severity Alerts

**Face Similarity < 85%**
- Triggers when average face similarity drops below 85%
- Indicates quality degradation
- Action: Investigate model performance

**Error Rate > 5%**
- Triggers when error rate exceeds 5%
- Indicates system instability
- Action: Check logs, investigate failures

### Medium Severity Alerts

**Latency Spike (2x baseline)**
- Triggers when P95 latency exceeds 2x baseline
- Indicates performance degradation
- Action: Check GPU availability, optimize

**Cost Spike (20% increase)**
- Triggers when cost per image increases 20%
- Indicates cost inefficiency
- Action: Review resource usage

**Thumbs Down Rate > 15%**
- Triggers when user dissatisfaction is high
- Indicates quality issues
- Action: Review recent generations

### Low Severity Alerts

**No Activity**
- Triggers when no generations in 5 minutes
- Indicates potential downtime
- Action: Check system status

## Dashboard Reports

### 6-Hour Summary Report

Generated every 6 hours, includes:
- Total generations
- Average face similarity
- Average generation time
- Total cost
- Error rate
- Trends (similarity, latency, cost)
- Top errors
- Mode popularity
- User satisfaction

### Daily Quality Regression Check

Compares today's quality vs last week:
- Detects >5% regression in face similarity
- Sends high-severity alert if detected
- Stores regression data for analysis

## Integration

### With Orchestrator

```python
# In orchestrator.py, after generation:
from ai_pipeline.monitoring.logger import log_generation
import time

start_time = time.time()
result = self._execute_plan(...)
elapsed_time = time.time() - start_time

# Log for monitoring
log_generation(
    user_id=user_id,
    generation_id=f"gen_{job_id}",
    mode=mode,
    time_seconds=elapsed_time,
    status="completed" if result else "failed",
    similarity=result.get("scores", {}).get("face_similarity"),
    quality_score=result.get("scores", {}).get("total"),
    cost=estimate_cost(elapsed_time, mode),
    identity_id=identity_id,
)
```

### With Refinement Engine

```python
# In refinement_engine.py:
from ai_pipeline.monitoring.logger import log_refinement
import time

start_time = time.time()
result = self.refine(...)
elapsed_time = time.time() - start_time

log_refinement(
    user_id=user_id,
    refinement_id=f"ref_{refinement_id}",
    original_generation_id=original_gen_id,
    time_seconds=elapsed_time,
    status="completed",
    cost=estimate_refinement_cost(elapsed_time),
)
```

## Cost Estimation

Example cost calculation:

```python
def estimate_cost(time_seconds: float, mode: str) -> float:
    """Estimate cost based on time and mode"""
    # A10G GPU: ~$0.10/hour = $0.000028/second
    base_cost_per_second = 0.000028
    
    # Mode multipliers
    multipliers = {
        "REALISM": 1.0,
        "CREATIVE": 1.2,
        "ULTRA": 1.5,
    }
    
    multiplier = multipliers.get(mode, 1.0)
    return time_seconds * base_cost_per_second * multiplier
```

## Visualization

### Grafana Integration

1. Set up Grafana data source pointing to metrics volume
2. Import dashboard JSON (create from metrics schema)
3. Visualize:
   - Face similarity over time
   - Latency percentiles
   - Cost trends
   - Error rates

### Metabase Integration

1. Connect Metabase to metrics database
2. Create dashboards:
   - Quality metrics
   - Performance metrics
   - Cost analysis
   - User satisfaction

## API Endpoints

### Get Dashboard Data

```python
from ai_pipeline.monitoring.dashboard import get_dashboard_data

# Get last 24 hours
data = get_dashboard_data.remote(hours=24)
```

### Get Metrics

```python
from ai_pipeline.monitoring.metrics import MetricsCollector
from datetime import datetime, timedelta

collector = MetricsCollector()
end = datetime.utcnow()
start = end - timedelta(hours=1)

metrics = collector.get_metrics.remote(start, end)
```

## Scheduled Jobs

### Metrics Collection
- **Schedule:** Every 5 minutes (`*/5 * * * *`)
- **Function:** `collect_metrics_scheduled()`
- **Action:** Collects and stores metrics

### Dashboard Report
- **Schedule:** Every 6 hours (`0 */6 * * *`)
- **Function:** `generate_dashboard_report()`
- **Action:** Generates and sends report

### Quality Regression
- **Schedule:** Daily at midnight (`0 0 * * *`)
- **Function:** `detect_quality_regression()`
- **Action:** Compares quality vs last week

## Storage

Metrics stored in Modal volume:
- `/data/metrics.jsonl` - Time-series metrics
- `/data/generation_logs.json` - Generation events
- `/data/alerts.jsonl` - Alert history
- `/data/reports.jsonl` - Dashboard reports
- `/data/regressions.jsonl` - Quality regression data

## Best Practices

1. **Log All Generations** - Include in orchestrator/identity engine
2. **Set Up Alerts** - Configure Slack/PagerDuty
3. **Monitor Trends** - Watch for gradual degradation
4. **Review Reports** - Check 6-hour summaries regularly
5. **Investigate Alerts** - Don't ignore quality alerts
6. **Track Costs** - Optimize based on cost metrics

## Troubleshooting

### Metrics Not Collecting
- Check scheduled job is running: `modal app logs photogenius-monitoring`
- Verify volume exists: `modal volume list`
- Check logs for errors

### Alerts Not Firing
- Verify alert thresholds are appropriate
- Check Slack webhook URL is correct
- Review alert logic in `alerts.py`

### High Error Rates
- Check service logs
- Verify GPU availability
- Review recent changes

### Cost Spikes
- Review generation times
- Check for inefficient modes
- Verify cost calculation

## Future Enhancements

- [ ] Real-time dashboard (WebSocket updates)
- [ ] Anomaly detection (ML-based)
- [ ] Predictive alerts (before thresholds)
- [ ] Cost optimization recommendations
- [ ] A/B testing support
- [ ] Custom metric definitions

## Support

For issues:
- Check logs: `modal app logs photogenius-monitoring`
- Review metrics: `get_dashboard_data()`
- Check alerts: `/data/alerts.jsonl`

---

**Status:** ✅ Production-ready monitoring system
