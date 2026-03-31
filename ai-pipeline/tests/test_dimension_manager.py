"""
Tests for Dimension Manager.
"""

import pytest

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False

try:
    from services.dimension_manager import (
        DimensionManager,
        DimensionPlan,
        DimensionSpec,
        resolve_dimensions,
        compute_aspect_ratio,
        gcd,
        MIN_DIMENSION,
        MAX_DIMENSION,
        MAX_MEGAPIXELS,
        NATIVE_RESOLUTIONS,
    )
except ImportError:
    from ai_pipeline.services.dimension_manager import (
        DimensionManager,
        DimensionPlan,
        DimensionSpec,
        resolve_dimensions,
        compute_aspect_ratio,
        gcd,
        MIN_DIMENSION,
        MAX_DIMENSION,
        MAX_MEGAPIXELS,
        NATIVE_RESOLUTIONS,
    )


def test_gcd():
    assert gcd(16, 9) == 1
    assert gcd(1920, 1080) == 120
    assert gcd(100, 50) == 50


def test_compute_aspect_ratio():
    assert compute_aspect_ratio(1920, 1080) == "16:9"
    assert compute_aspect_ratio(1024, 1024) == "1:1"
    assert compute_aspect_ratio(768, 512) == "3:2"


def test_validate_ok():
    dm = DimensionManager()
    assert dm.validate(1024, 1024) is None
    assert dm.validate(1920, 1080) is None


def test_validate_too_small():
    dm = DimensionManager()
    err = dm.validate(32, 32)
    assert err is not None
    assert str(MIN_DIMENSION) in err


def test_validate_too_large():
    dm = DimensionManager()
    err = dm.validate(5000, 5000)
    assert err is not None


def test_validate_megapixels():
    dm = DimensionManager()
    # 4000x4000 = 16 MP > 12
    err = dm.validate(4000, 4000)
    assert err is not None
    assert "MP" in err or "megapixel" in err.lower() or "12" in err


def test_plan_dimensions_1920x1080():
    dm = DimensionManager()
    plan = dm.plan_dimensions(1920, 1080)
    assert plan.is_valid is True
    assert plan.requested_w == 1920
    assert plan.requested_h == 1080
    assert plan.aspect_ratio == "16:9"
    assert plan.native_w > 0 and plan.native_h > 0
    assert (plan.native_w, plan.native_h) in NATIVE_RESOLUTIONS
    assert plan.post_process_strategy in ("exact", "upscale", "downscale")


def test_plan_dimensions_invalid():
    dm = DimensionManager()
    plan = dm.plan_dimensions(10, 10)
    assert plan.is_valid is False
    assert plan.validation_error is not None
    assert plan.native_w == 0 and plan.native_h == 0


def test_plan_dimensions_1024_exact():
    dm = DimensionManager()
    plan = dm.plan_dimensions(1024, 1024)
    assert plan.is_valid is True
    assert plan.native_w == 1024 and plan.native_h == 1024
    assert plan.post_process_strategy == "exact"


def test_parse_dimension_string():
    assert DimensionManager.parse_dimension_string("1920x1080") == (1920, 1080)
    assert DimensionManager.parse_dimension_string("1920 x 1080") == (1920, 1080)
    assert DimensionManager.parse_dimension_string("512, 512") == (512, 512)
    assert DimensionManager.parse_dimension_string("") is None
    assert DimensionManager.parse_dimension_string("invalid") is None


def test_preset_dimensions():
    assert DimensionManager.preset_dimensions("4k") == (3840, 2160)
    assert DimensionManager.preset_dimensions("instagram_story") == (1080, 1920)
    assert DimensionManager.preset_dimensions("favicon") == (64, 64)
    assert DimensionManager.preset_dimensions("unknown_preset") is None


def test_resolve_dimensions_default():
    plan = resolve_dimensions()
    assert plan.is_valid is True
    assert plan.requested_w == 1024 and plan.requested_h == 1024


def test_resolve_dimensions_preset():
    plan = resolve_dimensions(preset="fullhd")
    assert plan.is_valid is True
    assert plan.requested_w == 1920 and plan.requested_h == 1080


def test_resolve_dimensions_explicit():
    plan = resolve_dimensions(width=800, height=600)
    assert plan.is_valid is True
    assert plan.requested_w == 800 and plan.requested_h == 600


@pytest.mark.skipif(not HAS_PIL, reason="PIL required for post_process")
def test_post_process_exact():
    dm = DimensionManager()
    plan = dm.plan_dimensions(512, 512)
    img = Image.new("RGB", (512, 512), (128, 128, 128))
    out = dm.post_process(img, plan)
    assert out.size == (512, 512)


@pytest.mark.skipif(not HAS_PIL, reason="PIL required for post_process")
def test_post_process_upscale_crop():
    dm = DimensionManager()
    plan = dm.plan_dimensions(1920, 1080)
    # Native might be 1280x720; generate at native then post-process
    plan.native_w = 1280
    plan.native_h = 720
    plan.post_process_strategy = "upscale"
    img = Image.new("RGB", (1280, 720), (0, 0, 0))
    out = dm.post_process(img, plan)
    assert out.size == (1920, 1080)


@pytest.mark.skipif(not HAS_PIL, reason="PIL required for post_process")
def test_post_process_invalid_plan_returns_unchanged():
    dm = DimensionManager()
    plan = DimensionPlan(
        requested_w=100,
        requested_h=100,
        native_w=0,
        native_h=0,
        post_process_strategy="none",
        aspect_ratio="",
        is_valid=False,
    )
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    out = dm.post_process(img, plan)
    assert out is img


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
