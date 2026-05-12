# Knowledge Base Ingestion Pipeline Design

## Problem
CocoCat's knowledge base system has no automated ingestion. Wiki pages must be created manually via `write_file`. There's no pipeline to process raw source documents into structured wiki pages with metadata, cross-references, and catalog management.

## Solution
Implement llm-wiki's two-stage LLM ingestion pipeline as an agent tool:
1. **Phase 1 (Analysis)**: LLM reads source → extracts entities, concepts, relationships
2. **Phase 2 (Generation)**: LLM takes analysis → generates wiki pages with YAML frontmatter

## Storage Layout
```
knowledge/{kb}/
├── schema.md              # KB structure rules (page types, conventions)
├── purpose.md             # KB goals and scope
├── index.md               # Auto-generated content catalog
├── log.md                 # Append-only operation log
└── wiki/
    ├── entities/{slug}.md  # Entity pages with YAML frontmatter
    ├── concepts/{slug}.md  # Concept pages with YAML frontmatter
    └── sources/{slug}.md   # Source summary pages
```

## Page Format (YAML Frontmatter)
```markdown
---
type: entity|concept|source
title: Page Title
created: 2026-05-02
sources: ["source-file.md"]
tags: ["tag1", "tag2"]
related: ["other-page"]
---

Content in markdown...
```

## Tool: ingest_to_kb
- Agent-callable tool that takes `kb_id`, `source_path`
- Reads the source file
- Phase 1: LLM analysis
- Phase 2: LLM generates pages
- Writes pages, updates index.md, appends log.md
- Returns summary of what was created

## Phased Implementation
1. YAML frontmatter support + page model
2. Two-stage ingestion pipeline
3. index.md + log.md auto-maintenance
4. Agent tool integration
