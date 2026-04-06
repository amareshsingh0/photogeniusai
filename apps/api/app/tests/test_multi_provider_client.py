from app.services.external.multi_provider_client import MultiProviderClient


def test_get_client_uses_bearer_auth_for_kie(monkeypatch) -> None:
    monkeypatch.setenv("KIE_API_KEY", "test-kie-key")

    client = MultiProviderClient()._get_client("kie")

    assert client.headers["Authorization"] == "Bearer test-kie-key"
