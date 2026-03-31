"""
Prompt sanitization for Layer 1 safety.

Checks:
- Harmful keywords (violence, illegal content)
- Celebrity + sexual context
- Minor-related content
- Injection attacks
"""

import re
from dataclasses import dataclass
from typing import Optional


# Blocked keyword categories (expand in production)
BLOCKED_KEYWORDS = {
    "violence": ["murder", "kill", "blood", "gore"],
    "illegal": ["drugs", "weapons", "terrorism"],
    "csam": ["child", "minor", "underage", "young"],  # Combined with sexual context
}

# Celebrity names to protect (expand in production)
CELEBRITY_NAMES = [
    "taylor swift", "beyonce", "emma watson", "scarlett johansson",
    "jennifer lawrence", "kim kardashian", "selena gomez",
]

# Sexual context keywords
SEXUAL_KEYWORDS = ["nude", "naked", "sexual", "erotic", "nsfw", "porn"]


@dataclass
class SanitizeResult:
    """Result of prompt sanitization."""
    allowed: bool
    reason: Optional[str]
    modified_prompt: str
    blocked_category: Optional[str]
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "modified_prompt": self.modified_prompt,
            "blocked_category": self.blocked_category,
        }


def sanitize(prompt: str) -> SanitizeResult:
    """
    Sanitize a user prompt for safety.
    
    Args:
        prompt: User's text prompt
    
    Returns:
        SanitizeResult with allowed status and any modifications
    """
    prompt_lower = prompt.lower()
    
    # Check for injection attacks
    if any(char in prompt for char in ["<", ">", "{", "}", "\\x"]):
        return SanitizeResult(
            allowed=False,
            reason="Invalid characters detected",
            modified_prompt=prompt,
            blocked_category="injection",
        )
    
    # Check for blocked keywords
    for category, keywords in BLOCKED_KEYWORDS.items():
        for keyword in keywords:
            if keyword in prompt_lower:
                # Special handling for CSAM: only block if combined with sexual context
                if category == "csam":
                    has_sexual = any(s in prompt_lower for s in SEXUAL_KEYWORDS)
                    if has_sexual:
                        return SanitizeResult(
                            allowed=False,
                            reason="Content involving minors is strictly prohibited",
                            modified_prompt=prompt,
                            blocked_category="csam",
                        )
                else:
                    return SanitizeResult(
                        allowed=False,
                        reason=f"Content related to {category} is not allowed",
                        modified_prompt=prompt,
                        blocked_category=category,
                    )
    
    # Check for celebrity + sexual context
    for celeb in CELEBRITY_NAMES:
        if celeb in prompt_lower:
            has_sexual = any(s in prompt_lower for s in SEXUAL_KEYWORDS)
            if has_sexual:
                return SanitizeResult(
                    allowed=False,
                    reason="Sexual content of real public figures is not allowed",
                    modified_prompt=prompt,
                    blocked_category="celebrity_protection",
                )
    
    # Passed all checks
    return SanitizeResult(
        allowed=True,
        reason=None,
        modified_prompt=prompt,
        blocked_category=None,
    )
