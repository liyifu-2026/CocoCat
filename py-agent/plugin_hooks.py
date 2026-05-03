"""Hook registry — manage plugin lifecycle hooks."""
import copy


class HookRegistry:
    """Registry for plugin lifecycle hooks."""

    def __init__(self):
        self._hooks = {}  # event -> [handler_functions]

    def register(self, event: str, handler) -> None:
        self._hooks.setdefault(event, []).append(handler)

    def register_all(self, hooks: dict) -> None:
        for event, handlers in hooks.items():
            for h in handlers:
                self.register(event, h)

    def run_pre_tool_call(self, tool_name: str, args: dict) -> tuple[bool, str, dict]:
        """Run all pre_tool_call hooks. Returns (allowed, reason, modified_args)."""
        current_args = copy.deepcopy(args)
        for handler in self._hooks.get("pre_tool_call", []):
            try:
                result = handler(tool_name, current_args, {})
                if not isinstance(result, dict):
                    continue
                action = result.get("action", "continue")
                if action == "deny":
                    return False, result.get("reason", "Blocked by plugin"), current_args
                if "args" in result:
                    current_args = result["args"]
            except Exception as e:
                print(f"[HookRegistry] pre_tool_call error: {e}")
        return True, "", current_args

    def run_post_tool_call(self, tool_name: str, args: dict, result: str) -> str:
        """Run all post_tool_call hooks. Returns modified result."""
        current_result = result
        for handler in self._hooks.get("post_tool_call", []):
            try:
                res = handler(tool_name, args, current_result, {})
                if isinstance(res, dict) and "result" in res:
                    current_result = res["result"]
            except Exception as e:
                print(f"[HookRegistry] post_tool_call error: {e}")
        return current_result

    def clear(self) -> None:
        self._hooks = {}
