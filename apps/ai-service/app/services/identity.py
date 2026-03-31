"""
Identity loading for face-consistent generation.
Loads LoRA path + face embedding by identity_id.

TODO: Wire to DB (Prisma/Supabase) and storage (S3/R2).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Identity:
    """Loaded identity for generation."""
    identity_id: str
    lora_path: Optional[str] = None
    embedding: Optional[bytes] = None


async def load_identity(identity_id: str) -> Optional[Identity]:
    """
    Load identity by ID (LoRA + face embedding).

    Args:
        identity_id: User's identity ID from Identity Vault

    Returns:
        Identity or None if not found

    TODO: Fetch from DB, resolve LoRA from S3/R2, load embedding from Pinecone.
    """
    # Stub: always return a placeholder
    return Identity(identity_id=identity_id, lora_path=None, embedding=None)
