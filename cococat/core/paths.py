"""Centralized filesystem paths — sessions and memory organized by Scene×User."""


def memory_dir(scene_id: str = "default", user_id: str = "local") -> str:
    return f"scenes/{scene_id}/memory/{user_id}"


def session_dir(scene_id: str = "default", user_id: str = "local") -> str:
    return f"scenes/{scene_id}/sessions/{user_id}"
