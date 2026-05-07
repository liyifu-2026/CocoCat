"""CocoCat Web Management Panel — FastAPI backend proxying through Rust HTTP API."""
import json
import os
import re
import shutil
import sys
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio

# Load .env file BEFORE any module reads os.environ at import time
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from web.auth import verify_jwt_token, verify_api_key

# Python 3.10 compatibility: tomllib is 3.11+
if sys.version_info < (3, 11):
    import tomli as tomllib
    import tomli_w as tomli_w
    sys.modules['tomllib'] = tomllib
    sys.modules['tomli_w'] = tomli_w

app = FastAPI(title="CocoCat Panel")

from web.middleware.cors import setup_cors
setup_cors(app)

from web.middleware.error_handler import setup_error_handlers
setup_error_handlers(app)

from web.middleware.logging import setup_logging
setup_logging(app)

BASE_DIR = Path(__file__).resolve().parent.parent


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: str, data: dict):
        import json
        payload = json.dumps({"event": event, "data": data})
        stale = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Only protect /api/* paths; static files & SPA are public (client-side auth)
    if not path.startswith("/api/"):
        return await call_next(request)

    public_paths = ["/api/auth/login", "/api/auth/verify"]
    if path in public_paths:
        return await call_next(request)

    external_prefixes = ["/api/channels/", "/api/scenes/"]
    is_external = any(path.startswith(p) for p in external_prefixes)

    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    if is_external:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if verify_jwt_token(token):
                return await call_next(request)
        if api_key_header and verify_api_key(api_key_header):
            return await call_next(request)
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    token = auth_header[7:]
    if not verify_jwt_token(token):
        return JSONResponse({"error": "Invalid or expired token"}, status_code=401)
    return await call_next(request)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token", "")
    if not token or not verify_jwt_token(token):
        await ws.close(code=4001)
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.on_event("startup")
async def start_heartbeat():
    from web.auth import validate_config as validate_auth_config
    validate_auth_config()
    try:
        from web.routes.auth import validate_config as validate_web_auth
        validate_web_auth()
    except ImportError:
        pass
    from web.entry_manager import start_all_entries
    start_all_entries()
    from web.services.scheduler import start_scheduler
    start_scheduler()
    asyncio.create_task(_heartbeat_loop())
    asyncio.create_task(_outbox_poll_loop())


async def _heartbeat_loop():
    while True:
        await asyncio.sleep(10)
        await manager.broadcast("heartbeat", {"timestamp": __import__("datetime").datetime.now().isoformat()})


async def _outbox_poll_loop():
    """Poll reply_outbox.jsonl and retry sending undelivered replies."""
    import os, json, asyncio
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "mailbox")
    outbox_path = os.path.join(base, "reply_outbox.jsonl")

    while True:
        await asyncio.sleep(30)
        if not os.path.exists(outbox_path):
            continue
        try:
            with open(outbox_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                continue

            remaining = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    from web.routes.reply_handler import _send_reply
                    from scene_manager import SceneManager
                    mgr = SceneManager()
                    runtime = mgr.get_runtime(entry.get("scene_id", ""))
                    if runtime and runtime.state.name == "ACTIVE":
                        _send_reply(runtime, entry.get("channel", ""), entry.get("user_id", ""), entry.get("content", ""))
                    else:
                        remaining.append(line)
                except Exception:
                    remaining.append(line)

            # Rewrite with only failed entries
            with open(outbox_path, "w", encoding="utf-8") as f:
                for line in remaining:
                    f.write(line + "\n")
        except Exception as e:
            print(f"[OutboxPoll] Error: {e}")


# TODO: Migrate to Rust API — reads chat/general/messages.jsonl directly
@app.get("/api/chat")
def read_chat(limit: int = 50):
    chat_path = BASE_DIR / "chat" / "general" / "messages.jsonl"
    messages = []
    if chat_path.exists():
        with open(chat_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return {"messages": messages[-limit:]}


# TODO: Migrate to Rust API — reads scenes/ directory directly
@app.get("/api/scenes")
def list_scenes():
    scenes_dir = BASE_DIR / "scenes"
    scenes = []
    if scenes_dir.exists():
        for d in scenes_dir.iterdir():
            if d.is_dir():
                scene = {"id": d.name, "context": "", "mounted_kbs": [], "env_skills": [], "roster": []}
                ctx_path = d / "CONTEXT.md"
                if ctx_path.exists():
                    scene["context"] = ctx_path.read_text(encoding="utf-8")[:200]
                mount_path = d / "mounted_kbs.json"
                if mount_path.exists():
                    try:
                        scene["mounted_kbs"] = json.loads(mount_path.read_text(encoding="utf-8")).get("mounted", [])
                    except Exception:
                        pass
                skills_path = d / "skills" / "manifest.json"
                if skills_path.exists():
                    try:
                        scene["env_skills"] = json.loads(skills_path.read_text(encoding="utf-8")).get("env_skills", [])
                    except Exception:
                        pass
                roster_path = d / "roster.json"
                if roster_path.exists():
                    try:
                        scene["roster"] = json.loads(roster_path.read_text(encoding="utf-8")).get("agents", [])
                    except Exception:
                        pass
                scenes.append(scene)
    return {"scenes": scenes}


# TODO: Migrate to Rust API — reads skills/ directory directly
@app.get("/api/skills")
def list_skills():
    skills_dir = BASE_DIR / "skills"
    skills = {"public": [], "private": []}
    if skills_dir.exists():
        for tag in ["public", "private"]:
            tag_dir = skills_dir / tag
            if tag_dir.exists():
                for f in tag_dir.iterdir():
                    if f.suffix == ".md":
                        skills[tag].append({
                            "name": f.stem,
                            "title": f.read_text(encoding="utf-8").split("\n")[0].replace("# Skill: ", ""),
                        })
    return skills


# TODO: Migrate to Rust API — reads knowledge/ directory directly
@app.get("/api/knowledge")
def list_knowledge():
    kb_dir = BASE_DIR / "knowledge"
    kbs = []
    if kb_dir.exists():
        for d in kb_dir.iterdir():
            if d.is_dir():
                kbs.append({"id": d.name, "path": str(d)})
    return kbs


def _read_roster_agents(scene_id: str) -> list[str]:
    """Read agent roster from scene directory."""
    roster_path = BASE_DIR / "scenes" / scene_id / "roster.json"
    if roster_path.exists():
        try:
            roster = json.loads(roster_path.read_text(encoding="utf-8"))
            return roster.get("agents", [])
        except Exception:
            pass
    return []


async def _agent_process_message(scene_id: str, user_id: str, content: str, channel_type: str, api_key: str = ""):
    """Route message to Rust core via POST /api/chat."""
    agents = _read_roster_agents(scene_id)
    if not agents:
        return "No agents available in scene."

    agent_id = agents[0]

    from web.services.agent_executor import execute_agent
    result = await execute_agent(agent_id, scene_id, user_id, content, timeout=60)
    reply_text = result.get("content", "") or result.get("error", "System error.")

    return reply_text


@app.post("/api/scenes/{scene_id}/chat")
async def scene_chat(scene_id: str, request: Request):
    """Entry point for external users to send messages to a scene."""
    body = await request.json()
    user_id = body.get("user_id", "anonymous")
    content = body.get("content", "")

    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    reply_text = await _agent_process_message(scene_id, user_id, content, "web_api", body.get('api_key', ''))
    return JSONResponse({"reply": reply_text, "user_id": user_id})


# TODO: Migrate to Rust API — reads scene_router file-based storage
@app.get("/api/scenes/{scene_id}/users/{user_id}/history")
def get_user_history(scene_id: str, user_id: str, limit: int = 20):
    sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from scene_router import get_history
    history = get_history(scene_id, user_id, limit=limit)
    return {"history": history}


@app.api_route("/api/channels/wechat/{scene_id}", methods=["GET", "POST"])
async def wechat_webhook(scene_id: str, request: Request):
    import sys as _sys
    _sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from channels.wechat import WeChatChannel

    if request.method == "GET":
        params = dict(request.query_params)
        ch = WeChatChannel()
        ch.start(scene_id, {"token": params.get("token", "")})
        if ch.verify_signature(params.get("signature", ""), params.get("timestamp", ""), params.get("nonce", "")):
            return HTMLResponse(params.get("echostr", ""))
        return HTMLResponse("verification failed", status_code=403)

    body = await request.body()
    ch = WeChatChannel()
    ch.start(scene_id, {})
    api_key = ""
    chat_msg = ch.parse_wechat_message(body)
    if not chat_msg:
        return HTMLResponse("success")

    reply_text = await _agent_process_message(scene_id, chat_msg.user_id, chat_msg.content, "wechat", api_key)
    xml_reply = ch.make_reply(chat_msg.user_id, "gh_xxx", reply_text)
    return HTMLResponse(xml_reply, media_type="application/xml")


# TODO: Migrate to Rust API — reads roster.json from filesystem
@app.post("/api/channels/webhook/{target_type}/{target_id}")
async def channel_webhook(target_type: str, target_id: str, request: Request):
    body = await request.json()
    content = body.get("content", "")
    user_id = body.get("user_id", "external")
    channel_type = body.get("channel", "web_api")

    if target_type == "agent":
        from web.entry_manager import _route_to_agent as route
        route(target_id, channel_type, user_id, content)
        return {"status": "routed", "to": target_id}
    elif target_type == "scene":
        import json as _json
        base = Path(__file__).resolve().parent.parent
        roster_path = base / "scenes" / target_id / "roster.json"
        if roster_path.exists():
            try:
                roster = _json.loads(roster_path.read_text(encoding="utf-8"))
                agents = roster.get("agents", [])
                if agents:
                    route(agents[0], channel_type, user_id, content)
                    return {"status": "routed", "to": agents[0], "scene": target_id}
            except Exception:
                pass
        return JSONResponse({"error": "no agent available in scene"}, status_code=404)
    return JSONResponse({"error": "invalid target_type"}, status_code=400)


from web.routes.agents import router as agents_router
app.include_router(agents_router)

from web.routes.knowledge import router as knowledge_router
app.include_router(knowledge_router)

from web.routes.scenes import router as scene_router
app.include_router(scene_router)

from web.routes.entries import router as entries_router
app.include_router(entries_router)

from web.routes.mailbox import router as mailbox_router
app.include_router(mailbox_router)

from web.routes.chat_groups import router as chat_router
app.include_router(chat_router)

from web.routes.status import router as status_router
app.include_router(status_router)

from web.routes.schedule import router as schedule_router
app.include_router(schedule_router)

from web.routes.auth import router as auth_router
app.include_router(auth_router)

from web.routes.collaboration import router as collaboration_router
app.include_router(collaboration_router)

from web.routes.reply_handler import router as reply_router
app.include_router(reply_router)


@app.post("/api/hiring/plan")
async def create_hiring_plan(request: Request):
    """Submit a hiring plan to leader for candidate generation."""
    body = await request.json()
    position = body.get("position", "")
    count = body.get("count", 5)
    if not position:
        return JSONResponse({"error": "position is required"}, status_code=400)
    import httpx
    from web.auth import create_access_token
    token = create_access_token({"sub": "admin"})
    async with httpx.AsyncClient() as client:
        try:
            content = (
                f"请根据招聘需求畅想候选人。"
                f"职位={position}，"
                f"技能={body.get('skills','')}，"
                f"职责={body.get('responsibilities','')}，"
                f"特质={body.get('traits','')}，"
                f"数量={count}"
            )
            resp = await client.post(
                "http://localhost:3000/api/chat",
                json={"content": content, "agent_id": "leader", "scene_id": "default", "user_id": "admin"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            result = resp.json()
            return {"status": "plan_submitted", "task_uuid": result.get("task_uuid", "")}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)


# TODO: Migrate to Rust API — reads hire_requests/ directory directly
@app.get("/api/hiring/pending")
def list_pending_hires():
    pending_dir = BASE_DIR / "agents" / "hire_requests" / "pending"
    if not pending_dir.exists():
        return {"pending": []}
    hires = []
    for f in sorted(pending_dir.iterdir()):
        if f.suffix == ".json" and ".processed" not in f.name:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                hires.append(data)
            except Exception:
                pass
    return {"pending": hires}


_VALID_ID = re.compile(r"^[a-zA-Z0-9_-]+$")

def _validate_hire_id(hire_id: str) -> bool:
    return bool(_VALID_ID.match(hire_id))


def _create_agent_from_hire(hire_data: dict) -> dict:
    """Create agent directory structure and register in config.toml (Python fallback for Rust)."""
    new_id = hire_data.get("id", "")
    new_name = hire_data.get("name", "")
    if not new_id or not new_name:
        return {"error": "missing id or name"}
    config_path = BASE_DIR / "agents" / "config.toml"
    if config_path.exists():
        import tomllib, tomli_w
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        agents = config.get("agents", [])
        if not any(a.get("id") == new_id for a in agents):
            agents.append({
                "id": new_id, "name": new_name,
                "interpreter": "python",
                "script": "py-agent/agent_runtime.py",
                "enabled": True, "scene": "default",
            })
        config["agents"] = agents
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)
    mem_dir = BASE_DIR / "agents" / new_id / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "MEMORY.md").write_text(f"# {new_name} Memory\n\nPersonal memories and learnings.\n", encoding="utf-8")
    (mem_dir / "history.jsonl").write_text("", encoding="utf-8")
    (mem_dir / ".dream_cursor").write_text("0")
    skills_dir = BASE_DIR / "agents" / new_id / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "manifest.json").write_text(json.dumps({"public": [], "private": []}))
    profile_path = BASE_DIR / "agents" / new_id / "profile.json"
    if not profile_path.exists():
        profile = hire_data.get("profile", {})
        if not profile.get("gender"):
            profile["gender"] = "male" if sum(ord(c) for c in new_id) % 2 == 0 else "female"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "created", "agent_id": new_id}


# TODO: Migrate to Rust API — moves files and creates agents directly
@app.post("/api/hiring/pending/{hire_id}/approve")
async def approve_hire(hire_id: str, request: Request):
    if not _validate_hire_id(hire_id):
        return JSONResponse({"error": "invalid hire_id"}, status_code=400)
    pending_dir = BASE_DIR / "agents" / "hire_requests" / "pending"
    approved_dir = BASE_DIR / "agents" / "hire_requests" / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    src = pending_dir / f"{hire_id}.json"
    if not src.exists():
        return JSONResponse({"error": "hire request not found"}, status_code=404)
    dst = approved_dir / f"{hire_id}.json"
    try:
        body = await request.json()
        profile = body.get("profile")
    except Exception:
        profile = None
    if profile:
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            data["profile"] = {**data.get("profile", {}), **profile}
            dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            src.unlink()
        except Exception:
            return JSONResponse({"error": "failed to update profile"}, status_code=500)
    else:
        shutil.move(str(src), str(dst))
    try:
        hire_data = json.loads(dst.read_text(encoding="utf-8"))
        _create_agent_from_hire(hire_data)
    except Exception as e:
        print(f"[hire] Agent creation fallback failed: {e}")
    return {"status": "approved", "hire_id": hire_id}


@app.post("/api/hiring/pending/{hire_id}/reject")
def reject_hire(hire_id: str):
    if not _validate_hire_id(hire_id):
        return JSONResponse({"error": "invalid hire_id"}, status_code=400)
    pending_dir = BASE_DIR / "agents" / "hire_requests" / "pending"
    rejected_dir = BASE_DIR / "agents" / "hire_requests" / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    src = pending_dir / f"{hire_id}.json"
    if not src.exists():
        return JSONResponse({"error": "hire request not found"}, status_code=404)
    dst = rejected_dir / f"{hire_id}.json"
    shutil.move(str(src), str(dst))
    return {"status": "rejected", "hire_id": hire_id}


# Delivery endpoints — proxies to Rust core
@app.get("/api/deliveries")
async def list_deliveries(request: Request):
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.get("http://localhost:3000/api/deliveries", headers=headers, timeout=10)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)

@app.get("/api/deliveries/{delivery_id}")
async def get_delivery(request: Request, delivery_id: str):
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.get(f"http://localhost:3000/api/deliveries/{delivery_id}", headers=headers, timeout=10)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)

@app.post("/api/deliveries/{delivery_id}/archive")
async def archive_delivery(request: Request, delivery_id: str):
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.post(f"http://localhost:3000/api/deliveries/{delivery_id}/archive", headers=headers, timeout=10)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)

@app.post("/api/deliveries/{delivery_id}/read")
async def mark_delivery_read(request: Request, delivery_id: str):
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.post(f"http://localhost:3000/api/deliveries/{delivery_id}/read", headers=headers, timeout=10)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)

@app.get("/api/deliveries/{delivery_id}/files/{filename}")
async def download_delivery_file(request: Request, delivery_id: str, filename: str):
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.get(f"http://localhost:3000/api/deliveries/{delivery_id}/files/{filename}", headers=headers)
            from fastapi.responses import Response
            return Response(content=resp.content, media_type=resp.headers.get("content-type", "application/octet-stream"))
        except httpx.RequestError as e:
            return JSONResponse({"error": str(e)}, status_code=502)

# Serve React web-ui as SPA fallback (must be after all API routes)
from fastapi.staticfiles import StaticFiles
ui_dir = BASE_DIR / "web-ui" / "dist"
if ui_dir.exists():
    app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>CocoCat Panel</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 p-8">
<div class="max-w-6xl mx-auto">
<h1 class="text-2xl font-bold mb-6">CocoCat Management Panel</h1>
<div class="grid grid-cols-2 gap-6">
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Agents</h2>
    <div id="agents" class="text-sm">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Chat Log</h2>
    <div id="chat" class="text-sm max-h-64 overflow-y-auto">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Scenes</h2>
    <div id="scenes" class="text-sm">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Skills</h2>
    <div id="skills" class="text-sm">Loading...</div>
  </div>
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">Pending Hires</h2>
    <div id="pending-hires" class="text-sm">Loading...</div>
  </div>
</div>
</div>
<script>
async function load() {
  const agents = await (await fetch('/api/agents')).json();
  document.getElementById('agents').innerHTML = agents.agents.map(a =>
    `<div class="py-1">&#9632; ${a.name} (${a.id}) <span class="text-gray-400">scene: ${a.scene}</span></div>`
  ).join('');
  const chat = await (await fetch('/api/chat?limit=20')).json();
  document.getElementById('chat').innerHTML = chat.messages.map(m =>
    `<div class="py-1 border-b border-gray-100"><span class="font-medium">[${m.from}]</span> ${(m.content||'').substring(0,100)}</div>`
  ).join('');
  const scenes = await (await fetch('/api/scenes')).json();
  document.getElementById('scenes').innerHTML = scenes.scenes.map(s =>
    `<div class="py-2 border-b border-gray-100"><strong>${s.id}</strong> KB: ${(s.mounted_kbs||[]).join(', ')||'none'} Skills: ${(s.env_skills||[]).join(', ')||'none'}</div>`
  ).join('');
  const skills = await (await fetch('/api/skills')).json();
  document.getElementById('skills').innerHTML =
    '<div class="font-medium">Public:</div> ' + (skills.public.map(s=>s.title).join(', ')||'none') +
    '<br><div class="font-medium mt-2">Private:</div> ' + (skills.private.map(s=>s.title).join(', ')||'none');
  loadPendingHires();
}
load();
async function loadPendingHires() {
  const el = document.getElementById('pending-hires');
  const resp = await fetch('/api/hiring/pending');
  const data = await resp.json();
  if (!data.pending || data.pending.length === 0) {
    el.innerHTML = '<div class="text-gray-400">No pending hires</div>';
    return;
  }
  el.innerHTML = data.pending.map(h => `
    <div class="border-b border-gray-100 py-2">
      <strong>${h.name}</strong> (${h.id})<br>
      <span class="text-gray-500">Role: ${h.profile?.role || '?'}</span><br>
      <span class="text-gray-500">Scene: ${h.scene}</span>
      <div class="mt-2 flex gap-2">
        <button onclick="approveHire('${h.id}')" class="bg-green-500 text-white px-3 py-1 text-xs rounded">Approve</button>
        <button onclick="rejectHire('${h.id}')" class="bg-red-500 text-white px-3 py-1 text-xs rounded">Reject</button>
      </div>
    </div>
  `).join('');
}
async function approveHire(id) {
  await fetch('/api/hiring/pending/' + id + '/approve', {method: 'POST'});
  loadPendingHires();
}
async function rejectHire(id) {
  await fetch('/api/hiring/pending/' + id + '/reject', {method: 'POST'});
  loadPendingHires();
}
loadPendingHires();
</script>
<div class="mt-6 bg-white p-4 rounded shadow">
  <h2 class="font-semibold mb-3">Real-Time Events</h2>
  <div id="ws-log" class="bg-gray-100 p-2 text-xs max-h-40 overflow-y-auto" style="font-family:monospace">Connecting...</div>
</div>
<div class="mt-6 bg-white p-4 rounded shadow">
  <h2 class="font-semibold mb-3">Token Usage</h2>
  <div id="usage" class="text-sm">Loading...</div>
</div>
<script>
fetch('/api/usage?limit=10').then(r=>r.json()).then(d=>{
  let html = d.usage.map(u => `<div class="border-b border-gray-100 py-1">${u.agent_id}: ${u.total_tokens} tokens (${u.iterations} iters)</div>`).join('');
  document.getElementById('usage').innerHTML = html || '(no data)';
});
</script>
<script>
(function(){
  const el = document.getElementById('ws-log');
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { el.innerHTML = '<div class="text-green-600">Connected</div>'; };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    const line = document.createElement('div');
    line.className = 'border-b border-gray-200 py-0.5';
    let text = JSON.stringify(msg.data).substring(0, 120);
    if (msg.event === 'heartbeat') return;
    line.textContent = `${msg.event}: ${text}`;
    el.insertBefore(line, el.firstChild);
    if (el.children.length > 50) el.removeChild(el.lastChild);
  };
  ws.onclose = () => { el.innerHTML = '<div class="text-red-600">Disconnected</div>' + el.innerHTML; };
})();
</script>
</body></html>"""
