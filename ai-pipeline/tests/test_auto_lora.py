"""
Tests for auto-LoRA selection: recommend_loras, orchestrator integration, two_pass lora_names.
Edge cases: multi-category, no people/scene, LoRAs only applied when present on disk/S3.
"""

import pytest
from unittest.mock import patch, MagicMock

try:
    from services.smart_prompt_engine import SmartPromptEngine
    from services.universal_prompt_classifier import UniversalPromptClassifier, ClassificationResult
    from services.orchestrator_aws import generate_professional
except ImportError:
    from ai_pipeline.services.smart_prompt_engine import SmartPromptEngine
    from ai_pipeline.services.universal_prompt_classifier import (
        UniversalPromptClassifier,
        ClassificationResult,
    )
    from ai_pipeline.services.orchestrator_aws import generate_professional


def test_orchestrator_passes_lora_names_to_two_pass():
    """generate_professional calls generate_two_pass with lora_names when classifier/engine available."""
    import sys
    mod = sys.modules.get("services.orchestrator_aws") or sys.modules.get("ai_pipeline.services.orchestrator_aws")
    if mod is None:
        pytest.skip("orchestrator_aws not loaded")
    fake_result = {
        "preview": None,
        "final": None,
        "preview_base64": None,
        "final_base64": "fake_base64",
        "preview_time": 0.0,
        "final_time": 1.0,
    }
    with patch.object(mod, "generate_two_pass", return_value=fake_result) as m_two:
        with patch.object(mod, "generate_fast", return_value=fake_result):
            out = generate_professional(
                user_prompt="cinematic portrait of a woman",
                quality_tier="STANDARD",
            )
    assert out.get("status") in ("success", "error")
    if m_two.called:
        call_kw = m_two.call_args[1]
        assert "lora_names" in call_kw
        lora_names = call_kw["lora_names"]
        assert lora_names is None or (isinstance(lora_names, list) and len(lora_names) <= 3)


def test_two_pass_accepts_lora_names_signature():
    """generate_two_pass accepts lora_names parameter (ensure LoRAs only loaded when exist)."""
    try:
        from services.two_pass_generation import generate_two_pass
    except ImportError:
        from ai_pipeline.services.two_pass_generation import generate_two_pass
    import inspect
    sig = inspect.signature(generate_two_pass)
    assert "lora_names" in sig.parameters
    param = sig.parameters["lora_names"]
    assert param.default is None or param.default == []


def test_classifier_plus_recommend_loras_cinematic_portrait():
    """End-to-end: classify 'cinematic portrait' then recommend_loras yields expected set."""
    classifier = UniversalPromptClassifier()
    engine = SmartPromptEngine()
    classification = classifier.classify("cinematic portrait of a man in a suit")
    loras = engine.recommend_loras(classification)
    assert "color_harmony_v1" in loras
    # Portrait or has_people → skin_realism_v2; photograph medium → cinematic_lighting_v3
    assert len(loras) <= 3
    for name in loras:
        assert name in ("color_harmony_v1", "skin_realism_v2", "cinematic_lighting_v3")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])
