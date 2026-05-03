import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from agent_runner import AgentRunner


def test_agent_runner_creation():
    runner = AgentRunner("test_agent", "TestBot", "default")
    assert runner.agent_id == "test_agent"
    assert runner.agent_name == "TestBot"
    assert runner.scene == "default"


def test_agent_runner_ensure_loop():
    runner = AgentRunner("test_agent", "TestBot", "default")
    runner._ensure_loop()
    assert runner._loop is not None
    assert runner._loop.agent_id == "test_agent"


def test_agent_runner_caches_loop():
    runner = AgentRunner("test_agent")
    runner._ensure_loop()
    loop1 = runner._loop
    runner._ensure_loop()
    assert runner._loop is loop1



