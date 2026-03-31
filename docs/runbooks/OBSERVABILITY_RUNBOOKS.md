# Observability Runbooks

Full-stack tracing uses **correlation IDs** (`X-Request-ID`) and **structured logs** so you can debug issues across Frontend → API → Lambda → SageMaker → S3.

---

## 1. How to debug a failed generation (using correlation ID)

**When to use:** A user reports "my generation failed" or you see a 502/500 on generate.

### Step 1: Get the correlation ID

- **From the user:** Ask them to check the response headers of the failed request. In browser DevTools → Network → select the failed `/api/generate` or `/api/generations` request → Headers → look for **X-Request-ID** (or `x-request-id`).
- **From the app:** If the frontend stores the last request ID (e.g. from response headers), the support/feedback UI can show "Request ID: xxx" for the user to copy.
- **From the database:** If the generation was saved with a `correlationId`, you can look it up by generation ID or user:

  ```sql
  SELECT id, "correlationId", "originalPrompt", "createdAt" FROM "Generation"
  WHERE "correlationId" = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
  -- or by time range / user
  ORDER BY "createdAt" DESC LIMIT 20;
  ```

### Step 2: Search logs by correlation ID

- **Next.js / Node (Vercel or CloudWatch):**  
  Logs are JSON: `{"timestamp":"...","level":"...","service":"web","correlation_id":"...","message":"..."}`.  
  Search for: `correlation_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"` (or the value you have).

- **AWS Lambda (CloudWatch Logs):**  
  Open the log group for the generation Lambda (e.g. `/aws/lambda/PhotoGenius-GenerationFunction-xxx`).  
  In **Logs Insights**, run:

  ```kql
  fields @timestamp, @message
  | filter @message like /xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/
  | sort @timestamp asc
  ```

  (Replace with the actual correlation ID.)

- **SageMaker endpoint:**  
  If the Lambda passes `correlation_id` in the payload, the model/serving code can log it. Search the SageMaker endpoint’s CloudWatch log group for the same ID.

### Step 3: Interpret the flow

- **Web:** Look for `"message":"Safety check"`, `"Starting generation"`, `"Generation failed"`, `"DB save failed"`, etc. The last error before the user saw a failure is usually the cause.
- **Lambda:** Look for `"Generating images"`, `"S3 upload failed"`, `"Generation failed"`. If you see `S3 upload failed` with the same correlation_id, the failure is at S3 (permissions, bucket, or key).
- **SageMaker:** Look for inference start/end and any exception lines containing the correlation_id.

### Step 4: Fix and respond

- Fix the underlying error (safety block, timeout, S3, SageMaker, etc.).
- If the failure is intermittent, use the same correlation_id to correlate with metrics (e.g. throttling, cold start) in CloudWatch.

---

## 2. How to find slow requests

**When to use:** You want to identify the slowest generation or API calls (e.g. p99, or "top 10 slow").

### Option A: CloudWatch Logs Insights (structured logs)

If your logs include duration/latency in the JSON (e.g. `duration_ms`, `latency`):

1. Open **CloudWatch → Log groups** (e.g. `/aws/lambda/PhotoGenius-GenerationFunction-xxx` or your API/Next.js log group).
2. **Logs Insights**, select the log group(s), then run a query that parses and sorts by duration. Example (adjust field names to match your log schema):

  ```kql
  fields @timestamp, @message
  | parse @message /"duration_ms":(?<duration_ms>\d+)/
  | filter ispresent(duration_ms)
  | sort duration_ms desc
  | limit 20
  ```

  Or by correlation_id to get one request’s full flow:

  ```kql
  fields @timestamp, @message
  | filter @message like /correlation_id/
  | parse @message /"correlation_id":"(?<correlation_id>[^"]+)"/
  | parse @message /"duration_ms":(?<duration_ms>\d+)/
  | stats max(duration_ms) as max_ms by correlation_id
  | sort max_ms desc
  | limit 10
  ```

### Option B: CloudWatch Metrics

If you emit a **duration metric** (e.g. from Lambda or API Gateway):

1. **CloudWatch → Dashboards** (or create one).
2. Add a widget: metric for **Duration** (or your custom metric), statistic **p99** or **Average**, grouped by resource (e.g. Lambda function name).
3. Use **Metrics → All metrics** and filter by your namespace (e.g. `PhotoGenius`) to see latency over time.

### Option C: X-Ray (if enabled)

1. **X-Ray → Traces**.
2. Filter by **Response time** (e.g. > 5 s).
3. Open a trace to see the segment breakdown (API Gateway → Lambda → SageMaker, etc.) and identify the slow stage.

### Top 10 slow requests (summary)

- Use **Logs Insights** with a query that extracts `duration_ms` (or equivalent) and `correlation_id`, then `stats max(duration_ms) by correlation_id | sort max_ms desc | limit 10`.
- Or use **X-Ray** and sort traces by response time, then read the correlation ID from the trace metadata if you’ve added it as an annotation.

---

## 3. How to trace S3 upload failures

**When to use:** Generations succeed in SageMaker but images don’t appear (or user gets a fallback data URL). Often caused by S3 upload failures in Lambda.

### Step 1: Identify the request

Get the **correlation ID** for the failing request (see runbook 1). Optionally get the **job_id** or **generation id** from the UI or DB.

### Step 2: Lambda logs (S3 upload errors)

Lambda logs structured JSON with `"message":"S3 upload failed"` and `correlation_id`, `s3_key`, `error`.

1. Open **CloudWatch → Log groups** for the **generation Lambda** (e.g. `/aws/lambda/PhotoGenius-GenerationFunction-xxx`).
2. **Logs Insights**:

  ```kql
  fields @timestamp, @message
  | filter @message like /S3 upload failed/
  | filter @message like /<correlation_id>/
  ```

  Replace `<correlation_id>` with the actual value. You should see the `s3_key` and `error` in the same log line.

### Step 3: Common causes and checks

| Symptom / error | What to check |
|-----------------|----------------|
| `AccessDenied`, `403` | IAM role for Lambda: needs `s3:PutObject` (and optionally `s3:GetObject`) on the bucket/prefix. Bucket policy must allow the role. |
| `NoSuchBucket` | Bucket name (e.g. `S3_BUCKET` env var or config) is correct and in the same region as the Lambda. |
| `InvalidBucketName` | Bucket name format (lowercase, no underscore for bucket name). |
| Timeout | Large payload or slow network: increase Lambda timeout; consider streaming or smaller images. |
| Key/prefix | Ensure `generations/{user_id}/{job_id}_{i}.png` is allowed by any bucket lifecycle or encryption (KMS) config. |

### Step 4: Verify S3 from Lambda

- In the same Lambda code path, after a successful upload, the log includes the S3 URL. Search for the same `correlation_id` and confirm a line with the returned URL.
- In **S3 console**, open the bucket and prefix (e.g. `generations/<user_id>/`) and confirm the object exists for the given `job_id` and index.

### Step 5: End-to-end with correlation ID

To see the full path for one request:

1. **Lambda logs:** Filter by `correlation_id` → see "Generating images", "Generation completed", or "S3 upload failed".
2. **SageMaker logs:** If the endpoint logs the same `correlation_id`, you can confirm inference finished before the Lambda tried to upload.
3. **Database:** If the generation row was written with `correlationId`, you can confirm whether the failure happened before or after DB write (e.g. after S3 upload when saving the URL).

---

## Quick reference

| What you have | Where to look |
|---------------|----------------|
| Correlation ID (X-Request-ID) | Response headers of the request; DB `Generation.correlationId`; structured logs. |
| Structured log format | `{ "timestamp", "level", "service", "correlation_id", "message", ...metadata }` |
| Web logs | Next.js logs (Vercel/CloudWatch); `service: "web"`. |
| Lambda logs | CloudWatch log group for the generation Lambda; `service: "lambda-generation"`. |
| SageMaker logs | CloudWatch log group for the SageMaker endpoint (if it logs correlation_id). |
| S3 failures | Lambda logs: `"message":"S3 upload failed"` + `correlation_id`, `s3_key`, `error`. |
