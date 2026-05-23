"""CocoCat FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from cococat.db import Database
from cococat.core.event_bus import EventBus
from cococat.routes.ws import WsManager
from cococat.context import AppContext
from cococat.auth import auth_middleware
from cococat.config_store import ConfigStore
from cococat.core.channel_manager import ChannelManager
from cococat.core.auth_service import AuthService


def create_app(db_path: str = "cococat.db") -> FastAPI:
    """Create the FastAPI application with all routes."""
    db = Database(db_path)
    db.migrate()
    _seed_defaults(db)

    bus = EventBus()

    ctx = AppContext(
        db=db, bus=bus, ws_manager=WsManager(),
        config_store=ConfigStore(),
        channel_manager=ChannelManager(),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from cococat.worker import TaskWorker
        from cococat.core.cron_worker import CronWorker

        worker = TaskWorker(db, poll_interval=10)
        worker.set_ws_manager(app.state.ctx.ws_manager)
        await worker.start()
        app.state.ctx.worker = worker

        cron_worker = CronWorker(
            sub_executor=app.state.ctx.sub_executor,
            cron_dir=str(app.state.ctx.config_store.cron_dir),
        )
        await cron_worker.start()
        app.state.ctx.cron_worker = cron_worker

        await app.state.ctx.channel_manager.auto_reconnect(app.state.ctx)

        yield

        await worker.stop()
        await cron_worker.stop()

    app = FastAPI(title="CocoCat", version="2.0.0", lifespan=lifespan)

    app.state.ctx = ctx
    app.middleware("http")(auth_middleware)

    from cococat.routes.scenes import router as scenes_router
    from cococat.routes.chat import router as chat_router
    from cococat.routes.ws import router as ws_router
    from cococat.routes.knowledge import router as kb_router
    from cococat.routes.skills import router as skills_router
    from cococat.routes.scene_mgmt import router as scene_mgmt_router
    from cococat.routes.providers import router as providers_router
    from cococat.routes.channels import router as channels_router
    from cococat.routes.cron import router as cron_router
    from cococat.routes.settings import router as settings_router
    from cococat.routes.users import router as users_router
    from cococat.routes.pinned import router as pinned_router
    from cococat.routes.user_config import router as user_config_router

    app.include_router(scenes_router)
    app.include_router(chat_router)
    app.include_router(ws_router)
    app.include_router(kb_router)
    app.include_router(skills_router)
    app.include_router(scene_mgmt_router)
    app.include_router(providers_router)
    app.include_router(channels_router)
    app.include_router(cron_router)
    app.include_router(settings_router)
    app.include_router(users_router)
    app.include_router(pinned_router)
    app.include_router(user_config_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/auth/login")
    async def login(request: Request):
        from fastapi.responses import JSONResponse
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})
        username = body.get("username", "")
        password = body.get("password", "")

        auth = AuthService(app.state.ctx.db)
        token, error = auth.authenticate(username, password)
        if error:
            return JSONResponse(status_code=401, content={"detail": error})

        return {"access_token": token, "token_type": "bearer"}

    @app.get("/api/auth/status")
    async def auth_status():
        auth = AuthService(app.state.ctx.db)
        return {"has_users": auth.has_users()}

    @app.post("/api/auth/init")
    async def init_admin(request: Request):
        from fastapi.responses import JSONResponse
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

        username = (body.get("username", "")).strip()
        password = (body.get("password", ""))

        auth = AuthService(app.state.ctx.db)
        token, error = auth.initialize(username, password)
        if error:
            return JSONResponse(status_code=400, content={"detail": error})

        return {"access_token": token, "token_type": "bearer", "username": username}

    return app


async def get_ctx(request: Request) -> AppContext:
    """FastAPI dependency — returns the typed AppContext."""
    return request.app.state.ctx


def _seed_defaults(db: Database) -> None:
    """Seed default data if tables are empty."""
    _seed_scenes_from_yaml(db)


def _seed_scenes_from_yaml(db: Database) -> None:
    from cococat.scene.config import list_scenes
    existing = {r["id"] for r in db.query("SELECT id FROM scenes")}
    for sc in list_scenes():
        if sc.id in existing:
            continue
        db.scenes.create_full({
            "id": sc.id,
            "name": sc.name or sc.id,
            "description": "",
            "context": sc.context,
            "status": "running",
            "purpose": "",
            "kbs": sc.kbs,
            "skills": sc.skills,
            "tools": [],
            "channels": sc.channels,
            "llm_config": {},
            "visibility": "private",
        })
