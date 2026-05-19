# ADR-0001: Eliminate get_ctx_static global singleton

**Date:** 2026-05-19
**Status:** accepted

**Context:** `get_ctx_static()` was called from 14 locations across tools, channel manager, and route helpers. Any code that called it was untestable without first calling `set_ctx_static(mock)` globally. Tests polluted each other's state.

**Decision:** Removed the module-level singleton entirely. All 14 call sites now receive their dependencies as explicit parameters (e.g., `store` for ConfigStore, `ctx` for ChannelManager). ToolCatalog accepts explicit `tavily_api_key`. Route helpers accept optional `store` parameter.

**Consequences:** Every module can be tested by constructing only its declared inputs. No global state manipulation needed in tests.
