"""Centralized filesystem paths — sessions and memory organized by Scene×User."""

import os


def memory_dir(scene_id: str = "default", user_id: str = "local") -> str:
    return f"scenes/{scene_id}/memory/{user_id}"


def session_dir(scene_id: str = "default", user_id: str = "local") -> str:
    return f"scenes/{scene_id}/sessions/{user_id}"


def knowledge_dir() -> str:
    """Central knowledge base directory. Override via COCOCAT_KNOWLEDGE_DIR env var."""
    return os.environ.get("COCOCAT_KNOWLEDGE_DIR", "knowledge")
