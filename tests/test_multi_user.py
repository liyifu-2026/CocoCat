"""Tests for multi-user authentication."""
import os as _os

_os.environ["JWT_SECRET"] = "multi-user-test-secret-key-32byte!"
_os.environ["WEB_PASSWORD"] = ""

import pytest
import pytest_asyncio
import tempfile
from httpx import ASGITransport, AsyncClient
from cococat.app import create_app


@pytest_asyncio.fixture
async def app_with_users():
    import bcrypt

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    app = create_app(db_path)
    ctx = app.state.ctx

    ctx.db._conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    ctx.db._conn.execute(
        "INSERT INTO users (id, password_hash, display_name) VALUES (?, ?, ?)",
        ("alice", bcrypt.hashpw(b"alice1234", bcrypt.gensalt()).decode(), "Alice"),
    )
    ctx.db._conn.execute(
        "INSERT INTO users (id, password_hash, display_name) VALUES (?, ?, ?)",
        ("bob", bcrypt.hashpw(b"bob1234", bcrypt.gensalt()).decode(), "Bob"),
    )
    ctx.db._conn.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app


class TestMultiUserLogin:
    @pytest.mark.asyncio
    async def test_alice_logs_in_and_gets_jwt_with_her_username(self, app_with_users):
        from cococat.auth import JWT_SECRET
        client, _ = app_with_users
        resp = await client.post("/api/auth/login", json={
            "username": "alice",
            "password": "alice1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        token = data["access_token"]
        import jwt as pyjwt
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "alice"

    @pytest.mark.asyncio
    async def test_bob_logs_in_and_gets_jwt_with_his_username(self, app_with_users):
        from cococat.auth import JWT_SECRET
        client, _ = app_with_users
        resp = await client.post("/api/auth/login", json={
            "username": "bob",
            "password": "bob1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        token = data["access_token"]
        import jwt as pyjwt
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "bob"

    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(self, app_with_users):
        client, _ = app_with_users
        resp = await client.post("/api/auth/login", json={
            "username": "alice",
            "password": "wrong-password",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_401(self, app_with_users):
        client, _ = app_with_users
        resp = await client.post("/api/auth/login", json={
            "username": "ghost",
            "password": "whatever",
        })
        assert resp.status_code == 401


class TestUserManagement:
    @pytest_asyncio.fixture
    async def admin_client(self, app_with_users):
        from cococat.auth import create_access_token
        client, _ = app_with_users
        token = create_access_token({"sub": "alice"})
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    @pytest.mark.asyncio
    async def test_list_users(self, admin_client):
        resp = await admin_client.get("/api/users")
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) >= 2
        usernames = {u["id"] for u in users}
        assert "alice" in usernames
        assert "bob" in usernames

    @pytest.mark.asyncio
    async def test_create_user(self, admin_client):
        resp = await admin_client.post("/api/users", json={
            "username": "charlie",
            "password": "charlie5678",
        })
        assert resp.status_code == 200

        resp = await admin_client.post("/api/auth/login", json={
            "username": "charlie",
            "password": "charlie5678",
        })
        assert resp.status_code == 200

        resp = await admin_client.get("/api/users")
        usernames = {u["id"] for u in resp.json()}
        assert "charlie" in usernames

    @pytest.mark.asyncio
    async def test_delete_user(self, admin_client):
        await admin_client.post("/api/users", json={
            "username": "dave",
            "password": "dave9999",
        })
        resp = await admin_client.delete("/api/users/dave")
        assert resp.status_code == 200

        resp = await admin_client.post("/api/auth/login", json={
            "username": "dave",
            "password": "dave9999",
        })
        assert resp.status_code == 401

        resp = await admin_client.get("/api/users")
        usernames = {u["id"] for u in resp.json()}
        assert "dave" not in usernames

    @pytest.mark.asyncio
    async def test_reset_password(self, admin_client):
        resp = await admin_client.put("/api/users/alice/password", json={
            "password": "newpass5678",
        })
        assert resp.status_code == 200

        resp = await admin_client.post("/api/auth/login", json={
            "username": "alice",
            "password": "alice1234",
        })
        assert resp.status_code == 401

        resp = await admin_client.post("/api/auth/login", json={
            "username": "alice",
            "password": "newpass5678",
        })
        assert resp.status_code == 200


class TestApiKeyIsolation:
    @pytest.mark.asyncio
    async def test_alice_saves_and_reads_her_own_key(self, app_with_users):
        from cococat.auth import create_access_token
        client, _ = app_with_users
        token = create_access_token({"sub": "alice"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.put("/api/providers/key", json={
            "name": "deepseek", "key": "sk-alice-key-123",
        }, headers=headers)
        assert resp.status_code == 200
        resp = await client.get("/api/providers/deepseek/config", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["key"] == "sk-alice-key-123"

    @pytest.mark.asyncio
    async def test_bob_does_not_see_alices_key(self, app_with_users):
        from cococat.auth import create_access_token
        client, _ = app_with_users
        alice_h = {"Authorization": f"Bearer {create_access_token({"sub": "alice"})}"}
        bob_h = {"Authorization": f"Bearer {create_access_token({"sub": "bob"})}"}
        await client.put("/api/providers/key", json={
            "name": "deepseek", "key": "sk-alice-secret-abc",
        }, headers=alice_h)
        resp = await client.get("/api/providers/deepseek/config", headers=bob_h)
        assert resp.status_code == 200
        assert resp.json()["key"] != "sk-alice-secret-abc"

    @pytest.mark.asyncio
    async def test_bob_saves_and_reads_his_own_key(self, app_with_users):
        from cococat.auth import create_access_token
        client, _ = app_with_users
        token = create_access_token({"sub": "bob"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.put("/api/providers/key", json={
            "name": "deepseek", "key": "sk-bob-key-456",
        }, headers=headers)
        assert resp.status_code == 200
        resp = await client.get("/api/providers/deepseek/config", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["key"] == "sk-bob-key-456"


class TestChatIsolation:
    @pytest.mark.asyncio
    async def test_chat_uses_jwt_user_id(self, app_with_users):
        from cococat.auth import create_access_token
        client, _ = app_with_users
        token = create_access_token({"sub": "alice"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/chat", json={
            "content": "Hello from Alice",
        }, headers=headers)
        assert resp.status_code == 200
        resp = await client.get("/api/chat/history", headers=headers)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert any("Hello from Alice" in m.get("content", "") for m in messages)

    @pytest.mark.asyncio
    async def test_bob_history_does_not_show_alice_messages(self, app_with_users):
        from cococat.auth import create_access_token
        client, _ = app_with_users
        alice_h = {"Authorization": f"Bearer {create_access_token({"sub": "alice"})}"}
        bob_h = {"Authorization": f"Bearer {create_access_token({"sub": "bob"})}"}
        await client.post("/api/chat", json={"content": "Secret from Alice"}, headers=alice_h)
        await client.post("/api/chat", json={"content": "Message from Bob"}, headers=bob_h)
        resp = await client.get("/api/chat/history", headers=bob_h)
        messages = resp.json()["messages"]
        contents = " ".join(m.get("content", "") for m in messages)
        assert "Secret from Alice" not in contents
        assert "Message from Bob" in contents


class TestInitWizard:
    @pytest.mark.asyncio
    async def test_init_creates_admin_when_no_users_exist(self):
        """First-run: POST /api/auth/init creates admin user and returns JWT."""
        import tempfile
        import os as _os2, bcrypt as _bcrypt
        _os2.environ["JWT_SECRET"] = "init-test-secret-key-for-32bytes!"
        _os2.environ["WEB_PASSWORD"] = ""

        from cococat.app import create_app
        from cococat.auth import JWT_SECRET
        import jwt as pyjwt

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        app = create_app(db_path)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/auth/init", json={
                "username": "admin",
                "password": "admin1234",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            token = data["access_token"]
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            assert payload["sub"] == "admin"

            # Verify can log in with same credentials
            resp = await c.post("/api/auth/login", json={
                "username": "admin",
                "password": "admin1234",
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_init_rejected_when_users_exist(self, app_with_users):
        """Init fails when users already exist."""
        client, _ = app_with_users
        resp = await client.post("/api/auth/init", json={
            "username": "admin",
            "password": "admin1234",
        })
        assert resp.status_code == 400
