# PhotoGenius AWS Monitoring (Task 5.1)

## Dashboards

### dashboard.json (pipeline metrics)

- **dashboard.json**: CloudWatch dashboard with widgets for:
  - Validation first-try success rate (by category)
  - Refinement loops average
  - Aesthetic guidance time (ms)
  - Constraint solver execution time (ms)
  - Typography OCR accuracy
  - Math validation pass rate
  - Request & error count
  - Alarm status and configuration notes

### Deploy dashboard

```bash
# Replace REGION with your AWS region (e.g. us-east-1)
export REGION=us-east-1
# Optional: substitute region in dashboard (sed or use deploy script)
aws cloudwatch put-dashboard --dashboard-name PhotoGenius-Production --dashboard-body file://dashboard.json
```

Application (or a metrics Lambda) must publish custom metrics to namespace **PhotoGenius** with names:

- `ValidationFirstTrySuccessRate` (dimension Category optional)
- `RefinementLoopsAvg`
- `AestheticGuidanceTimeMs`
- `ConstraintSolverExecutionTimeMs`
- `TypographyOcrAccuracy`
- `MathValidationPassRate`
- `RequestCount`, `ErrorCount`

### observability-dashboard.json (correlation ID & tracing)

- **observability-dashboard.json**: Observability-focused dashboard:
  - Generation Lambda invocations, errors, duration (p99, max), concurrency, throttles
  - Custom namespace request/error count and generation latency (if emitted)
  - Text widget with **Logs Insights** query snippets to search by **correlation_id** (X-Request-ID)

Deploy:

```bash
aws cloudwatch put-dashboard --dashboard-name PhotoGenius-Observability --dashboard-body file://observability-dashboard.json
```

After deploy, edit the dashboard and replace `PhotoGenius-GenerationFunction-*` with your actual Lambda function name(s) if they differ. Use **Logs Insights** on the Lambda log group with the documented queries to trace a request end-to-end. Runbooks: `docs/runbooks/OBSERVABILITY_RUNBOOKS.md`.

## Alarms

- **alarms.yaml**: CloudFormation template for:
  - **Validation first-try success < 90%** (2 periods of 5 min) → SNS
  - **Typography OCR accuracy < 70%** → SNS
  - **Math validation pass rate < 98%** → SNS

### Deploy alarms

```bash
aws cloudformation deploy --template-file alarms.yaml --stack-name photogenius-alarms \
  --parameter-overrides SnsTopicArn=arn:aws:sns:REGION:ACCOUNT:your-topic
```

## Circuit breakers (observability.py)

- **Auto-validation**: If validation first-try failure rate > 20% over 5 minutes, auto-validation is disabled for 10 minutes; SNS alert when `CIRCUIT_SNS_ALERT_TOPIC_ARN` is set.
- **Typography**: If OCR failure rate > 30% over 5 minutes, fall back to no-text mode for 10 minutes; SNS alert.

Env: `CIRCUIT_VALIDATION_FAILURE_RATE_THRESHOLD`, `CIRCUIT_TYPOGRAPHY_FAILURE_RATE_THRESHOLD`, `CIRCUIT_SNS_ALERT_TOPIC_ARN`.

## Weekly report

- `build_weekly_metrics_report(...)` builds a summary dict (by category, tier, user segment).
- `send_weekly_report_email(report, to_emails, from_email)` sends via SES. Set `WEEKLY_REPORT_TO_EMAILS` (comma-separated) and optionally `WEEKLY_REPORT_FROM_EMAIL`. Schedule via EventBridge (e.g. weekly cron) to call a Lambda that aggregates metrics and calls these.
