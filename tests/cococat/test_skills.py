"""Tests for skills loader."""
import os
import tempfile
import pytest
from cococat.skills import load_skill_file, load_scene_skills, load_global_skills


def test_load_skill_file_with_frontmatter():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nname: test_tool\ndescription: A test tool\n---\n\n# Body\nSome instructions.")
        path = f.name

    skill = load_skill_file(path)
    assert skill is not None
    assert skill["name"] == "test_tool"
    assert "test tool" in skill["description"]
    assert "# Body" in skill["body"]
    os.unlink(path)


def test_load_skill_file_no_frontmatter():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Just a markdown file\nWith some instructions.")
        path = f.name

    skill = load_skill_file(path)
    assert skill is not None
    assert skill["name"] != ""
    os.unlink(path)


def test_load_scene_skills():
    with tempfile.TemporaryDirectory() as d:
        scene_dir = os.path.join(d, "scenes", "customer-service")
        os.makedirs(scene_dir)
        with open(os.path.join(scene_dir, "refund_procedure.md"), "w") as f:
            f.write("---\nname: refund_procedure\ndescription: Refund\n---\n# Body")

        tools = load_scene_skills("customer-service", skills_dir=d)
        names = {t["name"] for t in tools}
        assert "refund_procedure" in names


def test_load_scene_skills_nonexistent():
    tools = load_scene_skills("nonexistent-scene")
    assert tools == []


def test_load_global_skills():
    with tempfile.TemporaryDirectory() as d:
        public_dir = os.path.join(d, "public")
        os.makedirs(public_dir)
        with open(os.path.join(public_dir, "test_skill.md"), "w") as f:
            f.write("---\nname: test_skill\ndescription: A global skill\n---\n# Body")

        tools = load_global_skills(skills_dir=d)
        names = {t["name"] for t in tools}
        assert "test_skill" in names


def test_load_global_skills_empty():
    with tempfile.TemporaryDirectory() as d:
        tools = load_global_skills(skills_dir=d)
        assert tools == []


def test_load_skill_file_nonexistent():
    skill = load_skill_file("/nonexistent/skill.md")
    assert skill is None
