"""HTTP client for Rust core API communication."""
import httpx
import logging

logger = logging.getLogger("cococat.rust_api")

RUST_API_BASE = "http://localhost:3000/api"


async def chat(content: str, agent_id: str, scene_id: str, user_id: str, timeout: int = 120) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{RUST_API_BASE}/chat",
                json={
                    "content": content,
                    "agent_id": agent_id,
                    "scene_id": scene_id,
                    "user_id": user_id,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as e:
            logger.error(f"Rust API chat error: {e}")
            return {"error": f"Rust core unavailable: {e}"}
        except Exception as e:
            logger.error(f"Rust API chat unexpected error: {e}")
            return {"error": str(e)}


async def health_check() -> dict:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{RUST_API_BASE}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as e:
            return {"status": "unavailable", "error": str(e)}
