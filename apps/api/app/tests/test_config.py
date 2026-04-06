from app.services.smart import config


def test_get_model_config_uses_canonical_flux2pro_default(monkeypatch) -> None:
    monkeypatch.setitem(config.BUCKET_MODEL_MAP, "broken_bucket", {})

    result = config.get_model_config("broken_bucket", "balanced")

    assert result["model"] == "flux_2_pro"
    assert result["provider"] == "multi"
