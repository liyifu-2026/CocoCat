"""Test tool schema validity for OpenAI/DeepSeek function calling API compliance.

These tests validate that _tool_to_openai() produces schemas that the
DeepSeek API will accept. The key failure modes:
1. type=array without items schema → API rejects with 400
2. Empty params → some providers reject
3. type=number → valid but unusual; should be type=integer for integer params
"""
import json
import pytest
from cococat.core.tools import resolve_tools_for_mode
from cococat.providers.openai_compat import _tool_to_openai


def _all_tools():
    return resolve_tools_for_mode("kb-admin")


def test_array_type_has_items():
    """array-type parameters MUST have items schema for API compliance."""
    for t in _all_tools():
        converted = _tool_to_openai(t)
        props = converted["parameters"]["properties"]
        for k, v in props.items():
            if v.get("type") == "array":
                assert "items" in v, (
                    f"Tool '{t['name']}.{k}': type=array but missing 'items' schema. "
                    f"This causes DeepSeek API to return 400 Bad Request."
                )


def test_all_type_values_are_valid_json_schema():
    """All type values must be valid JSON Schema types."""
    valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}
    for t in _all_tools():
        converted = _tool_to_openai(t)
        props = converted["parameters"]["properties"]
        for k, v in props.items():
            assert v.get("type") in valid_types, (
                f"Tool '{t['name']}.{k}': invalid type '{v.get('type')}'. "
                f"Must be one of {valid_types}"
            )


def test_empty_params_tools_still_valid():
    """Tools with empty parameters should produce valid schema."""
    from cococat.core.tools import resolve_tools_for_mode as rtm
    core = rtm("kb-admin")
    for name in ("current_status",):
        tool = next(t for t in core if t["name"] == name)
        converted = _tool_to_openai(tool)
        params = converted["parameters"]
        assert params["type"] == "object"
        assert isinstance(params.get("properties"), dict)
        json.dumps(params)  # must serialize


def test_all_tools_serialize_to_valid_function_calls():
    """Every tool's OpenAI function format must be JSON-serializable."""
    for t in _all_tools():
        converted = _tool_to_openai(t)
        fc = {"type": "function", "function": converted}
        try:
            serialized = json.dumps(fc)
            # Verify round-trip
            parsed = json.loads(serialized)
            assert parsed["type"] == "function"
            assert parsed["function"]["name"] == t["name"]
        except (TypeError, ValueError) as e:
            pytest.fail(f"Tool '{t['name']}' cannot serialize: {e}")


def test_function_names_are_valid():
    """Function names must match API naming rules (alphanumeric, underscore, dash)."""
    import re
    for t in _all_tools():
        name = t["name"]
        assert re.match(r'^[a-zA-Z0-9_-]+$', name), (
            f"Tool name '{name}' contains invalid characters"
        )
        assert len(name) <= 64, f"Tool name '{name}' exceeds 64 char limit"


def test_no_duplicate_tool_names_across_all_sets():
    """No duplicate tool names within resolve_tools_for_mode sets."""
    from cococat.core.tools import resolve_tools_for_mode as rtm
    default = rtm("default")
    kb_admin = rtm("kb-admin")
    default_names = {t["name"] for t in default}
    kb_names = {t["name"] for t in kb_admin}
    assert len(default) == len(default_names), "default mode has duplicate names"
    assert len(kb_admin) == len(kb_names), "kb-admin mode has duplicate names"


def test_main_ai_has_no_write_or_execution_tools():
    """Main AI should have read tools + web, but NOT write_file/edit_file/bash/browser."""
    from cococat.core.tools import resolve_tools_for_mode as rtm
    main = rtm("default")
    names = {t["name"] for t in main}
    forbidden = {"write_file", "edit_file", "bash", "browser"}
    overlap = names & forbidden
    assert not overlap, f"Main AI has forbidden write/execution tools: {overlap}"
    assert "read_file" in names, "Main AI should have read_file"
    assert "web_search" in names, "Main AI should have web_search"


def test_core_tools_include_web_search_and_fetch():
    """Core (sub-agent) tools must include web_search and web_fetch."""
    from cococat.core.tools import resolve_tools_for_mode as rtm
    core = rtm("kb-admin")
    names = {t["name"] for t in core}
    assert "web_search" in names, "Sub-agent tools missing web_search"
    assert "web_fetch" in names, "Sub-agent tools missing web_fetch"


from cococat.core.tools import Tool

def test_tool_dict_access():
    """Tool supports dict-style access for backward compatibility."""
    t = Tool(name="test", description="A test tool", parameters={"x": "string"},
             execute=lambda p, c: "ok")
    assert t["name"] == "test"
    assert t["description"] == "A test tool"
    assert t["parameters"] == {"x": "string"}
    assert "name" in t
    assert "nonexistent" not in t


def test_tool_attr_access():
    """Tool supports attribute access (new)."""
    t = Tool(name="test", description="A test tool", parameters={"x": "string"},
             execute=lambda p, c: "ok")
    assert t.name == "test"
    assert t.description == "A test tool"
    assert t.parameters == {"x": "string"}


def test_tool_requires_sandbox_default():
    """Tool.requires_sandbox defaults to False."""
    t = Tool(name="bash", description="Run command", parameters={"cmd": "string"},
             execute=lambda p, c: "ok")
    assert t.requires_sandbox is False


def test_tool_requires_sandbox_true():
    """Tool.requires_sandbox can be set to True."""
    t = Tool(name="bash", description="Run command", parameters={"cmd": "string"},
             execute=lambda p, c: "ok", requires_sandbox=True)
    assert t.requires_sandbox is True


def test_tool_execute_works():
    """Tool.execute is callable."""
    t = Tool(name="echo", description="Echo", parameters={"msg": "string"},
             execute=lambda p, c: p["msg"])
    assert t.execute({"msg": "hello"}, {}) == "hello"
