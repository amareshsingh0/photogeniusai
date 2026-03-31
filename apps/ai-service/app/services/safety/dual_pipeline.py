"""
Dual-layer safety pipeline.

Layer 1 (Pre-generation): Prompt sanitization
- Block harmful keywords
- Detect celebrity names + sexual context
- Age-related content detection

Layer 2 (Post-generation): Image classification
- NSFW classification
- Age estimation (block if minor detected)
- Content provenance (C2PA metadata)
"""

from dataclasses import dataclass
from typing import Optional
from app.services.safety.prompt_sanitizer import sanitize, SanitizeResult  # type: ignore[reportAttributeAccessIssue]
from app.services.safety.nsfw_classifier import classify, NSFWResult  # type: ignore[reportAttributeAccessIssue]
from app.services.safety.age_estimator import estimate, AgeResult  # type: ignore[reportAttributeAccessIssue]


@dataclass
class SafetyResult:
    """Result of dual-layer safety check."""
    allowed: bool
    blocked_reason: Optional[str]
    pre_check: SanitizeResult
    post_check_nsfw: Optional[NSFWResult]
    post_check_age: Optional[AgeResult]
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "blocked_reason": self.blocked_reason,
            "pre_check": {
                "allowed": self.pre_check.allowed,
                "reason": self.pre_check.reason,
                "modified_prompt": self.pre_check.modified_prompt,
            },
            "post_check_nsfw": self.post_check_nsfw.to_dict() if self.post_check_nsfw else None,
            "post_check_age": self.post_check_age.to_dict() if self.post_check_age else None,
        }


def run_pre_check(prompt: str) -> tuple[bool, SanitizeResult]:
    """
    Run Layer 1 (pre-generation) safety check.
    
    Args:
        prompt: User's text prompt
    
    Returns:
        (allowed, SanitizeResult)
    """
    result = sanitize(prompt)
    return result.allowed, result


def run_post_check(image_url: str) -> tuple[bool, Optional[NSFWResult], Optional[AgeResult]]:
    """
    Run Layer 2 (post-generation) safety check.
    
    Args:
        image_url: URL to generated image
    
    Returns:
        (allowed, NSFWResult, AgeResult)
    """
    nsfw_result = classify(image_url)
    age_result = estimate(image_url)
    
    # Block if NSFW detected or minor detected
    allowed = nsfw_result.is_safe and age_result.is_adult
    
    return allowed, nsfw_result, age_result


def run_pipeline(prompt: str, image_url: Optional[str] = None) -> SafetyResult:
    """
    Run full dual-layer safety pipeline.
    
    Args:
        prompt: User's text prompt
        image_url: URL to generated image (for post-check)
    
    Returns:
        SafetyResult with all checks
    """
    # Layer 1: Pre-generation check
    pre_allowed, pre_result = run_pre_check(prompt)
    
    if not pre_allowed:
        return SafetyResult(
            allowed=False,
            blocked_reason=pre_result.reason,
            pre_check=pre_result,
            post_check_nsfw=None,
            post_check_age=None,
        )
    
    # Layer 2: Post-generation check (if image provided)
    if image_url:
        post_allowed, nsfw_result, age_result = run_post_check(image_url)
        
        if not post_allowed:
            reason = "NSFW content detected" if (nsfw_result and not nsfw_result.is_safe) else "Minor detected in image"
            return SafetyResult(
                allowed=False,
                blocked_reason=reason,
                pre_check=pre_result,
                post_check_nsfw=nsfw_result,
                post_check_age=age_result,
            )
        
        return SafetyResult(
            allowed=True,
            blocked_reason=None,
            pre_check=pre_result,
            post_check_nsfw=nsfw_result,
            post_check_age=age_result,
        )
    
    # No image provided, only pre-check
    return SafetyResult(
        allowed=True,
        blocked_reason=None,
        pre_check=pre_result,
        post_check_nsfw=None,
        post_check_age=None,
    )


# -----------------------------------------------------------------------------
# API for /api/v1/generate (pre_generation_check, post_generation_check)
# -----------------------------------------------------------------------------


async def pre_generation_check(
    user_id: str,
    prompt: str,
    mode: str,
) -> dict:
    """
    Pre-generation safety check for /api/v1/generate.

    Returns:
        {"allowed": bool, "violations": list[str]}
    """
    allowed, pre_result = run_pre_check(prompt)
    violations: list[str] = []
    if not allowed and pre_result.reason:
        violations.append(pre_result.reason)
    return {"allowed": allowed, "violations": violations}


async def post_generation_check(
    generated_image_path: str,
    mode: str,
) -> dict:
    """
    Post-generation safety check for /api/v1/generate.
    Treats generated_image_path as URL (path or full URL).

    Returns:
        {"safe": bool}
    """
    post_allowed, _, _ = run_post_check(generated_image_path)
    return {"safe": post_allowed}
