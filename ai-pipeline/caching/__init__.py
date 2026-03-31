"""
PhotoGenius Caching Module
Smart caching for repeated generation requests. Reduces compute and latency.
"""

from .smart_cache import SmartCache, smart_cache_app

__all__ = ["SmartCache", "smart_cache_app"]
