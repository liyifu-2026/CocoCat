"""Test settings API — API key configuration."""
import os
import tempfile
import pytest
import pytest_asyncio
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


class TestSettingsApi:
    @pytest.mark.asyncio
    async def test_get_settings_returns_key_status(self, client):
        """GET /api/settings returns API key status for configured services."""
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        # Should have at least tavily key status
        keys = {k["name"]: k for k in data["keys"]}
        assert "tavily" in keys
        assert "has_key" in keys["tavily"]

    @pytest.mark.asyncio
    async def test_save_and_retrieve_api_key(self, tmp_path, client):
        """PUT /api/settings/key saves a key and GET returns updated status."""
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING_KEY=old_value\n")

        original_environ = os.environ.copy()
        os.environ["COCOCAT_ENV_FILE"] = str(env_path)

        try:
            # Save a new key
            resp = await client.put("/api/settings/key", json={
                "name": "tavily",
                "value": "tvly-test-key-123",
            })
            assert resp.status_code == 200
            assert resp.json()["saved"] is True

            # Verify the file was updated
            content = env_path.read_text()
            assert "TAVILY_API_KEY=tvly-test-key-123" in content
            # Original key preserved
            assert "EXISTING_KEY=old_value" in content

            # GET now shows has_key=true
            resp = await client.get("/api/settings")
            keys = {k["name"]: k for k in resp.json()["keys"]}
            tavily = keys.get("tavily")
            assert tavily is not None
            assert tavily["has_key"] is True
        finally:
            os.environ.clear()
            os.environ.update(original_environ)

    @pytest.mark.asyncio
    async def test_update_existing_key(self, tmp_path, client):
        """PUT /api/settings/key updates an existing key."""
        env_path = tmp_path / ".env"
        env_path.write_text("TAVILY_API_KEY=old-key-value\nOTHER=val\n")

        original_environ = os.environ.copy()
        os.environ["COCOCAT_ENV_FILE"] = str(env_path)

        try:
            resp = await client.put("/api/settings/key", json={
                "name": "tavily",
                "value": "new-key-value",
            })
            assert resp.status_code == 200

            content = env_path.read_text()
            assert "TAVILY_API_KEY=new-key-value" in content
            assert "OTHER=val" in content  # untouched
            assert "TAVILY_API_KEY=old-key-value" not in content
        finally:
            os.environ.clear()
            os.environ.update(original_environ)

    @pytest.mark.asyncio
    async def test_save_key_missing_params(self, client):
        """PUT /api/settings/key returns 422 for missing params."""
        resp = await client.put("/api/settings/key", json={})
        assert resp.status_code == 422
