import sys, os, json, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from lsp_client import LSPPool, LSPClient
from tools import _default_lsp_command


def test_default_lsp_command():
    assert "pyright" in _default_lsp_command("python")
    assert "typescript" in _default_lsp_command("typescript")
    assert _default_lsp_command("ruby") == ""


def test_lsp_pool_key_uniqueness():
    pool = LSPPool()
    k1 = pool._key("cmd1", "/root/a")
    k2 = pool._key("cmd2", "/root/a")
    k3 = pool._key("cmd1", "/root/b")
    assert k1 != k2
    assert k1 != k3


def test_lsp_pool_cleanup():
    pool = LSPPool(idle_timeout=0)
    pool._clients["dummy"] = ("client", 0)
    pool.cleanup()
    assert "dummy" not in pool._clients


def test_lsp_pool_release_nonexistent():
    pool = LSPPool()
    pool.release("does", "not_exist")
