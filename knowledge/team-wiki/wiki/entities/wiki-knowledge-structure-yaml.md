type: concept
title: Wiki Knowledge Structure and YAML Frontmatter
created: 2025-04-07
summary: CocoCat’s knowledge base stores information as wiki pages, each containing structured YAML frontmatter and free‑form body text. This format bridges machine‑readable metadata and human‑friendly documentation, facilitating both automated queries and manual curation.
---
# Wiki Knowledge Structure and YAML Frontmatter

The [[KB system]] in CocoCat persists knowledge as a collection of wiki pages. Every page is designed with **YAML frontmatter** – a block of structured metadata at the top of the file, followed by the page’s main content written in plain text or Markdown.

## Frontmatter Specification
A typical page begins with delimiters `---` and contains key‑value pairs. Common fields include:
- `type` – page category (e.g., `concept`, `component`, `process`)
- `title` – human‑readable name
- `created` – date of creation
- `summary` – short description for indexing and previews
- `tags` – keywords for search and grouping

Additional keys may be defined per page type. The schema is validated by the [[Knowledge Base Agent]] on creation or update.

## Benefits
- **Machine‑readable** – the KB agent can index, search, and retrieve pages based on metadata fields.
- **Human‑readable** – content remains accessible and editable for collaborators, supporting manual curation.
- **Versionable** – structured metadata and text content together enable diffing and history tracking within the wiki store.

## Role of the KB Agent
The [[Knowledge Base Agent]] is responsible for:
- Enforcing frontmatter conventions and validation rules.
- Indexing pages so that other agents can query the KB.
- Maintaining consistency and linking between pages.

This approach makes the knowledge base a central, trusted component of the [[Multi-Agent Architecture in CocoCat|CocoCat architecture]].

## Related Pages
- [[Knowledge Base Agent]]
- [[KB system]]
- [[Multi-Agent Architecture in CocoCat]]