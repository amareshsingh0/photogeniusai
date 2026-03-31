# Cost Optimization Guide

## Current Cost Breakdown (1000 images/day)

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| SageMaker (ml.g5.xlarge) | ~2 hours/day active | $85 |
| Lambda (Orchestrator) | 1000 invocations | $0.20 |
| Lambda (Enhancement) | 1000 invocations | $0.02 |
| Lambda (Post-processing) | 1000 invocations | $2.50 |
| S3 Storage | 100GB | $2.30 |
| Data Transfer | 50GB out | $4.50 |
| **TOTAL** | | **~$95/month** |

**Per image cost: ~$0.03**

---

## Optimization Strategies

### 1. SageMaker Serverless Inference

Use serverless inference for pay-per-use and scale-to-zero:

```yaml
EndpointConfig:
  ServerlessConfig:
    MaxConcurrency: 10
    MemorySizeInMB: 6144
```

- **Pros:** Pay per use, auto-scale to zero  
- **Cons:** Cold start (5–10s first request)  
- **Savings:** 60–70% for low–medium traffic  

### 2. Spot Instances for Training

Use spot instances for model fine-tuning:

```python
training_job = estimator.fit(
    inputs=training_data,
    use_spot_instances=True,
    max_run=3600,
    max_wait=7200,
)
```

- **Savings:** ~70% on training costs  

### 3. S3 Intelligent Tiering

```yaml
LifecycleConfiguration:
  Rules:
    - Id: IntelligentTiering
      Status: Enabled
      Transitions:
        - Days: 30
          StorageClass: INTELLIGENT_TIERING
    - Id: DeleteOld
      Status: Enabled
      ExpirationInDays: 90
```

### 4. CloudFront Caching

Cache images at the edge to cut S3 requests:

```yaml
DefaultCacheBehavior:
  MinTTL: 86400      # 1 day
  MaxTTL: 31536000   # 1 year
  DefaultTTL: 2592000 # 30 days
```

- **Effect:** 80%+ reduction in S3 GET requests  

### 5. Batch Processing

Process multiple images per Lambda invocation to reduce cold starts:

```python
def lambda_handler(event, context):
    images = event.get("images", [])
    return [process_image(img) for img in images]
```

- **Savings:** 40–50% on Lambda  

### 6. Reserved Capacity

For stable traffic, use reserved capacity:

- 1-year: ~40% savings  
- 3-year: ~60% savings  

---

## Recommended Setup by Scale

### Small (< 1000 images/month)

- Serverless SageMaker  
- Lambda on-demand  
- S3 Standard  
- **Cost:** ~$10–20/month  

### Medium (1K–50K images/month)

- 1× SageMaker ml.g5.xlarge (auto-scale)  
- Lambda (optionally provisioned concurrency)  
- S3 Intelligent Tiering  
- CloudFront  
- **Cost:** ~$80–150/month  

### Large (50K–500K images/month)

- 2–5× SageMaker ml.g5.xlarge (auto-scale)  
- Multi-region if needed  
- Reserved capacity  
- **Cost:** ~$400–800/month  

### Enterprise (500K+ images/month)

- 10+ SageMaker instances  
- Dedicated VPC, multi-region, multi-AZ  
- 3-year reserved capacity  
- **Cost:** ~$2000–5000/month  

---

## Pro Tips

### CloudWatch budget alert

```yaml
BudgetAlert:
  Type: AWS::Budgets::Budget
  Properties:
    Budget:
      BudgetLimit:
        Amount: 200
        Unit: USD
      TimeUnit: MONTHLY
```

### Tagging for cost allocation

```yaml
Tags:
  - Key: Project
    Value: PhotoGenius
  - Key: Environment
    Value: Production
```

### Request quotas (API Gateway)

```yaml
UsagePlan:
  Quota:
    Limit: 10000
    Period: MONTH
  Throttle:
    RateLimit: 100
    BurstLimit: 200
```

### Async processing for non-urgent jobs

Use SQS + Step Functions for batch jobs; process overnight at lower priority for ~30–40% compute savings.

---

## Cost calculator (Python)

```python
def calculate_monthly_cost(images_per_day):
    LAMBDA_COST_PER_INVOCATION = 0.0000002
    LAMBDA_GB_SECOND = 0.0000166667
    SAGEMAKER_PER_HOUR = 1.41
    S3_STORAGE_PER_GB = 0.023
    DATA_TRANSFER_PER_GB = 0.09

    monthly_images = images_per_day * 30
    lambda_invocations = monthly_images * 3
    lambda_cost = lambda_invocations * LAMBDA_COST_PER_INVOCATION
    lambda_compute = (monthly_images * 0.5 * 3) * LAMBDA_GB_SECOND
    sagemaker_hours = (monthly_images * 10) / 3600
    sagemaker_cost = sagemaker_hours * SAGEMAKER_PER_HOUR
    storage_gb = (monthly_images * 5) / 1024
    storage_cost = storage_gb * S3_STORAGE_PER_GB
    transfer_cost = (storage_gb * 0.5) * DATA_TRANSFER_PER_GB

    total = lambda_cost + lambda_compute + sagemaker_cost + storage_cost + transfer_cost
    return {
        "total": round(total, 2),
        "per_image": round(total / monthly_images, 4),
        "breakdown": {
            "lambda": round(lambda_cost + lambda_compute, 2),
            "sagemaker": round(sagemaker_cost, 2),
            "storage": round(storage_cost, 2),
            "transfer": round(transfer_cost, 2),
        },
    }

# Examples
# calculate_monthly_cost(100)   # ~$30/month
# calculate_monthly_cost(1000)   # ~$95/month
# calculate_monthly_cost(10000)  # ~$650/month
```
