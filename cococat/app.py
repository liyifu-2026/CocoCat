"""CocoCat FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from cococat.db import Database
from cococat.core.event_bus import EventBus
from cococat.core.agent_pool import AgentPool
from cococat.routes.ws import WsManager
from cococat.context import AppContext
from cococat.auth import auth_middleware


def create_app(db_path: str = "cococat.db") -> FastAPI:
    """Create the FastAPI application with all routes."""
    db = Database(db_path)
    db.migrate()
    _seed_defaults(db)

    bus = EventBus()
    pool = AgentPool(bus)

    ctx = AppContext(db=db, bus=bus, pool=pool, ws_manager=WsManager())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from cococat.worker import TaskWorker
        from cococat.core.cron_worker import CronWorker

        worker = TaskWorker(db, pool, poll_interval=10)
        sub_exec = getattr(app.state.ctx, "sub_executor", None)
        if sub_exec:
            worker.set_dag_executor(sub_exec.dispatch)
        worker.set_dag_store(app.state.ctx.dag_store)
        worker.set_ws_manager(app.state.ctx.ws_manager)
        worker.set_sandbox_provider(app.state.ctx.sandbox_provider)
        await worker.start()
        app.state.ctx.worker = worker

        cron_worker = CronWorker(pool, sub_executor=sub_exec)
        await cron_worker.start()
        app.state.ctx.cron_worker = cron_worker

        yield

        await worker.stop()
        await cron_worker.stop()

    app = FastAPI(title="CocoCat", version="2.0.0", lifespan=lifespan)

    app.state.ctx = ctx
    app.middleware("http")(auth_middleware)

    from cococat.routes.agents import router as agents_router
    from cococat.routes.scenes import router as scenes_router
    from cococat.routes.chat import router as chat_router
    from cococat.routes.ws import router as ws_router
    from cococat.routes.knowledge import router as kb_router
    from cococat.routes.skills import router as skills_router
    from cococat.routes.scene_mgmt import router as scene_mgmt_router
    from cococat.routes.providers import router as providers_router
    from cococat.routes.channels import router as channels_router
    from cococat.routes.cron import router as cron_router
    from cococat.routes.dag import router as dag_router
    from cococat.routes.settings import router as settings_router

    app.include_router(agents_router)
    app.include_router(scenes_router)
    app.include_router(chat_router)
    app.include_router(ws_router)
    app.include_router(kb_router)
    app.include_router(skills_router)
    app.include_router(scene_mgmt_router)
    app.include_router(providers_router)
    app.include_router(channels_router)
    app.include_router(dag_router)
    app.include_router(cron_router)
    app.include_router(settings_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/auth/login")
    async def login(request: Request):
        from cococat.auth import create_access_token, verify_password
        try:
            body = await request.json()
        except Exception:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})
        if not verify_password(body.get("password", "")):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Incorrect password"})
        token = create_access_token({"sub": "admin"})
        return {"access_token": token, "token_type": "bearer"}

    return app


async def get_ctx(request: Request) -> AppContext:
    """FastAPI dependency — returns the typed AppContext."""
    return request.app.state.ctx


def _seed_defaults(db: Database) -> None:
    """Seed default data if tables are empty."""
    db.agents.seed_main()
