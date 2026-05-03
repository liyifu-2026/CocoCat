import json
import os
import time

AUTOCOMPACT_CHAR_BUDGET = 32000
KEEP_RECENT_ENTRIES = 5


def should_compact(history_text: str, budget: int = AUTOCOMPACT_CHAR_BUDGET) -> bool:
    return len(history_text) > budget


def compact_user_history(history_text: str, budget: int = AUTOCOMPACT_CHAR_BUDGET, keep_recent: int = KEEP_RECENT_ENTRIES) -> str:
    lines = [l for l in history_text.strip().split("\n") if l.strip()]
    if not lines:
        return ""
    if not should_compact(history_text, budget):
        return history_text
    entries = [json.loads(l) for l in lines]
    recent = entries[-keep_recent:]
    old = entries[:-keep_recent]
    summary = {
        "type": "compacted_summary",
        "original_count": len(old),
        "summary": f"[{len(old)} historical entries compacted]",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    result = [json.dumps(summary, ensure_ascii=False)] + [json.dumps(e, ensure_ascii=False) for e in recent]
    return "\n".join(result)


def run_auto_compact(agent_id: str):
    mem_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", agent_id, "memory")
    users_dir = os.path.join(mem_dir, "users")
    if not os.path.isdir(users_dir):
        return
    for user_hash in os.listdir(users_dir):
        history_path = os.path.join(users_dir, user_hash, "history.jsonl")
        if not os.path.exists(history_path):
            continue
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                content = f.read()
            compacted = compact_user_history(content)
            if compacted != content:
                with open(history_path, "w", encoding="utf-8") as f:
                    f.write(compacted)
        except Exception:
            pass
