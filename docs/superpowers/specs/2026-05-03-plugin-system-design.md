# Plugin System Design

## Overview

Add a plugin system to CocoCat that allows third-party code to register tools, hook into the agent lifecycle, and add new channels — without modifying core files.

## Discovery

Two mechanisms:

1. **Directory scan**: Scan `plugins/` directory for subdirectories containing `plugin.json`
2. **Python entry_points**: Scan `cococat.plugins` entry point group for pip-installed plugins

## Manifest (plugin.json)

```json
{
  "name": "email-plugin",
  "version": "1.0.0",
  "description": "Send and receive emails",
  "tools": [
    {
      "name": "send_email",
      "description": "Send an email via SMTP",
      "inputSchema": {
        "type": "object",
        "properties": {
          "to": {"type": "string"},
          "subject": {"type": "string"},
          "body": {"type": "string"}
        },
        "required": ["to", "subject"]
      },
      "handler": "email_tool.py:send_email"
    }
  ],
  "hooks": {
    "pre_tool_call": ["hooks/audit.py:on_pre_tool"],
    "post_tool_call": ["hooks/audit.py:on_post_tool"]
  },
  "channels": [
    {
      "type": "slack",
      "class": "channel.py:SlackChannel",
      "config_schema": {
        "bot_token": {"type": "string"}
      }
    }
  ]
}
```

## Hook System

Two lifecycle events:
- `pre_tool_call(tool_name, args, plugin_config)` → `{"action": "continue"|"deny", "args": ..., "reason": "..."}`
- `post_tool_call(tool_name, args, result, plugin_config)` → `{"action": "continue", "result": "..."}`

## Components

| File | Purpose |
|------|---------|
| `py-agent/plugin_manager.py` | Discovers, loads, enables/disables plugins |
| `py-agent/plugin_hooks.py` | HookRegistry managing lifecycle callback chains |
| `plugins/` directory | Plugin installation root |

## Installation

- From GitHub: `skill_manage action=install source=https://github.com/xxx/plugin-name`
- From local path: `skill_manage action=install source=./my-plugin`
- From pip: `pip install cococat-plugin-xxx` (entry_points discovery)
