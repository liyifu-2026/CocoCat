"""Workspace manager — singleton for unified workspace path resolution."""
import os
from pathlib import Path


class WorkspaceManager:
    """Singleton that resolves and manages the agent workspace directory.

    Resolution order: COCOCAT_WORKSPACE env > project root.
    """

    _instance: "WorkspaceManager | None" = None

    def __new__(cls) -> "WorkspaceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._path: Path | None = None
        return cls._instance

    @property
    def path(self) -> Path:
        """Absolute workspace path. Lazily resolved on first access."""
        if self._path is None:
            env_ws = os.environ.get("COCOCAT_WORKSPACE", "")
            if env_ws:
                self._path = Path(env_ws).resolve()
            else:
                self._path = self._resolve_project_root()
        return self._path

    @staticmethod
    def _resolve_project_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def ensure(self) -> None:
        """Create workspace directory if it does not exist."""
        self.path.mkdir(parents=True, exist_ok=True)

    def reload(self) -> None:
        """Clear cached path. Next .path access re-reads COCOCAT_WORKSPACE env."""
        self._path = None

    def validate_path(self, file_path: str) -> tuple:
        """Check if *file_path* lies inside the workspace.

        Returns (True, "") on success or (False, reason) on failure.
        """
        try:
            resolved = Path(file_path).resolve()
            if not str(resolved).startswith(str(self.path)):
                return False, "path outside workspace"
            return True, ""
        except Exception as e:
            return False, f"path validation error: {e}"
