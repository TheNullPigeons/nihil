"""Preset storage and compatibility with previous directory names."""

import pytest

from nihil.features import config_presets


@pytest.mark.parametrize("legacy_name", ["config-presets", "config-templates", "config-profiles"])
def test_preset_storage_keeps_legacy_files_accessible(tmp_path, monkeypatch, legacy_name):
    monkeypatch.setattr(config_presets, "PRESET_DIR", tmp_path / "presets")
    monkeypatch.setattr(config_presets, "_LEGACY_DIRS", tuple(
        tmp_path / name for name in ("config-presets", "config-templates", "config-profiles")
    ))
    config = tmp_path / "config.yml"
    config.write_text("network:\n  default_network: host\n")
    monkeypatch.setattr(config_presets, "CONFIG_FILE", config)
    legacy = tmp_path / legacy_name / "lab.yml"
    legacy.parent.mkdir()
    legacy.write_text("network:\n  default_network: docker\n")

    assert config_presets.list_presets() == ["lab"]
    assert config_presets.load_preset("lab").default_network == "docker"
    with pytest.raises(FileExistsError):
        config_presets.create_preset("lab")
    with pytest.raises(FileExistsError):
        config_presets.save_preset("lab")

    saved = config_presets.save_preset("lab", overwrite=True)
    assert saved == tmp_path / "presets" / "lab.yml"
    assert config_presets.load_preset("lab").default_network == "host"
    assert config_presets.list_presets() == ["lab"]
    assert legacy.is_file()
    created = config_presets.create_preset("new")
    assert created.parent == tmp_path / "presets"
    config_presets.delete_preset("lab")
    assert not saved.exists()
    assert not legacy.exists()
    assert config.read_text() == "network:\n  default_network: host\n"
