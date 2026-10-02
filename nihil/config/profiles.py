"""Local container profiles stored in ~/.nihil/profiles."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from nihil.config.defaults import NIHIL_HOME


PROFILE_FIELDS = (
    "image", "network", "workspace", "privileged", "vpn", "env",
    "disable_x11", "disable_wayland", "no_my_resources",
    "no_nihil_resources", "browser_ui", "browser_ui_port", "log", "tmux",
)
_BOOL_FIELDS = {
    "privileged", "disable_x11", "disable_wayland", "no_my_resources",
    "no_nihil_resources", "browser_ui", "log", "tmux",
}
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def profile_directory(directory: Optional[Path] = None) -> Path:
    return directory or NIHIL_HOME / "profiles"


def profile_path(name: str, directory: Optional[Path] = None) -> Path:
    if not _NAME_RE.fullmatch(name):
        raise ValueError("Profile name may only contain letters, digits, '_' and '-'.")
    return profile_directory(directory) / f"{name}.yml"


def validate_profile(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Profile must be a YAML mapping.")
    if data.get("version", 1) != 1:
        raise ValueError("Unsupported profile version (expected 1).")
    allowed = {"version", *PROFILE_FIELDS}
    unknown = [str(key) for key in data if key not in allowed]
    if unknown:
        raise ValueError(f"Unknown profile option(s): {', '.join(sorted(unknown))}.")
    if data.get("network") not in (None, "docker", "host", "disabled", "nat"):
        raise ValueError("Profile network must be docker, host, disabled or nat.")
    for field in _BOOL_FIELDS:
        if field in data and not isinstance(data[field], bool):
            raise ValueError(f"Profile option '{field}' must be true or false.")
    if "browser_ui_port" in data and (
        not isinstance(data["browser_ui_port"], int) or isinstance(data["browser_ui_port"], bool)
        or not 1 <= data["browser_ui_port"] <= 65535
    ):
        raise ValueError("Profile browser_ui_port must be between 1 and 65535.")
    if "env" in data and (
        not isinstance(data["env"], list) or not all(isinstance(item, str) for item in data["env"])
    ):
        raise ValueError("Profile env must be a list of KEY or KEY=VALUE strings.")
    for field in ("image", "workspace"):
        if field in data and not isinstance(data[field], str):
            raise ValueError(f"Profile option '{field}' must be a string.")
    if "vpn" in data and not isinstance(data["vpn"], (str, bool)):
        raise ValueError("Profile vpn must be true, false or a file path.")
    return data


def load_profile(name: str, directory: Optional[Path] = None) -> Dict[str, Any]:
    path = profile_path(name, directory)
    if not path.is_file():
        raise FileNotFoundError(f"Profile '{name}' not found in {path.parent}.")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in profile '{name}': {exc}") from exc
    return validate_profile(data)


def save_profile(name: str, values: Dict[str, Any], force: bool = False,
                 directory: Optional[Path] = None) -> Path:
    path = profile_path(name, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = validate_profile({"version": 1, **values})
    mode = "w" if force else "x"
    try:
        with path.open(mode, encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
    except FileExistsError as exc:
        raise FileExistsError(f"Profile '{name}' already exists. Use --force to overwrite it.") from exc
    return path


def list_profiles(directory: Optional[Path] = None) -> List[str]:
    root = profile_directory(directory)
    if not root.is_dir():
        return []
    return sorted(path.stem for path in root.glob("*.yml") if _NAME_RE.fullmatch(path.stem))
