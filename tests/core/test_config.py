from aurora_core.config.base import BaseParameters
from aurora_core.config.loader import load_toml_config
from aurora_core.config.settings import Settings


from dataclasses import dataclass


def test_base_parameters_from_dict():
    @dataclass
    class MyParams(BaseParameters):
        name: str
        value: int = 10

    data = {"name": "test", "value": 42, "extra": "ignored"}
    params = MyParams.from_dict(data)
    assert params.name == "test"
    assert params.value == 42


def test_load_toml_config(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text('app_name = "Test"\nport = 9000\n')
    data = load_toml_config(str(config_path))
    assert data["app_name"] == "Test"
    assert data["port"] == 9000


def test_settings_from_toml(tmp_path):
    config_path = tmp_path / "test.toml"
    config_path.write_text(
        'app_name = "TestApp"\nport = 9000\n[[llm_configs]]\nmodel_name = "gpt-4"\nmodel_type = "openai"\n'
    )
    settings = Settings.from_toml(str(config_path))
    assert settings.app_name == "TestApp"
    assert settings.port == 9000
    assert len(settings.llm_configs) == 1
    assert settings.llm_configs[0]["model_name"] == "gpt-4"
