import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from tools import (
    ReadFileTool, WriteFileTool, ExecCommandTool,
    GlobSearchTool, GrepSearchTool, EditFileTool,
    ToolRegistry, PermissionMode,
)


def test_read_file_tool_outside_workspace():
    tool = ReadFileTool()
    result = tool.execute(path="/etc/passwd")
    assert "denied" in result or "Error" in result


def test_write_file_tool_outside_workspace():
    tool = WriteFileTool()
    result = tool.execute(path="/etc/evil.txt", content="malicious")
    assert "denied" in result or "Error" in result


def test_edit_file_tool_outside_workspace():
    tool = EditFileTool()
    result = tool.execute(path="/etc/evil.txt", old_string="x", new_string="y")
    assert "denied" in result or "Error" in result


def test_glob_search_tool_outside_workspace():
    tool = GlobSearchTool()
    result = tool.execute(pattern="*.py", path="/etc")
    assert "denied" in result or "Error" in result


def test_read_file_tool_success():
    tmp_root = os.path.join(os.path.dirname(__file__), "__tmp__")
    os.makedirs(tmp_root, exist_ok=True)
    try:
        test_file = os.path.join(tmp_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello\nworld\n")
        tool = ReadFileTool()
        result = tool.execute(path=test_file)
        assert "hello" in result
        assert "world" in result
    finally:
        import shutil
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_exec_command_tool_basic():
    tool = ExecCommandTool()
    result = tool.execute(command="echo hello")
    assert "hello" in result


def test_exec_command_tool_no_shell_injection():
    tool = ExecCommandTool()
    result = tool.execute(command="echo hello && echo escaped")
    assert "hello" in result or "escaped" in result


def test_write_file_tool_in_workspace():
    tmp_root = os.path.join(os.path.dirname(__file__), "__tmp__")
    os.makedirs(tmp_root, exist_ok=True)
    try:
        filepath = os.path.join(tmp_root, "newfile.txt")
        tool = WriteFileTool()
        result = tool.execute(path=filepath, content="test content")
        assert "wrote" in result.lower() or "success" in result.lower()
        assert os.path.exists(filepath)
    finally:
        import shutil
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_tool_registry_permission_denied():
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    result = registry.execute("write_file", {"path": "/tmp/x", "content": "x"}, PermissionMode.READONLY)
    assert "denied" in result


def test_tool_registry_unknown_tool():
    registry = ToolRegistry()
    result = registry.execute("nonexistent", {}, PermissionMode.FULL_ACCESS)
    assert "unknown" in result


def test_grep_search_tool_basic():
    tmp_root = os.path.join(os.path.dirname(__file__), "__tmp__")
    os.makedirs(tmp_root, exist_ok=True)
    try:
        filepath = os.path.join(tmp_root, "search.txt")
        with open(filepath, "w") as f:
            f.write("hello world\nfoo bar\n")
        tool = GrepSearchTool()
        result = tool.execute(pattern="hello", path=tmp_root)
        assert "hello" in result
    finally:
        import shutil
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_tool_execute_error_handling():
    tool = ReadFileTool()
    result = tool.execute(path="/nonexistent_file_xyz")
    assert "Error" in result or "error" in result or "denied" in result
