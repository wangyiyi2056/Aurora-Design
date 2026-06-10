"""Tests for extraction configuration dataclasses.

Covers immutability, defaults, from_dict, and effective-types logic.
"""

import pathlib
import tempfile

import pytest

from aurora_ext.rag.extraction.config import (
    AddonParams,
    ExtractionConfig,
    EntityTypeConfig,
    KGExtractionFullConfig,
)


# ── ExtractionConfig ────────────────────────────────────────────────


class TestExtractionConfig:
    def test_defaults(self) -> None:
        cfg = ExtractionConfig()
        assert cfg.entity_extract_max_gleaning == 2
        assert cfg.relation_extract_max_gleaning == 2
        assert cfg.max_parallel_extract == 5
        assert cfg.enable_incremental_extract is True
        assert cfg.max_total_records == 100
        assert cfg.max_entity_records == 40
        assert cfg.use_json is False
        assert cfg.enable_cache is True

    def test_immutable(self) -> None:
        cfg = ExtractionConfig()
        with pytest.raises(AttributeError):
            cfg.max_parallel_extract = 10  # type: ignore[misc]

    def test_max_gleaning_property(self) -> None:
        cfg = ExtractionConfig(
            entity_extract_max_gleaning=3,
            relation_extract_max_gleaning=5,
        )
        assert cfg.max_gleaning == 5

    def test_from_dict_empty(self) -> None:
        cfg = ExtractionConfig.from_dict({})
        assert cfg == ExtractionConfig()

    def test_from_dict_partial(self) -> None:
        cfg = ExtractionConfig.from_dict({
            "max_parallel_extract": 8,
            "use_json": True,
        })
        assert cfg.max_parallel_extract == 8
        assert cfg.use_json is True
        # Others remain at defaults.
        assert cfg.entity_extract_max_gleaning == 2

    def test_from_dict_ignores_unknown_keys(self) -> None:
        cfg = ExtractionConfig.from_dict({
            "max_parallel_extract": 3,
            "nonexistent_key": "ignored",
        })
        assert cfg.max_parallel_extract == 3

    def test_from_dict_none(self) -> None:
        cfg = ExtractionConfig.from_dict(None)  # type: ignore[arg-type]
        assert cfg == ExtractionConfig()


# ── EntityTypeConfig ────────────────────────────────────────────────


class TestEntityTypeConfig:
    def test_defaults(self) -> None:
        cfg = EntityTypeConfig()
        assert cfg.custom_types == ()
        assert cfg.type_prompt_file is None
        assert "Person" in cfg.default_types
        assert "Organization" in cfg.default_types

    def test_effective_types_uses_custom_when_set(self) -> None:
        cfg = EntityTypeConfig(custom_types=("Foo", "Bar"))
        assert cfg.effective_types == ("Foo", "Bar")

    def test_effective_types_falls_back_to_default(self) -> None:
        cfg = EntityTypeConfig()
        assert cfg.effective_types == cfg.default_types

    def test_build_guidance_from_list(self) -> None:
        cfg = EntityTypeConfig(custom_types=("Person", "Technology"))
        guidance = cfg.build_entity_types_guidance()
        assert "Person" in guidance
        assert "Technology" in guidance
        assert "Classify each entity" in guidance

    def test_build_guidance_from_file(self) -> None:
        content = "Custom guidance:\n- Foo\n- Bar"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            cfg = EntityTypeConfig(type_prompt_file=path)
            guidance = cfg.build_entity_types_guidance()
            assert guidance == content
        finally:
            pathlib.Path(path).unlink()

    def test_build_guidance_missing_file_falls_back(self) -> None:
        cfg = EntityTypeConfig(
            custom_types=("Alpha",),
            type_prompt_file="/nonexistent/path.txt",
        )
        guidance = cfg.build_entity_types_guidance()
        assert "Alpha" in guidance

    def test_build_relation_guidance_none_when_empty(self) -> None:
        cfg = EntityTypeConfig()
        assert cfg.build_relation_types_guidance() is None

    def test_build_relation_guidance_with_types(self) -> None:
        cfg = EntityTypeConfig(custom_relation_types=("works_for", "uses"))
        guidance = cfg.build_relation_types_guidance()
        assert guidance is not None
        assert "works_for" in guidance
        assert "uses" in guidance

    def test_from_dict(self) -> None:
        data = {
            "entity_types": {
                "custom_types": ["Person", "Location"],
                "type_prompt_file": None,
            },
            "relation_types": {
                "custom_types": ["works_for"],
            },
        }
        cfg = EntityTypeConfig.from_dict(data)
        assert cfg.custom_types == ("Person", "Location")
        assert cfg.custom_relation_types == ("works_for",)

    def test_from_dict_empty(self) -> None:
        cfg = EntityTypeConfig.from_dict({})
        assert cfg.custom_types == ()

    def test_immutable(self) -> None:
        cfg = EntityTypeConfig()
        with pytest.raises(AttributeError):
            cfg.custom_types = ("X",)  # type: ignore[misc]


# ── AddonParams ─────────────────────────────────────────────────────


class TestAddonParams:
    def test_defaults(self) -> None:
        addon = AddonParams()
        assert addon.language == "English"
        assert addon.entity_types_guidance is None
        assert addon.relation_types_guidance is None

    def test_from_dict_language_section(self) -> None:
        data = {"language": {"output_language": "Chinese"}}
        addon = AddonParams.from_dict(data)
        assert addon.language == "Chinese"

    def test_from_dict_string_language(self) -> None:
        data = {"language": "Japanese"}
        addon = AddonParams.from_dict(data)
        assert addon.language == "Japanese"

    def test_from_dict_with_guidance(self) -> None:
        data = {
            "language": {"output_language": "Korean"},
            "entity_types_guidance": "Custom entity guidance",
            "relation_types_guidance": "Custom relation guidance",
        }
        addon = AddonParams.from_dict(data)
        assert addon.language == "Korean"
        assert addon.entity_types_guidance == "Custom entity guidance"
        assert addon.relation_types_guidance == "Custom relation guidance"

    def test_from_dict_empty(self) -> None:
        addon = AddonParams.from_dict({})
        assert addon == AddonParams()

    def test_immutable(self) -> None:
        addon = AddonParams()
        with pytest.raises(AttributeError):
            addon.language = "French"  # type: ignore[misc]


# ── KGExtractionFullConfig ─────────────────────────────────────────


class TestKGExtractionFullConfig:
    def test_defaults(self) -> None:
        cfg = KGExtractionFullConfig()
        assert cfg.extraction == ExtractionConfig()
        assert cfg.entity_types == EntityTypeConfig()
        assert cfg.addon == AddonParams()

    def test_from_toml_dict(self) -> None:
        data = {
            "entity_extract_max_gleaning": 3,
            "max_parallel_extract": 10,
            "language": {"output_language": "Chinese"},
            "entity_types": {
                "custom_types": ["Person", "API"],
            },
            "relation_types": {
                "custom_types": ["uses", "develops"],
            },
        }
        cfg = KGExtractionFullConfig.from_toml_dict(data)
        assert cfg.extraction.entity_extract_max_gleaning == 3
        assert cfg.extraction.max_parallel_extract == 10
        assert cfg.addon.language == "Chinese"
        assert cfg.entity_types.custom_types == ("Person", "API")
        assert cfg.entity_types.custom_relation_types == ("uses", "develops")

    def test_from_toml_dict_empty(self) -> None:
        cfg = KGExtractionFullConfig.from_toml_dict({})
        assert cfg == KGExtractionFullConfig()

    def test_from_toml_dict_none(self) -> None:
        cfg = KGExtractionFullConfig.from_toml_dict(None)  # type: ignore[arg-type]
        assert cfg == KGExtractionFullConfig()

    def test_immutable(self) -> None:
        cfg = KGExtractionFullConfig()
        with pytest.raises(AttributeError):
            cfg.extraction = ExtractionConfig()  # type: ignore[misc]
