# KB Search Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Replace substring-scan search with inverted-index + tokenization + multi-keyword + filtering.

**Architecture:** Build per-KB inverted index (stored as JSON), use 2-gram tokenization for Chinese + word-split for English, add AND/OR + type/tag filter support. Backward-compatible — existing `KBService.search()` API unchanged, search_kb tool params extended.

**Tech Stack:** Python 3.13, no new dependencies (pure Python tokenization)

---

## Design

### Tokenization Strategy

No external dependency (jieba not installed). Use bidirectional 2-gram shingling for Chinese + whitespace/word split for English/latin:

```
"性能60ms冷启动" → ["性能", "能6", "60", "0m", "ms", "s冷", "冷启", "启动"]
"hello world"    → ["hello", "world"]
"CocoCat v2"     → ["cococat", "v2"]
```

Mixed CJK + ASCII text: extract CJK runs for 2-gram, ASCII runs for word split.

### Index Structure

Per-KB index file: `knowledge/{kb_name}/.search-index.json`

```json
{
  "version": 1,
  "pages": {
    "entities/orchestrator-agent-coco": {
      "name": "Orchestrator Agent Coco",
      "tags": ["coco", "architecture"],
      "source": "test-cococat.md",
      "tokens": ["orchestrator", "agent", "coco", ...]
    }
  },
  "inverted": {
    "orchestrator": ["entities/orchestrator-agent-coco"],
    "agent": ["entities/orchestrator-agent-coco", "entities/multi-agent-architecture"],
    ...
  }
}
```

### Search Algorithm

1. Load/rebuild index if stale (file mtime check)
2. Tokenize query → query tokens
3. Support `AND` (default) via `&` separator or array input: `["性能", "60ms"]` = token1 AND token2
4. Support `OR` via `|` separator: `"性能|60ms"` = token1 OR token2
5. Look up inverted index per token → collect matching pages + hit counts
6. Rank by: (number of matching tokens / total query tokens) + per-page hit frequency
7. Filter by type/tag/source if provided
8. Return with snippet (highlighted), match fields, score

### API Changes

**`search_kb` tool** — extended params:

```
kb_name: string
query: string | string[]   # single query string or array of keywords
mode: "and" | "or"         # default "and" (only when query is array)
type: string               # optional: "entities" | "concepts"
tag: string                # optional filter
source: string             # optional filter  
limit: integer             # default 20
```

Backward compatible: existing callers using just `kb_name` + `query` work unchanged.

**`KBService.search()`** — new signature:

```python
def search(self, kb_name, query, mode="and", page_type=None, tag=None, source=None, limit=20)
```

Old callers using `search(kb_name, query)` work unchanged.

### Result Format

```json
{
  "name": "orchestrator-agent-coco",
  "title": "Orchestrator Agent Coco",
  "type": "entities",
  "tags": ["coco", "architecture"],
  "source": "test-cococat.md",
  "score": 0.85,
  "matched_tokens": ["orchestrator", "agent"],
  "snippet": "...the **orchestrator** **agent** dispatches tasks..."
}
```

---

## File Structure

```
cococat/kb/
  indexer.py          # NEW: KBIndex class (build/load/search)
  service.py          # MODIFY: use KBIndex in search()
  ...
cococat/core/tools/
  kb_tools.py         # MODIFY: extend _search_kb params
tests/cococat/
  test_kb_search.py   # NEW: index + search tests
```

---

## Task Breakdown

### Task 1: Create KBIndex class (`cococat/kb/indexer.py`)

- Tokenizer: `tokenize(text)` — CJK 2-gram + ASCII word split
- Index builder: `build_index(kb_path)` — walk wiki pages, tokenize, build inverted index
- Index loader: `load_index(kb_path)` — load or rebuild if stale
- Searcher: `search(index, query, mode, type, tag, source, limit)` — execute search
- Snippet generator: `make_snippet(content, matched_tokens)` — with `**highlight**`

### Task 2: Integrate into KBService.search() (`cococat/kb/service.py`)

- Replace substring scan with `KBIndex.search()`
- Keep backward-compatible `search(kb_name, query)` signature
- Add optional filtering params

### Task 3: Extend search_kb tool (`cococat/core/tools/kb_tools.py`)

- Accept new params: mode, type, tag, source, limit
- Forward to KBService.search()

### Task 4: Tests (`tests/cococat/test_kb_search.py`)

- Test tokenizer: Chinese, English, mixed
- Test index build and load
- Test search: single keyword, AND, OR, filter by type/tag
- Test snippet generation with highlights

### Task 5: API route update (`cococat/routes/knowledge.py`)

- Extend `/api/knowledge/{kb_name}/search` endpoint with new params

### Task 6: Index rebuild trigger

- Auto-rebuild on write_page / after ingest
- Optional manual rebuild command
