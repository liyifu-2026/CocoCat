# Skill: Knowledge Ingestion

Process source files and maintain the wiki knowledge base.

## KB Directory Layout
- `raw/sources/` — uploaded source files (immutable, read-only)
- `wiki/entities/{slug}.md` — named things (people, projects, tools, agents)
- `wiki/concepts/{slug}.md` — ideas, patterns, techniques, architectures
- `index.md` — content catalog (auto-maintained)
- `log.md` — append-only operation log

## Wiki Page Format
Every page uses YAML frontmatter:
```yaml
---
type: entity | concept
title: Human-readable title
created: YYYY-MM-DD
sources: ["source-filename"]
tags: ["tag1", "tag2"]
related: ["page-slug-1", "page-slug-2"]
summary: One-line summary of the page's content
---
```

Use `[[Wikilink]]` format for cross-references.

## Ingest Workflow
When processing a new source file from `raw/sources/`:

1. Read the source file
2. Analyze: identify main topic, related entities, related concepts
3. Create ONE wiki page for the main topic (entity or concept)
4. Scan ALL existing wiki pages for entities/concepts mentioned in the source
5. For each related existing page:
   - Append new information if the source reveals something new
   - Update `related` frontmatter to include the new page
   - Add `[[wikilink]]` in a "See Also" section
6. Update `index.md`: add entry for new page
7. Append to `log.md`: record what was done
8. If this is the first source for a new KB, generate `purpose.md` from the content

## Query Workflow
When answering questions using the wiki:
1. Read `index.md` first to find relevant pages
2. Drill into specific pages for details
3. Synthesize answers with [[wikilink]] citations
