type: component
title: Orchestrator Agent (Coco)
created: 2025-04-07
summary: Coco is the orchestrator agent that plans tasks, decomposes high‑level goals, and dispatches work items to worker agents via a DAG. It is the central coordinator in CocoCat’s multi-agent architecture.
---
# Orchestrator Agent (Coco)

The **Orchestrator Agent**, named **Coco**, is the planning and coordination hub of the [[Multi-Agent Architecture in CocoCat|CocoCat system]]. It receives abstract objectives and translates them into a structured, executable plan.

## Responsibilities
- **Task decomposition** – breaks down complex goals into smaller, manageable work items.
- **DAG construction** – arranges tasks into a [[DAG-based Task Dispatch|directed acyclic graph]] that captures dependencies and parallelism.
- **Dispatch** – sends ready tasks to [[Worker agents]] and monitors their progress.
- **Error recovery** – re‑evaluates the DAG when failures occur, potentially re‑routing or retrying tasks.

## Working with Other Agents
- Coco communicates solely through the DAG‑based dispatch protocol, never calling workers directly outside this framework.
- It relies on the [[Knowledge Base Agent]] to store and retrieve planning templates, historical execution logs, and domain knowledge.
- Worker agents report completion status back to Coco, which updates the DAG state and triggers subsequent tasks.

## Integration in the System
Coco’s role is central to achieving the separation of concerns in the multi‑agent architecture. By isolating planning and dispatch from execution and knowledge maintenance, the system remains modular and easier to evolve.

## See Also
- [[DAG-based Task Dispatch]]
- [[Worker agents]]
- [[Knowledge Base Agent]]
- [[Multi-Agent Architecture in CocoCat]]