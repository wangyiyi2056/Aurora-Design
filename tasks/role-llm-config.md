# Role-Specific LLM Configuration System

## Goal
Support per-role LLM model/parameter configuration for EXTRACT, QUERY, KEYWORDS, VLM.

## Plan

- [x] Create `aurora_core/llm/role_config.py` — `LLMRoleConfigManager` (TOML load + env var override + apply_to)
- [x] Create `aurora_core/llm/__init__.py` — module re-exports
- [x] Update `aurora_core/config/settings.py` — add `llm_roles` field
- [x] Update `configs/aurora.toml` — add `[llm_roles]` section (at file end to avoid TOML table scoping issues)
- [x] Update `aurora_serve/server.py` — wire role configs at bootstrap
- [x] Update `aurora_serve/knowledge/v2/service.py` — accept + apply role_configs
- [x] Write tests in `tests/core/test_role_config.py`
- [x] Run tests, verify, commit

## Review

**Commit**: `5ecd44c` — feat: implement role-specific LLM configuration system

**Test results**: 37 new tests, 62 total core tests pass (0 failures).
Pre-existing serve/ext test failures are unrelated (ImportError on `RerankerConfig`, `ExportScope`).

**Architecture decision**: Layered on top of existing `LLMRoleRegistry` (model/roles.py) rather than replacing it. `LLMRoleConfigManager` is a pure configuration layer that resolves TOML + env vars into `RoleLLMConfig` objects and delegates to the registry's `update_role_config`.

**TOML placement**: `[llm_roles]` section must be at the end of `aurora.toml` because TOML table headers scope all subsequent key-value pairs until the next header.
