import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from context import load_agent_memory, load_user_profile
from dream import _user_hash


def test_agent_memory_is_separate_from_user_profile():
    tmp = tempfile.mkdtemp()
    try:
        base_dir = os.path.join(tmp, "py-agent")
        os.makedirs(base_dir)
        mem_dir = os.path.join(tmp, "agents", "test_a", "memory")
        os.makedirs(mem_dir)
        mem_path = os.path.join(mem_dir, "MEMORY.md")
        with open(mem_path, "w") as f:
            f.write("# Agent global memory")
        uh = _user_hash("user_x")
        user_dir = os.path.join(mem_dir, "users", uh)
        os.makedirs(user_dir)
        with open(os.path.join(user_dir, "PROFILE.md"), "w") as f:
            f.write("- user specific fact")
        with open(mem_path) as f:
            agent_mem = f.read()
        user_prof = load_user_profile("test_a", "user_x", base_dir=base_dir)
        assert "Agent global memory" in agent_mem
        assert "user specific fact" in user_prof
        assert "user specific fact" not in agent_mem
        assert "Agent global memory" not in user_prof
    finally:
        shutil.rmtree(tmp)


def test_user_profile_isolation():
    tmp = tempfile.mkdtemp()
    try:
        base_dir = os.path.join(tmp, "py-agent")
        os.makedirs(base_dir)
        mem_dir = os.path.join(tmp, "agents", "test_b", "memory")
        os.makedirs(mem_dir)
        uh_a = _user_hash("alice")
        uh_b = _user_hash("bob")
        for uh, fact in [(uh_a, "- alice fact"), (uh_b, "- bob fact")]:
            user_dir = os.path.join(mem_dir, "users", uh)
            os.makedirs(user_dir)
            with open(os.path.join(user_dir, "PROFILE.md"), "w") as f:
                f.write(fact)
        alice = load_user_profile("test_b", "alice", base_dir=base_dir)
        bob = load_user_profile("test_b", "bob", base_dir=base_dir)
        assert "alice fact" in alice
        assert "bob fact" in bob
        assert "alice fact" not in bob
        assert "bob fact" not in alice
    finally:
        shutil.rmtree(tmp)


def test_agent_memory_default_empty():
    assert load_agent_memory("nonexistent_agent") == ""


def test_user_profile_default_empty():
    assert load_user_profile("nonexistent_agent", "no_user") == ""
