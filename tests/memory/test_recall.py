"""Test memory search and experience tools: recall, record/recall_experience."""
import pytest
import os


class TestRecall:
    @pytest.mark.asyncio
    async def test_recall_finds_in_memory_file(self, registry, tmp_path):
        mem_file = tmp_path / "memory.md"
        mem_file.write_text("user prefers dark mode\nuser likes python\n")
        ctx = {"memory_path": str(mem_file)}
        result = await registry.execute("recall", {"query": "dark"}, ctx)
        assert "dark mode" in result

    @pytest.mark.asyncio
    async def test_recall_no_match(self, registry, tmp_path):
        mem_file = tmp_path / "memory.md"
        mem_file.write_text("user prefers dark mode\n")
        ctx = {"memory_path": str(mem_file)}
        result = await registry.execute("recall", {"query": "nonexistent"}, ctx)
        assert "not found" in result.lower() or "no matches" in result.lower()

    @pytest.mark.asyncio
    async def test_recall_missing_query(self, registry):
        result = await registry.execute("recall", {})
        assert "required" in result.lower() or "query" in result.lower()

    @pytest.mark.asyncio
    async def test_recall_searches_experiences(self, registry, tmp_path):
        exp_dir = tmp_path / "experiences"
        os.makedirs(exp_dir / "coding")
        (exp_dir / "coding" / "python-tips.md").write_text("Python is great for data science\n")
        ctx = {"exp_path": str(exp_dir)}
        result = await registry.execute("recall", {"query": "Python"}, ctx)
        assert "Python" in result or "python" in result


class TestRecordExperience:
    @pytest.mark.asyncio
    async def test_record_creates_entry(self, registry, tmp_path):
        ctx = {"exp_path": str(tmp_path)}
        result = await registry.execute("record_experience", {
            "category": "coding", "entry": "Python list comprehensions are fast"
        }, ctx)
        assert "recorded" in result.lower() or "saved" in result.lower()
        file_path = tmp_path / "coding" / "python-list-comprehensions-are-fast.md"
        # Check any file was created in the coding directory
        coding_dir = tmp_path / "coding"
        assert coding_dir.is_dir()
        files = list(coding_dir.iterdir())
        assert len(files) > 0
        content = files[0].read_text()
        assert "Python list comprehensions" in content

    @pytest.mark.asyncio
    async def test_record_missing_category(self, registry):
        result = await registry.execute("record_experience", {"entry": "test"})
        assert "required" in result.lower() or "category" in result.lower()

    @pytest.mark.asyncio
    async def test_record_missing_entry(self, registry):
        result = await registry.execute("record_experience", {"category": "test"})
        assert "required" in result.lower() or "entry" in result.lower()


class TestRecallExperience:
    @pytest.mark.asyncio
    async def test_recall_experience_by_category(self, registry, tmp_path):
        exp_dir = tmp_path / "experiences"
        os.makedirs(exp_dir / "coding")
        (exp_dir / "coding" / "tip1.md").write_text("Use list comprehensions\n")
        (exp_dir / "coding" / "tip2.md").write_text("Avoid global state\n")
        ctx = {"exp_path": str(exp_dir)}
        result = await registry.execute("recall_experience", {"category": "coding"}, ctx)
        assert "list comprehensions" in result
        assert "Avoid" in result

    @pytest.mark.asyncio
    async def test_recall_experience_empty_category(self, registry, tmp_path):
        os.makedirs(tmp_path / "emptycat")
        ctx = {"exp_path": str(tmp_path)}
        result = await registry.execute("recall_experience", {"category": "emptycat"}, ctx)
        assert "no experiences" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_recall_experience_missing_category(self, registry):
        result = await registry.execute("recall_experience", {})
        assert "required" in result.lower() or "category" in result.lower()
