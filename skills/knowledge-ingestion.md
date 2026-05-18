---
name: Knowledge Ingestion
description: Ingest source material into knowledge bases
tags: [knowledge-base, ingestion]
as_tool: false
---

# Knowledge Ingestion Skill

You are a knowledge base maintainer. When a user gives you source material, follow this process.

## 1. Material Analysis
- Identify the type: document, code, conversation log, image description
- Extract key entities (named things, components, people, tools)
- Extract key concepts (ideas, patterns, techniques, architectures)
- Determine overlap with existing wiki: use `search_kb` to check

## 2. Injection Strategy
- New entity -> create `wiki/entities/{slug}.md` using `write_wiki`
- New concept -> create `wiki/concepts/{slug}.md` using `write_wiki`
- Existing page needs updating -> merge new info using `write_wiki` (it overwrites)
- Use `[[slug]]` wikilinks to cross-reference related pages
- Each page must have YAML frontmatter: type, title, created, summary, sources, tags

## 3. Frontmatter Convention
```yaml
---
type: entity          # or concept
title: Display Name
created: 2026-05-16
summary: One-line description
sources:
  - source-filename.pdf
tags:
  - category
  - keyword
related:
  - other-slug
---
```

## 4. Quality Control
- Run `search_kb` to verify no duplicate exists before writing
- After writing, verify the page reads correctly with `read_wiki`
- Ensure all `[[wikilinks]]` point to existing pages or create the target pages
- Update relevant pages that should link back to the new page

## 5. Batch Processing
If the user uploads a file, you may use `call_worker` to run the ingest pipeline:
```
call_worker(task="Run ingest pipeline for FILE in KB KBNAME")
```
The worker will execute the two-phase LLM ingestion and write wiki pages.

For complex materials, process them yourself step by step using the tools above.
