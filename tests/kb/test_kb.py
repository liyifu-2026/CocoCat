"""Tests for KB overview injection."""
import os
import tempfile
import pytest
from cococat.kb import load_kb_overview, inject_kb_context


@pytest.fixture
def kb_dir():
    with tempfile.TemporaryDirectory() as d:
        kb = os.path.join(d, "test-kb")
        os.makedirs(kb)
        with open(os.path.join(kb, "purpose.md"), "w") as f:
            f.write("This KB contains test documentation.")
        with open(os.path.join(kb, "index.md"), "w") as f:
            f.write("# Entities\n- test-entity\n\n# Concepts\n- test-concept")
        yield d


def test_load_kb_overview_empty():
    result = load_kb_overview([])
    assert result == ""


def test_load_kb_overview_with_kb(kb_dir):
    result = load_kb_overview(["test-kb"], knowledge_dir=kb_dir)
    assert "test-kb" in result
    assert "test documentation" in result
    assert "test-entity" in result


def test_inject_kb_context(kb_dir):
    prompt = "You are a helpful assistant."
    result = inject_kb_context(prompt, ["test-kb"], knowledge_dir=kb_dir)
    assert prompt in result
    assert "Available Knowledge Bases" in result


def test_load_kb_overview_nonexistent_kb():
    result = load_kb_overview(["nonexistent-kb"])
    assert result == ""  # KB dir not found, skipped


def test_load_kb_overview_mixed_exist_nonexist(kb_dir):
    """Existing KBs included, nonexistent ones silently skipped."""
    result = load_kb_overview(["nonexistent", "test-kb"], knowledge_dir=kb_dir)
    assert "test-kb" in result
    assert "test documentation" in result


def test_inject_kb_context_empty_kbs():
    prompt = "Base prompt"
    result = inject_kb_context(prompt, [])
    assert result == prompt  # Unchanged when no KBs


def test_inject_kb_context_no_overview(kb_dir):
    """When KBs exist but produce empty overview, prompt should be unchanged."""
    result = inject_kb_context("Base prompt", [], knowledge_dir=kb_dir)
    assert result == "Base prompt"


def test_load_kb_overview_empty_name_string(tmp_path):
    """KB name is empty string — os.path.join resolves to knowledge_dir itself."""
    result = load_kb_overview([""], knowledge_dir=str(tmp_path))
    # Empty name joins to knowledge_dir which is a real dir, so it shows as "### "
    assert "### " in result
    assert "Available Knowledge Bases" in result


def test_load_kb_overview_no_purpose_md(tmp_path):
    """KB directory exists but has no purpose.md — still produces overview from index."""
    kb = tmp_path / "kb-no-purpose"
    kb.mkdir()
    (kb / "index.md").write_text("# Entities\n- foo\n- bar")

    result = load_kb_overview(["kb-no-purpose"], knowledge_dir=str(tmp_path))
    assert "kb-no-purpose" in result
    assert "foo" in result
    assert "bar" in result
    assert "Purpose" not in result


def test_load_kb_overview_malformed_yaml_in_config(tmp_path):
    """KB directory contains a config.yaml with broken YAML — load_kb_overview ignores it."""
    kb = tmp_path / "kb-broken-config"
    kb.mkdir()
    (kb / "purpose.md").write_text("Valid purpose.")
    (kb / "index.md").write_text("# Entities\n- entity-a")
    (kb / "config.yaml").write_text("key: [unclosed\n  nested: ::broken")

    result = load_kb_overview(["kb-broken-config"], knowledge_dir=str(tmp_path))
    assert "kb-broken-config" in result
    assert "Valid purpose." in result
    assert "entity-a" in result


def test_inject_kb_context_with_empty_list():
    """inject_kb_context with empty KB list returns prompt unchanged."""
    prompt = "System prompt"
    result = inject_kb_context(prompt, [])
    assert result == prompt


def test_inject_kb_context_with_nonexistent_kb_name():
    """inject_kb_context with a nonexistent KB name returns prompt unchanged."""
    prompt = "System prompt"
    result = inject_kb_context(prompt, ["ghost-kb"])
    assert result == prompt


def test_load_kb_overview_with_mixed_existent_nonexistent(tmp_path):
    """load_kb_overview includes existing KBs, silently skips nonexistent ones."""
    kb_a = tmp_path / "kb-a"
    kb_a.mkdir()
    (kb_a / "purpose.md").write_text("Purpose A.")
    (kb_a / "index.md").write_text("# Entities\n- entity-a")

    result = load_kb_overview(["ghost-kb", "kb-a", "phantom-kb"], knowledge_dir=str(tmp_path))
    assert "kb-a" in result
    assert "Purpose A." in result
    assert "entity-a" in result
    assert "ghost-kb" not in result
    assert "phantom-kb" not in result
