"""Task worker — picks up pending KB tasks and DAG tasks, processes them."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Callable, Awaitable

if TYPE_CHECKING:
    from cococat.db import Database
    from cococat.core.agent_pool import AgentPool
    from cococat.core.dag_store import DagStore

logger = logging.getLogger("cococat.worker")


class CronJob:
    """A single cron job with last-run tracking."""

    def __init__(self, agent_id: str, name: str, schedule: str):
        self.agent_id = agent_id
        self.name = name
        self.schedule = schedule
        self._last_run: float = 0
        self._interval = self._parse_schedule(schedule)

    @staticmethod
    def _parse_schedule(schedule: str) -> float:
        mapping = {
            "@hourly": 3600,
            "@daily": 86400,
            "@weekly": 604800,
        }
        if schedule in mapping:
            return mapping[schedule]
        try:
            return float(schedule)
        except ValueError:
            return 86400

    def is_due(self) -> bool:
        now = time.time()
        if now - self._last_run >= self._interval:
            return True
        return False

    def mark_run(self) -> None:
        self._last_run = time.time()


class CronTaskRunner:
    """Checks registered cron jobs and fires handlers when due."""

    def __init__(self):
        self._jobs: list[CronJob] = []
        self._handler: Callable[[str, str], Awaitable[None]] | None = None

    def register(self, agent_id: str, name: str, schedule: str) -> None:
        self._jobs.append(CronJob(agent_id, name, schedule))

    def set_handler(self, handler: Callable[[str, str], Awaitable[None]]) -> None:
        self._handler = handler

    def tick(self) -> list[CronJob]:
        """Check all jobs, return list of due jobs."""
        due = [j for j in self._jobs if j.is_due()]
        for job in due:
            job.mark_run()
        return due

    def get_jobs(self) -> list[CronJob]:
        return list(self._jobs)


class TaskWorker:
    """Background worker that processes pending KB and DAG tasks.
    
    KB tasks: from tasks table (source='kb')
    DAG tasks: from dag.yaml files (status='pending')
    """

    def __init__(self, db: Database, pool: AgentPool, poll_interval: float = 5.0):
        self._db = db
        self._pool = pool
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._dag_executor = None
        self._dag_store: DagStore | None = None
        self._ws_manager = None
        self._dag_notify = False

    def set_dag_executor(self, executor):
        """Set the executor for DAG task processing."""
        self._dag_executor = executor

    def set_dag_store(self, dag_store: DagStore):
        """Set the DagStore for DAG persistence."""
        self._dag_store = dag_store

    def set_ws_manager(self, ws_manager):
        """Set WebSocket manager for DAG completion notifications."""
        self._ws_manager = ws_manager

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("TaskWorker started (poll every %.0fs)", self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("TaskWorker stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._process_kb()
                await self._process_dag()
                await self._process_cron()
            except Exception:
                logger.exception("TaskWorker error")
            await asyncio.sleep(self._poll_interval)

    async def _process_dag(self) -> None:
        """Process one pending DAG task. On run completion, notify via WS."""
        if not self._dag_executor or not self._dag_store:
            return
        from cococat.core.tools.dag import _execute_pending_dag_task
        try:
            count = await _execute_pending_dag_task(self._dag_store, self._dag_executor)
            if count:
                logger.info("TaskWorker: executed %d DAG task(s)", count)
                await self._check_run_completion()
        except Exception:
            logger.exception("TaskWorker: DAG task execution failed")

    async def _check_run_completion(self) -> None:
        """Check if any DAG run is fully complete and notify via WS."""
        if not self._ws_manager or not self._dag_store:
            return
        for data in self._dag_store.list_all():
            if data.get("status") == "done":
                continue

            all_tasks = []
            all_done = True
            for stage in data.get("stages", []):
                for task in stage.get("tasks", []):
                    all_tasks.append(task)
                    if task.get("status") != "done":
                        all_done = False

            if all_done and all_tasks:
                data["status"] = "done"
                run_id = data.get("run_id", "?")
                self._dag_store.save(run_id, data)
                session_id = data.get("session_id")
                summary = f"[DAG] 任务全部完成! {run_id[:8]} — {len(all_tasks)} 个任务已完成。"
                await self._ws_manager.broadcast("dag.completed", {
                    "run_id": run_id,
                    "session_id": session_id,
                    "summary": summary,
                    "task_count": len(all_tasks),
                })
                logger.info("TaskWorker: DAG run %s completed, notified session %s", run_id[:8], session_id)

    async def _process_kb(self) -> None:
        """Claim and process one pending KB task."""
        row = self._db.tasks.claim_pending_kb()
        if not row:
            return

        task_uuid = row["task_uuid"]
        target_agent = row["target_agent"]

        import json
        try:
            params = json.loads(row["params"])
        except json.JSONDecodeError:
            params = {}

        agent = self._pool.get_agent(target_agent)
        if not agent:
            self._db.tasks.fail(task_uuid, f"Agent '{target_agent}' not found")
            return

        kb_name = params.get("kb_name", "unknown")
        filename = params.get("filename", "unknown")

        logger.info("Processing KB task %s: %s/%s", task_uuid, kb_name, filename)

        try:
            from cococat.ingest.ingest import IngestPipeline
            kb_dir = f"knowledge/{kb_name}"
            pipeline = IngestPipeline(agent._llm, kb_dir)
            ingest_result = await pipeline.ingest(filename, kb_name=kb_name)

            if ingest_result.skipped:
                summary = f"Skipped (cache hit): {filename}"
            else:
                summary = f"Ingested {filename} -> {len(ingest_result.written_files)} wiki pages"

            self._db.tasks.complete(task_uuid, summary)
        except Exception as e:
            self._db.tasks.fail(task_uuid, str(e)[:500])

    async def _process_cron(self) -> None:
        """Fire due cron jobs."""
        cron_runner = getattr(self, '_cron_runner', None)
        if not cron_runner:
            return
        due = cron_runner.tick()
        handler = getattr(cron_runner, '_handler', None)
        if not handler:
            return
        for job in due:
            try:
                await handler(job.agent_id, job.name)
            except Exception:
                logger.exception("Cron job %s/%s failed", job.agent_id, job.name)
