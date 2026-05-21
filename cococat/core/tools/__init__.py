"""Tool system — mode-based tool registry."""

import os

from cococat.core.tools.types import Tool, ToolRegistry, _make, _merge_ctx, _ensure_tool_context  # noqa: F401 — re-export
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
    "read_file": lambda: make_readonly_file_tools()[0],
    "write_file": lambda: make_file_tools()[1],
    "edit_file": lambda: make_file_tools()[2],
    "list_dir": lambda: make_readonly_file_tools()[1],
    "glob": lambda: make_readonly_file_tools()[2],
    "grep": lambda: make_readonly_file_tools()[3],
    "bash": lambda: make_execution_tools(None)[0],
    "web_search": lambda key=None: make_web_tools(key)[0],
    "web_fetch": lambda key=None: make_web_tools(key)[1],
    "remember": lambda: make_memory_tools()[1],
    "forget": lambda: make_memory_tools()[2],
    "pin": lambda: make_memory_tools()[3],
    "unpin": lambda: make_memory_tools()[4],
    "list_pins": lambda: make_memory_tools()[5],
    "recall": lambda: make_memory_tools()[0],
    "search_kb": lambda: make_kb_tools()[0],
    "read_wiki": lambda: make_kb_tools()[1],
    "write_wiki": lambda: make_kb_admin_tools()[1],
    "list_kbs": lambda: make_kb_tools()[2],
    "run_lint": lambda: make_kb_admin_tools()[3],
    "run_dedup": lambda: make_kb_admin_tools()[2],
    "gen_overview": lambda: make_kb_admin_tools()[4],
    "cron": lambda: make_meta_tools()[0],
    "wait": lambda: make_meta_tools()[2],
    "current_status": lambda: make_meta_tools()[1],
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
        elif tool_name == "switch_mode":
            tools.append(make_switch_mode_tool(mode_switch_flag))
        elif tool_name in _ALL_TOOL_FACTORIES:
            try:
                factory = _ALL_TOOL_FACTORIES[tool_name]
                if tool_name in ("web_search", "web_fetch"):
                    tool = factory(tavily_api_key)
                else:
                    tool = factory()
                if isinstance(tool, list):
                    tools.extend(tool)
                else:
                    tools.append(tool)
            except Exception:
                continue
    return tools
