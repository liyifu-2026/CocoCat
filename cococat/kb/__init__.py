"""KB package — overview injection, ingest pipeline, sanitization, caching."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("cococat.kb")


def load_kb_overview(kb_names: list[str], knowledge_dir: str = "knowledge") -> str:
    """Build a KB overview section for system prompts.

    For each KB, reads purpose.md (first 300 chars) and index.md (first 30 lines).
    Returns formatted markdown string or empty string if no KBs available.
    """
    if not kb_names:
        return ""

    sections = []
    found_any = False

    for kb_name in kb_names:
        kb_path = os.path.join(knowledge_dir, kb_name)
        if not os.path.isdir(kb_path):
            continue

        if not found_any:
            found_any = True
            sections.append("## Available Knowledge Bases\n")
            sections.append("You have access to the following knowledge bases. "
                             "Use read_file to browse their wiki pages.\n")

        sections.append(f"### {kb_name}")

        # Read purpose
        purpose_path = os.path.join(kb_path, "purpose.md")
        if os.path.exists(purpose_path):
            try:
                with open(purpose_path, encoding="utf-8") as f:
                    purpose = f.read(300)
                sections.append(f"*Purpose:* {purpose.strip()[:300]}")
            except OSError:
                pass

        # Read index (first 30 lines)
        index_path = os.path.join(kb_path, "index.md")
        if os.path.exists(index_path):
            try:
                with open(index_path, encoding="utf-8") as f:
                    index_lines = [next(f, "").rstrip() for _ in range(30)]
                index_preview = "\n".join(line for line in index_lines if line.strip())
                if index_preview:
                    sections.append(f"*Index preview:*\n```\n{index_preview[:500]}\n```")
            except (OSError, StopIteration):
                pass

        sections.append("")  # blank line between KBs

    if not found_any:
        return ""

    return "\n".join(sections)


def inject_kb_context(system_prompt: str, kb_names: list[str],
                      knowledge_dir: str = "knowledge") -> str:
    """Append KB overview to an existing system prompt."""
    overview = load_kb_overview(kb_names, knowledge_dir)
    if overview:
        return system_prompt + "\n\n" + overview
    return system_prompt
