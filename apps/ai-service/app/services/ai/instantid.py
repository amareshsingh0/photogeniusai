"""
InstantID pipeline for face-consistent generation.

Provides ip_adapter_image / controlnet-style face control.
TODO: Integrate real InstantID (IP-Adapter + ControlNet) when models available.
"""

from typing import Any, Optional

# Type alias for identity embedding (numpy array or bytes)
IdentityEmbedding = Any


class InstantIDPipeline:
    """
    Placeholder for InstantID face-consistency pipeline.
    Swap for real implementation when IP-Adapter + ControlNet are wired.
    """

    def __init__(self) -> None:
        self._ready = False

    def load(self) -> None:
        """Load InstantID models. No-op in stub."""
        self._ready = True

    def prepare(
        self,
        identity_embedding: Optional[IdentityEmbedding] = None,
        controlnet_conditioning_scale: float = 0.9,
    ) -> Optional[IdentityEmbedding]:
        """
        Prepare face embedding for generation.
        Returns embedding for use as ip_adapter_image.
        """
        return identity_embedding
