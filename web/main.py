"""CocoCat Web Management Panel — FastAPI backend."""
import json
import os
import sys
import subprocess
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="CocoCat Panel")

BASE_DIR = Path(__file__).resolve().parent.parent


@app.get("/api/agents")
def list_agents():
    config_path = BASE_DIR / "agents" / "config.toml"
    agents = []
    if config_path.exists():
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            agents.append({
                "id": a["id"],
                "name": a["name"],
                "enabled": a.get("enabled", True),
                "scene": a.get("scene", "default"),
            })
    return {"agents": agents}


@app.get("/api/chat")
def read_chat(limit: int = 50):
    chat_path = BASE_DIR / "chat" / "group.jsonl"
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


@app.get("/api/knowledge")
def list_knowledge():
    kb_dir = BASE_DIR / "knowledge"
    kbs = []
    if kb_dir.exists():
        for d in kb_dir.iterdir():
            if d.is_dir():
                kbs.append({"id": d.name, "path": str(d)})
    return kbs


@app.post("/api/scenes/{scene_id}/chat")
async def scene_chat(scene_id: str, request: Request):
    """Entry point for external users to send messages to a scene."""
    body = await request.json()
    user_id = body.get("user_id", "anonymous")
    content = body.get("content", "")

    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    sys.path.insert(0, str(BASE_DIR / "py-agent"))

    from scene_router import store_message, get_history

    store_message(scene_id, user_id, {
        "content": content,
        "direction": "incoming",
        "channel_type": "web_api",
    })

    scene_dir = BASE_DIR / "scenes" / scene_id
    context = ""
    ctx_path = scene_dir / "CONTEXT.md"
    if ctx_path.exists():
        context = ctx_path.read_text(encoding="utf-8")

    history = get_history(scene_id, user_id, limit=10)
    history_text = "\n".join([f"[{h['direction']}] {h['content']}" for h in history])

    agent_script = str(BASE_DIR / "py-agent" / "agent_runtime.py")
    prompt = f"{context}\n\n## Conversation\n{history_text}\n\n[user] {content}\n\nRespond to the user's message concisely."
    task = json.dumps({"jsonrpc": "2.0", "method": "task", "params": {"prompt": prompt}, "id": 1})

    try:
        api_key = os.environ.get('OPENAI_API_KEY', '') or body.get('api_key', '')
        base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.deepseek.com')
        model = os.environ.get('LLM_MODEL', 'deepseek-v4-flash')
        agent_env = dict(os.environ)
        agent_env.update({
            'OPENAI_API_KEY': api_key,
            'OPENAI_BASE_URL': base_url,
            'LLM_MODEL': model,
            'PYTHONPATH': str(BASE_DIR / 'py-agent'),
        })
        result = subprocess.run(
            ["python", "-u", agent_script],
            input=task, capture_output=True, text=True, timeout=60,
            env=agent_env,
        )
        reply_text = "(no response)"
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    resp = json.loads(line)
                    content_text = resp.get("result", {}).get("content", "")
                    if content_text:
                        reply_text = content_text
                        break
                except json.JSONDecodeError:
                    continue
    except subprocess.TimeoutExpired:
        reply_text = "Agent processing timed out."
    except Exception as e:
        reply_text = f"Agent error: {e}"

    store_message(scene_id, user_id, {
        "content": reply_text,
        "direction": "outgoing",
        "channel_type": "web_api",
    })

    return JSONResponse({"reply": reply_text, "user_id": user_id})


@app.get("/api/scenes/{scene_id}/users/{user_id}/history")
def get_user_history(scene_id: str, user_id: str, limit: int = 20):
    """Read a user's conversation history in a scene."""
    sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from scene_router import get_history
    history = get_history(scene_id, user_id, limit=limit)
    return {"history": history}


@app.api_route("/api/channels/wechat/{scene_id}", methods=["GET", "POST"])
async def wechat_webhook(scene_id: str, request: Request):
    """WeChat webhook: receive messages from WeChat Official Account."""
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
    chat_msg = ch.parse_wechat_message(body)
    if not chat_msg:
        return HTMLResponse("success")

    from scene_router import store_message, get_history

    store_message(scene_id, chat_msg.user_id, {
        "content": chat_msg.content, "direction": "incoming", "channel_type": "wechat",
    })

    scene_dir = BASE_DIR / "scenes" / scene_id
    context = ""
    ctx_path = scene_dir / "CONTEXT.md"
    if ctx_path.exists():
        context = ctx_path.read_text(encoding="utf-8")

    history = get_history(scene_id, chat_msg.user_id, limit=10)
    history_text = "\n".join([f"[{h['direction']}] {h['content']}" for h in history])

    api_key = os.environ.get('OPENAI_API_KEY', '')
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.deepseek.com')
    model = os.environ.get('LLM_MODEL', 'deepseek-v4-flash')

    agent_script = str(BASE_DIR / "py-agent" / "agent_runtime.py")
    prompt = f"{context}\n\n## Conversation\n{history_text}\n\n[user] {chat_msg.content}\n\nRespond concisely."
    task = json.dumps({"jsonrpc": "2.0", "method": "task", "params": {"prompt": prompt}, "id": 1})

    try:
        result = subprocess.run(
            ["python", "-u", agent_script], input=task,
            capture_output=True, text=True, timeout=60,
            env={
                'OPENAI_API_KEY': api_key,
                'OPENAI_BASE_URL': base_url,
                'LLM_MODEL': model,
                'PYTHONPATH': str(BASE_DIR / 'py-agent'),
            },
        )
        reply_text = "(processing)"
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    resp = json.loads(line)
                    ct = resp.get("result", {}).get("content", "")
                    if ct:
                        reply_text = ct
                        break
                except json.JSONDecodeError:
                    pass
    except Exception:
        reply_text = "System busy, please try again later."

    store_message(scene_id, chat_msg.user_id, {
        "content": reply_text, "direction": "outgoing", "channel_type": "wechat",
    })

    xml_reply = ch.make_reply(chat_msg.user_id, "gh_xxx", reply_text)
    return HTMLResponse(xml_reply, media_type="application/xml")


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
}
load();
</script>
</body></html>"""
