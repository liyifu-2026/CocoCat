# WeChat Channel Implementation Plan

**Goal:** Add WeChat Official Account (公众号) channel to the scene entry system.

**Architecture:** WeChat sends messages via HTTP POST webhook. The channel verifies signatures, parses XML messages with `wechatpy`, routes to scene processing, and returns XML replies.

---

### Task 1: Install dependency + create WeChat channel

**Files:**
- Create: `py-agent/channels/wechat.py`
- Modify: `web/main.py`

- [ ] **Step 1: Install wechatpy**

```powershell
pip install wechatpy
```

- [ ] **Step 2: Create wechat.py**

```python
"""WeChat Official Account channel."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from wechatpy import parse_message
from wechatpy.utils import check_signature
from wechatpy.replies import create_reply


class WeChatChannel(Channel):
    channel_type = "wechat"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.app_id = ""
        self.app_secret = ""

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.token = config.get("token", "")
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        try:
            check_signature(self.token, signature, timestamp, nonce)
            return True
        except Exception:
            return False

    def parse_wechat_message(self, body: bytes) -> ChatMessage | None:
        msg = parse_message(body)
        if msg.type == "text":
            content = msg.content
        elif msg.type == "voice":
            content = msg.recognition or "[voice message]"
        else:
            content = f"[{msg.type} message]"

        return ChatMessage(
            channel_type="wechat",
            scene_id=self.scene_id,
            user_id=msg.source,
            content=content,
            msg_type="text" if msg.type in ("text", "voice") else msg.type,
        )

    def make_reply(self, to_user: str, from_user: str, text: str) -> str:
        from wechatpy.replies import TextReply
        import xml.etree.ElementTree as ET
        reply = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(__import__('time').time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{text}]]></Content>
</xml>"""
        return reply

    def send(self, reply: str, user_id: str):
        pass  # Reply is returned in HTTP response
```

- [ ] **Step 3: Add WeChat webhook endpoint to web/main.py**

Add after the scene_chat endpoint:

```python
@app.post("/api/channels/wechat/{scene_id}")
async def wechat_webhook(scene_id: str, request: Request):
    """WeChat webhook: receive messages from WeChat Official Account."""
    import sys as _sys
    _sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from channels.wechat import WeChatChannel

    # GET request = WeChat server verification
    if request.method == "GET":
        params = dict(request.query_params)
        ch = WeChatChannel()
        ch.start(scene_id, {"token": params.get("token", "")})
        if ch.verify_signature(params.get("signature",""), params.get("timestamp",""), params.get("nonce","")):
            return HTMLResponse(params.get("echostr", ""))
        return HTMLResponse("signature verification failed", status_code=403)

    # POST request = incoming message
    body = await request.body()
    ch = WeChatChannel()
    ch.start(scene_id, {})
    chat_msg = ch.parse_wechat_message(body)
    if not chat_msg:
        return HTMLResponse("success")

    # Store + process via scene router
    from scene_router import store_message, get_history
    import subprocess, json as _json

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
    task = _json.dumps({"jsonrpc": "2.0", "method": "task", "params": {"prompt": prompt}, "id": 1})

    try:
        result = subprocess.run(
            ["python", "-u", agent_script], input=task,
            capture_output=True, text=True, timeout=60,
            env={'OPENAI_API_KEY': api_key, 'OPENAI_BASE_URL': base_url, 'LLM_MODEL': model},
        )
        reply_text = "(processing)"
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    resp = _json.loads(line)
                    ct = resp.get("result", {}).get("content", "")
                    if ct: reply_text = ct; break
                except: pass
    except: reply_text = "System busy, please try again later."

    store_message(scene_id, chat_msg.user_id, {
        "content": reply_text, "direction": "outgoing", "channel_type": "wechat",
    })

    xml_reply = ch.make_reply(chat_msg.user_id, "gh_xxx", reply_text)
    return HTMLResponse(xml_reply, media_type="application/xml")
```

- [ ] **Step 4: Test import**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from channels.wechat import WeChatChannel; ch = WeChatChannel(); print('wechat channel ok')"
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/channels/wechat.py web/main.py
git commit -m "feat: add WeChat channel with webhook endpoint"
```
