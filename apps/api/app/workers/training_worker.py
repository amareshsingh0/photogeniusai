"""
Training worker. Queues and processes LoRA training jobs.
Use with Celery, ARQ, or Modal.com workers in production.
"""


async def run_training_job(identity_id: str, image_urls: list[str]) -> None:
    """Process a training job. Update identity status and store LoRA path when done."""
    # TODO: enqueue to Modal.com or local GPU worker; update DB on completion
    _ = identity_id
    _ = image_urls
