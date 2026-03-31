#!/usr/bin/env python3
"""Check SageMaker CloudWatch logs for model loading errors."""
import boto3
import sys

logs = boto3.client("logs", region_name="us-east-1")
log_group = "/aws/sagemaker/Endpoints/photogenius-standard"

print(f"Checking logs: {log_group}")

try:
    streams = logs.describe_log_streams(
        logGroupName=log_group, orderBy="LastEventTime", descending=True, limit=3
    )
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

for stream in streams.get("logStreams", [])[:2]:
    print(f"\n=== Stream: {stream['logStreamName'][:60]}... ===")
    events = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream["logStreamName"],
        limit=50,
        startFromHead=False,
    )
    for event in events.get("events", []):
        msg = event["message"]
        # Skip tqdm progress bars
        if "%|" not in msg and "it/s]" not in msg:
            print(msg[:250])
