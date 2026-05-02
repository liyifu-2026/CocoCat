---
type: concept
title: Multi-Agent Systems
created: 2026-05-02
---

# Multi-Agent Systems

## Key Principles
1. **Single Responsibility**: Each agent has a clear role and set of skills
2. **Scene Isolation**: Agents work within scenes that provide relevant context
3. **Message Passing**: Agents communicate through a central message bus
4. **Human Oversight**: Team leader coordinates and assigns tasks

## Communication Patterns
- **Direct**: Agent A sends task to Agent B via dispatch_task tool
- **Broadcast**: System messages to all agents via chat log
- **Hierarchical**: Leader delegates to employees, employees report back

## Skill Tags
- `public`: All agents must learn
- `private`: Specific agent masters
- `env`: Scene provides automatically
