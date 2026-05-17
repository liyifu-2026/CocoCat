type: concept
title: DAG-based Task Dispatch
created: 2025-04-07
summary: The orchestrator agent dispatches tasks to worker agents using a directed acyclic graph (DAG) to model dependencies. This communication pattern ensures correct execution order, enables parallelism, and supports reliable workflows.
---
# DAG-based Task Dispatch

In CocoCat, task orchestration relies on a **directed acyclic graph (DAG)** model. Tasks are represented as nodes, and edges denote dependencies – a task can only start after all its predecessors have completed. The [[Orchestrator Agent (Coco)]] builds the DAG during planning and then dispatches tasks to [[Worker agents]] accordingly.

## Key Properties
- **Deterministic ordering**  
  By respecting the DAG’s partial order, the orchestrator guarantees that no task runs before its prerequisites are satisfied.
- **Parallel execution**  
  Independent tasks (no dependency chain between them) can be dispatched simultaneously to different workers, improving throughput.
- **Error handling & retries**  
  The DAG structure allows pin‑pointing failed tasks and restarting only the affected sub‑graph, without re‑executing already completed work.

## Dispatch Protocol
1. The orchestrator parses a high‑level goal into a DAG of concrete work items.
2. The DAG is traversed; source nodes (with no dependencies) are sent to available worker agents.
3. Upon completion of a task, the worker reports back, and the orchestrator updates the graph state, enabling newly unblocked tasks.
4. The process repeats until all nodes have been processed or a terminal failure occurs.

## Relationship to System Architecture
This dispatch mechanism is the backbone of CocoCat’s [[Multi-Agent Architecture in CocoCat|multi-agent architecture]], linking planning with execution. It ensures that the system can handle complex, multi‑step workflows while maintaining clear dependency and state management.

## See Also
- [[Orchestrator Agent (Coco)]]
- [[Worker agents]]
- [[Multi-Agent Architecture in CocoCat]]