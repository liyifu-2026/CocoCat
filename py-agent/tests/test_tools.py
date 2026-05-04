import pytest
import tempfile
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import ReadFileTool, WriteFileTool, EditFileTool, ExecCommandTool, WebFetchTool, SubAgentTool
from tools import ToolRegistry, PermissionMode, RememberTool, RecallTool

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def _test_path(name):
    return os.path.join(TEST_DIR, name)


class TestReadFileTool:
    def test_read_file_success(self):
        path = _test_path("test_read_success.txt")
        try:
            with open(path, "w") as f:
                f.write("hello world\nline 2\nline 3")
            tool = ReadFileTool()
            result = tool.execute(path=path)
            assert "hello world" in result
            assert "3 total lines" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_read_file_not_found(self):
        tool = ReadFileTool()
        result = tool.execute(path="/nonexistent/file_that_does_not_exist_12345.txt")
        assert "error" in result.lower() or "not found" in result.lower()

    def test_read_file_with_offset_and_limit(self):
        path = _test_path("test_read_offset.txt")
        try:
            with open(path, "w") as f:
                f.write("line 1\nline 2\nline 3\nline 4\nline 5")
            tool = ReadFileTool()
            result = tool.execute(path=path, offset=2, limit=2)
            assert "line 2" in result
            assert "line 3" in result
            assert "line 1" not in result
            assert "Read 2 lines" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_read_empty_file(self):
        path = _test_path("test_read_empty.txt")
        try:
            open(path, "w").close()
            tool = ReadFileTool()
            result = tool.execute(path=path)
            assert "0 total lines" in result or "Read 0 lines" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestWriteFileTool:
    _tmpdir = None

    def _ensure_tmpdir(self):
        if self._tmpdir is None:
            self._tmpdir = tempfile.mkdtemp(dir=TEST_DIR)
        return self._tmpdir

    def test_write_file_success(self):
        path = _test_path("test_write_success.txt")
        try:
            tool = WriteFileTool()
            result = tool.execute(path=path, content="hello world")
            assert "Successfully wrote" in result
            with open(path, "r") as f:
                assert f.read() == "hello world"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_write_file_creates_dirs(self):
        path = _test_path("subdir_write_test/nested/test.txt")
        try:
            tool = WriteFileTool()
            result = tool.execute(path=path, content="nested file")
            assert "Successfully wrote" in result
            assert os.path.exists(path)
        finally:
            if os.path.exists(_test_path("subdir_write_test")):
                import shutil
                shutil.rmtree(_test_path("subdir_write_test"))

    def test_write_file_empty_content(self):
        path = _test_path("test_write_empty.txt")
        try:
            tool = WriteFileTool()
            result = tool.execute(path=path, content="")
            assert "Successfully wrote" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestEditFileTool:
    def test_edit_file_success(self):
        path = _test_path("test_edit_success.txt")
        try:
            with open(path, "w") as f:
                f.write("hello world")
            tool = EditFileTool()
            result = tool.execute(path=path, old_string="hello", new_string="goodbye")
            assert "Applied edit" in result
            with open(path, "r") as f:
                assert f.read() == "goodbye world"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_edit_file_old_string_not_found(self):
        path = _test_path("test_edit_notfound.txt")
        try:
            with open(path, "w") as f:
                f.write("hello world")
            tool = EditFileTool()
            result = tool.execute(path=path, old_string="nonexistent", new_string="replacement")
            assert "error" in result.lower() or "not found" in result.lower()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_edit_file_identical_strings(self):
        path = _test_path("test_edit_identical.txt")
        try:
            with open(path, "w") as f:
                f.write("hello world")
            tool = EditFileTool()
            result = tool.execute(path=path, old_string="hello", new_string="hello")
            assert "must differ" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_edit_file_replace_all(self):
        path = _test_path("test_edit_replace_all.txt")
        try:
            with open(path, "w") as f:
                f.write("foo bar foo bar")
            tool = EditFileTool()
            result = tool.execute(path=path, old_string="foo", new_string="baz", replace_all=True)
            assert "Applied edit" in result
            with open(path, "r") as f:
                assert f.read() == "baz bar baz bar"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_edit_file_not_found(self):
        tool = EditFileTool()
        result = tool.execute(path="/nonexistent/file_12345.txt", old_string="foo", new_string="bar")
        assert "error" in result.lower() or "not found" in result.lower()


class TestExecCommandTool:
    def test_command_success(self):
        tool = ExecCommandTool()
        result = tool.execute(command="echo hello", timeout=5)
        assert "hello" in result

    def test_command_timeout(self):
        tool = ExecCommandTool()
        result = tool.execute(command="sleep 10", timeout=1)
        assert "timed out" in result.lower()

    def test_command_failure(self):
        tool = ExecCommandTool()
        result = tool.execute(command="exit 42", timeout=5)
        assert "exit code: 42" in result


class TestWebFetchTool:
    def test_fetch_invalid_url(self):
        tool = WebFetchTool()
        result = tool.execute(url="http://nonexistent.invalid.url.xyz", max_chars=100)
        assert "error" in result.lower() or "failed" in result.lower()

    def test_fetch_empty_url(self):
        tool = WebFetchTool()
        result = tool.execute(url="", max_chars=100)
        assert "error" in result.lower() or "failed" in result.lower()

    def test_fetch_max_chars_param(self):
        tool = WebFetchTool()
        assert hasattr(tool, "execute")
        params = tool.parameters
        props = params.get("properties", {})
        assert "max_chars" in props


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ReadFileTool()
        registry.register(tool)
        assert registry.get("read_file") is tool

    def test_get_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent_tool", {})
        assert "unknown tool" in result

    def test_get_definitions(self):
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        defs = registry.get_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "read_file"

    def test_permission_denied(self):
        registry = ToolRegistry()
        tool = ExecCommandTool()
        registry.register(tool)
        result = registry.execute("exec_command", {"command": "ls"}, PermissionMode.READONLY)
        assert "Permission denied" in result

    def test_default_registry_has_tools(self):
        from tools import create_default_registry
        registry = create_default_registry()
        assert registry.get("read_file") is not None
        assert registry.get("write_file") is not None
        assert registry.get("exec_command") is not None
        assert registry.get("edit_file") is not None
        assert registry.get("web_fetch") is not None
        assert registry.get("sub_agent") is not None


class TestPermissionMode:
    def test_readonly_le_write(self):
        assert PermissionMode.READONLY <= PermissionMode.WORKSPACE_WRITE

    def test_write_le_full(self):
        assert PermissionMode.WORKSPACE_WRITE <= PermissionMode.FULL_ACCESS

    def test_readonly_le_full(self):
        assert PermissionMode.READONLY <= PermissionMode.FULL_ACCESS

    def test_full_not_le_write(self):
        assert not (PermissionMode.FULL_ACCESS <= PermissionMode.WORKSPACE_WRITE)
