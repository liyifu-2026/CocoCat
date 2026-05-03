import sys, os, tempfile, shutil, stat
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from git_store import GitStore


def _rmtree_readonly(path):
    def _onerror(func, p, exc_info):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_onerror)


def test_git_store_init_and_commit():
    tmp = tempfile.mkdtemp()
    try:
        store = GitStore(tmp)
        assert os.path.isdir(os.path.join(tmp, ".git"))
        test_file = os.path.join(tmp, "TEST.md")
        with open(test_file, "w") as f:
            f.write("hello")
        store.commit("test: first commit")
        log = store.log()
        assert len(log) >= 1
        assert "test: first commit" in log[0]
    finally:
        _rmtree_readonly(tmp)


def test_git_store_revert():
    tmp = tempfile.mkdtemp()
    try:
        store = GitStore(tmp)
        test_file = os.path.join(tmp, "TEST.md")
        with open(test_file, "w") as f:
            f.write("version 1")
        store.commit("v1")
        with open(test_file, "w") as f:
            f.write("version 2")
        store.commit("v2")
        store.revert()
        with open(test_file) as f:
            assert f.read() == "version 1"
    finally:
        _rmtree_readonly(tmp)
