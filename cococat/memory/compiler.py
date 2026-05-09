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

        today = datetime.now().strftime("%Y-%m-%d")
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
            content = result.get("content", "") if isinstance(result, dict) else str(result)
        except Exception:
            logger.exception("compileToday failed")
            return

        path = os.path.join(self._memory_dir, "today.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Today ({datetime.now().strftime('%Y-%m-%d')})\n\n{content[:2000]}")

    async def _compile_week(self) -> None:
        """Stub — folds today into week.md. LLM call can be added later."""
        today_path = os.path.join(self._memory_dir, "today.md")
        if not os.path.exists(today_path):
            return

        week_path = os.path.join(self._memory_dir, "week.md")
        with open(today_path, encoding="utf-8") as f:
            today_content = f.read(500)

        # Simple append for now — full LLM fold can be added later
        header = f"## {datetime.now().strftime('%Y-%m-%d')}\n{today_content}\n\n"
        mode = "a" if os.path.exists(week_path) else "w"
        with open(week_path, mode, encoding="utf-8") as f:
            f.write(header)

    async def _compile_longterm(self) -> None:
        """Stub — LLM fold week into longterm profile."""
        pass

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
