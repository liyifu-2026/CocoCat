---
type: entity
title: CocoCat
created: 2026-05-02
summary: "Multi-agent team management system built with Rust + Python"
related: ["message-bus-architecture", "multi-agent-systems"]
---

# CocoCat

CocoCat is a multi-agent team management system built with Rust + Python.

## Architecture
- **Rust Core**: Agent process manager, [[message-bus-architecture]], JSON-RPC transport
- **Python Agents**: LLM-driven agents with ReAct loop, tools, sub-agents
- **Scenes**: Work contexts with scene-specific memory and skills

## Key Components
- AgentRegistry: manages multiple agent processes
- AgentLoop: ReAct (LLM -> tool -> observe -> repeat) execution engine
- [[message-bus-architecture]]: routes messages between agents via dispatch queue
- Scene System: injects scene context and env-tagged skills

## See Also
- [[message-bus-architecture]]
- [[multi-agent-systems]]
