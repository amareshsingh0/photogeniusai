# 🎯 Intelligent Auto-Scaling System

## Overview

**Cost-effective** image generation system jo **automatically** complexity detect karke right GPU use karta hai.

---

## Architecture

### 2 SageMaker Endpoints:

#### 1. **Small Endpoint** (Always On)
- Name: `photogenius-small-dev`
- Instance: `ml.g5.2xlarge` (24GB GPU)
- Cost: **$1.21/hour** (~$870/month)
- Use: Simple images (single person, portrait, simple scenes)
- Status: Always running (cost-effective for common use)

#### 2. **Large Endpoint** (Auto On/Off)
- Name: `photogenius-large-dev`
- Instance: `ml.g5.12xlarge` (96GB GPU)
- Cost: **$7.09/hour** (only when running)
- Use: Complex images (multiple people, objects, detailed scenes)
- Status: **Auto-starts when needed, auto-stops after 5 min idle**

### Smart Router Lambda

Automatically analyzes:
- Number of people in prompt
- Number of objects
- Scene complexity
- Resolution requirements
- Quality tier (FAST/STANDARD/PREMIUM)

**Routes to appropriate endpoint** based on complexity score.

---

## Complexity Detection

### Routes to Small GPU ($1.21/hr):
- ✅ Single person portrait
- ✅ Simple landscape
- ✅ Product photo
- ✅ Basic scenes
- ✅ Standard resolution (1024x1024)
- ✅ Single candidate generation

### Routes to Large GPU ($7.09/hr, auto-scales):
- 🎯 Multiple people ("group photo", "crowd", "family")
- 🎯 Complex scenes ("detailed cityscape", "busy market")
- 🎯 Many objects ("holding flowers and umbrella")
- 🎯 High resolution (>1024x1024)
- 🎯 Multiple candidates (Best-of-N selection)
- 🎯 PREMIUM tier with refinement

---

## Cost Savings Example

### Without Intelligent Scaling:
- Large GPU always on: **$7.09/hr × 720hr = $5,105/month**

### With Intelligent Scaling:
- Small GPU (always on): $1.21/hr × 720hr = **$870/month**
- Large GPU (10% usage): $7.09/hr × 72hr = **$510/month**
- **Total: $1,380/month (73% savings!)**

---

## Deployment Steps

### Step 1: Deploy Small Endpoint (Always On)

```bash
cd "c:\desktop\PhotoGenius AI\aws\sagemaker"

# Use memory-optimized handler for small GPU
cp model/code/inference_memory_optimized.py model/code/inference.py

# Deploy small endpoint
python deploy_simple.py
# When prompted, name it: photogenius-small-dev
```

### Step 2: Deploy Large Endpoint (Auto-Scale)

```bash
# Use full enhanced handler for large GPU
cp model/code/inference_enhanced.py model/code/inference.py

# Deploy large endpoint with g5.12xlarge
# (Edit deploy_simple.py: INSTANCE_TYPE = "ml.g5.12xlarge")
python deploy_simple.py
# When prompted, name it: photogenius-large-dev
```

### Step 3: Deploy Smart Router Lambda

```bash
cd "c:\desktop\PhotoGenius AI\aws"

# Add smart_router to SAM template
sam build
sam deploy
```

### Step 4: Setup Auto-Shutdown (CloudWatch)

Create CloudWatch Event Rule:

```bash
aws events put-rule \
  --name photogenius-large-gpu-auto-shutdown \
  --schedule-expression "rate(5 minutes)" \
  --state ENABLED

# Attach Lambda target (auto-shutdown function)
aws events put-targets \
  --rule photogenius-large-gpu-auto-shutdown \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:photogenius-auto-shutdown"
```

---

## Auto-Shutdown Lambda

```python
# aws/lambda/auto_shutdown/handler.py

import boto3
import time

sagemaker = boto3.client("sagemaker")
LARGE_ENDPOINT = "photogenius-large-dev"
IDLE_TIMEOUT = 300  # 5 minutes

def lambda_handler(event, context):
    """Check if large endpoint is idle and stop it."""

    # Get endpoint status
    response = sagemaker.describe_endpoint(EndpointName=LARGE_ENDPOINT)
    status = response["EndpointStatus"]

    if status != "InService":
        return {"message": "Endpoint not running"}

    # Check last invocation time (from CloudWatch metrics)
    cloudwatch = boto3.client("cloudwatch")

    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/SageMaker",
        MetricName="ModelLatency",
        Dimensions=[
            {"Name": "EndpointName", "Value": LARGE_ENDPOINT},
            {"Name": "VariantName", "Value": "AllTraffic"},
        ],
        StartTime=time.time() - IDLE_TIMEOUT,
        EndTime=time.time(),
        Period=300,
        Statistics=["SampleCount"],
    )

    # If no requests in last 5 minutes, stop endpoint
    datapoints = response["Datapoints"]
    if not datapoints or all(d["SampleCount"] == 0 for d in datapoints):
        print(f"Stopping idle endpoint: {LARGE_ENDPOINT}")
        sagemaker.delete_endpoint(EndpointName=LARGE_ENDPOINT)
        return {"message": "Endpoint stopped (idle)"}

    return {"message": "Endpoint still active"}
```

---

## Frontend Integration

Update `.env.local`:

```env
# Use Smart Router instead of direct endpoint
AWS_LAMBDA_GENERATION_URL=https://xxx.execute-api.us-east-1.amazonaws.com/Prod/smart-generate

# Or keep existing and add smart router
AWS_LAMBDA_SMART_ROUTER_URL=https://xxx.../Prod/smart-generate
```

---

## Testing

### Test Simple Image (Small GPU):

```bash
curl -X POST https://xxx.../Prod/smart-generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a beautiful portrait of a woman",
    "quality_tier": "STANDARD"
  }'

# Response includes routing info:
# "routing": {
#   "endpoint": "photogenius-small-dev",
#   "complexity_score": 20,
#   "cost_per_hour": "$1.21"
# }
```

### Test Complex Image (Large GPU):

```bash
curl -X POST https://xxx.../Prod/smart-generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a group photo of 5 people at a wedding with detailed background",
    "quality_tier": "PREMIUM",
    "num_candidates": 4
  }'

# Response includes routing info:
# "routing": {
#   "endpoint": "photogenius-large-dev",
#   "complexity_score": 125,
#   "cost_per_hour": "$7.09"
# }

# If large GPU was stopped, you'll get:
# Status 202: "Starting large GPU (30-60 seconds)..."
# Retry after 60 seconds
```

---

## Monitoring

### Check Endpoint Status:

```bash
# Small endpoint (should always be InService)
aws sagemaker describe-endpoint --endpoint-name photogenius-small-dev

# Large endpoint (may be stopped if idle)
aws sagemaker describe-endpoint --endpoint-name photogenius-large-dev
```

### View Routing Decisions:

```bash
# Check Lambda logs
aws logs tail /aws/lambda/photogenius-smart-router --follow

# Look for:
# "Complexity Score: 85"
# "Selected Endpoint: photogenius-large-dev"
# "Reasoning: High complexity detected"
```

### Cost Monitoring:

```bash
# SageMaker costs
aws ce get-cost-and-usage \
  --time-period Start=2024-02-01,End=2024-02-28 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://sagemaker-filter.json

# sagemaker-filter.json:
{
  "Dimensions": {
    "Key": "SERVICE",
    "Values": ["Amazon SageMaker"]
  }
}
```

---

## Advantages

### 1. Cost-Effective ✅
- **73% cost savings** for typical usage
- Only pay for large GPU when needed
- Small GPU handles 80-90% of requests

### 2. Automatic ✅
- No manual intervention needed
- Smart routing based on complexity
- Auto-scales up/down

### 3. Best Quality ✅
- Complex images get full resources
- Simple images processed efficiently
- No quality compromise

### 4. Fast ✅
- Small GPU always ready (no cold start)
- Large GPU starts in 30-60s when needed
- Most requests instant

---

## Troubleshooting

### Issue: Large GPU not starting

**Check:**
```bash
aws sagemaker describe-endpoint --endpoint-name photogenius-large-dev
```

**If "Failed"**, check CloudWatch logs:
```bash
aws logs tail /aws/sagemaker/Endpoints/photogenius-large-dev
```

### Issue: Routing to wrong endpoint

**Adjust complexity threshold** in `smart_router/handler.py`:

```python
# Current threshold: 50
if complexity_score >= 50:
    return LARGE_ENDPOINT

# Increase to route less to large GPU (save cost):
if complexity_score >= 75:
    return LARGE_ENDPOINT

# Decrease to route more to large GPU (better quality):
if complexity_score >= 30:
    return LARGE_ENDPOINT
```

---

## Summary

### System Components:
1. ✅ Small Endpoint (ml.g5.2xlarge, always on, $1.21/hr)
2. ✅ Large Endpoint (ml.g5.12xlarge, auto-scale, $7.09/hr)
3. ✅ Smart Router Lambda (complexity analysis)
4. ✅ Auto-Shutdown Lambda (5 min idle timeout)

### Expected Performance:
- 90% requests → Small GPU (instant)
- 10% requests → Large GPU (auto-start if needed)
- **73% cost savings** vs always-on large GPU
- **No quality compromise**

### Cost Breakdown:
- Small GPU: $870/month (fixed)
- Large GPU: $510/month (10% usage)
- Lambda: $5/month
- **Total: ~$1,385/month**

---

**Yeh system fully automatic hai aur cost-effective bhi!** 🎉
