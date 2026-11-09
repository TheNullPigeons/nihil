"""Named presets based on the user's Nihil configuration."""

import os
import re
from pathlib import Path

import yaml

from nihil.config import CONFIG_FILE, NIHIL_HOME, NihilConfig


PRESET_DIR = NIHIL_HOME / "presets"
_LEGACY_DIRS = (NIHIL_HOME / "config-presets", NIHIL_HOME / "config-templates", NIHIL_HOME / "config-profiles")
SETUP_DIR = NIHIL_HOME / "my-resources" / "setup"
_PRESET_OPTIONS_KEY = "container"
_BOOLEAN_OPTIONS = {
    "privileged", "workspace_here", "disable_x11", "disable_wayland",
    "no_my_resources", "no_nihil_resources", "browser_ui", "log", "tmux", "no_shell",
}
_STRING_OPTIONS = {"image", "workspace", "network", "browser_ui_password"}


def _preset_path(name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError("Preset names must start with a letter or digit and contain only letters, digits, '.', '_' or '-'.")
    return PRESET_DIR / f"{name}.yml"


def _find_preset(name: str) -> Path:
    path = _preset_path(name)
    if path.is_file():
        return path
    for directory in _LEGACY_DIRS:
        legacy_path = directory / path.name
        if legacy_path.is_file():
            return legacy_path
    raise FileNotFoundError(f"Config preset '{name}' does not exist.")


def list_presets() -> list[str]:
    names = {path.stem for directory in (*_LEGACY_DIRS, PRESET_DIR) for path in directory.glob("*.yml")}
    return sorted(names)


def create_preset(name: str, options: dict | None = None, config_data: dict | None = None) -> Path:
    """Create a preset from edited config data and container options."""
    NihilConfig.from_file(CONFIG_FILE)
    if options and "browser_ui_port" in options and not 1 <= options["browser_ui_port"] <= 65535:
        raise ValueError("Browser UI port must be between 1 and 65535.")
    if options:
        options = _validate_container_options(options, name)
    path = _preset_path(name)
    if any((directory / path.name).exists() for directory in _LEGACY_DIRS):
        raise FileExistsError(f"Preset '{name}' already exists.")
    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    if config_data is None and not options:
        content = CONFIG_FILE.read_bytes()
    else:
        data = config_data if config_data is not None else (yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {})
        selected = dict(data)
        if options:
            selected[_PRESET_OPTIONS_KEY] = options
        content = yaml.safe_dump(selected, sort_keys=False, allow_unicode=True).encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as preset:
        preset.write(content)
    return path


def save_preset(name: str, overwrite: bool = False) -> Path:
    path = _preset_path(name)
    if not overwrite and (path.exists() or any((directory / path.name).exists() for directory in _LEGACY_DIRS)):
        raise FileExistsError(f"Preset '{name}' already exists; use --force to replace it.")
    NihilConfig.from_file(CONFIG_FILE)
    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    content = CONFIG_FILE.read_bytes()
    if path.exists():
        path.chmod(0o600)
        path.write_bytes(content)
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as preset:
            preset.write(content)
    return path


def preset_path(name: str) -> Path:
    return _find_preset(name)


def delete_preset(name: str) -> None:
    path = _preset_path(name)
    paths = [path, *(directory / path.name for directory in _LEGACY_DIRS)]
    existing = [candidate for candidate in paths if candidate.exists()]
    if not existing:
        raise FileNotFoundError(f"Config preset '{name}' does not exist.")
    for candidate in existing:
        candidate.unlink()


def load_preset(name: str) -> NihilConfig:
    return NihilConfig.from_file(_find_preset(name))


def load_preset_options(name: str) -> dict:
    try:
        data = yaml.safe_load(_find_preset(name).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(f"Cannot read config preset '{name}': {e}") from e
    options = data.get(_PRESET_OPTIONS_KEY, {})
    return _validate_container_options(options, name)


def _validate_container_options(options: dict, name: str) -> dict:
    if not isinstance(options, dict):
        raise ValueError(f"Invalid container options in preset '{name}'.")
    if set(options) - (_BOOLEAN_OPTIONS | _STRING_OPTIONS | {"vpn", "env", "browser_ui_resolution", "browser_ui_port", "scripts"}):
        raise ValueError(f"Unknown container option in preset '{name}'.")
    for key in _BOOLEAN_OPTIONS:
        if key in options and options[key] is not None and not isinstance(options[key], bool):
            raise ValueError(f"Invalid {key} option in preset '{name}'.")
    for key in _STRING_OPTIONS:
        if key in options and options[key] is not None and (not isinstance(options[key], str) or (key == "network" and not options[key])):
            raise ValueError(f"Invalid {key} option in preset '{name}'.")
    if "vpn" in options and options["vpn"] is not None and not isinstance(options["vpn"], (bool, str)):
        raise ValueError(f"Invalid vpn option in preset '{name}'.")
    if "env" in options and options["env"] is not None and (not isinstance(options["env"], list) or not all(isinstance(item, str) for item in options["env"])):
        raise ValueError(f"Invalid env option in preset '{name}'.")
    if "browser_ui_resolution" in options and options["browser_ui_resolution"] is not None and options["browser_ui_resolution"] not in ("1280x720", "1920x1080", "2560x1440"):
        raise ValueError(f"Invalid browser_ui_resolution option in preset '{name}'.")
    if "browser_ui_port" in options and options["browser_ui_port"] is not None and (not isinstance(options["browser_ui_port"], int) or isinstance(options["browser_ui_port"], bool) or not 1 <= options["browser_ui_port"] <= 65535):
        raise ValueError(f"Invalid browser_ui_port option in preset '{name}'.")
    if "scripts" in options and options["scripts"] is not None and (not isinstance(options["scripts"], list) or not all(isinstance(item, str) for item in options["scripts"])):
        raise ValueError(f"Invalid scripts option in preset '{name}'.")
    return options


def load_preset_scripts(name: str, options: dict | None = None) -> list[Path] | None:
    options = options if options is not None else load_preset_options(name)
    if "scripts" not in options or options["scripts"] is None:
        return None
    root = SETUP_DIR.resolve()
    scripts = []
    for relative_path in options["scripts"]:
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root) or path.suffix != ".sh" or not path.is_file():
            raise ValueError(f"Invalid or missing startup script in preset '{name}': {relative_path}")
        scripts.append(path)
    return scripts


def edit_preset_config() -> tuple[dict, dict] | None:
    config = NihilConfig.from_file(CONFIG_FILE)
    from nihil.features.preset_config_selector import run_config_editor

    return run_config_editor(config._data)


def choose_preset() -> str | None:
    presets = list_presets()
    if not presets:
        return None
    from rich.console import Console
    from rich.prompt import IntPrompt

    console = Console()
    for index, name in enumerate(presets, 1):
        console.print(f"[cyan]{index}.[/] {name}")
    try:
        choice = IntPrompt.ask(
            "Select a config preset",
            choices=[str(index) for index in range(1, len(presets) + 1)],
            default=1,
        )
    except KeyboardInterrupt:
        return None
    return presets[choice - 1]
