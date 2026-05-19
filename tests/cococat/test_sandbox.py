"""Tests for PathSandbox and tool sandbox wrapping."""
import os
import pytest
from cococat.core.sandbox_path import PathSandbox, wrap_tool_with_sandbox


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
