# Team Wiki Schema

This schema tells the LLM how to maintain this wiki.
It is a living document — co-evolve it with the LLM as the wiki grows.

## Page Types

- `entities/{slug}.md` — Named things (agents, tools, projects, people)
- `concepts/{slug}.md` — Ideas, patterns, techniques, architectures

## Page Format

Every page uses YAML frontmatter:

```yaml
---
type: entity | concept
title: Human-readable title
created: YYYY-MM-DD
sources: ["source-filename"]
tags: ["tag1", "tag2"]
related: ["page-slug-1", "page-slug-2"]
summary: "One-line summary of this page's content"
---
```

Use `[[Wikilink]]` format for cross-references. Use `summary` field for index generation.

## Ingest Workflow

When ingesting a new source:

1. Read the source file from `raw/sources/`
2. Create ONE new wiki page for the main topic
3. Then scan ALL existing wiki pages for entities and concepts mentioned in the source
4. For each related existing page, UPDATE its content:
   - Add new information if the source reveals something new
   - Update the `related` frontmatter to include the new page
   - Add a `[[wikilink]]` in the "See Also" section
5. A single source typically touches 5-15 wiki pages total
6. Never delete existing content — append or revise

## Query Workflow

When answering questions using the wiki:

1. Read `index.md` first to find relevant pages
2. Drill into specific pages for details
3. Synthesize answers with `[[wikilink]]` citations
4. Valuable answers should be filed back via `save_to_kb`

## Lint Workflow

Periodically health-check the wiki:

- Orphan pages with no inbound [[links]]
- Broken [[wikilinks]] pointing to nonexistent pages
- Contradictions between pages
- Missing cross-references between related topics
- Stale claims superseded by newer sources
