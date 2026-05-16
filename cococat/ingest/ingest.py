"""Two-phase KB ingest pipeline — llm-wiki aligned."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cococat.ingest.parser import parse_file_blocks
from cococat.ingest.sanitize import sanitize_frontmatter
from cococat.ingest.cache import IngestCache

logger = logging.getLogger("cococat.ingest")


@dataclass
class IngestResult:
    source_hash: str = ""
    written_files: list[str] = field(default_factory=list)
    skipped: bool = False


class IngestPipeline:
    """Two-phase LLM-driven KB ingestion.

    Phase 1 (Analysis): LLM reads source → structured analysis
    Phase 2 (Generation): LLM takes analysis → FILE blocks → wiki pages
    """

    def __init__(self, llm: Any, kb_dir: str):
        self._llm = llm
        self._kb_dir = kb_dir
        self._cache = IngestCache(os.path.join(kb_dir, ".llm-wiki"))

    async def ingest(self, filename: str, kb_name: str = "") -> IngestResult:
        """Ingest a source file into wiki pages.

        Returns IngestResult with list of written file paths.
        """
        # Calculate source hash
        src_path = os.path.join(self._kb_dir, "raw", "sources", filename)
        if not os.path.exists(src_path):
            logger.warning("Source not found: %s", src_path)
            return IngestResult()

        with open(src_path, encoding="utf-8") as f:
            source_content = f.read()

        content_hash = hashlib.sha256(source_content.encode()).hexdigest()[:16]

        # Check cache
        cached = self._cache.get(content_hash)
        if cached:
            logger.info("Cache hit for %s, skipping LLM", filename)
            return IngestResult(source_hash=content_hash, skipped=True,
                               written_files=cached)

        # Phase 1: Analysis
        analysis = await self._analyze(source_content, kb_name)
        if not analysis:
            return IngestResult(source_hash=content_hash)

        # Phase 2: Generation
        generation = await self._generate(analysis, source_content, kb_name)
        if not generation:
            return IngestResult(source_hash=content_hash)

        # Parse FILE blocks
        blocks = parse_file_blocks(generation)
        written = []

        for block in blocks:
            # Sanitize
            content = sanitize_frontmatter(block.content)

            # Write to disk
            file_path = os.path.join(self._kb_dir, block.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            written.append(file_path)

        # Update index
        if written:
            self._update_index(written)
            self._update_log(filename, kb_name)
            self._cache.set(content_hash, written)

        return IngestResult(source_hash=content_hash, written_files=written)

    async def _analyze(self, source: str, kb_name: str) -> str:
        """Phase 1: LLM analyzes source and produces structured analysis."""
        prompt = f"""You are a research analyst. Analyze this source document for a knowledge base.

Source ({kb_name or 'unknown'}):
{source[:8000]}

Produce a structured analysis:
1. Key entities (name, type, role)
2. Key concepts (definition, significance)
3. Main arguments/findings
4. Connections to existing wiki (check index.md if available)
5. Recommendations for new pages

Analysis:"""

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            return result.content or ""
        except Exception:
            logger.exception("Phase 1 analysis failed")
            return ""

    async def _generate(self, analysis: str, source: str, kb_name: str) -> str:
        """Phase 2: LLM generates wiki pages from analysis."""
        prompt = f"""You are a wiki maintainer. Based on the analysis below, create wiki pages.

Analysis:
{analysis[:4000]}

Original source summary:
{source[:1000]}

Instructions:
- Create ONE wiki page per entity or concept
- Use ---FILE:wiki/entities/name.md--- ... ---END FILE--- blocks
- Each page must have YAML frontmatter: type, title, created, summary
- Use [[wikilink]] for cross-references
- Update existing pages if the source adds new information
- Do NOT echo the analysis in your output. Only produce FILE blocks.

Generate wiki pages:"""

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            return result.content or ""
        except Exception:
            logger.exception("Phase 2 generation failed")
            return ""

    def _update_index(self, written_files: list[str]) -> None:
        """Update index.md with entries for new pages."""
        index_path = os.path.join(self._kb_dir, "index.md")
        entries = []

        for fpath in written_files:
            rel = os.path.relpath(fpath, self._kb_dir)
            # Determine category from path
            if "/entities/" in rel:
                category = "Entities"
            elif "/concepts/" in rel:
                category = "Concepts"
            else:
                category = "Pages"
            name = os.path.splitext(os.path.basename(rel))[0]
            entries.append((category, name))

        # Read existing index
        existing = ""
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as f:
                existing = f.read()

        # Append new entries
        new_lines = []
        current_cat = None
        for cat, name in entries:
            if cat != current_cat:
                new_lines.append(f"\n## {cat}")
                current_cat = cat
            new_lines.append(f"- {name}")

        if existing:
            content = existing.rstrip() + "\n" + "\n".join(new_lines)
        else:
            content = "# Index\n" + "\n".join(new_lines)

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _update_log(self, filename: str, kb_name: str) -> None:
        """Append to log.md."""
        log_path = os.path.join(self._kb_dir, "log.md")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- {ts} | Ingested '{filename}' into wiki pages\n"

        mode = "a" if os.path.exists(log_path) else "w"
        with open(log_path, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write("# Ingest Log\n")
            f.write(entry)
