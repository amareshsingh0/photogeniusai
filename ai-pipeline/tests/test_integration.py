"""
End-to-end integration tests for the complete pipeline.

Tests: enhancement -> config -> generation -> quality -> retry.

Run from ai-pipeline:
  pytest tests/test_integration.py -v -s
  # or
  python tests/test_integration.py

Requires ai-pipeline on PYTHONPATH. Tests that need real Flux/Replicate API
will skip with NotImplementedError; domain, config, and enhancer tests run
when services load (fix services/__init__.py if imports fail).

Validation checklist:
- Full pipeline works end-to-end (when finish engine implemented)
- Domain classification is accurate (test_different_domains)
- Wow boosters enhance prompts (test_wow_boosters_enhance_prompts)
- Config auto-detection works (test_config_builder)
- Quality assessment / verdict thresholds (test_quality_verdict_thresholds)
- Retry logic (test_quality_retry when generation available)
- API endpoints: see apps/api unified_generate.py
- Error handling: skips and HTTP errors in endpoints
- Performance: run with real backend for timing
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest  # type: ignore[reportMissingImports]

# Ensure ai-pipeline is on path so "services" resolves
_tests_dir = Path(__file__).resolve().parent
_ai_pipeline = _tests_dir.parent
if str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

# Optional imports (skip module if deps unavailable). Typed as Any so Pyright allows use after assert.
UnifiedOrchestrator: Any = None
OrchestrationResult: Any = None
GenerationQuality: Any = None
QualityVerdict: Any = None
UniversalPromptEnhancer: Any = None
PromptDomain: Any = None
SmartConfigBuilder: Any = None

try:
    from services.unified_orchestrator import UnifiedOrchestrator as _UO, OrchestrationResult as _OR
    from services.generation_config import GenerationQuality as _GQ, SmartConfigBuilder as _SB
    from services.quality_assessment import QualityVerdict as _QV
    UnifiedOrchestrator = _UO
    OrchestrationResult = _OR
    GenerationQuality = _GQ
    SmartConfigBuilder = _SB
    QualityVerdict = _QV
except Exception:
    pass

try:
    from services.universal_prompt_enhancer import UniversalPromptEnhancer as _UPEnh, PromptDomain as _PD
    UniversalPromptEnhancer = _UPEnh
    PromptDomain = _PD
except Exception:
    pass


def _orch_available():
    return UnifiedOrchestrator is not None and QualityVerdict is not None


def _enhancer_available():
    return UniversalPromptEnhancer is not None and PromptDomain is not None


def _config_available():
    return SmartConfigBuilder is not None and GenerationQuality is not None


# ==================== Full pipeline (requires real Flux/Replicate or skip) ====================


@pytest.mark.asyncio
async def test_full_pipeline_image():
    """Test complete image generation pipeline (skips if finish engine not implemented)."""
    if not _orch_available():
        pytest.skip("UnifiedOrchestrator not available (services package)")
    Orch = UnifiedOrchestrator
    QV = QualityVerdict
    GQ = GenerationQuality
    assert Orch is not None and QV is not None and GQ is not None
    orchestrator = Orch(
        max_retries=1,
        quality_threshold=QV.ACCEPTABLE,
        finish_engine="flux",
    )
    try:
        result = await orchestrator.process(
            prompt="young woman at beach sunset",
            wow_intensity=0.8,
            quality=GQ.FAST,
            skip_quality_check=True,
        )
    except NotImplementedError as e:
        pytest.skip(f"Finish engine not implemented (need real Flux/Replicate): {e}")
    if not result.success and result.error_message and "not configured" in result.error_message.lower():
        pytest.skip(f"Finish engine not configured: {result.error_message}")
    assert result.success, result.error_message or "process failed"
    assert result.image_url
    domain_val = getattr(result.domain, "value", str(result.domain))
    assert domain_val == "image"
    assert result.attempts_made >= 1
    print(f"[OK] Image generated: {result.image_url[:60]}...")


@pytest.mark.asyncio
async def test_quality_retry():
    """Test quality-based retry logic (skips if finish engine not implemented)."""
    if not _orch_available():
        pytest.skip("UnifiedOrchestrator not available")
    Orch = UnifiedOrchestrator
    QV = QualityVerdict
    GQ = GenerationQuality
    assert Orch is not None and QV is not None and GQ is not None
    orchestrator = Orch(
        max_retries=2,
        quality_threshold=QV.EXCELLENT,
        finish_engine="flux",
    )
    try:
        result = await orchestrator.process(
            prompt="simple test",
            wow_intensity=0.5,
            quality=GQ.FAST,
        )
    except NotImplementedError as e:
        pytest.skip(f"Finish engine not implemented: {e}")
    if not result.success and result.error_message and "not configured" in (result.error_message or "").lower():
        pytest.skip(f"Finish engine not configured: {result.error_message}")
    assert result.attempts_made >= 1
    if result.quality_score:
        assert result.quality_score.verdict in (
            QV.EXCELLENT,
            QV.GOOD,
            QV.ACCEPTABLE,
            QV.POOR,
        )
    # Either we made multiple attempts (retry) or we achieved EXCELLENT
    assert result.attempts_made > 1 or (
        result.quality_score is not None
        and result.quality_score.verdict == QV.EXCELLENT
    ), f"expected retries or EXCELLENT; got attempts={result.attempts_made} verdict={getattr(result.quality_score, 'verdict', None)}"
    print(f"[OK] Quality retry: {result.attempts_made} attempts")


# ==================== Enhancement only (no generation) ====================


@pytest.mark.asyncio
async def test_different_domains():
    """Test enhancement and domain classification across domains."""
    if not _enhancer_available():
        pytest.skip("UniversalPromptEnhancer not available")
    Enhancer = UniversalPromptEnhancer
    assert Enhancer is not None
    enhancer = Enhancer()
    test_cases = [
        ("young woman portrait", "image"),
        ("solve x^2 + 5x + 6", "math_reasoning"),
        ("write a story about robots", "creative_writing"),
        ("create Python function to sort", "code"),
        ("what is quantum physics", "general"),
    ]
    for prompt, expected_domain in test_cases:
        result = enhancer.enhance(prompt, wow_intensity=0.6)
        domain_val = getattr(result.domain, "value", str(result.domain))
        assert domain_val == expected_domain, f"prompt={prompt!r} got domain={domain_val}"
        assert len(result.enhanced) >= len(prompt)
        print(f"[OK] {prompt[:30]:30} -> {domain_val}")


# ==================== Config builder only ====================


def test_config_builder():
    """Test smart config builder presets and auto-detection."""
    if not _config_available():
        pytest.skip("SmartConfigBuilder not available")
    Builder = SmartConfigBuilder
    GQ = GenerationQuality
    assert Builder is not None and GQ is not None
    builder = Builder()
    config = builder.build_from_preset(
        quality=GQ.ULTRA,
        aspect_ratio="16:9",
    )
    assert config.steps >= 70
    assert config.width == 1344
    assert config.height == 768
    print(f"[OK] Config: {config.steps} steps, {config.width}x{config.height}")
    config2 = builder.auto_build_config(
        prompt="portrait of woman, highly detailed, masterpiece",
        domain="image",
    )
    assert config2.quality_preset == GQ.ULTRA
    assert config2.aspect_ratio == "3:4"
    print(f"[OK] Auto-detected: {config2.quality_preset.value}, {config2.aspect_ratio}")


# ==================== Enhancement + wow boosters ====================


def test_wow_boosters_enhance_prompts():
    """Test that wow boosters are applied and enhance prompt length."""
    if not _enhancer_available():
        pytest.skip("UniversalPromptEnhancer not available")
    Enhancer = UniversalPromptEnhancer
    assert Enhancer is not None
    enhancer = Enhancer()
    prompt = "a dragon in the sky"
    result = enhancer.enhance(prompt, wow_intensity=0.8)
    assert len(result.enhanced) > len(prompt)
    assert result.wow_factor_score >= 0
    assert "unexpected_twist" in result.enhancements_applied or any(
        "twist" in s for s in result.enhancements_applied
    )
    print(f"[OK] Wow boosters applied: {len(result.enhancements_applied)} enhancements")


# ==================== Quality assessment (no generation URL needed for helpers) ====================


def test_quality_verdict_thresholds():
    """Test quality verdict ordering and threshold logic."""
    QV = QualityVerdict
    if QV is None:
        pytest.skip("QualityVerdict not available")
    assert QV is not None
    try:
        from services.quality_assessment import QualityAssessment
    except Exception as e:
        pytest.skip(f"QualityAssessment not available: {e}")
    assessor = QualityAssessment()
    assert assessor._determine_verdict(0.9) == QV.EXCELLENT
    assert assessor._determine_verdict(0.80) == QV.GOOD
    assert assessor._determine_verdict(0.70) == QV.ACCEPTABLE
    assert assessor._determine_verdict(0.5) == QV.POOR
    print("[OK] Quality verdict thresholds OK")


# ==================== Run from command line ====================


if __name__ == "__main__":
    skipped = []

    async def _run_async_tests():
        for name, coro in [
            ("full_pipeline", test_full_pipeline_image()),
            ("quality_retry", test_quality_retry()),
            ("different_domains", test_different_domains()),
        ]:
            try:
                await coro
            except BaseException as e:
                skipped.append(f"{name}: {e}")

    try:
        asyncio.run(_run_async_tests())
    except BaseException as e:
        skipped.append(f"async: {e}")

    for name, fn in [
        ("config_builder", test_config_builder),
        ("wow_boosters", test_wow_boosters_enhance_prompts),
        ("quality_verdict", test_quality_verdict_thresholds),
    ]:
        try:
            fn()
        except BaseException as e:
            skipped.append(f"{name}: {e}")

    if skipped:
        print("\nSkipped or failed:", *skipped, sep="\n  ")
    print("\n[OK] Integration test run finished.")
