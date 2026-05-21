"""Meta tools — cron, wait, current_status, switch_mode."""
import json
import os

from cococat.core.types import ToolContext


def _resolve(ctx):
    return ToolContext.from_dict(ctx)


def _cron(schedule: str, task: str, ctx: ToolContext) -> str:
    if not schedule or not task:
        return "Error: 'schedule' and 'task' are required"
    ctx = _resolve(ctx)
    cron_dir = ctx.cron_path or "runs/cron"
    os.makedirs(cron_dir, exist_ok=True)
    import uuid
    entry_id = uuid.uuid4().hex[:8]
    filepath = os.path.join(cron_dir, f"{entry_id}.json")
    entry = {
        "id": entry_id, "schedule": schedule, "task": task,
        "status": "active", "created_at": "", "last_run": 0,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)
    return f"Cron job '{entry_id}' created. Schedule: {schedule}"


def _current_status(ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    lines = [f"Agent: {ctx.agent_id}"]
    if ctx.bound_scene:
        lines.append(f"Scene: {ctx.bound_scene}")
    lines.append(f"Role: {ctx.role}")
    if ctx.agent_dir:
        lines.append(f"Directory: {ctx.agent_dir}")
    cron_dir = ctx.cron_path or "runs/cron"
    if os.path.isdir(cron_dir):
        jobs = [f for f in os.listdir(cron_dir) if f.endswith(".json")]
        if jobs:
            lines.append(f"Cron jobs: {len(jobs)}")
    return "\n".join(lines)


def _wait(seconds_str: str) -> str:
    import time
    if not seconds_str:
        return "Waited for 0s"
    try:
        seconds = float(seconds_str)
    except (ValueError, TypeError):
        return "Error: 'seconds' must be a number"
    if seconds < 0:
        return "Error: 'seconds' must be non-negative"
    if seconds > 300:
        return "Error: max wait is 300s"
    if seconds > 0:
        time.sleep(min(seconds, 300))
    return f"Waited for {seconds}s"


def make_meta_tools():
    from cococat.core.tools.types import Tool
    return [
        Tool(name="cron", description="Schedule a delayed or recurring task",
             parameters={"schedule": "string", "task": "string"},
             execute=lambda p, ctx: _cron(p.get("schedule", ""), p.get("task", ""), ctx)),
        Tool(name="current_status", description="Show current agent state — identity, scene, working directory",
             parameters={},
             execute=lambda p, ctx: _current_status(ctx)),
        Tool(name="wait", description="Wait for N seconds before the next step",
             parameters={"seconds": "string"},
             execute=lambda p, ctx: _wait(p.get("seconds", ""))),
    ]


def make_switch_mode_tool(mode_switch_flag: list | None = None):
    from cococat.core.tools.types import Tool

    def _switch_mode(params: dict, ctx) -> str:
        target = params.get("target_mode", "")
        reason = params.get("reason", "")
        if not target:
            return "Error: 'target_mode' is required"
        if mode_switch_flag is not None:
            mode_switch_flag.append(target)

        scene_id = getattr(ctx, 'scene_id', 'default')
        user_id = getattr(ctx, 'user_id', 'local')
        pin_line = f"[mode-switch → {target}] {reason}" if reason else f"[mode-switch → {target}]"
        from cococat.core.paths import memory_dir
        pin_path = os.path.join(memory_dir(scene_id, user_id), "pinned.md")
        os.makedirs(os.path.dirname(pin_path) or ".", exist_ok=True)
        with open(pin_path, "a", encoding="utf-8") as f:
            f.write(pin_line + "\n")

        tool_summary = ""
        try:
            from cococat.core.modes import load_mode
            mode = load_mode(target)
            sample = list(mode.tools)[:8]
            if sample:
                tool_summary = f" ({len(mode.tools)} tools: {', '.join(sample)}{'...' if len(mode.tools) > 8 else ''})"
        except Exception:
            pass

        reason_text = f"\nReason: {reason}" if reason else ""
        return f"Switching to {target} mode{tool_summary}{reason_text}"

    return Tool(
        name="switch_mode",
        description="Switch to another mode. Context auto-pinned for cross-mode continuity. Available modes: default, kb-admin.",
        parameters={"target_mode": "string", "reason": "string"},
        execute=_switch_mode,
    )
