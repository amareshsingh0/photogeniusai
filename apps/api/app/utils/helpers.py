"""Helper utilities."""

import uuid


def new_id() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())
