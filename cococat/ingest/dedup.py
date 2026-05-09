"""Dedup pipeline — detect and merge duplicate wiki pages."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from cococat.ingest.merge import parse_frontmatter, write_frontmatter, backup_page

logger = logging.getLogger("cococat.ingest.dedup")


class DedupPipeline:
    """3-stage dedup pipeline for wiki pages.

    Stage 1: Summarize — extract (slug, title, description, tags) from every page
    Stage 2: Detect — LLM identifies groups of likely-duplicate slugs
    Stage 3: Merge — LLM merges bodies + rewrites cross-references
    """

    def __init__(self, llm: Any, kb_dir: str):
        self._llm = llm
        self._kb_dir = kb_dir
        self._not_duplicates_path = os.path.join(
            kb_dir, ".llm-wiki", "dedup-not-duplicates.json"
        )
        self._not_duplicates: set[tuple[str, str]] = self._load_not_duplicates()

    def _load_not_duplicates(self) -> set[tuple[str, str]]:
        if os.path.exists(self._not_duplicates_path):
            try:
                with open(self._not_duplicates_path, encoding="utf-8") as f:
                    data = json.load(f)
                return {tuple(pair) for pair in data}
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_not_duplicates(self) -> None:
        os.makedirs(os.path.dirname(self._not_duplicates_path), exist_ok=True)
        with open(self._not_duplicates_path, "w", encoding="utf-8") as f:
            json.dump([list(p) for p in self._not_duplicates], f)

    async def run(self) -> int:
        """Run full dedup pipeline. Returns number of pages merged."""
        # Stage 1: Summarize all pages
        pages = self._summarize_all()
        if len(pages) < 2:
            return 0

        # Stage 2: Detect duplicates
        groups = await self._detect(pages)
        if not groups:
            return 0

        # Stage 3: Merge each group
        merged = 0
        for group in groups:
            if await self._merge_group(group):
                merged += len(group) - 1  # N pages → 1 keeper, N-1 removed

        return merged

    def _summarize_all(self) -> list[dict]:
        """Extract (slug, title, description, tags) from every wiki page."""
        wiki_dir = os.path.join(self._kb_dir, "wiki")
        if not os.path.isdir(wiki_dir):
            return []

        pages = []
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                with open(path, encoding="utf-8") as f:
                    fm, body = parse_frontmatter(f.read())
                slug = fname[:-3]
                rel = os.path.relpath(root, wiki_dir)
                pages.append({
                    "slug": slug,
                    "path": os.path.join(rel, fname),
                    "title": fm.get("title", slug),
                    "description": fm.get("summary", body[:200]),
                    "tags": fm.get("tags", []),
                })
        return pages

    async def _detect(self, pages: list[dict]) -> list[list[str]]:
        """LLM identifies groups of likely-duplicate page slugs."""
        catalog = "\n".join(
            f"- {p['slug']}: {p['title']} — {p['description'][:100]} [tags: {', '.join(p.get('tags', []))}]"
            for p in pages
        )

        known_non_dups = "\n".join(
            f"- {a} ≠ {b}" for a, b in self._not_duplicates
        )

        prompt = f"""Identify groups of likely-duplicate wiki pages.
Only return groups where you're confident the pages cover the same topic.

Pages:
{catalog}

Known non-duplicates (do NOT suggest these):
{known_non_dups if known_non_dups else '(none)'}

Return JSON: [["slug1", "slug2"], ["slug3", "slug4", "slug5"]]
Return empty array [] if no duplicates found."""

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            content = result.get("content", "") if isinstance(result, dict) else str(result)

            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                groups = json.loads(content[json_start:json_end])
                if isinstance(groups, list):
                    return [
                        g for g in groups
                        if isinstance(g, list) and len(g) >= 2
                        and not self._is_known_non_duplicate(g)
                    ]
        except Exception:
            logger.exception("Dedup detection failed")

        return []

    def _is_known_non_duplicate(self, group: list[str]) -> bool:
        """Check if any pair in the group is known to NOT be duplicates."""
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if (a, b) in self._not_duplicates or (b, a) in self._not_duplicates:
                    return True
        return False

    async def _merge_group(self, slugs: list[str]) -> bool:
        """Merge a group of duplicate pages. Keeps first, merges rest into it."""
        if len(slugs) < 2:
            return False

        # Find all pages in the group
        pages = self._summarize_all()
        group_pages = [p for p in pages if p["slug"] in slugs]

        keeper = group_pages[0]
        to_merge = group_pages[1:]

        keeper_path = os.path.join(self._kb_dir, "wiki", keeper["path"])
        backup_dir = os.path.join(self._kb_dir, ".llm-wiki", "page-history")

        with open(keeper_path, encoding="utf-8") as f:
            keeper_content = f.read()

        for dup in to_merge:
            dup_path = os.path.join(self._kb_dir, "wiki", dup["path"])

            with open(dup_path, encoding="utf-8") as f:
                dup_content = f.read()

            # Merge via LLM
            merged = await self._llm_merge(keeper_content, dup_content)

            # Write merged content
            with open(keeper_path, "w", encoding="utf-8") as f:
                f.write(merged)

            keeper_content = merged

            # Remove duplicate
            backup_page(dup_path, backup_dir)
            os.remove(dup_path)

        # Update index
        slugs_to_remove = set(slugs[1:])
        self._update_index_remove(slugs_to_remove)

        return True

    async def _llm_merge(self, page1: str, page2: str) -> str:
        """LLM merges two wiki pages into one."""
        prompt = f"""Merge these two wiki pages into one coherent page.
Combine all information. Remove duplicates. Preserve structure and wikilinks.
Union frontmatter fields (sources, tags, related).

PAGE 1:
{page1[:3000]}

PAGE 2:
{page2[:3000]}

MERGED:"""

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            return result.get("content", "") if isinstance(result, dict) else str(result)
        except Exception:
            return page1 + "\n\n## From merged page\n" + page2

    def _update_index_remove(self, slugs: set[str]) -> None:
        """Remove entries from index.md."""
        index_path = os.path.join(self._kb_dir, "index.md")
        if not os.path.exists(index_path):
            return
        with open(index_path, encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") and stripped[2:].strip() in slugs:
                continue
            new_lines.append(line)

        with open(index_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
