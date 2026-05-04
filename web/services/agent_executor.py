"""Agent execution via Rust core API — replaces direct subprocess spawning."""
from web.services.api_client import chat as rust_chat


async def execute_agent(agent_id: str, scene_id: str, user_id: str, content: str, timeout: int = 120) -> dict:
    result = await rust_chat(content, agent_id, scene_id, user_id, timeout=timeout)
    if "error" in result:
        return {"error": result["error"]}
    reply = result.get("reply", result.get("content", ""))
    return {"content": reply}
