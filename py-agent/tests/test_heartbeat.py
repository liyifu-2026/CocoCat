import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from heartbeat import HeartbeatService
from evaluator import evaluate_response
from providers.base import LLMResponse, ToolCallRequest


# ── _is_deliverable ────────────────────────────────────────────────────

class TestIsDeliverable:
    def test_normal_response_is_deliverable(self):
        assert HeartbeatService._is_deliverable("All tasks completed successfully")

    def test_empty_response_is_deliverable(self):
        assert HeartbeatService._is_deliverable("")

    def test_finalization_fallback_is_blocked(self):
        assert not HeartbeatService._is_deliverable(
            "Sorry, I couldn't produce a final answer"
        )

    def test_leaked_heartbeat_md_is_blocked(self):
        assert not HeartbeatService._is_deliverable(
            "Based on my review of HEARTBEAT.md"
        )

    def test_leaked_decision_logic_is_blocked(self):
        assert not HeartbeatService._is_deliverable(
            "This is a judgment call: valid options are A, B, C"
        )

    def test_leaked_instructions_is_blocked(self):
        assert not HeartbeatService._is_deliverable(
            "I am supposed to review my instructions"
        )

    def test_case_insensitive_matching(self):
        assert not HeartbeatService._is_deliverable("Heartbeat.Md referenced")


# ── evaluate_response ──────────────────────────────────────────────────

class TestEvaluateResponse:
    def _mock_provider(self, should_notify: bool):
        provider = MagicMock()
        provider.chat_with_retry.return_value = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="evaluate_notification",
                    arguments={"should_notify": should_notify, "reason": "test"},
                )
            ],
            finish_reason="tool_calls",
        )
        return provider

    def test_notify_when_llm_says_yes(self):
        result = evaluate_response(
            "New feature deployed",
            "Implement feature X",
            self._mock_provider(True),
            "test-model",
        )
        assert result is True

    def test_suppress_when_llm_says_no(self):
        result = evaluate_response(
            "Everything is normal",
            "Routine check",
            self._mock_provider(False),
            "test-model",
        )
        assert result is False

    def test_fails_open_on_error(self):
        provider = MagicMock()
        provider.chat_with_retry.side_effect = Exception("LLM down")
        result = evaluate_response("test", "test", provider, "test-model")
        assert result is True

    def test_defaults_to_notify_when_no_tool_call(self):
        provider = MagicMock()
        provider.chat_with_retry.return_value = LLMResponse(
            content="No tool call here",
            finish_reason="stop",
        )
        result = evaluate_response("test", "test", provider, "test-model")
        assert result is True


# ── HeartbeatService ───────────────────────────────────────────────────

class TestHeartbeatServiceLifecycle:
    def test_start_stop(self):
        hb = HeartbeatService(agent_id="test_agent")
        hb.start()
        assert hb._running is True
        assert hb._thread is not None
        assert hb._thread.is_alive()
        hb.stop()
        assert hb._running is False

    def test_start_is_idempotent(self):
        hb = HeartbeatService(agent_id="test_agent")
        hb.start()
        thread = hb._thread
        hb.start()  # second start should be no-op
        assert hb._thread is thread
        hb.stop()


class TestHeartbeatReadFile:
    def test_read_existing_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Test content")
            path = f.name
        try:
            hb = HeartbeatService(agent_id="x", heartbeat_file=path)
            content = hb._read_heartbeat_file()
            assert content == "Test content"
        finally:
            os.unlink(path)

    def test_read_missing_file(self):
        hb = HeartbeatService(agent_id="x", heartbeat_file="/nonexistent/file.md")
        assert hb._read_heartbeat_file() is None

    def test_read_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            path = f.name
        try:
            hb = HeartbeatService(agent_id="x", heartbeat_file=path)
            assert hb._read_heartbeat_file() == ""
        finally:
            os.unlink(path)


class TestHeartbeatDecide:
    def _make_mock_provider(self, action: str, tasks: str = ""):
        provider = MagicMock()
        provider.chat_with_retry.return_value = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="heartbeat",
                    arguments={"action": action, "tasks": tasks},
                )
            ],
            finish_reason="tool_calls",
        )
        return provider

    def test_decide_skip(self):
        hb = HeartbeatService(
            agent_id="test_agent",
            provider=self._make_mock_provider("skip"),
            model="test-model",
        )
        import asyncio
        action, tasks = asyncio.run(hb._decide("HEARTBEAT.md content"))
        assert action == "skip"

    def test_decide_run(self):
        hb = HeartbeatService(
            agent_id="test_agent",
            provider=self._make_mock_provider("run", "Check disk space"),
            model="test-model",
        )
        import asyncio
        action, tasks = asyncio.run(hb._decide("HEARTBEAT.md content"))
        assert action == "run"
        assert tasks == "Check disk space"

    def test_decide_no_provider(self):
        hb = HeartbeatService(agent_id="test_agent", provider=None)
        import asyncio
        action, tasks = asyncio.run(hb._decide("content"))
        assert action == "skip"

    def test_decide_provider_error(self):
        provider = MagicMock()
        provider.chat_with_retry.side_effect = Exception("API error")
        hb = HeartbeatService(
            agent_id="test_agent",
            provider=provider,
            model="test-model",
        )
        import asyncio
        action, tasks = asyncio.run(hb._decide("content"))
        assert action == "skip"


class TestHeartbeatMailboxProcessing:
    def test_processes_unread_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                f.write(json.dumps({
                    "from": "admin",
                    "content": "execute task 1",
                    "timestamp": datetime.now().isoformat(),
                    "status": "unread",
                }) + "\n")

            executed = []
            notified = []

            def on_exec(prompt):
                executed.append(prompt)
                return f"done: {prompt}"

            def on_notify(sender, response):
                notified.append((sender, response))

            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                on_execute=on_exec,
                on_notify=on_notify,
            )
            with patch("mailbox._mailbox_dir", return_value=os.path.join(tmpdir, "test_agent")):
                hb._process_mailbox()

            assert len(executed) == 1
            assert executed[0] == "execute task 1"
            assert len(notified) == 1
            assert notified[0][0] == "admin"
            assert "done: execute task 1" in notified[0][1]

    def test_skips_read_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                f.write(json.dumps({
                    "from": "admin",
                    "content": "old message",
                    "timestamp": datetime.now().isoformat(),
                    "status": "read",
                }) + "\n")

            executed = []

            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                on_execute=lambda p: executed.append(p) or "done",
                on_notify=lambda s, r: None,
            )
            with patch("mailbox._mailbox_dir", return_value=os.path.join(tmpdir, "test_agent")):
                hb._process_mailbox()

            assert len(executed) == 0

    def test_skips_empty_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                f.write(json.dumps({
                    "from": "admin",
                    "content": "",
                    "timestamp": datetime.now().isoformat(),
                    "status": "unread",
                }) + "\n")

            executed = []

            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                on_execute=lambda p: executed.append(p) or "",
            )
            with patch("mailbox._mailbox_dir", return_value=os.path.join(tmpdir, "test_agent")):
                hb._process_mailbox()

            assert len(executed) == 0

    def test_suppresses_non_deliverable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                f.write(json.dumps({
                    "from": "admin",
                    "content": "do something",
                    "timestamp": datetime.now().isoformat(),
                    "status": "unread",
                }) + "\n")

            notified = []

            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                on_execute=lambda p: "Sorry, I couldn't produce a final answer",
                on_notify=lambda s, r: notified.append((s, r)),
            )
            with patch("mailbox._mailbox_dir", return_value=os.path.join(tmpdir, "test_agent")):
                hb._process_mailbox()

            assert len(notified) == 0


class TestHeartbeatProcessHeartbeat:
    """Tests the full HEARTBEAT.md pipeline: _process_heartbeat()"""

    def test_full_run_pipeline_notifies(self):
        executed = []
        notified = []

        hb = HeartbeatService(
            agent_id="test_agent",
            model="test-model",
            on_execute=lambda p: executed.append(p) or f"done: {p}",
            on_notify=lambda s, r: notified.append((s, r)),
        )
        with patch.object(hb, "_decide", return_value=("run", "tasks here")):
            import asyncio
            asyncio.run(hb._process_heartbeat("HEARTBEAT.md content"))

        assert len(executed) == 1
        assert len(notified) == 1
        assert "done: tasks here" in notified[0][1]

    def test_skip_does_nothing(self):
        executed = []

        hb = HeartbeatService(
            agent_id="test_agent",
            on_execute=lambda p: executed.append(p) or "",
        )
        with patch.object(hb, "_decide", return_value=("skip", "")):
            import asyncio
            asyncio.run(hb._process_heartbeat("content"))

        assert len(executed) == 0

    def test_no_provider_skips(self):
        executed = []
        hb = HeartbeatService(
            agent_id="test_agent", provider=None,
            on_execute=lambda p: executed.append(p) or "",
        )
        import asyncio
        asyncio.run(hb._process_heartbeat("content"))
        assert len(executed) == 0

    def test_empty_response_suppresses(self):
        notified = []

        hb = HeartbeatService(
            agent_id="test_agent",
            on_execute=lambda p: "",
            on_notify=lambda s, r: notified.append((s, r)),
        )
        with patch.object(hb, "_decide", return_value=("run", "tasks")):
            import asyncio
            asyncio.run(hb._process_heartbeat("content"))

        assert len(notified) == 0

    def test_non_deliverable_suppresses(self):
        notified = []

        hb = HeartbeatService(
            agent_id="test_agent",
            on_execute=lambda p: "couldn't produce a final answer",
            on_notify=lambda s, r: notified.append((s, r)),
        )
        with patch.object(hb, "_decide", return_value=("run", "tasks")):
            import asyncio
            asyncio.run(hb._process_heartbeat("content"))

        assert len(notified) == 0

    def test_evaluate_suppress_no_notify(self):
        notified = []

        hb = HeartbeatService(
            agent_id="test_agent", model="test-model",
            provider=MagicMock(),
            on_execute=lambda p: "routine check ok",
            on_notify=lambda s, r: notified.append((s, r)),
        )
        hb.provider.chat_with_retry.return_value = LLMResponse(
            content=None,
            tool_calls=[ToolCallRequest(
                id="c1", name="evaluate_notification",
                arguments={"should_notify": False, "reason": "routine"},
            )],
            finish_reason="tool_calls",
        )
        with patch.object(hb, "_decide", return_value=("run", "tasks")):
            import asyncio
            asyncio.run(hb._process_heartbeat("content"))

        assert len(notified) == 0


class TestHeartbeatMailboxProcessingExtended:
    def test_marks_message_read_after_processing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                f.write(json.dumps({
                    "from": "admin", "content": "task 1",
                    "timestamp": datetime.now().isoformat(), "status": "unread",
                }) + "\n")

            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                on_execute=lambda p: f"done: {p}",
                on_notify=lambda s, r: None,
            )
            with patch("mailbox._mailbox_dir", return_value=inbox_dir):
                hb._process_mailbox()

            with open(inbox_file) as f:
                msg = json.loads(f.readline())
            assert msg["status"] == "read"

    def test_evaluate_suppress_no_notification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                f.write(json.dumps({
                    "from": "admin", "content": "check status",
                    "timestamp": datetime.now().isoformat(), "status": "unread",
                }) + "\n")

            notified = []
            provider = MagicMock()
            provider.chat_with_retry.return_value = LLMResponse(
                content=None,
                tool_calls=[ToolCallRequest(
                    id="c1", name="evaluate_notification",
                    arguments={"should_notify": False, "reason": "routine"},
                )],
                finish_reason="tool_calls",
            )

            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                provider=provider, model="test-model",
                on_execute=lambda p: "all normal",
                on_notify=lambda s, r: notified.append((s, r)),
            )
            with patch("mailbox._mailbox_dir", return_value=inbox_dir):
                hb._process_mailbox()

            assert len(notified) == 0

    def test_multiple_unread_messages_all_processed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "test_agent")
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_file = os.path.join(inbox_dir, "inbox.jsonl")
            with open(inbox_file, "w") as f:
                for i in range(3):
                    f.write(json.dumps({
                        "from": "admin", "content": f"task {i}",
                        "timestamp": datetime.now().isoformat(), "status": "unread",
                    }) + "\n")

            executed = []
            hb = HeartbeatService(
                agent_id="test_agent",
                mailbox_base=os.path.join(tmpdir, "test_agent"),
                on_execute=lambda p: executed.append(p) or f"done: {p}",
                on_notify=lambda s, r: None,
            )
            with patch("mailbox._mailbox_dir", return_value=inbox_dir):
                hb._process_mailbox()

            assert len(executed) == 3
            assert executed == ["task 0", "task 1", "task 2"]


class TestHeartbeatActivityLog:
    def test_log_activity_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_file = os.path.join(tmpdir, "activity.jsonl")
            hb = HeartbeatService(agent_id="test_agent")
            hb._activity_file = activity_file
            hb._log_activity("heartbeat_tick", detail="decide=skip")

            assert os.path.exists(activity_file)
            with open(activity_file) as f:
                entry = json.loads(f.readline())
            assert entry["type"] == "heartbeat_tick"
            assert entry["agent_id"] == "test_agent"
            assert entry["detail"] == "decide=skip"
            assert "ts" in entry

    def test_log_activity_appends(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_file = os.path.join(tmpdir, "activity.jsonl")
            hb = HeartbeatService(agent_id="test_agent")
            hb._activity_file = activity_file
            hb._log_activity("heartbeat_tick", detail="tick 1")
            hb._log_activity("mailbox_msg", sender="admin", content="hello")

            lines = open(activity_file).read().strip().split("\n")
            assert len(lines) == 2
            assert json.loads(lines[0])["detail"] == "tick 1"
            assert json.loads(lines[1])["sender"] == "admin"

    def test_log_activity_all_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            activity_file = os.path.join(tmpdir, "activity.jsonl")
            hb = HeartbeatService(agent_id="test_agent", agent_name="TestAgent")
            hb._activity_file = activity_file
            hb._log_activity("schedule_task", content="backup db",
                              result="done", task_id=5,
                              detail="status=completed")

            entry = json.loads(open(activity_file).readline())
            assert entry["type"] == "schedule_task"
            assert entry["content"] == "backup db"
            assert entry["result"] == "done"
            assert entry["task_id"] == 5
            assert entry["agent_name"] == "TestAgent"


class TestHeartbeatProcessSchedule:
    def _make_schedule(self, tmpdir, tasks):
        sched_file = os.path.join(tmpdir, "schedule.json")
        with open(sched_file, "w") as f:
            json.dump({"tasks": tasks}, f)
        return sched_file

    def test_processes_pending_task_for_self(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sched_file = self._make_schedule(tmpdir, [
                {"id": 1, "task": "备份数据库", "assigned_to": "employee_a", "status": "pending"},
                {"id": 2, "task": "写测试", "assigned_to": "employee_b", "status": "pending"},
            ])
            executed = []
            hb = HeartbeatService(agent_id="employee_a", on_execute=lambda p: executed.append(p) or "done")
            hb._schedule_file = sched_file
            hb._activity_file = os.path.join(tmpdir, "activity.jsonl")
            hb._process_schedule()

            assert executed == ["备份数据库"]
            data = json.loads(open(sched_file).read())
            assert data["tasks"][0]["status"] == "completed"
            assert data["tasks"][1]["status"] == "pending"

    def test_skips_other_agents_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sched_file = self._make_schedule(tmpdir, [
                {"id": 1, "task": "task for B", "assigned_to": "employee_b", "status": "pending"},
            ])
            executed = []
            hb = HeartbeatService(agent_id="employee_a", on_execute=lambda p: executed.append(p) or "done")
            hb._schedule_file = sched_file
            hb._process_schedule()
            assert len(executed) == 0

    def test_no_schedule_file(self):
        hb = HeartbeatService(agent_id="test_agent")
        hb._schedule_file = "/nonexistent/schedule.json"
        hb._process_schedule()  # should not raise

    def test_records_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sched_file = self._make_schedule(tmpdir, [
                {"id": 1, "task": "do work", "assigned_to": "test_agent", "status": "pending"},
            ])
            hb = HeartbeatService(agent_id="test_agent",
                                   on_execute=lambda p: "completed successfully")
            hb._schedule_file = sched_file
            hb._process_schedule()

            data = json.loads(open(sched_file).read())
            assert data["tasks"][0]["result"] == "completed successfully"

    def test_handles_execution_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sched_file = self._make_schedule(tmpdir, [
                {"id": 1, "task": "risky task", "assigned_to": "test_agent", "status": "pending"},
            ])
            hb = HeartbeatService(agent_id="test_agent",
                                   on_execute=lambda p: (_ for _ in ()).throw(Exception("crash")))
            hb._schedule_file = sched_file
            hb._process_schedule()

            data = json.loads(open(sched_file).read())
            assert data["tasks"][0]["status"] == "failed"
            assert "crash" in data["tasks"][0]["result"]


class TestHeartbeatTriggerNow:
    def test_trigger_with_prompt(self):
        executed = []
        hb = HeartbeatService(
            agent_id="test_agent",
            on_execute=lambda p: executed.append(p) or f"result: {p}",
        )
        result = hb.trigger_now(prompt="direct task")
        assert executed == ["direct task"]
        assert result == "result: direct task"

    def test_trigger_without_prompt_no_file(self):
        hb = HeartbeatService(
            agent_id="test_agent",
            heartbeat_file="/nonexistent/file.md",
        )
        result = hb.trigger_now()
        assert result is None
