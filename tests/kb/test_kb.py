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
