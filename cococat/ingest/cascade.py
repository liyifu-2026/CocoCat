"""Cascade deletion — remove source → clean wiki pages + cross-references."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from cococat.ingest.merge import parse_frontmatter, write_frontmatter, backup_page, update_index_remove

logger = logging.getLogger("cococat.ingest.cascade")

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


async def cascade_delete_source(
    source_filename: str,
    kb_dir: str,
    llm: Any | None = None,
) -> list[str]:
    """Delete a source file and clean up all wiki pages referencing it.

    Returns list of files that were modified.
    """
    modified: list[str] = []

    # 1. Find all wiki pages that reference this source
    affected = _find_pages_by_source(source_filename, kb_dir)
    if not affected:
        return []

    # 2. Backup each affected page
    backup_dir = os.path.join(kb_dir, ".llm-wiki", "page-history")
    for page_path in affected:
        backup_page(page_path, backup_dir)

    # 3. Remove the source reference from each page
    slugs_to_remove = set()
    for page_path in affected:
        with open(page_path, encoding="utf-8") as f:
            content = f.read()

        fm, body = parse_frontmatter(content)

        # Remove source from sources array
        sources = fm.get("sources", []) or []
        if source_filename in sources:
            sources.remove(source_filename)
            fm["sources"] = sources

        # Remove wikilinks to removed pages
        for other_path in affected:
            other_slug = os.path.splitext(os.path.basename(other_path))[0]
            body = _remove_wikilink(body, other_slug)
            slugs_to_remove.add(other_slug)

        new_content = write_frontmatter(fm, body)
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        modified.append(page_path)

    # 4. Remove from related: arrays in all other pages
    wiki_dir = os.path.join(kb_dir, "wiki")
    if os.path.isdir(wiki_dir):
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                if path in affected:
                    continue
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                fm, body = parse_frontmatter(content)
                related = fm.get("related", []) or []
                new_related = [r for r in related if r not in slugs_to_remove]
                if len(new_related) != len(related):
                    backup_page(path, backup_dir)
                    fm["related"] = new_related
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(write_frontmatter(fm, body))
                    modified.append(path)

    # 5. Update index.md
    update_index_remove(kb_dir, slugs_to_remove)

    # 6. Delete the source file
    src_path = os.path.join(kb_dir, "raw", "sources", source_filename)
    if os.path.exists(src_path):
        os.remove(src_path)

    return modified


def _find_pages_by_source(source_filename: str, kb_dir: str) -> list[str]:
    """Find all wiki pages that list the given source in their frontmatter."""
    wiki_dir = os.path.join(kb_dir, "wiki")
    if not os.path.isdir(wiki_dir):
        return []

    results = []
    for root, _, files in os.walk(wiki_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            fm, _ = parse_frontmatter(content)
            sources = fm.get("sources", []) or []
            if source_filename in sources:
                results.append(path)
    return results


def _remove_wikilink(body: str, slug: str) -> str:
    """Remove all [[slug]] references from body text."""
    return re.sub(rf"\[\[{re.escape(slug)}\]\]", slug, body)
