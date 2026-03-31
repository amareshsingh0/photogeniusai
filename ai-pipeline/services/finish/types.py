"""Shared types for finish engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FinishResult:
    """Result of a generation finish (Flux/Replicate)."""

    image_url: str
    alternative_urls: List[str]
    generation_time: float
    model_used: str
    parameters: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_url": self.image_url,
            "alternative_urls": self.alternative_urls,
            "generation_time": self.generation_time,
            "model_used": self.model_used,
            "parameters": self.parameters,
            "metadata": self.metadata or {},
        }
