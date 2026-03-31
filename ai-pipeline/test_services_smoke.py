#!/usr/bin/env python3
"""Smoke tests for prompt_service, routing_service, execution_service (direct load)."""

from __future__ import annotations

import sys
from pathlib import Path

# Load modules directly to avoid services.__init__ side effects
def _load(name: str, rel_path: str):
    import importlib.util
    root = Path(__file__).resolve().parent
    path = (root / rel_path).resolve()
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_prompt_service():
    import types
    obs = types.ModuleType("observability")
    obs.trace_function = lambda n=None: (lambda f: f)
    obs.track_llm_call = lambda _: (lambda f: f)
    obs.CircuitBreaker = None
    obs.Metrics = None
    obs.StructuredLogger = None
    services = types.ModuleType("services")
    services.observability = obs
    sys.modules["services"] = services
    sys.modules["services.observability"] = obs

    ps = _load("prompt_service", "services/prompt_service.py")
    svc = ps.PromptService(claude_client=None)
    p = svc.parse("beach", mode="REALISM", use_cache=False)
    assert p.full_prompt
    assert "beach" in p.subject
    assert p.parsing_method == "fallback"
    assert p.final_prompt == p.full_prompt

    out = svc.synthesize_multimodal_from_parts(
        ["User text: sunset", "Reference image: golden hour"],
        mode="REALISM",
    )
    assert isinstance(out, str)
    assert "sunset" in out or "golden" in out or "|" in out

    # synthesize_multimodal -> ParsedPrompt (no Claude)
    parsed = svc.synthesize_multimodal(
        text_prompt="portrait",
        image_analysis=None,
        voice_transcript=None,
        mode="REALISM",
    )
    assert hasattr(parsed, "full_prompt")
    assert hasattr(parsed, "final_prompt")
    assert parsed.parsing_method in ("fallback", "claude_multimodal")
    print("  prompt_service OK")


def test_routing_service():
    import types
    obs = types.ModuleType("observability")
    obs.trace_function = lambda n=None: (lambda f: f)
    obs.StructuredLogger = None
    services = types.ModuleType("services")
    services.observability = obs
    sys.modules["services"] = services
    sys.modules["services.observability"] = obs

    rs = _load("routing_service", "services/routing_service.py")
    svc = rs.RoutingService(ultra_available=False)
    r = svc.select_engine("BALANCED", width=1024, height=1024, user_tier="free")
    assert r.engine in ("realtime", "sdxl", "ultra_high_res")
    assert r.estimated_time_seconds >= 0
    assert r.params_override

    r2 = svc.select_engine("FAST", resolution=1024, user_tier="pro")
    assert r2.engine in ("realtime", "sdxl", "ultra_high_res")
    print("  routing_service OK")


def test_execution_service():
    import types
    obs = types.ModuleType("observability")
    obs.trace_function = lambda n=None: (lambda f: f)
    obs.tracked_engine_call = lambda _n, fn, *a, **k: fn(*a, **k)
    obs.StructuredLogger = None
    services = types.ModuleType("services")
    services.observability = obs
    sys.modules["services"] = services
    sys.modules["services.observability"] = obs
    rt = types.ModuleType("routing_service")
    rt.EngineType = type("E", (), {"REALTIME": "realtime", "ULTRA_HIGH_RES": "ultra_high_res"})()
    sys.modules["services.routing_service"] = rt

    ex = _load("execution_service", "services/execution_service.py")
    svc = ex.ExecutionService()
    assert not svc.has_engine("realtime")
    svc.register_realtime(lambda **kw: [{"image_base64": "x", "prompt": kw.get("prompt", "")}])
    assert svc.has_engine("realtime")
    out = svc.execute_realtime(prompt="test", mode="REALISM")
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0].get("prompt") == "test"
    print("  execution_service OK")


if __name__ == "__main__":
    test_prompt_service()
    test_routing_service()
    test_execution_service()
    print("services smoke OK")
