# Test knowledge document

## Key Points
- CocoCat uses a multi-agent architecture for task orchestration
- The KB system stores knowledge in wiki pages with YAML frontmatter
- Agents communicate via DAG-based task dispatch

## Architecture
The system has three main components:
1. Orchestrator agent (Coco) - plans and dispatches
2. Worker agents - execute tasks
3. Knowledge base agent - maintains wiki
