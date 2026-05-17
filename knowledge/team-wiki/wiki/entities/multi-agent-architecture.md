type: concept
title: Multi-Agent Architecture in CocoCat
created: 2025-04-07
summary: CocoCat employs a multi-agent architecture where specialized agents (orchestrator, workers, knowledge base agent) collaborate to handle complex tasks. This separation of concerns improves modularity, scalability, and maintainability.
---
# Multi-Agent Architecture in CocoCat

The CocoCat platform is designed around a **multi-agent paradigm**, meaning that distinct software agents with dedicated responsibilities work together to plan, execute, and document tasks. This architecture avoids a monolithic design and instead distributes intelligence across several agent types:

- **[[Orchestrator Agent (Coco)]]** – responsible for high‑level planning, decomposing tasks, and dispatching work to worker agents.
- **[[Worker agents]]** – perform the actual execution of tasks delivered by the orchestrator.
- **[[Knowledge Base Agent]]** – maintains the system’s wiki‑based knowledge store, ensuring information is structured, versioned, and queryable.

These agents communicate through a **[[DAG-based Task Dispatch]]** mechanism, where tasks and their dependencies are modeled as a directed acyclic graph. This allows for deterministic ordering, parallel execution where possible, and robust error handling.

## Rationale
The multi‑agent design was chosen to:
- Encapsulate distinct concerns (planning, execution, knowledge management).
- Enable independent development and scaling of each agent type.
- Simplify debugging by isolating responsibilities.
- Support future extension with new agent roles or capabilities.

## Related Pages
- [[DAG-based Task Dispatch]]
- [[Orchestrator Agent (Coco)]]
- [[Knowledge Base Agent]]
- [[Wiki Knowledge Structure and YAML Frontmatter]]