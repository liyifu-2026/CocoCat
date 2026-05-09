"""Tests for KB pipeline — parser, sanitizer, cache."""
import os
import tempfile
import pytest
from cococat.ingest.parser import parse_file_blocks, is_safe_ingest_path
from cococat.ingest.sanitize import sanitize_frontmatter
from cococat.ingest.cache import IngestCache
from cococat.ingest.ingest import IngestPipeline
from cococat.ingest.merge import parse_frontmatter, write_frontmatter, merge_frontmatter_arrays, backup_page


# ── Page Merge ──

def test_parse_frontmatter():
    content = "---\ntype: entity\ntitle: Test\n---\n\n# Body\nContent."
    fm, body = parse_frontmatter(content)
    assert fm["type"] == "entity"
    assert fm["title"] == "Test"
    assert "Body" in body


def test_parse_frontmatter_no_fm():
    content = "# Just a heading\nContent."
    fm, body = parse_frontmatter(content)
    assert fm == {}
    assert body == content


def test_write_frontmatter_roundtrip():
    fm = {"type": "entity", "title": "Test", "tags": ["a", "b"]}
    body = "# Test\nContent."
    result = write_frontmatter(fm, body)
    parsed_fm, parsed_body = parse_frontmatter(result)
    assert parsed_fm["type"] == "entity"
    assert "Content" in parsed_body


def test_merge_frontmatter_arrays():
    old_fm = {"type": "entity", "title": "Old", "created": "2026-01-01",
              "sources": ["a.md"], "tags": ["x"], "related": ["y"]}
    new_fm = {"type": "concept", "title": "New",
              "sources": ["b.md"], "tags": ["z"], "related": ["w"]}

    merged = merge_frontmatter_arrays(old_fm, new_fm)

    # Locked fields preserved from old
    assert merged["type"] == "entity"
    assert merged["title"] == "Old"
    assert merged["created"] == "2026-01-01"

    # Arrays unioned
    assert set(merged["sources"]) == {"a.md", "b.md"}
    assert set(merged["tags"]) == {"x", "z"}
    assert set(merged["related"]) == {"y", "w"}

    # Updated timestamp
    assert "updated" in merged


def test_backup_page_creates_backup():
    with tempfile.TemporaryDirectory() as d:
        page = os.path.join(d, "test.md")
        backup_dir = os.path.join(d, ".backups")
        with open(page, "w") as f:
            f.write("original content")

        backup = backup_page(page, backup_dir)
        assert backup is not None
        assert os.path.exists(backup)
        with open(backup) as f:
            assert f.read() == "original content"


# ── Dedup ──

from cococat.ingest.dedup import DedupPipeline


class DedupLLM:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, tools=None, **kwargs):
        content = messages[-1]["content"]
        self.calls.append(content[:100])
        if "Identify groups" in content:
            return {"content": json.dumps([["page-a", "page-a-dup"]])}
        return {"content": "# Merged Page\nCombined content."}


@pytest.mark.asyncio
async def test_dedup_summarize():
    with tempfile.TemporaryDirectory() as d:
        wiki_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(wiki_dir)
        with open(os.path.join(wiki_dir, "page-a.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Page A\nsummary: First page\n---\nContent A")
        with open(os.path.join(wiki_dir, "page-b.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Page B\n---\nContent B")

        pipeline = DedupPipeline(DedupLLM(), d)
        pages = pipeline._summarize_all()
        assert len(pages) == 2
        slugs = {p["slug"] for p in pages}
        assert slugs == {"page-a", "page-b"}


# ── Cascade Deletion ──

from cococat.ingest.cascade import cascade_delete_source


def test_cascade_delete_removes_source_ref():
    with tempfile.TemporaryDirectory() as d:
        # Create wiki page referencing source
        entities_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entities_dir)
        page = os.path.join(entities_dir, "test-entity.md")
        with open(page, "w") as f:
            f.write("---\ntype: entity\nsources: [test-source.md]\n---\n# Test\nSee [[test-entity]] for more.")

        # Create source file
        src_dir = os.path.join(d, "raw", "sources")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "test-source.md"), "w") as f:
            f.write("source")

        import asyncio
        modified = asyncio.run(cascade_delete_source("test-source.md", d))

        assert len(modified) >= 1
        # Verify source removed from frontmatter
        with open(page) as f:
            content = f.read()
        assert "test-source.md" not in content or "sources: []" in content


def test_cascade_delete_removes_related():
    with tempfile.TemporaryDirectory() as d:
        entities_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entities_dir)

        page_a = os.path.join(entities_dir, "page-a.md")
        with open(page_a, "w") as f:
            f.write("---\ntype: entity\nsources: [src.md]\n---\n# A")

        src_dir = os.path.join(d, "raw", "sources")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "src.md"), "w") as f:
            f.write("source")

        import asyncio
        modified = asyncio.run(cascade_delete_source("src.md", d))

        # Source should be deleted
        assert not os.path.exists(os.path.join(src_dir, "src.md"))
        # Page A should still exist but source ref removed
        assert os.path.exists(page_a)
        with open(page_a) as f:
            assert "src.md" not in f.read()


# ── Overview + Lint ──

from cococat.ingest.overview import update_overview, lint_kb


def test_update_overview_without_llm():
    with tempfile.TemporaryDirectory() as d:
        entities_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entities_dir)
        with open(os.path.join(entities_dir, "page-a.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Page A\nsummary: First page\n---\n# A")

        import asyncio
        overview = asyncio.run(update_overview(d))
        assert "Page A" in overview
        assert os.path.exists(os.path.join(d, "overview.md"))


def test_lint_finds_broken_links():
    with tempfile.TemporaryDirectory() as d:
        entities_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entities_dir)
        with open(os.path.join(entities_dir, "page-a.md"), "w") as f:
            f.write("---\ntype: entity\n---\n# A\nSee [[nonexistent]] and [[page-a]]")

        report = lint_kb(d)
        assert len(report["broken_links"]) >= 1
        assert report["broken_links"][0]["to"] == "nonexistent"


def test_lint_finds_orphans():
    with tempfile.TemporaryDirectory() as d:
        entities_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entities_dir)
        with open(os.path.join(entities_dir, "orphan.md"), "w") as f:
            f.write("---\ntype: entity\n---\n# Orphan")

        report = lint_kb(d)
        assert len(report["orphans"]) >= 1
        assert report["orphans"][0]["slug"] == "orphan"


# ── Knowledge Graph ──

from cococat.ingest.graph import KnowledgeGraph


def test_graph_builds_from_wiki():
    with tempfile.TemporaryDirectory() as d:
        entities_dir = os.path.join(d, "wiki", "entities")
        concepts_dir = os.path.join(d, "wiki", "concepts")
        os.makedirs(entities_dir)
        os.makedirs(concepts_dir)

        # Pages with cross-references
        with open(os.path.join(entities_dir, "a.md"), "w") as f:
            f.write("---\ntype: entity\nsources: [src.md]\n---\n# A\nSee [[b]]")
        with open(os.path.join(entities_dir, "b.md"), "w") as f:
            f.write("---\ntype: entity\nsources: [src.md]\n---\n# B\nSee [[a]]")
        with open(os.path.join(concepts_dir, "c.md"), "w") as f:
            f.write("---\ntype: concept\n---\n# C\nSee [[a]] and [[b]]")

        graph = KnowledgeGraph(d)
        assert len(graph._pages) == 3

        # a and b share source + cross-link → strong edge
        assert ("a", "b") in graph._edges or ("b", "a") in graph._edges

        insights = graph.insights()
        assert "connections" in insights
        assert "gaps" in insights
        assert "bridges" in insights


def test_graph_to_d3():
    with tempfile.TemporaryDirectory() as d:
        entities_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entities_dir)
        with open(os.path.join(entities_dir, "x.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: X\n---\n# X\n[[y]]")
        with open(os.path.join(entities_dir, "y.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Y\n---\n# Y")

        graph = KnowledgeGraph(d)
        d3 = graph.to_d3()
        assert len(d3["nodes"]) == 2
        assert len(d3["links"]) >= 1


# ── Image Pipeline ──

from cococat.ingest.image import ImagePipeline


def test_image_pipeline_find_images():
    with tempfile.TemporaryDirectory() as d:
        # Create some image files
        with open(os.path.join(d, "chart.png"), "w") as f:
            f.write("fake png")
        with open(os.path.join(d, "document.md"), "w") as f:
            f.write("not an image")
        with open(os.path.join(d, "photo.jpg"), "w") as f:
            f.write("fake jpg")

        pipeline = ImagePipeline()
        images = pipeline.find_images(d)
        assert len(images) == 2
        assert any("chart.png" in i for i in images)


def test_image_cache_hit():
    with tempfile.TemporaryDirectory() as d:
        # Create image
        img_path = os.path.join(d, "test.png")
        with open(img_path, "wb") as f:
            f.write(b"test image bytes")

        pipeline = ImagePipeline(kb_dir=d)
        h = pipeline.hash_image(img_path)
        assert h is not None

        pipeline.set_cached_caption(h, "A test chart")
        cached = pipeline.get_cached_caption(h)
        assert cached == "A test chart"


def test_image_cache_miss():
    pipeline = ImagePipeline()
    assert pipeline.get_cached_caption("nonexistent_hash") is None


class FakeLLM:
    def __init__(self, analysis: str = "Analysis: test entity found.", 
                 generation: str = ""):
        self.analysis = analysis
        self.generation = generation or (
            "---FILE:wiki/entities/test-entity.md---\n"
            "---\ntype: entity\ntitle: Test Entity\n---\n# Test\nContent.\n---END FILE---\n"
        )
        self.calls = []

    async def chat(self, messages, tools=None, **kwargs):
        content = messages[-1]["content"]
        self.calls.append(content[:100])
        if "research analyst" in content.lower():
            return {"content": self.analysis}
        return {"content": self.generation}


@pytest.fixture
def kb_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.mark.asyncio
async def test_two_phase_ingest_creates_wiki_page(kb_dir):
    # Create source file
    src_dir = os.path.join(kb_dir, "raw", "sources")
    os.makedirs(src_dir)
    with open(os.path.join(src_dir, "test.md"), "w") as f:
        f.write("# Test Source\nThis is a test document.")

    llm = FakeLLM()
    pipeline = IngestPipeline(llm, kb_dir)

    result = await pipeline.ingest("test.md", kb_name="test-kb")
    assert result.written_files
    assert any("test-entity.md" in f for f in result.written_files)
    assert llm.calls  # At least one LLM call happened


@pytest.mark.asyncio
async def test_ingest_cache_hit_skips_llm(kb_dir):
    src_dir = os.path.join(kb_dir, "raw", "sources")
    os.makedirs(src_dir)
    with open(os.path.join(src_dir, "test.md"), "w") as f:
        f.write("cached content")

    llm = FakeLLM()
    pipeline = IngestPipeline(llm, kb_dir)

    # First ingest
    await pipeline.ingest("test.md", kb_name="test-kb")
    call_count = len(llm.calls)

    # Second ingest — should hit cache
    await pipeline.ingest("test.md", kb_name="test-kb")
    assert len(llm.calls) == call_count  # No new LLM calls


@pytest.mark.asyncio
async def test_ingest_updates_index(kb_dir):
    src_dir = os.path.join(kb_dir, "raw", "sources")
    os.makedirs(src_dir)
    with open(os.path.join(src_dir, "test.md"), "w") as f:
        f.write("test content")

    llm = FakeLLM()
    pipeline = IngestPipeline(llm, kb_dir)
    await pipeline.ingest("test.md", kb_name="test-kb")

    index_path = os.path.join(kb_dir, "index.md")
    assert os.path.exists(index_path)
    with open(index_path) as f:
        content = f.read()
    assert "test-entity" in content


# ── Parser ──

def test_parse_single_file_block():
    text = """Here is the analysis.

---FILE:wiki/entities/test.md---
---
type: entity
title: Test
---
# Test
Content here.
---END FILE---"""
    blocks = parse_file_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].path == "wiki/entities/test.md"
    assert "type: entity" in blocks[0].content


def test_parse_multiple_blocks():
    text = """---FILE:wiki/entities/a.md---
content a
---END FILE---
---FILE:wiki/concepts/b.md---
content b
---END FILE---"""
    blocks = parse_file_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].path == "wiki/entities/a.md"
    assert blocks[1].path == "wiki/concepts/b.md"


def test_parse_rejects_path_traversal():
    assert not is_safe_ingest_path("../outside.md")
    assert not is_safe_ingest_path("wiki/../../etc/passwd")
    assert is_safe_ingest_path("wiki/entities/test.md")


def test_parse_blocks_exclude_unsafe_paths():
    text = """---FILE:wiki/entities/ok.md---
safe
---END FILE---
---FILE:../malicious.md---
unsafe
---END FILE---"""
    blocks = parse_file_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].path == "wiki/entities/ok.md"


def test_parse_handles_code_fences():
    text = """---FILE:wiki/test.md---
```yaml
---FILE:nope.md---
this is inside a code fence
---END FILE---
```
real content
---END FILE---"""
    blocks = parse_file_blocks(text)
    assert len(blocks) == 1  # "nope.md" inside code fence → excluded
    assert blocks[0].path == "wiki/test.md"


# ── Sanitizer ──

def test_sanitize_strips_code_fence_wrapper():
    content = '```yaml\n---\ntype: entity\ntitle: Test\n---\n```\n\n# Body'
    cleaned = sanitize_frontmatter(content)
    assert cleaned.startswith("---\ntype:")
    assert "```yaml" not in cleaned
    assert "# Body" in cleaned


def test_sanitize_fixes_frontmatter_prefix():
    content = "frontmatter:\n  type: entity\n  title: Test"
    cleaned = sanitize_frontmatter(content)
    assert cleaned.startswith("---\ntype: entity")
    assert "frontmatter:" not in cleaned


def test_sanitize_fixes_wikilink_yaml():
    content = "---\ntype: entity\nrelated: [[a]], [[b]], [[c]]\n---\n\n# Body"
    cleaned = sanitize_frontmatter(content)
    assert "related:" in cleaned
    assert "[a, b, c]" in cleaned


# ── Cache ──

def test_cache_hit_returns_file_list():
    with tempfile.TemporaryDirectory() as d:
        cache_dir = os.path.join(d, ".llm-wiki")
        cache = IngestCache(cache_dir)

        # Create actual files
        os.makedirs(os.path.join(d, "wiki", "entities"), exist_ok=True)
        os.makedirs(os.path.join(d, "wiki", "concepts"), exist_ok=True)
        for p in ["wiki/entities/x.md", "wiki/concepts/y.md"]:
            with open(os.path.join(d, p), "w") as f:
                f.write("content")

        cache.set("abc123", [
            os.path.join(d, "wiki/entities/x.md"),
            os.path.join(d, "wiki/concepts/y.md"),
        ])

        files = cache.get("abc123")
        assert files is not None


def test_cache_miss_returns_none():
    with tempfile.TemporaryDirectory() as d:
        cache = IngestCache(os.path.join(d, ".llm-wiki"))
        assert cache.get("nonexistent") is None


def test_cache_hit_but_file_missing_returns_none():
    with tempfile.TemporaryDirectory() as d:
        cache = IngestCache(os.path.join(d, ".llm-wiki"))
        cache.set("hash1", ["nonexistent.md"])
        assert cache.get("hash1") is None  # File doesn't exist on disk


# ── Cascade Deletion ──

def test_find_pages_by_source():
    from cococat.ingest.cascade import _find_pages_by_source
    with tempfile.TemporaryDirectory() as d:
        wiki_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(wiki_dir)
        path1 = os.path.join(wiki_dir, "page1.md")
        path2 = os.path.join(wiki_dir, "page2.md")
        with open(path1, "w") as f:
            f.write("---\ntype: entity\nsources:\n  - source-a.md\n---\n# P1")
        with open(path2, "w") as f:
            f.write("---\ntype: entity\nsources:\n  - source-b.md\n---\n# P2")

        result = _find_pages_by_source("source-a.md", d)
        assert len(result) == 1
        assert "page1.md" in result[0]


def test_find_pages_by_source_none():
    from cococat.ingest.cascade import _find_pages_by_source
    with tempfile.TemporaryDirectory() as d:
        result = _find_pages_by_source("nonexistent.md", d)
        assert result == []


def test_remove_wikilink():
    from cococat.ingest.cascade import _remove_wikilink
    body = "See [[refund-policy]] for details. Also [[faq]] and [[refund-policy]] again."
    result = _remove_wikilink(body, "refund-policy")
    assert "[[refund-policy]]" not in result
    assert "[[faq]]" in result  # Other wikilinks preserved


def test_cascade_update_index_remove():
    from cococat.ingest.cascade import _update_index_remove
    with tempfile.TemporaryDirectory() as d:
        index_path = os.path.join(d, "index.md")
        with open(index_path, "w") as f:
            f.write("# Index\n- page-a\n- page-b\n- page-c\n")

        _update_index_remove({"page-b"}, d)
        with open(index_path) as f:
            content = f.read()
        assert "page-a" in content
        assert "page-b" not in content
        assert "page-c" in content


# ── Dedup ──

def test_dedup_summarize_all():
    from cococat.ingest.dedup import DedupPipeline

    class FakeLLM: pass

    with tempfile.TemporaryDirectory() as d:
        entity_dir = os.path.join(d, "wiki", "entities")
        concept_dir = os.path.join(d, "wiki", "concepts")
        os.makedirs(entity_dir)
        os.makedirs(concept_dir)
        with open(os.path.join(entity_dir, "refund.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Refund\ntags: [finance]\nsummary: Refund process\n---\n# Refund")
        with open(os.path.join(concept_dir, "policy.md"), "w") as f:
            f.write("---\ntype: concept\ntitle: Policy\ntags: [rules]\n---\n# Policy")

        dp = DedupPipeline(FakeLLM(), d)
        pages = dp._summarize_all()
        assert len(pages) == 2
        slugs = {p["slug"] for p in pages}
        assert slugs == {"refund", "policy"}


def test_dedup_is_known_non_duplicate():
    from cococat.ingest.dedup import DedupPipeline

    class FakeLLM: pass

    with tempfile.TemporaryDirectory() as d:
        dp = DedupPipeline(FakeLLM(), d)
        dp._not_duplicates = {("a", "b")}

        assert dp._is_known_non_duplicate(["a", "b"]) is True
        assert dp._is_known_non_duplicate(["b", "a"]) is True  # Order doesn't matter
        assert dp._is_known_non_duplicate(["a", "c"]) is False
        assert dp._is_known_non_duplicate(["a"]) is False  # Single entry


def test_dedup_load_save_not_duplicates():
    from cococat.ingest.dedup import DedupPipeline

    class FakeLLM: pass

    with tempfile.TemporaryDirectory() as d:
        llm_wiki_dir = os.path.join(d, ".llm-wiki")
        os.makedirs(llm_wiki_dir)
        path = os.path.join(llm_wiki_dir, "dedup-not-duplicates.json")
        import json
        with open(path, "w") as f:
            json.dump([["a", "b"], ["c", "d"]], f)

        dp = DedupPipeline(FakeLLM(), d)
        assert ("a", "b") in dp._not_duplicates
        assert ("c", "d") in dp._not_duplicates


def test_dedup_update_index_remove():
    from cococat.ingest.dedup import DedupPipeline

    class FakeLLM: pass

    with tempfile.TemporaryDirectory() as d:
        dp = DedupPipeline(FakeLLM(), d)
        index_path = os.path.join(d, "index.md")
        with open(index_path, "w") as f:
            f.write("- slug-a\n- slug-b\n- slug-c\n- slug-d\n")

        dp._update_index_remove({"slug-b", "slug-d"})
        with open(index_path) as f:
            content = f.read()
        assert "slug-a" in content
        assert "slug-b" not in content
        assert "slug-c" in content
        assert "slug-d" not in content


# ── Overview ──

def test_update_overview_no_llm():
    from cococat.ingest.overview import update_overview

    with tempfile.TemporaryDirectory() as d:
        entity_dir = os.path.join(d, "wiki", "entities")
        concept_dir = os.path.join(d, "wiki", "concepts")
        os.makedirs(entity_dir)
        os.makedirs(concept_dir)
        with open(os.path.join(entity_dir, "refund.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Refund\nsummary: Process\n---\n# Refund")
        with open(os.path.join(concept_dir, "policy.md"), "w") as f:
            f.write("---\ntype: concept\ntitle: Policy\n---\n# Policy")

        import asyncio
        result = asyncio.run(update_overview(d, llm=None))
        assert "Refund" in result
        assert "Policy" in result
        overview_path = os.path.join(d, "overview.md")
        assert os.path.exists(overview_path)


def test_lint_kb():
    from cococat.ingest.overview import lint_kb

    with tempfile.TemporaryDirectory() as d:
        entity_dir = os.path.join(d, "wiki", "entities")
        os.makedirs(entity_dir)
        # Page with broken link + missing type
        with open(os.path.join(entity_dir, "page1.md"), "w") as f:
            f.write("---\ntitle: Page1\n---\nSee [[page2]] for more.")
        # Page with no issues
        with open(os.path.join(entity_dir, "page2.md"), "w") as f:
            f.write("---\ntype: entity\ntitle: Page2\n---\n# P2")

        result = lint_kb(d)
        # page1 has broken link to page2? No — page2 exists. But page2 doesn't link to page1.
        # page1 has no type → missing_fm
        assert len(result["missing_fm"]) == 1
        assert result["missing_fm"][0]["slug"] == "page1"
        # page2 should be orphan (no inbound links, no page1 → page2 is a valid link)
        assert len(result["broken_links"]) == 0  # page2 exists
        # page2 is orphan (no one links to it from page1? page1 does link)
        # page1 links to page2 via [[page2]], so page2 has inbound link from page1
        orphans = [o["slug"] for o in result["orphans"]]
        assert "page2" not in orphans  # page1 links to it
