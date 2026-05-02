# Team Wiki Schema

## Page Types
- `entities/{slug}.md` — Named things (agents, tools, projects)
- `concepts/{slug}.md` — Ideas, patterns, techniques
- `sources/{slug}.md` — Source document summaries

## Page Format
Every page uses YAML frontmatter:

---
type: entity | concept | source
title: Human-readable title
created: YYYY-MM-DD
sources: ["source-filename"]
tags: ["tag1", "tag2"]
related: ["page-slug"]
---
