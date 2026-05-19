import os
import tempfile
import pytest
from cococat.kb.service import KBService


@pytest.fixture
def temp_kb():
    """Create a temporary KB directory with test pages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_dir = os.path.join(tmpdir, "test-kb")
        wiki_dir = os.path.join(kb_dir, "wiki", "entities")
        os.makedirs(wiki_dir)
        with open(os.path.join(wiki_dir, "python.md"), "w") as f:
            f.write("---\ntitle: Python\ntype: entity\n---\n\nPython is a programming language.")
        with open(os.path.join(wiki_dir, "rust.md"), "w") as f:
            f.write("---\ntitle: Rust\ntype: entity\n---\n\nRust is a systems programming language.")
        concepts_dir = os.path.join(kb_dir, "wiki", "concepts")
        os.makedirs(concepts_dir)
        with open(os.path.join(concepts_dir, "async.md"), "w") as f:
            f.write("---\ntitle: Async\ntype: concept\n---\n\nAsync programming with coroutines.")
        os.makedirs(os.path.join(kb_dir, "raw", "sources"))
        with open(os.path.join(kb_dir, "index.md"), "w") as f:
            f.write("# Index\n\n## Entities\n- python\n- rust\n\n## Concepts\n- async")
        with open(os.path.join(kb_dir, "purpose.md"), "w") as f:
            f.write("Test knowledge base for unit tests.")
        yield kb_dir


def test_search_finds_matching_pages(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    results = service.search("test-kb", "programming")
    assert len(results) >= 2
    names = [r["name"] for r in results]
    assert "python" in names
    assert "rust" in names


def test_search_case_insensitive(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    results = service.search("test-kb", "PYTHON")
    assert len(results) >= 1
    assert results[0]["name"] == "python"


def test_search_no_match(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    results = service.search("test-kb", "zzzzzz_nonexistent")
    assert results == []


def test_read_page(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    page = service.read("test-kb", "entities", "python")
    assert page is not None
    assert page["name"] == "python"
    assert "programming language" in page["content"]


def test_read_nonexistent_page(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    page = service.read("test-kb", "entities", "nonexistent")
    assert page is None


def test_list_pages(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    pages = service.list_pages("test-kb")
    assert "entities" in pages
    assert "concepts" in pages
    assert "python" in pages["entities"]
    assert "async" in pages["concepts"]


def test_write_page(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    service.write_page("test-kb", "entities", "golang", "Go is a compiled language.", {
        "title": "Go", "type": "entity",
    })
    page = service.read("test-kb", "entities", "golang")
    assert page is not None
    assert "compiled language" in page["content"]


def test_write_page_default_frontmatter(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    service.write_page("test-kb", "entities", "neo4j", "Graph database.", None)
    page = service.read("test-kb", "entities", "neo4j")
    assert page is not None
    assert "type: entity" in page["content"].lower()


def test_write_page_updates_index(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    service.write_page("test-kb", "concepts", "testing", "Testing is important.", {
        "title": "Testing", "type": "concept",
    })
    index_path = os.path.join(temp_kb, "index.md")
    with open(index_path) as f:
        content = f.read()
    assert "testing" in content.lower()


def test_get_overview_context(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    ctx = service.get_overview_context(["test-kb"])
    assert "test-kb" in ctx
    assert "Test knowledge base" in ctx


def test_run_lint(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    result = service.run_lint("test-kb")
    assert isinstance(result, dict)
    assert "orphans" in result
    assert "broken_links" in result
    assert "missing_fm" in result


def test_get_graph(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    data = service.get_graph("test-kb")
    assert isinstance(data, dict)
    assert "graph" in data
    assert "insights" in data
    assert "nodes" in data["graph"]
    assert "links" in data["graph"]


@pytest.mark.asyncio
async def test_cascade_delete_async(temp_kb):
    src_file = "test-source.txt"
    src_path = os.path.join(temp_kb, "raw", "sources", src_file)
    os.makedirs(os.path.dirname(src_path), exist_ok=True)
    with open(src_path, "w") as f:
        f.write("test content")
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    service.write_page("test-kb", "entities", "from-source", "Content from source.", {
        "title": "From Source",
        "sources": [src_file],
    })
    modified = await service.cascade_delete("test-kb", src_file)
    assert isinstance(modified, list)
    # Verify source file was removed
    assert not os.path.exists(src_path)
    # Verify page no longer references the source
    page = service.read("test-kb", "entities", "from-source")
    assert page is not None
    assert src_file not in page["content"]


@pytest.mark.asyncio
async def test_run_dedup_no_llm_skips(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    result = await service.run_dedup("test-kb", None)
    assert isinstance(result, dict)
    assert "merged" in result
