type: component
title: Knowledge Base Agent
created: 2025-04-07
summary: The Knowledge Base Agent manages CocoCat’s wiki‑based knowledge store, ensuring pages are properly structured with YAML frontmatter, indexed, and retrievable by other agents.
---
# Knowledge Base Agent

The **Knowledge Base Agent** is a dedicated component in [[Multi-Agent Architecture in CocoCat|CocoCat’s architecture]] that owns the [[KB system]] and all interactions with it. Its primary mission is to keep the system’s collective knowledge organized, consistent, and accessible.

## Core Functions
- **Page creation & validation** – enforces [[Wiki Knowledge Structure and YAML Frontmatter|YAML frontmatter]] conventions, checking required fields and types.
- **Indexing & search** – builds and maintains an index over all wiki pages, allowing fast retrieval by metadata or content.
- **Linking & consistency** – monitors [[wikilink]] references, flags broken links, and suggests connections between related pages.
- **Collaboration support** – tracks page versions and integrates with the wiki engine to enable collaborative editing.

## Interaction with Other Agents
- Provides an API for the [[Orchestrator Agent (Coco)]] and [[Worker agents]] to store execution logs, templates, and discovered facts.
- Retrieves structured information (e.g., planning rules, historical data) that the orchestrator uses when constructing [[DAG-based Task Dispatch|DAGs]].
- Serves as the single source of truth, ensuring that knowledge is not siloed within individual agents.

## Role in the Platform
By treating knowledge management as a first‑class concern, the Knowledge Base Agent enables CocoCat to learn from past executions, share context across tasks, and support human oversight through clear, structured documentation.

## Related Pages
- [[Wiki Knowledge Structure and YAML Frontmatter]]
- [[KB system]]
- [[Orchestrator Agent (Coco)]]
- [[Multi-Agent Architecture in CocoCat]]
- [[Worker agents]]