"""
Tests for Image Modification Engine.
"""

import pytest

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

try:
    from services.image_modification_engine import (
        IntentParser,
        ModificationPlanner,
        ImageModificationExecutor,
        ImageModificationEngine,
        ModificationType,
    )
except ImportError:
    from ai_pipeline.services.image_modification_engine import (
        IntentParser,
        ModificationPlanner,
        ImageModificationExecutor,
        ImageModificationEngine,
        ModificationType,
    )


pytestmark = pytest.mark.skipif(Image is None, reason="PIL required")


def _avg_luma(img: "Image.Image") -> float:
    # Convert to grayscale and average
    g = img.convert("L")
    px = list(g.getdata())
    return sum(px) / max(1, len(px))


def test_intent_parser_new_image():
    assert IntentParser.parse("make a new image of a cat") == ModificationType.NEW_IMAGE
    assert IntentParser.parse("something completely different") == ModificationType.NEW_IMAGE


def test_intent_parser_global():
    assert IntentParser.parse("make it brighter") == ModificationType.MODIFY_GLOBAL
    assert IntentParser.parse("increase contrast a bit") == ModificationType.MODIFY_GLOBAL


def test_intent_parser_style():
    assert IntentParser.parse("make it watercolor") == ModificationType.MODIFY_STYLE
    assert IntentParser.parse("same but as a noir photo") == ModificationType.MODIFY_STYLE


def test_intent_parser_region():
    assert IntentParser.parse("change the background to forest") == ModificationType.MODIFY_REGION
    assert IntentParser.parse("remove the sky clouds") == ModificationType.MODIFY_REGION


def test_planner_new_image():
    p = ModificationPlanner()
    plan = p.plan("make a new image of a dog", current_prompt="a cat")
    assert plan.mod_type == ModificationType.NEW_IMAGE
    assert plan.new_prompt == "make a new image of a dog"


def test_planner_global_brightness():
    p = ModificationPlanner()
    plan = p.plan("make it brighter", current_prompt="x")
    assert plan.mod_type == ModificationType.MODIFY_GLOBAL
    assert "brightness" in plan.global_adjustments
    assert plan.global_adjustments["brightness"] > 0


def test_planner_style_strength_subtle():
    p = ModificationPlanner()
    plan = p.plan("make it slightly watercolor", current_prompt="x")
    assert plan.mod_type == ModificationType.MODIFY_STYLE
    assert plan.img2img_strength == pytest.approx(0.35, abs=1e-6)


def test_executor_apply_global_brightness_increases_luma():
    ex = ImageModificationExecutor()
    img = Image.new("RGB", (64, 64), (30, 30, 30))
    plan = ModificationPlanner().plan("make it brighter", current_prompt="x")
    out, _ = ex.execute(img, plan, diffusion_pipeline=None)
    assert out.size == img.size
    assert _avg_luma(out) > _avg_luma(img)


def test_executor_fallback_noir_is_grayscale():
    ex = ImageModificationExecutor()
    img = Image.new("RGB", (32, 32), (10, 80, 200))
    plan = ModificationPlanner().plan("make it noir", current_prompt="x")
    out, _ = ex.execute(img, plan, diffusion_pipeline=None)
    assert out.size == img.size
    r, g, b = out.split()
    assert list(r.getdata()) == list(g.getdata()) == list(b.getdata())


def test_engine_modify_returns_plan_and_image():
    engine = ImageModificationEngine(diffusion_pipeline=None)
    img = Image.new("RGB", (64, 64), (50, 50, 50))
    out, plan = engine.modify(img, "make it more vibrant", current_prompt="a portrait")
    assert out.size == img.size
    assert plan.mod_type in (
        ModificationType.MODIFY_GLOBAL,
        ModificationType.MODIFY_STYLE,
        ModificationType.MODIFY_REGION,
        ModificationType.MODIFY_ATTRIBUTE,
        ModificationType.NEW_IMAGE,
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

