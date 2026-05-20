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
        sub_exec = getattr(app.state.ctx, "sub_executor", None)
        if sub_exec:
            worker.set_dag_executor(sub_exec.dispatch)
        worker.set_dag_store(app.state.ctx.dag_store)
        worker.set_ws_manager(app.state.ctx.ws_manager)
        worker.set_sandbox_provider(app.state.ctx.sandbox_provider)
        worker.set_config_store(app.state.ctx.config_store)
        await worker.start()
        app.state.ctx.worker = worker

        cron_worker = CronWorker(sub_executor=sub_exec, cron_dir=str(app.state.ctx.config_store.cron_dir))
        await cron_worker.start()
        app.state.ctx.cron_worker = cron_worker

        import asyncio as _asyncio
        loop = _asyncio.get_running_loop()
        app.state.ctx.channel_manager.auto_reconnect(app.state.ctx, loop)

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
    from cococat.routes.users import router as users_router
    from cococat.routes.pinned import router as pinned_router

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
    app.include_router(users_router)
    app.include_router(pinned_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/auth/login")
    async def login(request: Request):
        from cococat.auth import create_access_token, verify_password, verify_user_password
        from fastapi.responses import JSONResponse
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})
        password = body.get("password", "")
        username = body.get("username", "")

        # Multi-user: check against users table if username provided and table has rows
        db = app.state.ctx.db
        has_users = db._conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0] > 0 if username else False

        if has_users:
            if not verify_user_password(username, password, db):
                return JSONResponse(status_code=401, content={"detail": "Incorrect username or password"})
            token = create_access_token({"sub": username})
        else:
            # Legacy single-password auth (dev mode / pre-migration)
            if not verify_password(password):
                return JSONResponse(status_code=401, content={"detail": "Incorrect password"})
            token = create_access_token({"sub": "admin"})

        return {"access_token": token, "token_type": "bearer"}

    @app.get("/api/auth/status")
    async def auth_status():
        db = app.state.ctx.db
        has_users = db._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0
        return {"has_users": has_users}

    @app.post("/api/auth/init")
    async def init_admin(request: Request):
        """First-run: create initial admin user. Only works when no users exist."""
        from cococat.auth import create_access_token
        from fastapi.responses import JSONResponse
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

        db = app.state.ctx.db
        has_users = db._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0
        if has_users:
            return JSONResponse(status_code=400, content={"detail": "Users already exist"})

        username = (body.get("username", "")).strip()
        password = (body.get("password", ""))
        if not username or len(password) < 4 or not password.strip():
            return JSONResponse(status_code=400, content={"detail": "Username required, password >= 4 chars"})

        import bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db._conn.execute(
            "INSERT INTO users (id, password_hash, display_name) VALUES (?, ?, ?)",
            (username, password_hash, username),
        )
        db._conn.commit()

        import os
        os.makedirs(f"config/users/{username}", exist_ok=True)
        os.makedirs(f"agents/{username}/memory/compiled", exist_ok=True)
        os.makedirs(f"agents/{username}/memory/summaries", exist_ok=True)
        os.makedirs(f"agents/{username}/sessions", exist_ok=True)

        token = create_access_token({"sub": username})
        return {"access_token": token, "token_type": "bearer", "username": username}

    return app


async def get_ctx(request: Request) -> AppContext:
    """FastAPI dependency — returns the typed AppContext."""
    return request.app.state.ctx


def _seed_defaults(db: Database) -> None:
    """Seed default data if tables are empty."""
    db.agents.seed_main()
    _seed_scenes_from_yaml(db)


def _seed_scenes_from_yaml(db: Database) -> None:
    from cococat.scene.config import list_scenes
    existing = {r["id"] for r in db._conn.execute("SELECT id FROM scenes").fetchall()}
    for sc in list_scenes():
        if sc.id in existing:
            continue
        db.scenes.create_full({
            "id": sc.id,
            "name": sc.name or sc.id,
            "description": "",
            "context": sc.context,
            "agent_id": None,
            "status": "running",
            "purpose": "",
            "kbs": sc.kbs,
            "skills": sc.skills,
            "tools": [],
            "channels": sc.channels,
            "llm_config": {},
            "visibility": "private",
        })
