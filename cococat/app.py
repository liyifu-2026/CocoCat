"""CocoCat FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from cococat.db import Database
from cococat.core.event_bus import EventBus
from cococat.core.agent_pool import AgentPool
from cococat.routes.ws import WsManager


def create_app(db_path: str = "cococat.db") -> FastAPI:
    """Create the FastAPI application with all routes."""
    db = Database(db_path)
    db.migrate()
    _seed_defaults(db)

    bus = EventBus()
    pool = AgentPool(bus)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from cococat.worker import TaskWorker
        worker = TaskWorker(db, pool, poll_interval=10)
        await worker.start()
        app.state.worker = worker
        yield
        await worker.stop()

    app = FastAPI(title="CocoCat", version="2.0.0", lifespan=lifespan)

    app.state.db = db
    app.state.bus = bus
    app.state.pool = pool
    app.state.ws_manager = WsManager()

    from cococat.routes.agents import router as agents_router
    from cococat.routes.scenes import router as scenes_router
    from cococat.routes.chat import router as chat_router
    from cococat.routes.ws import router as ws_router
    from cococat.routes.knowledge import router as kb_router
    from cococat.routes.skills import router as skills_router
    from cococat.routes.scene_mgmt import router as scene_mgmt_router
    from cococat.routes.providers import router as providers_router
    from cococat.routes.channels import router as channels_router

    app.include_router(agents_router)
    app.include_router(scenes_router)
    app.include_router(chat_router)
    app.include_router(ws_router)
    app.include_router(kb_router)
    app.include_router(skills_router)
    app.include_router(scene_mgmt_router)
    app.include_router(providers_router)
    app.include_router(channels_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


def _seed_defaults(db: Database) -> None:
    """Seed default data if tables are empty."""
    existing = db.execute("SELECT id FROM agents WHERE id = 'main'")
    if not existing:
        db.execute_insert(
            "INSERT INTO agents (id, name, role, model, status) "
            "VALUES ('main', 'Main AI', 'main', 'deepseek-chat', 'running')"
        )
