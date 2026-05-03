"""Tests for plugin manager."""
import sys, os, json, tempfile, pytest
sys.path.insert(0, "py-agent")

from plugin_manager import discover_plugins, install_plugin, uninstall_plugin, list_plugins
from plugin_hooks import HookRegistry


def test_hook_registry():
    reg = HookRegistry()
    calls = []

    def pre(tool, args, cfg):
        calls.append(("pre", tool))
        return {"action": "continue", "args": args}

    def post(tool, args, result, cfg):
        calls.append(("post", tool))
        return {"action": "continue", "result": result}

    reg.register("pre_tool_call", pre)
    reg.register("post_tool_call", post)

    allowed, reason, args = reg.run_pre_tool_call("test_tool", {"x": 1})
    assert allowed
    assert args == {"x": 1}

    result = reg.run_post_tool_call("test_tool", {"x": 1}, "done")
    assert result == "done"
    assert calls == [("pre", "test_tool"), ("post", "test_tool")]


def test_hook_deny():
    reg = HookRegistry()

    def deny_hook(tool, args, cfg):
        return {"action": "deny", "reason": "not allowed"}

    reg.register("pre_tool_call", deny_hook)
    allowed, reason, args = reg.run_pre_tool_call("test_tool", {})
    assert not allowed
    assert "not allowed" in reason


def test_discover_empty():
    plugins = discover_plugins()
    assert isinstance(plugins, dict)


def test_install_uninstall():
    with tempfile.TemporaryDirectory() as tmp:
        # Create a minimal plugin
        plugin_dir = os.path.join(tmp, "test-plugin")
        os.makedirs(plugin_dir)
        manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "Test",
            "tools": [],
        }
        with open(os.path.join(plugin_dir, "plugin.json"), "w") as f:
            json.dump(manifest, f)

        # Install from local path
        result = install_plugin(plugin_dir, "test-plugin")
        assert "successfully" in result

        plugins = discover_plugins()
        assert "test-plugin" in plugins

        result = uninstall_plugin("test-plugin")
        assert "successfully" in result
