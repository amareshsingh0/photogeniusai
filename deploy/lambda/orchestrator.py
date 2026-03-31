"""
Lambda Orchestrator for PhotoGenius AI (Task 11).

Handles:
- Request validation
- Tier selection (STANDARD / PREMIUM / PERFECT)
- SageMaker endpoint invocation
- Progress tracking (DynamoDB)
- Result storage (S3)

API:
- POST /generate  -> create job, invoke SageMaker, return job_id (202)
- GET  /status/{job_id}  -> job status and progress
- GET  /result/{job_id}  -> presigned image URL and metadata
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime
from typing import Any, Tuple

import boto3

# AWS clients (lazy init to allow tests)
_sagemaker_runtime = None
_s3 = None
_dynamodb = None
_jobs_table = None

# Configuration from environment
JOBS_TABLE = os.environ.get("JOBS_TABLE", "photogenius-jobs")
IMAGES_BUCKET = os.environ.get("IMAGES_BUCKET", "photogenius-images")
STANDARD_ENDPOINT = os.environ.get("STANDARD_ENDPOINT", "photogenius-standard")
PREMIUM_ENDPOINT = os.environ.get("PREMIUM_ENDPOINT", "photogenius-two-pass")
PERFECT_ENDPOINT = os.environ.get("PERFECT_ENDPOINT", "photogenius-perfect")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _get_jobs_table():
    global _jobs_table
    if _jobs_table is None:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        _jobs_table = dynamodb.Table(JOBS_TABLE)
    return _jobs_table


def _get_sagemaker():
    global _sagemaker_runtime
    if _sagemaker_runtime is None:
        _sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=REGION)
    return _sagemaker_runtime


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=REGION)
    return _s3


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda handler.

    Supports:
    - POST /generate - Create new generation job
    - GET /status/{job_id} - Check job status
    - GET /result/{job_id} - Get final result
    - OPTIONS - CORS preflight
    """
    try:
        http_method = _get_http_method(event)
        path = _get_path(event)
        path_params = event.get("pathParameters") or {}

        # CORS preflight
        if http_method == "OPTIONS":
            return {
                "statusCode": 204,
                "headers": cors_headers(),
                "body": "",
            }

        # Route
        if http_method == "POST" and (
            "/generate" in path or path.strip("/") == "generate"
        ):
            return handle_generate(event)
        if http_method == "GET" and "/status/" in path:
            job_id = (
                path_params.get("job_id") or path.split("/status/")[-1].split("/")[0]
            )
            return handle_status(event, job_id)
        if http_method == "GET" and "/result/" in path:
            job_id = (
                path_params.get("job_id") or path.split("/result/")[-1].split("/")[0]
            )
            return handle_result(event, job_id)

        return error_response(404, "Not found")
    except Exception as e:
        print(f"Lambda error: {e}")
        return error_response(500, f"Internal error: {str(e)}")


def _get_http_method(event: dict) -> str:
    req_ctx = event.get("requestContext") or {}
    http = req_ctx.get("http") or {}
    return event.get("httpMethod") or http.get("method") or ""


def _get_path(event: dict) -> str:
    return event.get("path") or event.get("rawPath") or ""


def handle_generate(event: dict) -> dict:
    """
    Handle POST /generate.

    Body: { "prompt": "...", "tier": "auto"|"standard"|"premium"|"perfect",
            "environment": "rainy"|"fantasy"|"normal", "seed": 42 }
    Returns: 202 with job_id, status, tier, estimated_time_seconds, check_status_url.
    """
    body_raw = event.get("body") or "{}"
    try:
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
    except json.JSONDecodeError:
        return error_response(400, "Invalid JSON body")

    prompt = body.get("prompt")
    if not prompt or not str(prompt).strip():
        return error_response(400, "Missing required field: prompt")

    # tier: "auto"|"standard"|"premium"|"perfect"; also accept quality_tier (FAST|STANDARD|PREMIUM|PERFECT)
    requested_tier = (
        (body.get("tier") or body.get("quality_tier") or "auto").strip().lower()
    )
    if requested_tier == "fast":
        requested_tier = "standard"
    elif requested_tier not in ("standard", "premium", "perfect"):
        requested_tier = "auto"
    environment = (body.get("environment") or "normal").strip().lower()
    seed = body.get("seed")

    tier, reason = select_tier(prompt, requested_tier)
    job_id = generate_job_id(prompt)

    jobs_table = _get_jobs_table()
    job_record = {
        "job_id": job_id,
        "prompt": prompt,
        "tier": tier,
        "tier_selection_reason": reason,
        "environment": environment,
        "seed": seed,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    jobs_table.put_item(Item=job_record)

    print(f"Created job: {job_id} tier: {tier}")

    # Invoke SageMaker synchronously (Lambda waits for result)
    invoke_sagemaker_sync(job_id, prompt, tier, environment, seed)

    # Return 200 with result so web/API get image in one call (no polling required)
    result_body = _build_result_body(job_id, include_base64=True)
    if result_body:
        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps(result_body),
        }
    # Job failed or not found
    jobs_table = _get_jobs_table()
    resp = jobs_table.get_item(Key={"job_id": job_id})
    job = resp.get("Item", {})
    return {
        "statusCode": 500 if job.get("status") == "failed" else 202,
        "headers": cors_headers(),
        "body": json.dumps(
            {
                "job_id": job_id,
                "status": job.get("status", "unknown"),
                "error": job.get("error_message", "Generation failed"),
                "tier": tier,
                "check_status_url": f"/status/{job_id}",
            }
        ),
    }


def _build_result_body(job_id: str, include_base64: bool = True) -> dict | None:
    """Build response body for completed job (image_url, metadata, images array). Returns None if not completed."""
    jobs_table = _get_jobs_table()
    response = jobs_table.get_item(Key={"job_id": job_id})
    if "Item" not in response:
        return None
    job = response["Item"]
    if job.get("status") != "completed":
        return None
    s3_key = job.get("image_s3_key")
    if not s3_key:
        return None
    s3_client = _get_s3()
    image_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": IMAGES_BUCKET, "Key": s3_key},
        ExpiresIn=3600,
    )
    image_base64 = None
    if include_base64:
        obj = s3_client.get_object(Bucket=IMAGES_BUCKET, Key=s3_key)
        image_base64 = base64.b64encode(obj["Body"].read()).decode("utf-8")
    metadata = {
        "final_score": job.get("final_score", 0.0),
        "iterations": job.get("total_iterations", 0),
        "tier": job["tier"],
        "prompt": job.get("prompt", ""),
    }
    img_entry = {"url": image_url}
    if image_base64:
        img_entry["base64"] = image_base64
    return {
        "job_id": job_id,
        "status": "completed",
        "image_url": image_url,
        "image_base64": image_base64,
        "metadata": metadata,
        "images": [img_entry],
    }


def handle_status(event: dict, job_id: str) -> dict:
    """
    Handle GET /status/{job_id}.

    Returns: job_id, status, tier, prompt, elapsed_time, optional progress/result_url/error.
    """
    if not job_id:
        return error_response(400, "Missing job_id")

    jobs_table = _get_jobs_table()
    response = jobs_table.get_item(Key={"job_id": job_id})

    if "Item" not in response:
        return error_response(404, f"Job not found: {job_id}")

    job = response["Item"]
    created_str = job["created_at"].replace("Z", "").split("+")[0]
    created_at = datetime.fromisoformat(created_str)
    elapsed = (datetime.utcnow() - created_at).total_seconds()

    status_response = {
        "job_id": job_id,
        "status": job["status"],
        "tier": job["tier"],
        "prompt": job["prompt"],
        "elapsed_time": int(elapsed),
    }
    if "current_iteration" in job:
        status_response["current_iteration"] = job["current_iteration"]
        max_it = job.get("max_iterations", 3)
        status_response["max_iterations"] = max_it
        status_response["progress"] = job["current_iteration"] / max_it if max_it else 0
    if job["status"] == "completed":
        status_response["result_url"] = f"/result/{job_id}"
        status_response["image_url"] = job.get("image_s3_url")
    if job["status"] == "failed":
        status_response["error"] = job.get("error_message", "Unknown error")

    return {
        "statusCode": 200,
        "headers": cors_headers(),
        "body": json.dumps(status_response),
    }


def handle_result(event: dict, job_id: str) -> dict:
    """
    Handle GET /result/{job_id}.

    Returns: job_id, image_url (presigned), metadata; optional image_base64 if ?include_base64=true.
    """
    if not job_id:
        return error_response(400, "Missing job_id")

    jobs_table = _get_jobs_table()
    response = jobs_table.get_item(Key={"job_id": job_id})

    if "Item" not in response:
        return error_response(404, f"Job not found: {job_id}")

    job = response["Item"]
    if job["status"] != "completed":
        return error_response(400, f"Job not completed. Status: {job['status']}")

    s3_key = job.get("image_s3_key")
    if not s3_key:
        return error_response(500, "Image not found in storage")

    s3_client = _get_s3()
    image_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": IMAGES_BUCKET, "Key": s3_key},
        ExpiresIn=3600,
    )

    qs = event.get("queryStringParameters") or {}
    include_base64 = qs.get("include_base64") == "true"

    result_response = {
        "job_id": job_id,
        "image_url": image_url,
        "metadata": {
            "final_score": job.get("final_score", 0.0),
            "iterations": job.get("total_iterations", 0),
            "tier": job["tier"],
            "prompt": job["prompt"],
        },
    }
    if include_base64:
        obj = s3_client.get_object(Bucket=IMAGES_BUCKET, Key=s3_key)
        img_data = obj["Body"].read()
        result_response["image_base64"] = base64.b64encode(img_data).decode("utf-8")

    return {
        "statusCode": 200,
        "headers": cors_headers(),
        "body": json.dumps(result_response),
    }


def select_tier(prompt: str, requested_tier: str) -> Tuple[str, str]:
    """
    Select optimal tier: STANDARD / PREMIUM / PERFECT.

    - User can override with explicit tier.
    - Auto: simple -> STANDARD, medium -> PREMIUM, complex -> PERFECT.
    """
    if requested_tier != "auto":
        tier = requested_tier.upper()
        if tier in ("STANDARD", "PREMIUM", "PERFECT"):
            return tier, f"User requested {tier}"
        return "STANDARD", "Invalid tier requested, defaulting to STANDARD"

    prompt_lower = prompt.lower()
    person_count = 0
    for pattern in [
        r"(\d+)\s+(people|children|kids|person|adults)",
        r"(couple|pair)",
        r"family\s+of\s+(\d+)",
    ]:
        for m in re.finditer(pattern, prompt_lower):
            g = m.groups()
            for x in g:
                if isinstance(x, str) and x.isdigit():
                    person_count += int(x)
                elif x in ("couple", "pair"):
                    person_count += 2

    has_weather = any(w in prompt_lower for w in ["rain", "snow", "storm", "fog"])
    has_fantasy = any(
        w in prompt_lower for w in ["dragon", "magic", "fantasy", "ethereal", "crystal"]
    )
    has_complex = any(
        w in prompt_lower for w in ["crowd", "city", "detailed", "intricate"]
    )

    complexity_score = 0
    reasons = []
    if person_count >= 4:
        complexity_score += 2
        reasons.append(f"{person_count} people")
    elif person_count >= 2:
        complexity_score += 1
        reasons.append(f"{person_count} people")
    if has_weather:
        complexity_score += 1
        reasons.append("weather effects")
    if has_fantasy:
        complexity_score += 2
        reasons.append("fantasy elements")
    if has_complex:
        complexity_score += 1
        reasons.append("complex scene")

    if complexity_score >= 3:
        return "PERFECT", f"Complex prompt ({', '.join(reasons)})"
    if complexity_score >= 1:
        return "PREMIUM", f"Medium complexity ({', '.join(reasons)})"
    return "STANDARD", "Simple prompt"


def invoke_sagemaker_sync(
    job_id: str,
    prompt: str,
    tier: str,
    environment: str,
    seed: Any,
) -> None:
    """Invoke SageMaker endpoint and update job with result or failure."""
    endpoint_map = {
        "STANDARD": STANDARD_ENDPOINT,
        "PREMIUM": PREMIUM_ENDPOINT,
        "PERFECT": PERFECT_ENDPOINT,
    }
    endpoint_name = endpoint_map.get(tier, STANDARD_ENDPOINT)
    payload = {"prompt": prompt, "environment": environment, "seed": seed}
    jobs_table = _get_jobs_table()
    sm = _get_sagemaker()
    s3_client = _get_s3()

    try:
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :status, updated_at = :updated",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "processing",
                ":updated": datetime.utcnow().isoformat() + "Z",
            },
        )

        try:
            response = sm.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Body=json.dumps(payload),
            )
        except Exception as e:
            err_str = str(e).lower()
            if tier == "PERFECT" and (
                "not found" in err_str
                or "resourcenotfound" in err_str
                or "does not exist" in err_str
            ):
                endpoint_name = PREMIUM_ENDPOINT
                response = sm.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType="application/json",
                    Body=json.dumps(payload),
                )
            else:
                raise
        result = json.loads(response["Body"].read())

        img_b64 = result.get("image")
        if not img_b64:
            raise ValueError("No image in SageMaker response")

        s3_key = f"images/{job_id}.png"
        img_data = base64.b64decode(img_b64)
        s3_client.put_object(
            Bucket=IMAGES_BUCKET,
            Key=s3_key,
            Body=img_data,
            ContentType="image/png",
        )

        meta = result.get("metadata") or {}
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :status, image_s3_key = :key, "
            "final_score = :score, total_iterations = :iters, "
            "updated_at = :updated, completed_at = :completed",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "completed",
                ":key": s3_key,
                ":score": meta.get("final_score", 0.0),
                ":iters": meta.get("total_iterations", 0),
                ":updated": datetime.utcnow().isoformat() + "Z",
                ":completed": datetime.utcnow().isoformat() + "Z",
            },
        )
        print(f"Job {job_id} completed")
    except Exception as e:
        print(f"SageMaker error: {e}")
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :status, error_message = :err, updated_at = :updated",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "failed",
                ":err": str(e),
                ":updated": datetime.utcnow().isoformat() + "Z",
            },
        )


def generate_job_id(prompt: str) -> str:
    """Generate unique job ID."""
    raw = f"{prompt}{datetime.utcnow().isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def estimate_generation_time(tier: str) -> int:
    """Estimated generation time in seconds."""
    return {"STANDARD": 30, "PREMIUM": 45, "PERFECT": 90}.get(tier, 45)


def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json",
    }


def error_response(status_code: int, message: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": cors_headers(),
        "body": json.dumps(
            {
                "error": message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ),
    }
