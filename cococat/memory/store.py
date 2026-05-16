"""MemoryStore — unified memory: file-based + SQLite FTS5, manual + automated."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger("cococat.memory")

DREAM_THRESHOLD = 50
KEEP_LINES = 30
TURNS_PER_SUMMARY = 6
_DREAM_MODEL_CANDIDATES = ["deepseek-chat"]


class MemoryStore:
    """Unified memory layer.

    Single interface for all memory operations:
      remember / recall / forget  (manual, called by tools)
      dream                      (auto-extract from conversation)
      summarize / compile        (periodic from session summaries)
      extract_facts              (FTS5 atomic facts)
    """

    def __init__(self, llm: Any = None, db: Any = None, memory_dir: str = "memory"):
        self._llm = llm
        self._db = db
        self._memory_dir = memory_dir
        self._turn_counts: dict[str, int] = {}
        self._fingerprints: dict[str, str] = {}
        self._fact_snapshots: dict[str, str] = {}

    # ── Manual operations ───────────────────────────────────

    def remember(self, text: str, category: str | None = None, exp_path: str = "") -> str:
        """Add a fact or experience.

        category=None → append to memory.md (pin).
        Otherwise → write to {exp_path or memory_dir/experiences}/{category}/{slug}.md.
        """
        if category:
            return self._record_experience(category, text, exp_path)
        return self._pin(text)

    def recall(self, query: str) -> str:
        """Search memory.md + FTS5 + experiences/ for query. Returns formatted results."""
        q = query.lower()
        results = []

        # 1. Search memory.md
        mem_path = os.path.join(self._memory_dir, "memory.md")
        if os.path.exists(mem_path):
            with open(mem_path, encoding="utf-8") as f:
                for line in f:
                    if q in line.lower():
                        results.append(("memory", line.strip()))

        # 2. Search FTS5
        if self._db:
            try:
                rows = self._db.execute(
                    "SELECT fact FROM facts_fts WHERE facts_fts MATCH ?", (query,)
                )
                for row in rows:
                    results.append(("fts5", row[0].strip()))
            except Exception:
                pass

        # 3. Search experiences/ (under memory_dir)
        exp_path = os.path.join(self._memory_dir, "experiences")
        if os.path.isdir(exp_path):
            for root, _, files in os.walk(exp_path):
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding="utf-8") as f:
                        content = f.read()
                    if q in content.lower():
                        results.append(
                            (os.path.relpath(root, exp_path), content.strip()[:200])
                        )

        if not results:
            return "No matches found"
        return "\n---\n".join(f"[{src}] {text}" for src, text in results)

    def forget(self, keyword: str) -> str:
        """Remove lines matching keyword from memory.md."""
        mem_path = os.path.join(self._memory_dir, "memory.md")
        if not os.path.exists(mem_path):
            return f"No facts matching '{keyword}' found"
        with open(mem_path, encoding="utf-8") as f:
            lines = f.readlines()
        kept = [l for l in lines if keyword.lower() not in l.lower()]
        if len(kept) == len(lines):
            return f"No facts matching '{keyword}' found"
        with open(mem_path, "w", encoding="utf-8") as f:
            f.writelines(kept)
        return f"Unpinned facts matching '{keyword}'"

    def load_for_system_prompt(self) -> str:
        """Return memory.md content for inclusion in system prompt."""
        path = os.path.join(self._memory_dir, "memory.md")
        if not os.path.exists(path):
            return ""
        try:
            with open(path, encoding="utf-8") as f:
                return f.read(3000)
        except OSError:
            return ""

    # ── Internal manual helpers ─────────────────────────────

    def _pin(self, fact: str) -> str:
        mem_path = os.path.join(self._memory_dir, "memory.md")
        os.makedirs(self._memory_dir, exist_ok=True)
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(fact if fact.endswith("\n") else fact + "\n")
        return f"Pinned: {fact}"

    def _record_experience(self, category: str, entry: str, exp_path: str = "") -> str:
        root = exp_path or os.path.join(self._memory_dir, "experiences")
        cat_dir = os.path.join(root, category)
        os.makedirs(cat_dir, exist_ok=True)
        slug = entry.lower().strip()[:60].replace(" ", "-").replace("/", "-")
        fpath = os.path.join(cat_dir, f"{slug}.md")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(entry if entry.endswith("\n") else entry + "\n")
        return f"Recorded experience in '{category}': {entry[:80]}"

    def read_experiences(self, category: str, exp_path: str = "") -> str:
        root = exp_path or os.path.join(self._memory_dir, "experiences")
        cat_dir = os.path.join(root, category)
        if not os.path.isdir(cat_dir):
            return f"No experiences found for category '{category}'"
        entries = []
        for fname in sorted(os.listdir(cat_dir)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(cat_dir, fname), encoding="utf-8") as f:
                entries.append(f"{fname[:-3]}:\n{f.read().strip()}")
        if not entries:
            return f"No experiences found for category '{category}'"
        return "\n\n".join(entries)

    # ── Auto-dream ──────────────────────────────────────────

    async def dream(self, session_path: str) -> None:
        """Fire-and-forget: extract facts from session, pin to memory.md, truncate session."""
        try:
            if not os.path.exists(session_path):
                return

            with open(session_path, encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) < DREAM_THRESHOLD:
                return

            session_content = "".join(lines)
            memory_path = self._memory_path_from_session(session_path)
            existing = ""
            if os.path.exists(memory_path):
                with open(memory_path, encoding="utf-8") as f:
                    existing = f.read()

            llm = self._get_llm()
            if not llm:
                logger.warning("auto_dream: no LLM available")
                return

            prompt = self._dream_prompt(session_content, existing)
            resp = await llm.chat([{"role": "user", "content": prompt}])
            raw = resp.content or ""

            pinned = 0
            os.makedirs(os.path.dirname(memory_path) or ".", exist_ok=True)
            for line in raw.splitlines():
                fact = line.strip()
                if not fact or fact in existing:
                    continue
                with open(memory_path, "a", encoding="utf-8") as f:
                    f.write(fact + "\n")
                existing += fact + "\n"
                pinned += 1

            if pinned:
                logger.info("auto_dream: pinned %d facts → %s", pinned, memory_path)

            # Truncate session
            if len(lines) > KEEP_LINES:
                with open(session_path, "w", encoding="utf-8") as f:
                    f.writelines(lines[-KEEP_LINES:])

        except Exception:
            logger.warning("auto_dream failed", exc_info=True)

    def _memory_path_from_session(self, session_path: str) -> str:
        return os.path.join(os.path.dirname(session_path), "memory", "memory.md")

    @staticmethod
    def _dream_prompt(session_history: str, existing_memory: str) -> str:
        memory_block = ""
        if existing_memory.strip():
            memory_block = (
                "\n## 已有记忆（不要重复输出）\n"
                f"{existing_memory.strip()}\n"
            )
        return (
            "你是一个记忆助手。从以下对话历史中提取迄今为止新发现的关键事实。\n"
            "每条不超过 30 字。只提取对后续对话有用的信息：\n"
            "用户偏好、项目信息、进行中的任务、重要决策、代码改动要点。\n"
            "不要提取闲聊内容。\n"
            f"{memory_block}\n"
            "对话历史：\n"
            f"{session_history[-8000:]}\n\n"
            "输出格式：严格每行一条事实，不要编号，不要前缀，不要空行。"
        )

    # ── Session summarization (from MemoryTicker) ───────────

    async def notify_turn(self, session: Any) -> None:
        sid = session.id
        self._turn_counts[sid] = self._turn_counts.get(sid, 0) + 1
        if self._turn_counts[sid] >= TURNS_PER_SUMMARY:
            await self._summarize(session)
            self._turn_counts[sid] = 0

    async def notify_session_end(self, session: Any) -> None:
        await self._summarize(session)
        self._turn_counts.pop(session.id, None)

    async def _summarize(self, session: Any) -> None:
        messages = await session.read()
        if len(messages) < 2:
            return

        content_hash = self._hash_messages(messages)
        if self._fingerprints.get(session.id) == content_hash:
            return

        summary_dir = os.path.join(self._memory_dir, "summaries")
        os.makedirs(summary_dir, exist_ok=True)

        recent = messages[-20:]
        text = "\n".join(
            f"[{m['role']}]: {m.get('content', '')[:500]}"
            for m in recent
        )

        prompt = (
            "Summarize this conversation segment in 2-3 sentences.\n"
            "Focus on: key topics discussed, decisions made, user preferences revealed.\n\n"
            f"Conversation:\n{text}\n\nSummary:"
        )

        llm = self._get_llm()
        if not llm:
            return

        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            summary_text = result.content or ""
        except Exception:
            logger.exception("Summarization failed for session %s", session.id)
            return

        summary_path = os.path.join(summary_dir, f"{session.id}.json")
        summary_data = {
            "session_id": session.id,
            "fingerprint": content_hash,
            "summary": summary_text[:1000],
            "message_count": len(messages),
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

        self._fingerprints[session.id] = content_hash

    # ── Daily compilation (from DailyCompiler) ──────────────

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

    # ── Facts extraction (from FactsExtractor) ──────────────

    async def extract_facts(self) -> int:
        summaries_dir = os.path.join(self._memory_dir, "summaries")
        if not os.path.isdir(summaries_dir):
            return 0

        count = 0
        fact_store = self._db.facts if self._db else None
        for fname in os.listdir(summaries_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(summaries_dir, fname)
            session_id = fname[:-5]
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            fp = data.get("fingerprint", "")
            if self._fact_snapshots.get(session_id) == fp:
                continue

            new_facts = await self._extract_atomic(data["summary"], session_id)
            if new_facts and fact_store:
                for fact in new_facts:
                    fact_store.insert(
                        f"{session_id}-{fact['hash'][:8]}", "main",
                        fact["text"], fact["text"], fact.get("tags", ""),
                        session_id,
                    )
                fact_store.rebuild_index()
                count += len(new_facts)

            self._fact_snapshots[session_id] = fp

        return count

    async def _extract_atomic(self, summary: str, session_id: str) -> list[dict]:
        prompt = (
            "Extract 1-3 key facts from this conversation summary.\n"
            "Each fact should be a single sentence. Add a tag (preference/decision/context).\n\n"
            f"Summary: {summary[:1000]}\n\n"
            'Return JSON array: [{"text": "...", "tags": "..."}]'
        )
        llm = self._get_llm()
        if not llm:
            return []
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = result.content or ""
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                facts = json.loads(content[json_start:json_end])
                return [
                    {"text": f["text"], "tags": f.get("tags", ""),
                     "hash": str(hash(f["text"]))}
                    for f in facts if isinstance(f, dict) and "text" in f
                ]
        except Exception:
            logger.exception("Facts extraction failed for %s", session_id)
        return []

    # ── LLM helpers ─────────────────────────────────────────

    def _get_llm(self):
        if self._llm:
            return self._llm
        from cococat.providers.factory import ProviderFactory
        from cococat.providers.credentials import CredentialManager
        creds = CredentialManager()
        factory = ProviderFactory(credential_manager=creds)
        for model in _DREAM_MODEL_CANDIDATES:
            provider = factory.create_sync(model)
            if provider:
                return provider
        for spec in factory._registry.list_all():
            provider = factory.create_sync(spec["name"])
            if provider:
                return provider
        return None

    @staticmethod
    def _hash_messages(messages: list[dict]) -> str:
        text = json.dumps(
            [{"r": m["role"], "c": m.get("content", "")[:200]} for m in messages[-20:]],
            sort_keys=True,
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]
