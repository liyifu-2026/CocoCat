"""KB Indexer — inverted index with CJK bigram + ASCII word tokenization, BM25 ranking, byte offsets."""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")

_STOP_CHARS = set(
    "的了的在是我有和就不人都一上也他到说来去你会着看这那他她它那们可以因所如果但而与或对被把让向将其只种些之中过为"
)
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "may", "might", "shall", "of", "to", "in", "for",
    "on", "with", "at", "by", "from", "as", "it", "and", "or", "not",
    "but", "that", "this", "these", "those",
}


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


def _tokenize_with_positions(text: str) -> list[tuple[str, int]]:
    """Tokenize text and return (token, start_char_pos) pairs."""
    results: list[tuple[str, int]] = []
    pos = 0
    for m in _CJK_RE.finditer(text):
        if m.start() > pos:
            ascii_part = text[pos:m.start()]
            for wm in _WORD_RE.finditer(ascii_part):
                results.append((wm.group().lower(), pos + wm.start()))
        cjk = m.group()
        for i in range(len(cjk) - 1):
            results.append((cjk[i:i + 2], m.start() + i))
        if len(cjk) == 1:
            results.append((cjk, m.start()))
        pos = m.end()
    if pos < len(text):
        ascii_part = text[pos:]
        for wm in _WORD_RE.finditer(ascii_part):
            results.append((wm.group().lower(), pos + wm.start()))
    return results


def _is_stop_token(token: str) -> bool:
    """Check if token should be filtered: any char is a stop char, or whole token is a stop word."""
    if token in _STOP_WORDS:
        return True
    for ch in token:
        if ch in _STOP_CHARS:
            return True
    return False


class KBIndex:
    """Per-KB inverted index for fast full-text search with BM25 ranking."""

    def __init__(self, kb_path: str):
        self._kb_path = kb_path
        self._index_path = os.path.join(kb_path, ".search-index.json")
        self._forward_path = os.path.join(kb_path, ".forward-index.json")
        self._pages: dict[str, dict] = {}
        self._inverted: dict[str, dict[str, list[int]]] = {}
        self._forward_pages: dict[str, list[str]] = {}
        self._total_docs = 0
        self._total_tokens = 0
        self._avgdl = 0.0
        self._load()

    def _page_path(self, page_id: str) -> str:
        """Convert page_id (e.g. 'entities/slug') to filesystem path."""
        parts = page_id.split("/", 1)
        wiki_dir = os.path.join(self._kb_path, "wiki")
        if len(parts) > 1:
            return os.path.join(wiki_dir, parts[0], f"{parts[1]}.md")
        return os.path.join(wiki_dir, f"{page_id}.md")

    @staticmethod
    def _page_type(page_id: str) -> str:
        """Extract page type from page_id (e.g. 'entities/slug' → 'entities')."""
        return page_id.split("/")[0] if "/" in page_id else ""

    def _load(self) -> None:
        """Load cached index and refresh if needed."""
        for p in (self._index_path + ".tmp", self._forward_path + ".tmp"):
            if os.path.exists(p):
                os.remove(p)

        loaded = False
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._pages = data.get("pages", {})
                self._inverted = data.get("inverted", {})
                self._total_docs = data.get("total_docs", 0)
                self._total_tokens = data.get("total_tokens", 0)
                self._avgdl = data.get("avgdl", 0.0)
                loaded = True
            except (json.JSONDecodeError, KeyError):
                pass

        if not loaded:
            self._rebuild_full()
        else:
            self.rebuild()

    def _save_atomic(self, path: str, data: dict) -> None:
        """Write JSON atomically via tmp file + os.replace."""
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)

    def _to_index_data(self) -> dict:
        return {
            "total_docs": self._total_docs,
            "total_tokens": self._total_tokens,
            "avgdl": self._avgdl,
            "pages": self._pages,
            "inverted": self._inverted,
        }

    def _to_forward_data(self) -> dict:
        return {
            "pages": self._forward_pages,
        }

    def _recompute_stats(self) -> None:
        self._total_docs = len(self._pages)
        self._total_tokens = sum(p.get("token_count", 0) for p in self._pages.values())
        self._avgdl = self._total_tokens / self._total_docs if self._total_docs > 0 else 0.0

    # ── rebuild ─────────────────────────────────────────

    def rebuild(self) -> None:
        """Incremental rebuild; falls back to full rebuild if forward index unavailable or inconsistent."""
        try:
            with open(self._forward_path, encoding="utf-8") as f:
                fwd = json.load(f)
            self._forward_pages = fwd.get("pages", {})
            if set(self._forward_pages) != set(self._pages):
                self._rebuild_full()
                return
            self._rebuild_incremental()
            return
        except (json.JSONDecodeError, OSError, KeyError):
            pass
        self._rebuild_full()

    def _rebuild_full(self) -> None:
        """Full rebuild from scratch — walk all wiki pages."""
        self._pages = {}
        self._inverted = {}
        self._forward_pages = {}

        wiki_dir = os.path.join(self._kb_path, "wiki")
        if not os.path.isdir(wiki_dir):
            self._total_docs = 0
            self._total_tokens = 0
            self._avgdl = 0.0
            self._save_atomic(self._index_path, self._to_index_data())
            self._save_atomic(self._forward_path, self._to_forward_data())
            return

        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                slug = fname[:-3]
                rel = os.path.relpath(root, wiki_dir)
                page_id = f"{rel}/{slug}" if rel != "." else slug
                self._add_page(page_id, mtime)

        self._recompute_stats()
        self._save_atomic(self._index_path, self._to_index_data())
        self._save_atomic(self._forward_path, self._to_forward_data())

    def _rebuild_incremental(self) -> None:
        """Incremental update: detect new/modified/deleted pages, update indexes."""
        wiki_dir = os.path.join(self._kb_path, "wiki")
        if not os.path.isdir(wiki_dir):
            self._pages = {}
            self._inverted = {}
            self._forward_pages = {}
            self._total_docs = 0
            self._total_tokens = 0
            self._avgdl = 0.0
            self._save_atomic(self._index_path, self._to_index_data())
            self._save_atomic(self._forward_path, self._to_forward_data())
            return

        current_files: dict[str, float] = {}
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                slug = fname[:-3]
                rel = os.path.relpath(root, wiki_dir)
                page_id = f"{rel}/{slug}" if rel != "." else slug
                current_files[page_id] = mtime

        new_set = set(current_files)
        old_set = set(self._pages)

        for page_id in old_set - new_set:
            self._remove_page(page_id)

        for page_id, mtime in current_files.items():
            if page_id not in self._pages or mtime > self._pages[page_id].get("mtime", 0):
                self._remove_page(page_id)
                self._add_page(page_id, mtime)

        self._recompute_stats()
        self._save_atomic(self._index_path, self._to_index_data())
        self._save_atomic(self._forward_path, self._to_forward_data())

    def _add_page(self, page_id: str, mtime: float) -> None:
        """Read a wiki page, tokenize, add to inverted + forward indexes."""
        path = self._page_path(page_id)

        try:
            with open(path, "rb") as f:
                raw_bytes = f.read()
            text = raw_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return

        fm: dict[str, Any] = {}
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                try:
                    import yaml
                    fm = yaml.safe_load(text[3:end]) or {}
                except Exception:
                    pass

        title = fm.get("title", "")
        tags = fm.get("tags", []) or []
        source = fm.get("source", "")
        if not source:
            sources_list = fm.get("sources", [])
            source = sources_list[0] if sources_list else ""

        tokens_with_pos = _tokenize_with_positions(text)

        # Precompute char→byte offsets (O(n) single pass)
        char_to_byte: list[int] = [0]
        byte_pos = 0
        for ch in text:
            char_to_byte.append(byte_pos)
            byte_pos += len(ch.encode("utf-8"))

        all_tokens: list[str] = []
        for token, char_pos in tokens_with_pos:
            if _is_stop_token(token):
                continue
            all_tokens.append(token)
            byte_offset = char_to_byte[char_pos]
            self._inverted.setdefault(token, {}).setdefault(page_id, []).append(byte_offset)

        slug = os.path.basename(page_id)

        self._pages[page_id] = {
            "name": slug,
            "title": title,
            "tags": tags,
            "source": source,
            "token_count": len(all_tokens),
            "mtime": mtime,
        }
        self._forward_pages[page_id] = all_tokens

    def _remove_page(self, page_id: str) -> None:
        """Remove a page from inverted + forward + pages indexes."""
        old_tokens = self._forward_pages.get(page_id, [])
        for token in old_tokens:
            if token in self._inverted:
                self._inverted[token].pop(page_id, None)
                if not self._inverted[token]:
                    del self._inverted[token]
        self._pages.pop(page_id, None)
        self._forward_pages.pop(page_id, None)

    # ── search ──────────────────────────────────────────

    def search(
        self,
        query: str | list[str],
        mode: str = "and",
        page_type: str | None = None,
        tag: str | None = None,
        source: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search the index with BM25 ranking. Returns [{name, title, type, tags, source, score, matched_tokens, snippet}, ...]."""
        if isinstance(query, list):
            query_terms: list[str] = []
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

        query_terms = [t for t in query_terms if not _is_stop_token(t)]
        query_terms = list(dict.fromkeys(query_terms))

        if not query_terms:
            return []

        k1 = 1.5
        b = 0.4
        N = self._total_docs
        avgdl = self._avgdl

        page_scores: dict[str, float] = {}
        page_matched: dict[str, set[str]] = {}

        for term in query_terms:
            postings = self._inverted.get(term, {})
            n = len(postings)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1) if n > 0 else 0.0

            for page_id, offsets in postings.items():
                info = self._pages.get(page_id, {})
                pg_type = self._page_type(page_id)
                pg_tags = info.get("tags", [])
                pg_source = info.get("source", "")

                # Filter before scoring — skip pages that don't match
                if page_type and pg_type != page_type:
                    continue
                if tag and tag not in pg_tags:
                    continue
                if source and pg_source != source:
                    continue

                f = len(offsets)
                dl = info.get("token_count", 1)

                # Title boost: exact token match in title → ×3, partial → ×2
                title_lower = info.get("title", "").lower()
                title_boost = 1.0
                if term.lower() in title_lower:
                    title_boost = 3.0 if f' {term.lower()} ' in f' {title_lower} ' or title_lower.startswith(term.lower()) or title_lower.endswith(term.lower()) else 2.0

                numerator = f * (k1 + 1)
                denominator = f + k1 * (1 - b + b * dl / avgdl) if avgdl > 0 else f + k1
                bm25 = idf * numerator / denominator * title_boost

                if page_id not in page_scores:
                    page_scores[page_id] = 0.0
                    page_matched[page_id] = set()
                page_scores[page_id] += bm25
                page_matched[page_id].add(term)

        scored: list[tuple[float, str, set[str]]] = []
        for page_id, score in page_scores.items():
            matched = page_matched[page_id]
            if mode == "and" and len(matched) < len(query_terms):
                continue
            scored.append((score, page_id, matched))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[dict] = []
        for score, page_id, matched in scored:
            info = self._pages.get(page_id, {})
            slug = info.get("name", page_id)
            page_type_str = self._page_type(page_id)

            snippet = self._make_snippet(page_id, matched)

            results.append({
                "name": slug,
                "title": info.get("title", slug),
                "type": page_type_str,
                "tags": info.get("tags", []),
                "source": info.get("source", ""),
                "score": round(score, 3),
                "matched_tokens": sorted(matched),
                "snippet": snippet,
            })

            if len(results) >= limit:
                break

        return results

    # ── snippet ─────────────────────────────────────────

    def _make_snippet(self, page_id: str, matched_tokens: set[str]) -> str:
        """Generate snippet with **highlighted** matched tokens. Uses byte offsets when available, falls back to text mode."""
        path = self._page_path(page_id)

        # Try byte-offset-based snippet first
        first_offset: int | None = None
        for token in matched_tokens:
            offsets = self._inverted.get(token, {}).get(page_id, [])
            if offsets:
                if first_offset is None or offsets[0] < first_offset:
                    first_offset = offsets[0]

        if first_offset is not None:
            try:
                with open(path, "rb") as f:
                    f.seek(max(0, first_offset - 150))
                    raw = f.read(400)
                for i in range(len(raw)):
                    try:
                        text = raw[i:].decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text = ""
                if text.strip():
                    for t in sorted(matched_tokens, key=lambda x: -len(x)):
                        pattern = re.compile(re.escape(t), re.IGNORECASE)
                        text = pattern.sub(f"**{t}**", text)
                    return text
            except OSError:
                pass

        # Fallback: text-mode substring snippet
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read(3000)
        except OSError:
            return ""

        lower = content.lower()
        best_idx = len(content)
        for t in matched_tokens:
            idx = lower.find(t.lower())
            if idx != -1 and idx < best_idx:
                best_idx = idx

        if best_idx < len(content):
            start = max(0, best_idx - 60)
            end = min(len(content), best_idx + 160)
            text = content[start:end].strip()
        else:
            text = content[:200].strip()

        for t in sorted(matched_tokens, key=lambda x: -len(x)):
            pattern = re.compile(re.escape(t), re.IGNORECASE)
            text = pattern.sub(f"**{t}**", text)

        return text
