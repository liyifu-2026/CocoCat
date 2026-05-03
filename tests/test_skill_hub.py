import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from skill_hub import (
    load_registry, save_registry, install_skill_from_path,
    search_registry, uninstall_skill, validate_skill, list_installed_skills,
    SKILLS_DIR,
)


def _cleanup():
    reg = SKILLS_DIR / "registry.json"
    if reg.exists():
        reg.unlink()
    for f in (SKILLS_DIR / "public").iterdir():
        if f.name.endswith((".md", ".tmp")):
            f.unlink()


def _make_skill(name: str, content: str = "") -> str:
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, f"{name}.md")
    with open(path, "w") as f:
        f.write(content or f"# Skill: {name}\nTest.")
    return path


def test_load_registry_empty():
    _cleanup()
    assert load_registry() == []


def test_save_and_load_registry():
    _cleanup()
    entries = [{"name": "test-skill", "source": "/tmp", "type": "local", "version": 1}]
    save_registry(entries)
    loaded = load_registry()
    assert len(loaded) == 1
    assert loaded[0]["name"] == "test-skill"


def test_install_and_uninstall_skill():
    _cleanup()
    src = _make_skill("test_skill")
    result = install_skill_from_path(src)
    assert "Installed" in result
    registry = load_registry()
    names = [e["name"] for e in registry]
    assert "test_skill" in names
    result = uninstall_skill("test_skill")
    assert "Uninstalled" in result
    registry = load_registry()
    names = [e["name"] for e in registry]
    assert "test_skill" not in names


def test_install_increments_version():
    _cleanup()
    src = _make_skill("ver_skill")
    install_skill_from_path(src)
    v1 = load_registry()[0]["version"]
    install_skill_from_path(src)
    assert load_registry()[0]["version"] > v1


def test_search_registry():
    _cleanup()
    src = _make_skill("unique_name")
    install_skill_from_path(src)
    results = search_registry("unique")
    assert len(results) >= 1
    assert results[0]["name"] == "unique_name"
    assert search_registry("nonexistent") == []


def test_validate_skill():
    _cleanup()
    src = _make_skill("ok_skill")
    install_skill_from_path(src)
    result = validate_skill("ok_skill")
    assert "valid" in result
    assert "Error" in validate_skill("nonexistent")


def test_list_installed_skills():
    _cleanup()
    assert list_installed_skills() == []
    src = _make_skill("list_me")
    install_skill_from_path(src)
    skills = list_installed_skills()
    names = [s["name"] for s in skills]
    assert "list_me" in names
