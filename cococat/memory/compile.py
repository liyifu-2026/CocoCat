"""Periodic daily → weekly → longterm memory compilation."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger("cococat.memory")


class CompileMemory:
    """Periodic compilation of session summaries into structured memory files.

    Owns no mutable state — works from files on disk.
    """

    def __init__(self, memory_dir: str = "memory", get_llm: Callable[[], Any] | None = None):
        self._memory_dir = memory_dir
        self._get_llm = get_llm or (lambda: None)

    async def compile(self) -> None:
        summaries = self._load_summaries()
        if not summaries:
            return
        await self._compile_today(summaries)
        await self._compile_week()
        await self._compile_longterm()
        await self._assemble()

    def _load_summaries(self) -> list[dict]:
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
                    results.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        return results

    async def _compile_today(self, summaries: list[dict]) -> None:
        text = "\n\n".join(
            f"### Session {s.get('session_id', '?')[:8]}\n{s.get('summary', '')[:500]}"
            for s in summaries[-20:]
        )
        prompt = f"Summarize today's events in 3-5 bullet points (max 300 words):\n\n{text}\n\nBullet points:"
        llm = self._get_llm()
        if not llm:
            return
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:2000]
        except Exception:
            logger.exception("compileToday failed")
            return
        path = os.path.join(self._memory_dir, "today.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Today ({datetime.now().strftime('%Y-%m-%d')})\n\n{content}")

    async def _compile_week(self) -> None:
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
        prompt = (
            "Compress the following daily memory entries into a concise weekly digest (max 200 words).\n"
            "Remove redundant information. Keep concrete facts, decisions, and outcomes.\n\n"
            f"Existing weekly context:\n{existing[:2000] or '(none)'}\n\n"
            f"Today ({today_label}):\n{today_content[:1500]}\n\n"
            f"Weekly digest (include {today_label}):"
        )
        llm = self._get_llm()
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}]) if llm else None
            content = (result.content or "")[:2000] if result else ""
        except Exception:
            logger.exception("compileWeek failed, falling back to append")
            content = f"## {today_label}\n{today_content[:500]}\n\n"
        if content:
            with open(week_path, "w", encoding="utf-8") as f:
                f.write(content)

    async def _compile_longterm(self) -> None:
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
        prompt = (
            "Synthesize the following weekly memory into a long-term profile (max 300 words).\n"
            "Focus on: persistent user preferences, recurring patterns, important decisions, and knowledge that remains relevant over time.\n\n"
            f"Existing long-term profile:\n{existing[:1500] or '(none)'}\n\n"
            f"Weekly memory:\n{week_content[:3000]}\n\n"
            "Long-term profile:"
        )
        llm = self._get_llm()
        if not llm:
            return
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:3000]
        except Exception:
            logger.exception("compileLongterm failed")
            return
        with open(longterm_path, "w", encoding="utf-8") as f:
            f.write(content)

    async def _assemble(self) -> None:
        sections = []
        for name in ["today.md", "week.md", "longterm.md"]:
            path = os.path.join(self._memory_dir, name)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    sections.append(f.read(2000))
        if sections:
            memory_md = os.path.join(self._memory_dir, "memory.md")
            with open(memory_md, "w", encoding="utf-8") as f:
                f.write("\n\n".join(sections))
