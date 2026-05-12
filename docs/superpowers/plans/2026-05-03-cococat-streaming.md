# Streaming Support Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Scene chat streams agent response tokens via WebSocket in real-time.

---

### Task 1: Add chat_stream() to LLM client

**Files:**
- Modify: `py-agent/llm.py`

- [ ] **Step 1: Add streaming method to OpenAICompatibleProvider**

Add after the existing `chat()` method:

```python
    def chat_stream(self, messages, tools=None, max_tokens=4096, temperature=0.7):
        """Stream tokens from LLM. Yields dicts with 'type': 'delta'|'done'."""
        kwargs = dict(model=self.model, messages=self._sanitize(messages), max_tokens=max_tokens, temperature=temperature, stream=True, stream_options={"include_usage": True})
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = self.client.chat.completions.create(**kwargs)
        content_chunks = []
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_chunks.append(delta.content)
                yield {"type": "delta", "content": delta.content}
        yield {"type": "done", "content": "".join(content_chunks)}
```

- [ ] **Step 2: Add chat_stream to LLMClient**

```python
    def chat_stream(self, messages, tools=None, max_tokens=4096, temperature=0.7):
        for provider in self.providers:
            if hasattr(provider, 'chat_stream'):
                yield from provider.chat_stream(messages, tools=tools, max_tokens=max_tokens, temperature=temperature)
                return
        yield {"type": "done", "content": "(streaming not supported)"}
```

- [ ] **Step 3: Test import**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from llm import LLMClient; c=LLMClient(); print('stream method:', hasattr(c, 'chat_stream'))"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/llm.py
git commit -m "feat: add chat_stream() for token-level streaming"
```

---

### Task 2: Add task_stream method to agent_runtime.py

**Files:**
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Add task_stream handler**

In `handle_request`, add after the `task` handler:

```python
    elif method == "task_stream":
        if agent_loop is None:
            return {"error": "agent loop not initialized"}
        prompt = params.get("prompt", "")
        if not prompt:
            return {"error": "no prompt provided"}
        # Instead of running the full loop, run a simple streaming prompt
        result = agent_loop.llm.chat_stream(
            messages=[
                {"role": "system", "content": agent_loop._build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
        )
        # Stream results to stdout as JSON lines, then return summary
        full_content = ""
        for token in result:
            if token["type"] == "delta":
                full_content += token["content"]
                line = json.dumps({"event": "delta", "content": token["content"]}, ensure_ascii=False)
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            elif token["type"] == "done":
                full_content = token.get("content", full_content)
                line = json.dumps({"event": "done", "content": full_content}, ensure_ascii=False)
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
        return {"content": full_content, "streamed": True}
```

Note: `agent_loop` needs a `_build_system_prompt()` method. Add this to `AgentLoop`:

```python
    def _build_system_prompt(self):
        from context import build_system_prompt, build_tool_descriptions
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        from context import load_agent_memory
        agent_memory = load_agent_memory(self.agent_id)
        return build_system_prompt(
            agent_id=self.agent_id, agent_name=self.agent_name,
            tool_descriptions=tool_desc, workspace=self.workspace,
            scene_name=self.scene_name, scene_context=self.scene_context,
            agent_memory=agent_memory, agent_skills="", env_skills=self.scene_skills,
        )
```

- [ ] **Step 2: Commit**

```bash
git add py-agent/agent_runtime.py py-agent/agent_loop.py
git commit -m "feat: add task_stream method for token-level streaming"
```

---

### Task 3: Stream tokens to WebSocket from scene API

**Files:**
- Modify: `web/main.py`

- [ ] **Step 1: Update scene_chat to use streaming**

Replace the agent subprocess block in `scene_chat` to use `task_stream` instead of `task`, reading stdout line by line and forwarding to WebSocket:

```python
    reply_text = "(processing)"
    try:
        task = json.dumps({"jsonrpc": "2.0", "method": "task_stream", "params": {"prompt": prompt}, "id": 1})
        proc = subprocess.Popen(
            ["python", "-u", agent_script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={'OPENAI_API_KEY': api_key, 'OPENAI_BASE_URL': base_url, 'LLM_MODEL': model},
        )
        proc.stdin.write(task)
        proc.stdin.close()

        full_content = ""
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                if evt.get("event") == "delta":
                    full_content += evt.get("content", "")
                    import asyncio
                    try:
                        asyncio.get_event_loop().create_task(
                            manager.broadcast("stream_delta", {
                                "scene_id": scene_id, "user_id": user_id,
                                "delta": evt.get("content", ""),
                            })
                        )
                    except: pass
                elif evt.get("event") == "done":
                    full_content = evt.get("content", full_content)
            except json.JSONDecodeError:
                continue

        reply_text = full_content or "(no response)"
        proc.wait(timeout=5)
    except Exception as e:
        reply_text = f"Stream error: {e}"
```

Note: The `asyncio.get_event_loop().create_task()` for broadcasting is a quick approach. For production, this should use a proper async queue.

- [ ] **Step 2: Commit**

```bash
git add web/main.py
git commit -m "feat: stream agent tokens to WebSocket from scene API"
```
