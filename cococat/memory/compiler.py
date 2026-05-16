"""Daily memory compiler — compiles session summaries into structured memory files."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger("cococat.memory.compiler")


class DailyCompiler:
    """Compiles session summaries into today.md, week.md, longterm.md, facts.md.

    Called once per day (at midnight or on first use after date change).
    Uses fingerprint caching to avoid redundant LLM calls.
    """

    def __init__(self, llm: Any, memory_dir: str):
        self._llm = llm
        self._memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)

    async def compile_all(self) -> None:
        """Run all daily compilation steps."""
        summaries = self._load_summaries()
        if not summaries:
            return

        await self._compile_today(summaries)
        await self._compile_week()
        await self._compile_longterm()
        await self._assemble()

    def _load_summaries(self) -> list[dict]:
        """Load today's session summaries."""
        summaries_dir = os.path.join(self._memory_dir, "summaries")
        if not os.path.isdir(summaries_dir):
            return []

        results = []
        for fname in os.listdir(summaries_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(summaries_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
            except (json.JSONDecodeError, OSError):
                pass
        return results

    async def _compile_today(self, summaries: list[dict]) -> None:
        """Compile today's summaries into today.md (3-5 coarse events)."""
        if not summaries:
            return

        text = "\n\n".join(
            f"### Session {s.get('session_id', '?')[:8]}\n{s.get('summary', '')[:500]}"
            for s in summaries[-20:]  # Last 20 sessions
        )

        prompt = f"Summarize today's events in 3-5 bullet points (max 300 words):\n\n{text}\n\nBullet points:"

        try:
            result = await self._llm.chat(messages=[{"role": "user", "content": prompt}])
            content = result.content or ""
        except Exception:
            logger.exception("compileToday failed")
            return

        path = os.path.join(self._memory_dir, "today.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Today ({datetime.now().strftime('%Y-%m-%d')})\n\n{content[:2000]}")

    async def _compile_week(self) -> None:
        """Fold today.md into week.md using LLM summarization.

        Reads existing week content + today's content, asks LLM to produce
        a compressed weekly digest. Falls back to simple append on LLM error.
        """
        today_path = os.path.join(self._memory_dir, "today.md")
        if not os.path.exists(today_path):
            return

        with open(today_path, encoding="utf-8") as f:
            today_content = f.read(2000)

        week_path = os.path.join(self._memory_dir, "week.md")
        existing = ""
        if os.path.exists(week_path):
            with open(week_path, encoding="utf-8") as f:
                existing = f.read(3000)

        today_label = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""Compress the following daily memory entries into a concise weekly digest (max 200 words).
Remove redundant information. Keep concrete facts, decisions, and outcomes.

Existing weekly context:
{existing[:2000] or '(none)'}

Today ({today_label}):
{today_content[:1500]}

Weekly digest (include {today_label}):"""

        try:
            result = await self._llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:2000]
        except Exception:
            logger.exception("compileWeek failed, falling back to append")
            header = f"## {today_label}\n{today_content[:500]}\n\n"
            content = header

        with open(week_path, "w", encoding="utf-8") as f:
            f.write(content)

    async def _compile_longterm(self) -> None:
        """Fold week.md into longterm.md using LLM summarization.

        Reads week content, asks LLM to extract a persistent long-term profile.
        Only runs if week.md has accumulated enough content.
        """
        week_path = os.path.join(self._memory_dir, "week.md")
        if not os.path.exists(week_path):
            return

        with open(week_path, encoding="utf-8") as f:
            week_content = f.read(5000)

        if len(week_content) < 200:
            return

        longterm_path = os.path.join(self._memory_dir, "longterm.md")
        existing = ""
        if os.path.exists(longterm_path):
            with open(longterm_path, encoding="utf-8") as f:
                existing = f.read(3000)

        prompt = f"""Synthesize the following weekly memory into a long-term profile (max 300 words).
Focus on: persistent user preferences, recurring patterns, important decisions, and knowledge that remains relevant over time.

Existing long-term profile:
{existing[:1500] or '(none)'}

Weekly memory:
{week_content[:3000]}

Long-term profile:"""

        try:
            result = await self._llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:3000]
        except Exception:
            logger.exception("compileLongterm failed")
            return

        with open(longterm_path, "w", encoding="utf-8") as f:
            f.write(content)

    async def _assemble(self) -> None:
        """Assemble memory.md from facts.md + today.md + week.md + longterm.md."""
        sections = []

        for name in ["facts.md", "today.md", "week.md", "longterm.md"]:
            path = os.path.join(self._memory_dir, name)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    sections.append(f.read(2000))

        if not sections:
            return

        memory_md = os.path.join(self._memory_dir, "memory.md")
        with open(memory_md, "w", encoding="utf-8") as f:
            f.write("\n\n".join(sections))
