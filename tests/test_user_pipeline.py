import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from agent_loop import AgentLoop


def test_agent_loop_accepts_user_id():
    loop = AgentLoop(agent_id="test_agent", user_id="test_user")
    assert loop.user_id == "test_user"


def test_agent_loop_default_user_id():
    loop = AgentLoop(agent_id="test_agent")
    assert loop.user_id == ""


