"""CocoCat FastAPI application."""
from fastapi import FastAPI
from cococat.db import Database
from cococat.core.event_bus import EventBus
from cococat.core.agent_pool import AgentPool


def create_app(db_path: str = "cococat.db") -> FastAPI:
    """Create the FastAPI application with all routes."""
    app = FastAPI(title="CocoCat", version="2.0.0")

    db = Database(db_path)
    db.migrate()

    bus = EventBus()
    pool = AgentPool(bus)

    app.state.db = db
    app.state.bus = bus
    app.state.pool = pool

    from cococat.routes.agents import router as agents_router
    from cococat.routes.scenes import router as scenes_router
    from cococat.routes.chat import router as chat_router

    app.include_router(agents_router)
    app.include_router(scenes_router)
    app.include_router(chat_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app
