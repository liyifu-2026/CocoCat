# ADR-0002: ConfigStore as single source of truth for auth

**Date:** 2026-05-19
**Status:** accepted

**Context:** `ConfigStore` and `CredentialManager` independently read `config/auth.json`, each with their own cache. When `ConfigStore.set_auth()` wrote a new key (via API), `CredentialManager._data` remained stale until process restart.

**Decision:** `CredentialManager` now accepts an optional `config_store` parameter. When provided, it delegates `get()` to `config_store.get_auth()` instead of reading auth.json directly. The production bootstrap passes `ctx.config_store` to CredentialManager.

**Consequences:** Single source of truth for auth data. No cache staleness. Standalone CredentialManager (tests, non-app contexts) still supports direct file I/O as fallback.
