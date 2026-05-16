"""Page merge — frontmatter union + LLM body merge + history backup."""

from __future__ import annotations

import logging
import os
import re
import shutil
import yaml
from datetime import datetime
from typing import Any

logger = logging.getLogger("cococat.ingest.merge")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from wiki page content. Returns (frontmatter, body)."""
    match = _FRONTMATTER_RE.match(content)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = content[match.end():]
        return fm, body
    return {}, content


def write_frontmatter(fm: dict, body: str) -> str:
    """Write YAML frontmatter + body back to string."""
    fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{fm_str}\n---\n\n{body.strip()}"


def merge_frontmatter_arrays(old_fm: dict, new_fm: dict) -> dict:
    """Union frontmatter array fields (sources, tags, related).

    Deterministic — no LLM needed. Preserves locked fields (type, title, created).
    """
    merged = dict(new_fm)

    # Preserve locked fields from existing page
    for field in ("type", "title", "created"):
        if field in old_fm:
            merged[field] = old_fm[field]

    # Union array fields
    for field in ("sources", "tags", "related"):
        old_arr = old_fm.get(field, []) or []
        new_arr = new_fm.get(field, []) or []
        merged[field] = sorted(set(old_arr + new_arr))

    # Always update 'updated' timestamp
    merged["updated"] = datetime.now().strftime("%Y-%m-%d")

    return merged


def backup_page(file_path: str, backup_dir: str) -> str | None:
    """Save a pre-merge snapshot of a file. Returns backup path or None."""
    if not os.path.exists(file_path):
        return None

    os.makedirs(backup_dir, exist_ok=True)
    safe_name = file_path.replace("/", "_").replace("\\", "_")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"{safe_name}-{ts}.md")

    shutil.copy2(file_path, backup_path)
    logger.debug("Backed up %s → %s", file_path, backup_path)
    return backup_path


async def merge_page(
    existing_path: str,
    new_content: str,
    llm: Any,
    backup_dir: str = ".llm-wiki/page-history",
) -> str:
    """Merge new content into an existing wiki page.

    1. Parse frontmatter from both
    2. Union frontmatter arrays (deterministic)
    3. If bodies differ, LLM merge
    4. Sanity check: result ≥ 70% of max(old, new) length
    5. Backup old version before writing
    """
    # Read existing
    with open(existing_path, encoding="utf-8") as f:
        old_content = f.read()

    old_fm, old_body = parse_frontmatter(old_content)
    new_fm, new_body = parse_frontmatter(new_content)

    # Frontmatter union
    merged_fm = merge_frontmatter_arrays(old_fm, new_fm)

    # Body merge
    if new_body.strip() == old_body.strip():
        merged_body = old_body  # No change needed
    elif not old_body.strip():
        merged_body = new_body  # New page, just use new body
    elif not new_body.strip():
        merged_body = old_body  # Nothing new to add
    else:
        # LLM merge
        merged_body = await _llm_merge_bodies(old_body, new_body, llm)

        # Sanity check
        max_len = max(len(old_body), len(new_body))
        if len(merged_body) < max_len * 0.7:
            logger.warning("LLM merge result too short, using old body + new body")
            merged_body = old_body + "\n\n## Updates\n" + new_body

    # Backup
    backup_page(existing_path, backup_dir)

    # Write
    result = write_frontmatter(merged_fm, merged_body)
    return result


async def _llm_merge_bodies(old_body: str, new_body: str, llm: Any) -> str:
    """Use LLM to intelligently merge two wiki page bodies."""
    prompt = f"""Merge these two wiki page bodies. Combine information coherently.
Keep the structure of the existing page. Add new information from the new version.
Remove duplicate information. Preserve wikilinks.

EXISTING PAGE:
{old_body[:3000]}

NEW VERSION:
{new_body[:3000]}

MERGED:"""

    try:
        result = await llm.chat(messages=[{"role": "user", "content": prompt}])
        return result.content or ""
    except Exception:
        logger.exception("LLM body merge failed")
        return old_body + "\n\n## Updates\n" + new_body
