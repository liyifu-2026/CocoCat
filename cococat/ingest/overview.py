"""KB overview + lint — global summary + health checks."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from cococat.ingest.merge import parse_frontmatter

logger = logging.getLogger("cococat.ingest.overview")

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


async def update_overview(kb_dir: str, llm: Any | None = None) -> str:
    """Re-generate overview.md — 2-5 paragraph global summary of all wiki content.

    If no LLM provided, generates a simple index-based overview.
    """
    wiki_dir = os.path.join(kb_dir, "wiki")
    if not os.path.isdir(wiki_dir):
        return ""

    # Collect all page summaries
    pages = []
    for root, _, files in os.walk(wiki_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            with open(path, encoding="utf-8") as f:
                fm, body = parse_frontmatter(f.read())
            pages.append({
                "slug": fname[:-3],
                "title": fm.get("title", fname[:-3]),
                "summary": fm.get("summary", body[:200]),
                "type": fm.get("type", ""),
            })

    if not pages:
        return ""

    if llm:
        catalog = "\n".join(
            f"- {p['title']} ({p['type']}): {p['summary'][:150]}"
            for p in pages
        )
        prompt = f"Write a 2-5 paragraph global summary of this knowledge base:\n\n{catalog}"
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = result.content or ""
        except Exception:
            content = f"# Overview\n\nKnowledge base with {len(pages)} pages."
    else:
        content = f"# Overview\n\nThis knowledge base contains {len(pages)} wiki pages.\n\n"
        for p in pages[:20]:
            content += f"- **{p['title']}** ({p['type']}): {p['summary'][:100]}\n"

    overview_path = os.path.join(kb_dir, "overview.md")
    with open(overview_path, "w", encoding="utf-8") as f:
        f.write(content)

    return content


def lint_kb(kb_dir: str) -> dict:
    """Run health checks on a KB wiki.

    Returns: {orphans: [...], broken_links: [...], missing_fm: [...]}
    """
    wiki_dir = os.path.join(kb_dir, "wiki")
    if not os.path.isdir(wiki_dir):
        return {"orphans": [], "broken_links": [], "missing_fm": []}

    pages: dict[str, dict] = {}  # slug → {path, fm, body, inbound_links}
    all_slugs = set()

    # First pass: collect all pages
    for root, _, files in os.walk(wiki_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            slug = fname[:-3]
            all_slugs.add(slug)

            with open(path, encoding="utf-8") as f:
                content = f.read()
            fm, body = parse_frontmatter(content)

            pages[slug] = {
                "path": path,
                "slug": slug,
                "fm": fm,
                "body": body,
                "inbound_links": set(),
            }

    # Second pass: find broken links and inbound links
    broken_links: list[dict] = []
    for slug, info in pages.items():
        # Check wikilinks in body and related
        refs = _WIKILINK_RE.findall(info["body"])
        refs += info["fm"].get("related", []) or []

        for ref in set(refs):
            if ref in all_slugs and ref != slug:
                if ref in pages:
                    pages[ref]["inbound_links"].add(slug)
            elif ref not in all_slugs:
                broken_links.append({
                    "from": slug,
                    "to": ref,
                    "path": info["path"],
                })

    # Find orphans (no inbound links)
    orphans = [
        {"slug": s, "path": i["path"]}
        for s, i in pages.items()
        if not i["inbound_links"] and not i["fm"].get("inbound_links")
    ]

    # Find missing frontmatter
    missing_fm = [
        {"slug": s, "path": i["path"]}
        for s, i in pages.items()
        if not i["fm"].get("type")
    ]

    return {
        "orphans": orphans,
        "broken_links": broken_links,
        "missing_fm": missing_fm,
    }
