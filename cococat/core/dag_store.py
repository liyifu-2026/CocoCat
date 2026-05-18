"""DAG persistence — unified store interface replacing dual db/filesystem paths."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import yaml


class DagStore(ABC):
    """Interface for DAG run persistence.

    Two adapters: FileDagStore (filesystem YAML), SqliteDagStore (SQLite).
    Decision made at construction time — callers never branch on backend.
    """

    @abstractmethod
    def save(self, run_id: str, data: dict) -> None:
        """Save or update a DAG run."""
        ...

    @abstractmethod
    def load(self, run_id: str) -> dict | None:
        """Load a DAG run. Returns None if not found."""
        ...

    @abstractmethod
    def get_pending_task(self) -> dict | None:
        """Find one pending task across all runs.

        Returns dict with keys: run_id, data, task_id, prompt, session_id.
        Returns None if no pending tasks.
        """
        ...

    @abstractmethod
    def list_all(self) -> list[dict]:
        """List all DAG run data dicts (with run_id set in each)."""
        ...

    @abstractmethod
    def delete(self, run_id: str) -> None:
        """Delete a DAG run by ID."""
        ...


class FileDagStore(DagStore):
    """Filesystem-backed DAG store using YAML under {dag_dir}/{run_id}/dag.yaml."""

    def __init__(self, dag_dir: str = "runs"):
        self._dag_dir = dag_dir

    def save(self, run_id: str, data: dict) -> None:
        run_dir = os.path.join(self._dag_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        dag_path = os.path.join(run_dir, "dag.yaml")
        with open(dag_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def load(self, run_id: str) -> dict | None:
        dag_path = os.path.join(self._dag_dir, run_id, "dag.yaml")
        if not os.path.exists(dag_path):
            return None
        try:
            with open(dag_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError:
            return None

    def get_pending_task(self) -> dict | None:
        if not os.path.isdir(self._dag_dir):
            return None
        for run_dir in sorted(os.listdir(self._dag_dir)):
            dag_path = os.path.join(self._dag_dir, run_dir, "dag.yaml")
            if not os.path.exists(dag_path):
                continue
            try:
                with open(dag_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except (yaml.YAMLError, OSError):
                continue
            run_id = data.get("run_id", run_dir)
            for stage in data.get("stages", []):
                for task in stage.get("tasks", []):
                    if task.get("status") == "pending":
                        return {
                            "run_id": run_id,
                            "data": data,
                            "task_id": task.get("id", "?"),
                            "prompt": task.get("prompt", "Execute this task"),
                            "session_id": data.get("session_id"),
                        }
        return None

    def list_all(self) -> list[dict]:
        results = []
        if not os.path.isdir(self._dag_dir):
            return results
        for run_dir in sorted(os.listdir(self._dag_dir)):
            dag_path = os.path.join(self._dag_dir, run_dir, "dag.yaml")
            if not os.path.exists(dag_path):
                continue
            try:
                with open(dag_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                data.setdefault("run_id", run_dir)
                results.append(data)
            except (yaml.YAMLError, OSError):
                continue
        return results

    def delete(self, run_id: str) -> None:
        import shutil
        run_path = os.path.join(self._dag_dir, run_id)
        if os.path.exists(run_path):
            shutil.rmtree(run_path)


class SqliteDagStore(DagStore):
    """SQLite-backed DAG store delegating to DagRunStore."""

    def __init__(self, db):
        self._store = db.dag_runs

    def save(self, run_id: str, data: dict) -> None:
        self._store.save(run_id, data)

    def load(self, run_id: str) -> dict | None:
        return self._store.load(run_id)

    def get_pending_task(self) -> dict | None:
        return self._store.get_pending_task()

    def list_all(self) -> list[dict]:
        return self._store.list_all()

    def delete(self, run_id: str) -> None:
        self._store.delete(run_id)
