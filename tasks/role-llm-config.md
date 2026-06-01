# Role-Specific LLM Configuration System

## Goal
Support per-role LLM model/parameter configuration for EXTRACT, QUERY, KEYWORDS, VLM.

## Plan

- [ ] Create `aurora_core/llm/role_config.py` — `LLMRoleConfigManager` (TOML load + env var override + apply_to)
- [ ] Create `aurora_core/llm/__init__.py` — module re-exports
- [ ] Update `aurora_core/config/settings.py` — add `llm_roles` field
- [ ] Update `configs/aurora.toml` — add `[llm_roles]` section
- [ ] Update `aurora_serve/server.py` — wire role configs at bootstrap
- [ ] Update `aurora_serve/knowledge/v2/service.py` — accept + apply role_configs
- [ ] Write tests in `tests/core/test_role_config.py`
- [ ] Run tests, verify, commit
