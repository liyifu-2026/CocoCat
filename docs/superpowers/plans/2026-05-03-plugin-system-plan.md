# Plugin System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Add plugin system to CocoCat — discover, load, and manage plugins that register tools, hooks, and channels.

---

### Task 1: Create plugin manager core

**Files:**
- Create: `py-agent/plugin_manager.py`
- Create: `py-agent/plugin_hooks.py`
- Create: `tests/test_plugin_manager.py`

**Changes:**
- `py-agent/plugin_manager.py`: PluginManager class with discover, load, enable/disable, install, uninstall
- `py-agent/plugin_hooks.py`: HookRegistry with pre/post tool call hooks
- `tests/test_plugin_manager.py`: Tests for discovery, loading, hooks

### Task 2: Integrate plugin tools into ToolRegistry

**Files:**
- Modify: `py-agent/tools.py`

**Changes:**
- PluginManager registers plugin tools into ToolRegistry
- Plugin tools appear alongside built-in tools

### Task 3: Integrate plugin hooks into agent loop

**Files:**
- Modify: `py-agent/agent_loop.py`

**Changes:**
- Before/after each tool call, run pre/post hooks from HookRegistry
- Hooks can deny tool calls

### Task 4: Create example plugin

**Files:**
- Create: `plugins/example-plugin/plugin.json`
- Create: `plugins/example-plugin/hello_tool.py`
- Create: `plugins/example-plugin/hooks/logger.py`

**Changes:**
- Example plugin with one tool and one hook for testing
