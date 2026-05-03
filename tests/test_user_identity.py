import sys, os, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from context import load_user_profile, build_system_prompt


def test_load_user_profile_exists():
    tmp = tempfile.mkdtemp()
    try:
        from context import _user_hash
        uh = _user_hash("user_abc")
        base_dir = os.path.join(tmp, "py-agent")
        os.makedirs(base_dir)
        profile_dir = os.path.join(tmp, "agents", "test_a", "memory", "users", uh)
        os.makedirs(profile_dir)
        profile_path = os.path.join(profile_dir, "PROFILE.md")
        with open(profile_path, "w") as f:
            f.write("- likes blue products")
        profile = load_user_profile(agent_id="test_a", user_id="user_abc", base_dir=base_dir)
        assert profile == "- likes blue products"
    finally:
        shutil.rmtree(tmp)


def test_load_user_profile_not_exists():
    profile = load_user_profile(agent_id="test", user_id="nonexistent")
    assert profile == ""


def test_build_system_prompt_with_user():
    prompt = build_system_prompt(
        agent_name="TestBot",
        agent_memory="I know things.",
        agent_skills="",
        env_skills="",
        user_profile="likes blue",
        user_conversation="[user] hello\n[agent] hi",
    )
    assert "## Current User" in prompt
    assert "likes blue" in prompt
    assert "## Conversation History" in prompt
    assert "[user] hello" in prompt


def test_build_system_prompt_without_user():
    prompt = build_system_prompt(agent_name="TestBot", agent_memory="mem")
    assert "## Current User" not in prompt
    assert "## Conversation History" not in prompt
