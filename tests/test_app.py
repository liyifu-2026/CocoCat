"""Tests for cococat.app — create_app, health, routes, middleware, seeding."""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cococat.app import create_app, _seed_defaults
from cococat.db import Database


class TestCreateApp:
    @pytest.fixture
    def app(self):
        return create_app(":memory:")

    def test_returns_fastapi_instance(self, app):
        assert isinstance(app, FastAPI)
        assert app.title == "CocoCat"
        assert app.state.ctx is not None

    def test_context_has_required_attrs(self, app):
        ctx = app.state.ctx
        for attr in ("db", "bus", "pool", "ws_manager", "config_store", "channel_manager"):
            assert hasattr(ctx, attr), f"ctx missing {attr}"

    def test_routes_registered(self, app):
        assert len(app.routes) >= 8

    def test_middleware_installed(self, app):
        assert app.user_middleware, "No middleware installed"

    def test_health_endpoint(self, app):
        with TestClient(app) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


class TestSeedDefaults:
    def test_seeds_main_when_empty(self):
        db = Database(":memory:")
        db.migrate()
        assert len(db.agents.list_all()) == 0
        with patch("cococat.app._seed_scenes_from_yaml"):
            _seed_defaults(db)
        assert len(db.agents.list_all()) == 1
        agent = db.agents.get("main")
        assert agent is not None

    def test_seed_is_idempotent(self):
        db = Database(":memory:")
        db.migrate()
        with patch("cococat.app._seed_scenes_from_yaml"):
            _seed_defaults(db)
            _seed_defaults(db)
        assert len(db.agents.list_all()) == 1
