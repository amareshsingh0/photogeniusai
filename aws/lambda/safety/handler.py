"""
PhotoGenius AI - Safety Check Lambda
Checks prompts for safety violations before generation.
"""

import json
import re
import os

# Blocked keywords with context
BLOCKED_KEYWORDS = {
    "always_block": [
        "child", "minor", "underage", "young", "teen", "kid",
        "csam", "cp", "pedo",
    ],
    "context_sensitive": {
        "nude": ["lipstick", "color", "palette", "shade", "makeup"],  # OK in makeup context
        "naked": ["eye", "truth", "emotion"],  # OK in artistic context
        "explicit": ["consent", "permission", "instruction"],  # OK in consent context
    }
}

# Mode-specific thresholds
MODE_THRESHOLDS = {
    "REALISM": {"strictness": 0.6},
    "CREATIVE": {"strictness": 0.7},
    "ROMANTIC": {"strictness": 0.3},  # Strictest
    "FASHION": {"strictness": 0.5},
    "CINEMATIC": {"strictness": 0.6},
}


def check_safety(prompt: str, mode: str = "REALISM") -> dict:
    """
    Check prompt for safety violations.

    Returns:
        dict: {"allowed": bool, "violations": list, "confidence": float}
    """
    prompt_lower = prompt.lower()
    violations = []

    # Check always-blocked keywords
    for keyword in BLOCKED_KEYWORDS["always_block"]:
        if keyword in prompt_lower:
            violations.append(f"Blocked content: {keyword}")

    # Check context-sensitive keywords
    for keyword, safe_contexts in BLOCKED_KEYWORDS["context_sensitive"].items():
        if keyword in prompt_lower:
            # Check if any safe context word is present
            has_safe_context = any(ctx in prompt_lower for ctx in safe_contexts)
            if not has_safe_context:
                violations.append(f"Potentially unsafe: {keyword}")

    # Mode-specific checks
    if mode == "ROMANTIC":
        romantic_blocked = ["lingerie", "underwear", "bikini", "swimsuit"]
        for keyword in romantic_blocked:
            if keyword in prompt_lower:
                violations.append(f"Not allowed in ROMANTIC mode: {keyword}")

    allowed = len(violations) == 0
    confidence = 1.0 if allowed else 0.0

    return {
        "allowed": allowed,
        "violations": violations,
        "confidence": confidence,
        "mode": mode,
    }


def lambda_handler(event, context):
    """
    AWS Lambda handler for safety checks.

    Expected input:
        {"prompt": "...", "mode": "REALISM"}

    Returns:
        {"allowed": bool, "violations": list}
    """
    try:
        # Parse input
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)

        prompt = body.get("prompt", "")
        mode = body.get("mode", "REALISM").upper()

        if not prompt:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": "prompt is required"})
            }

        # Check safety
        result = check_safety(prompt, mode)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": str(e)})
        }


# For local testing
if __name__ == "__main__":
    test_event = {
        "body": json.dumps({
            "prompt": "professional headshot with soft lighting",
            "mode": "REALISM"
        })
    }
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
