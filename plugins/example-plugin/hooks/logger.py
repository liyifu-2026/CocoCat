import sys


def log_pre_tool(tool_name: str, args: dict, config: dict) -> dict:
    print(f"[PluginHook] Pre-tool: {tool_name} with args: {args}", file=sys.stderr)
    return {"action": "continue", "args": args}


def log_post_tool(tool_name: str, args: dict, result: str, config: dict) -> dict:
    print(f"[PluginHook] Post-tool: {tool_name} = {result[:50]}", file=sys.stderr)
    return {"action": "continue", "result": result}
