from app.api.v1.endpoints.admin_models import (
    DEFAULT_MODELS,
    _canonical_model_id,
    _equivalent_model_ids,
)


def test_legacy_model_ids_map_to_canonical_registry() -> None:
    assert _canonical_model_id("imagen_4_standard") == "imagen_4_base"
    assert _canonical_model_id("gemini_flash_image") == "gemini_3_imagen"


def test_equivalent_model_ids_include_legacy_aliases() -> None:
    assert _equivalent_model_ids("imagen_4_base") == ["imagen_4_base", "imagen_4_standard"]
    assert _equivalent_model_ids("gemini_flash_image") == ["gemini_3_imagen", "gemini_flash_image"]


def test_default_model_registry_avoids_unintegrated_provider_labels() -> None:
    providers = {model["provider"] for model in DEFAULT_MODELS}

    assert "wavespeed" not in providers
    assert "vertex" not in providers
