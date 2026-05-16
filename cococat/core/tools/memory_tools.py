"""Memory tools — pin, unpin, recall, experience recording."""
import os

from cococat.core.types import ToolContext


def _memory_path(ctx: ToolContext) -> str:
    if "memory_path" in ctx:
        return ctx["memory_path"]
    agent_dir = ctx.get("agent_dir", "agents/main")
    path = os.path.join(agent_dir, "memory", "memory.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _pin(fact: str, ctx: ToolContext) -> str:
    if not fact:
        return "Error: 'fact' is required"
    path = _memory_path(ctx)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(fact if fact.endswith("\n") else fact + "\n")
        return f"Pinned: {fact}"
    except Exception as e:
        return f"Error pinning fact: {e}"


def _unpin(keyword: str, ctx: ToolContext) -> str:
    if not keyword:
        return "Error: 'keyword' is required"
    path = _memory_path(ctx)
    try:
        if not os.path.exists(path):
            return f"No facts matching '{keyword}' found"
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        kept = [l for l in lines if keyword.lower() not in l.lower()]
        if len(kept) == len(lines):
            return f"No facts matching '{keyword}' found"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(kept)
        return f"Unpinned facts matching '{keyword}'"
    except Exception as e:
        return f"Error unpinning fact: {e}"


def _recall(query: str, ctx: ToolContext) -> str:
    if not query:
        return "Error: 'query' is required"
    q = query.lower()
    results = []

    mem_path = _memory_path(ctx)
    if os.path.exists(mem_path):
        with open(mem_path, encoding="utf-8") as f:
            for line in f:
                if q in line.lower():
                    results.append(("memory", line.strip()))

    exp_path = ctx.get("exp_path", "memory/experiences")
    if os.path.isdir(exp_path):
        for root, _, files in os.walk(exp_path):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                if q in content.lower():
                    results.append((os.path.relpath(root, exp_path), content.strip()[:200]))

    if not results:
        return "No matches found"
    return "\n---\n".join(f"[{src}] {text}" for src, text in results)


def _record_experience(category: str, entry: str, ctx: ToolContext) -> str:
    if not category:
        return "Error: 'category' is required"
    if not entry:
        return "Error: 'entry' is required"
    exp_path = ctx.get("exp_path", "memory/experiences")
    cat_dir = os.path.join(exp_path, category)
    try:
        os.makedirs(cat_dir, exist_ok=True)
        slug = entry.lower().strip()[:60].replace(" ", "-").replace("/", "-")
        fname = f"{slug}.md"
        fpath = os.path.join(cat_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(entry if entry.endswith("\n") else entry + "\n")
        return f"Recorded experience in '{category}': {entry[:80]}"
    except Exception as e:
        return f"Error recording experience: {e}"


def _recall_experience(category: str, ctx: ToolContext) -> str:
    if not category:
        return "Error: 'category' is required"
    exp_path = ctx.get("exp_path", "memory/experiences")
    cat_dir = os.path.join(exp_path, category)
    if not os.path.isdir(cat_dir):
        return f"No experiences found for category '{category}'"
    try:
        entries = []
        for fname in sorted(os.listdir(cat_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(cat_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read().strip()
            entries.append(f"{fname[:-3]}:\n{content}")
        if not entries:
            return f"No experiences found for category '{category}'"
        return "\n\n".join(entries)
    except Exception as e:
        return f"Error reading experiences: {e}"
