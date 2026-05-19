"""Test provider API — extended provider list with base_url and env_key."""
import json
import pytest
import pytest_asyncio
import tempfile
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from cococat.app import create_app


@pytest_asyncio.fixture
async def client():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    app = create_app(db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestProvidersApi:
    @pytest.mark.asyncio
    async def test_list_providers_includes_base_url_and_env_key(self, client):
        """GET /api/providers returns base_url and env_key for each provider."""
        resp = await client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        providers = data["providers"]
        assert len(providers) > 0

        deepseek = next((p for p in providers if p["name"] == "deepseek"), None)
        assert deepseek is not None
        assert "base_url" in deepseek
        assert deepseek["base_url"] == "https://api.deepseek.com"
        assert "env_key" in deepseek
        assert deepseek["env_key"] == "DEEPSEEK_API_KEY"

    @pytest.mark.asyncio
    async def test_list_providers_has_14_providers(self, client):
        """GET /api/providers returns all built-in providers."""
        resp = await client.get("/api/providers")
        data = resp.json()
        providers = data["providers"]
        names = {p["name"] for p in providers}
        assert "deepseek" in names
        assert "openai" in names
        assert "anthropic" in names
        assert "gemini" in names
        assert "ollama" in names
        assert len(providers) >= 20  # 29 builtins
        assert "openrouter" in names
        assert "minimax" in names


class TestProviderKeySave:
    @pytest.mark.asyncio
    async def test_save_provider_key(self, tmp_path, client):
        """PUT /api/providers/key saves key to auth.json and GET reflects it."""
        auth_path = tmp_path / "auth.json"
        auth_path.write_text('{"existing": "old-key"}')

        import os as _os
        original = _os.environ.copy()
        _os.environ["COCOCAT_AUTH_FILE"] = str(auth_path)

        try:
            # Save key
            resp = await client.put("/api/providers/key", json={
                "name": "deepseek",
                "key": "sk-test-123",
            })
            assert resp.status_code == 200
            assert resp.json()["saved"] is True

            # Verify auth.json was updated
            auth_data = json.loads(auth_path.read_text())
            assert auth_data["deepseek"] == "sk-test-123"
            assert auth_data["existing"] == "old-key"
        finally:
            _os.environ.clear()
            _os.environ.update(original)

    @pytest.mark.asyncio
    async def test_save_key_missing_params(self, client):
        """PUT /api/providers/key returns 422 for missing params."""
        resp = await client.put("/api/providers/key", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_save_key_unknown_provider(self, client):
        """PUT /api/providers/key returns 400 for unknown provider."""
        resp = await client.put("/api/providers/key", json={
            "name": "nonexistent-xyz",
            "key": "sk-xxx",
        })
        assert resp.status_code == 400


class TestProviderTest:
    @pytest.mark.asyncio
    async def test_provider_test_returns_ok(self, client):
        """POST /api/providers/test calls GET /models and returns ok/status."""
        resp = await client.post("/api/providers/test", json={
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "key": "sk-fake-key",
        })
        assert resp.status_code == 200
        data = resp.json()
        # With fake key, should get 401 or error
        assert "ok" in data
        assert "status" in data

    @pytest.mark.asyncio
    async def test_provider_test_missing_url(self, client):
        """POST /api/providers/test returns 4xx without base_url."""
        resp = await client.post("/api/providers/test", json={})
        assert resp.status_code in (400, 422)


class TestProviderFetchModels:
    @pytest.mark.asyncio
    async def test_fetch_models_returns_list(self, client):
        """POST /api/providers/fetch-models calls GET /models and returns model list."""
        # Use a provider that might respond; with fake key we'll get error
        resp = await client.post("/api/providers/fetch-models", json={
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "key": "sk-fake",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data or "error" in data

    @pytest.mark.asyncio
    async def test_fetch_models_missing_url(self, client):
        """fetch-models returns 4xx without base_url."""
        resp = await client.post("/api/providers/fetch-models", json={})
        assert resp.status_code in (400, 422)


class TestProviderModels:
    @pytest.mark.asyncio
    async def test_get_provider_models(self, client):
        """GET /api/providers/{name}/models returns structured model data."""
        resp = await client.get("/api/providers/deepseek/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "default" in data

    @pytest.mark.asyncio
    async def test_add_and_remove_model(self, client):
        """PUT /api/providers/{name}/models adds/removes models."""
        # Add a model
        resp = await client.put("/api/providers/deepseek/models", json={
            "action": "add",
            "model_id": "test-model",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["models"] is not None
        assert "test-model" in data["models"]

        # Verify persisted (new format: {available, enabled, default})
        resp = await client.get("/api/providers/deepseek/models")
        assert "test-model" in resp.json()["enabled"]

        # Remove
        resp = await client.put("/api/providers/deepseek/models", json={
            "action": "remove",
            "model_id": "test-model",
        })
        assert resp.status_code == 200
        assert "test-model" not in resp.json()["models"]
