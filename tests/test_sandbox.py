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


def test_path_validator_blocks_outside():
    ws = Path(tempfile.mkdtemp())
    ok, reason = path_val.validate("/etc/passwd", ws)
    assert not ok
    assert "outside workspace" in reason


def test_output_truncator():
    short = "hello"
    assert truncator.truncate(short) == short
    long = "x" * 20000
    truncated = truncator.truncate(long)
    assert len(truncated) <= 10000 + 50
    assert "truncated" in truncated
