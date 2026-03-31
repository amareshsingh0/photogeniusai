"""
Engine routing and tier logic.

Encapsulates quality-tier → engine mapping, resolution caps, and routing decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from services.observability import StructuredLogger, trace_function
except ImportError:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    StructuredLogger = None  # type: ignore[assignment, misc]

try:
    from config.tier_config import get_tier_limits, normalize_tier

    _USE_TIER_CONFIG = True
except ImportError:
    _USE_TIER_CONFIG = False
    get_tier_limits = None  # type: ignore[assignment, misc]
    normalize_tier = None  # type: ignore[assignment, misc]


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


class QualityTier(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    BALANCED = "BALANCED"
    PREMIUM = "PREMIUM"
    ULTRA = "ULTRA"


class EngineType(str, Enum):
    REALTIME = "realtime"
    SDXL = "sdxl"
    ULTRA_HIGH_RES = "ultra_high_res"
    IDENTITY_V2 = "identity_v2"
    CREATIVE = "creative"
    COMPOSITION = "composition"
    FINISH = "finish"


@dataclass
class RoutingDecision:
    """Engine routing decision."""

    engine: str  # engine name (realtime, ultra_high_res, sdxl, ...)
    engine_type: EngineType
    estimated_time_seconds: int
    resolution_cap: int
    width: int
    height: int
    params_override: Dict[str, Any]
    reason: str


# Align with orchestrator QUALITY_TIER_CONFIG
TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "FAST": {
        "engine": "realtime",
        "steps": 4,
        "target_time": 8,
        "max_resolution": 1024,
        "guidance_scale": 5.0,
    },
    "STANDARD": {
        "engine": "realtime",
        "steps": 8,
        "target_time": 15,
        "max_resolution": 1024,
        "guidance_scale": 6.0,
    },
    "BALANCED": {
        "engine": "sdxl",
        "steps": 50,
        "target_time": 50,
        "max_resolution": 2048,
        "guidance_scale": 7.5,
    },
    "PREMIUM": {
        "engine": "sdxl",
        "steps": 80,
        "target_time": 90,
        "max_resolution": 2048,
        "guidance_scale": 8.0,
    },
    "ULTRA": {
        "engine": "ultra_high_res",
        "steps": 80,
        "target_time": 180,
        "max_resolution": 4096,
        "guidance_scale": 8.0,
    },
}

TIER_RESOLUTION_CAPS: Dict[str, int] = {
    "free": 1024,
    "hobby": 1024,
    "pro": 2048,
    "studio": 4096,
    "enterprise": 4096,
}


class RoutingService:
    """Intelligent engine routing based on request parameters."""

    def __init__(
        self,
        ultra_available: bool = False,
        estimate_ultra_time_fn: Optional[Any] = None,
    ):
        self.ultra_available = ultra_available
        self.estimate_ultra_time = estimate_ultra_time_fn
        _log().info("RoutingService initialized")

    def _resolution_cap_for_tier(self, user_tier: Optional[str]) -> int:
        if not user_tier:
            return 1024
        t = (user_tier or "free").lower()
        return TIER_RESOLUTION_CAPS.get(t, 1024)

    def _validate_and_cap_resolution(
        self,
        width: int,
        height: int,
        user_tier: Optional[str],
        quality_tier: str,
    ) -> tuple:
        cap = self._resolution_cap_for_tier(user_tier)
        tier_cfg = TIER_CONFIG.get(
            (quality_tier or "BALANCED").upper(),
            TIER_CONFIG["BALANCED"],
        )
        max_res = min(cap, tier_cfg.get("max_resolution", 2048))
        w = max(256, min(width, max_res))
        h = max(256, min(height, max_res))
        return w, h

    @trace_function("routing.select_engine")
    def select_engine(
        self,
        quality_tier: str,
        width: int = 1024,
        height: int = 1024,
        resolution: Optional[int] = None,
        user_tier: Optional[str] = None,
        has_identity: bool = False,
        has_style: bool = False,
    ) -> RoutingDecision:
        """
        Select engine and params from quality tier and resolution.

        When resolution is provided, it is used as max(width, height) for routing;
        width/height still default to 1024 unless overridden.
        """
        if resolution is not None:
            width = height = max(256, resolution)
        t = (quality_tier or "BALANCED").upper()
        w, h = self._validate_and_cap_resolution(
            width, height, user_tier, t
        )
        max_dim = max(w, h)
        cap = self._resolution_cap_for_tier(user_tier)

        use_ultra = self.ultra_available and (
            max_dim > 2048 or t == "ULTRA"
        )
        if use_ultra:
            cfg = TIER_CONFIG.get("ULTRA", TIER_CONFIG["BALANCED"]).copy()
            cfg["width"] = min(w, 4096)
            cfg["height"] = min(h, 4096)
            est = cfg.get("target_time", 180)
            if self.estimate_ultra_time:
                try:
                    est = int(self.estimate_ultra_time(cfg["width"], cfg["height"], 1))
                except Exception:
                    pass
            _log().info(
                "Ultra High-Res routing: %dx%d (tier=%s), ~%ds"
                % (cfg["width"], cfg["height"], t, est)
            )
            return RoutingDecision(
                engine="ultra_high_res",
                engine_type=EngineType.ULTRA_HIGH_RES,
                estimated_time_seconds=est,
                resolution_cap=cap,
                width=cfg["width"],
                height=cfg["height"],
                params_override={
                    "num_inference_steps": cfg.get("steps", 80),
                    "guidance_scale": cfg.get("guidance_scale", 8.0),
                },
                reason="Resolution %d requires Ultra High-Res engine" % max_dim,
            )

        cfg = TIER_CONFIG.get(t, TIER_CONFIG["BALANCED"]).copy()
        cfg["width"] = w
        cfg["height"] = h
        eng = cfg.get("engine", "sdxl")
        et = (
            EngineType.ULTRA_HIGH_RES
            if eng == "ultra_high_res"
            else EngineType.REALTIME
            if eng == "realtime"
            else EngineType.SDXL
        )
        _log().info(
            "Routing: engine=%s tier=%s target=%ss"
            % (eng, t, cfg.get("target_time", 50))
        )
        return RoutingDecision(
            engine=eng,
            engine_type=et,
            estimated_time_seconds=cfg.get("target_time", 50),
            resolution_cap=cap,
            width=w,
            height=h,
            params_override={
                "num_inference_steps": cfg.get("steps", 50),
                "guidance_scale": cfg.get("guidance_scale", 7.5),
            },
            reason="Quality tier %s -> %s" % (t, eng),
        )
