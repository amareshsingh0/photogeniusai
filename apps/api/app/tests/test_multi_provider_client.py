import asyncio

from app.services.external.multi_provider_client import MODEL_PROVIDER_CHAIN, MultiProviderClient


def test_get_client_uses_bearer_auth_for_kie(monkeypatch) -> None:
    monkeypatch.setenv("KIE_API_KEY", "test-kie-key")

    client = MultiProviderClient()._get_client("kie")

    assert client.headers["Authorization"] == "Bearer test-kie-key"


def test_generate_accepts_legacy_flux_pro_alias(monkeypatch) -> None:
    monkeypatch.setenv("KIE_API_KEY", "test-kie-key")
    client = MultiProviderClient()
    calls = []

    async def fake_call_provider(provider: str, model_id: str, **kwargs):
        calls.append((provider, model_id, kwargs["prompt"]))
        return {
            "image_url": "https://example.com/generated.jpg",
            "all_urls": ["https://example.com/generated.jpg"],
            "image_b64": None,
            "metadata": {},
            "success": True,
            "backend": "test-backend",
            "model": model_id,
            "generation_time": 0.01,
        }

    monkeypatch.setattr(client, "_call_provider", fake_call_provider)

    result = asyncio.run(client.generate(model_key="flux_pro", prompt="festival poster"))

    assert result["success"] is True
    assert result["model_key"] == "flux_2_pro"
    assert result["requested_model_key"] == "flux_pro"
    assert calls[0][1] == MODEL_PROVIDER_CHAIN["flux_2_pro"][0][1]
