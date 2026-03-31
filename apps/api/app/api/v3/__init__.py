"""
API v3 – AI Orchestrator endpoints

Central hub for all AI operations:
- Smart generation with automatic mode/category detection
- Two-pass generation (preview + full quality)
- Identity-based generation
- Group photo generation
- System status and health checks
"""

from .orchestrator import router

__all__ = ["router"]
