"""
Generation worker. Handles async image generation jobs.
Use with task queue in production for scaling.
"""


async def run_generation_job(
    user_id: str,
    identity_id: str | None,
    prompt: str,
    mode: str,
) -> list[str]:
    """Process a generation job. Returns output image URLs."""
    # TODO: call AI service, run safety checks, upload to S3, return URLs
    _ = user_id
    _ = identity_id
    _ = prompt
    _ = mode
    return []
