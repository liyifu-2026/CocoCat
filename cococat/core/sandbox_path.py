"""Tool sandbox — path validation for scene-bound agents."""

from __future__ import annotations

import os
from pathlib import Path

from cococat.core.types import ToolContext


class PathSandbox:
    """Validates file paths for scene-bound agents.

    When bound to a scene, agents can only access:
    - Workspace directory (read/write/bash)
    - Scene KB directories (read only)
    """

    def __init__(
        self,
        workspace: str | None = None,
        knowledge_dir: str = "knowledge",
        allowed_kbs: list[str] | None = None,
    ):
        if workspace is None:
            from cococat.core.workspace import WorkspaceManager
            workspace = str(WorkspaceManager().path)
        self._workspace = os.path.abspath(workspace)
        self._knowledge_dir = os.path.abspath(knowledge_dir)
        self._allowed_kbs = allowed_kbs or []

    def is_allowed_read(self, path: str) -> bool:
        """Check if a file path can be read."""
        abs_path = os.path.abspath(path)

        # Workspace is always allowed
        if abs_path.startswith(self._workspace):
            return True

        # KB directories are allowed
        for kb in self._allowed_kbs:
            kb_path = os.path.join(self._knowledge_dir, kb)
            if abs_path.startswith(os.path.abspath(kb_path)):
                return True

        return False

    def is_allowed_write(self, path: str) -> bool:
        """Check if a file path can be written to. Only workspace allowed."""
        abs_path = os.path.abspath(path)
        return abs_path.startswith(self._workspace)

    @staticmethod
    def is_safe_path(path: str) -> bool:
        """Reject path traversal attempts."""
        if ".." in Path(path).parts:
            return False
        if os.path.isabs(path) and not path.startswith(("/tmp", "/home", "/workspace")):
            return False
        return True


def wrap_tool_with_sandbox(tool_def, sandbox: PathSandbox):
    """Wrap a tool's execute function with sandbox validation.

    Uses tool.sandbox_operation to determine the check type
    instead of hardcoded name sets: "read", "write", or "exec".
    """
    original = tool_def["execute"]
    op = getattr(tool_def, "sandbox_operation", "")

    def sandboxed(params: dict, context: ToolContext):
        path = params.get("path") or params.get("file_path") or ""

        if path and not PathSandbox.is_safe_path(path):
            return f"Error: path traversal detected for '{path}'"

        if op == "read" and path:
            if not sandbox.is_allowed_read(path):
                return f"Error: access denied. '{path}' is outside allowed directories."

        if op == "write" and path:
            if not sandbox.is_allowed_write(path):
                return f"Error: write access denied for '{path}'"

        if op == "exec" and path:
            if not sandbox.is_allowed_write(path):
                return f"Error: exec access denied for '{path}'"

        return original(params, context)

    return {**tool_def, "execute": sandboxed}
