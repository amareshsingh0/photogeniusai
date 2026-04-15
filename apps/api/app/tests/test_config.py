from app.services.smart.model_config import QualityTier, get_model_for_request, normalize_quality_tier


def test_get_model_for_request_returns_valid_model() -> None:
    result = get_model_for_request("photorealism", "2k")

    assert result["model"] is not None
    assert result["provider"] in {"fal", "google", "xai", "hunyuan", "ideogram", "seedream", "wan", "recraft"}
    assert result["num_images"] == 1
    assert result["tier_used"] == QualityTier.RES_2K.value


def test_get_model_for_request_fallback_for_unknown_bucket() -> None:
    result = get_model_for_request("unknown_bucket", "quality")

    # Legacy "quality" should normalize to 2k and use the 2k default model.
    assert result["model"] is not None
    assert result["num_images"] == 1
    assert result["tier_used"] == QualityTier.RES_2K.value
    assert result["model_key"] == "imagen_4_base"


def test_normalize_quality_tier_maps_legacy_values() -> None:
    assert normalize_quality_tier("fast") == QualityTier.RES_1K.value
    assert normalize_quality_tier("balanced") == QualityTier.RES_2K.value
    assert normalize_quality_tier("quality") == QualityTier.RES_2K.value
    assert normalize_quality_tier("ultra") == QualityTier.RES_4K.value


def test_get_model_for_request_selects_4k_model() -> None:
    result = get_model_for_request("photorealism", "4k")

    assert result["model_key"] == "imagen_4_ultra"
    assert result["max_resolution"] == 4096
