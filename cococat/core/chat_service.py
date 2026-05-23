"""ChatService — chat execution logic extracted from route handlers."""

from cococat.context import AppContext
from cococat.db import new_uuid


class ChatService:
    """Encapsulates chat orchestration: tool resolution, sandbox execution, message persistence."""

    def __init__(self, ctx: AppContext):
        self._ctx = ctx

    async def chat(
        self,
        content: str,
        *,
        user_id: str = "local",
        scene_id: str = "default",
        session_id: str | None = None,
        mode: str = "default",
    ) -> dict:
        """Process a chat message: persist user msg, resolve tools, run agent, persist reply."""
        msg_store = self._ctx.db.messages
        msg_uuid = new_uuid()
        msg_store.save(
            msg_uuid=msg_uuid, agent_id="main", user_id=user_id,
            role="user", content=content, scene_id=scene_id,
            channel_type="web",
        )

        from cococat.core.tools import resolve_tools_for_mode, resolve_tavily_key
        sub_executor = self._ctx.sub_executor
        tavily_key = resolve_tavily_key(self._ctx.config_store)

        tools = resolve_tools_for_mode(
            mode,
            sub_agent_executor=sub_executor.dispatch if sub_executor else None,
            tavily_api_key=tavily_key,
            mode_switch_flag=None,
        )

        sandbox_provider = self._ctx.sandbox_provider
        if not sandbox_provider:
            reply = f"[System] ExecutorProvider not available for agent 'main'"
        else:
            try:
                async def on_event(event_type: str, data: dict):
                    await self._ctx.ws_manager.broadcast(event_type, {
                        **(data or {}),
                        "agent_id": "main",
                        "session_id": session_id,
                    })

                reply = await sandbox_provider.run_once(
                    prompt=content,
                    agent_id="main",
                    tools=tools,
                    on_event=on_event,
                    session_id=session_id,
                    mode=mode,
                    scene_id=scene_id,
                    user_id=user_id,
                )
            except Exception as e:
                reply = f"Error: {e}"

        reply_uuid = new_uuid()
        msg_store.save(
            msg_uuid=reply_uuid, agent_id="main", user_id=user_id,
            role="assistant", content=reply, scene_id=scene_id,
        )

        return {"reply": reply, "msg_uuid": reply_uuid}

    async def get_history(self, scene_id: str = "default", limit: int = 50, session_id: str = "") -> dict:
        """Get chat history. If session_id provided, reads from session file via Session class."""
        if session_id:
            from cococat.core.session import Session
            from cococat.core.paths import session_dir
            user = self._ctx.user_id or "local"
            dir_path = session_dir(scene_id, user)
            session = Session(session_id, dir_path)
            all_msgs = await session.read()
            msgs = [{"role": m.get("role", ""), "content": m.get("content", "")} for m in all_msgs]
            return {"messages": msgs}
        return {"messages": self._ctx.db.messages.get_chat_history(scene_id, limit, user_id=self._ctx.user_id)}
