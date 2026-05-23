"""Tool system — mode-based tool registry."""

import os

from cococat.core.tools.types import Tool, ToolRegistry, _make, _with_env, _ensure_tool_context  # noqa: F401 — re-export
from cococat.core.tools.file_ops import make_file_tools, make_readonly_file_tools
from cococat.core.tools.execution import make_execution_tools
from cococat.core.tools.web import make_web_tools
from cococat.core.tools.memory_tools import make_memory_tools
from cococat.core.tools.meta import make_meta_tools, make_switch_mode_tool
from cococat.core.tools.kb_tools import make_kb_tools, make_kb_admin_tools


def resolve_tavily_key(config_store=None) -> str | None:
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    if config_store:
        try:
            return config_store.get_auth("tavily")
        except Exception:
            pass
    return None


_ALL_TOOL_FACTORIES = {
    "read_file": lambda: make_readonly_file_tools()["read_file"],
    "write_file": lambda: make_file_tools()["write_file"],
    "edit_file": lambda: make_file_tools()["edit_file"],
    "list_dir": lambda: make_readonly_file_tools()["list_dir"],
    "glob": lambda: make_readonly_file_tools()["glob"],
    "grep": lambda: make_readonly_file_tools()["grep"],
    "bash": lambda: make_execution_tools(None)["bash"],
    "web_search": lambda key=None: make_web_tools(key)["web_search"],
    "web_fetch": lambda key=None: make_web_tools(key)["web_fetch"],
    "remember": lambda: make_memory_tools()["remember"],
    "forget": lambda: make_memory_tools()["forget"],
    "pin": lambda: make_memory_tools()["pin"],
    "unpin": lambda: make_memory_tools()["unpin"],
    "list_pins": lambda: make_memory_tools()["list_pins"],
    "recall": lambda: make_memory_tools()["recall"],
    "search_kb": lambda: make_kb_tools()["search_kb"],
    "read_wiki": lambda: make_kb_tools()["read_wiki"],
    "write_wiki": lambda: make_kb_admin_tools()["write_wiki"],
    "list_kbs": lambda: make_kb_tools()["list_kbs"],
    "run_lint": lambda: make_kb_admin_tools()["run_lint"],
    "run_dedup": lambda: make_kb_admin_tools()["run_dedup"],
    "gen_overview": lambda: make_kb_admin_tools()["gen_overview"],
    "cron": lambda: make_meta_tools()["cron"],
    "wait": lambda: make_meta_tools()["wait"],
    "current_status": lambda: make_meta_tools()["current_status"],
    "switch_mode": lambda flag=None: make_switch_mode_tool(flag),
}


def resolve_tools_for_mode(mode_id: str, sub_agent_executor=None, tavily_api_key=None, mode_switch_flag=None):
    from cococat.core.modes import load_mode

    mode = load_mode(mode_id)
    tools = []
    for tool_name in mode.tools:
        if tool_name == "sub_agent":
            if sub_agent_executor:
                tools.append(Tool(
                    name="sub_agent",
                    description="Spawn a sub-agent to execute a task",
                    parameters={"task": "string", "agent_id": "string"},
                    execute=lambda params, ctx, executor=sub_agent_executor, m=mode_id: executor(params.get("task", ""), params.get("agent_id", "sub"), mode=m),
                ))
        elif tool_name in _ALL_TOOL_FACTORIES:
            try:
                factory = _ALL_TOOL_FACTORIES[tool_name]
                if tool_name in ("web_search", "web_fetch"):
                    tools.append(factory(tavily_api_key))
                elif tool_name == "switch_mode":
                    tools.append(factory(mode_switch_flag))
                else:
                    tools.append(factory())
            except Exception:
                continue
    return tools


def make_default_tools(tavily_api_key: str | None = None) -> list:
    """Build the default tool set (bash + readonly file + web + memory + kb).

    Shared single source of truth — used by cubesandbox and modes that want all tools.
    Returns a flat list of Tool objects.
    """
    return (
        list(make_execution_tools().values())
        + list(make_readonly_file_tools().values())
        + list(make_web_tools(tavily_api_key).values())
        + list(make_memory_tools().values())
        + list(make_kb_tools().values())
    )
