"""KB Indexer — inverted index with CJK bigram + ASCII word tokenization."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize text: CJK → 2-gram, ASCII → word split, lowercase."""
    tokens: list[str] = []
    pos = 0
    for m in _CJK_RE.finditer(text):
        if m.start() > pos:
            ascii_part = text[pos:m.start()]
            tokens.extend(t.lower() for t in _WORD_RE.findall(ascii_part))
        cjk = m.group()
        for i in range(len(cjk) - 1):
            tokens.append(cjk[i:i + 2])
        if len(cjk) == 1:
            tokens.append(cjk)
        pos = m.end()
    if pos < len(text):
        tokens.extend(t.lower() for t in _WORD_RE.findall(text[pos:]))
    return tokens


def _load_page(path: str) -> dict[str, Any] | None:
    """Load a wiki page and extract frontmatter + body."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read(10000)
    except OSError:
        return None
    fm: dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            try:
                import yaml
                fm = yaml.safe_load(raw[3:end]) or {}
            except Exception:
                pass
            body = raw[end + 3:]
    return {
        "title": fm.get("title", ""),
        "tags": fm.get("tags", []) or [],
        "source": fm.get("source", ""),
        "body": body.strip(),
    }


class KBIndex:
    """Per-KB inverted index for fast full-text search."""

    def __init__(self, kb_path: str):
        self._kb_path = kb_path
        self._index_path = os.path.join(kb_path, ".search-index.json")
        self._pages: dict[str, dict] = {}
        self._inverted: dict[str, list[str]] = {}
        self._mtime: float = 0
        self._load()

    def _load(self) -> None:
        """Load cached index if fresh, otherwise rebuild."""
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("version") == 1:
                    self._pages = data.get("pages", {})
                    self._inverted = data.get("inverted", {})
                    self._mtime = data.get("_mtime", 0)
                    if not self._is_stale():
                        return
            except (json.JSONDecodeError, KeyError):
                pass
        self.rebuild()

    def _is_stale(self) -> bool:
        """Check if any wiki page is newer than cached index."""
        wiki_dir = os.path.join(self._kb_path, "wiki")
        if not os.path.isdir(wiki_dir):
            return False
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if fname.endswith(".md"):
                    try:
                        mtime = os.path.getmtime(os.path.join(root, fname))
                        if mtime > self._mtime:
                            return True
                    except OSError:
                        pass
        return False

    def rebuild(self) -> None:
        """Walk wiki pages, tokenize, build inverted index."""
        self._pages = {}
        self._inverted = {}
        wiki_dir = os.path.join(self._kb_path, "wiki")
        if not os.path.isdir(wiki_dir):
            self._save()
            return

        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                page = _load_page(path)
                if not page:
                    continue
                slug = fname[:-3]
                rel = os.path.relpath(root, wiki_dir)
                page_id = f"{rel}/{slug}"

                tokens = tokenize(page["title"]) + tokenize(page["body"])
                seen: set[str] = set()
                for t in tokens:
                    if t not in seen:
                        seen.add(t)
                        self._inverted.setdefault(t, []).append(page_id)

                self._pages[page_id] = {
                    "name": slug,
                    "title": page["title"],
                    "tags": page.get("tags", []),
                    "source": page.get("source", ""),
                }

        self._save()

    def _save(self) -> None:
        """Persist index to disk."""
        self._mtime = time.time()
        data = {
            "version": 1,
            "pages": self._pages,
            "inverted": self._inverted,
            "_mtime": self._mtime,
        }
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def search(
        self,
        query: str | list[str],
        mode: str = "and",
        page_type: str | None = None,
        tag: str | None = None,
        source: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search the index. Returns ranked results with snippets."""
        if isinstance(query, list):
            query_terms = []
            for q in query:
                query_terms.extend(tokenize(q))
        else:
            if "|" in query or "&" in query:
                parts = re.split(r"\s*[|&]\s*", query)
                query_terms = []
                for p in parts:
                    query_terms.extend(tokenize(p))
                if "|" in query and "&" not in query:
                    mode = "or"
            else:
                query_terms = tokenize(query)

        if not query_terms:
            return []

        query_terms = list(dict.fromkeys(query_terms))
        page_hits: dict[str, tuple[set[str], int]] = {}

        for term in query_terms:
            for page_id in self._inverted.get(term, []):
                if page_id not in page_hits:
                    page_hits[page_id] = (set(), 0)
                matched, count = page_hits[page_id]
                matched.add(term)
                page_hits[page_id] = (matched, count + 1)

        scored = []
        for page_id, (matched, count) in page_hits.items():
            if mode == "and" and len(matched) < len(query_terms):
                continue
            score = count / max(1, len(self._pages.get(page_id, {}).get("name", "")))
            scored.append((score, page_id, matched))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, page_id, matched in scored[:limit]:
            info = self._pages.get(page_id, {})
            slug = info.get("name", page_id)
            page_type_str = page_id.split("/")[0] if "/" in page_id else ""
            tags = info.get("tags", [])
            source_val = info.get("source", "")

            if page_type and page_type_str != page_type:
                continue
            if tag and tag not in tags:
                continue
            if source and source_val != source:
                continue

            snippet = self._make_snippet(page_id, matched)

            results.append({
                "name": slug,
                "title": info.get("title", slug),
                "type": page_type_str,
                "tags": tags,
                "source": source_val,
                "score": round(score, 3),
                "matched_tokens": sorted(matched),
                "snippet": snippet,
            })

        return results[:limit]

    def _make_snippet(self, page_id: str, matched_tokens: set[str]) -> str:
        """Generate a snippet with **highlighted** matched tokens around the first match."""
        parts = page_id.split("/", 1)
        wiki_dir = os.path.join(self._kb_path, "wiki")
        path = os.path.join(wiki_dir, parts[0], f"{parts[1]}.md") if len(parts) > 1 else os.path.join(wiki_dir, f"{page_id}.md")
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read(5000)
        except OSError:
            return ""

        lower = content.lower()
        best_idx = len(content)
        for t in matched_tokens:
            idx = lower.find(t.lower())
            if idx != -1 and idx < best_idx:
                best_idx = idx

        if best_idx >= len(content):
            return content[:200].strip()

        start = max(0, best_idx - 60)
        end = min(len(content), best_idx + 160)
        snippet = content[start:end].strip()

        for t in sorted(matched_tokens, key=lambda x: -len(x)):
            pattern = re.compile(re.escape(t), re.IGNORECASE)
            snippet = pattern.sub(f"**{t}**", snippet)

        return snippet
