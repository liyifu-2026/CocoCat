"""Periodic day → week → longterm memory compilation with cron triggers."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger("cococat.memory")


class CompileMemory:
    """Periodic compilation of session summaries and daily memories."""

    def __init__(self, memory_dir: str = "memory", get_llm: Callable[[], Any] | None = None):
        self._memory_dir = memory_dir
        self._get_llm = get_llm or (lambda: None)
        self._compiled_dir = os.path.join(memory_dir, "compiled")
        self._cursor_file = os.path.join(self._compiled_dir, ".cursor")

    def _read_cursor(self) -> dict:
        if os.path.exists(self._cursor_file):
            try:
                with open(self._cursor_file, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _write_cursor(self, cursor: dict) -> None:
        os.makedirs(self._compiled_dir, exist_ok=True)
        with open(self._cursor_file, "w", encoding="utf-8") as f:
            json.dump(cursor, f)

    async def compile_day(self) -> None:
        """Compress new summaries into a daily digest. Skipped if no new summaries."""
        summaries_dir = os.path.join(self._memory_dir, "summaries")
        if not os.path.isdir(summaries_dir):
            return

        cursor = self._read_cursor()
        last_processed = cursor.get("day_last_processed", "")

        new_summaries = sorted(
            f for f in os.listdir(summaries_dir)
            if f.endswith(".json") and f > last_processed
        )
        if not new_summaries:
            return

        texts = []
        for fname in new_summaries[-30:]:  # max 30
            path = os.path.join(summaries_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                texts.append(data.get("summary", "")[:500])
            except (json.JSONDecodeError, OSError):
                pass

        if not texts:
            return

        prompt = "Summarize today's events in 3-5 bullet points (max 300 words):\n\n" + "\n".join(texts) + "\n\nBullet points:"
        llm = self._get_llm()
        if not llm:
            return
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:2000]
        except Exception:
            logger.exception("compile_day failed")
            return

        date_str = datetime.now().strftime("%Y-%m-%d")
        day_path = os.path.join(self._compiled_dir, f"{date_str}.md")
        os.makedirs(self._compiled_dir, exist_ok=True)
        with open(day_path, "w", encoding="utf-8") as f:
            f.write(f"# {date_str}\n\n{content}")

        cursor["day_last_processed"] = new_summaries[-1]
        self._write_cursor(cursor)
        logger.info("compile_day: wrote %s (%d summaries)", day_path, len(new_summaries))

    async def compile_week(self) -> None:
        """Synthesize new day files into a weekly digest. Skipped if no new day files."""
        if not os.path.isdir(self._compiled_dir):
            return

        cursor = self._read_cursor()
        last_processed = cursor.get("week_last_processed", "")

        day_files = sorted(
            f for f in os.listdir(self._compiled_dir)
            if f.endswith(".md") and not f.startswith(".") and f > last_processed
        )[:14]  # max 14 days
        if not day_files:
            return

        texts = []
        for fname in day_files:
            path = os.path.join(self._compiled_dir, fname)
            with open(path, encoding="utf-8") as f:
                texts.append(f.read(1500))

        today = datetime.now()
        week_num = today.isocalendar()[1]
        week_label = f"{today.year}-W{week_num:02d}"

        prompt = (
            "Synthesize these daily observations into a concise weekly summary (max 200 words). "
            "Remove redundancy. Keep concrete facts, decisions, and outcomes.\n\n"
            + "\n\n".join(texts)
            + f"\n\nWeekly summary ({week_label}):"
        )
        llm = self._get_llm()
        if not llm:
            return
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:2000]
        except Exception:
            logger.exception("compile_week failed")
            return

        week_path = os.path.join(self._compiled_dir, f"{week_label}.md")
        with open(week_path, "w", encoding="utf-8") as f:
            f.write(f"# Week {week_label}\n\n{content}")

        cursor["week_last_processed"] = max(day_files)
        self._write_cursor(cursor)
        logger.info("compile_week: wrote %s (%d day files)", week_path, len(day_files))

    async def compile_longterm(self) -> None:
        """Synthesize new week files into longterm archive. Overwrites single file."""
        if not os.path.isdir(self._compiled_dir):
            return

        cursor = self._read_cursor()
        last_processed = cursor.get("longterm_last_processed", "")

        week_files = sorted(
            f for f in os.listdir(self._compiled_dir)
            if f.startswith(f"{datetime.now().year}-W") and f > last_processed
        )
        if not week_files:
            return

        texts = []
        for fname in week_files:
            path = os.path.join(self._compiled_dir, fname)
            with open(path, encoding="utf-8") as f:
                texts.append(f.read(2000))

        month_label = datetime.now().strftime("%Y-%m")
        longterm_path = os.path.join(self._compiled_dir, f"{month_label}-longterm.md")

        existing = ""
        if os.path.exists(longterm_path):
            with open(longterm_path, encoding="utf-8") as f:
                existing = f.read(3000)

        prompt = (
            "Synthesize new weekly observations into the existing long-term profile. "
            "Remove redundancies. Keep concrete facts, decisions, user preferences, and project context. "
            "Max 300 words.\n\n"
            f"### Existing profile\n{existing[:1500] or '(none)'}\n\n"
            f"### New observations\n" + "\n\n".join(texts) +
            f"\n\n### Updated long-term profile ({month_label}):"
        )
        llm = self._get_llm()
        if not llm:
            return
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = (result.content or "")[:3000]
        except Exception:
            logger.exception("compile_longterm failed")
            return

        with open(longterm_path, "w", encoding="utf-8") as f:
            f.write(f"# Long-term Memory ({month_label})\n\n{content}")

        cursor["longterm_last_processed"] = max(week_files)
        self._write_cursor(cursor)
        logger.info("compile_longterm: wrote %s (%d week files)", longterm_path, len(week_files))

    async def compile(self) -> None:
        """Run all compile steps in sequence."""
        await self.compile_day()
        await self.compile_week()
        await self.compile_longterm()
