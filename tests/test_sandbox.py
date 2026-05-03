import sys, tempfile
from pathlib import Path
import pytest
sys.path.insert(0, "py-agent")
from sandbox import CommandValidator, IS_WINDOWS, EnvironmentSanitizer, PathValidator, OutputTruncator

validator = CommandValidator()


def test_block_destructive_windows():
    if not IS_WINDOWS:
        pytest.skip("Windows-only test")
    assert not validator.validate("del /f /s C:\\*", "FULL_ACCESS")[0]
    assert not validator.validate("rmdir /s /q C:\\", "FULL_ACCESS")[0]
    assert not validator.validate("format D: /q", "FULL_ACCESS")[0]


def test_block_destructive_linux():
    if IS_WINDOWS:
        pytest.skip("Linux-only test")
    assert not validator.validate("rm -rf /", "FULL_ACCESS")[0]
    assert not validator.validate("sudo apt install nginx", "FULL_ACCESS")[0]
    assert not validator.validate("dd if=/dev/zero of=/dev/sda", "FULL_ACCESS")[0]


def test_block_ssrf():
    assert not validator.validate("curl http://169.254.169.254/latest/meta-data/", "FULL_ACCESS")[0]
    assert not validator.validate("wget http://10.0.0.1/config", "FULL_ACCESS")[0]
    assert not validator.validate("curl http://192.168.1.1/admin", "FULL_ACCESS")[0]


def test_allow_safe_commands():
    assert validator.validate("echo hello", "FULL_ACCESS")[0]
    assert validator.validate("ls -la", "FULL_ACCESS")[0]
    assert validator.validate("python --version", "FULL_ACCESS")[0]
    assert validator.validate("git status", "FULL_ACCESS")[0]
    assert validator.validate("pip list", "FULL_ACCESS")[0]


sanitizer = EnvironmentSanitizer()
path_val = PathValidator()
truncator = OutputTruncator()


def test_env_sanitizer_removes_secrets():
    dirty = {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-xxx", "HOME": "/root", "JWT_SECRET": "mysecret"}
    clean = sanitizer.sanitize(dirty)
    assert "OPENAI_API_KEY" not in clean
    assert "JWT_SECRET" not in clean
    assert "PATH" in clean
    if not IS_WINDOWS:
        assert "HOME" in clean


def test_path_validator_allows_workspace():
    ws = Path(tempfile.mkdtemp())
    (ws / "test.txt").write_text("hello")
    ok, _ = path_val.validate(str(ws / "test.txt"), ws)
    assert ok


def test_path_validator_case_insensitive_windows():
    ws = Path(tempfile.mkdtemp())
    (ws / "test.txt").write_text("hello")
    if IS_WINDOWS:
        upper_path = str(ws / "test.txt").upper()
        ok, _ = path_val.validate(upper_path, ws)
        assert ok
    else:
        ok, _ = path_val.validate(str(ws / "test.txt"), ws)
        assert ok


def test_path_validator_blocks_outside():
    ws = Path(tempfile.mkdtemp())
    ok, reason = path_val.validate("/etc/passwd", ws)
    assert not ok
    assert "outside workspace" in reason


def test_env_sanitizer_preserves_cococat_vars():
    dirty = {"COCOCAT_WORKSPACE": "/project", "COCOCAT_MODE": "dev", "PATH": "/usr/bin"}
    clean = sanitizer.sanitize(dirty)
    assert clean.get("COCOCAT_WORKSPACE") == "/project"
    assert clean.get("COCOCAT_MODE") == "dev"
    assert clean.get("PATH") == "/usr/bin"


def test_output_truncator():
    short = "hello"
    assert truncator.truncate(short) == short
    long = "x" * 20000
    truncated = truncator.truncate(long)
    assert len(truncated) <= 10000 + 50
    assert "truncated" in truncated


def test_output_truncator_custom_max():
    text = "hello world " * 10
    truncated = truncator.truncate(text, max_chars=5)
    assert "truncated" in truncated
    assert len(truncated) < len(text)


def test_exec_command_sandbox_blocks_dangerous():
    from tools import ExecCommandTool
    tool = ExecCommandTool()
    is_win = sys.platform == "win32"
    cmd = "del /f /s C:\\*" if is_win else "rm -rf /"
    result = tool.execute(command=cmd)
    assert "rejected" in result.lower()


def test_exec_command_sandbox_allows_safe():
    from tools import ExecCommandTool
    tool = ExecCommandTool()
    result = tool.execute(command="echo hello_cococat_sandbox_test")
    assert "hello_cococat_sandbox_test" in result


def test_file_tool_path_validation_blocks_outside():
    from tools import ReadFileTool
    tool = ReadFileTool()
    path = "C:\\Windows\\win.ini" if sys.platform == "win32" else "/etc/passwd"
    result = tool.execute(path=path)
    assert "outside workspace" in result.lower() or "rejected" in result.lower()
