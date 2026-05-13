"""Test glob tool via ToolRegistry public interface."""
import pytest
import os


@pytest.mark.asyncio
async def test_glob_finds_md_files(registry, tmp_path):
    (tmp_path / "readme.md").write_text("# hi")
    (tmp_path / "notes.md").write_text("notes")
    (tmp_path / "main.py").write_text("print(1)")
    os.makedirs(tmp_path / "sub", exist_ok=True)
    (tmp_path / "sub" / "deep.md").write_text("deep")

    result = await registry.execute("glob", {"pattern": str(tmp_path / "*.md")})
    assert "readme.md" in result
    assert "notes.md" in result
    assert "main.py" not in result


@pytest.mark.asyncio
async def test_glob_recursive(registry, tmp_path):
    os.makedirs(tmp_path / "sub", exist_ok=True)
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "sub" / "b.md").write_text("b")

    result = await registry.execute("glob", {"pattern": str(tmp_path / "**/*.md")})
    assert "a.md" in result
    assert "b.md" in result


@pytest.mark.asyncio
async def test_glob_no_match(registry, tmp_path):
    result = await registry.execute("glob", {"pattern": str(tmp_path / "*.xyz")})
    assert result == "" or "no matches" in result.lower()


@pytest.mark.asyncio
async def test_glob_missing_pattern(registry):
    result = await registry.execute("glob", {})
    assert "'pattern' is required" in result
