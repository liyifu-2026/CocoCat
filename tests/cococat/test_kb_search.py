"""Tests for KB indexer and search."""
import os
import tempfile
import pytest
from cococat.kb.indexer import tokenize, KBIndex


def _make_test_kb(tmpdir: str) -> KBIndex:
    """Create a test KB with two pages and return its index."""
    wiki = os.path.join(tmpdir, "wiki")
    entities = os.path.join(wiki, "entities")
    concepts = os.path.join(wiki, "concepts")
    os.makedirs(entities)
    os.makedirs(concepts)

    with open(os.path.join(entities, "fast-startup.md"), "w", encoding="utf-8") as f:
        f.write("---\ntitle: Fast Startup\ntags: [performance, latency]\nsource: benchmark.md\n---\n\n毫秒级冷启动性能优化\nFast cold startup performance optimization\n")

    with open(os.path.join(concepts, "caching.md"), "w", encoding="utf-8") as f:
        f.write("---\ntitle: Caching Strategy\ntags: [performance, cache]\n---\n\n缓存策略概述\nCaching strategy overview\n")

    return KBIndex(tmpdir)


def test_tokenize_chinese():
    tokens = tokenize("性能优化测试")
    assert "性能" in tokens
    assert "优化" in tokens
    assert "测试" in tokens


def test_tokenize_english():
    tokens = tokenize("hello world")
    assert "hello" in tokens
    assert "world" in tokens


def test_tokenize_mixed():
    tokens = tokenize("CocoCat v2 性能测试")
    assert "cococat" in tokens
    assert "v2" in tokens
    assert "性能" in tokens


def test_index_build_and_search():
    with tempfile.TemporaryDirectory() as d:
        idx = _make_test_kb(d)

        # Single keyword
        results = idx.search("性能")
        assert len(results) >= 1
        names = {r["name"] for r in results}
        assert "fast-startup" in names or "caching" in names

        # Multi-keyword AND via array
        results = idx.search(["caching", "strategy"])
        assert len(results) >= 1

        # Multi-keyword OR
        results = idx.search("caching|nonexistent", mode="or")
        assert len(results) >= 1

        # Filter by type
        results = idx.search("性能", page_type="entities")
        for r in results:
            assert r["type"] == "entities"

        # Filter by tag
        results = idx.search("性能", tag="latency")
        assert len(results) >= 1
        for r in results:
            assert "latency" in r.get("tags", [])


def test_snippet_highlight():
    with tempfile.TemporaryDirectory() as d:
        idx = _make_test_kb(d)
        results = idx.search("冷启动")
        assert len(results) >= 1
        snippet = results[0]["snippet"]
        assert "**" in snippet  # has highlighting


def test_match_tokens():
    with tempfile.TemporaryDirectory() as d:
        idx = _make_test_kb(d)
        results = idx.search(["fast", "startup"])
        assert len(results) >= 1
        matched = results[0]["matched_tokens"]
        assert "fast" in matched
        assert "startup" in matched


def test_empty_query():
    with tempfile.TemporaryDirectory() as d:
        idx = _make_test_kb(d)
        results = idx.search("")
        assert results == []


def test_no_results():
    with tempfile.TemporaryDirectory() as d:
        idx = _make_test_kb(d)
        results = idx.search("xyzzy_nonexistent_12345")
        assert results == []


def test_score_ordering():
    with tempfile.TemporaryDirectory() as d:
        idx = _make_test_kb(d)
        results = idx.search("performance")
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]


def test_index_persistence():
    with tempfile.TemporaryDirectory() as d:
        idx1 = _make_test_kb(d)
        results1 = idx1.search("性能")
        assert len(results1) >= 1

        # Create a second index from same dir — should load from cache
        idx2 = KBIndex(d)
        results2 = idx2.search("性能")
        assert len(results2) == len(results1)
