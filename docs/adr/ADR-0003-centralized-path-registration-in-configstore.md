# ADR-0003: Centralized path registration in ConfigStore

**Date:** 2026-05-19
**Status:** accepted

**Context:** 32+ hardcoded path strings (`"agents/"`, `"runs/cron"`, `"knowledge/"`, etc.) scattered across 7+ modules. Renaming a directory required touching 10+ files.

**Decision:** Added directory properties to ConfigStore: `agents_dir`, `runs_dir`, `cron_dir`, `knowledge_dir`, `memory_dir`, `scenes_dir`, `skills_dir`, `todos_path`. Each supports a `COCOCAT_*_DIR` environment variable override. Updated bootstrap.py and route files to use these properties.

**Consequences:** Single location for path configuration. Deployment customization via environment variables. Some internal module paths (KB subdirectories like `wiki/`, `raw/`) remain as sub-path conventions within a given base dir.
