import pytest
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sandbox import (
    CommandValidator, EnvironmentSanitizer, PathValidator,
    OutputTruncator, atomic_write, FileLock, wrap_with_namespace,
)


class TestCommandValidator:
    def setup_method(self):
        self.validator = CommandValidator()

    def test_block_rm_rf_root(self):
        valid, reason = self.validator.validate("rm -rf /", "full")
        assert not valid
        assert "dangerous" in reason.lower()

    def test_block_sudo(self):
        valid, reason = self.validator.validate("sudo apt install", "full")
        assert not valid

    def test_block_mkfs(self):
        valid, reason = self.validator.validate("mkfs.ext4 /dev/sda1", "full")
        assert not valid

    def test_block_dd(self):
        valid, reason = self.validator.validate("dd if=/dev/zero of=/dev/sda", "full")
        assert not valid

    def test_block_shutdown(self):
        valid, reason = self.validator.validate("shutdown -h now", "full")
        assert not valid

    def test_block_reboot(self):
        valid, reason = self.validator.validate("reboot", "full")
        assert not valid

    def test_block_iptables(self):
        valid, reason = self.validator.validate("iptables -F", "full")
        assert not valid

    def test_block_package_install(self):
        valid, reason = self.validator.validate("apt install nginx", "full")
        assert not valid

    def test_allow_safe_command(self):
        valid, reason = self.validator.validate("ls -la", "full")
        assert valid

    def test_allow_echo(self):
        valid, reason = self.validator.validate("echo hello world", "full")
        assert valid

    def test_allow_git_log(self):
        valid, reason = self.validator.validate("git log --oneline -5", "full")
        assert valid

    def test_allow_python_script(self):
        valid, reason = self.validator.validate("python3 -c 'print(1)'", "full")
        assert valid

    def test_detect_ssrf_curl_to_internal(self):
        valid, reason = self.validator.validate("curl http://169.254.169.254/latest/meta-data/", "full")
        assert not valid
        assert "internal" in reason.lower() or "ssrf" in reason.lower()

    def test_detect_ssrf_wget_to_internal(self):
        valid, reason = self.validator.validate("wget http://192.168.1.1/", "full")
        assert not valid
        assert "internal" in reason.lower() or "ssrf" in reason.lower()

    def test_allow_curl_to_external(self):
        valid, reason = self.validator.validate("curl https://api.example.com/data", "full")
        assert valid

    def test_block_wget_to_localhost(self):
        valid, reason = self.validator.validate("wget http://127.0.0.1:8080/", "full")
        assert not valid


class TestEnvironmentSanitizer:
    def setup_method(self):
        self.sanitizer = EnvironmentSanitizer()

    def test_remove_api_key(self):
        env = {"PATH": "/usr/bin", "API_KEY": "secret123", "HOME": "/root"}
        clean = self.sanitizer.sanitize(env)
        assert "API_KEY" not in clean
        assert "PATH" in clean
        assert "HOME" in clean

    def test_remove_token(self):
        env = {"GITHUB_TOKEN": "ghp_abc123", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "GITHUB_TOKEN" not in clean

    def test_remove_password(self):
        env = {"DB_PASSWORD": "hunter2", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "DB_PASSWORD" not in clean

    def test_remove_secret(self):
        env = {"MY_SECRET": "secret_value", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "MY_SECRET" not in clean

    def test_remove_auth(self):
        env = {"AUTH_TOKEN": "abc123", "PATH": "/usr/bin"}
        clean = self.sanitizer.sanitize(env)
        assert "AUTH_TOKEN" not in clean

    def test_keep_safe_vars(self):
        env = {"PATH": "/usr/bin", "HOME": "/root", "USER": "test"}
        clean = self.sanitizer.sanitize(env)
        assert "PATH" in clean
        assert "HOME" in clean
        assert "USER" in clean

    def test_does_not_mutate_original(self):
        env = {"API_KEY": "secret"}
        original = dict(env)
        self.sanitizer.sanitize(env)
        assert env == original


class TestPathValidator:
    def setup_method(self):
        self.validator = PathValidator()

    def test_valid_path_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            test_path = os.path.join(tmpdir, "subdir", "file.txt")
            os.makedirs(os.path.join(tmpdir, "subdir"))
            open(test_path, "w").close()
            valid, reason = self.validator.validate(test_path, workspace)
            assert valid

    def test_path_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            valid, reason = self.validator.validate("/etc/passwd", workspace)
            assert not valid
            assert "outside" in reason.lower()

    def test_path_with_dotdot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            workspace = Path(subdir)
            malicious = os.path.join(subdir, "..", "..", "etc", "passwd")
            valid, reason = self.validator.validate(malicious, workspace)
            assert not valid

    def test_empty_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            valid, reason = self.validator.validate("", workspace)
            assert not valid


class TestOutputTruncator:
    def setup_method(self):
        self.truncator = OutputTruncator()

    def test_no_truncation_needed(self):
        output = "short text"
        result = self.truncator.truncate(output, max_chars=100)
        assert result == "short text"

    def test_truncation_happens(self):
        output = "a" * 1000
        result = self.truncator.truncate(output, max_chars=100)
        assert len(result) < len(output)
        assert "truncated" in result

    def test_exact_boundary(self):
        output = "a" * 100
        result = self.truncator.truncate(output, max_chars=100)
        assert result == output

    def test_custom_max_chars(self):
        output = "a" * 500
        result = self.truncator.truncate(output, max_chars=50)
        assert "truncated" in result
        assert len(result) < 200


class TestAtomicWrite:
    def test_basic_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            atomic_write(path, "hello world")
            with open(path, "r") as f:
                assert f.read() == "hello world"

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            atomic_write(path, "first content")
            atomic_write(path, "second content")
            with open(path, "r") as f:
                assert f.read() == "second content"

    def test_creates_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a", "b", "c", "test.txt")
            atomic_write(path, "nested")
            assert os.path.exists(path)

    def test_write_empty_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.txt")
            atomic_write(path, "")
            with open(path, "r") as f:
                assert f.read() == ""


class TestFileLock:
    def test_acquire_and_release(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "test.lock")
            with FileLock(lock_path, timeout=1.0):
                assert os.path.exists(lock_path + ".lock")
            assert not os.path.exists(lock_path + ".lock")

    def test_lock_context_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "test.lock")
            with FileLock(lock_path, timeout=1.0) as lock:
                assert lock is not None
