"""Tests for SceneConfig, SceneManager, SceneRuntime, AgentHandle."""
import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from scene_config import load_scene_config, list_scenes
from scene_manager import SceneManager, SceneRuntime, SceneState


def test_list_scenes():
    scenes = list_scenes()
    assert "default" in scenes
    assert "development" in scenes


def test_load_default_scene():
    cfg = load_scene_config("default")
    assert cfg is not None
    assert cfg.scene_id == "default"
    assert cfg.name != ""
    assert cfg.context != ""
    assert isinstance(cfg.mounted_kbs, list)
    assert isinstance(cfg.env_skills, list)


def test_load_nonexistent_scene():
    assert load_scene_config("nonexistent_12345") is None


def test_scene_runtime_initial_state():
    from scene_config import load_scene_config
    cfg = load_scene_config("default")
    rt = SceneRuntime(cfg)
    assert rt.state == SceneState.IDLE
    assert rt.agent_id is None


def test_scene_runtime_assign():
    from scene_config import load_scene_config
    cfg = load_scene_config("default")
    rt = SceneRuntime(cfg)
    ok = rt.assign_agent("test_agent")
    assert ok
    assert rt.state == SceneState.ACTIVE
    assert rt.agent_id == "test_agent"


def test_scene_runtime_unassign():
    from scene_config import load_scene_config
    cfg = load_scene_config("default")
    rt = SceneRuntime(cfg)
    rt.assign_agent("test_agent")
    ok = rt.unassign_agent()
    assert ok
    assert rt.state == SceneState.IDLE
    assert rt.agent_id is None


def test_scene_manager_singleton():
    m1 = SceneManager()
    m2 = SceneManager()
    assert m1 is m2


def test_scene_manager_get_or_create():
    mgr = SceneManager()
    rt = mgr.get_or_create("default")
    assert rt is not None
    assert rt.scene_id == "default"


def test_scene_manager_get_or_create_unknown():
    mgr = SceneManager()
    assert mgr.get_or_create("__nonexistent__") is None


def test_scene_manager_assign_unassign():
    mgr = SceneManager()
    ok = mgr.assign_agent("default", "test_agent")
    assert ok
    rt = mgr.get_runtime("default")
    assert rt.state == SceneState.ACTIVE
    ok = mgr.unassign_agent("default")
    assert ok
    assert rt.state == SceneState.IDLE


def test_scene_manager_list_active():
    mgr = SceneManager()
    mgr.assign_agent("development", "test_agent2")
    active = mgr.list_active()
    assert "development" in active
    mgr.unassign_agent("development")
    active = mgr.list_active()
    assert "development" not in active


def test_agent_handle_assign_release():
    from agent_handle import AgentHandle
    h = AgentHandle("test_agent")
    assert h.is_assigned == False
    h.assign_to_scene("test_scene", "context")
    assert h.is_assigned == True
    assert h.scene_id == "test_scene"
    h.release()
    assert h.is_assigned == False
    assert h.scene_id is None


def test_agent_handle_send_message():
    from agent_handle import AgentHandle
    import tempfile, os, json
    h = AgentHandle("test_send_agent")
    h.assign_to_scene("test_scene", "ctx")
    msg_id = h.send_message("weixin", "user123", "hello")
    assert msg_id is not None
    assert "scene:test_scene:weixin:user123" in msg_id
    h.release()


def test_agent_handle_send_message_with_reply_url():
    from agent_handle import AgentHandle
    import os, json
    h = AgentHandle("test_reply_url_agent")
    h.assign_to_scene("test_scene", "ctx")
    h.send_message("weixin", "user123", "hello", reply_url="http://test:8080/reply")
    base = os.path.join(os.path.dirname(__file__), "..", "agents", "mailbox", "test_reply_url_agent")
    inbox_path = os.path.join(base, "inbox.jsonl")
    assert os.path.exists(inbox_path)
    with open(inbox_path, "r") as f:
        line = json.loads(f.readline().strip())
    assert line["reply_url"] == "http://test:8080/reply"
    assert line["channel"] == "weixin"
    assert line["external_user"] == "user123"
    assert line["scene_id"] == "test_scene"
    assert line["target_type"] == "scene"
    assert line["target_id"] == "test_scene"
    h.release()


def test_agent_direct_target_type():
    """_route_to_agent should set target_type='agent' for agent-direct messages."""
    import os, json
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web"))
    from web.entry_manager import _route_to_agent
    _route_to_agent("test_direct_agent", "weixin", "user1", "hello")
    inbox = os.path.join(os.path.dirname(__file__), "..", "agents", "mailbox", "test_direct_agent", "inbox.jsonl")
    assert os.path.exists(inbox)
    with open(inbox, "r") as f:
        line = json.loads(f.readline().strip())
    assert line["target_type"] == "agent"
    assert line["target_id"] == "test_direct_agent"
    assert line["channel"] == "weixin"
    print("agent-direct target_type OK")
