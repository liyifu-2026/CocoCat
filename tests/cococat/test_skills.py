"""Tests for skills loader."""
import os
import tempfile
import pytest
from cococat.skills import load_skill, resolve_skills, skills_to_prompt, skills_to_tools


def test_load_skill_with_frontmatter():
    with tempfile.TemporaryDirectory() as d:
        md = os.path.join(d, "code_review.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("---\nname: Code Review\ndescription: Review code\n"
                    "tags: [development, review]\nas_tool: true\n---\n\n# Review\nBody here.")

        skill = load_skill("code_review", skills_dir=d)
        assert skill is not None
        assert skill["id"] == "code_review"
        assert skill["name"] == "Code Review"
        assert skill["description"] == "Review code"
        assert skill["tags"] == ["development", "review"]
        assert skill["as_tool"] is True
        assert "Body here" in skill["body"]
        assert "---" not in skill["body"]


def test_load_skill_no_frontmatter():
    with tempfile.TemporaryDirectory() as d:
        md = os.path.join(d, "hello.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("# Just a markdown file\nInstructions here.")

        skill = load_skill("hello", skills_dir=d)
        assert skill is not None
        assert skill["id"] == "hello"
        assert skill["name"] == "hello"
        assert "Instructions" in skill["description"]
        assert skill["tags"] == []
        assert skill["as_tool"] is False
        assert "# Just a markdown file" in skill["body"]


def test_load_skill_nonexistent():
    skill = load_skill("nonexistent", skills_dir="/tmp/nope")
    assert skill is None


def test_resolve_skills():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: A\n---\n\n# A body")
        with open(os.path.join(d, "b.md"), "w", encoding="utf-8") as f:
            f.write("# B body")

        skills = resolve_skills(["a", "b", "missing"], skills_dir=d)
        assert len(skills) == 2
        ids = {s["id"] for s in skills}
        assert ids == {"a", "b"}


def test_resolve_skills_empty():
    skills = resolve_skills([], skills_dir="/tmp/nope")
    assert skills == []


def test_skills_to_prompt():
    skills = [
        {"id": "a", "name": "A", "description": "...", "tags": [], "as_tool": False, "body": "Skill A body\nLine 2"},
        {"id": "b", "name": "B", "description": "...", "tags": ["x"], "as_tool": False, "body": "Skill B body"},
    ]
    prompt = skills_to_prompt(skills)
    assert "## Active Skills" in prompt
    assert "### a" in prompt
    assert "Skill A body" in prompt
    assert "### b" in prompt
    assert "Skill B body" in prompt


def test_skills_to_prompt_empty():
    assert skills_to_prompt([]) == ""


def test_skills_to_tools():
    skills = [
        {"id": "a", "name": "A", "description": "Desc A", "tags": [], "as_tool": True, "body": "A body"},
        {"id": "b", "name": "B", "description": "Desc B", "tags": [], "as_tool": False, "body": "B body"},
        {"id": "c", "name": "C", "description": "Desc C", "tags": [], "as_tool": True, "body": "C body"},
    ]
    tools = skills_to_tools(skills)
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"a", "c"}
    assert "Desc A" in [t["description"] for t in tools]


def test_skills_to_tools_empty():
    assert skills_to_tools([]) == []
