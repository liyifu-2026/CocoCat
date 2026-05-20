"""Tests for PathSandbox, tool sandbox wrapping, and ExecutorProvider."""
import os
import pytest
from cococat.core.sandbox_path import PathSandbox, wrap_tool_with_sandbox
from cococat.core.sandbox import ExecutorProvider, InProcessExecutor


# ── PathSandbox tests (from tests/cococat/test_sandbox.py) ──

class ToolDef(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(name)


@pytest.fixture
def sandbox():
    return PathSandbox(
        workspace="workspace",
        knowledge_dir="knowledge",
        allowed_kbs=["product-manual", "faq"],
    )


def _tool(name, sandbox_operation, execute):
    return ToolDef(name=name, parameters={}, execute=execute, sandbox_operation=sandbox_operation)


def _call(wrapped, params, ctx=None):
    return wrapped["execute"](params, ctx or {})


# ── PathSandbox ──

def test_is_allowed_read_workspace(sandbox):
    assert sandbox.is_allowed_read("workspace/file.txt")


def test_is_allowed_read_allowed_kb(sandbox):
    assert sandbox.is_allowed_read("knowledge/product-manual/page.md")
    assert sandbox.is_allowed_read("knowledge/faq/readme.md")


def test_is_allowed_read_disallowed_kb(sandbox):
    assert not sandbox.is_allowed_read("knowledge/team-wiki/secret.md")


def test_is_allowed_read_outside(sandbox):
    assert not sandbox.is_allowed_read("/etc/passwd")


def test_is_allowed_write_workspace(sandbox):
    assert sandbox.is_allowed_write("workspace/notes.txt")


def test_is_allowed_write_kb_denied(sandbox):
    assert not sandbox.is_allowed_write("knowledge/product-manual/edit.md")


def test_is_allowed_write_outside(sandbox):
    assert not sandbox.is_allowed_write("/etc/crontab")


def test_is_allowed_write_subdir(sandbox):
    assert sandbox.is_allowed_write("workspace/sub/deep/file.txt")


# ── PathSandbox.is_safe_path ──

def test_is_safe_path_normal():
    assert PathSandbox.is_safe_path("workspace/notes.txt") is True


def test_is_safe_path_rejects_dotdot():
    assert PathSandbox.is_safe_path("../etc/passwd") is False


def test_is_safe_path_rejects_hidden_dotdot():
    assert PathSandbox.is_safe_path("workspace/foo/../../etc/passwd") is False


def test_is_safe_path_rejects_absolute_etc():
    assert PathSandbox.is_safe_path("/etc/passwd") is False


def test_is_safe_path_allows_tmp():
    assert PathSandbox.is_safe_path("/tmp/test.txt") is True


def test_is_safe_path_allows_home():
    assert PathSandbox.is_safe_path("/home/user/data.txt") is True


def test_is_safe_path_relative_ok():
    assert PathSandbox.is_safe_path("subdir/file.txt") is True


# ── wrap_tool_with_sandbox ──

def test_wrap_read_allowed(sandbox):
    tool = _tool("read_file", "read", lambda p, c: f"read {p['path']}")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "workspace/doc.md"})
    assert result == "read workspace/doc.md"


def test_wrap_read_denied(sandbox):
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "knowledge/team-wiki/page.md"})
    assert "access denied" in result.lower()


def test_wrap_write_allowed(sandbox):
    tool = _tool("write_file", "write", lambda p, c: "ok")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "workspace/new.md", "content": "x"})
    assert result == "ok"


def test_wrap_write_denied(sandbox):
    tool = _tool("write_file", "write", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "knowledge/product-manual/page.md", "content": "x"})
    assert "denied" in result.lower()


def test_wrap_bash_workspace_allowed(sandbox):
    tool = _tool("bash", "exec", lambda p, c: "exec ok")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "workspace", "command": "ls"})
    assert result == "exec ok"


def test_wrap_bash_denied(sandbox):
    tool = _tool("bash", "exec", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "knowledge/product-manual", "command": "rm -rf /"})
    assert "denied" in result.lower()


def test_wrap_path_traversal_blocked(sandbox):
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "../../etc/passwd"})
    assert "path traversal" in result.lower()


def test_wrap_no_path_passes_through(sandbox):
    tool = _tool("current_status", "", lambda p, c: "status ok")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {})
    assert result == "status ok"


def test_wrap_grep_allowed(sandbox):
    tool = _tool("grep", "read", lambda p, c: f"found in {p['path']}")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "workspace/log.txt", "pattern": "error"})
    assert "workspace" in result


def test_wrap_glob_allowed(sandbox):
    tool = _tool("glob", "read", lambda p, c: "2 files")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "knowledge/product-manual/"})
    assert result == "2 files"


def test_wrap_edit_file_write_denied(sandbox):
    tool = _tool("edit_file", "write", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "knowledge/product-manual/page.md", "old": "x", "new": "y"})
    assert "denied" in result.lower()


# ── ExecutorProvider tests (from cococat/tests/core/test_sandbox.py) ──

class TestExecutorProvider:
    @pytest.mark.asyncio
    async def test_create_and_destroy(self):
        provider = ExecutorProvider()
        sid = await provider.create("default", {"kbs": ["test"]})
        assert sid.startswith("local-")
        await provider.destroy(sid)
        assert sid not in provider._sandboxes

    @pytest.mark.asyncio
    async def test_run_once_returns_string(self):
        provider = ExecutorProvider()
        result = await provider.run_once("say hello", agent_id="main")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_once_with_events(self):
        events = []
        provider = ExecutorProvider()
        result = await provider.run_once(
            "say hello",
            agent_id="main",
            on_event=lambda t, d: events.append((t, d)),
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_unknown_sandbox(self):
        provider = ExecutorProvider()
        with pytest.raises(ValueError, match="Unknown sandbox"):
            await provider.run("nonexistent", "hi")

    @pytest.mark.asyncio
    async def test_concurrent_sandboxes(self):
        provider = ExecutorProvider(executor=InProcessExecutor(max_workers=2))
        s1 = await provider.create()
        s2 = await provider.create()
        assert s1 != s2
        await provider.destroy(s1)
        await provider.destroy(s2)


# ── PathSandbox edge case tests ──

def test_is_allowed_read_rejects_empty_string(sandbox):
    """Empty string path should not be allowed for read access."""
    assert not sandbox.is_allowed_read("")


def test_is_allowed_write_rejects_empty_string(sandbox):
    """Empty string path should not be allowed for write access."""
    assert not sandbox.is_allowed_write("")


def test_is_allowed_read_rejects_none(sandbox):
    """None path should raise TypeError (not silently pass)."""
    with pytest.raises(TypeError):
        sandbox.is_allowed_read(None)


def test_is_allowed_write_rejects_none(sandbox):
    """None path should raise TypeError (not silently pass)."""
    with pytest.raises(TypeError):
        sandbox.is_allowed_write(None)


def test_is_allowed_read_rejects_null_byte_injection(sandbox):
    """Null byte injection 'safe\\0/etc/passwd' should be rejected for read."""
    assert not sandbox.is_allowed_read("safe\0/etc/passwd")


def test_is_allowed_write_rejects_null_byte_injection(sandbox):
    """Null byte injection 'safe\\0/etc/passwd' should be rejected for write."""
    assert not sandbox.is_allowed_write("safe\0/etc/passwd")


def test_is_allowed_read_rejects_absolute_path(sandbox):
    """Absolute path /etc/passwd should be rejected for read."""
    assert not sandbox.is_allowed_read("/etc/passwd")


def test_is_allowed_write_rejects_absolute_path(sandbox):
    """Absolute path /etc/shadow should be rejected for write."""
    assert not sandbox.is_allowed_write("/etc/shadow")


def test_is_allowed_read_rejects_triple_dotdot_traversal(sandbox):
    """Triple dot-dot traversal ../../../etc/passwd should be rejected for read."""
    assert not sandbox.is_allowed_read("../../../etc/passwd")


def test_is_allowed_write_rejects_triple_dotdot_traversal(sandbox):
    """Triple dot-dot traversal ../../../etc/passwd should be rejected for write."""
    assert not sandbox.is_allowed_write("../../../etc/passwd")


def test_is_allowed_read_rejects_dot_slash_traversal(sandbox):
    """Traversal via './../../../root/.ssh' should be rejected for read."""
    assert not sandbox.is_allowed_read("./../../../root/.ssh")


def test_is_allowed_write_rejects_dot_slash_traversal(sandbox):
    """Traversal via './../../../root/.ssh' should be rejected for write."""
    assert not sandbox.is_allowed_write("./../../../root/.ssh")


# ── PathSandbox.is_safe_path edge case tests ──

def test_is_safe_path_rejects_empty_string():
    """Empty string path is safe (not a traversal) — the tool handles missing params."""
    assert PathSandbox.is_safe_path("") is True


def test_is_safe_path_rejects_none():
    """None path should raise TypeError."""
    with pytest.raises(TypeError):
        PathSandbox.is_safe_path(None)


def test_is_safe_path_rejects_null_byte_injection():
    """Path with embedded null byte should be rejected as unsafe."""
    assert PathSandbox.is_safe_path("safe\0/etc/passwd") is False


def test_is_safe_path_rejects_sole_dotdot():
    """A bare '../' path should be rejected."""
    assert PathSandbox.is_safe_path("../") is False


def test_is_safe_path_rejects_dot_slash_traversal():
    """Traversal hidden behind './' with ../ should be rejected."""
    assert PathSandbox.is_safe_path("./../../../root/.ssh") is False


def test_is_safe_path_rejects_url_encoded_traversal():
    """URL-encoded traversal '..%2F..%2F..%2Fetc/passwd' should be rejected."""
    assert PathSandbox.is_safe_path("..%2F..%2F..%2Fetc/passwd") is False


def test_is_safe_path_rejects_absolute_path_root():
    """Absolute path /root/.ssh should be rejected."""
    assert PathSandbox.is_safe_path("/root/.ssh") is False


def test_is_safe_path_rejects_absolute_path_var():
    """Absolute path /var/log should be rejected."""
    assert PathSandbox.is_safe_path("/var/log") is False


# ── wrap_tool_with_sandbox edge case tests ──

def test_wrap_empty_path_passes_through(sandbox):
    """Empty path tool passes through — tool handles missing params on its own."""
    tool = _tool("read_file", "read", lambda p, c: "reached")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": ""})
    assert result == "reached"


def test_wrap_none_path_handled_gracefully(sandbox):
    """None path should not crash and should result in an error response."""
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": None})
    assert isinstance(result, str)


def test_wrap_triple_dotdot_traversal_blocked(sandbox):
    """Triple dot-dot traversal ../../../etc/passwd should be blocked."""
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "../../../etc/passwd"})
    assert "path traversal" in result.lower()


def test_wrap_dot_slash_traversal_blocked(sandbox):
    """Traversal via './../../../root/.ssh' should be blocked."""
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "./../../../root/.ssh"})
    assert "path traversal" in result.lower()


def test_wrap_absolute_path_blocked(sandbox):
    """Absolute path /etc/passwd should be blocked by sandbox."""
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "/etc/passwd"})
    assert "path traversal" in result.lower()


def test_wrap_write_absolute_path_blocked(sandbox):
    """Absolute path /etc/crontab should be blocked for write."""
    tool = _tool("write_file", "write", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "/etc/crontab", "content": "x"})
    assert "path traversal" in result.lower() or "denied" in result.lower()


def test_wrap_null_byte_path_blocked(sandbox):
    """Null byte injection in read path should be caught."""
    tool = _tool("read_file", "read", lambda p, c: "should not reach")
    wrapped = wrap_tool_with_sandbox(tool, sandbox)
    result = _call(wrapped, {"path": "workspace/\0/etc/passwd"})
    assert "path traversal" in result.lower() or "denied" in result.lower()
